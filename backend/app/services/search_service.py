import time
from typing import Callable, Iterable, List, Optional

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.cache import cache
from app.models.all_models import Post

try:
    from prometheus_client import Counter, Histogram

    ES_OP_TOTAL = Counter("aiseek_es_op_total", "ES ops total", ["op", "outcome"])
    ES_OP_LATENCY = Histogram("aiseek_es_op_latency_seconds", "ES ops latency seconds", ["op"])
    SEARCH_CACHE_TOTAL = Counter("aiseek_search_cache_total", "Search cache total", ["layer", "outcome", "has_cursor"])
except Exception:
    ES_OP_TOTAL = None
    ES_OP_LATENCY = None
    SEARCH_CACHE_TOTAL = None
_ES_CLIENTS = {}
_ES_CLIENT_SWEEP_AT = 0.0
_ES_DOWN_LOCAL_UNTIL = 0.0
_ES_DOWN_CACHE_AT = 0.0
_ES_DOWN_CACHE_VAL = False
_SEARCH_POSTS_POLICY_CACHE_AT = 0.0
_SEARCH_POSTS_POLICY_CACHE_VAL = None


def _search_posts_policy() -> dict:
    global _SEARCH_POSTS_POLICY_CACHE_AT, _SEARCH_POSTS_POLICY_CACHE_VAL
    now_ts = time.monotonic()
    cached = _SEARCH_POSTS_POLICY_CACHE_VAL
    if isinstance(cached, dict) and (now_ts - float(_SEARCH_POSTS_POLICY_CACHE_AT or 0.0)) < 2.0:
        return cached

    def _int_opt(s, name, default, lo, hi):
        try:
            v = int(getattr(s, name, default) or default)
        except Exception:
            v = default
        if v < lo:
            return lo
        if v > hi:
            return hi
        return v

    val = {
        "es_url": "",
        "es_index": "posts",
        "es_timeout": 1.6,
        "es_max_retries": 1,
        "es_retry_on_timeout": True,
        "key_q_max_len": 64,
        "ttl": 8,
        "lock_ttl": 2,
        "cursor_ttl": 4,
        "cursor_lock_ttl": 1,
    }
    try:
        s = get_settings()
        val["es_url"] = str(getattr(s, "ELASTICSEARCH_URL", "") or "").strip()
        val["es_index"] = str(getattr(s, "ELASTICSEARCH_INDEX", "posts") or "posts")
        try:
            val["es_timeout"] = float(getattr(s, "ES_REQUEST_TIMEOUT_SEC", 1.6) or 1.6)
        except Exception:
            val["es_timeout"] = 1.6
        val["es_max_retries"] = _int_opt(s, "ES_MAX_RETRIES", 1, 0, 5)
        val["es_retry_on_timeout"] = bool(getattr(s, "ES_RETRY_ON_TIMEOUT", True))
        val["key_q_max_len"] = _int_opt(s, "SEARCH_POSTS_CACHE_KEY_QUERY_MAX_LEN", 64, 8, 128)
        val["ttl"] = _int_opt(s, "SEARCH_POSTS_CACHE_TTL_SEC", 8, 1, 120)
        val["lock_ttl"] = _int_opt(s, "SEARCH_POSTS_CACHE_LOCK_TTL_SEC", 2, 1, 15)
        val["cursor_ttl"] = _int_opt(s, "SEARCH_POSTS_CURSOR_CACHE_TTL_SEC", 4, 1, 60)
        val["cursor_lock_ttl"] = _int_opt(s, "SEARCH_POSTS_CURSOR_CACHE_LOCK_TTL_SEC", 1, 1, 10)
    except Exception:
        pass

    _SEARCH_POSTS_POLICY_CACHE_AT = now_ts
    _SEARCH_POSTS_POLICY_CACHE_VAL = val
    return val


