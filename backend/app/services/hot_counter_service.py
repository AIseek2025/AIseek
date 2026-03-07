import time
from typing import Dict, Optional, Tuple

from app.core.cache import cache
from app.core.config import get_settings
from app.core.redis_scripts import TOKEN_BUCKET

try:
    from prometheus_client import Counter

    HOT_SHED_DROPPED = Counter("hot_shed_dropped_total", "Hot shed dropped writes", ["op"])
except Exception:
    HOT_SHED_DROPPED = None


DELTA_TTL_SECONDS = 24 * 3600


def _enabled() -> bool:
    try:
        return bool(get_settings().HOT_COUNTERS_ENABLED)
    except Exception:
        return False


def write_mode() -> str:
    try:
        m = (get_settings().HOT_COUNTERS_WRITE_MODE or "dual").strip().lower()
        if m in {"dual", "redis"}:
            return m
    except Exception:
        pass
    return "dual"


def delta_key(post_id: int) -> str:
    return f"post:delta:{int(post_id)}"


def add_delta(post_id: int, *, likes: int = 0, favorites: int = 0, comments: int = 0, views: int = 0) -> None:
    if not _enabled() or write_mode() != "redis":
        return
    if not likes and not favorites and not comments and not views:
        return
    key = delta_key(post_id)
    script = (
        "local key=KEYS[1];"
        "local likes=tonumber(ARGV[1]) or 0;"
        "local favorites=tonumber(ARGV[2]) or 0;"
        "local comments=tonumber(ARGV[3]) or 0;"
        "local views=tonumber(ARGV[4]) or 0;"
        "local ttl=tonumber(ARGV[5]) or 0;"
        "if likes~=0 then redis.call('HINCRBY',key,'likes',likes); end;"
        "if favorites~=0 then redis.call('HINCRBY',key,'favorites',favorites); end;"
        "if comments~=0 then redis.call('HINCRBY',key,'comments',comments); end;"
        "if views~=0 then redis.call('HINCRBY',key,'views',views); end;"
        "if ttl>0 then redis.call('EXPIRE',key,ttl); end;"
        "return 1;"
    )
    try:
        cache.eval_cached(
            script,
            keys=[key],
            args=[str(int(likes)), str(int(favorites)), str(int(comments)), str(int(views)), str(int(DELTA_TTL_SECONDS))],
        )
    except Exception:
        if likes:
            cache.hincrby(key, "likes", int(likes), ttl=DELTA_TTL_SECONDS)
        if favorites:
            cache.hincrby(key, "favorites", int(favorites), ttl=DELTA_TTL_SECONDS)
        if comments:
            cache.hincrby(key, "comments", int(comments), ttl=DELTA_TTL_SECONDS)
        if views:
            cache.hincrby(key, "views", int(views), ttl=DELTA_TTL_SECONDS)


def _hot_bucket_params() -> Tuple[int, int]:
    s = get_settings()
    window = int(getattr(s, "FEED_RECALL_HOT_WINDOW_SEC", 86400) or 86400)
    if window < 60:
        window = 60
    if window > 2592000:
        window = 2592000
    bucket = int(getattr(s, "FEED_RECALL_HOT_BUCKET_SEC", 300) or 300)
    if bucket < 5:
        bucket = 5
    if bucket > 3600:
        bucket = 3600
    if bucket > window:
        bucket = window
    return window, bucket


def hot_bucket_key(bucket_sec: int, bucket_id: int) -> str:
    return f"hot:z:{int(bucket_sec)}:{int(bucket_id)}"


def _allow_hot_event(*, post_id: int, user_id: Optional[int], event: str, ttl_sec: int) -> bool:
    if not user_id or ttl_sec <= 0:
        return True
    r = cache._get_redis()  # noqa: SLF001
    if not r:
        return False
    key = f"hot:evt:{str(event)}:{int(post_id)}:{int(user_id)}"
    try:
        return bool(r.set(key, "1", nx=True, ex=int(ttl_sec)))
    except Exception:
        return False


