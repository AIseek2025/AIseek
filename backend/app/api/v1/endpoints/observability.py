import json
import hashlib
import time
import hmac
import base64
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.core.cache import cache
from app.core.config import get_settings
from app.core.celery_app import apply_async_with_context
from app.db.session import SessionLocal
from app.models.all_models import ClientEvent as ClientEventRow
from app.tasks.client_events import drain_client_event_stream


router = APIRouter()

try:
    from prometheus_client import Counter

    CLIENT_EVENT_INGEST_TOTAL = Counter(
        "aiseek_client_event_ingest_total",
        "Client event ingest events",
        ["result"],
    )
    CLIENT_EVENT_TOKEN_TOTAL = Counter(
        "aiseek_client_event_token_total",
        "Client event token endpoint",
        ["result"],
    )
except Exception:
    CLIENT_EVENT_INGEST_TOTAL = None
    CLIENT_EVENT_TOKEN_TOTAL = None


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


def _rate_limit_ok(ip: Optional[str], session_id: Optional[str], *, ip_rpm: int, session_rpm: int) -> bool:
    r = cache.redis()
    if not r:
        return True
    ip2 = str(ip or "").strip() or "0"
    sid2 = str(session_id or "").strip() or "0"
    if len(sid2) > 64:
        sid2 = sid2[:64]
    try:
        ip_lim = int(ip_rpm or 0)
    except Exception:
        ip_lim = 0
    try:
        sid_lim = int(session_rpm or 0)
    except Exception:
        sid_lim = 0
    if ip_lim <= 0 and sid_lim <= 0:
        return True
    key_ip = f"rl:ce:ip:{ip2}"
    key_sid = f"rl:ce:sid:{sid2}"
    script = (
        "local k=KEYS[1];"
        "local lim=tonumber(ARGV[1]) or 0;"
        "local ttl=tonumber(ARGV[2]) or 60;"
        "if lim<=0 then return 1 end;"
        "local v=redis.call('INCR',k);"
        "if v==1 then redis.call('EXPIRE',k,ttl); end;"
        "if v>lim then return 0 end;"
        "return 1;"
    )
    try:
        if ip_lim > 0:
            if cache.eval_cached(script, keys=[key_ip], args=[str(int(ip_lim)), "60"]) != 1:
                return False
        if sid_lim > 0 and sid2 != "0":
            if cache.eval_cached(script, keys=[key_sid], args=[str(int(sid_lim)), "60"]) != 1:
                return False
    except Exception:
        return True
    return True


def _rate_limit_token_ok(ip: Optional[str], session_id: Optional[str], *, ip_rpm: int, session_rpm: int) -> bool:
    r = cache.redis()
    if not r:
        return True
    ip2 = str(ip or "").strip() or "0"
    sid2 = str(session_id or "").strip() or "0"
    if len(sid2) > 64:
        sid2 = sid2[:64]
    try:
        ip_lim = int(ip_rpm or 0)
    except Exception:
        ip_lim = 0
    try:
        sid_lim = int(session_rpm or 0)
    except Exception:
        sid_lim = 0
    if ip_lim <= 0 and sid_lim <= 0:
        return True
    key_ip = f"rl:ce:token:ip:{ip2}"
    key_sid = f"rl:ce:token:sid:{sid2}"
    script = (
        "local k=KEYS[1];"
        "local lim=tonumber(ARGV[1]) or 0;"
        "local ttl=tonumber(ARGV[2]) or 60;"
        "if lim<=0 then return 1 end;"
        "local v=redis.call('INCR',k);"
        "if v==1 then redis.call('EXPIRE',k,ttl); end;"
        "if v>lim then return 0 end;"
        "return 1;"
    )
    try:
        if ip_lim > 0:
            if cache.eval_cached(script, keys=[key_ip], args=[str(int(ip_lim)), "60"]) != 1:
                return False
        if sid_lim > 0 and sid2 != "0":
            if cache.eval_cached(script, keys=[key_sid], args=[str(int(sid_lim)), "60"]) != 1:
                return False
    except Exception:
        return True
    return True


