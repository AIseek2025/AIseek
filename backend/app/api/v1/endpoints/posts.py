from fastapi import APIRouter, Depends, HTTPException, Response, Header, Request, Body, Query
from sqlalchemy.orm import Session, joinedload
from app.api.deps import get_current_user_optional, get_db, get_read_db
from app.models.all_models import Post, Interaction, User, Follow, Category, MediaAsset, AIJob
from typing import List, Optional, Any
from pydantic import BaseModel
from sqlalchemy import or_
from datetime import datetime
import uuid
import subprocess
from pathlib import Path

from app.core.cache import cache
from app.core.ai_stages import stage_rank, allow_draft_write, allow_assistant_message_write
from app.services.feed_service import get_feed as get_feed_service
from app.services.post_presenter import decorate_flags, serialize_post_base

router = APIRouter()


def _probe_local_video_duration_sec(source_url: Optional[str]) -> Optional[int]:
    try:
        s = str(source_url or "")
        target_path = ""
        if s.startswith("http://") or s.startswith("https://"):
            target_path = s
        elif s.startswith("/static/"):
            p = Path(__file__).resolve().parents[4] / "static" / s[len("/static/") :]
            if p.exists() and p.is_file():
                target_path = str(p)
        
        if not target_path:
            return None

        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            target_path,
        ]
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=10).decode("utf-8", errors="ignore").strip()
        d = int(round(float(out)))
        return d if d > 0 else None
    except Exception:
        return None


def _normalize_duration_value(value: Optional[Any]) -> Optional[int]:
    try:
        if value is None:
            return None
        d = int(value)
        return d if d > 0 else None
    except Exception:
        return None


def _pick_duration_with_fallback(
    duration: Optional[Any],
    mp4_url: Optional[str],
    video_url: Optional[str],
    source_url: Optional[str],
) -> Optional[int]:
    d = _normalize_duration_value(duration)
    if d:
        return d
    for u in (mp4_url, video_url, source_url):
        d2 = _probe_local_video_duration_sec(u)
        if d2:
            return d2
    return None

class PostCreate(BaseModel):
    content: str = "" # Optional if file uploaded
    post_type: str = "video"
    custom_instructions: Optional[str] = None
    user_id: Optional[int] = None
    category: Optional[str] = None
    voice_style: Optional[str] = None # New
    bgm_mood: Optional[str] = None # New
    # New fields for Creator Upload
    title: Optional[str] = None
    file_key: Optional[str] = None # S3 Key or Local Key
    images: Optional[List[str]] = None # List of S3 Keys for image post
    duration: Optional[int] = None

class PostOut(BaseModel):
    id: int
    title: Optional[str]
    summary: Optional[str]
    post_type: str
    video_url: Optional[str]
    hls_url: Optional[str] = None
    mp4_url: Optional[str] = None
    images: Optional[List[str]]
    cover_url: Optional[str] = None
    subtitle_tracks: Optional[Any] = None
    duration: Optional[int] = None
    video_width: Optional[int] = None
    video_height: Optional[int] = None
    media_version: Optional[str] = None
    created_at: Optional[datetime] = None
    views_count: int
    likes_count: int
    status: str
    category: Optional[str]
    ai_job_id: Optional[str] = None
    
    # User Info
    user_id: int
    user_nickname: Optional[str]
    user_avatar: Optional[str]
    content_text: Optional[str]
    comments_count: int
    favorites_count: int = 0
    shares_count: int = 0
    downloads_count: int = 0
    download_enabled: bool = False
    is_liked: bool = False
    is_favorited: bool = False
    is_reposted: bool = False
    is_following: bool = False
    error_message: Optional[str] = None
    
    class Config:
        orm_mode = True

class CallbackData(BaseModel):
    job_id: str
    post_id: Optional[int] = None
    status: str
    progress: Optional[int] = None
    stage: Optional[str] = None
    stage_message: Optional[str] = None
    draft_json: Optional[Any] = None
    assistant_message: Optional[str] = None
    no_post_status: Optional[bool] = None
    video_url: Optional[str] = None
    hls_url: Optional[str] = None
    mp4_url: Optional[str] = None
    media_version: Optional[str] = None
    cover_url: Optional[str] = None
    duration: Optional[int] = None
    video_width: Optional[int] = None
    video_height: Optional[int] = None
    images: Optional[List[str]] = None
    error: Optional[str] = None
    title: Optional[str] = None
    summary: Optional[str] = None
    subtitle_tracks: Optional[Any] = None
    placeholder_trace: Optional[Any] = None
    placeholder_audit: Optional[Any] = None
    cover_trace: Optional[Any] = None
    cover_audit: Optional[Any] = None


class MediaAssetOut(BaseModel):
    id: int
    version: str
    hls_url: Optional[str] = None
    mp4_url: Optional[str] = None
    cover_url: Optional[str] = None
    duration: Optional[int] = None
    video_width: Optional[int] = None
    video_height: Optional[int] = None
    subtitle_tracks: Optional[Any] = None
    background_audit: Optional[Any] = None
    created_at: Optional[datetime] = None

    class Config:
        orm_mode = True


class MediaActivateIn(BaseModel):
    user_id: int
    media_asset_id: Optional[int] = None
    version: Optional[str] = None


class DownloadSettingsIn(BaseModel):
    user_id: int
    download_enabled: bool = False


class PublishIn(BaseModel):
    user_id: int


class DownloadOut(BaseModel):
    kind: str
    filename: Optional[str] = None
    url: Optional[str] = None
    files: Optional[List[str]] = None

def _serialize_post_base(post: Post) -> dict:
    return serialize_post_base(post)


def _serialize_posts_base(posts: List[Post]) -> List[dict]:
    from app.services.post_presenter import serialize_posts_base

    return serialize_posts_base(posts)


def _maybe_current_user_id(authorization: Optional[str], db: Session) -> Optional[int]:
    try:
        from app.api.v1.endpoints.users import get_current_user

        u = get_current_user(authorization=authorization, db=db)
        return int(getattr(u, "id", 0) or 0) or None
    except Exception:
        return None


@router.get("/user/{user_id}", response_model=List[PostOut])
def get_user_posts(
    user_id: int,
    response: Response,
    viewer_id: Optional[int] = None,
    ai_only: bool = False,
    limit: int = 50,
    cursor: Optional[str] = None,
    db: Session = Depends(get_read_db),
):
    from sqlalchemy import and_, or_

    from app.utils.cursor import decode_cursor, encode_cursor, cursor_datetime

    show_all_for_owner = viewer_id is not None and int(viewer_id) == int(user_id)
    if show_all_for_owner:
        query = db.query(Post).filter(Post.user_id == user_id, Post.status.in_(["done", "preview", "processing", "queued", "failed", "returned"]))
    else:
        query = db.query(Post).filter(Post.user_id == user_id, Post.status == "done")
    if bool(ai_only):
        query = query.filter(Post.ai_job_id.isnot(None))
    cur = decode_cursor(cursor)
    cur_dt = cursor_datetime(cur, "created_at")
    cur_id = cur.get("id") if isinstance(cur, dict) else None
    if cur_dt is not None and isinstance(cur_id, int):
        query = query.filter(or_(Post.created_at < cur_dt, and_(Post.created_at == cur_dt, Post.id < cur_id)))

    posts = query.options(joinedload(Post.owner), joinedload(Post.active_media_asset)).order_by(Post.created_at.desc(), Post.id.desc()).limit(limit).all()
    if posts:
        last = posts[-1]
        if getattr(last, "created_at", None) is not None:
            response.headers["x-next-cursor"] = encode_cursor({
                "created_at": float(last.created_at.timestamp()),
                "id": int(last.id),
            })
    items = _serialize_posts_base(posts)
    return decorate_flags(items, viewer_id or user_id, db)


@router.get("/search", response_model=List[PostOut])
def search_posts(
    response: Response,
    query: str = Query(..., min_length=1, max_length=128),
    user_id: Optional[int] = None,
    limit: int = Query(50, ge=1, le=200),
    cursor: Optional[str] = Query(None, max_length=512),
    db: Session = Depends(get_read_db),
):
    q = query.strip()
    if not q:
        return []
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
    from app.core.config import get_settings

    s = get_settings()
    q_lc = q.lower()
    try:
        key_q_max_len = int(getattr(s, "SEARCH_POSTS_CACHE_KEY_QUERY_MAX_LEN", 64) or 64)
    except Exception:
        key_q_max_len = 64
    key_q_max_len = max(8, min(128, int(key_q_max_len)))
    q_key = q_lc[:key_q_max_len]
    try:
        ttl = int(getattr(s, "SEARCH_POSTS_CACHE_TTL_SEC", 8) or 8)
    except Exception:
        ttl = 8
    try:
        lock_ttl = int(getattr(s, "SEARCH_POSTS_CACHE_LOCK_TTL_SEC", 2) or 2)
    except Exception:
        lock_ttl = 2
    cur = str(cursor or "")
    if cur:
        try:
            ttl = int(getattr(s, "SEARCH_POSTS_CURSOR_CACHE_TTL_SEC", 4) or 4)
        except Exception:
            ttl = 4
        try:
            lock_ttl = int(getattr(s, "SEARCH_POSTS_CURSOR_CACHE_LOCK_TTL_SEC", 1) or 1)
        except Exception:
            lock_ttl = 1
    ttl = max(1, min(60 if cur else 120, int(ttl)))
    lock_ttl = max(1, min(10 if cur else 15, int(lock_ttl)))
    key = ""
    try:
        from app.core.cache import stable_sig
        key = f"search:posts:items:v3:{stable_sig(['posts', q_key, int(limit or 0), cur])}"
    except Exception:
        key = ""

    def _build_payload():
        out = search_post_ids(q, db, limit=limit, cursor=cursor)
        ids = out.get("ids") if isinstance(out, dict) else None
        nxt = out.get("next_cursor") if isinstance(out, dict) else None
        if not ids:
            return {"items": [], "next_cursor": nxt}
        posts = db.query(Post).options(joinedload(Post.owner), joinedload(Post.active_media_asset)).filter(Post.status == "done", Post.id.in_(ids)).all()
        by_id = {int(p.id): p for p in posts if p}
        ordered = [by_id[i] for i in ids if i in by_id]
        items = _serialize_posts_base(ordered)
        return {"items": items, "next_cursor": nxt}

    payload = None
    if key:
        try:
            payload = cache.get_or_set_json(key, ttl=int(ttl), builder=_build_payload, lock_ttl=int(lock_ttl))
        except Exception:
            payload = None
    if not isinstance(payload, dict):
        payload = _build_payload()
    nxt = payload.get("next_cursor") if isinstance(payload, dict) else None
    if nxt:
        response.headers["x-next-cursor"] = str(nxt)
    items = payload.get("items") if isinstance(payload, dict) else []
    if not isinstance(items, list):
        items = []
    return decorate_flags(items, user_id, db)