def search_posts(query: str, db: Session, limit: int = 50) -> List[Post]:
    s = get_settings()
    q = (query or "").strip()
    if not q:
        return []

    if not s.ELASTICSEARCH_URL:
        return _search_posts_db(q, db, limit)

    ids = _search_posts_es(
        q,
        s.ELASTICSEARCH_URL,
        s.ELASTICSEARCH_INDEX,
        limit,
        timeout=float(getattr(s, "ES_REQUEST_TIMEOUT_SEC", 1.6) or 1.6),
        max_retries=int(getattr(s, "ES_MAX_RETRIES", 1) or 1),
        retry_on_timeout=bool(getattr(s, "ES_RETRY_ON_TIMEOUT", True)),
    )
    if not ids:
        return _search_posts_db(q, db, limit)

    posts = db.query(Post).filter(Post.id.in_(ids), Post.status == "done").all()
    by_id = {p.id: p for p in posts}
    ordered = [by_id[i] for i in ids if i in by_id]
    return ordered


def _es_cooldown_sec() -> int:
    s = get_settings()
    try:
        v = int(getattr(s, "ES_COOLDOWN_SEC", 10) or 10)
    except Exception:
        v = 10
    if v < 1:
        v = 1
    if v > 300:
        v = 300
    return int(v)


def _es_down_until_key() -> str:
    s = get_settings()
    url = str(getattr(s, "ELASTICSEARCH_URL", "") or "").strip()
    idx = str(getattr(s, "ELASTICSEARCH_INDEX", "") or "").strip()
    try:
        from app.core.cache import stable_sig

        sk = stable_sig(["es", url, idx])[:16]
    except Exception:
        sk = "default"
    return f"es:down_until:{sk}"


def _es_down_check_interval_sec() -> float:
    s = get_settings()
    try:
        ms = int(getattr(s, "ES_DOWN_CHECK_INTERVAL_MS", 250) or 250)
    except Exception:
        ms = 250
    ms = max(50, min(10000, int(ms)))
    return float(ms) / 1000.0


def _es_is_down() -> bool:
    global _ES_DOWN_LOCAL_UNTIL, _ES_DOWN_CACHE_AT, _ES_DOWN_CACHE_VAL
    now_ts = time.time()
    if float(_ES_DOWN_LOCAL_UNTIL or 0.0) > now_ts:
        return True
    if float(_ES_DOWN_CACHE_AT or 0.0) > now_ts:
        return bool(_ES_DOWN_CACHE_VAL)
    try:
        v = cache.get_json(_es_down_until_key())
        until = float(v or 0.0)
        is_down = bool(until > now_ts)
        _ES_DOWN_CACHE_VAL = is_down
        _ES_DOWN_CACHE_AT = now_ts + float(_es_down_check_interval_sec())
        _ES_DOWN_LOCAL_UNTIL = until if is_down else 0.0
        return is_down
    except Exception:
        _ES_DOWN_CACHE_VAL = bool(float(_ES_DOWN_LOCAL_UNTIL or 0.0) > now_ts)
        _ES_DOWN_CACHE_AT = now_ts + float(_es_down_check_interval_sec())
        return bool(_ES_DOWN_CACHE_VAL)


def _mark_es_down() -> None:
    global _ES_DOWN_LOCAL_UNTIL, _ES_DOWN_CACHE_AT, _ES_DOWN_CACHE_VAL
    try:
        now_ts = time.time()
        until = float(now_ts + float(_es_cooldown_sec()))
        _ES_DOWN_LOCAL_UNTIL = until
        _ES_DOWN_CACHE_VAL = True
        _ES_DOWN_CACHE_AT = now_ts + float(_es_down_check_interval_sec())
        cache.set_json(_es_down_until_key(), until, ttl=int(_es_cooldown_sec()) + 5)
    except Exception:
        return


def _es_client_pool_params() -> tuple:
    s = get_settings()
    try:
        max_size = int(getattr(s, "ES_CLIENT_POOL_MAX", 32) or 32)
    except Exception:
        max_size = 32
    try:
        ttl_sec = int(getattr(s, "ES_CLIENT_TTL_SEC", 1800) or 1800)
    except Exception:
        ttl_sec = 1800
    try:
        sweep_interval_ms = int(getattr(s, "ES_CLIENT_SWEEP_INTERVAL_MS", 1000) or 1000)
    except Exception:
        sweep_interval_ms = 1000
    max_size = max(4, min(256, int(max_size)))
    ttl_sec = max(60, min(86400, int(ttl_sec)))
    sweep_interval_ms = max(100, min(60000, int(sweep_interval_ms)))
    return max_size, ttl_sec, (float(sweep_interval_ms) / 1000.0)