def _enforce_signed(request: Request, *, rt: Optional[Dict[str, Any]] = None) -> Optional[str]:
    s = get_settings()
    base_required = bool(getattr(s, "CLIENT_EVENT_SIGNED_REQUIRED", False)) or False
    if base_required and isinstance(rt, dict) and rt.get("signed_required") is False:
        return None
    required = base_required
    secret = str(getattr(s, "CLIENT_EVENT_SHARED_SECRET", "") or "").strip()
    if not required:
        return None
    if not secret:
        return "misconfigured_secret"
    try:
        token = request.headers.get("x-aiseek-token") or request.headers.get("X-Aiseek-Token")
    except Exception:
        token = None
    if token:
        err2 = _verify_event_token(str(token), request)
        if not err2:
            return None
    ts = request.headers.get("x-aiseek-ts") or request.headers.get("X-Aiseek-Ts")
    sig = request.headers.get("x-aiseek-sig") or request.headers.get("X-Aiseek-Sig")
    if not ts or not sig:
        return "missing_signature"
    try:
        ts_i = int(ts)
    except Exception:
        return "bad_signature"
    window_raw = (rt.get("sig_window_sec") if isinstance(rt, dict) else None)
    window = int(window_raw) if window_raw is not None else int(getattr(s, "CLIENT_EVENT_SIG_WINDOW_SEC", 30) or 30)
    if window < 3:
        window = 3
    if window > 600:
        window = 600
    now = int(time.time())
    if abs(now - ts_i) > window:
        return "expired_signature"
    try:
        msg = f"{ts_i}\n{request.method.upper()}\n{request.url.path}".encode("utf-8")
        exp = hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(str(sig), str(exp)):
            return "bad_signature"
    except Exception:
        return "bad_signature"
    return None


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _b64url_decode(s: str) -> Optional[bytes]:
    try:
        s2 = str(s or "").strip()
        if not s2:
            return None
        pad = "=" * ((4 - (len(s2) % 4)) % 4)
        return base64.urlsafe_b64decode((s2 + pad).encode("utf-8"))
    except Exception:
        return None


def _token_secret() -> str:
    s = get_settings()
    sec = str(getattr(s, "CLIENT_EVENT_SHARED_SECRET", "") or "").strip()
    if sec:
        return sec
    return str(getattr(s, "SECRET_KEY", "") or "")


def _issue_event_token(request: Request) -> Dict[str, Any]:
    s = get_settings()
    ttl = int(getattr(s, "CLIENT_EVENT_TOKEN_TTL_SEC", 600) or 600)
    if ttl < 30:
        ttl = 30
    if ttl > 86400:
        ttl = 86400
    exp = int(time.time()) + ttl
    sid = ""
    try:
        sid = str(request.cookies.get("aiseek_sid") or "").strip()
    except Exception:
        sid = ""
    ua = ""
    try:
        ua = str(request.headers.get("user-agent") or "").strip()
    except Exception:
        ua = ""
    ua_h = hashlib.sha1(ua.encode("utf-8", "ignore")).hexdigest()[:16] if ua else ""
    payload = {"v": 1, "exp": int(exp), "sid": sid, "uah": ua_h}
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    b64 = _b64url_encode(raw)
    sec = _token_secret()
    sig = hmac.new(sec.encode("utf-8"), msg=b64.encode("utf-8"), digestmod=hashlib.sha256).hexdigest()
    return {"token": f"{b64}.{sig}", "exp": int(exp)}


def _verify_event_token(token: str, request: Request) -> Optional[str]:
    sec = _token_secret()
    if not sec:
        return "misconfigured_secret"
    t = str(token or "").strip()
    if not t or "." not in t:
        return "bad_token"
    b64, sig = t.split(".", 1)
    if not b64 or not sig:
        return "bad_token"
    exp = hmac.new(sec.encode("utf-8"), msg=b64.encode("utf-8"), digestmod=hashlib.sha256).hexdigest()
    if not hmac.compare_digest(str(sig), str(exp)):
        return "bad_token"
    raw = _b64url_decode(b64)
    if not raw:
        return "bad_token"
    try:
        obj = json.loads(raw.decode("utf-8", "ignore") or "{}")
    except Exception:
        obj = {}
    if not isinstance(obj, dict):
        return "bad_token"
    try:
        exp_i = int(obj.get("exp") or 0)
    except Exception:
        exp_i = 0
    if exp_i <= 0 or exp_i < int(time.time()):
        return "expired_token"
    sid = str(obj.get("sid") or "").strip()
    if sid:
        try:
            sid_req = str(request.cookies.get("aiseek_sid") or "").strip()
        except Exception:
            sid_req = ""
        if sid_req and sid_req != sid:
            return "bad_token"
    uah = str(obj.get("uah") or "").strip()
    if uah:
        try:
            ua = str(request.headers.get("user-agent") or "").strip()
        except Exception:
            ua = ""
        uah2 = hashlib.sha1(ua.encode("utf-8", "ignore")).hexdigest()[:16] if ua else ""
        if uah2 and uah2 != uah:
            return "bad_token"
    return None


