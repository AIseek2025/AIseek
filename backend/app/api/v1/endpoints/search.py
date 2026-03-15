from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response
from sqlalchemy.orm import Session
from app.api.deps import get_read_db
from app.models.all_models import Post, AIJob, MediaAsset
from typing import List, Optional, Any
from pydantic import BaseModel
import time
import json
import secrets
import base64
from datetime import datetime

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
    cover_metrics: Optional[Any] = None
    subtitle_audit: Optional[Any] = None
    generation_quality: Optional[Any] = None
    analysis_audit: Optional[Any] = None
    
    class Config:
        orm_mode = True


class SearchShareViewsCreateReq(BaseModel):
    code: str


class SearchShareViewsCreateResp(BaseModel):
    key: str
    expires_at_ms: int


class SearchShareViewsResolveResp(BaseModel):
    code: str
    expires_at_ms: int


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


def _decode_share_code_payload(raw_code: str):
    code = str(raw_code or "").strip()
    if not code or not code.startswith("SV1."):
        return None
    try:
        b64url = code[4:]
        b64 = b64url.replace("-", "+").replace("_", "/")
        pad_len = (4 - (len(b64) % 4)) % 4
        padded = b64 + ("=" * pad_len)
        txt = base64.b64decode(padded.encode("utf-8")).decode("utf-8")
        parsed = json.loads(txt or "{}")
    except Exception:
        return None
    if not isinstance(parsed, dict):
        return None
    if str(parsed.get("schema") or "") != "search_history_views_share_v1":
        return None
    views = parsed.get("views")
    if not isinstance(views, list) or not views:
        return None
    try:
        issued_at_ms = int(parsed.get("issued_at_ms") or 0)
        expires_at_ms = int(parsed.get("expires_at_ms") or 0)
    except Exception:
        return None
    if issued_at_ms <= 0 or expires_at_ms <= 0 or expires_at_ms < issued_at_ms:
        return None
    parsed["issued_at_ms"] = issued_at_ms
    parsed["expires_at_ms"] = expires_at_ms
    return parsed


def _record_share_metric(event: str, share_key: str = "", detail: str = ""):
    ev = str(event or "").strip().lower()
    if not ev:
        return
    try:
        from app.core.cache import cache
    except Exception:
        return
    try:
        cache.hincrby("search:share:views:metrics:total", ev, 1, ttl=45 * 24 * 3600)
        day = datetime.utcnow().strftime("%Y%m%d")
        cache.hincrby(f"search:share:views:metrics:day:{day}", ev, 1, ttl=45 * 24 * 3600)
    except Exception:
        pass
    try:
        r = cache.redis()
        if not r:
            return
        payload = {
            "ts": int(time.time()),
            "event": ev,
            "key": str(share_key or "").strip()[:80],
            "detail": str(detail or "").strip()[:120],
        }
        raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        rk = "search:share:views:metrics:samples"
        r.lpush(rk, raw)
        r.ltrim(rk, 0, 199)
        r.expire(rk, 45 * 24 * 3600)
    except Exception:
        pass