def _es_client_pool_sweep(now_ts: float, max_size: int, ttl_sec: int) -> None:
    stale = []
    for k, v in list(_ES_CLIENTS.items()):
        try:
            ts = float((v or {}).get("ts") or 0.0)
        except Exception:
            ts = 0.0
        if ts <= 0 or (now_ts - ts) > float(ttl_sec):
            stale.append(k)
    for k in stale:
        _ES_CLIENTS.pop(k, None)
    while len(_ES_CLIENTS) > int(max_size):
        try:
            oldest_k = min(_ES_CLIENTS.items(), key=lambda kv: float((kv[1] or {}).get("ts") or 0.0))[0]
        except Exception:
            break
        _ES_CLIENTS.pop(oldest_k, None)


def _get_es_client(url: str, timeout: float, max_retries: int, retry_on_timeout: bool):
    global _ES_CLIENT_SWEEP_AT
    try:
        from elasticsearch import Elasticsearch
    except Exception:
        return None
    key = (
        str(url or "").strip(),
        float(timeout or 1.6),
        int(max_retries or 1),
        bool(retry_on_timeout),
    )
    now_ts = time.time()
    max_size, ttl_sec, sweep_interval_sec = _es_client_pool_params()
    try:
        if now_ts >= float(_ES_CLIENT_SWEEP_AT or 0.0):
            _es_client_pool_sweep(now_ts, int(max_size), int(ttl_sec))
            _ES_CLIENT_SWEEP_AT = now_ts + float(sweep_interval_sec)
    except Exception:
        pass
    entry = _ES_CLIENTS.get(key)
    if isinstance(entry, dict):
        c = entry.get("c")
        if c is not None:
            entry["ts"] = now_ts
            return c
    try:
        opts = {
            "request_timeout": float(timeout or 1.6),
            "max_retries": int(max_retries or 1),
            "retry_on_timeout": bool(retry_on_timeout),
        }
        c = Elasticsearch(str(url), **opts)
        _ES_CLIENTS[key] = {"c": c, "ts": now_ts}
        return c
    except Exception:
        return None


def search_post_ids(query: str, db: Session, *, limit: int = 50, cursor: Optional[str] = None) -> dict:
    pol = _search_posts_policy()
    q = (query or "").strip()
    if not q:
        return {"ids": [], "next_cursor": None, "source": "none"}
    q_lc = q.lower()
    key_q_max_len = int(pol.get("key_q_max_len", 64) or 64)
    q_key = q_lc[:key_q_max_len]
    try:
        lim = int(limit or 50)
    except Exception:
        lim = 50
    if lim < 1:
        lim = 1
    if lim > 200:
        lim = 200

    key = ""
    key_ttl = int(pol.get("ttl", 8) or 8)
    key_lock_ttl = int(pol.get("lock_ttl", 2) or 2)
    try:
        from app.core.cache import stable_sig

        cur = str(cursor or "")
        key = f"search:posts:v3:{stable_sig(['posts', q_key, int(lim), cur])}"
        if cur:
            key_ttl = int(pol.get("cursor_ttl", 4) or 4)
            key_lock_ttl = int(pol.get("cursor_lock_ttl", 1) or 1)
    except Exception:
        key = ""

    def build():
        es_url = str(pol.get("es_url", "") or "")
        es_index = str(pol.get("es_index", "posts") or "posts")
        if not es_url or _es_is_down():
            out = _search_posts_db_ids(q, db, lim, cursor)
            out["source"] = "db"
            return out
        out = _search_posts_es_ids(
            q,
            es_url,
            es_index,
            lim,
            cursor=cursor,
            timeout=float(pol.get("es_timeout", 1.6) or 1.6),
            max_retries=int(pol.get("es_max_retries", 1) or 1),
            retry_on_timeout=bool(pol.get("es_retry_on_timeout", True)),
        )
        if not out.get("ids"):
            out = _search_posts_db_ids(q, db, lim, cursor)
            out["source"] = "db"
            return out
        out["source"] = "es"
        return out

    if key:
        built = {"v": False}

        def _build_marked():
            built["v"] = True
            return build()

        v = cache.get_or_set_json(key, ttl=int(key_ttl), builder=_build_marked, lock_ttl=int(key_lock_ttl))
        if SEARCH_CACHE_TOTAL is not None:
            try:
                SEARCH_CACHE_TOTAL.labels("search_post_ids", "miss" if built["v"] else "hit", "1" if cursor else "0").inc()
            except Exception:
                pass
        if isinstance(v, dict) and isinstance(v.get("ids"), list):
            return v
    out = build()
    return out if isinstance(out, dict) else {"ids": [], "next_cursor": None, "source": "none"}