@router.get("/categories")
def list_categories(db: Session = Depends(get_read_db)):
    v = cache.version("categories")
    key = f"categories:v{v}"

    def _build():
        cats = db.query(Category).filter(Category.is_active == True).order_by(Category.sort_order.asc(), Category.id.asc()).all()
        return [c.name for c in cats if c and c.name]

    return cache.get_or_set_json(key, ttl=300, builder=_build) or []


@router.get("/{post_id}", response_model=PostOut)
def get_post(
    post_id: int,
    user_id: Optional[int] = None,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_read_db)
):
    # Try to get user_id from token if not provided
    if user_id is None and authorization:
        uid = _maybe_current_user_id(authorization, db)
        if uid:
            user_id = uid

    try:
        if user_id is not None:
            post0 = db.query(Post).options(joinedload(Post.owner), joinedload(Post.active_media_asset)).filter(Post.id == post_id).first()
            if post0:
                # Allow owner to see preview/processing/etc
                # Added "preview" to the allowed statuses
                if int(user_id) == int(post0.user_id) and str(post0.status) in {"processing", "queued", "failed", "returned", "preview"}:
                    base0 = _serialize_post_base(post0)
                    items0 = decorate_flags([base0], user_id, db)
                    return items0[0]
    except Exception:
        pass
    pv = cache.version(f"post:{int(post_id)}")
    key = f"post:v{pv}:id{int(post_id)}"

    def _build():
        post = db.query(Post).options(joinedload(Post.owner), joinedload(Post.active_media_asset)).filter(Post.id == post_id).first()
        if not post or post.status != "done":
            return None
        return _serialize_post_base(post)

    base = cache.get_or_set_json(key, ttl=60, builder=_build)
    if not base:
        raise HTTPException(status_code=404, detail="Post not found")
    items = decorate_flags([base], user_id, db)
    return items[0]


