from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session
from app.api.deps import get_read_db
from app.models.all_models import Post
from typing import List, Optional
from pydantic import BaseModel
import time

router = APIRouter()

try:
    from prometheus_client import Counter

    SEARCH_API_CACHE_TOTAL = Counter("aiseek_search_api_cache_total", "Search API cache total", ["layer", "outcome", "has_cursor"])
except Exception:
    SEARCH_API_CACHE_TOTAL = None

class SearchResult(BaseModel):
    id: int
    title: Optional[str]
    summary: Optional[str]
    post_type: str
    video_url: Optional[str]
    images: Optional[List[str]]
    category: Optional[str]
    
    class Config:
        orm_mode = True


_SEARCH_POSTS_POLICY_CACHE_AT = 0.0
_SEARCH_POSTS_POLICY_CACHE_VAL = None


def _search_posts_policy():
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
        "key_q_max_len": 64,
        "ttl": 8,
        "cursor_ttl": 4,
        "lock_ttl": 2,
        "cursor_lock_ttl": 1,
        "rerank_enabled": True,
        "rerank_cursor_enabled": False,
        "rerank_group_size": 5,
    }
    try:
        from app.core.config import get_settings

        s = get_settings()
        val["key_q_max_len"] = _int_opt(s, "SEARCH_POSTS_CACHE_KEY_QUERY_MAX_LEN", 64, 8, 128)
        val["ttl"] = _int_opt(s, "SEARCH_POSTS_CACHE_TTL_SEC", 8, 1, 120)
        val["cursor_ttl"] = _int_opt(s, "SEARCH_POSTS_CURSOR_CACHE_TTL_SEC", 4, 1, 60)
        val["lock_ttl"] = _int_opt(s, "SEARCH_POSTS_CACHE_LOCK_TTL_SEC", 2, 1, 15)
        val["cursor_lock_ttl"] = _int_opt(s, "SEARCH_POSTS_CURSOR_CACHE_LOCK_TTL_SEC", 1, 1, 10)
        val["rerank_enabled"] = bool(getattr(s, "SEARCH_RERANK_ENABLED", True))
        val["rerank_cursor_enabled"] = bool(getattr(s, "SEARCH_RERANK_CURSOR_ENABLED", False))
        val["rerank_group_size"] = _int_opt(s, "SEARCH_RERANK_GROUP_SIZE", 5, 1, 50)
    except Exception:
        pass

    _SEARCH_POSTS_POLICY_CACHE_AT = now_ts
    _SEARCH_POSTS_POLICY_CACHE_VAL = val
    return val


@router.get("/hot", response_model=List[str])
def hot_search(limit: int = Query(10, ge=1, le=50)):
    from app.services.search_hot_service import get_hot_queries

    return get_hot_queries(limit=limit)

@router.get("/posts", response_model=List[SearchResult])
def search_posts(
    response: Response,
    q: str = Query(..., min_length=1, max_length=128),
    limit: int = Query(50, ge=1, le=200),
    cursor: Optional[str] = Query(None, max_length=512),
    db: Session = Depends(get_read_db),
):
    query = (q or "").strip()
    if not query:
        return []
    query_lc = query.lower()
    if cursor:
        try:
            from app.utils.cursor import decode_cursor

            if decode_cursor(cursor) is None:
                raise HTTPException(status_code=400, detail="invalid_cursor")
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=400, detail="invalid_cursor")
    from app.services.search_service import search_post_ids

    def _build_items():
        out = search_post_ids(query, db, limit=limit, cursor=cursor)
        ids = out.get("ids") if isinstance(out, dict) else None
        nxt = out.get("next_cursor") if isinstance(out, dict) else None
        if not ids:
            return {"items": [], "next_cursor": nxt}
        try:
            from app.services.engagement_service import get_search_ctr_map, rerank_in_groups

            pol = _search_posts_policy()
            rerank_enabled = bool(pol.get("rerank_enabled", True))
            if cursor and not bool(pol.get("rerank_cursor_enabled", False)):
                rerank_enabled = False
            if rerank_enabled:
                ctr = get_search_ctr_map(ids)
                group = int(pol.get("rerank_group_size", 5) or 5)
                ids = rerank_in_groups(list(ids), ctr, group_size=group)
        except Exception:
            pass
        rows = (
            db.query(
                Post.id,
                Post.title,
                Post.summary,
                Post.post_type,
                Post.video_url,
                Post.images,
                Post.category,
            )
            .filter(Post.status == "done", Post.id.in_(ids))
            .all()
        )
        by_id = {}
        for r in rows or []:
            try:
                by_id[int(r[0])] = r
            except Exception:
                continue
        items = []
        for i in ids:
            row = by_id.get(int(i))
            if not row:
                continue
            try:
                images = list(row[5] or [])
            except Exception:
                images = None
            items.append(
                {
                    "id": int(row[0] or 0),
                    "title": row[1],
                    "summary": row[2],
                    "post_type": row[3] or "video",
                    "video_url": row[4],
                    "images": images,
                    "category": row[6],
                }
            )
        return {"items": items, "next_cursor": nxt}

    payload = None
    try:
        from app.core.cache import cache, stable_sig

        pol = _search_posts_policy()
        key_q_max_len = int(pol.get("key_q_max_len", 64) or 64)
        cur = str(cursor or "")
        key = f"search:api:posts:items:v2:{stable_sig(['q', query_lc[:key_q_max_len], int(limit or 0), cur])}"
        ttl = int(pol.get("cursor_ttl", 4) if cur else pol.get("ttl", 8))
        lock_ttl = int(pol.get("cursor_lock_ttl", 1) if cur else pol.get("lock_ttl", 2))
        if ttl < 1:
            ttl = 1
        if ttl > (60 if cur else 120):
            ttl = 60 if cur else 120
        if lock_ttl < 1:
            lock_ttl = 1
        if lock_ttl > (10 if cur else 15):
            lock_ttl = 10 if cur else 15
        built = {"v": False}

        def _build_items_marked():
            built["v"] = True
            return _build_items()

        payload = cache.get_or_set_json(key, ttl=int(ttl), builder=_build_items_marked, lock_ttl=int(lock_ttl))
        if SEARCH_API_CACHE_TOTAL is not None:
            try:
                SEARCH_API_CACHE_TOTAL.labels("search_posts_items", "miss" if built["v"] else "hit", "1" if cur else "0").inc()
            except Exception:
                pass
    except Exception:
        payload = None
    if not isinstance(payload, dict):
        payload = _build_items()
    nxt = payload.get("next_cursor") if isinstance(payload, dict) else None
    if nxt:
        response.headers["x-next-cursor"] = str(nxt)
    items = payload.get("items") if isinstance(payload, dict) else []
    return items if isinstance(items, list) else []