def _search_posts_db(q: str, db: Session, limit: int) -> List[Post]:
    import sqlalchemy as sa
    from sqlalchemy import or_

    dialect = ""
    try:
        dialect = str(getattr(getattr(db, "bind", None), "dialect", None).name or "")
    except Exception:
        dialect = ""
    if dialect == "postgresql":
        vec = sa.func.to_tsvector(
            "simple",
            sa.func.coalesce(Post.title, "") + sa.literal(" ") + sa.func.coalesce(Post.content_text, ""),
        )
        tsq = sa.func.plainto_tsquery("simple", q)
        cond = vec.op("@@")(tsq)
        return (
            db.query(Post)
            .filter(Post.status == "done", or_(cond, Post.category.ilike(f"%{q}%")))
            .order_by(Post.created_at.desc())
            .limit(limit)
            .all()
        )

    return (
        db.query(Post)
        .filter(
            Post.status == "done",
            or_(
                Post.title.contains(q),
                Post.content_text.contains(q),
                Post.category.contains(q),
            ),
        )
        .order_by(Post.created_at.desc())
        .limit(limit)
        .all()
    )


def _search_posts_db_ids(q: str, db: Session, limit: int, cursor: Optional[str]) -> dict:
    import sqlalchemy as sa
    from sqlalchemy import and_, or_

    from app.utils.cursor import decode_cursor, encode_cursor, cursor_datetime

    dialect = ""
    try:
        dialect = str(getattr(getattr(db, "bind", None), "dialect", None).name or "")
    except Exception:
        dialect = ""
    if dialect == "postgresql":
        vec = sa.func.to_tsvector(
            "simple",
            sa.func.coalesce(Post.title, "") + sa.literal(" ") + sa.func.coalesce(Post.content_text, ""),
        )
        tsq = sa.func.plainto_tsquery("simple", q)
        cond = vec.op("@@")(tsq)
        query = db.query(Post.id, Post.created_at).filter(Post.status == "done", or_(cond, Post.category.ilike(f"%{q}%")))
    else:
        query = (
            db.query(Post.id, Post.created_at)
            .filter(
                Post.status == "done",
                or_(
                    Post.title.contains(q),
                    Post.content_text.contains(q),
                    Post.category.contains(q),
                ),
            )
        )
    cur = decode_cursor(cursor)
    cur_dt = cursor_datetime(cur, "created_at")
    cur_id = cur.get("id") if isinstance(cur, dict) else None
    if cur_dt is not None and isinstance(cur_id, int):
        query = query.filter(or_(Post.created_at < cur_dt, and_(Post.created_at == cur_dt, Post.id < cur_id)))
    rows = query.order_by(Post.created_at.desc(), Post.id.desc()).limit(int(limit)).all()
    ids: List[int] = []
    next_cursor = None
    if rows:
        for pid, _ in rows:
            try:
                ids.append(int(pid))
            except Exception:
                pass
        last = rows[-1]
        try:
            if last and last[1] is not None:
                next_cursor = encode_cursor({"created_at": float(last[1].timestamp()), "id": int(last[0])})
        except Exception:
            next_cursor = None
    return {"ids": ids, "next_cursor": next_cursor}


