from __future__ import annotations

import datetime
import math
import time
from urllib.parse import urlparse
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.cache import cache
from app.core.config import get_settings
from app.core.http_client import build_outgoing_headers, http_get_json
from app.core.request_context import get_request_id, get_session_id
from app.models.all_models import Interaction, Post

try:
    from prometheus_client import Counter

    FEED_RECALL_TOTAL = Counter(
        "aiseek_feed_recall_total",
        "Feed recall attempts",
        ["provider", "outcome"],
    )
except Exception:
    FEED_RECALL_TOTAL = None


@dataclass
class RecallResult:
    candidates: List[Dict[str, Any]]
    provider: str


class FeedRecallProvider:
    name: str = "base"

    def recall(self, db: Session, *, cat_key: str, kind: str) -> RecallResult:
        raise NotImplementedError


class LocalDBRecallProvider(FeedRecallProvider):
    name = "local"

    def _cache_key(self, cat_key: str, kind: str) -> str:
        v = cache.version(f"recall:local:{kind}:{cat_key}")
        return f"recall:local:{kind}:cand:v{v}:cat{cat_key}"

    def _recent(self, db: Session, cat_key: str, limit2: int) -> List[Dict[str, Any]]:
        qq = db.query(Post.id, Post.category, Post.created_at).filter(Post.status == "done")
        if cat_key != "all":
            qq = qq.filter(Post.category == cat_key)
        rows = qq.order_by(Post.created_at.desc(), Post.id.desc()).limit(limit2).all()
        out: List[Dict[str, Any]] = []
        for pid, cat, created_at in rows:
            ts = float(created_at.timestamp()) if created_at is not None else 0.0
            out.append({"id": int(pid), "category": cat or "", "created_at": ts, "score": 0.0})
        return out

    def _hot(self, db: Session, cat_key: str, limit2: int) -> List[Dict[str, Any]]:
        s = get_settings()
        r = cache._get_redis()  # noqa: SLF001
        if r:
            try:
                bucket_sec = int(getattr(s, "FEED_RECALL_HOT_BUCKET_SEC", 300) or 300)
                if bucket_sec < 5:
                    bucket_sec = 5
                if bucket_sec > 3600:
                    bucket_sec = 3600
                window = int(getattr(s, "FEED_RECALL_HOT_WINDOW_SEC", 86400) or 86400)
                if window < 60:
                    window = 60
                if window > 2592000:
                    window = 2592000
                n_buckets = int(window // bucket_sec) + 1
                now = int(time.time())
                cur = now // bucket_sec
                keys = [f"hot:z:{bucket_sec}:{cur - i}" for i in range(n_buckets)]
                decay = bool(getattr(s, "FEED_RECALL_HOT_DECAY_ENABLED", False)) or False
                weighted = None
                if decay:
                    half = int(getattr(s, "FEED_RECALL_HOT_DECAY_HALF_LIFE_SEC", 900) or 900)
                    if half < 1:
                        half = 1
                    weighted = {}
                    for i in range(n_buckets):
                        age = float(i * bucket_sec)
                        w = math.pow(0.5, age / float(half))
                        if w < 1e-6:
                            w = 1e-6
                        weighted[keys[i]] = float(w)
                tmp = f"hot:tmp:{bucket_sec}:{cur}"
                pipe = r.pipeline()
                pipe.zunionstore(tmp, weighted if weighted else keys)
                pipe.expire(tmp, 3)
                fetch_n = int(limit2) * (5 if cat_key != "all" else 2)
                if fetch_n < limit2:
                    fetch_n = limit2
                if fetch_n > 5000:
                    fetch_n = 5000
                pipe.zrevrange(tmp, 0, fetch_n - 1, withscores=True)
                res = pipe.execute()
                ids_raw = res[-1] if res and isinstance(res, list) else []
                ids: List[int] = []
                scores = {}
                for pair in ids_raw or []:
                    try:
                        pid = int(pair[0])
                        sc = float(pair[1])
                        ids.append(pid)
                        scores[pid] = sc
                    except Exception:
                        continue
                if ids:
                    qq = db.query(Post.id, Post.category, Post.created_at).filter(Post.status == "done", Post.id.in_(ids))
                    if cat_key != "all":
                        qq = qq.filter(Post.category == cat_key)
                    rows = qq.all()
                    m = {int(pid): (cat or "", created_at) for pid, cat, created_at in rows}
                    out: List[Dict[str, Any]] = []
                    for pid in ids:
                        v = m.get(int(pid))
                        if not v:
                            continue
                        cat, created_at = v
                        ts = float(created_at.timestamp()) if created_at is not None else 0.0
                        out.append({"id": int(pid), "category": cat or "", "created_at": ts, "score": float(scores.get(int(pid)) or 0.0)})
                        if len(out) >= limit2:
                            break
                    return out
            except Exception:
                pass

        from sqlalchemy import func
        window = int(getattr(s, "FEED_RECALL_HOT_WINDOW_SEC", 86400) or 86400)
        if window < 60:
            window = 60
        if window > 2592000:
            window = 2592000
        min_dt = datetime.datetime.fromtimestamp(time.time() - float(window), tz=datetime.timezone.utc)

        qq = (
            db.query(Post.id, Post.category, Post.created_at, func.count(Interaction.id).label("c"))
            .join(Interaction, Interaction.post_id == Post.id)
            .filter(Post.status == "done", Interaction.type.in_(["like", "favorite"]), Interaction.created_at >= min_dt)
        )
        if cat_key != "all":
            qq = qq.filter(Post.category == cat_key)
        rows = qq.group_by(Post.id).order_by(func.count(Interaction.id).desc(), Post.created_at.desc(), Post.id.desc()).limit(limit2).all()
        out: List[Dict[str, Any]] = []
        for pid, cat, created_at, c in rows:
            ts = float(created_at.timestamp()) if created_at is not None else 0.0
            try:
                sc = float(c or 0)
            except Exception:
                sc = 0.0
            out.append({"id": int(pid), "category": cat or "", "created_at": ts, "score": float(sc)})
        return out

    def _dedupe_merge(self, primary: List[Dict[str, Any]], secondary: List[Dict[str, Any]], limit2: int) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        seen = set()
        for it in primary + secondary:
            if not isinstance(it, dict):
                continue
            pid = it.get("id")
            if not pid:
                continue
            try:
                pid_i = int(pid)
            except Exception:
                continue
            if pid_i in seen:
                continue
            seen.add(pid_i)
            out.append(it)
            if len(out) >= limit2:
                break
        return out

    def recall(self, db: Session, *, cat_key: str, kind: str) -> RecallResult:
        s = get_settings()
        cand_limit = int(getattr(s, "FEED_CAND_LIMIT", 500) or 500)
        if cand_limit < 10:
            cand_limit = 10
        if cand_limit > 5000:
            cand_limit = 5000

        kind2 = (kind or "recent").strip().lower()
        if kind2 not in {"recent", "hot", "blend"}:
            kind2 = "recent"

        def _get_or_build(k: str) -> List[Dict[str, Any]]:
            ttl = int(getattr(s, "FEED_CAND_TTL_SEC", 5) or 5)
            if ttl < 1:
                ttl = 1
            if ttl > 600:
                ttl = 600
            if k == "hot":
                ttl2 = int(getattr(s, "FEED_RECALL_HOT_TTL_SEC", 20) or 20)
                if ttl2 < 1:
                    ttl2 = 1
                if ttl2 > 600:
                    ttl2 = 600
                ttl = ttl2
            key = self._cache_key(cat_key, k)
            hit = False
            arr: Optional[List[Dict[str, Any]]] = None
            try:
                cached = cache.get_json(key)
                if isinstance(cached, list):
                    hit = True
                    arr = cached
            except Exception:
                arr = None
            if arr is None:
                if k == "hot":
                    arr = self._hot(db, cat_key, cand_limit)
                else:
                    arr = self._recent(db, cat_key, cand_limit)
                try:
                    cache.set_json(key, arr, ttl=ttl)
                except Exception:
                    pass
            _metric(self.name, "cache_hit" if hit else "cache_miss")
            return arr if isinstance(arr, list) else []

        if kind2 == "blend":
            hot_lim = int(getattr(s, "FEED_RECALL_BLEND_HOT_LIMIT", 50) or 50)
            if hot_lim < 0:
                hot_lim = 0
            if hot_lim > cand_limit:
                hot_lim = cand_limit
            hot = _get_or_build("hot")
            recent = _get_or_build("recent")
            arr = self._dedupe_merge(hot[:hot_lim], recent, cand_limit)
            if not arr:
                arr = recent
        else:
            arr = _get_or_build(kind2)
            if kind2 == "hot" and not arr:
                arr = _get_or_build("recent")
        _metric(self.name, "ok")
        return RecallResult(candidates=arr, provider=self.name)


class RemoteHTTPRecallProvider(FeedRecallProvider):
    name = "remote"

    def _cb_key(self) -> str:
        return "cb:feed_recall_remote"

    def _cb_get(self) -> Dict[str, Any]:
        obj = cache.get_json(self._cb_key())
        return obj if isinstance(obj, dict) else {}

    def _cb_set(self, obj: Dict[str, Any], ttl: int) -> None:
        cache.set_json(self._cb_key(), obj, ttl=ttl)

    def _cb_is_open(self) -> bool:
        st = self._cb_get()
        try:
            open_until = float(st.get("open_until") or 0)
        except Exception:
            open_until = 0
        return open_until > time.time()

    def _cb_mark_success(self) -> None:
        try:
            self._cb_set({"fail": 0, "open_until": 0}, ttl=600)
        except Exception:
            pass

    def _cb_mark_failure(self) -> None:
        s = get_settings()
        thr = int(getattr(s, "FEED_RECALL_CB_FAIL_THRESHOLD", 5) or 5)
        if thr < 1:
            thr = 1
        if thr > 50:
            thr = 50
        open_sec = int(getattr(s, "FEED_RECALL_CB_OPEN_SEC", 30) or 30)
        if open_sec < 3:
            open_sec = 3
        if open_sec > 600:
            open_sec = 600
        st = self._cb_get()
        try:
            fail = int(st.get("fail") or 0) + 1
        except Exception:
            fail = 1
        open_until = float(st.get("open_until") or 0)
        if fail >= thr:
            open_until = time.time() + open_sec
        try:
            self._cb_set({"fail": fail, "open_until": open_until}, ttl=max(open_sec * 2, 120))
        except Exception:
            pass

    def recall(self, db: Session, *, cat_key: str, kind: str) -> RecallResult:
        s = get_settings()
        _, url, _, kind2 = _get_runtime_cfg()
        if not url:
            _metric(self.name, "disabled")
            return RecallResult(candidates=[], provider=self.name)
        if self._cb_is_open():
            _metric(self.name, "circuit_open")
            return RecallResult(candidates=[], provider=self.name)

        timeout = float(getattr(s, "FEED_RECALL_TIMEOUT_SEC", 0.35) or 0.35)
        if timeout < 0.05:
            timeout = 0.05
        if timeout > 5:
            timeout = 5
        cand_limit = int(getattr(s, "FEED_CAND_LIMIT", 500) or 500)
        if cand_limit < 10:
            cand_limit = 10
        if cand_limit > 5000:
            cand_limit = 5000

        k = (kind2 or kind or "recent").strip().lower()
        if k not in {"recent", "hot", "blend"}:
            k = "recent"
        params = {"cat": cat_key, "limit": cand_limit, "v": 1, "kind": k}
        try:
            p = urlparse(url)
            signed_path = p.path or "/"
        except Exception:
            signed_path = "/"
        headers = build_outgoing_headers({"accept": "application/json"}, signed_method="GET", signed_path=signed_path)
        attempts = int(getattr(s, "FEED_RECALL_RETRIES", 1) or 1)
        if attempts < 0:
            attempts = 0
        if attempts > 2:
            attempts = 2

        last_err: Optional[str] = None
        data = http_get_json(
            url,
            service="feed_recall_remote",
            params=params,
            headers=headers,
            timeout=timeout,
            retries=attempts,
        )
        arr = _normalize_candidates(data)
        if not arr:
            self._cb_mark_failure()
            _metric(self.name, "empty")
            return RecallResult(candidates=[], provider=self.name)
        self._cb_mark_success()
        _metric(self.name, "ok")
        return RecallResult(candidates=arr, provider=self.name)


def _metric(provider: str, outcome: str) -> None:
    try:
        if FEED_RECALL_TOTAL is not None:
            FEED_RECALL_TOTAL.labels(provider, outcome).inc()
    except Exception:
        pass


def _normalize_candidates(data: Any) -> List[Dict[str, Any]]:
    if isinstance(data, dict):
        v = data.get("version")
        if str(v) == "1" or int(v or 0) == 1:
            return _normalize_candidates(data.get("items"))
    if not isinstance(data, list):
        return []
    out: List[Dict[str, Any]] = []
    for it in data:
        if not isinstance(it, dict):
            continue
        try:
            pid = int(it.get("id") or 0)
        except Exception:
            pid = 0
        if pid <= 0:
            continue
        cat = it.get("category")
        cat_s = str(cat) if cat is not None else ""
        try:
            ts = float(it.get("created_at") or 0)
        except Exception:
            ts = 0.0
        try:
            score = float(it.get("score") or 0)
        except Exception:
            score = 0.0
        out.append({"id": pid, "category": cat_s, "created_at": ts, "score": float(score)})
    return out


def get_recall_provider() -> FeedRecallProvider:
    mode, _, _, _ = _get_runtime_cfg()
    if mode in {"remote", "http"}:
        return RemoteHTTPRecallProvider()
    if mode in {"auto", "fallback"}:
        return RemoteHTTPRecallProvider()
    return LocalDBRecallProvider()


def recall_candidates(db: Session, *, cat_key: str) -> RecallResult:
    mode, url, percent, kind = _get_runtime_cfg()
    local = LocalDBRecallProvider()
    if mode == "local":
        return local.recall(db, cat_key=cat_key, kind=kind)
    remote = RemoteHTTPRecallProvider()
    if mode == "auto" and percent < 100:
        sid = None
        try:
            sid = get_session_id()
        except Exception:
            sid = None
        if not sid:
            _metric("auto", "skip_remote")
            return local.recall(db, cat_key=cat_key, kind=kind)
        if _bucket_0_99(str(sid)) >= percent:
            _metric("auto", "skip_remote")
            return local.recall(db, cat_key=cat_key, kind=kind)
    rr = remote.recall(db, cat_key=cat_key, kind=kind)
    if rr.candidates:
        return rr
    _metric("auto", "fallback_local")
    return local.recall(db, cat_key=cat_key, kind=kind)


def get_runtime_kind() -> str:
    try:
        _, _, _, kind = _get_runtime_cfg()
        return str(kind or "recent")
    except Exception:
        return "recent"


def _bucket_0_99(s: str) -> int:
    h = 2166136261
    for ch in str(s or ""):
        h ^= ord(ch)
        h = (h * 16777619) & 0xFFFFFFFF
    return int(h % 100)


def _get_runtime_cfg() -> tuple[str, str, int, str]:
    s = get_settings()
    mode = str(getattr(s, "FEED_RECALL_PROVIDER", "local") or "local").strip().lower()
    url = str(getattr(s, "FEED_RECALL_URL", "") or "").strip()
    kind = str(getattr(s, "FEED_RECALL_KIND", "recent") or "recent").strip().lower()
    if kind not in {"recent", "hot", "blend"}:
        kind = "recent"
    try:
        pct = int(getattr(s, "FEED_RECALL_PERCENT", 100) or 100)
    except Exception:
        pct = 100
    if pct < 0:
        pct = 0
    if pct > 100:
        pct = 100
    try:
        import json
        from pathlib import Path

        app_root = Path(__file__).resolve().parents[1]
        p = app_root / "runtime" / "feed_recall.json"
        if p.exists():
            obj = json.loads(p.read_text(encoding="utf-8", errors="ignore") or "{}")
            if isinstance(obj, dict):
                m2 = str(obj.get("provider") or "").strip().lower()
                u2 = str(obj.get("url") or "").strip()
                k2 = str(obj.get("kind") or "").strip().lower()
                has_pct = "percent" in obj
                try:
                    p2 = int(obj.get("percent") if has_pct else pct)
                except Exception:
                    p2 = pct
                if m2:
                    mode = m2
                if u2:
                    url = u2
                if k2 in {"recent", "hot", "blend"}:
                    kind = k2
                if (mode == "auto") and (not has_pct):
                    p2 = 0
                if p2 < 0:
                    p2 = 0
                if p2 > 100:
                    p2 = 100
                pct = p2
    except Exception:
        pass
    return mode or "local", url, pct, kind
