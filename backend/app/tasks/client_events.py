import json
import os
import time
import hashlib
from typing import Any, Dict, List, Optional, Tuple

from app.core.cache import cache
from app.core.celery_app import apply_async_with_context, celery_app
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.all_models import ClientEvent as ClientEventRow
from app.tasks.reco_profile import rebuild_user_persona

try:
    from prometheus_client import Counter

    CLIENT_EVENT_DRAIN_TOTAL = Counter(
        "aiseek_client_event_drain_total",
        "Client event drain attempts",
        ["stream", "outcome"],
    )
    CLIENT_EVENT_DRAINED_TOTAL = Counter(
        "aiseek_client_event_drained_total",
        "Client event drained messages",
        ["stream"],
    )
    CLIENT_EVENT_PERSISTED_TOTAL = Counter(
        "aiseek_client_event_persisted_total",
        "Client event persisted rows",
        ["stream"],
    )
except Exception:
    CLIENT_EVENT_DRAIN_TOTAL = None
    CLIENT_EVENT_DRAINED_TOTAL = None
    CLIENT_EVENT_PERSISTED_TOTAL = None


_CE_RT = {"exp": 0.0, "cfg": {}}


def _client_events_runtime() -> Dict[str, Any]:
    now = time.time()
    try:
        if float(_CE_RT.get("exp") or 0) > now and isinstance(_CE_RT.get("cfg"), dict):
            return _CE_RT["cfg"]
    except Exception:
        pass
    try:
        from app.observability.runtime_client_events import read_runtime_client_events

        cfg = read_runtime_client_events()
    except Exception:
        cfg = {}
    try:
        _CE_RT["cfg"] = cfg
        _CE_RT["exp"] = now + 1.0
    except Exception:
        pass
    return cfg


def _now_ms() -> int:
    return int(time.time() * 1000)


def _safe_event_name(name: Any) -> str:
    s = str(name or "").strip()
    if not s:
        return ""
    if len(s) > 80:
        s = s[:80]
    return s


def _safe_str(v: Any, max_len: int) -> str:
    s = str(v or "").strip()
    if not s:
        return ""
    if len(s) > int(max_len or 0):
        return s[: int(max_len or 0)]
    return s


def _safe_data(data: Any, max_bytes: int) -> Optional[Dict[str, Any]]:
    if data is None:
        return None
    if not isinstance(data, dict):
        return None
    try:
        raw = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        return None
    if len(raw.encode("utf-8", "ignore")) <= int(max_bytes or 0):
        return data
    return None


def _extract_user_id(data: Optional[Dict[str, Any]]) -> Optional[int]:
    if not data:
        return None
    v = data.get("user_id")
    if v is None:
        return None
    try:
        s = str(v).strip()
        if s.isdigit():
            uid = int(s)
            return uid if uid > 0 else None
    except Exception:
        return None
    return None


def _ensure_group(r, stream: str, group: str) -> None:
    try:
        r.xgroup_create(str(stream), str(group), id="0", mkstream=True)
    except Exception:
        pass


def _norm_query(q: Any) -> str:
    s = str(q or "").strip().lower()
    if not s:
        return ""
    if len(s) > 64:
        s = s[:64]
    return s


def _q_sig(q: str) -> str:
    try:
        return hashlib.sha1(str(q).encode("utf-8")).hexdigest()[:12]
    except Exception:
        return ""


def _sample_ok(key: str, rate: float) -> bool:
    try:
        r = float(rate or 0.0)
    except Exception:
        r = 0.0
    if r >= 1.0:
        return True
    if r <= 0.0:
        return False
    try:
        h = hashlib.sha1(str(key).encode("utf-8")).hexdigest()
        v = int(h[:8], 16)
        thr = int(r * 0xFFFFFFFF)
        return v <= thr
    except Exception:
        return False