def _search_posts_es(q: str, url: str, index: str, limit: int, timeout: float = 1.6, max_retries: int = 1, retry_on_timeout: bool = True) -> List[int]:
    if _es_is_down():
        return []
    client = _get_es_client(url, timeout, max_retries, retry_on_timeout)
    if client is None:
        return []
    try:
        tracer = None
        try:
            from opentelemetry import trace

            tracer = trace.get_tracer("aiseek.search")
        except Exception:
            tracer = None

        t0 = time.time()
        if tracer:
            with tracer.start_as_current_span("es.search") as span:
                span.set_attribute("es.index", index)
                span.set_attribute("es.limit", int(limit))
                resp = client.search(
                    index=index,
                    size=limit,
                    query={
                        "multi_match": {
                            "query": q,
                            "fields": ["title^3", "content_text^2", "category"],
                            "type": "best_fields",
                        }
                    },
                    _source=False,
                )
        else:
            resp = client.search(
                index=index,
                size=limit,
                query={
                    "multi_match": {
                        "query": q,
                        "fields": ["title^3", "content_text^2", "category"],
                        "type": "best_fields",
                    }
                },
                _source=False,
            )
        dt = time.time() - t0
        try:
            if ES_OP_LATENCY:
                ES_OP_LATENCY.labels("search").observe(float(dt))
            if ES_OP_TOTAL:
                ES_OP_TOTAL.labels("search", "ok").inc()
        except Exception:
            pass
    except Exception:
        try:
            if ES_OP_TOTAL:
                ES_OP_TOTAL.labels("search", "err").inc()
        except Exception:
            pass
        _mark_es_down()
        return []

    hits = resp.get("hits", {}).get("hits", [])
    out: List[int] = []
    for h in hits:
        try:
            out.append(int(h.get("_id")))
        except Exception:
            continue
    return out


def _search_posts_es_ids(
    q: str,
    url: str,
    index: str,
    limit: int,
    *,
    cursor: Optional[str] = None,
    timeout: float = 1.6,
    max_retries: int = 1,
    retry_on_timeout: bool = True,
) -> dict:
    if _es_is_down():
        return {"ids": [], "next_cursor": None}
    client = _get_es_client(url, timeout, max_retries, retry_on_timeout)
    if client is None:
        return {"ids": [], "next_cursor": None}

    from app.utils.cursor import decode_cursor, encode_cursor

    sa = None
    try:
        cur = decode_cursor(cursor)
        if isinstance(cur, dict) and isinstance(cur.get("sa"), list):
            sa = cur.get("sa")
    except Exception:
        sa = None

    t0 = time.time()
    try:
        body = {
            "size": int(limit),
            "query": {
                "multi_match": {
                    "query": q,
                    "fields": ["title^3", "content_text^2", "category"],
                    "type": "best_fields",
                }
            },
            "sort": ["_score", {"_id": "asc"}],
            "_source": False,
        }
        if sa:
            body["search_after"] = sa
        resp = client.search(index=index, **body)
        dt = time.time() - t0
        try:
            if ES_OP_LATENCY:
                ES_OP_LATENCY.labels("search").observe(float(dt))
            if ES_OP_TOTAL:
                ES_OP_TOTAL.labels("search", "ok").inc()
        except Exception:
            pass
    except Exception:
        try:
            if ES_OP_TOTAL:
                ES_OP_TOTAL.labels("search", "err").inc()
        except Exception:
            pass
        _mark_es_down()
        return {"ids": [], "next_cursor": None}

    hits = resp.get("hits", {}).get("hits", [])
    out: List[int] = []
    next_cursor = None
    last_sort = None
    for h in hits:
        try:
            out.append(int(h.get("_id")))
            last_sort = h.get("sort")
        except Exception:
            continue
    if last_sort and isinstance(last_sort, list):
        try:
            next_cursor = encode_cursor({"sa": last_sort})
        except Exception:
            next_cursor = None
    return {"ids": out, "next_cursor": next_cursor}