@router.post("/{post_id}/remove")
def remove_own_post(
    post_id: int,
    current_user: User = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    uid = int(getattr(current_user, "id", 0) or 0) if current_user else 0
    if uid <= 0:
        raise HTTPException(status_code=401, detail="Not authenticated")
    post = db.query(Post).filter(Post.id == int(post_id)).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    is_admin = bool(getattr(current_user, "is_superuser", False)) if current_user else False
    if not is_admin and int(getattr(post, "user_id", 0) or 0) != int(uid):
        raise HTTPException(status_code=403, detail="forbidden")
    post.status = "removed"
    db.commit()
    try:
        cache.bump("feed:all")
        if getattr(post, "category", None):
            cache.bump(f"feed:{post.category}")
        cache.bump(f"post:{int(post.id)}")
    except Exception:
        pass
    return {"ok": True, "post_id": int(post.id), "status": str(post.status)}

@router.post("/create", response_model=PostOut)
def create_post(post_in: PostCreate, current_user: User = Depends(get_current_user_optional), db: Session = Depends(get_db)):
    uid = int(getattr(current_user, "id", 0) or 0) if current_user else int(post_in.user_id or 0)
    if uid <= 0:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if post_in.user_id is not None and int(post_in.user_id) != int(uid):
        raise HTTPException(status_code=403, detail="forbidden")
    user = current_user if current_user else db.query(User).filter(User.id == int(uid)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if getattr(user, "is_active", True) is False:
        raise HTTPException(status_code=403, detail="Account disabled")
    # 1. Create DB Record
    is_upload = bool(post_in.file_key or post_in.images)
    
    db_post = Post(
        user_id=uid,
        content_text=post_in.content,
        post_type=post_in.post_type,
        custom_instructions=post_in.custom_instructions,
        status="processing" if is_upload else "queued",
        category=post_in.category,
        title=post_in.title,
        download_enabled=True,
    )
    
    video_input = None
    use_s3 = False
    should_enqueue_process = False

    if is_upload:
        from app.core.config import settings
        use_s3 = settings.R2_ACCESS_KEY_ID and settings.R2_SECRET_ACCESS_KEY
        if use_s3:
            base_url = settings.R2_PUBLIC_URL.rstrip('/')
        else:
            base_url = "/static"

        if post_in.post_type == "video" and post_in.file_key:
            if post_in.file_key.startswith("http"):
                db_post.source_url = post_in.file_key
                db_post.video_url = post_in.file_key
                video_input = post_in.file_key
                should_enqueue_process = bool(use_s3)
                db_post.status = "processing" if should_enqueue_process else "done"
            else:
                db_post.source_key = post_in.file_key
                local_abs = Path(__file__).resolve().parents[4] / "static" / str(post_in.file_key)
                local_exists = bool(str(post_in.file_key).startswith("uploads/") and local_abs.exists() and local_abs.is_file())
                if local_exists:
                    db_post.source_url = f"/static/{post_in.file_key}"
                    db_post.video_url = db_post.source_url
                    video_input = db_post.source_url
                    should_enqueue_process = False
                    db_post.status = "done"
                else:
                    db_post.source_url = f"{base_url}/{post_in.file_key}"
                    db_post.video_url = db_post.source_url
                    if use_s3:
                        video_input = post_in.file_key
                        should_enqueue_process = True
                        db_post.status = "processing"
                    else:
                        video_input = db_post.source_url
                        should_enqueue_process = False
                        db_post.status = "done"
            if post_in.duration is not None:
                try:
                    d = int(post_in.duration)
                    if d > 0:
                        db_post.duration = d
                except Exception:
                    pass
            if not getattr(db_post, "duration", None):
                d2 = _probe_local_video_duration_sec(getattr(db_post, "source_url", None))
                if d2:
                    db_post.duration = int(d2)
            
        elif post_in.post_type == "image_text" and (post_in.images or post_in.file_key):
            if post_in.file_key:
                 key = post_in.file_key
                 url = f"{base_url}/{key}" if not key.startswith("http") else key
                 db_post.images = [url]
            else:
                 db_post.images = [f"{base_url}/{key}" if not key.startswith("http") else key for key in post_in.images]
            db_post.status = "done"
            
    db.add(db_post)
    db.commit()
    db.refresh(db_post)

    ai_job_id = None
    if not is_upload:
        try:
            ai_job_id = str(uuid.uuid4())
            db_post.ai_job_id = ai_job_id
            job = AIJob(
                id=ai_job_id,
                user_id=int(uid),
                post_id=int(db_post.id),
                kind="generate_video",
                status="queued",
                progress=0,
                stage="queued",
                stage_message=None,
                input_json={
                    "post_type": post_in.post_type,
                    "content": post_in.content,
                    "category": post_in.category,
                    "custom_instructions": post_in.custom_instructions,
                    "voice_style": post_in.voice_style,
                    "bgm_mood": post_in.bgm_mood,
                    "title": post_in.title,
                },
            )
            db.add(job)
            db.commit()
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass

    try:
        cache.bump("feed:all")
        if post_in.category:
            cache.bump(f"feed:{post_in.category}")
        cache.bump(f"post:{int(db_post.id)}")
    except Exception:
        pass
    
    # Update user stats
    # Stats updates are handled by counter service elsewhere
    
    try:
        from app.services.queue_service import send_worker_task

        if is_upload:
            if post_in.post_type == "video":
                if video_input and should_enqueue_process:
                    send_worker_task("process_upload_video", args=[str(db_post.id), video_input, str(uid)])
        else:
            tid = send_worker_task("generate_video", args=[str(ai_job_id or db_post.id), post_in.content, str(uid)], kwargs={
                "post_type": post_in.post_type,
                "custom_instructions": post_in.custom_instructions,
                "voice_style": post_in.voice_style,
                "bgm_mood": post_in.bgm_mood,
                "post_id": int(db_post.id),
            })
            try:
                if ai_job_id:
                    job2 = db.query(AIJob).filter(AIJob.id == str(ai_job_id)).first()
                    if job2:
                        job2.worker_task_id = str(tid or "") or getattr(job2, "worker_task_id", None)
                        job2.status = "queued"
                        job2.stage = "queued"
                        if int(getattr(job2, "progress", 0) or 0) < 1:
                            job2.progress = 1
                        if str(getattr(job2, "stage_message", "") or "") in {"", "None", "已派发"}:
                            job2.stage_message = "已派发，等待处理"
                        job2.error = None
                        db.commit()
            except Exception:
                try:
                    db.rollback()
                except Exception:
                    pass
    except Exception as e:
        if not is_upload: 
            db_post.status = "queued"
            try:
                if ai_job_id:
                    job2 = db.query(AIJob).filter(AIJob.id == str(ai_job_id)).first()
                    if job2:
                        job2.status = "queued"
                        job2.stage = "dispatch_failed"
                        job2.stage_message = "任务派发失败，可重试"
                        job2.error = str(e)
            except Exception:
                pass
            db.commit()

    try:
        if db_post.status == "done":
            from app.tasks.search_index import index_post
            from app.core.celery_app import apply_async_with_context

            apply_async_with_context(index_post, args=[int(db_post.id)], dedupe_key=f"index_post:{int(db_post.id)}", dedupe_ttl=10, max_queue_depth=10000, drop_when_overloaded=True)
    except Exception:
        pass
    
    base = _serialize_post_base(db_post)
    return decorate_flags([base], uid, db)[0]

@router.post("/callback")
async def worker_callback(
    data: CallbackData,
    request: Request,
    x_worker_ts: str = Header(None),
    x_worker_sig: str = Header(None),
    x_worker_secret: str = Header(None),
    db: Session = Depends(get_db),
):
    import logging
    logger = logging.getLogger("uvicorn.error")
    logger.info(f"DEBUG: callback received for job_id={data.job_id} status={data.status} progress={data.progress}")

    """Receive status updates from worker."""
    def _metric(field: str, delta: int = 1, threshold_key: str = "", sample_payload: Optional[dict] = None) -> None:
        try:
            day = datetime.utcnow().strftime("%Y%m%d")
            k = f"metrics:worker_cb:{day}"
            d = int(delta)
            if d == 0:
                return
            v = cache.hincrby(k, str(field or "x"), int(d), ttl=172800)
            if v is None:
                return
            tk = str(threshold_key or "").strip()
            if not tk:
                return
            th = cache.get_json("metrics:worker_cb:thresholds")
            if not isinstance(th, dict):
                th = _default_cb_thresholds()
            cfg = th.get(tk) if isinstance(th.get(tk), dict) else None
            if not isinstance(cfg, dict):
                cfg = (_default_cb_thresholds().get(tk) or {})
            y = int(cfg.get("y") or 0)
            r = int(cfg.get("r") or 0)
            if r < y:
                r = y
            prev = int(v) - int(d)
            lvl = ""
            tval = 0
            if r > 0 and prev < r <= int(v):
                lvl = "red"
                tval = int(r)
            elif y > 0 and prev < y <= int(v):
                lvl = "yellow"
                tval = int(y)
            if not lvl:
                return
            latch_key = f"metrics:worker_cb:alerted:{day}:{tk}:{lvl}"
            try:
                if cache.get_json(latch_key) is not None:
                    return
                cache.set_json(latch_key, 1, ttl=172800)
            except Exception:
                pass
            akey = f"metrics:worker_cb:alerts:{day}"
            arr = cache.get_json(akey)
            if not isinstance(arr, list):
                arr = []
            aid = ""
            try:
                from app.core.cache import stable_sig

                aid = stable_sig([day, tk, lvl, str(field or ""), int(v), int(tval)])
            except Exception:
                aid = ""
            arr.append(
                {
                    "id": aid,
                    "ts": int(datetime.utcnow().timestamp()),
                    "level": lvl,
                    "key": tk,
                    "field": str(field or ""),
                    "value": int(v),
                    "threshold": int(tval),
                    "payload": sample_payload or {},
                }
            )
            if len(arr) > 100:
                arr = arr[-100:]
            cache.set_json(akey, arr, ttl=172800)
        except Exception:
            pass
    def _sample(kind: str, payload: dict) -> None:
        try:
            day = datetime.utcnow().strftime("%Y%m%d")
            key = f"metrics:worker_cb:samples:{day}"
            arr = cache.get_json(key)
            if not isinstance(arr, list):
                arr = []
            item = {"ts": int(datetime.utcnow().timestamp()), "kind": str(kind or "")[:64], "payload": payload or {}}
            arr.append(item)
            if len(arr) > 60:
                arr = arr[-60:]
            cache.set_json(key, arr, ttl=172800)
        except Exception:
            pass
    try:
        from app.core.config import settings
        import hmac
        import hashlib
        import time

        secret = str(getattr(settings, "WORKER_SECRET", "") or "")
        if getattr(settings, "READINESS_STRICT", False) and secret == "m3pro_worker_2026":
            raise HTTPException(status_code=500, detail="misconfigured_worker_secret")
        ok = False
        raw = None
        if x_worker_ts and x_worker_sig:
            try:
                ts = int(str(x_worker_ts).strip())
            except Exception:
                ts = 0
            now = int(time.time())
            window = int(getattr(settings, "WORKER_SIG_WINDOW_SEC", 300) or 300)
            if window < 30:
                window = 30
            if ts <= 0 or abs(now - ts) > window:
                raise HTTPException(status_code=401, detail="Unauthorized")
            raw = await request.body()
            msg = str(ts).encode("utf-8") + b"." + raw
            exp = hmac.new(secret.encode("utf-8"), msg=msg, digestmod=hashlib.sha256).hexdigest()
            if not hmac.compare_digest(exp, str(x_worker_sig).strip()):
                raise HTTPException(status_code=401, detail="Unauthorized")
            ok = True
        if not ok:
            if getattr(settings, "WORKER_SIGNED_CALLBACK_REQUIRED", False):
                raise HTTPException(status_code=401, detail="Unauthorized")
            if not x_worker_secret or not hmac.compare_digest(str(x_worker_secret), secret):
                raise HTTPException(status_code=401, detail="Unauthorized")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        from app.core.config import settings
        import hashlib

        jid = str(getattr(data, "job_id", "") or "").strip()
        if not jid:
            jid = str(getattr(data, "post_id", "") or "").strip()
        if not raw:
            try:
                raw = await request.body()
            except Exception:
                raw = b""
        sig_key = ""
        if x_worker_ts and x_worker_sig:
            sig_key = f"ts:{str(x_worker_ts).strip()}:{str(x_worker_sig).strip()[:18]}"
        else:
            sig_key = hashlib.sha256(raw).hexdigest()[:18]
        dedupe_key = f"cb:worker:{jid}:{sig_key}"
        ttl = int(getattr(settings, "WORKER_SIG_WINDOW_SEC", 300) or 300) + 120
        try:
            if not cache.set_nx(dedupe_key, "1", ttl):
                payload = {"job_id": str(getattr(data, "job_id", "") or ""), "post_id": getattr(data, "post_id", None), "stage": getattr(data, "stage", None), "status": getattr(data, "status", None)}
                _metric("dup", 1, "dup", payload)
                _sample("dup", payload)
                return {"status": "ok", "dup": True}
        except Exception:
            try:
                if cache.get_json(dedupe_key) is not None:
                    payload = {"job_id": str(getattr(data, "job_id", "") or ""), "post_id": getattr(data, "post_id", None), "stage": getattr(data, "stage", None), "status": getattr(data, "status", None)}
                    _metric("dup", 1, "dup", payload)
                    _sample("dup", payload)
                    return {"status": "ok", "dup": True}
                cache.set_json(dedupe_key, 1, ttl=ttl)
            except Exception:
                pass
    except Exception:
        pass

    post = None
    post_id = None
    job = None
    try:
        if data.job_id:
            job = db.query(AIJob).filter(AIJob.id == str(data.job_id)).first()
    except Exception:
        job = None
    try:
        if data.post_id is not None:
            post_id = int(data.post_id)
        elif job and getattr(job, "post_id", None) is not None:
            post_id = int(job.post_id)
        else:
            post_id = int(data.job_id)
    except Exception:
        post_id = None
    if post_id is not None:
        post = db.query(Post).filter(Post.id == int(post_id)).first()
    
    # Allow callback if either Post or Job exists
    if not post and not job:
        raise HTTPException(status_code=404, detail="Post or Job not found")

    st = (data.status or "").strip().lower()
    if st in {"completed", "success", "published"}:
        st = "done"
    if st in {"error"}:
        st = "failed"
    if st in {"canceled", "cancelled"}:
        st = "cancelled"
    if st not in {"queued", "processing", "done", "failed", "cancelled"}:
        st = "failed"

    st_post = "failed" if st == "cancelled" else ("preview" if st == "done" else st)
    try:
        def _allow_status_transition(cur: str, nxt: str) -> bool:
            c = str(cur or "").strip().lower()
            n = str(nxt or "").strip().lower()
            if not c:
                return True
            if c == n:
                return True
            allow = {
                "queued": {"queued", "processing", "preview", "done", "failed", "cancelled"},
                "processing": {"processing", "preview", "done", "failed", "cancelled"},
                "preview": {"preview", "done", "failed", "cancelled"},
                "done": {"done"},
                "failed": {"failed", "processing", "done", "cancelled"},
                "cancelled": {"cancelled"},
            }
            return n in allow.get(c, {n})

        cur_job = str(getattr(job, "status", "") or "") if job else ""
        cur_post = str(getattr(post, "status", "") or "") if post else ""
        
        if job and not _allow_status_transition(cur_job, st):
            payload = {"reason": "job_status_regress", "job_id": str(getattr(data, "job_id", "") or ""), "post_id": int(getattr(post, "id", 0) or 0) if post else 0, "cur": cur_job, "new": st, "stage": getattr(data, "stage", None), "progress": getattr(data, "progress", None)}
            _metric("ignored_job_status_regress", 1, "ij", payload)
            _sample("ignored", payload)
            return {"status": "ok", "ignored": True, "reason": "job_status_regress", "cur": cur_job, "new": st}
        if post and data.no_post_status is not True and not _allow_status_transition(cur_post, st_post):
            payload = {"reason": "post_status_regress", "job_id": str(getattr(data, "job_id", "") or ""), "post_id": int(getattr(post, "id", 0) or 0), "cur": cur_post, "new": st_post, "stage": getattr(data, "stage", None), "progress": getattr(data, "progress", None)}
            _metric("ignored_post_status_regress", 1, "ip", payload)
            _sample("ignored", payload)
            return {"status": "ok", "ignored": True, "reason": "post_status_regress", "cur": cur_post, "new": st_post}
    except Exception:
        pass
    
    if post and data.no_post_status is not True:
        post.status = st_post
    try:
        if job:
            job.status = st
            cur_prog = 0
            try:
                cur_prog = max(0, min(100, int(getattr(job, "progress", 0) or 0)))
            except Exception:
                cur_prog = 0
            new_prog = None
            regressing = False
            if data.progress is not None:
                try:
                    new_prog = max(0, min(100, int(data.progress)))
                except Exception:
                    new_prog = None
            if new_prog is not None:
                if new_prog < cur_prog:
                    regressing = True
                    payload = {"job_id": str(getattr(data, "job_id", "") or ""), "post_id": int(getattr(post, "id", 0) or 0), "cur": int(cur_prog), "new": int(new_prog), "stage": getattr(data, "stage", None)}
                    _metric("progress_regress", 1, "pr", payload)
                    _sample("progress_regress", payload)
                    new_prog = cur_prog
                try:
                    job.progress = int(new_prog)
                except Exception:
                    pass
            if data.stage and not regressing:
                try:
                    cur_stage = str(getattr(job, "stage", "") or "")
                    cur_r = stage_rank(cur_stage)
                    new_r = stage_rank(str(data.stage))
                    p_now = int(getattr(job, "progress", 0) or 0)
                    if new_r >= cur_r or (new_prog is not None and int(new_prog) >= p_now):
                        job.stage = str(data.stage)[:120]
                except Exception:
                    try:
                        job.stage = str(data.stage)[:120]
                    except Exception:
                        pass
            if data.stage_message is not None and not regressing:
                job.stage_message = str(data.stage_message)
            if data.draft_json is not None and not regressing and allow_draft_write(data.stage):
                try:
                    job.draft_json = data.draft_json
                except Exception:
                    pass
                try:
                    from app.models.all_models import AIJobDraftVersion

                    src = str(data.stage or "worker")[:64]
                    db.add(AIJobDraftVersion(job_id=str(job.id), user_id=int(job.user_id), source=src, draft_json=data.draft_json))
                except Exception:
                    pass
            if data.assistant_message and not regressing and allow_assistant_message_write(data.stage):
                try:
                    from app.models.all_models import AIJobMessage

                    msg = str(data.assistant_message or "").strip()
                    if msg:
                        db.add(AIJobMessage(job_id=str(job.id), user_id=int(job.user_id), role="assistant", content=msg))
                except Exception:
                    pass
            if st == "failed" and data.error:
                job.error = str(data.error)
            try:
                ph_trace = data.placeholder_trace
                ph_audit = data.placeholder_audit
                if ph_trace is not None or ph_audit is not None:
                    cur = getattr(job, "result_json", None)
                    if not isinstance(cur, dict):
                        cur = {}
                    ph = cur.get("placeholder") if isinstance(cur.get("placeholder"), dict) else {}
                    if ph_trace is not None:
                        if isinstance(ph_trace, list):
                            ph["trace"] = ph_trace[-400:]
                        else:
                            ph["trace"] = ph_trace
                    if ph_audit is not None:
                        ph["audit"] = ph_audit
                    ph["updated_at"] = datetime.utcnow().isoformat()
                    cur["placeholder"] = ph
                    job.result_json = cur
                    try:
                        day = datetime.utcnow().strftime("%Y%m%d")
                        k = f"metrics:placeholder:{day}"
                        provs = []
                        if isinstance(ph_audit, dict):
                            if str(ph_audit.get("type") or "") == "composed" and isinstance(ph_audit.get("segments"), list):
                                for s in ph_audit.get("segments")[:20]:
                                    if isinstance(s, dict) and s.get("provider"):
                                        provs.append(str(s.get("provider")))
                            elif ph_audit.get("provider"):
                                provs.append(str(ph_audit.get("provider")))
                        for p in provs[:20]:
                            cache.hincrby(k, f"picked:{p}", 1, ttl=172800)
                    except Exception:
                        pass
                cv_trace = data.cover_trace
                cv_audit = data.cover_audit
                if cv_trace is not None or cv_audit is not None:
                    cur = getattr(job, "result_json", None)
                    if not isinstance(cur, dict):
                        cur = {}
                    cv = cur.get("cover") if isinstance(cur.get("cover"), dict) else {}
                    if cv_trace is not None:
                        if isinstance(cv_trace, list):
                            cv["trace"] = cv_trace[-300:]
                        else:
                            cv["trace"] = cv_trace
                    if cv_audit is not None:
                        cv["audit"] = cv_audit
                    cv["updated_at"] = datetime.utcnow().isoformat()
                    cur["cover"] = cv
                    job.result_json = cur
            except Exception:
                pass
            logger.info(f"DEBUG: committing job update job_id={job.id} status={job.status} progress={job.progress}")
            db.commit()
            logger.info(f"DEBUG: commit successful")
            try:
                from app.api.v1.endpoints.ai_jobs import _append_job_event

                _append_job_event(
                    str(job.id),
                    "progress",
                    {
                        "status": st,
                        "progress": int(getattr(job, "progress", 0) or 0),
                        "stage": getattr(job, "stage", None),
                        "stage_message": getattr(job, "stage_message", None),
                    },
                )
                if data.assistant_message:
                    _append_job_event(str(job.id), "assistant", {"message": str(data.assistant_message or "")[:500]})
            except Exception:
                pass
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
    hls_url = (data.hls_url or "").strip() or None
    mp4_url = (data.mp4_url or "").strip() or None
    video_url = (data.video_url or "").strip() or None
    if not hls_url and video_url and video_url.lower().endswith(".m3u8"):
        hls_url = video_url
    if not mp4_url and video_url and not video_url.lower().endswith(".m3u8"):
        mp4_url = video_url

    cov = (data.cover_url or "").strip() or None
    ver = (data.media_version or "").strip() or None
    if not ver:
        ver = str(uuid.uuid4())

    final_duration = _pick_duration_with_fallback(
        data.duration,
        mp4_url,
        video_url,
        getattr(post, "source_url", None),
    )

    if hls_url or mp4_url or cov:
        asset = MediaAsset(
            post_id=int(post.id),
            version=ver,
            hls_url=hls_url,
            mp4_url=mp4_url,
            cover_url=cov,
            duration=final_duration,
            video_width=int(data.video_width) if data.video_width is not None else None,
            video_height=int(data.video_height) if data.video_height is not None else None,
            subtitle_tracks=data.subtitle_tracks,
            background_audit=data.placeholder_audit,
        )
        db.add(asset)
        db.flush()
        try:
            post.active_media_asset_id = int(asset.id)
        except Exception:
            pass

    if hls_url or mp4_url:
        post.video_url = hls_url or mp4_url
    if mp4_url:
        post.processed_url = mp4_url
    if cov:
        post.cover_url = cov
    if final_duration is not None:
        post.duration = int(final_duration)
    if data.video_width is not None:
        try:
            post.video_width = int(data.video_width)
        except Exception:
            pass
    if data.video_height is not None:
        try:
            post.video_height = int(data.video_height)
        except Exception:
            pass
    if data.images:
        post.images = data.images
    if data.title:
        try:
            cur = str(getattr(post, "title", "") or "").strip()
            incoming = str(data.title or "").strip()
            if incoming and incoming.lower() != "untitled":
                if (not cur) or (cur.lower() == "untitled"):
                    post.title = incoming
        except Exception:
            post.title = data.title
    if data.summary:
        post.summary = data.summary
    if data.error:
        post.error_message = data.error
    elif st == "cancelled":
        post.error_message = "已取消"
        
    db.commit()

    try:
        cache.bump("feed:all")
        if post.category:
            cache.bump(f"feed:{post.category}")
        cache.bump(f"post:{int(post.id)}")
    except Exception:
        pass

    try:
        if post.status == "done":
            from app.tasks.search_index import index_post
            from app.core.celery_app import apply_async_with_context

            apply_async_with_context(index_post, args=[int(post.id)], dedupe_key=f"index_post:{int(post.id)}", dedupe_ttl=10, max_queue_depth=10000, drop_when_overloaded=True)
    except Exception:
        pass
    return {"status": "ok"}


class AdminPostUserOut(BaseModel):
    id: int
    username: str
    nickname: Optional[str] = None


class AdminPostOut(BaseModel):
    id: int
    title: Optional[str] = None
    summary: Optional[str] = None
    post_type: str
    status: str
    category: Optional[str] = None
    cover_url: Optional[str] = None
    video_url: Optional[str] = None
    images: Optional[List[str]] = None
    likes_count: int = 0
    comments_count: int = 0
    created_at: Optional[datetime] = None
    user: Optional[AdminPostUserOut] = None


def _require_admin(authorization: str = Header(None), db: Session = Depends(get_db)) -> User:
    from app.api.v1.endpoints.users import get_current_user

    u = get_current_user(authorization=authorization, db=db)
    if not getattr(u, "is_superuser", False):
        raise HTTPException(status_code=403, detail="Forbidden")
    return u


@router.post("/admin/fix_durations")
def admin_fix_durations(
    limit: int = 50,
    current_user: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    from sqlalchemy import or_
    posts = db.query(Post).filter(Post.status == "done", or_(Post.duration == 0, Post.duration == None)).limit(limit).all()
    updated = []
    for p in posts:
        d = _probe_local_video_duration_sec(getattr(p, "video_url", None) or getattr(p, "processed_url", None) or getattr(p, "source_url", None))
        if d and d > 0:
            p.duration = int(d)
            updated.append({"id": int(p.id), "duration": int(d)})
    
    if updated:
        db.commit()
        for item in updated:
            try:
                cache.bump(f"post:{item['id']}")
            except Exception:
                pass
        try:
            cache.bump("feed:all")
        except Exception:
            pass
            
    return {"ok": True, "count": len(updated), "updated": updated}


@router.get("/admin/list", response_model=List[AdminPostOut])
def admin_list_posts(
    q: Optional[str] = None,
    username: Optional[str] = None,
    status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100,
    current_user: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    from sqlalchemy import or_

    lim = int(limit or 100)
    if lim < 1:
        lim = 1
    if lim > 500:
        lim = 500

    query = db.query(Post).options(joinedload(Post.owner)).order_by(Post.created_at.desc(), Post.id.desc())
    if status and status.strip():
        query = query.filter(Post.status == status.strip())
    if start_date or end_date:
        import datetime as _dt

        sd = (start_date or "").strip()
        ed = (end_date or "").strip()
        try:
            if sd:
                ds = _dt.date.fromisoformat(sd)
                query = query.filter(Post.created_at >= _dt.datetime(ds.year, ds.month, ds.day))
        except Exception:
            raise HTTPException(status_code=400, detail="bad_start_date")
        try:
            if ed:
                de = _dt.date.fromisoformat(ed)
                query = query.filter(Post.created_at < (_dt.datetime(de.year, de.month, de.day) + _dt.timedelta(days=1)))
        except Exception:
            raise HTTPException(status_code=400, detail="bad_end_date")
    if q and q.strip():
        qq = q.strip()
        query = query.filter(or_(Post.title.contains(qq), Post.summary.contains(qq), Post.content_text.contains(qq)))
    if username and username.strip():
        uu = username.strip()
        query = query.join(User, User.id == Post.user_id).filter(or_(User.username.contains(uu), User.nickname.contains(uu), User.aiseek_id.contains(uu)))

    posts = query.limit(lim).all()
    out: List[dict] = []
    for p in posts:
        owner = getattr(p, "owner", None)
        out.append({
            "id": int(p.id),
            "title": getattr(p, "title", None),
            "summary": getattr(p, "summary", None),
            "post_type": getattr(p, "post_type", "video"),
            "status": getattr(p, "status", "") or "",
            "category": getattr(p, "category", None),
            "cover_url": getattr(p, "cover_url", None),
            "video_url": getattr(p, "video_url", None),
            "images": getattr(p, "images", None),
            "likes_count": int(getattr(p, "likes_count", 0) or 0),
            "comments_count": int(getattr(p, "comments_count", 0) or 0),
            "created_at": getattr(p, "created_at", None),
            "user": {
                "id": int(getattr(owner, "id", 0) or 0),
                "username": getattr(owner, "username", "") or "",
                "nickname": getattr(owner, "nickname", None),
            } if owner else None
        })
    return out


@router.get("/admin/metrics/worker-callback")
def admin_worker_callback_metrics(
    days: int = 7,
    current_user: User = Depends(_require_admin),
):
    d = int(days or 7)
    if d < 1:
        d = 1
    if d > 30:
        d = 30
    today = datetime.utcnow().date()
    series: List[dict] = []
    totals: dict = {}
    for i in range(d):
        day = today.fromordinal(today.toordinal() - i)
        key = f"metrics:worker_cb:{day.strftime('%Y%m%d')}"
        raw = cache.hgetall(key) or {}
        cur: dict = {}
        for k, v in raw.items():
            try:
                cur[str(k)] = int(v)
            except Exception:
                cur[str(k)] = 0
        series.append({"day": day.strftime("%Y-%m-%d"), "metrics": cur})
        for k, v in cur.items():
            try:
                totals[k] = int(totals.get(k) or 0) + int(v or 0)
            except Exception:
                pass
    series.reverse()
    mode = "local"
    try:
        mode = "redis" if bool(cache.redis_enabled()) else "local"
    except Exception:
        mode = "local"
    return {"days": d, "totals": totals, "series": series, "storage": mode}


@router.get("/admin/metrics/worker-callback/samples")
def admin_worker_callback_samples(
    days: int = 1,
    limit: int = 30,
    current_user: User = Depends(_require_admin),
):
    d = int(days or 1)
    if d < 1:
        d = 1
    if d > 7:
        d = 7
    lim = int(limit or 30)
    if lim < 1:
        lim = 1
    if lim > 200:
        lim = 200
    today = datetime.utcnow().date()
    out: List[dict] = []
    for i in range(d):
        day = today.fromordinal(today.toordinal() - i)
        key = f"metrics:worker_cb:samples:{day.strftime('%Y%m%d')}"
        arr = cache.get_json(key)
        if not isinstance(arr, list):
            continue
        for it in reversed(arr):
            if not isinstance(it, dict):
                continue
            out.append(it)
            if len(out) >= lim:
                break
        if len(out) >= lim:
            break
    mode = "local"
    try:
        mode = "redis" if bool(cache.redis_enabled()) else "local"
    except Exception:
        mode = "local"
    return {"days": d, "limit": lim, "items": out[:lim], "storage": mode}


@router.get("/admin/metrics/worker-callback/alerts")
def admin_worker_callback_alerts(
    days: int = 3,
    limit: int = 50,
    include_acked: bool = True,
    current_user: User = Depends(_require_admin),
):
    d = int(days or 3)
    if d < 1:
        d = 1
    if d > 30:
        d = 30
    lim = int(limit or 50)
    if lim < 1:
        lim = 1
    if lim > 300:
        lim = 300
    today = datetime.utcnow().date()
    out: List[dict] = []
    for i in range(d):
        day = today.fromordinal(today.toordinal() - i)
        day_key = day.strftime("%Y%m%d")
        key = f"metrics:worker_cb:alerts:{day_key}"
        arr = cache.get_json(key)
        if not isinstance(arr, list):
            continue
        for it in reversed(arr):
            if not isinstance(it, dict):
                continue
            item = dict(it)
            try:
                aid = str(item.get("id") or "").strip()
                if aid:
                    ack_key = f"metrics:worker_cb:alerts_ack:{day_key}:{aid}"
                    item["ack"] = bool(cache.get_json(ack_key))
                item["day"] = day_key
            except Exception:
                pass
            if include_acked is not True:
                try:
                    if bool(item.get("ack")):
                        continue
                except Exception:
                    pass
            out.append(item)
            if len(out) >= lim:
                break
        if len(out) >= lim:
            break
    mode = "local"
    try:
        mode = "redis" if bool(cache.redis_enabled()) else "local"
    except Exception:
        mode = "local"
    return {"days": d, "limit": lim, "items": out[:lim], "storage": mode}


@router.post("/admin/metrics/worker-callback/alerts/{day}/{alert_id}/ack")
def admin_ack_worker_callback_alert(
    day: str,
    alert_id: str,
    current_user: User = Depends(_require_admin),
):
    d = str(day or "").strip()
    aid = str(alert_id or "").strip()
    if not d or not aid:
        raise HTTPException(status_code=400, detail="bad_request")
    if len(d) != 8 or not d.isdigit():
        raise HTTPException(status_code=400, detail="bad_day")
    if len(aid) > 64:
        raise HTTPException(status_code=400, detail="bad_id")
    key = f"metrics:worker_cb:alerts_ack:{d}:{aid}"
    cache.set_json(key, 1, ttl=172800)
    return {"ok": True, "day": d, "id": aid}


@router.post("/admin/metrics/worker-callback/alerts/{day}/ack_all")
def admin_ack_all_worker_callback_alerts(
    day: str,
    current_user: User = Depends(_require_admin),
):
    d = str(day or "").strip()
    if not d or len(d) != 8 or not d.isdigit():
        raise HTTPException(status_code=400, detail="bad_day")
    key = f"metrics:worker_cb:alerts:{d}"
    arr = cache.get_json(key)
    if not isinstance(arr, list):
        return {"ok": True, "day": d, "count": 0}
    n = 0
    for it in arr:
        if not isinstance(it, dict):
            continue
        aid = str(it.get("id") or "").strip()
        if not aid:
            continue
        ack_key = f"metrics:worker_cb:alerts_ack:{d}:{aid}"
        try:
            if cache.get_json(ack_key):
                continue
        except Exception:
            pass
        cache.set_json(ack_key, 1, ttl=172800)
        n += 1
    return {"ok": True, "day": d, "count": int(n)}


@router.post("/admin/metrics/worker-callback/alerts/ack_batch")
def admin_ack_worker_callback_alerts_batch(
    body: dict = Body(...),
    current_user: User = Depends(_require_admin),
):
    b = body if isinstance(body, dict) else {}
    items = b.get("items")
    if not isinstance(items, list):
        raise HTTPException(status_code=400, detail="bad_request")
    if len(items) > 500:
        raise HTTPException(status_code=400, detail="too_many")
    n = 0
    for it in items:
        if not isinstance(it, dict):
            continue
        d = str(it.get("day") or "").strip()
        aid = str(it.get("id") or "").strip()
        if not d or len(d) != 8 or not d.isdigit():
            continue
        if not aid or len(aid) > 64:
            continue
        key = f"metrics:worker_cb:alerts_ack:{d}:{aid}"
        try:
            if cache.get_json(key):
                continue
        except Exception:
            pass
        cache.set_json(key, 1, ttl=172800)
        n += 1
    return {"ok": True, "count": int(n)}


class MetricsThreshold(BaseModel):
    y: int
    r: int


class WorkerCallbackThresholds(BaseModel):
    dup: MetricsThreshold
    ij: MetricsThreshold
    ip: MetricsThreshold
    pr: MetricsThreshold


def _default_cb_thresholds() -> dict:
    return {"dup": {"y": 5, "r": 20}, "ij": {"y": 2, "r": 10}, "ip": {"y": 2, "r": 10}, "pr": {"y": 2, "r": 10}}


@router.get("/admin/metrics/worker-callback/thresholds")
def admin_worker_callback_thresholds(
    current_user: User = Depends(_require_admin),
):
    key = "metrics:worker_cb:thresholds"
    v = cache.get_json(key)
    if not isinstance(v, dict):
        v = _default_cb_thresholds()
    mode = "local"
    try:
        mode = "redis" if bool(cache.redis_enabled()) else "local"
    except Exception:
        mode = "local"
    return {"thresholds": v, "storage": mode}


@router.post("/admin/metrics/worker-callback/thresholds")
def admin_set_worker_callback_thresholds(
    body: dict = Body(...),
    current_user: User = Depends(_require_admin),
):
    b = body if isinstance(body, dict) else {}
    raw = b.get("thresholds") if isinstance(b.get("thresholds"), dict) else b
    defv = _default_cb_thresholds()
    def _clamp(x: Any, lo: int, hi: int) -> int:
        try:
            v = int(x)
        except Exception:
            v = lo
        if v < lo:
            v = lo
        if v > hi:
            v = hi
        return int(v)
    out = {}
    for k in ["dup", "ij", "ip", "pr"]:
        src = raw.get(k) if isinstance(raw.get(k), dict) else defv[k]
        y = _clamp(src.get("y"), 0, 10_000)
        r = _clamp(src.get("r"), 0, 10_000)
        if r < y:
            r = y
        out[k] = {"y": int(y), "r": int(r)}
    cache.set_json("metrics:worker_cb:thresholds", out, ttl=315360000)
    return {"ok": True, "thresholds": out}


@router.get("/admin/metrics/placeholder/providers")
def admin_placeholder_providers(
    current_user: User = Depends(_require_admin),
):
    from app.core.config import settings
    import time as _time
    import redis as _redis

    providers = ["pixabay", "pexels"]
    out = []
    mode = "local"
    try:
        r = _redis.Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_timeout=float(getattr(settings, "REDIS_SOCKET_TIMEOUT_SEC", 0.6) or 0.6),
            socket_connect_timeout=float(getattr(settings, "REDIS_CONNECT_TIMEOUT_SEC", 0.3) or 0.3),
            max_connections=int(getattr(settings, "REDIS_MAX_CONNECTIONS", 200) or 200),
        )
        mode = "redis"
        now = int(_time.time())
        for p in providers:
            open_until = 0
            fails = 0
            try:
                open_until = int(r.get(f"ph:cb:open_until:{p}") or 0)
            except Exception:
                open_until = 0
            try:
                fails = int(r.get(f"ph:cb:fail:{p}") or 0)
            except Exception:
                fails = 0
            out.append(
                {
                    "provider": p,
                    "circuit_open": bool(open_until and now < open_until),
                    "open_until": int(open_until) if open_until else None,
                    "fail_count": int(fails),
                }
            )
    except Exception:
        out = [{"provider": p, "circuit_open": False, "open_until": None, "fail_count": 0} for p in providers]
    return {"providers": out, "storage": mode}


@router.get("/admin/metrics/placeholder/jobs/{job_id}")
def admin_placeholder_job_trace(
    job_id: str,
    current_user: User = Depends(_require_admin),
    db: Session = Depends(get_read_db),
):
    jid = str(job_id or "").strip()
    if not jid:
        raise HTTPException(status_code=400, detail="bad_job_id")
    job = db.query(AIJob).filter(AIJob.id == str(jid)).first()
    if not job:
        raise HTTPException(status_code=404, detail="not_found")
    post = None
    try:
        if getattr(job, "post_id", None) is not None:
            post = db.query(Post).filter(Post.id == int(job.post_id)).first()
    except Exception:
        post = None
    asset = None
    try:
        if post and getattr(post, "active_media_asset_id", None) is not None:
            asset = db.query(MediaAsset).filter(MediaAsset.id == int(post.active_media_asset_id)).first()
    except Exception:
        asset = None
    rj = getattr(job, "result_json", None)
    ph = None
    if isinstance(rj, dict) and isinstance(rj.get("placeholder"), dict):
        ph = rj.get("placeholder")
    return {
        "job_id": str(jid),
        "user_id": int(getattr(job, "user_id", 0) or 0),
        "post_id": int(getattr(job, "post_id", 0) or 0) if getattr(job, "post_id", None) is not None else None,
        "status": str(getattr(job, "status", "") or ""),
        "stage": str(getattr(job, "stage", "") or ""),
        "placeholder": ph,
        "background_audit": getattr(asset, "background_audit", None) if asset is not None else None,
    }


@router.get("/admin/metrics/cover/providers")
def admin_cover_providers(
    current_user: User = Depends(_require_admin),
):
    from app.core.config import settings
    import time as _time
    import redis as _redis

    providers = ["wanx", "openai"]
    out = []
    mode = "local"
    try:
        r = _redis.Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_timeout=float(getattr(settings, "REDIS_SOCKET_TIMEOUT_SEC", 0.6) or 0.6),
            socket_connect_timeout=float(getattr(settings, "REDIS_CONNECT_TIMEOUT_SEC", 0.3) or 0.3),
            max_connections=int(getattr(settings, "REDIS_MAX_CONNECTIONS", 200) or 200),
        )
        mode = "redis"
        now = int(_time.time())
        for p in providers:
            open_until = 0
            fails = 0
            try:
                open_until = int(r.get(f"cv:cb:open_until:{p}") or 0)
            except Exception:
                open_until = 0
            try:
                fails = int(r.get(f"cv:cb:fail:{p}") or 0)
            except Exception:
                fails = 0
            out.append(
                {
                    "provider": p,
                    "circuit_open": bool(open_until and now < open_until),
                    "open_until": int(open_until) if open_until else None,
                    "fail_count": int(fails),
                }
            )
    except Exception:
        out = [{"provider": p, "circuit_open": False, "open_until": None, "fail_count": 0} for p in providers]
    return {"providers": out, "storage": mode}


@router.get("/admin/metrics/cover/jobs/{job_id}")
def admin_cover_job_trace(
    job_id: str,
    current_user: User = Depends(_require_admin),
    db: Session = Depends(get_read_db),
):
    jid = str(job_id or "").strip()
    if not jid:
        raise HTTPException(status_code=400, detail="bad_job_id")
    job = db.query(AIJob).filter(AIJob.id == str(jid)).first()
    if not job:
        raise HTTPException(status_code=404, detail="not_found")
    rj = getattr(job, "result_json", None)
    cv = None
    if isinstance(rj, dict) and isinstance(rj.get("cover"), dict):
        cv = rj.get("cover")
    return {
        "job_id": str(jid),
        "user_id": int(getattr(job, "user_id", 0) or 0),
        "post_id": int(getattr(job, "post_id", 0) or 0) if getattr(job, "post_id", None) is not None else None,
        "status": str(getattr(job, "status", "") or ""),
        "stage": str(getattr(job, "stage", "") or ""),
        "cover": cv,
    }


@router.post("/{post_id}/admin_remove")
def admin_remove_post(
    post_id: int,
    current_user: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    post = db.query(Post).filter(Post.id == int(post_id)).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    post.status = "removed"
    db.commit()
    try:
        cache.bump("feed:all")
        if post.category:
            cache.bump(f"feed:{post.category}")
        cache.bump(f"post:{int(post.id)}")
    except Exception:
        pass
    return {"ok": True, "post_id": int(post.id), "status": str(post.status)}


@router.post("/{post_id}/admin_restore")
def admin_restore_post(
    post_id: int,
    current_user: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    post = db.query(Post).filter(Post.id == int(post_id)).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if str(getattr(post, "status", "") or "") not in ("removed", "deleted"):
        raise HTTPException(status_code=400, detail="Not restorable")
    post.status = "done"
    db.commit()
    try:
        cache.bump("feed:all")
        if post.category:
            cache.bump(f"feed:{post.category}")
        cache.bump(f"post:{int(post.id)}")
    except Exception:
        pass
    return {"ok": True, "post_id": int(post.id), "status": str(post.status)}


@router.post("/{post_id}/admin_soft_delete")
def admin_soft_delete_post(
    post_id: int,
    current_user: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    from app.models.all_models import Comment, CommentReaction, Danmaku, MediaAsset

    post = db.query(Post).filter(Post.id == int(post_id)).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    pid = int(post.id)
    try:
        try:
            post.active_media_asset_id = None
        except Exception:
            pass
        try:
            db.flush()
        except Exception:
            pass
        cids = [int(x[0]) for x in db.query(Comment.id).filter(Comment.post_id == pid).all()]
        if cids:
            db.query(CommentReaction).filter(CommentReaction.comment_id.in_(cids)).delete(synchronize_session=False)
        db.query(Comment).filter(Comment.post_id == pid).delete(synchronize_session=False)
        db.query(Danmaku).filter(Danmaku.post_id == pid).delete(synchronize_session=False)
        db.query(Interaction).filter(Interaction.post_id == pid).delete(synchronize_session=False)
        db.query(MediaAsset).filter(MediaAsset.post_id == pid).delete(synchronize_session=False)
        try:
            db.query(AIJob).filter(AIJob.post_id == pid).delete(synchronize_session=False)
        except Exception:
            pass
        post.status = "deleted"
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Delete failed")

    try:
        cache.bump("feed:all")
        if getattr(post, "category", None):
            cache.bump(f"feed:{post.category}")
        cache.bump(f"post:{pid}")
    except Exception:
        pass
    return {"ok": True, "post_id": pid, "status": str(getattr(post, "status", "") or "")}


@router.delete("/{post_id}/admin_delete")
def admin_delete_post(
    post_id: int,
    current_user: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    from app.models.all_models import Comment, CommentReaction, Danmaku, MediaAsset

    post = db.query(Post).filter(Post.id == int(post_id)).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    try:
        try:
            post.active_media_asset_id = None
        except Exception:
            pass
        try:
            db.flush()
        except Exception:
            pass
        cids = [int(x[0]) for x in db.query(Comment.id).filter(Comment.post_id == int(post.id)).all()]
        if cids:
            db.query(CommentReaction).filter(CommentReaction.comment_id.in_(cids)).delete(synchronize_session=False)
        db.query(Comment).filter(Comment.post_id == int(post.id)).delete(synchronize_session=False)
        db.query(Danmaku).filter(Danmaku.post_id == int(post.id)).delete(synchronize_session=False)
        db.query(Interaction).filter(Interaction.post_id == int(post.id)).delete(synchronize_session=False)
        db.query(MediaAsset).filter(MediaAsset.post_id == int(post.id)).delete(synchronize_session=False)
        db.delete(post)
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Delete failed")

    try:
        cache.bump("feed:all")
        if getattr(post, "category", None):
            cache.bump(f"feed:{post.category}")
        cache.bump(f"post:{int(post_id)}")
    except Exception:
        pass
    return {"ok": True, "post_id": int(post_id)}


class AdminBulkRemoveIn(BaseModel):
    q: Optional[str] = None
    username: Optional[str] = None
    status: Optional[str] = "done"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    limit: int = 500


@router.post("/admin/bulk_remove")
def admin_bulk_remove_posts(
    body: AdminBulkRemoveIn,
    current_user: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    from sqlalchemy import or_

    lim = int(getattr(body, "limit", 500) or 500)
    if lim < 1:
        lim = 1
    if lim > 2000:
        lim = 2000

    q = (getattr(body, "q", None) or "").strip()
    username = (getattr(body, "username", None) or "").strip()
    st = (getattr(body, "status", None) or "").strip()
    sd = (getattr(body, "start_date", None) or "").strip()
    ed = (getattr(body, "end_date", None) or "").strip()

    query = db.query(Post.id)
    if st:
        query = query.filter(Post.status == st)
    if sd or ed:
        import datetime as _dt

        try:
            if sd:
                ds = _dt.date.fromisoformat(sd)
                query = query.filter(Post.created_at >= _dt.datetime(ds.year, ds.month, ds.day))
        except Exception:
            raise HTTPException(status_code=400, detail="bad_start_date")
        try:
            if ed:
                de = _dt.date.fromisoformat(ed)
                query = query.filter(Post.created_at < (_dt.datetime(de.year, de.month, de.day) + _dt.timedelta(days=1)))
        except Exception:
            raise HTTPException(status_code=400, detail="bad_end_date")
    if q:
        query = query.filter(or_(Post.title.contains(q), Post.summary.contains(q), Post.content_text.contains(q)))
    if username:
        query = query.join(User, User.id == Post.user_id).filter(or_(User.username.contains(username), User.nickname.contains(username), User.aiseek_id.contains(username)))
    ids = [int(x[0]) for x in query.order_by(Post.created_at.desc(), Post.id.desc()).limit(lim).all()]
    if not ids:
        return {"ok": True, "count": 0, "post_ids": []}

    try:
        db.query(Post).filter(Post.id.in_(ids)).update({Post.status: "removed"}, synchronize_session=False)
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Bulk remove failed")

    try:
        cache.bump("feed:all")
    except Exception:
        pass
    return {"ok": True, "count": len(ids), "post_ids": ids}


class AdminBulkDeleteIn(BaseModel):
    q: Optional[str] = None
    username: Optional[str] = None
    status: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    limit: int = 500


@router.post("/admin/bulk_delete")
def admin_bulk_delete_posts(
    body: AdminBulkDeleteIn,
    current_user: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    from sqlalchemy import or_
    from app.models.all_models import Comment, CommentReaction, Danmaku, MediaAsset

    lim = int(getattr(body, "limit", 500) or 500)
    if lim < 1:
        lim = 1
    if lim > 2000:
        lim = 2000

    q = (getattr(body, "q", None) or "").strip()
    username = (getattr(body, "username", None) or "").strip()
    st = (getattr(body, "status", None) or "").strip()
    sd = (getattr(body, "start_date", None) or "").strip()
    ed = (getattr(body, "end_date", None) or "").strip()
    if not st and not q and not username:
        raise HTTPException(status_code=400, detail="missing_filter")

    query = db.query(Post.id)
    if st:
        query = query.filter(Post.status == st)
    if sd or ed:
        import datetime as _dt

        try:
            if sd:
                ds = _dt.date.fromisoformat(sd)
                query = query.filter(Post.created_at >= _dt.datetime(ds.year, ds.month, ds.day))
        except Exception:
            raise HTTPException(status_code=400, detail="bad_start_date")
        try:
            if ed:
                de = _dt.date.fromisoformat(ed)
                query = query.filter(Post.created_at < (_dt.datetime(de.year, de.month, de.day) + _dt.timedelta(days=1)))
        except Exception:
            raise HTTPException(status_code=400, detail="bad_end_date")
    if q:
        query = query.filter(or_(Post.title.contains(q), Post.summary.contains(q), Post.content_text.contains(q)))
    if username:
        query = query.join(User, User.id == Post.user_id).filter(or_(User.username.contains(username), User.nickname.contains(username), User.aiseek_id.contains(username)))
    ids = [int(x[0]) for x in query.order_by(Post.created_at.desc(), Post.id.desc()).limit(lim).all()]
    if not ids:
        return {"ok": True, "count": 0, "post_ids": []}

    try:
        try:
            db.query(Post).filter(Post.id.in_(ids)).update({Post.active_media_asset_id: None}, synchronize_session=False)
        except Exception:
            pass
        cids = [int(x[0]) for x in db.query(Comment.id).filter(Comment.post_id.in_(ids)).all()]
        if cids:
            db.query(CommentReaction).filter(CommentReaction.comment_id.in_(cids)).delete(synchronize_session=False)
        db.query(Comment).filter(Comment.post_id.in_(ids)).delete(synchronize_session=False)
        db.query(Danmaku).filter(Danmaku.post_id.in_(ids)).delete(synchronize_session=False)
        db.query(Interaction).filter(Interaction.post_id.in_(ids)).delete(synchronize_session=False)
        db.query(MediaAsset).filter(MediaAsset.post_id.in_(ids)).delete(synchronize_session=False)
        try:
            db.query(AIJob).filter(AIJob.post_id.in_(ids)).delete(synchronize_session=False)
        except Exception:
            pass
        db.query(Post).filter(Post.id.in_(ids)).update({Post.status: "deleted"}, synchronize_session=False)
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Bulk delete failed")

    try:
        cache.bump("feed:all")
    except Exception:
        pass
    return {"ok": True, "count": len(ids), "post_ids": ids}


@router.get("/{post_id}/media", response_model=List[MediaAssetOut])
def list_media_assets(post_id: int, user_id: int, db: Session = Depends(get_db)):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if int(post.user_id) != int(user_id):
        raise HTTPException(status_code=403, detail="Not authorized")
    assets = (
        db.query(MediaAsset)
        .filter(MediaAsset.post_id == int(post_id))
        .order_by(MediaAsset.created_at.desc(), MediaAsset.id.desc())
        .all()
    )
    return assets


@router.post("/{post_id}/media/activate")
def activate_media_asset(post_id: int, body: MediaActivateIn, db: Session = Depends(get_db)):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if int(post.user_id) != int(body.user_id):
        raise HTTPException(status_code=403, detail="Not authorized")

    q = db.query(MediaAsset).filter(MediaAsset.post_id == int(post_id))
    if body.media_asset_id is not None:
        q = q.filter(MediaAsset.id == int(body.media_asset_id))
    elif body.version:
        q = q.filter(MediaAsset.version == str(body.version))
    else:
        raise HTTPException(status_code=400, detail="media_asset_id or version required")

    asset = q.first()
    if not asset:
        raise HTTPException(status_code=404, detail="Media asset not found")

    try:
        post.active_media_asset_id = int(asset.id)
    except Exception:
        pass
    if getattr(asset, "hls_url", None) or getattr(asset, "mp4_url", None):
        post.video_url = getattr(asset, "hls_url", None) or getattr(asset, "mp4_url", None)
    if getattr(asset, "mp4_url", None):
        post.processed_url = getattr(asset, "mp4_url", None)
    if getattr(asset, "cover_url", None):
        post.cover_url = getattr(asset, "cover_url", None)
    if getattr(asset, "duration", None) is not None:
        post.duration = int(getattr(asset, "duration", 0) or 0)
    if getattr(asset, "video_width", None) is not None:
        post.video_width = int(getattr(asset, "video_width", 0) or 0)
    if getattr(asset, "video_height", None) is not None:
        post.video_height = int(getattr(asset, "video_height", 0) or 0)

    db.commit()
    try:
        cache.bump("feed:all")
        if post.category:
            cache.bump(f"feed:{post.category}")
        cache.bump(f"post:{int(post.id)}")
    except Exception:
        pass
    return {"status": "ok"}


@router.post("/{post_id}/download/settings")
def set_download_settings(post_id: int, body: DownloadSettingsIn, authorization: Optional[str] = Header(None), db: Session = Depends(get_db)):
    uid = _maybe_current_user_id(authorization, db)
    if uid is None:
        raise HTTPException(status_code=401, detail="unauthorized")
    if int(uid) != int(body.user_id):
        raise HTTPException(status_code=403, detail="forbidden")
    post = db.query(Post).filter(Post.id == int(post_id)).first()
    if not post:
        raise HTTPException(status_code=404, detail="post_not_found")
    try:
        if int(getattr(post, "user_id", 0) or 0) != int(uid):
            u = db.query(User).filter(User.id == int(uid)).first()
            if not u or not bool(getattr(u, "is_superuser", False)):
                raise HTTPException(status_code=403, detail="forbidden")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=403, detail="forbidden")

    try:
        post.download_enabled = bool(body.download_enabled)
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="update_failed")
    try:
        cache.bump("feed:all")
        if post.category:
            cache.bump(f"feed:{post.category}")
        cache.bump(f"post:{int(post.id)}")
    except Exception:
        pass
    return {"ok": True, "download_enabled": bool(getattr(post, "download_enabled", False) or False)}


@router.post("/{post_id}/publish")
def publish_post(post_id: int, body: PublishIn, authorization: Optional[str] = Header(None), db: Session = Depends(get_db)):
    uid = _maybe_current_user_id(authorization, db)
    if uid is None:
        raise HTTPException(status_code=401, detail="unauthorized")
    if int(uid) != int(body.user_id):
        raise HTTPException(status_code=403, detail="forbidden")
    post = db.query(Post).filter(Post.id == int(post_id)).first()
    if not post:
        raise HTTPException(status_code=404, detail="post_not_found")
    if int(getattr(post, "user_id", 0) or 0) != int(uid):
        raise HTTPException(status_code=403, detail="forbidden")
    st = str(getattr(post, "status", "") or "").strip().lower()
    if st not in {"preview", "done"}:
        raise HTTPException(status_code=400, detail="post_not_ready")
    try:
        post.status = "done"
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="publish_failed")
    try:
        cache.bump("feed:all")
        if post.category:
            cache.bump(f"feed:{post.category}")
        cache.bump(f"post:{int(post.id)}")
    except Exception:
        pass
    try:
        from app.tasks.search_index import index_post
        from app.core.celery_app import apply_async_with_context

        apply_async_with_context(index_post, args=[int(post.id)], dedupe_key=f"index_post:{int(post.id)}", dedupe_ttl=10, max_queue_depth=10000, drop_when_overloaded=True)
    except Exception:
        pass
    return {"ok": True, "status": "done"}


@router.get("/{post_id}/download", response_model=DownloadOut)
def get_download(post_id: int, authorization: Optional[str] = Header(None), db: Session = Depends(get_db)):
    post = db.query(Post).options(joinedload(Post.active_media_asset)).filter(Post.id == int(post_id)).first()
    if not post:
        raise HTTPException(status_code=404, detail="post_not_found")

    uid = _maybe_current_user_id(authorization, db)
    is_owner = bool(uid is not None and int(uid) == int(getattr(post, "user_id", 0) or 0))
    if not bool(getattr(post, "download_enabled", False) or False) and not is_owner:
        raise HTTPException(status_code=403, detail="download_disabled")

    kind = str(getattr(post, "post_type", None) or "video")
    if kind == "image_text":
        imgs = getattr(post, "images", None)
        files = [str(x) for x in imgs] if isinstance(imgs, list) else []
        if not files:
            raise HTTPException(status_code=404, detail="missing_media")
        return DownloadOut(kind="image_text", files=files)

    st = str(getattr(post, "status", "") or "")
    if st and st != "done":
        raise HTTPException(status_code=409, detail="not_ready")

    active = getattr(post, "active_media_asset", None)
    mp4_url = None
    hls_url = None
    try:
        mp4_url = getattr(active, "mp4_url", None) if active is not None else None
        hls_url = getattr(active, "hls_url", None) if active is not None else None
    except Exception:
        mp4_url = None
        hls_url = None
    if not mp4_url:
        mp4_url = getattr(post, "processed_url", None)
    if not mp4_url:
        u = getattr(post, "video_url", None)
        if isinstance(u, str) and u and not u.lower().endswith(".m3u8"):
            mp4_url = u
        elif isinstance(u, str) and u and u.lower().endswith(".m3u8"):
            hls_url = hls_url or u
    if not mp4_url:
        if hls_url:
            title = str(getattr(post, "title", "") or "").strip() or f"post_{int(post.id)}"
            filename = "".join([c if c.isalnum() or c in {"-", "_", "."} else "_" for c in title])[:80].strip("_") or f"post_{int(post.id)}"
            if not filename.lower().endswith(".m3u8"):
                filename = filename + ".m3u8"
            return DownloadOut(kind="video", filename=filename, url=str(hls_url))
        raise HTTPException(status_code=404, detail="missing_media")

    title = str(getattr(post, "title", "") or "").strip() or f"post_{int(post.id)}"
    filename = "".join([c if c.isalnum() or c in {"-", "_", "."} else "_" for c in title])[:80].strip("_") or f"post_{int(post.id)}"
    if not filename.lower().endswith(".mp4"):
        filename = filename + ".mp4"

    out_url = str(mp4_url)
    try:
        from app.services.storage import storage_service

        key = storage_service.extract_object_key(out_url)
        if key:
            signed = storage_service.generate_presigned_download_url(key, filename=filename, expiration=600)
            if signed:
                out_url = signed
    except Exception:
        pass

    try:
        if not is_owner:
            post.downloads_count = int(getattr(post, "downloads_count", 0) or 0) + 1
            db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass

    return DownloadOut(kind="video", filename=filename, url=out_url)

@router.delete("/{post_id}")
def delete_post(post_id: int, authorization: Optional[str] = Header(None), db: Session = Depends(get_db)):
    from app.api.v1.endpoints.users import get_current_user
    from app.models.all_models import Comment, CommentReaction, Danmaku, MediaAsset

    u = get_current_user(authorization=authorization, db=db)
    post = db.query(Post).filter(Post.id == int(post_id)).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if int(getattr(post, "user_id", 0) or 0) != int(getattr(u, "id", 0) or 0):
        raise HTTPException(status_code=403, detail="Not authorized to delete this post")

    cat = getattr(post, "category", None)
    try:
        try:
            post.active_media_asset_id = None
        except Exception:
            pass
        try:
            db.flush()
        except Exception:
            pass
        cids = [int(x[0]) for x in db.query(Comment.id).filter(Comment.post_id == int(post.id)).all()]
        if cids:
            db.query(CommentReaction).filter(CommentReaction.comment_id.in_(cids)).delete(synchronize_session=False)
        db.query(Comment).filter(Comment.post_id == int(post.id)).delete(synchronize_session=False)
        db.query(Danmaku).filter(Danmaku.post_id == int(post.id)).delete(synchronize_session=False)
        db.query(Interaction).filter(Interaction.post_id == int(post.id)).delete(synchronize_session=False)
        db.query(MediaAsset).filter(MediaAsset.post_id == int(post.id)).delete(synchronize_session=False)
        db.delete(post)
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Delete failed")
    try:
        cache.bump("feed:all")
        if cat:
            cache.bump(f"feed:{cat}")
        cache.bump(f"post:{int(post_id)}")
    except Exception:
        pass
    return {"status": "ok", "message": "Post deleted"}