def _topic_for_event_name(name: str) -> str:
    s = str(name or "").strip()
    if not s:
        return "other"
    head = s.split(":", 1)[0].strip().lower()
    if head in {"feed", "player", "search"}:
        return head
    return "other"


class ClientEventIn(BaseModel):
    name: str
    ts: int
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    tab: Optional[str] = None
    route: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


class ClientEventsIn(BaseModel):
    events: List[ClientEventIn]
    token: Optional[str] = None


@router.get("/token")
async def issue_event_token(request: Request):
    s = get_settings()
    enabled = bool(getattr(s, "CLIENT_EVENT_TOKEN_RATE_LIMIT_ENABLED", True))
    ip = request.client.host if request.client else None
    sid = ""
    try:
        sid = str(request.cookies.get("aiseek_sid") or "").strip()
    except Exception:
        sid = ""
    if enabled:
        ip_rpm = int(getattr(s, "CLIENT_EVENT_TOKEN_RATE_LIMIT_IP_RPM", 300) or 300)
        sid_rpm = int(getattr(s, "CLIENT_EVENT_TOKEN_RATE_LIMIT_SID_RPM", 600) or 600)
        if not _rate_limit_token_ok(ip, sid or None, ip_rpm=ip_rpm, session_rpm=sid_rpm):
            try:
                if CLIENT_EVENT_TOKEN_TOTAL:
                    CLIENT_EVENT_TOKEN_TOTAL.labels("rate_limited").inc(1)
            except Exception:
                pass
            return {"ok": False, "error": "rate_limited"}
    tok = _issue_event_token(request)
    try:
        if CLIENT_EVENT_TOKEN_TOTAL:
            CLIENT_EVENT_TOKEN_TOTAL.labels("ok").inc(1)
    except Exception:
        pass
    return {"ok": True, "token": tok.get("token"), "exp": tok.get("exp")}