def ensure_posts_alias(es_url: Optional[str] = None, alias: Optional[str] = None) -> Optional[str]:
    s = get_settings()
    url = es_url or s.ELASTICSEARCH_URL
    a = alias or s.ELASTICSEARCH_INDEX
    if not url or not a:
        return None
    client = _get_es_client(
        url,
        float(getattr(s, "ES_REQUEST_TIMEOUT_SEC", 1.6) or 1.6),
        int(getattr(s, "ES_MAX_RETRIES", 1) or 1),
        bool(getattr(s, "ES_RETRY_ON_TIMEOUT", True)),
    )
    if client is None:
        return None
    try:
        if client.indices.exists_alias(name=a):
            return str(a)
    except Exception:
        _mark_es_down()
        return None
    new_index = f"{a}-{time.strftime('%Y%m%d%H%M%S')}"
    try:
        shards = int(getattr(s, "ES_INDEX_SHARDS", 3) or 3)
    except Exception:
        shards = 3
    try:
        reps = int(getattr(s, "ES_INDEX_REPLICAS", 1) or 1)
    except Exception:
        reps = 1
    if shards < 1:
        shards = 1
    if shards > 24:
        shards = 24
    if reps < 0:
        reps = 0
    if reps > 5:
        reps = 5
    body = {
        "settings": {"number_of_shards": shards, "number_of_replicas": reps},
        "mappings": {
            "properties": {
                "title": {"type": "text"},
                "content_text": {"type": "text"},
                "category": {"type": "keyword"},
                "user_id": {"type": "integer"},
                "created_at": {"type": "date"},
            }
        },
    }
    try:
        client.indices.create(index=new_index, body=body)
        client.indices.put_alias(index=new_index, name=a)
        return str(a)
    except Exception:
        _mark_es_down()
        return None


def bulk_index_into_index(posts: Iterable[Post], es_url: str, index_name: str) -> int:
    s = get_settings()
    url = es_url
    idx = str(index_name or "").strip()
    if not url or not idx:
        return 0
    try:
        from elasticsearch import Elasticsearch, helpers
    except Exception:
        return 0
    opts = {
        "request_timeout": float(getattr(s, "ES_REQUEST_TIMEOUT_SEC", 1.6) or 1.6),
        "max_retries": int(getattr(s, "ES_MAX_RETRIES", 1) or 1),
        "retry_on_timeout": bool(getattr(s, "ES_RETRY_ON_TIMEOUT", True)),
    }
    client = Elasticsearch(url, **opts)
    try:
        chunk = int(getattr(s, "ES_BULK_CHUNK_SIZE", 500) or 500)
    except Exception:
        chunk = 500
    if chunk < 50:
        chunk = 50
    if chunk > 2000:
        chunk = 2000

    def actions():
        for post in posts:
            if not post:
                continue
            yield {
                "_op_type": "index",
                "_index": str(idx),
                "_id": str(int(post.id)),
                "_source": {
                    "title": post.title or "",
                    "content_text": post.content_text or "",
                    "category": post.category or "",
                    "user_id": int(post.user_id or 0),
                    "created_at": post.created_at.isoformat() if getattr(post, "created_at", None) else None,
                },
            }

    try:
        ok, _ = helpers.bulk(client, actions(), chunk_size=chunk, raise_on_error=False, refresh=False)
        return int(ok or 0)
    except Exception:
        return 0