@celery_app.task(bind=True)
def drain_client_event_stream(self, max_messages: int = 2000, stream_override: Optional[str] = None) -> dict:
    s = get_settings()
    rt = _client_events_runtime()
    stream = str(stream_override or getattr(s, "CLIENT_EVENT_STREAM_KEY", "events:client") or "events:client")
    group = str(getattr(s, "CLIENT_EVENT_STREAM_GROUP", "client_events") or "client_events")
    consumer = _safe_str(os.getenv("HOSTNAME") or "worker", 32) + ":" + _safe_str(str(os.getpid()), 12)
    maxlen = int(getattr(s, "CLIENT_EVENT_STREAM_MAXLEN", 200000) or 200000)
    max_data_bytes = int(getattr(s, "CLIENT_EVENT_MAX_DATA_BYTES", 8192) or 8192)
    persona_debounce_sec = int(getattr(s, "PERSONA_REBUILD_DEBOUNCE_SEC", 600) or 600)
    apply_hot = bool(getattr(s, "CLIENT_EVENT_APPLY_HOT_ENABLED", False))
    apply_search_hot = bool(getattr(s, "SEARCH_HOT_ENABLED", False))
    apply_eng = bool(getattr(s, "ENGAGEMENT_COUNTERS_ENABLED", True))
    persist_enabled = bool(rt.get("persist_enabled")) if rt.get("persist_enabled") is not None else bool(getattr(s, "CLIENT_EVENT_PERSIST_ENABLED", True))
    persist_strict = bool(rt.get("persist_strict")) if rt.get("persist_strict") is not None else bool(getattr(s, "CLIENT_EVENT_PERSIST_STRICT", True))
    persist_rate_raw = rt.get("persist_sample_rate") if rt.get("persist_sample_rate") is not None else getattr(s, "CLIENT_EVENT_PERSIST_SAMPLE_RATE", 1.0)
    persist_rate = float(persist_rate_raw) if persist_rate_raw is not None else 1.0
    st_key = "events:client:drain:status:" + _safe_str(stream.replace(":", "_"), 80)

    r = cache.redis()
    if not r:
        out = {"ok": False, "error": "redis_unavailable"}
        try:
            if CLIENT_EVENT_DRAIN_TOTAL:
                CLIENT_EVENT_DRAIN_TOTAL.labels(stream, "redis_unavailable").inc(1)
        except Exception:
            pass
        try:
            cache.set_json(st_key, out, ttl=30)
        except Exception:
            pass
        return out

    _ensure_group(r, stream, group)
    try:
        msgs = r.xreadgroup(group, consumer, {stream: ">"}, count=int(max_messages or 0) or 2000)
    except Exception:
        msgs = []
    if not msgs:
        out = {"ok": True, "drained": 0}
        try:
            if CLIENT_EVENT_DRAIN_TOTAL:
                CLIENT_EVENT_DRAIN_TOTAL.labels(stream, "empty").inc(1)
        except Exception:
            pass
        try:
            cache.set_json(st_key, out, ttl=30)
        except Exception:
            pass
        return out

    rows: List[ClientEventRow] = []
    ack_ids: List[str] = []
    user_ids: List[int] = []
    hot_ops: List[Tuple[int, int, float, bool]] = []
    search_ops: List[Tuple[str, int]] = []
    eng_ops: List[Tuple[str, int, int]] = []

    def add_uid(uid: int) -> None:
        if uid <= 0:
            return
        if uid not in user_ids:
            user_ids.append(uid)

    for _, items in msgs:
        for mid, fields in items:
            try:
                raw = fields.get("payload") if isinstance(fields, dict) else None
                if not raw:
                    continue
                ev = json.loads(raw)
                if not isinstance(ev, dict):
                    continue
                name = _safe_event_name(ev.get("name"))
                if not name:
                    continue
                ts = ev.get("ts")
                try:
                    ts2 = float(ts) / 1000.0 if float(ts) > 10_000_000_000 else float(ts)
                except Exception:
                    ts2 = float(_now_ms()) / 1000.0
                data = _safe_data(ev.get("data"), max_data_bytes)
                uid = _extract_user_id(data)
                if apply_hot:
                    try:
                        nm = str(ev.get("name") or "").strip()
                        if nm == "player:watch" and uid and data:
                            pid = int(data.get("post_id") or 0)
                            if pid > 0:
                                wt = data.get("watch_time_sec")
                                dur = data.get("duration_sec")
                                comp = bool(data.get("completed")) if data.get("completed") is not None else False
                                dwell = data.get("dwell_ms")
                                from app.services.hot_counter_service import compute_view_points

                                pts = float(
                                    compute_view_points(
                                        watch_time_sec=float(wt) if wt is not None else None,
                                        duration_sec=float(dur) if dur is not None else None,
                                        completed=bool(comp),
                                        dwell_ms=int(dwell) if dwell is not None else None,
                                    )
                                )
                                if pts > 0:
                                    hot_ops.append((pid, int(uid), float(pts), bool(comp)))
                    except Exception:
                        pass
                if apply_search_hot:
                    try:
                        nm = str(ev.get("name") or "").strip()
                        if nm == "search:query" and uid and data:
                            qv = _norm_query(data.get("q") or data.get("keyword") or data.get("query"))
                            if qv and len(qv) >= 2:
                                search_ops.append((qv, int(uid)))
                    except Exception:
                        pass
                if apply_eng:
                    try:
                        nm = str(ev.get("name") or "").strip()
                        if uid and data:
                            pid = int(data.get("post_id") or 0)
                            if pid > 0:
                                if nm == "feed:impression":
                                    eng_ops.append(("feed_impr", pid, int(uid)))
                                elif nm == "search:impression":
                                    eng_ops.append(("search_impr", pid, int(uid)))
                                elif nm == "search:click":
                                    eng_ops.append(("search_click", pid, int(uid)))
                    except Exception:
                        pass
                if persist_enabled:
                    try:
                        sid3 = _safe_str(ev.get("session_id"), 64) or ""
                        rid3 = _safe_str(ev.get("request_id"), 64) or ""
                        if _sample_ok(f"{sid3}|{rid3}|{mid}", persist_rate):
                            rows.append(
                                ClientEventRow(
                                    session_id=sid3 or None,
                                    user_id=uid,
                                    name=name,
                                    ts=ts2,
                                    tab=_safe_str(ev.get("tab"), 32) or None,
                                    route=_safe_str(ev.get("route"), 120) or None,
                                    request_id=rid3 or None,
                                    data=data,
                                )
                            )
                    except Exception:
                        pass
                if uid:
                    add_uid(int(uid))
                ack_ids.append(mid)
            except Exception:
                continue

    if not ack_ids:
        out = {"ok": True, "drained": 0}
        try:
            cache.set_json(st_key, out, ttl=30)
        except Exception:
            pass
        return out

    persisted = 0
    if persist_enabled and rows:
        db = SessionLocal()
        try:
            db.add_all(rows)
            db.commit()
            persisted = len(rows)
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
            if persist_strict:
                out = {"ok": False, "error": "db_write_failed", "drained": 0}
                try:
                    if CLIENT_EVENT_DRAIN_TOTAL:
                        CLIENT_EVENT_DRAIN_TOTAL.labels(stream, "db_write_failed").inc(1)
                except Exception:
                    pass
                try:
                    cache.set_json(st_key, out, ttl=30)
                except Exception:
                    pass
                return out
        finally:
            try:
                db.close()
            except Exception:
                pass

    try:
        r.xack(stream, group, *ack_ids)
    except Exception:
        pass
    try:
        r.xtrim(stream, maxlen=int(maxlen), approximate=True)
    except Exception:
        pass

    if user_ids:
        for uid in user_ids[:200]:
            if persona_debounce_sec > 0 and cache.set_nx(f"debounce:persona:{int(uid)}", "1", ttl=persona_debounce_sec):
                apply_async_with_context(rebuild_user_persona, args=[int(uid)])

    if apply_hot and hot_ops:
        try:
            from app.services.hot_counter_service import add_delta, add_hot_rank
            view_ttl = int(getattr(s, "FEED_RECALL_HOT_VIEW_DEDUPE_SEC", 30) or 30)
            if view_ttl < 0:
                view_ttl = 0
            if view_ttl > 3600:
                view_ttl = 3600
            for pid, uid, pts, _ in hot_ops[:5000]:
                add_hot_rank(int(pid), views=float(pts), user_id=int(uid))
                if view_ttl > 0:
                    if cache.set_nx(f"hot:evt:viewcnt:{int(pid)}:{int(uid)}", "1", ttl=view_ttl):
                        add_delta(int(pid), views=1)
                else:
                    add_delta(int(pid), views=1)
        except Exception:
            pass

    if apply_search_hot and search_ops:
        try:
            if cache.redis():
                window = int(getattr(s, "SEARCH_HOT_WINDOW_SEC", 3600) or 3600)
                if window < 60:
                    window = 60
                if window > 7 * 86400:
                    window = 7 * 86400
                bucket = int(getattr(s, "SEARCH_HOT_BUCKET_SEC", 60) or 60)
                if bucket < 5:
                    bucket = 5
                if bucket > 3600:
                    bucket = 3600
                if bucket > window:
                    bucket = window
                dedupe = int(getattr(s, "SEARCH_HOT_DEDUPE_SEC", 10) or 10)
                if dedupe < 0:
                    dedupe = 0
                if dedupe > 3600:
                    dedupe = 3600
                now = int(time.time())
                bid = now // int(bucket)
                zkey = f"search:hot:z:{int(bucket)}:{int(bid)}"
                zexp = int(window + bucket * 2)
                seen = set()
                script = (
                    "local dk=KEYS[1];"
                    "local zk=KEYS[2];"
                    "local q=ARGV[1];"
                    "local ttl=tonumber(ARGV[2]) or 0;"
                    "local zexp=tonumber(ARGV[3]) or 0;"
                    "if ttl>0 then "
                    "  local ok=redis.call('SET',dk,'1','NX','EX',ttl);"
                    "  if ok then redis.call('ZINCRBY',zk,1,q); end;"
                    "else "
                    "  redis.call('ZINCRBY',zk,1,q);"
                    "end;"
                    "if zexp>0 then redis.call('EXPIRE',zk,zexp); end;"
                    "return 1;"
                )
                reqs = []
                for qv, uid in search_ops[:5000]:
                    sig = _q_sig(qv)
                    if not sig:
                        continue
                    k2 = (int(uid), sig)
                    if k2 in seen:
                        continue
                    seen.add(k2)
                    dk = f"search:evt:q:{int(uid)}:{sig}"
                    reqs.append((dk, str(qv), str(int(dedupe)), str(int(zexp))))
                if reqs:
                    try:
                        rdb = cache.redis()
                        if rdb:
                            step = 500
                            for i in range(0, len(reqs), step):
                                pipe = rdb.pipeline()
                                part = reqs[i : i + step]
                                for dk, qv2, d2, z2 in part:
                                    pipe.eval(script, 2, dk, zkey, qv2, d2, z2)
                                pipe.execute()
                        else:
                            for dk, qv2, d2, z2 in reqs:
                                cache.eval_cached(script, keys=[dk, zkey], args=[qv2, d2, z2])
                    except Exception:
                        for dk, qv2, d2, z2 in reqs:
                            cache.eval_cached(script, keys=[dk, zkey], args=[qv2, d2, z2])
        except Exception:
            pass

    if apply_eng and eng_ops:
        try:
            ttl = int(getattr(s, "ENGAGEMENT_COUNTERS_TTL_SEC", 604800) or 604800)
            if ttl < 60:
                ttl = 60
            if ttl > 90 * 86400:
                ttl = 90 * 86400
            ded_impr = int(getattr(s, "ENGAGEMENT_DEDUPE_IMPRESSION_SEC", 300) or 300)
            if ded_impr < 0:
                ded_impr = 0
            if ded_impr > 86400:
                ded_impr = 86400
            ded_clk = int(getattr(s, "ENGAGEMENT_DEDUPE_CLICK_SEC", 60) or 60)
            if ded_clk < 0:
                ded_clk = 0
            if ded_clk > 86400:
                ded_clk = 86400
            script = (
                "local dk=KEYS[1];"
                "local hk=KEYS[2];"
                "local field=ARGV[1];"
                "local dt=tonumber(ARGV[2]) or 0;"
                "local ht=tonumber(ARGV[3]) or 0;"
                "if dt>0 then "
                "  local ok=redis.call('SET',dk,'1','NX','EX',dt);"
                "  if not ok then return 0 end;"
                "end;"
                "redis.call('HINCRBY',hk,field,1);"
                "if ht>0 then "
                "  local t=redis.call('TTL',hk);"
                "  if t<0 then redis.call('EXPIRE',hk,ht); end;"
                "end;"
                "return 1;"
            )
            seen = set()
            for kind, pid, uid in eng_ops[:10000]:
                try:
                    pid2 = int(pid)
                    uid2 = int(uid)
                    k2 = (str(kind), pid2, uid2)
                    if k2 in seen:
                        continue
                    seen.add(k2)
                    dt = ded_impr if str(kind) in {"feed_impr", "search_impr"} else ded_clk
                    dk = f"eng:evt:{str(kind)}:{pid2}:{uid2}"
                    hk = f"eng:post:{pid2}"
                    cache.eval_cached(script, keys=[dk, hk], args=[str(kind), str(int(dt)), str(int(ttl))])
                except Exception:
                    continue
        except Exception:
            pass

    try:
        if CLIENT_EVENT_DRAIN_TOTAL:
            CLIENT_EVENT_DRAIN_TOTAL.labels(stream, "ok").inc(1)
    except Exception:
        pass
    try:
        if CLIENT_EVENT_DRAINED_TOTAL:
            CLIENT_EVENT_DRAINED_TOTAL.labels(stream).inc(int(len(ack_ids)))
    except Exception:
        pass
    try:
        if CLIENT_EVENT_PERSISTED_TOTAL and persisted:
            CLIENT_EVENT_PERSISTED_TOTAL.labels(stream).inc(int(persisted))
    except Exception:
        pass

    out = {"ok": True, "drained": len(ack_ids), "persisted": int(persisted)}
    try:
        cache.set_json(st_key, out, ttl=30)
    except Exception:
        pass
    return out