def _view_delta(*, post_id: int, user_id: int, new_points: float, ttl_sec: int) -> float:
    if ttl_sec <= 0:
        return float(new_points or 0.0)
    try:
        n = float(new_points or 0.0)
    except Exception:
        return 0.0
    if n <= 0:
        return 0.0
    script = (
        "local key=KEYS[1];"
        "local n=tonumber(ARGV[1]) or 0;"
        "local ttl=tonumber(ARGV[2]) or 0;"
        "if n<=0 then return 0 end;"
        "local v=tonumber(redis.call('GET',key) or '0') or 0;"
        "if n<=v then return 0 end;"
        "redis.call('SET',key,tostring(n),'EX',ttl);"
        "return tostring(n-v);"
    )
    try:
        d = cache.eval(script, keys=[f"hot:evt:view:{int(post_id)}:{int(user_id)}"], args=[str(float(n)), str(int(ttl_sec))])
        try:
            return float(d or 0.0)
        except Exception:
            return 0.0
    except Exception:
        return 0.0


def compute_view_points(*, watch_time_sec: Optional[float], duration_sec: Optional[float], completed: bool, dwell_ms: Optional[int]) -> float:
    s = get_settings()
    try:
        full = float(getattr(s, "FEED_RECALL_VIEW_PCT_FULL", 0.9) or 0.9)
    except Exception:
        full = 0.9
    try:
        half = float(getattr(s, "FEED_RECALL_VIEW_PCT_HALF", 0.5) or 0.5)
    except Exception:
        half = 0.5
    try:
        t_short = float(getattr(s, "FEED_RECALL_VIEW_SEC_SHORT", 1.5) or 1.5)
    except Exception:
        t_short = 1.5
    try:
        t_mid = float(getattr(s, "FEED_RECALL_VIEW_SEC_MID", 5.0) or 5.0)
    except Exception:
        t_mid = 5.0
    try:
        p_full = float(getattr(s, "FEED_RECALL_VIEW_POINTS_FULL", 1.0) or 1.0)
    except Exception:
        p_full = 1.0
    try:
        p_half = float(getattr(s, "FEED_RECALL_VIEW_POINTS_HALF", 0.6) or 0.6)
    except Exception:
        p_half = 0.6
    try:
        p_mid = float(getattr(s, "FEED_RECALL_VIEW_POINTS_MID", 0.3) or 0.3)
    except Exception:
        p_mid = 0.3
    try:
        p_short = float(getattr(s, "FEED_RECALL_VIEW_POINTS_SHORT", 0.1) or 0.1)
    except Exception:
        p_short = 0.1

    wt = 0.0
    try:
        wt = float(watch_time_sec or 0.0)
    except Exception:
        wt = 0.0
    dur = 0.0
    try:
        dur = float(duration_sec or 0.0)
    except Exception:
        dur = 0.0
    ratio = (wt / dur) if dur > 0 else 0.0
    if completed or (dur > 0 and ratio >= full):
        return float(p_full)
    if dur > 0 and ratio >= half:
        return float(p_half)
    if wt >= t_mid:
        return float(p_mid)
    try:
        dm = int(dwell_ms or 0)
    except Exception:
        dm = 0
    if dm >= int(t_mid * 1000):
        return float(p_mid)
    if wt >= t_short:
        return float(p_short)
    if dm >= int(t_short * 1000):
        return float(p_short)
    return 0.0