def rebuild_posts_index(
    db: Session,
    *,
    limit: int = 5000,
    es_url: Optional[str] = None,
    alias: Optional[str] = None,
    progress: Optional[Callable[[dict], None]] = None,
    is_cancelled: Optional[Callable[[], bool]] = None,
) -> dict:
    s = get_settings()
    url = es_url or s.ELASTICSEARCH_URL
    a = alias or s.ELASTICSEARCH_INDEX
    if not url or not a:
        return {"ok": 0, "alias": str(a or ""), "new_index": None, "switched": False}
    try:
        from elasticsearch import Elasticsearch
        from elasticsearch import helpers
    except Exception:
        return {"ok": 0, "alias": str(a or ""), "new_index": None, "switched": False}
    opts = {
        "request_timeout": float(getattr(s, "ES_REQUEST_TIMEOUT_SEC", 1.6) or 1.6),
        "max_retries": int(getattr(s, "ES_MAX_RETRIES", 1) or 1),
        "retry_on_timeout": bool(getattr(s, "ES_RETRY_ON_TIMEOUT", True)),
    }
    if _es_is_down():
        return {"ok": 0, "alias": str(a), "new_index": None, "switched": False}
    client = Elasticsearch(url, **opts)
    new_index = f"{a}-{time.strftime('%Y%m%d%H%M%S')}"
    try:
        shards = int(getattr(s, "ES_INDEX_SHARDS", 3) or 3)
    except Exception:
        shards = 3
    try:
        reps = int(getattr(s, "ES_INDEX_REPLICAS", 1) or 1)
    except Exception:
        reps = 1
    if shards < 1:
        shards = 1
    if shards > 24:
        shards = 24
    if reps < 0:
        reps = 0
    if reps > 5:
        reps = 5
    body = {
        "settings": {"number_of_shards": shards, "number_of_replicas": reps},
        "mappings": {
            "properties": {
                "title": {"type": "text"},
                "content_text": {"type": "text"},
                "category": {"type": "keyword"},
                "user_id": {"type": "integer"},
                "created_at": {"type": "date"},
            }
        },
    }
    try:
        client.indices.create(index=new_index, body=body)
    except Exception:
        _mark_es_down()
        return {"ok": 0, "alias": str(a), "new_index": None, "switched": False}

    try:
        total = int(
            db.query(Post)
            .filter(Post.status == "done")
            .order_by(Post.created_at.desc())
            .limit(int(limit))
            .count()
        )
    except Exception:
        total = 0

    try:
        chunk = int(getattr(s, "ES_BULK_CHUNK_SIZE", 500) or 500)
    except Exception:
        chunk = 500
    if chunk < 50:
        chunk = 50
    if chunk > 2000:
        chunk = 2000

    def emit(obj: dict) -> None:
        if not progress:
            return
        try:
            progress(obj)
        except Exception:
            return

    emit({"status": "indexing", "alias": str(a), "new_index": str(new_index), "ok": 0, "total": int(total)})

    q = (
        db.query(Post)
        .filter(Post.status == "done")
        .order_by(Post.created_at.desc())
        .limit(int(limit))
    )

    def actions():
        for post in q.yield_per(200):
            if not post:
                continue
            yield {
                "_op_type": "index",
                "_index": str(new_index),
                "_id": str(int(post.id)),
                "_source": {
                    "title": post.title or "",
                    "content_text": post.content_text or "",
                    "category": post.category or "",
                    "user_id": int(post.user_id or 0),
                    "created_at": post.created_at.isoformat() if getattr(post, "created_at", None) else None,
                },
            }

    ok = 0
    i = 0
    try:
        throttle_ms = int(getattr(s, "ES_BULK_THROTTLE_MS", 0) or 0)
    except Exception:
        throttle_ms = 0
    if throttle_ms < 0:
        throttle_ms = 0
    if throttle_ms > 2000:
        throttle_ms = 2000
    try:
        for success, _ in helpers.streaming_bulk(client, actions(), chunk_size=chunk, raise_on_error=False, refresh=False):
            i += 1
            if success:
                ok += 1
            if i % 500 == 0:
                try:
                    if is_cancelled and bool(is_cancelled()):
                        emit({"status": "cancelled", "alias": str(a), "new_index": str(new_index), "ok": int(ok), "total": int(total)})
                        try:
                            client.indices.delete(index=str(new_index))
                        except Exception:
                            pass
                        return {"ok": int(ok), "alias": str(a), "new_index": str(new_index), "switched": False, "total": int(total), "cancelled": True}
                except Exception:
                    pass
                emit({"status": "indexing", "alias": str(a), "new_index": str(new_index), "ok": int(ok), "total": int(total)})
                if throttle_ms:
                    time.sleep(float(throttle_ms) / 1000.0)
    except Exception:
        _mark_es_down()
        emit({"status": "failed", "alias": str(a), "new_index": str(new_index), "ok": int(ok), "total": int(total)})
        return {"ok": int(ok), "alias": str(a), "new_index": str(new_index), "switched": False}

    emit({"status": "indexed", "alias": str(a), "new_index": str(new_index), "ok": int(ok), "total": int(total)})

    old = []
    try:
        actions = []
        try:
            if client.indices.exists_alias(name=a):
                cur = client.indices.get_alias(name=a)
                for idx in (cur or {}).keys():
                    old.append(str(idx))
                    actions.append({"remove": {"index": str(idx), "alias": str(a)}})
        except Exception:
            pass
        actions.append({"add": {"index": str(new_index), "alias": str(a)}})
        client.indices.update_aliases(body={"actions": actions})
    except Exception:
        _mark_es_down()
        try:
            if old:
                client.indices.update_aliases(body={"actions": [{"remove": {"index": str(new_index), "alias": str(a)}}]})
        except Exception:
            pass
        return {"ok": int(ok), "alias": str(a), "new_index": str(new_index), "switched": False}

    switched = False
    try:
        cur2 = client.indices.get_alias(name=a)
        switched = bool(cur2 and str(new_index) in cur2.keys())
    except Exception:
        switched = False
    if not switched:
        try:
            actions = [{"remove": {"index": str(new_index), "alias": str(a)}}]
            for idx in old:
                actions.append({"add": {"index": str(idx), "alias": str(a)}})
            client.indices.update_aliases(body={"actions": actions})
        except Exception:
            pass
        return {"ok": int(ok), "alias": str(a), "new_index": str(new_index), "switched": False}

    try:
        keep = int(getattr(s, "ES_ALIAS_KEEP_INDICES", 3) or 3)
    except Exception:
        keep = 3
    if keep < 1:
        keep = 1
    if keep > 10:
        keep = 10
    try:
        pat = f"{a}-"
        all_idx = sorted([k for k in (client.indices.get(index=f"{a}-*") or {}).keys() if str(k).startswith(pat)], reverse=True)
        for idx in all_idx[keep:]:
            try:
                client.indices.delete(index=str(idx))
            except Exception:
                pass
    except Exception:
        pass
    emit({"status": "done", "alias": str(a), "new_index": str(new_index), "ok": int(ok), "total": int(total)})
    return {"ok": int(ok), "alias": str(a), "new_index": str(new_index), "switched": True, "total": int(total)}