@router.post("/share-views", response_model=SearchShareViewsCreateResp)
def create_search_share_views_short(req: SearchShareViewsCreateReq):
    code = str(req.code or "").strip()
    if not code:
        _record_share_metric("create_empty", detail="400")
        raise HTTPException(status_code=400, detail="empty_code")
    if len(code) > 20000:
        _record_share_metric("create_too_long", detail="400")
        raise HTTPException(status_code=400, detail="code_too_long")
    payload = _decode_share_code_payload(code)
    if not payload:
        _record_share_metric("create_invalid", detail="400")
        raise HTTPException(status_code=400, detail="invalid_code")
    now_ms = int(time.time() * 1000)
    expires_at_ms = int(payload.get("expires_at_ms") or 0)
    ttl_sec = int((expires_at_ms - now_ms) / 1000)
    if ttl_sec <= 0:
        _record_share_metric("create_expired", detail="400")
        raise HTTPException(status_code=400, detail="expired_code")
    if ttl_sec > 7 * 24 * 3600:
        ttl_sec = 7 * 24 * 3600
    try:
        from app.core.cache import cache, stable_sig
    except Exception:
        _record_share_metric("create_cache_unavailable", detail="503")
        raise HTTPException(status_code=503, detail="cache_unavailable")
    if not cache.redis_enabled():
        _record_share_metric("create_cache_unavailable", detail="503")
        raise HTTPException(status_code=503, detail="cache_unavailable")
    alias_key = f"search:share:views:alias:v1:{stable_sig(['share_views', code])}"
    try:
        alias = cache.get_json(alias_key)
        if isinstance(alias, dict):
            ex_key = str(alias.get("key") or "").strip()
            if ex_key:
                ex_payload = cache.get_json(f"search:share:views:v1:{ex_key}")
                if isinstance(ex_payload, dict):
                    ex_code = str(ex_payload.get("code") or "").strip()
                    ex_exp = int(ex_payload.get("expires_at_ms") or 0)
                    if ex_code == code and ex_exp > now_ms:
                        _record_share_metric("create_reused", share_key=ex_key, detail="200")
                        return {"key": ex_key, "expires_at_ms": ex_exp}
    except Exception:
        pass
    store = {"code": code, "expires_at_ms": expires_at_ms, "created_at_ms": now_ms}
    encoded = json.dumps(store, ensure_ascii=False)
    for _ in range(8):
        key = secrets.token_urlsafe(6).replace("=", "")
        if len(key) > 16:
            key = key[:16]
        redis_key = f"search:share:views:v1:{key}"
        try:
            if cache.set_nx(redis_key, encoded, ttl=ttl_sec):
                try:
                    cache.set_json(alias_key, {"key": key}, ttl=ttl_sec)
                except Exception:
                    pass
                _record_share_metric("create_ok", share_key=key, detail="200")
                return {"key": key, "expires_at_ms": expires_at_ms}
        except Exception:
            _record_share_metric("create_cache_unavailable", detail="503")
            raise HTTPException(status_code=503, detail="cache_unavailable")
    _record_share_metric("create_failed", detail="503")
    raise HTTPException(status_code=503, detail="short_link_create_failed")