def add_hot_rank(
    post_id: int,
    *,
    likes: int = 0,
    favorites: int = 0,
    comments: int = 0,
    shares: int = 0,
    views: int = 0,
    user_id: Optional[int] = None,
) -> None:
    if not _enabled() or write_mode() != "redis":
        return
    if not likes and not favorites and not comments and not shares and not views:
        return
    if not allow_post_write(int(post_id)):
        try:
            if HOT_SHED_DROPPED is not None:
                HOT_SHED_DROPPED.labels("hot_rank").inc()
        except Exception:
            pass
        return
    r = cache._get_redis()  # noqa: SLF001
    if not r:
        return
    s = get_settings()
    w_like = float(getattr(s, "FEED_RECALL_HOT_W_LIKE", 1.0) or 1.0)
    w_fav = float(getattr(s, "FEED_RECALL_HOT_W_FAVORITE", 3.0) or 3.0)
    w_comment = float(getattr(s, "FEED_RECALL_HOT_W_COMMENT", 2.0) or 2.0)
    w_repost = float(getattr(s, "FEED_RECALL_HOT_W_REPOST", 4.0) or 4.0)
    w_view = float(getattr(s, "FEED_RECALL_HOT_W_VIEW", 0.05) or 0.05)
    view_ttl = int(getattr(s, "FEED_RECALL_HOT_VIEW_DEDUPE_SEC", 30) or 30)
    if view_ttl < 0:
        view_ttl = 0
    if view_ttl > 3600:
        view_ttl = 3600
    repost_ttl = int(getattr(s, "FEED_RECALL_HOT_REPOST_DEDUPE_SEC", 60) or 60)
    if repost_ttl < 0:
        repost_ttl = 0
    if repost_ttl > 86400:
        repost_ttl = 86400
    window_sec, bucket_sec = _hot_bucket_params()
    now = int(time.time())
    bucket_id = now // int(bucket_sec)
    key = hot_bucket_key(bucket_sec, bucket_id)
    score = 0.0
    try:
        if likes:
            score += float(likes) * float(w_like)
        if favorites:
            score += float(favorites) * float(w_fav)
        if comments:
            score += float(comments) * float(w_comment)
        if shares:
            if int(shares) > 0 and (not _allow_hot_event(post_id=int(post_id), user_id=user_id, event="repost", ttl_sec=repost_ttl)):
                shares = 0
            score += float(shares) * float(w_repost)
        if views:
            if user_id:
                d = _view_delta(post_id=int(post_id), user_id=int(user_id), new_points=float(views), ttl_sec=view_ttl)
                score += float(d) * float(w_view)
            else:
                score += float(views) * float(w_view)
    except Exception:
        return
    if float(score) == 0.0:
        return
    try:
        script = (
            "local key=KEYS[1];"
            "local member=ARGV[1];"
            "local score=tonumber(ARGV[2]) or 0;"
            "local ttl=tonumber(ARGV[3]) or 0;"
            "if score==0 then return 0 end;"
            "redis.call('ZINCRBY',key,score,member);"
            "if ttl>0 then "
            "  local t=redis.call('TTL',key);"
            "  if (not t) or t<0 or t<math.floor(ttl/3) then redis.call('EXPIRE',key,ttl); end;"
            "end;"
            "return 1;"
        )
        cache.eval_cached(
            script,
            keys=[key],
            args=[str(int(post_id)), str(float(score)), str(int(window_sec + bucket_sec * 2))],
        )
    except Exception:
        return


def get_delta(post_id: int) -> Dict[str, int]:
    if not _enabled() or write_mode() != "redis":
        return {"likes": 0, "favorites": 0, "comments": 0, "views": 0}
    r = cache._get_redis()  # noqa: SLF001
    if not r:
        return {"likes": 0, "favorites": 0, "comments": 0, "views": 0}
    try:
        h = r.hgetall(delta_key(post_id))
    except Exception:
        return {"likes": 0, "favorites": 0, "comments": 0, "views": 0}
    out = {"likes": 0, "favorites": 0, "comments": 0, "views": 0}
    for k in out.keys():
        try:
            out[k] = int(h.get(k) or 0)
        except Exception:
            out[k] = 0
    return out


def get_deltas(post_ids: list[int]) -> Dict[int, Dict[str, int]]:
    if not post_ids:
        return {}
    if not _enabled() or write_mode() != "redis":
        return {}
    r = cache._get_redis()  # noqa: SLF001
    if not r:
        return {}
    uniq = []
    seen = set()
    for pid in post_ids:
        try:
            p = int(pid)
        except Exception:
            continue
        if p <= 0 or p in seen:
            continue
        seen.add(p)
        uniq.append(p)
    if not uniq:
        return {}
    pipe = r.pipeline()
    for pid in uniq:
        pipe.hgetall(delta_key(pid))
    try:
        rows = pipe.execute()
    except Exception:
        return {}
    out = {}
    for i, h in enumerate(rows or []):
        if not isinstance(h, dict) or not h:
            continue
        d = {"likes": 0, "favorites": 0, "comments": 0, "views": 0}
        for k in d.keys():
            try:
                d[k] = int(h.get(k) or 0)
            except Exception:
                d[k] = 0
        if d["likes"] or d["favorites"] or d["comments"] or d["views"]:
            out[int(uniq[i])] = d
    return out


