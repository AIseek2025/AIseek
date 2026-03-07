import time
from typing import Dict, List, Tuple

from app.core.cache import cache
from app.core.config import get_settings

try:
    from prometheus_client import Counter

    SEARCH_HOT_CACHE_TOTAL = Counter("aiseek_search_hot_cache_total", "Search hot cache total", ["outcome"])
except Exception:
    SEARCH_HOT_CACHE_TOTAL = None


def _params() -> Tuple[int, int]:
    s = get_settings()
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
    return window, bucket


def hot_bucket_key(bucket_sec: int, bucket_id: int) -> str:
    return f"search:hot:z:{int(bucket_sec)}:{int(bucket_id)}"


def get_hot_queries(limit: int = 10) -> List[str]:
    lim = int(limit or 0)
    if lim < 1:
        lim = 1
    if lim > 50:
        lim = 50
    s = get_settings()
    if not bool(getattr(s, "SEARCH_HOT_ENABLED", False)):
        return []
    try:
        top_ttl = int(getattr(s, "SEARCH_HOT_TOP_CACHE_TTL_SEC", 12) or 12)
    except Exception:
        top_ttl = 12
    if top_ttl < 3:
        top_ttl = 3
    if top_ttl > 120:
        top_ttl = 120
    try:
        top_lock_ttl = int(getattr(s, "SEARCH_HOT_TOP_CACHE_LOCK_TTL_SEC", 2) or 2)
    except Exception:
        top_lock_ttl = 2
    if top_lock_ttl < 1:
        top_lock_ttl = 1
    if top_lock_ttl > 10:
        top_lock_ttl = 10
    try:
        scan_max = int(getattr(s, "SEARCH_HOT_SCAN_BUCKETS_MAX", 48) or 48)
    except Exception:
        scan_max = 48
    if scan_max < 8:
        scan_max = 8
    if scan_max > 240:
        scan_max = 240
    key = f"search:hot:top:v2:lim{lim}:scan{int(scan_max)}"

    def _build():
        r = cache.redis()
        if not r:
            return []
        window_sec, bucket_sec = _params()
        now = int(time.time())
        bucket_id = now // int(bucket_sec)
        buckets = max(1, int(window_sec // bucket_sec) + 1)
        take = min(int(scan_max), buckets)
        want = max(lim * 3, lim + 2)
        pipe = r.pipeline()
        keys = []
        for i in range(take):
            k = hot_bucket_key(bucket_sec, bucket_id - i)
            keys.append(k)
        out = None
        try:
            tmp_key = f"search:hot:tmp:{int(bucket_sec)}:{int(bucket_id)}:{int(scan_max)}"
            r.zunionstore(tmp_key, keys, aggregate="SUM")
            r.expire(tmp_key, 2)
            out = [r.zrevrange(tmp_key, 0, want - 1, withscores=True)]
        except Exception:
            out = None
        if out is None:
            pipe = r.pipeline()
            for k in keys:
                pipe.zrevrange(k, 0, want - 1, withscores=True)
            out = pipe.execute()
        agg: Dict[str, float] = {}
        for items in out or []:
            if not items:
                continue
            for q, sc in items:
                try:
                    qq = str(q or "").strip()
                    if not qq:
                        continue
                    agg[qq] = float(agg.get(qq, 0.0)) + float(sc or 0.0)
                except Exception:
                    continue
        if not agg:
            return []
        top = sorted(agg.items(), key=lambda x: (-x[1], x[0]))[:lim]
        return [k for k, _ in top]

    cached = None
    try:
        cached = cache.get_json(key)
    except Exception:
        cached = None
    if isinstance(cached, list):
        if SEARCH_HOT_CACHE_TOTAL is not None:
            try:
                SEARCH_HOT_CACHE_TOTAL.labels("hit").inc()
            except Exception:
                pass
        return cached
    if SEARCH_HOT_CACHE_TOTAL is not None:
        try:
            SEARCH_HOT_CACHE_TOTAL.labels("miss").inc()
        except Exception:
            pass
    out = cache.get_or_set_json(key, ttl=int(top_ttl), builder=_build, lock_ttl=int(top_lock_ttl)) or []
    return out if isinstance(out, list) else []