@router.get("/share-views/{share_key}", response_model=SearchShareViewsResolveResp)
def resolve_search_share_views_short(share_key: str = Path(..., min_length=4, max_length=64)):
    key = str(share_key or "").strip()
    if not key:
        _record_share_metric("resolve_invalid_key", detail="400")
        raise HTTPException(status_code=400, detail="invalid_key")
    if not all(ch.isalnum() or ch in "-_" for ch in key):
        _record_share_metric("resolve_invalid_key", share_key=key, detail="400")
        raise HTTPException(status_code=400, detail="invalid_key")
    try:
        from app.core.cache import cache
    except Exception:
        _record_share_metric("resolve_cache_unavailable", share_key=key, detail="503")
        raise HTTPException(status_code=503, detail="cache_unavailable")
    if not cache.redis_enabled():
        _record_share_metric("resolve_cache_unavailable", share_key=key, detail="503")
        raise HTTPException(status_code=503, detail="cache_unavailable")
    redis_key = f"search:share:views:v1:{key}"
    try:
        payload = cache.get_json(redis_key)
    except Exception:
        _record_share_metric("resolve_cache_unavailable", share_key=key, detail="503")
        raise HTTPException(status_code=503, detail="cache_unavailable")
    if not isinstance(payload, dict):
        _record_share_metric("resolve_not_found", share_key=key, detail="404")
        raise HTTPException(status_code=404, detail="share_not_found")
    code = str(payload.get("code") or "").strip()
    expires_at_ms = int(payload.get("expires_at_ms") or 0)
    now_ms = int(time.time() * 1000)
    if not code or expires_at_ms <= now_ms:
        _record_share_metric("resolve_expired", share_key=key, detail="404")
        raise HTTPException(status_code=404, detail="share_expired")
    _record_share_metric("resolve_ok", share_key=key, detail="200")
    return {"code": code, "expires_at_ms": expires_at_ms}


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

    def _extract_job_observability(result_json: Any):
        out = {"cover_metrics": None, "subtitle_audit": None, "generation_quality": None, "analysis_audit": None}
        try:
            if not isinstance(result_json, dict):
                return out
            cv = result_json.get("cover") if isinstance(result_json.get("cover"), dict) else {}
            an = result_json.get("analysis") if isinstance(result_json.get("analysis"), dict) else {}
            sb = result_json.get("subtitle") if isinstance(result_json.get("subtitle"), dict) else {}
            qv = result_json.get("quality") if isinstance(result_json.get("quality"), dict) else {}
            if isinstance(cv.get("metrics"), dict):
                out["cover_metrics"] = cv.get("metrics")
            if isinstance(an.get("audit"), dict):
                out["analysis_audit"] = an.get("audit")
            if isinstance(sb.get("audit"), dict):
                out["subtitle_audit"] = sb.get("audit")
            if isinstance(qv.get("generation"), dict):
                out["generation_quality"] = qv.get("generation")
        except Exception:
            return out
        return out

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
                Post.ai_job_id,
            )
            .filter(Post.status == "done", Post.id.in_(ids))
            .all()
        )
        job_ids = []
        for r in rows or []:
            try:
                jid = str(r[7] or "").strip()
            except Exception:
                jid = ""
            if jid:
                job_ids.append(jid)
        job_obs = {}
        if job_ids:
            try:
                jrows = db.query(AIJob.id, AIJob.result_json).filter(AIJob.id.in_(list(set(job_ids)))).all()
                for jr in jrows or []:
                    try:
                        jid = str(jr[0] or "").strip()
                    except Exception:
                        jid = ""
                    if not jid:
                        continue
                    job_obs[jid] = _extract_job_observability(jr[1])
            except Exception:
                job_obs = {}
        media_fallback = {}
        try:
            post_ids = [int(r[0]) for r in (rows or []) if r and r[0] is not None]
        except Exception:
            post_ids = []
        if post_ids:
            try:
                from app.api.v1.endpoints.posts import _infer_subtitle_quality_from_tracks

                mrows = (
                    db.query(MediaAsset.post_id, MediaAsset.subtitle_tracks, MediaAsset.id)
                    .filter(MediaAsset.post_id.in_(list(set(post_ids))))
                    .order_by(MediaAsset.id.desc())
                    .all()
                )
                latest = {}
                for mr in mrows or []:
                    try:
                        pid = int(mr[0] or 0)
                    except Exception:
                        pid = 0
                    if pid <= 0:
                        continue
                    if pid in latest:
                        continue
                    latest[pid] = mr[1]
                for pid, tracks in latest.items():
                    sb, gq = _infer_subtitle_quality_from_tracks(tracks)
                    if sb is not None or gq is not None:
                        media_fallback[int(pid)] = {"subtitle_audit": sb, "generation_quality": gq}
            except Exception:
                media_fallback = {}
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
            jid = str(row[7] or "").strip()
            obs = job_obs.get(jid) or {}
            fb = media_fallback.get(int(row[0] or 0)) or {}
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
                    "cover_metrics": obs.get("cover_metrics"),
                    "analysis_audit": obs.get("analysis_audit"),
                    "subtitle_audit": obs.get("subtitle_audit") or fb.get("subtitle_audit"),
                    "generation_quality": obs.get("generation_quality") or fb.get("generation_quality"),
                }
            )
        return {"items": items, "next_cursor": nxt}

    payload = None
    try:
        from app.core.cache import cache, stable_sig

        pol = _search_posts_policy()
        key_q_max_len = int(pol.get("key_q_max_len", 64) or 64)
        cur = str(cursor or "")
        key = f"search:api:posts:items:v3:{stable_sig(['q', query_lc[:key_q_max_len], int(limit or 0), cur])}"
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