@router.post("/events")
async def ingest_events(payload: ClientEventsIn, request: Request):
    s = get_settings()
    root = Path(__file__).resolve().parents[4]
    log_dir = root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    fp = log_dir / "frontend_events.log"

    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    try:
        sid_hdr = request.headers.get("x-aiseek-sid")
    except Exception:
        sid_hdr = None
    session_hint = str(sid_hdr or "").strip() or None
    if not session_hint:
        try:
            session_hint = request.cookies.get("aiseek_sid")
        except Exception:
            session_hint = None

    rt = _client_events_runtime()
    rate_limit_enabled = bool(rt.get("rate_limit_enabled")) if rt.get("rate_limit_enabled") is not None else bool(getattr(s, "CLIENT_EVENT_RATE_LIMIT_ENABLED", True))
    ip_rpm_raw = rt.get("rate_limit_ip_rpm") if rt.get("rate_limit_ip_rpm") is not None else getattr(s, "CLIENT_EVENT_RATE_LIMIT_IP_RPM", 600)
    sid_rpm_raw = rt.get("rate_limit_session_rpm") if rt.get("rate_limit_session_rpm") is not None else getattr(s, "CLIENT_EVENT_RATE_LIMIT_SESSION_RPM", 1200)
    if rate_limit_enabled:
        ip_rpm = int(ip_rpm_raw or 0)
        sid_rpm = int(sid_rpm_raw or 0)
        if not _rate_limit_ok(ip, session_hint, ip_rpm=ip_rpm, session_rpm=sid_rpm):
            try:
                if CLIENT_EVENT_INGEST_TOTAL:
                    CLIENT_EVENT_INGEST_TOTAL.labels("rate_limited").inc(1)
            except Exception:
                pass
            return {"ok": True, "accepted": 0, "queued": False, "dropped": "rate_limited"}

    sig_err = _enforce_signed(request, rt=rt)
    if sig_err:
        if payload and getattr(payload, "token", None):
            err2 = _verify_event_token(str(getattr(payload, "token")), request)
            if not err2:
                sig_err = None
        if sig_err:
            try:
                if CLIENT_EVENT_INGEST_TOTAL:
                    CLIENT_EVENT_INGEST_TOTAL.labels("unauthorized").inc(1)
            except Exception:
                pass
            return {"ok": True, "accepted": 0, "queued": False, "dropped": str(sig_err)}

    lines = []
    row_items = []
    stream_items = []
    max_data_bytes = int(getattr(s, "CLIENT_EVENT_MAX_DATA_BYTES", 8192) or 8192)
    ingest_rate_raw = rt.get("ingest_sample_rate") if rt.get("ingest_sample_rate") is not None else getattr(s, "CLIENT_EVENT_INGEST_SAMPLE_RATE", 1.0)
    ingest_rate = float(ingest_rate_raw) if ingest_rate_raw is not None else 1.0
    drop_unknown = bool(rt.get("drop_unknown_heads")) if rt.get("drop_unknown_heads") is not None else bool(getattr(s, "CLIENT_EVENT_DROP_UNKNOWN_HEADS", True))
    dropped_sample = 0
    dropped_unknown2 = 0
    for e in payload.events[:500]:
        if ingest_rate < 1.0:
            try:
                sid0 = str(e.session_id or session_hint or "")
                rid0 = str(e.request_id or "")
                if not _sample_ok(f"{sid0}|{rid0}|{e.name}|{e.ts}", ingest_rate):
                    dropped_sample += 1
                    continue
            except Exception:
                dropped_sample += 1
                continue
        if drop_unknown:
            try:
                if _topic_for_event_name(str(e.name or "")) == "other":
                    dropped_unknown2 += 1
                    continue
            except Exception:
                dropped_unknown2 += 1
                continue
        data2 = None
        if e.data and isinstance(e.data, dict):
            try:
                raw = json.dumps(e.data, ensure_ascii=False, separators=(",", ":"))
                if len(raw.encode("utf-8", "ignore")) <= max_data_bytes:
                    data2 = e.data
            except Exception:
                data2 = None
        lines.append(
            json.dumps(
                {
                    "name": e.name,
                    "ts": e.ts,
                    "session_id": e.session_id,
                    "request_id": e.request_id,
                    "tab": e.tab,
                    "route": e.route,
                    "data": data2,
                    "ip": ip,
                    "ua": ua,
                },
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )

        try:
            uid = int(data2.get("user_id")) if data2 and isinstance(data2.get("user_id"), (int, float, str)) and str(data2.get("user_id")).isdigit() else None
            ts2 = float(e.ts) / 1000.0 if e.ts > 10_000_000_000 else float(e.ts)
            row_items.append((e.session_id, uid, e.name, ts2, e.tab, e.route, e.request_id, data2))
        except Exception:
            pass
        try:
            stream_items.append(
                {
                    "name": str(e.name or ""),
                    "ts": int(e.ts or 0),
                    "session_id": str(e.session_id or ""),
                    "request_id": str(e.request_id or ""),
                    "tab": str(e.tab or ""),
                    "route": str(e.route or ""),
                    "data": data2,
                    "ip": ip,
                    "ua": ua,
                }
            )
        except Exception:
            pass

    if lines:
        if bool(getattr(s, "CLIENT_EVENT_LOG_ENABLED", True)):
            with fp.open("a", encoding="utf-8", errors="ignore") as f:
                f.write("\n".join(lines) + "\n")

    use_stream = bool(getattr(s, "CLIENT_EVENT_STREAM_ENABLED", True))
    shard_stream = bool(getattr(s, "CLIENT_EVENT_STREAM_SHARD_ENABLED", True))
    stream_ok = False
    if use_stream and stream_items:
        r = cache.redis()
        if r:
            base_stream = str(getattr(s, "CLIENT_EVENT_STREAM_KEY", "events:client") or "events:client")
            maxlen = int(getattr(s, "CLIENT_EVENT_STREAM_MAXLEN", 200000) or 200000)
            try:
                buckets = {}
                topics_seen = set()
                if shard_stream:
                    for it in stream_items:
                        topic = _topic_for_event_name(str(it.get("name") or ""))
                        topics_seen.add(topic)
                        sk = f"{base_stream}:{topic}"
                        if sk not in buckets:
                            buckets[sk] = []
                        buckets[sk].append(it)
                else:
                    buckets[base_stream] = stream_items
                pipe = r.pipeline()
                for sk, items in buckets.items():
                    for it in items:
                        pipe.xadd(str(sk), {"payload": json.dumps(it, ensure_ascii=False, separators=(",", ":"))}, maxlen=maxlen, approximate=True)
                pipe.execute()
                stream_ok = True
            except Exception:
                stream_ok = False
            if stream_ok:
                try:
                    debounce_sec = int(getattr(s, "CLIENT_EVENT_DRAIN_DEBOUNCE_SEC", 3) or 3)
                    if debounce_sec < 1:
                        debounce_sec = 1
                    if debounce_sec > 30:
                        debounce_sec = 30
                    max_topics = int(getattr(s, "CLIENT_EVENT_DRAIN_MAX_TOPICS_PER_BATCH", 8) or 8)
                    if max_topics < 1:
                        max_topics = 1
                    if max_topics > 64:
                        max_topics = 64
                    max_messages = int(getattr(s, "CLIENT_EVENT_DRAIN_MAX_MESSAGES", 2000) or 2000)
                    if max_messages < 200:
                        max_messages = 200
                    if max_messages > 20000:
                        max_messages = 20000
                    if shard_stream:
                        for topic in list(topics_seen)[:max_topics]:
                            lk = f"lock:drain:client_events:{topic}"
                            if cache.set_nx(lk, "1", ttl=debounce_sec):
                                apply_async_with_context(drain_client_event_stream, kwargs={"max_messages": max_messages, "stream_override": f"{base_stream}:{topic}"}, dedupe_key=f"drain_client_events:{topic}", dedupe_ttl=2, max_queue_depth=10000, drop_when_overloaded=True)
                    else:
                        if cache.set_nx("lock:drain:client_events", "1", ttl=debounce_sec):
                            apply_async_with_context(drain_client_event_stream, kwargs={"max_messages": max_messages, "stream_override": base_stream}, dedupe_key="drain_client_events:base", dedupe_ttl=2, max_queue_depth=10000, drop_when_overloaded=True)
                except Exception:
                    pass

    if row_items and (not stream_ok) and bool(getattr(s, "CLIENT_EVENT_DB_FALLBACK_ENABLED", True)):
        db = SessionLocal()
        try:
            rows = [
                ClientEventRow(
                    session_id=sid,
                    user_id=uid,
                    name=name,
                    ts=ts2,
                    tab=tab,
                    route=route,
                    request_id=rid,
                    data=data2,
                )
                for (sid, uid, name, ts2, tab, route, rid, data2) in row_items
            ]
            db.add_all(rows)
            db.commit()
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
        finally:
            try:
                db.close()
            except Exception:
                pass
        try:
            persona_debounce_sec = int(getattr(s, "PERSONA_REBUILD_DEBOUNCE_SEC", 600) or 600)
            if persona_debounce_sec > 0:
                from app.tasks.reco_profile import rebuild_user_persona

                uids = []
                for _, uid, _, _, _, _, _, _ in row_items:
                    if uid and int(uid) not in uids:
                        uids.append(int(uid))
                for uid in uids[:200]:
                    if cache.set_nx(f"debounce:persona:{int(uid)}", "1", ttl=persona_debounce_sec):
                        apply_async_with_context(rebuild_user_persona, args=[int(uid)], dedupe_key=f"rebuild_persona:{int(uid)}", dedupe_ttl=max(5, int(persona_debounce_sec)), max_queue_depth=20000, drop_when_overloaded=True)
        except Exception:
            pass

    try:
        if CLIENT_EVENT_INGEST_TOTAL:
            if dropped_sample:
                CLIENT_EVENT_INGEST_TOTAL.labels("sampled_out").inc(int(dropped_sample))
            if dropped_unknown2:
                CLIENT_EVENT_INGEST_TOTAL.labels("dropped_unknown").inc(int(dropped_unknown2))
            CLIENT_EVENT_INGEST_TOTAL.labels("accepted").inc(int(len(lines)))
            CLIENT_EVENT_INGEST_TOTAL.labels("queued").inc(int(len(lines)) if stream_ok else 0)
    except Exception:
        pass

    return {"ok": True, "accepted": len(lines), "queued": bool(stream_ok)}