def take_delta(post_id: int) -> Optional[Dict[str, int]]:
    if not _enabled() or write_mode() != "redis":
        return None

    script = (
        "local key=KEYS[1];"
        "local likes=redis.call('HGET',key,'likes') or '0';"
        "local favorites=redis.call('HGET',key,'favorites') or '0';"
        "local comments=redis.call('HGET',key,'comments') or '0';"
        "local views=redis.call('HGET',key,'views') or '0';"
        "redis.call('HSET',key,'likes','0','favorites','0','comments','0','views','0');"
        "return {likes,favorites,comments,views};"
    )
    res = cache.eval(script, keys=[delta_key(post_id)], args=[])
    if not res or not isinstance(res, (list, tuple)):
        return None
    try:
        return {"likes": int(res[0]), "favorites": int(res[1]), "comments": int(res[2]), "views": int(res[3])}
    except Exception:
        return None


def take_deltas(post_ids: list[int]) -> Dict[int, Dict[str, int]]:
    if not post_ids:
        return {}
    if not _enabled() or write_mode() != "redis":
        return {}

    r = cache._get_redis()  # noqa: SLF001
    if not r:
        return {}

    script = (
        "local key=KEYS[1];"
        "local likes=redis.call('HGET',key,'likes') or '0';"
        "local favorites=redis.call('HGET',key,'favorites') or '0';"
        "local comments=redis.call('HGET',key,'comments') or '0';"
        "local views=redis.call('HGET',key,'views') or '0';"
        "redis.call('HSET',key,'likes','0','favorites','0','comments','0','views','0');"
        "return {likes,favorites,comments,views};"
    )

    pipe = r.pipeline()
    for pid in post_ids:
        pipe.eval(script, 1, delta_key(pid))

    try:
        results = pipe.execute()
    except Exception:
        return {}

    out = {}
    for i, res in enumerate(results):
        if res and isinstance(res, (list, tuple)):
            try:
                l, f, c, v = int(res[0]), int(res[1]), int(res[2]), int(res[3])
                if l != 0 or f != 0 or c != 0 or v != 0:
                    out[post_ids[i]] = {"likes": l, "favorites": f, "comments": c, "views": v}
            except Exception:
                pass
    return out


def should_schedule_flush(post_id: int, min_interval_sec: int = 2) -> bool:
    if not _enabled():
        return False
    r = cache._get_redis()  # noqa: SLF001
    if not r:
        return True
    key = f"post:flush:{int(post_id)}"
    try:
        return bool(r.set(key, "1", nx=True, ex=int(min_interval_sec)))
    except Exception:
        return True


def mark_dirty(post_id: int) -> bool:
    if not _enabled() or write_mode() != "redis":
        return False
    r = cache._get_redis()  # noqa: SLF001
    if not r:
        return False
    try:
        s = get_settings()
        shards = int(getattr(s, "HOT_DIRTY_SHARDS", 8) or 8)
        shard = int(post_id) % max(1, shards)
        r.zadd(f"post:dirty:{shard}", {str(int(post_id)): int(time.time())})
        return True
    except Exception:
        return False


def should_schedule_dirty_flush(shard: int) -> bool:
    if not _enabled() or write_mode() != "redis":
        return False
    r = cache._get_redis()  # noqa: SLF001
    if not r:
        return False
    try:
        s = get_settings()
        ttl = int(getattr(s, "HOT_DIRTY_FLUSH_DEBOUNCE_SEC", 1) or 1)
    except Exception:
        ttl = 1
    try:
        return bool(r.set(f"post:dirty:flush_lock:{int(shard)}", "1", nx=True, ex=ttl))
    except Exception:
        return True


def shard_for_post(post_id: int) -> int:
    try:
        shards = int(get_settings().HOT_DIRTY_SHARDS or 8)
    except Exception:
        shards = 8
    return int(post_id) % max(1, int(shards))


def allow_post_write(post_id: int) -> bool:
    try:
        s = get_settings()
        if not bool(getattr(s, "HOT_SHED_ENABLED", False)):
            return True
        limit = int(getattr(s, "HOT_SHED_POST_WRITE_PER_SEC", 500) or 500)
    except Exception:
        return True

    r = cache._get_redis()  # noqa: SLF001
    if not r:
        return True
    try:
        burst = int(getattr(get_settings(), "HOT_SHED_BURST", 200) or 200)
        rate = max(0.001, float(limit))
        key = f"post:tb:{int(post_id)}"
        ok = bool(int(cache.eval_cached(TOKEN_BUCKET, keys=[key], args=[str(rate), str(burst), str(time.time()), "1"])) == 1)
        if not ok and HOT_SHED_DROPPED is not None:
            try:
                HOT_SHED_DROPPED.labels("write").inc()
            except Exception:
                pass
        return ok
    except Exception:
        return True