def index_post_to_es(post: Post, es_url: Optional[str] = None, es_index: Optional[str] = None) -> bool:
    s = get_settings()
    url = es_url or s.ELASTICSEARCH_URL
    index = es_index or s.ELASTICSEARCH_INDEX
    if not url:
        return False
    if not ensure_posts_alias(url, index):
        return False
    try:
        from elasticsearch import Elasticsearch
    except Exception:
        return False

    doc = {
        "title": post.title or "",
        "content_text": post.content_text or "",
        "category": post.category or "",
        "user_id": post.user_id,
        "created_at": post.created_at.isoformat() if getattr(post, "created_at", None) else None,
    }
    headers = None
    try:
        from app.core.request_context import get_request_id, get_session_id

        rid = get_request_id()
        sid = get_session_id()
        h = {}
        if rid:
            h["x-request-id"] = rid
        if sid:
            h["x-session-id"] = sid
        headers = h or None
    except Exception:
        headers = None

    opts = {
        "request_timeout": float(getattr(s, "ES_REQUEST_TIMEOUT_SEC", 1.6) or 1.6),
        "max_retries": int(getattr(s, "ES_MAX_RETRIES", 1) or 1),
        "retry_on_timeout": bool(getattr(s, "ES_RETRY_ON_TIMEOUT", True)),
    }
    client = Elasticsearch(url, headers=headers, **opts) if headers else Elasticsearch(url, **opts)
    try:
        tracer = None
        try:
            from opentelemetry import trace

            tracer = trace.get_tracer("aiseek.search")
        except Exception:
            tracer = None

        if tracer:
            with tracer.start_as_current_span("es.index") as span:
                span.set_attribute("es.index", index)
                span.set_attribute("post.id", int(post.id))
                client.index(index=index, id=str(post.id), document=doc, refresh=False)
        else:
            client.index(index=index, id=str(post.id), document=doc, refresh=False)
        return True
    except Exception:
        return False
