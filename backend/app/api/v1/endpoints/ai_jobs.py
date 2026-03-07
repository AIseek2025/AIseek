from datetime import datetime, timezone, timedelta
from typing import Optional, List, Any

from fastapi import APIRouter, Depends, HTTPException, Header, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload
import uuid
import asyncio
import json
import hmac
import time
import re
import os
import urllib.request
import urllib.error
from starlette.responses import StreamingResponse

from app.api.deps import get_db, get_read_db
from app.core.cache import cache
from app.models.all_models import AIJob, Post, User, AIModerationCheck, AIJobMessage, AIJobDraftVersion, UserPersona
from app.api.v1.endpoints.users import get_current_user


router = APIRouter()
_XREAD_SEM = asyncio.Semaphore(64)

@router.get("/worker/users/{user_id}/persona-tags")
async def worker_get_user_persona_tags(
    user_id: int,
    request: Request,
    x_worker_ts: str = Header(None),
    x_worker_sig: str = Header(None),
    x_worker_secret: str = Header(None),
    db: Session = Depends(get_read_db),
):
    from app.core.worker_auth import verify_worker_request

    await verify_worker_request(
        request,
        x_worker_ts=x_worker_ts,
        x_worker_sig=x_worker_sig,
        x_worker_secret=x_worker_secret,
        require_signed=False,
    )
    uid = int(user_id or 0)
    if uid <= 0:
        raise HTTPException(status_code=400, detail="invalid_user_id")
    persona = db.query(UserPersona).filter(UserPersona.user_id == uid).first()
    tags = (getattr(persona, "tags", None) or []) if persona else []
    return {"user_id": uid, "tags": tags, "updated_at": getattr(persona, "updated_at", None) if persona else None}

def _auth_user_id(authorization: Optional[str], db: Session) -> Optional[int]:
    if not authorization:
        return None
    u = get_current_user(authorization=authorization, db=db)
    return int(getattr(u, "id"))


def _queued_pressure(db: Session) -> int:
    try:
        key = "cnt:ai_jobs:queued"
        val = cache.get_or_set_json(
            key,
            ttl=3,
            lock_ttl=1,
            builder=lambda: int(db.query(AIJob).filter(AIJob.status == "queued").count()),
        )
        return max(0, int(val or 0))
    except Exception:
        try:
            return max(0, int(db.query(AIJob).filter(AIJob.status == "queued").count()))
        except Exception:
            return 0

def _acquire_job_lock(job_id: str, kind: str, ttl: int) -> bool:
    jid = str(job_id or "").strip()
    if not jid:
        return True
    try:
        from app.core.config import settings
        import redis

        r = redis.Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_timeout=float(getattr(settings, "REDIS_SOCKET_TIMEOUT_SEC", 0.6) or 0.6),
            socket_connect_timeout=float(getattr(settings, "REDIS_CONNECT_TIMEOUT_SEC", 0.3) or 0.3),
            max_connections=int(getattr(settings, "REDIS_MAX_CONNECTIONS", 200) or 200),
        )
        key = f"lock:ai:{str(kind or 'job')}:{jid}"
        return bool(r.set(key, "1", nx=True, ex=int(ttl or 30)))
    except Exception:
        try:
            from app.core.config import settings
            if getattr(settings, "READINESS_STRICT", False):
                return False
        except Exception:
            pass
        try:
            key = f"lock:ai:{str(kind or 'job')}:{jid}"
            if cache.get_json(key) is not None:
                return False
            cache.set_json(key, 1, ttl=int(ttl or 30))
            return True
        except Exception:
            return True

def _release_job_lock(job_id: str, kind: str) -> None:
    jid = str(job_id or "").strip()
    if not jid:
        return
    key = f"lock:ai:{str(kind or 'job')}:{jid}"
    try:
        from app.core.config import settings
        import redis

        r = redis.Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_timeout=float(getattr(settings, "REDIS_SOCKET_TIMEOUT_SEC", 0.6) or 0.6),
            socket_connect_timeout=float(getattr(settings, "REDIS_CONNECT_TIMEOUT_SEC", 0.3) or 0.3),
            max_connections=int(getattr(settings, "REDIS_MAX_CONNECTIONS", 200) or 200),
        )
        try:
            r.delete(key)
        except Exception:
            pass
    except Exception:
        pass

def _rate_limit_or_skip(user_id: int, kind: str) -> None:
    try:
        from app.core.config import settings
        import redis
        import time
        from app.core.redis_scripts import TOKEN_BUCKET

        if int(user_id or 0) <= 0:
            return
        if kind == "create":
            rate_per_min = float(getattr(settings, "AI_CREATE_RATE_PER_MIN", 20) or 20)
            burst = float(getattr(settings, "AI_CREATE_BURST", 10) or 10)
            key = f"tb:ai_create:{int(user_id)}"
        elif kind == "suggest":
            rate_per_min = float(getattr(settings, "AI_SUGGEST_RATE_PER_MIN", 6) or 6)
            burst = float(getattr(settings, "AI_SUGGEST_BURST", 3) or 3)
            key = f"tb:ai_suggest:{int(user_id)}"
        elif kind == "revise":
            rate_per_min = float(getattr(settings, "AI_REVISE_RATE_PER_MIN", 3) or 3)
            burst = float(getattr(settings, "AI_REVISE_BURST", 2) or 2)
            key = f"tb:ai_revise:{int(user_id)}"
        else:
            return

        r = redis.Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_timeout=float(getattr(settings, "REDIS_SOCKET_TIMEOUT_SEC", 0.6) or 0.6),
            socket_connect_timeout=float(getattr(settings, "REDIS_CONNECT_TIMEOUT_SEC", 0.3) or 0.3),
            max_connections=int(getattr(settings, "REDIS_MAX_CONNECTIONS", 200) or 200),
        )
        rate = rate_per_min / 60.0
        now = float(time.time())
        ok = r.eval(TOKEN_BUCKET, 1, key, rate, burst, now, 1)
        if int(ok or 0) != 1:
            raise HTTPException(status_code=429, detail="rate_limited")
    except HTTPException:
        raise
    except Exception:
        try:
            from app.core.config import settings
            if getattr(settings, "READINESS_STRICT", False):
                raise HTTPException(status_code=503, detail="rate_limit_unavailable")
        except HTTPException:
            raise
        except Exception:
            pass

def _append_job_event(job_id: str, kind: str, payload: Any = None, ttl: int = 3600) -> None:
    try:
        from app.services.job_event_service import append_job_event

        append_job_event(job_id, kind, payload, ttl=ttl)
    except Exception:
        pass


@router.get("/jobs/{job_id}/events")
def get_job_events(job_id: str, user_id: Optional[int] = None, since: int = 0, authorization: Optional[str] = Header(None), db: Session = Depends(get_read_db)):
    job = db.query(AIJob).filter(AIJob.id == str(job_id)).first()
    if not job:
        raise HTTPException(status_code=404, detail="not_found")
    au = _auth_user_id(authorization, db)
    if au is not None:
        user_id = au
    if user_id is not None and int(user_id) != int(job.user_id):
        raise HTTPException(status_code=403, detail="forbidden")
    key = f"ai:job:events:{str(job_id)}"
    arr = cache.get_json(key)
    out: List[dict] = []
    if isinstance(arr, list):
        for e in arr:
            if not isinstance(e, dict):
                continue
            try:
                if int(e.get("id") or 0) <= int(since or 0):
                    continue
            except Exception:
                pass
            out.append(e)
    return {"events": out}


@router.get("/jobs/{job_id}/events/stream")
async def stream_job_events(
    job_id: str,
    user_id: Optional[int] = None,
    since: int = 0,
    last_event_id: Optional[str] = Header(None, alias="Last-Event-ID"),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_read_db),
):
    job = db.query(AIJob).filter(AIJob.id == str(job_id)).first()
    if not job:
        raise HTTPException(status_code=404, detail="not_found")
    au = _auth_user_id(authorization, db)
    if au is not None:
        user_id = au
    if user_id is not None and int(user_id) != int(job.user_id):
        raise HTTPException(status_code=403, detail="forbidden")

    jid = str(job_id)
    last = int(since or 0)
    if last <= 0 and last_event_id:
        try:
            last = int(str(last_event_id).strip() or "0")
        except Exception:
            last = int(since or 0)
    key = f"ai:job:events:{jid}"

    async def gen():
        nonlocal last
        yield "event: hello\ndata: {}\n\n"
        try:
            snap = {
                "id": int(last or 0),
                "ts": int(time.time()),
                "type": "progress",
                "data": {
                    "status": str(getattr(job, "status", "") or ""),
                    "progress": int(getattr(job, "progress", 0) or 0),
                    "stage": getattr(job, "stage", None),
                    "stage_message": getattr(job, "stage_message", None),
                },
            }
            data = json.dumps(snap, ensure_ascii=False, separators=(",", ":"))
            yield f"event: ev\ndata: {data}\n\n"
        except Exception:
            pass
        keep = 0
        while True:
            delay = 1.5
            try:
                from app.services.job_event_service import stream_enabled, xread_job_events

                sent = 0
                if stream_enabled():
                    try:
                        await asyncio.wait_for(_XREAD_SEM.acquire(), timeout=0.01)
                        try:
                            last, batch = await asyncio.to_thread(xread_job_events, jid, last, 900, 50)
                        finally:
                            try:
                                _XREAD_SEM.release()
                            except Exception:
                                pass
                    except asyncio.TimeoutError:
                        batch = []
                    for e in batch:
                        try:
                            eid = int(e.get("id") or 0)
                        except Exception:
                            continue
                        data = json.dumps(e, ensure_ascii=False, separators=(",", ":"))
                        yield f"id: {eid}\nevent: ev\ndata: {data}\n\n"
                        sent += 1
                        if sent >= 50:
                            break
                else:
                    arr = cache.get_json(key)
                    if isinstance(arr, list):
                        for e in arr:
                            if not isinstance(e, dict):
                                continue
                            try:
                                eid = int(e.get("id") or 0)
                            except Exception:
                                continue
                            if eid <= last:
                                continue
                            last = max(last, eid)
                            data = json.dumps(e, ensure_ascii=False, separators=(",", ":"))
                            yield f"id: {eid}\nevent: ev\ndata: {data}\n\n"
                            sent += 1
                            if sent >= 50:
                                break
                if sent == 0:
                    keep += 1
                    if keep >= 30:
                        keep = 0
                        yield ":\n\n"
                else:
                    keep = 0
                    delay = 0.25
            except Exception:
                yield ":\n\n"
                delay = 2.0
            await asyncio.sleep(delay)

    return StreamingResponse(gen(), media_type="text/event-stream")


class CancelIn(BaseModel):
    user_id: int


class DispatchIn(BaseModel):
    user_id: int


class SubmitIn(BaseModel):
    user_id: int
    post_type: str = "video"
    content: str
    title: Optional[str] = None
    tags: Optional[str] = None
    category: Optional[str] = None
    custom_instructions: Optional[str] = None
    voice_sample_url: Optional[str] = None
    avatar_video_url: Optional[str] = None
    voice_style: Optional[str] = None
    bgm_mood: Optional[str] = None
    bgm_id: Optional[str] = None
    subtitle_mode: Optional[str] = None
    requested_duration_sec: Optional[int] = None
    cover_orientation: Optional[str] = None


def _norm_tags(raw: Optional[str], limit: int = 6) -> List[str]:
    txt = str(raw or "").strip()
    if not txt:
        return []
    parts = re.split(r"[,\s，、#]+", txt)
    out: List[str] = []
    seen = set()
    for p in parts:
        t = str(p or "").strip()
        if not t:
            continue
        t = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff_-]", "", t)[:18]
        if not t:
            continue
        k = t.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(t)
        if len(out) >= int(limit):
            break
    return out


def _auto_title_by_content(content: str, category: Optional[str]) -> str:
    base = re.sub(r"\s+", " ", str(content or "")).strip()
    if not base:
        cat = str(category or "").strip()
        return f"{cat}视频作品" if cat else "AI创作作品"
    seg = re.split(r"[。！？!?；;\n]", base, maxsplit=1)[0].strip()
    seg = seg[:26].strip()
    return (seg + "…") if len(seg) >= 26 else seg


def _deepseek_title_by_content(content: str, category: Optional[str]) -> str:
    fallback = _auto_title_by_content(content, category)
    key = str(os.getenv("DEEPSEEK_API_KEY", "") or "").strip()
    if not key:
        return fallback
    text = re.sub(r"\s+", " ", str(content or "")).strip()
    if not text:
        return fallback
    prompt = (
        "你是短视频标题编辑。基于用户文本，生成1个中文标题。"
        "要求：12-20字、口语化、信息密度高、不含引号和井号，不要返回解释。"
    )
    payload = {
        "model": str(os.getenv("DEEPSEEK_MODEL", "deepseek-chat") or "deepseek-chat"),
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": text[:2200]},
        ],
        "temperature": 0.3,
        "max_tokens": 48,
    }
    base = str(os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1") or "https://api.deepseek.com/v1").rstrip("/")
    url = f"{base}/chat/completions"
    try:
        req = urllib.request.Request(
            url=url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=6.0) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
        data = json.loads(raw or "{}")
        msg = (((data or {}).get("choices") or [{}])[0] or {}).get("message") or {}
        out = str(msg.get("content") or "").strip()
        out = re.sub(r"[\r\n\t]+", " ", out).strip(" \"'`#")
        out = re.sub(r"\s+", " ", out).strip()
        out = out[:26].strip()
        return out or fallback
    except Exception:
        return fallback


def _auto_tags_by_content(content: str, category: Optional[str], limit: int = 4) -> List[str]:
    out: List[str] = []
    cat = str(category or "").strip()
    if cat:
        out.append(cat[:18])
    text = str(content or "")
    for m in re.findall(r"[A-Za-z0-9\u4e00-\u9fff]{2,8}", text):
        t = str(m or "").strip()
        if not t:
            continue
        if t in out:
            continue
        out.append(t)
        if len(out) >= int(limit):
            break
    if not out:
        out = ["AI创作", "视频作品"]
    return out[: int(limit)]


class ReviseIn(BaseModel):
    user_id: int
    feedback: str


class DraftIn(BaseModel):
    user_id: int
    draft_json: Any
    source: Optional[str] = None


class RerunIn(BaseModel):
    user_id: int
    draft_json: Optional[Any] = None
    source: Optional[str] = None


class RegenCoverIn(BaseModel):
    user_id: int


class AppealIn(BaseModel):
    user_id: int
    statement: str
    proof_url: Optional[str] = None


class ReviewDecisionIn(BaseModel):
    action: str
    note: Optional[str] = None


class ChatIn(BaseModel):
    user_id: int
    content: str


class ReviseFromChatIn(BaseModel):
    user_id: int


@router.post("/jobs/{job_id}/chat/ai_suggest")
def chat_ai_suggest(job_id: str, body: ReviseFromChatIn, authorization: Optional[str] = Header(None), db: Session = Depends(get_db)):
    job = db.query(AIJob).filter(AIJob.id == str(job_id)).first()
    if not job:
        raise HTTPException(status_code=404, detail="not_found")
    au = _auth_user_id(authorization, db)
    uid = int(au) if au is not None else int(body.user_id)
    if au is not None and int(body.user_id) != int(au):
        raise HTTPException(status_code=403, detail="forbidden")
    if uid != int(job.user_id):
        raise HTTPException(status_code=403, detail="forbidden")
    if str(getattr(job, "stage", "") or "") == "chat_ai" and str(getattr(job, "status", "") or "") == "processing":
        raise HTTPException(status_code=409, detail="busy")
    _rate_limit_or_skip(uid, "suggest")
    if not _acquire_job_lock(str(job_id), "suggest", ttl=90):
        raise HTTPException(status_code=409, detail="busy")
    post = None
    if getattr(job, "post_id", None) is not None:
        post = db.query(Post).filter(Post.id == int(job.post_id)).first()
    if not post:
        try:
            _release_job_lock(str(job_id), "suggest")
        except Exception:
            pass
        raise HTTPException(status_code=404, detail="post_not_found")

    msgs = (
        db.query(AIJobMessage)
        .filter(AIJobMessage.job_id == str(job_id), AIJobMessage.role == "user")
        .order_by(AIJobMessage.id.desc())
        .limit(20)
        .all()
    )
    feedback = [str(m.content or "").strip() for m in reversed(msgs) if str(m.content or "").strip()]
    if not feedback:
        raise HTTPException(status_code=400, detail="empty_chat")

    inp = job.input_json if isinstance(getattr(job, "input_json", None), dict) else {}
    content = str(inp.get("content") or post.content_text or "")
    post_type = str(inp.get("post_type") or post.post_type or "video")
    custom = inp.get("custom_instructions") or post.custom_instructions
    draft = getattr(job, "draft_json", None)
    if not isinstance(draft, dict):
        draft = {}

    try:
        job.stage = "chat_ai"
        job.stage_message = "AI正在生成建议"
        job.status = "processing"
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass

    try:
        from app.services.queue_service import send_worker_task

        send_worker_task(
            "refine_script",
            args=[str(job_id), content, str(uid)],
            kwargs={
                "post_id": int(post.id),
                "post_type": post_type,
                "custom_instructions": custom,
                "draft_json": draft,
                "chat_messages": feedback,
            },
        )
    except Exception as e:
        try:
            job.status = "queued"
            job.stage = "chat_ai_dispatch_failed"
            job.stage_message = "任务派发失败，可重试"
            job.error = str(e)
            db.commit()
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
        try:
            _release_job_lock(str(job_id), "suggest")
        except Exception:
            pass
        return {"ok": False, "stage": "chat_ai_dispatch_failed"}

    try:
        _append_job_event(str(job_id), "chat_ai", {"status": "queued"})
    except Exception:
        pass
    return {"ok": True}


@router.get("/jobs/{job_id}")
def get_job(job_id: str, user_id: Optional[int] = None, db: Session = Depends(get_read_db)):
    job = db.query(AIJob).filter(AIJob.id == str(job_id)).first()
    if not job:
        raise HTTPException(status_code=404, detail="not_found")
    if user_id is not None and int(user_id) != int(job.user_id):
        raise HTTPException(status_code=403, detail="forbidden")
    return {
        "id": str(job.id),
        "user_id": int(job.user_id),
        "post_id": int(job.post_id) if getattr(job, "post_id", None) is not None else None,
        "kind": getattr(job, "kind", None),
        "status": getattr(job, "status", "") or "",
        "progress": int(getattr(job, "progress", 0) or 0),
        "stage": getattr(job, "stage", None),
        "stage_message": getattr(job, "stage_message", None),
        "dispatch_attempts": int(getattr(job, "dispatch_attempts", 0) or 0),
        "next_dispatch_at": getattr(job, "next_dispatch_at", None),
        "draft_json": getattr(job, "draft_json", None),
        "error": getattr(job, "error", None),
        "created_at": getattr(job, "created_at", None),
        "updated_at": getattr(job, "updated_at", None),
        "cancelled_at": getattr(job, "cancelled_at", None),
    }


@router.get("/jobs/by_post/{post_id}")
def get_job_by_post(post_id: int, user_id: Optional[int] = None, db: Session = Depends(get_read_db)):
    job = db.query(AIJob).filter(AIJob.post_id == int(post_id)).order_by(AIJob.created_at.desc()).first()
    if not job:
        return {"job_id": None}
    if user_id is not None and int(user_id) != int(job.user_id):
        raise HTTPException(status_code=403, detail="forbidden")
    return {"job_id": str(job.id)}


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str, body: CancelIn, db: Session = Depends(get_db)):
    job = db.query(AIJob).filter(AIJob.id == str(job_id)).first()
    if not job:
        raise HTTPException(status_code=404, detail="not_found")
    if int(body.user_id) != int(job.user_id):
        raise HTTPException(status_code=403, detail="forbidden")

    st = str(getattr(job, "status", "") or "")
    if st in {"done", "failed", "cancelled"}:
        return {"status": st}

    try:
        job.status = "cancelled"
        job.stage = "cancelled"
        job.stage_message = "用户已取消"
        job.cancelled_at = datetime.now(timezone.utc)
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass

    try:
        cache.set_json(f"ai:cancel:{str(job_id)}", {"ts": int(datetime.now().timestamp()), "by": int(body.user_id)}, ttl=3600)
    except Exception:
        pass
    try:
        _append_job_event(str(job_id), "cancel", {"by": int(body.user_id)})
    except Exception:
        pass
    return {"status": "cancelled"}


@router.post("/jobs/{job_id}/dispatch")
def redispatch_job(job_id: str, body: DispatchIn, authorization: Optional[str] = Header(None), db: Session = Depends(get_db)):
    job = db.query(AIJob).filter(AIJob.id == str(job_id)).first()
    if not job:
        raise HTTPException(status_code=404, detail="not_found")
    au = _auth_user_id(authorization, db)
    uid = int(au) if au is not None else int(body.user_id)
    if au is not None and int(body.user_id) != int(au):
        raise HTTPException(status_code=403, detail="forbidden")
    if uid != int(job.user_id):
        raise HTTPException(status_code=403, detail="forbidden")
    if str(getattr(job, "status", "") or "") in {"done", "cancelled"}:
        return {"ok": True, "status": str(getattr(job, "status", "") or "")}

    post_id = getattr(job, "post_id", None)
    if post_id is None:
        raise HTTPException(status_code=400, detail="missing_post")
    post = db.query(Post).filter(Post.id == int(post_id)).first()
    if not post:
        raise HTTPException(status_code=404, detail="post_not_found")

    try:
        job.status = "queued"
        job.stage = "dispatch_pending"
        job.stage_message = "等待派发"
        job.error = None
        job.worker_task_id = None
        job.next_dispatch_at = datetime.now()
        post.status = "queued"
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        raise HTTPException(status_code=400, detail="update_failed")

    try:
        _append_job_event(str(job.id), "dispatch_pending", {"post_id": int(post.id), "kind": getattr(job, "kind", None)})
    except Exception:
        pass
    return {"ok": True, "job_id": str(job.id), "post_id": int(post.id), "stage": "dispatch_pending"}


@router.get("/jobs/{job_id}/cancelled")
def is_cancelled(job_id: str, x_worker_secret: str = Header(None)):
    from app.core.config import settings

    if getattr(settings, "READINESS_STRICT", False) and str(getattr(settings, "WORKER_SECRET", "")) == "m3pro_worker_2026":
        raise HTTPException(status_code=500, detail="misconfigured_worker_secret")
    if not x_worker_secret or not hmac.compare_digest(str(x_worker_secret), str(getattr(settings, "WORKER_SECRET", ""))):
        raise HTTPException(status_code=401, detail="Unauthorized")
    v = cache.get_json(f"ai:cancel:{str(job_id)}")
    return {"cancelled": bool(v)}


@router.get("/jobs/{job_id}/draft")
def get_draft(job_id: str, user_id: Optional[int] = None, authorization: Optional[str] = Header(None), db: Session = Depends(get_read_db)):
    job = db.query(AIJob).filter(AIJob.id == str(job_id)).first()
    if not job:
        raise HTTPException(status_code=404, detail="not_found")
    au = _auth_user_id(authorization, db)
    if au is not None:
        user_id = au
    if user_id is not None and int(user_id) != int(job.user_id):
        raise HTTPException(status_code=403, detail="forbidden")
    return {"draft_json": getattr(job, "draft_json", None)}


@router.get("/jobs/{job_id}/review")
def get_review(job_id: str, user_id: Optional[int] = None, authorization: Optional[str] = Header(None), db: Session = Depends(get_read_db)):
    job = db.query(AIJob).filter(AIJob.id == str(job_id)).first()
    if not job:
        raise HTTPException(status_code=404, detail="not_found")
    au = _auth_user_id(authorization, db)
    if au is not None:
        user_id = au
    if user_id is not None and int(user_id) != int(job.user_id):
        raise HTTPException(status_code=403, detail="forbidden")
    chk = db.query(AIModerationCheck).filter(AIModerationCheck.job_id == str(job_id)).order_by(AIModerationCheck.id.desc()).first()
    if not chk:
        return {"status": str(getattr(job, "status", "") or ""), "reasons": [], "appeal": None, "message": getattr(job, "stage_message", None)}
    return {
        "status": str(getattr(chk, "status", "") or ""),
        "reasons": getattr(chk, "reasons", None) or [],
        "appeal": getattr(chk, "appeal", None),
        "message": getattr(job, "stage_message", None),
    }


@router.get("/jobs/{job_id}/chat")
def get_chat(job_id: str, user_id: Optional[int] = None, limit: int = 80, authorization: Optional[str] = Header(None), db: Session = Depends(get_read_db)):
    job = db.query(AIJob).filter(AIJob.id == str(job_id)).first()
    if not job:
        raise HTTPException(status_code=404, detail="not_found")
    au = _auth_user_id(authorization, db)
    if au is not None:
        user_id = au
    if user_id is not None and int(user_id) != int(job.user_id):
        raise HTTPException(status_code=403, detail="forbidden")
    lim = int(limit or 80)
    if lim < 1:
        lim = 1
    if lim > 200:
        lim = 200
    rows = (
        db.query(AIJobMessage)
        .filter(AIJobMessage.job_id == str(job_id))
        .order_by(AIJobMessage.id.desc())
        .limit(lim)
        .all()
    )
    out: List[dict] = []
    for m in reversed(rows):
        out.append(
            {
                "id": int(m.id),
                "role": str(getattr(m, "role", "") or ""),
                "content": str(getattr(m, "content", "") or ""),
                "created_at": getattr(m, "created_at", None),
            }
        )
    return {"messages": out}


@router.get("/posts/{post_id}/chat")
def get_post_chat(post_id: int, user_id: Optional[int] = None, limit: int = 200, authorization: Optional[str] = Header(None), db: Session = Depends(get_read_db)):
    au = _auth_user_id(authorization, db)
    if au is not None:
        user_id = au
    if user_id is None:
        raise HTTPException(status_code=401, detail="unauthorized")
    post = db.query(Post).filter(Post.id == int(post_id)).first()
    if not post or int(getattr(post, "user_id", 0) or 0) != int(user_id):
        raise HTTPException(status_code=404, detail="post_not_found")
    lim = int(limit or 200)
    if lim < 1:
        lim = 1
    if lim > 2000:
        lim = 2000
    rows = (
        db.query(AIJobMessage, AIJob)
        .join(AIJob, AIJob.id == AIJobMessage.job_id)
        .filter(AIJob.post_id == int(post_id), AIJob.user_id == int(user_id))
        .order_by(AIJobMessage.created_at.desc(), AIJobMessage.id.desc())
        .limit(lim)
        .all()
    )
    out: List[dict] = []
    for m, j in reversed(rows):
        out.append(
            {
                "id": int(m.id),
                "job_id": str(getattr(j, "id", "") or ""),
                "role": str(getattr(m, "role", "") or ""),
                "content": str(getattr(m, "content", "") or ""),
                "created_at": getattr(m, "created_at", None),
            }
        )
    return {"messages": out}


@router.post("/jobs/{job_id}/chat")
def post_chat(job_id: str, body: ChatIn, authorization: Optional[str] = Header(None), db: Session = Depends(get_db)):
    job = db.query(AIJob).filter(AIJob.id == str(job_id)).first()
    if not job:
        raise HTTPException(status_code=404, detail="not_found")
    au = _auth_user_id(authorization, db)
    uid = int(au) if au is not None else int(body.user_id)
    if au is not None and int(body.user_id) != int(au):
        raise HTTPException(status_code=403, detail="forbidden")
    if uid != int(job.user_id):
        raise HTTPException(status_code=403, detail="forbidden")
    content = str(body.content or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="empty")
    if len(content) > 2000:
        content = content[:2000]
    msg = AIJobMessage(job_id=str(job_id), user_id=int(uid), role="user", content=content)
    db.add(msg)
    db.commit()

    parsed = None
    reply = None
    try:
        from app.services.ai_chat_command_service import build_ack_message, parse_chat_commands

        parsed = parse_chat_commands(content)
        reply = build_ack_message(parsed)
    except Exception:
        parsed = None
        reply = None

    if parsed and isinstance(parsed, dict):
        updates = parsed.get("updates") if isinstance(parsed.get("updates"), dict) else {}
        post_updates = parsed.get("post_updates") if isinstance(parsed.get("post_updates"), dict) else {}
        append_instr = parsed.get("append_instructions") if isinstance(parsed.get("append_instructions"), list) else []
        actions = parsed.get("actions") if isinstance(parsed.get("actions"), list) else []

        if updates:
            base_input = job.input_json if isinstance(getattr(job, "input_json", None), dict) else {}
            merged = dict(base_input)
            for k, v in list(updates.items())[:24]:
                merged[str(k)] = v
            job.input_json = merged

        post = None
        try:
            if getattr(job, "post_id", None) is not None:
                post = db.query(Post).filter(Post.id == int(job.post_id)).first()
        except Exception:
            post = None

        if post and post_updates:
            if "title" in post_updates:
                try:
                    post.title = str(post_updates.get("title") or "")[:120] or None
                except Exception:
                    pass
            if "category" in post_updates:
                try:
                    post.category = str(post_updates.get("category") or "")[:64] or None
                except Exception:
                    pass

        if append_instr:
            add = "\n".join([str(x or "").strip() for x in append_instr if str(x or "").strip()])[:1200]
            if add:
                try:
                    base_input = job.input_json if isinstance(getattr(job, "input_json", None), dict) else {}
                    cur = str((base_input or {}).get("custom_instructions") or "")
                    nxt = (cur.strip() + ("\n\n" if cur.strip() else "") + "用户追加指令：\n" + add).strip()
                    base_input2 = dict(base_input)
                    base_input2["custom_instructions"] = nxt[:12000]
                    job.input_json = base_input2
                except Exception:
                    pass
                if post:
                    try:
                        cur2 = str(getattr(post, "custom_instructions", "") or "")
                        post.custom_instructions = (cur2.strip() + ("\n\n" if cur2.strip() else "") + "用户追加指令：\n" + add).strip()[:12000] or None
                    except Exception:
                        pass

        if "rerun" in actions:
            try:
                if not post and getattr(job, "post_id", None) is not None:
                    post = db.query(Post).filter(Post.id == int(job.post_id)).first()
            except Exception:
                post = None
            draft0 = getattr(job, "draft_json", None)
            base_input = job.input_json if isinstance(getattr(job, "input_json", None), dict) else {}
            if post and draft0 is not None:
                try:
                    content0 = str((base_input or {}).get("content") or getattr(post, "content_text", "") or "")
                    post_type0 = str((base_input or {}).get("post_type") or getattr(post, "post_type", None) or "video")
                    new_job_id = str(uuid.uuid4())
                    job2 = AIJob(
                        id=new_job_id,
                        user_id=int(uid),
                        post_id=int(post.id),
                        kind="rerun_draft",
                        status="queued",
                        progress=0,
                        stage="queued",
                        input_json={
                            "base_job_id": str(job_id),
                            "post_type": post_type0,
                            "content": content0,
                            "custom_instructions": (base_input or {}).get("custom_instructions"),
                            "voice_style": (base_input or {}).get("voice_style"),
                            "bgm_mood": (base_input or {}).get("bgm_mood"),
                            "bgm_id": (base_input or {}).get("bgm_id"),
                            "subtitle_mode": (base_input or {}).get("subtitle_mode"),
                            "requested_duration_sec": (base_input or {}).get("requested_duration_sec"),
                            "cover_orientation": (base_input or {}).get("cover_orientation"),
                            "title": (base_input or {}).get("title") or getattr(post, "title", None),
                            "category": (base_input or {}).get("category") or getattr(post, "category", None),
                        },
                        draft_json=draft0,
                    )
                    db.add(job2)
                    post.ai_job_id = new_job_id
                    post.status = "queued"
                    job2.stage = "dispatch_pending"
                    job2.stage_message = "等待派发"
                    job2.next_dispatch_at = datetime.now()
                    db.commit()
                    try:
                        _append_job_event(str(new_job_id), "dispatch_pending", {"post_id": int(post.id), "kind": "generate_video"})
                        _append_job_event(str(new_job_id), "rerun", {"base_job_id": str(job_id), "post_id": int(post.id)})
                    except Exception:
                        pass
                    reply = (str(reply or "").strip() + ("\n" if str(reply or "").strip() else "") + f"已重跑：新任务 {new_job_id}").strip()
                except Exception:
                    try:
                        db.rollback()
                    except Exception:
                        pass
                    reply = (str(reply or "").strip() + ("\n" if str(reply or "").strip() else "") + "重跑失败：草稿缺失或系统繁忙").strip()
            else:
                reply = (str(reply or "").strip() + ("\n" if str(reply or "").strip() else "") + "当前任务还没有可用草稿，无法重跑。").strip()

        if parsed.get("ask_submit_status"):
            try:
                from app.services.reputation_service import check_submit_allowed, effective_reputation_score

                u = db.query(User).filter(User.id == int(uid)).first()
                if u:
                    ok, deny = check_submit_allowed(db, u)
                    score = effective_reputation_score(u)
                    if ok:
                        tail = f"发布检查：当前信誉分{int(score)}，可以正常发布。"
                    else:
                        tail = f"发布检查：当前信誉分{int(score)}，暂时无法发布（{deny}）。"
                    reply = (str(reply or "").strip() + ("\n" if str(reply or "").strip() else "") + tail).strip()
            except Exception:
                pass

        try:
            db.commit()
            try:
                db.add(
                    AIJobDraftVersion(
                        job_id=str(job.id),
                        user_id=int(uid),
                        source="chat_apply",
                        draft_json=getattr(job, "draft_json", None),
                    )
                )
                db.commit()
            except Exception:
                try:
                    db.rollback()
                except Exception:
                    pass
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass

        if reply and str(reply).strip():
            try:
                db.add(AIJobMessage(job_id=str(job_id), user_id=int(uid), role="assistant", content=str(reply).strip()[:2000]))
                db.commit()
            except Exception:
                try:
                    db.rollback()
                except Exception:
                    pass
    try:
        _append_job_event(str(job_id), "chat", {"len": len(content)})
    except Exception:
        pass
    return {"ok": True}



@router.post("/jobs/{job_id}/draft")
def update_draft(job_id: str, body: DraftIn, authorization: Optional[str] = Header(None), db: Session = Depends(get_db)):
    job = db.query(AIJob).filter(AIJob.id == str(job_id)).first()
    if not job:
        raise HTTPException(status_code=404, detail="not_found")
    au = _auth_user_id(authorization, db)
    uid = int(au) if au is not None else int(body.user_id)
    if au is not None and int(body.user_id) != int(au):
        raise HTTPException(status_code=403, detail="forbidden")
    if uid != int(job.user_id):
        raise HTTPException(status_code=403, detail="forbidden")
    try:
        job.draft_json = body.draft_json
        job.stage_message = "脚本已更新"
        try:
            db.add(
                AIJobDraftVersion(
                    job_id=str(job.id),
                    user_id=int(uid),
                    source=str(body.source or "user_edit")[:64],
                    draft_json=body.draft_json,
                )
            )
        except Exception:
            pass
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        raise HTTPException(status_code=400, detail="update_failed")
    try:
        _append_job_event(str(job.id), "draft_update", {})
    except Exception:
        pass
    return {"ok": True}


@router.get("/jobs/{job_id}/draft/history")
def get_draft_history(job_id: str, user_id: Optional[int] = None, limit: int = 50, authorization: Optional[str] = Header(None), db: Session = Depends(get_read_db)):
    job = db.query(AIJob).filter(AIJob.id == str(job_id)).first()
    if not job:
        raise HTTPException(status_code=404, detail="not_found")
    au = _auth_user_id(authorization, db)
    if au is not None:
        user_id = au
    if user_id is not None and int(user_id) != int(job.user_id):
        raise HTTPException(status_code=403, detail="forbidden")
    lim = int(limit or 50)
    if lim < 1:
        lim = 1
    if lim > 200:
        lim = 200
    rows = (
        db.query(AIJobDraftVersion)
        .filter(AIJobDraftVersion.job_id == str(job_id))
        .order_by(AIJobDraftVersion.id.desc())
        .limit(lim)
        .all()
    )
    out: List[dict] = []
    for r in rows:
        out.append(
            {
                "id": int(r.id),
                "source": getattr(r, "source", None),
                "created_at": getattr(r, "created_at", None),
            }
        )
    return {"items": out}


@router.get("/jobs/{job_id}/draft/history/{version_id}")
def get_draft_history_item(job_id: str, version_id: int, user_id: Optional[int] = None, authorization: Optional[str] = Header(None), db: Session = Depends(get_read_db)):
    job = db.query(AIJob).filter(AIJob.id == str(job_id)).first()
    if not job:
        raise HTTPException(status_code=404, detail="not_found")
    au = _auth_user_id(authorization, db)
    if au is not None:
        user_id = au
    if user_id is not None and int(user_id) != int(job.user_id):
        raise HTTPException(status_code=403, detail="forbidden")
    v = (
        db.query(AIJobDraftVersion)
        .filter(AIJobDraftVersion.job_id == str(job_id), AIJobDraftVersion.id == int(version_id))
        .first()
    )
    if not v:
        raise HTTPException(status_code=404, detail="not_found")
    return {"id": int(v.id), "source": getattr(v, "source", None), "draft_json": getattr(v, "draft_json", None)}


@router.post("/jobs/{job_id}/rerun")
def rerun_from_draft(job_id: str, body: RerunIn, authorization: Optional[str] = Header(None), db: Session = Depends(get_db)):
    base = db.query(AIJob).filter(AIJob.id == str(job_id)).first()
    if not base:
        raise HTTPException(status_code=404, detail="not_found")
    au = _auth_user_id(authorization, db)
    uid = int(au) if au is not None else int(body.user_id)
    if au is not None and int(body.user_id) != int(au):
        raise HTTPException(status_code=403, detail="forbidden")
    if uid != int(base.user_id):
        raise HTTPException(status_code=403, detail="forbidden")
    post_id = getattr(base, "post_id", None)
    if post_id is None:
        raise HTTPException(status_code=400, detail="missing_post")
    post = db.query(Post).filter(Post.id == int(post_id)).first()
    if not post:
        raise HTTPException(status_code=404, detail="post_not_found")

    draft = body.draft_json if body.draft_json is not None else getattr(base, "draft_json", None)
    if draft is None:
        raise HTTPException(status_code=400, detail="missing_draft")

    base_input = base.input_json if isinstance(getattr(base, "input_json", None), dict) else {}
    content = str((base_input or {}).get("content") or post.content_text or "")
    post_type = str((base_input or {}).get("post_type") or post.post_type or "video")
    custom = (base_input or {}).get("custom_instructions")
    voice_style = (base_input or {}).get("voice_style")
    bgm_mood = (base_input or {}).get("bgm_mood")
    bgm_id = (base_input or {}).get("bgm_id")
    subtitle_mode = (base_input or {}).get("subtitle_mode")

    new_job_id = str(uuid.uuid4())
    job = AIJob(
        id=new_job_id,
        user_id=int(uid),
        post_id=int(post.id),
        kind="rerun_draft",
        status="queued",
        progress=0,
        stage="queued",
        input_json={
            "base_job_id": str(job_id),
            "post_type": post_type,
            "content": content,
            "custom_instructions": custom,
            "voice_style": voice_style,
            "bgm_mood": bgm_mood,
            "bgm_id": bgm_id,
            "subtitle_mode": subtitle_mode,
        },
        draft_json=draft,
    )
    db.add(job)
    post.ai_job_id = new_job_id
    post.status = "queued"
    db.commit()

    try:
        job.stage = "dispatch_pending"
        job.stage_message = "等待派发"
        job.error = None
        job.worker_task_id = None
        job.next_dispatch_at = datetime.now()
        db.commit()
        try:
            _append_job_event(str(new_job_id), "dispatch_pending", {"post_id": int(post.id), "kind": "generate_video"})
        except Exception:
            pass
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
    try:
        _append_job_event(str(new_job_id), "rerun", {"base_job_id": str(job_id), "post_id": int(post.id)})
    except Exception:
        pass
    return {"job_id": str(new_job_id), "post_id": int(post.id)}


@router.post("/submit")
def submit_ai(body: SubmitIn, authorization: Optional[str] = Header(None), db: Session = Depends(get_db)):
    au = _auth_user_id(authorization, db)
    if au is not None and int(au) != int(body.user_id):
        raise HTTPException(status_code=403, detail="forbidden")
    user = db.query(User).filter(User.id == int(body.user_id)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if getattr(user, "is_active", True) is False:
        raise HTTPException(status_code=403, detail="Account disabled")
    _rate_limit_or_skip(int(body.user_id), "create")

    from app.services.ai_moderation import preflight_text
    from app.services.reputation_service import apply_penalty, check_submit_allowed, is_violation_issues, summarize_issues_cn

    post_type = str(body.post_type or "video")
    if post_type not in {"video", "image_text"}:
        raise HTTPException(status_code=400, detail="invalid_post_type")

    qp = _queued_pressure(db)
    pf = preflight_text(body.content, user_id=int(body.user_id), requested_duration_sec=body.requested_duration_sec, queue_pressure=qp)

    ok_submit, deny = check_submit_allowed(db, user)
    if not ok_submit:
        raise HTTPException(status_code=403, detail={"action": "blocked", "limit": deny})
    if not pf.get("ok"):
        act = str(pf.get("action") or "")
        if act == "cooldown":
            raise HTTPException(status_code=429, detail={"action": "cooldown", "issues": pf.get("issues")})
        issues = pf.get("issues") or []
        try:
            day = datetime.utcnow().strftime("%Y%m%d")
            k = f"metrics:moderation:{day}"
            for it in issues:
                if not isinstance(it, dict):
                    continue
                if str(it.get("kind") or "") == "risk" and str(it.get("type") or "") == "violence":
                    m = str(it.get("mode") or "").strip() or "reject"
                    cache.hincrby(k, f"violence:reject:{m}", 1, ttl=172800)
        except Exception:
            pass
        reason = summarize_issues_cn(issues)
        content_text = str(pf.get("sanitized_text") or str(body.content or "") or "")[:30000]
        raw_title = str(body.title or "").strip()
        tags = _norm_tags(body.tags)
        if not raw_title:
            raw_title = _deepseek_title_by_content(content_text, body.category)
        if not tags:
            tags = _auto_tags_by_content(content_text, body.category)
        if tags:
            tag_line = " ".join([f"#{t}" for t in tags])
            if tag_line and tag_line not in content_text:
                content_text = (content_text.strip() + ("\n" if content_text.strip() else "") + tag_line).strip()[:30000]
        post = Post(
            user_id=int(body.user_id),
            content_text=content_text,
            post_type=post_type,
            custom_instructions=body.custom_instructions,
            status="returned",
            category=body.category,
            title=raw_title or None,
            error_message=reason,
            download_enabled=True,
        )
        db.add(post)
        db.commit()
        db.refresh(post)
        try:
            if is_violation_issues(issues):
                apply_penalty(db, user, int(post.id), issues)
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
        return {"post_id": int(post.id), "status": "returned"}

    content_text = str(pf.get("sanitized_text") or "")
    raw_title = str(body.title or "").strip()
    tags = _norm_tags(body.tags)
    if not raw_title:
        raw_title = _deepseek_title_by_content(content_text, body.category)
    if not tags:
        tags = _auto_tags_by_content(content_text, body.category)
    if tags:
        tag_line = " ".join([f"#{t}" for t in tags])
        if tag_line and tag_line not in content_text:
            content_text = (content_text.strip() + ("\n" if content_text.strip() else "") + tag_line).strip()[:30000]
    custom_req = body.custom_instructions
    try:
        issues = pf.get("issues") or []
        vio_modes = []
        for it in issues:
            if not isinstance(it, dict):
                continue
            if str(it.get("kind") or "") == "risk" and str(it.get("type") or "") == "violence":
                m = str(it.get("mode") or "").strip() or "sensitive_context"
                vio_modes.append(m)
        if vio_modes:
            day = datetime.utcnow().strftime("%Y%m%d")
            k = f"metrics:moderation:{day}"
            for m in vio_modes[:5]:
                cache.hincrby(k, f"violence:{m}", 1, ttl=172800)
            safety_line = (
                "安全要求：内容可能涉及暴力/危险事件。请以新闻报道/科普防范角度表达，避免血腥细节与煽动性措辞；"
                "不要提供任何可执行的实施方法、步骤、材料清单或购买渠道；如涉及自伤，请给出求助与心理支持提示。"
            )
            custom_req = (str(custom_req or "").strip() + ("\n\n" if str(custom_req or "").strip() else "") + safety_line).strip()
    except Exception:
        pass
    try:
        if post_type == "video":
            tsec = int(pf.get("target_sec") or 0)
            sc = int(pf.get("scene_count") or 0)
            reqd = pf.get("requested_duration_sec")
            if tsec > 0 or sc > 0:
                sys_line = f"系统参数：目标视频时长约{tsec or 60}秒；建议分镜{sc or 8}段；用户时长上限{int(reqd) if reqd is not None else '无'}秒。"
                custom_req = (str(custom_req or "").strip() + ("\n\n" if str(custom_req or "").strip() else "") + sys_line).strip()
    except Exception:
        custom_req = body.custom_instructions
    post = Post(
        user_id=int(body.user_id),
        content_text=content_text,
        post_type=post_type,
        custom_instructions=custom_req,
        status="queued",
        category=body.category,
        title=raw_title or None,
        download_enabled=True,
    )
    db.add(post)
    db.commit()
    db.refresh(post)

    job_id = str(uuid.uuid4())
    post.ai_job_id = job_id
    job = AIJob(
        id=job_id,
        user_id=int(body.user_id),
        post_id=int(post.id),
        kind="generate_video",
        status="queued",
        progress=0,
        stage="queued",
        input_json={
            "post_type": post_type,
            "content": content_text,
            "category": body.category,
            "custom_instructions": custom_req,
            "voice_sample_url": body.voice_sample_url,
            "avatar_video_url": body.avatar_video_url,
            "voice_style": body.voice_style,
            "bgm_mood": body.bgm_mood,
            "bgm_id": body.bgm_id,
            "subtitle_mode": body.subtitle_mode,
            "requested_duration_sec": pf.get("requested_duration_sec"),
            "cover_orientation": body.cover_orientation,
            "title": raw_title or None,
            "tags": tags,
            "preflight": {
                "issues": pf.get("issues") or [],
                "value_tier": pf.get("value_tier"),
                "target_sec": pf.get("target_sec"),
                "scene_count": pf.get("scene_count"),
                "queue_pressure": pf.get("queue_pressure"),
            },
        },
    )
    db.add(job)
    db.commit()
    try:
        _append_job_event(str(job_id), "submit", {"post_id": int(post.id), "post_type": post_type})
    except Exception:
        pass

    try:
        job.stage = "dispatch_pending"
        job.stage_message = "等待派发"
        job.error = None
        job.worker_task_id = None
        job.next_dispatch_at = datetime.now()
        db.commit()
        try:
            _append_job_event(str(job_id), "dispatch_pending", {"post_id": int(post.id), "kind": "generate_video"})
        except Exception:
            pass
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass

    return {"post_id": int(post.id), "job_id": str(job_id), "stage": str(getattr(job, "stage", "") or "")}


@router.post("/posts/{post_id}/resubmit")
def resubmit_returned_post(post_id: int, body: SubmitIn, authorization: Optional[str] = Header(None), db: Session = Depends(get_db)):
    au = _auth_user_id(authorization, db)
    if au is not None and int(au) != int(body.user_id):
        raise HTTPException(status_code=403, detail="forbidden")
    user = db.query(User).filter(User.id == int(body.user_id)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    post = db.query(Post).filter(Post.id == int(post_id)).first()
    if not post or int(getattr(post, "user_id", 0) or 0) != int(body.user_id):
        raise HTTPException(status_code=404, detail="post_not_found")

    from app.services.ai_moderation import preflight_text
    from app.services.reputation_service import apply_penalty, check_submit_allowed, is_violation_issues

    post_type = str(getattr(post, "post_type", None) or body.post_type or "video")
    if post_type not in {"video", "image_text"}:
        post_type = "video"
    content = str(getattr(post, "content_text", "") or "")

    qp = _queued_pressure(db)
    pf = preflight_text(content, user_id=int(body.user_id), requested_duration_sec=body.requested_duration_sec, queue_pressure=qp)
    if not pf.get("ok"):
        try:
            issues = pf.get("issues") or []
            if is_violation_issues(issues):
                apply_penalty(db, user, int(post.id), issues)
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
        raise HTTPException(status_code=400, detail={"action": "preflight_reject", "issues": pf.get("issues")})

    ok_submit, deny = check_submit_allowed(db, user)
    if not ok_submit:
        raise HTTPException(status_code=403, detail={"action": "blocked", "limit": deny})

    content_text = str(pf.get("sanitized_text") or content)[:30000]
    custom_req = str(getattr(post, "custom_instructions", None) or body.custom_instructions or "").strip() or None
    try:
        issues = pf.get("issues") or []
        vio_modes = []
        for it in issues:
            if not isinstance(it, dict):
                continue
            if str(it.get("kind") or "") == "risk" and str(it.get("type") or "") == "violence":
                m = str(it.get("mode") or "").strip() or "sensitive_context"
                vio_modes.append(m)
        if vio_modes:
            safety_line = (
                "安全要求：内容可能涉及暴力/危险事件。请以新闻报道/科普防范角度表达，避免血腥细节与煽动性措辞；"
                "不要提供任何可执行的实施方法、步骤、材料清单或购买渠道；如涉及自伤，请给出求助与心理支持提示。"
            )
            custom_req = (str(custom_req or "").strip() + ("\n\n" if str(custom_req or "").strip() else "") + safety_line).strip()
    except Exception:
        pass

    new_job_id = str(uuid.uuid4())
    post.ai_job_id = new_job_id
    post.status = "queued"
    job = AIJob(
        id=new_job_id,
        user_id=int(body.user_id),
        post_id=int(post.id),
        kind="generate_video",
        status="queued",
        progress=0,
        stage="queued",
        input_json={
            "post_type": post_type,
            "content": content_text,
            "category": getattr(post, "category", None),
            "custom_instructions": custom_req,
            "voice_style": body.voice_style,
            "bgm_mood": body.bgm_mood,
            "bgm_id": body.bgm_id,
            "subtitle_mode": body.subtitle_mode,
            "requested_duration_sec": pf.get("requested_duration_sec"),
            "title": getattr(post, "title", None),
            "preflight": {
                "issues": pf.get("issues") or [],
                "value_tier": pf.get("value_tier"),
                "target_sec": pf.get("target_sec"),
                "scene_count": pf.get("scene_count"),
                "queue_pressure": pf.get("queue_pressure"),
            },
        },
    )
    db.add(job)
    db.commit()
    try:
        job.stage = "dispatch_pending"
        job.stage_message = "等待派发"
        job.error = None
        job.worker_task_id = None
        job.next_dispatch_at = datetime.now()
        db.commit()
        _append_job_event(str(new_job_id), "dispatch_pending", {"post_id": int(post.id), "kind": "generate_video"})
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
    try:
        _append_job_event(str(new_job_id), "resubmit", {"post_id": int(post.id)})
    except Exception:
        pass
    return {"job_id": str(new_job_id), "post_id": int(post.id), "stage": str(getattr(job, "stage", "") or "")}


@router.post("/posts/{post_id}/regen_cover")
def regen_cover(post_id: int, body: RegenCoverIn, authorization: Optional[str] = Header(None), db: Session = Depends(get_db)):
    au = _auth_user_id(authorization, db)
    if au is None:
        raise HTTPException(status_code=401, detail="unauthorized")
    if au is not None and int(au) != int(body.user_id):
        raise HTTPException(status_code=403, detail="forbidden")
    post = db.query(Post).options(joinedload(Post.active_media_asset)).filter(Post.id == int(post_id)).first()
    if not post or int(getattr(post, "user_id", 0) or 0) != int(body.user_id):
        raise HTTPException(status_code=404, detail="post_not_found")
    job_id = str(getattr(post, "ai_job_id", "") or "").strip()
    if not job_id:
        raise HTTPException(status_code=400, detail="missing_job_id")
    mp4_url = None
    hls_url = None
    try:
        active = getattr(post, "active_media_asset", None)
        if active is not None:
            mp4_url = getattr(active, "mp4_url", None)
            hls_url = getattr(active, "hls_url", None)
    except Exception:
        pass
    if not mp4_url:
        mp4_url = getattr(post, "processed_url", None)
    if not hls_url:
        u = getattr(post, "video_url", None)
        if isinstance(u, str) and u.lower().endswith(".m3u8"):
            hls_url = u
    if not mp4_url and not hls_url:
        raise HTTPException(status_code=400, detail="missing_video_url")

    from app.services.queue_service import send_worker_task

    cover_orientation = None
    try:
        job = db.query(AIJob).filter(AIJob.id == str(job_id)).first()
        inp = job.input_json if job and isinstance(getattr(job, "input_json", None), dict) else {}
        cover_orientation = inp.get("cover_orientation")
    except Exception:
        cover_orientation = None

    tid = send_worker_task(
        "generate_cover_only",
        kwargs={
            "job_id": str(job_id),
            "user_id": str(int(body.user_id)),
            "post_id": str(int(post.id)),
            "title": str(getattr(post, "title", None) or ""),
            "summary": str(getattr(post, "summary", None) or ""),
            "mp4_url": str(mp4_url or "") or None,
            "hls_url": str(hls_url or "") or None,
            "cover_orientation": cover_orientation,
        },
    )
    try:
        job = db.query(AIJob).filter(AIJob.id == str(job_id)).first()
        if job:
            job.status = "processing"
            job.stage = "cover_dispatched"
            job.stage_message = "封面任务已派发"
            job.error = None
            try:
                job.progress = max(1, int(getattr(job, "progress", 0) or 0))
            except Exception:
                job.progress = 1
            job.worker_task_id = str(tid or "") or getattr(job, "worker_task_id", None)
            db.commit()
            try:
                _append_job_event(str(job_id), "cover_dispatched", {"post_id": int(post.id), "task_id": str(tid or "")})
            except Exception:
                pass
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass

    return {"ok": True, "task_id": str(tid or ""), "job_id": str(job_id), "post_id": int(post.id)}


@router.post("/jobs/{job_id}/revise")
def revise_job(job_id: str, body: ReviseIn, db: Session = Depends(get_db)):
    base = db.query(AIJob).filter(AIJob.id == str(job_id)).first()
    if not base:
        raise HTTPException(status_code=404, detail="not_found")
    if int(body.user_id) != int(base.user_id):
        raise HTTPException(status_code=403, detail="forbidden")

    post_id = getattr(base, "post_id", None)
    if post_id is None:
        raise HTTPException(status_code=400, detail="missing_post")
    post = db.query(Post).filter(Post.id == int(post_id)).first()
    if not post:
        raise HTTPException(status_code=404, detail="post_not_found")

    base_input = base.input_json if isinstance(getattr(base, "input_json", None), dict) else {}
    content = str((base_input or {}).get("content") or post.content_text or "")
    base_req = str((base_input or {}).get("custom_instructions") or post.custom_instructions or "")
    fb = str(body.feedback or "").strip()
    if not fb:
        raise HTTPException(status_code=400, detail="empty_feedback")
    custom = (base_req + "\n\n用户二次反馈修改要求：\n" + fb).strip()

    new_job_id = str(uuid.uuid4())
    job = AIJob(
        id=new_job_id,
        user_id=int(body.user_id),
        post_id=int(post.id),
        kind="revise",
        status="queued",
        progress=0,
        stage="queued",
        input_json={
            "base_job_id": str(job_id),
            "post_type": str((base_input or {}).get("post_type") or post.post_type or "video"),
            "content": content,
            "custom_instructions": custom,
            "feedback": fb,
        },
    )
    db.add(job)
    post.ai_job_id = new_job_id
    post.status = "queued"
    db.commit()
    try:
        _append_job_event(str(new_job_id), "revise", {"base_job_id": str(job_id), "post_id": int(post.id)})
    except Exception:
        pass

    try:
        job.stage = "dispatch_pending"
        job.stage_message = "等待派发"
        job.error = None
        job.worker_task_id = None
        job.next_dispatch_at = datetime.now()
        db.commit()
        try:
            _append_job_event(str(new_job_id), "dispatch_pending", {"post_id": int(post.id), "kind": "generate_video"})
        except Exception:
            pass
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass

    return {"job_id": str(new_job_id), "post_id": int(post.id)}


@router.post("/jobs/{job_id}/revise_from_chat")
def revise_from_chat(job_id: str, body: ReviseFromChatIn, authorization: Optional[str] = Header(None), db: Session = Depends(get_db)):
    base = db.query(AIJob).filter(AIJob.id == str(job_id)).first()
    if not base:
        raise HTTPException(status_code=404, detail="not_found")
    au = _auth_user_id(authorization, db)
    uid = int(au) if au is not None else int(body.user_id)
    if au is not None and int(body.user_id) != int(au):
        raise HTTPException(status_code=403, detail="forbidden")
    if uid != int(base.user_id):
        raise HTTPException(status_code=403, detail="forbidden")
    _rate_limit_or_skip(uid, "revise")
    if not _acquire_job_lock(str(job_id), "revise", ttl=30):
        raise HTTPException(status_code=409, detail="busy")
    post_id = getattr(base, "post_id", None)
    if post_id is None:
        raise HTTPException(status_code=400, detail="missing_post")
    post = db.query(Post).filter(Post.id == int(post_id)).first()
    if not post:
        raise HTTPException(status_code=404, detail="post_not_found")

    msgs = (
        db.query(AIJobMessage)
        .filter(AIJobMessage.job_id == str(job_id), AIJobMessage.role == "user")
        .order_by(AIJobMessage.id.desc())
        .limit(12)
        .all()
    )
    arr = [str(m.content or "").strip() for m in reversed(msgs) if str(m.content or "").strip()]
    if not arr:
        raise HTTPException(status_code=400, detail="empty_chat")
    fb = "\n".join([f"- {x}" for x in arr])[:6000]

    base_input = base.input_json if isinstance(getattr(base, "input_json", None), dict) else {}
    content = str((base_input or {}).get("content") or post.content_text or "")
    base_req = str((base_input or {}).get("custom_instructions") or post.custom_instructions or "")
    custom = (base_req + "\n\n用户二次反馈修改要求（对话汇总）：\n" + fb).strip()

    new_job_id = str(uuid.uuid4())
    job = AIJob(
        id=new_job_id,
        user_id=int(uid),
        post_id=int(post.id),
        kind="revise",
        status="queued",
        progress=0,
        stage="queued",
        input_json={
            "base_job_id": str(job_id),
            "post_type": str((base_input or {}).get("post_type") or post.post_type or "video"),
            "content": content,
            "custom_instructions": custom,
            "feedback": fb,
            "voice_style": (base_input or {}).get("voice_style"),
            "bgm_mood": (base_input or {}).get("bgm_mood"),
            "bgm_id": (base_input or {}).get("bgm_id"),
            "subtitle_mode": (base_input or {}).get("subtitle_mode"),
            "requested_duration_sec": (base_input or {}).get("requested_duration_sec"),
            "cover_orientation": (base_input or {}).get("cover_orientation"),
            "title": (base_input or {}).get("title") or getattr(post, "title", None),
            "category": (base_input or {}).get("category") or getattr(post, "category", None),
        },
        draft_json=getattr(base, "draft_json", None),
    )
    db.add(job)
    post.ai_job_id = new_job_id
    post.status = "queued"
    db.commit()

    try:
        db.add(AIJobMessage(job_id=str(new_job_id), user_id=int(uid), role="assistant", content="已提交修改，将生成新版本"))
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass

    try:
        job.stage = "dispatch_pending"
        job.stage_message = "等待派发"
        job.error = None
        job.worker_task_id = None
        job.next_dispatch_at = datetime.now()
        db.commit()
        try:
            _append_job_event(str(new_job_id), "dispatch_pending", {"post_id": int(post.id), "kind": "generate_video"})
        except Exception:
            pass
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
    try:
        _append_job_event(str(new_job_id), "revise", {"base_job_id": str(job_id), "post_id": int(post.id)})
    except Exception:
        pass
    return {"job_id": str(new_job_id), "post_id": int(post.id)}


@router.get("/admin/jobs")
def admin_list_jobs(
    status: Optional[str] = None,
    user_id: Optional[int] = None,
    limit: int = 100,
    authorization: str = Header(None),
    db: Session = Depends(get_db),
):
    from app.api.v1.endpoints.users import get_current_user

    u = get_current_user(authorization=authorization, db=db)
    if not getattr(u, "is_superuser", False):
        raise HTTPException(status_code=403, detail="Forbidden")

    lim = int(limit or 100)
    if lim < 1:
        lim = 1
    if lim > 500:
        lim = 500

    q = db.query(AIJob).order_by(AIJob.created_at.desc())
    if status:
        q = q.filter(AIJob.status == str(status))
    if user_id is not None:
        q = q.filter(AIJob.user_id == int(user_id))
    rows = q.limit(lim).all()
    out: List[dict] = []
    for j in rows:
        out.append(
            {
                "id": str(j.id),
                "user_id": int(j.user_id),
                "post_id": int(j.post_id) if getattr(j, "post_id", None) is not None else None,
                "kind": getattr(j, "kind", None),
                "status": getattr(j, "status", "") or "",
                "progress": int(getattr(j, "progress", 0) or 0),
                "stage": getattr(j, "stage", None),
                "stage_message": getattr(j, "stage_message", None),
                "error": getattr(j, "error", None),
                "created_at": getattr(j, "created_at", None),
            }
        )
    return out


@router.post("/admin/jobs/{job_id}/cancel")
def admin_cancel_job(
    job_id: str,
    authorization: str = Header(None),
    db: Session = Depends(get_db),
):
    from app.api.v1.endpoints.users import get_current_user

    u = get_current_user(authorization=authorization, db=db)
    if not getattr(u, "is_superuser", False):
        raise HTTPException(status_code=403, detail="Forbidden")

    job = db.query(AIJob).filter(AIJob.id == str(job_id)).first()
    if not job:
        raise HTTPException(status_code=404, detail="not_found")

    st = str(getattr(job, "status", "") or "")
    if st in {"done", "failed", "cancelled"}:
        return {"ok": True, "status": st}

    try:
        job.status = "cancelled"
        job.stage = "cancelled"
        job.stage_message = "管理员取消"
        job.cancelled_at = datetime.now(timezone.utc)
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="cancel_failed")

    try:
        cache.set_json(f"ai:cancel:{str(job_id)}", {"ts": int(datetime.now().timestamp()), "by": int(getattr(u, "id", 0) or 0)}, ttl=3600)
    except Exception:
        pass
    try:
        _append_job_event(str(job_id), "cancel", {"by": int(getattr(u, "id", 0) or 0), "admin": True})
    except Exception:
        pass
    try:
        pid = getattr(job, "post_id", None)
        if pid is not None:
            post = db.query(Post).filter(Post.id == int(pid)).first()
            if post:
                post.status = "failed"
                post.error_message = "已取消"
                db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
    return {"ok": True, "status": "cancelled"}


@router.post("/jobs/{job_id}/appeal")
def appeal_job(job_id: str, body: AppealIn, db: Session = Depends(get_db)):
    job = db.query(AIJob).filter(AIJob.id == str(job_id)).first()
    if not job:
        raise HTTPException(status_code=404, detail="not_found")
    if int(body.user_id) != int(job.user_id):
        raise HTTPException(status_code=403, detail="forbidden")
    st = str(getattr(job, "status", "") or "")
    if st != "needs_review":
        raise HTTPException(status_code=400, detail="not_in_review")

    statement = str(body.statement or "").strip()
    if not statement:
        raise HTTPException(status_code=400, detail="empty_statement")

    chk = db.query(AIModerationCheck).filter(AIModerationCheck.job_id == str(job_id)).order_by(AIModerationCheck.id.desc()).first()
    if not chk:
        chk = AIModerationCheck(job_id=str(job_id), user_id=int(job.user_id), post_id=getattr(job, "post_id", None), status="pending", reasons=[])
        db.add(chk)
        db.commit()
        db.refresh(chk)
    try:
        chk.appeal = {"statement": statement, "proof_url": body.proof_url, "ts": int(datetime.now().timestamp())}
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        raise HTTPException(status_code=400, detail="appeal_failed")
    try:
        _append_job_event(str(job_id), "appeal", {"check_id": int(chk.id)})
    except Exception:
        pass
    return {"ok": True, "check_id": int(chk.id)}


def _require_admin(authorization: str = Header(None), db: Session = Depends(get_db)) -> User:
    from app.api.v1.endpoints.users import get_current_user

    u = get_current_user(authorization=authorization, db=db)
    if not getattr(u, "is_superuser", False):
        raise HTTPException(status_code=403, detail="Forbidden")
    return u


@router.get("/admin/metrics/moderation")
def admin_moderation_metrics(
    days: int = 7,
    current_user: User = Depends(_require_admin),
):
    d = int(days or 7)
    if d < 1:
        d = 1
    if d > 30:
        d = 30
    out = []
    totals = {}
    for i in range(d):
        day = (datetime.utcnow() - timedelta(days=i)).strftime("%Y%m%d")
        key = f"metrics:moderation:{day}"
        h = cache.hgetall(key) or {}
        metrics = {}
        if isinstance(h, dict):
            for k, v in h.items():
                try:
                    metrics[str(k)] = int(v)
                    totals[str(k)] = int(totals.get(str(k)) or 0) + int(v)
                except Exception:
                    continue
        out.append({"day": day, "metrics": metrics})
    out.sort(key=lambda x: x.get("day") or "")
    return {"totals": totals, "series": out, "storage": "redis" if cache.redis_enabled() else "local"}


@router.get("/admin/review/list")
def admin_list_review(
    status: Optional[str] = "pending",
    limit: int = 200,
    current_user: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    lim = int(limit or 200)
    if lim < 1:
        lim = 1
    if lim > 500:
        lim = 500
    q = db.query(AIModerationCheck).order_by(AIModerationCheck.created_at.desc(), AIModerationCheck.id.desc())
    if status and str(status).strip():
        q = q.filter(AIModerationCheck.status == str(status).strip())
    rows = q.limit(lim).all()
    out: List[dict] = []
    for c in rows:
        out.append(
            {
                "id": int(c.id),
                "job_id": str(c.job_id),
                "user_id": int(c.user_id),
                "post_id": int(c.post_id) if getattr(c, "post_id", None) is not None else None,
                "status": str(getattr(c, "status", "") or ""),
                "reasons": getattr(c, "reasons", None),
                "appeal": getattr(c, "appeal", None),
                "decision_note": getattr(c, "decision_note", None),
                "decided_by": getattr(c, "decided_by", None),
                "decided_at": getattr(c, "decided_at", None),
                "created_at": getattr(c, "created_at", None),
            }
        )
    return out


def _dispatch_generate(job: AIJob, post: Post) -> None:
    inp = job.input_json if isinstance(getattr(job, "input_json", None), dict) else {}
    from app.services.queue_service import send_worker_task

    pf = inp.get("preflight") if isinstance(inp.get("preflight"), dict) else {}
    ci = str(inp.get("custom_instructions") or "").strip()
    guard = "画面不要直接贴大段原文/全文；只用字幕呈现口播内容，字幕用短句分行显示。"
    if guard not in ci:
        ci = (ci + ("\n" if ci else "") + guard).strip()
    sm = inp.get("subtitle_mode")
    if sm is None or str(sm).strip() == "":
        sm = "zh"
    send_worker_task(
        "generate_video",
        args=[str(job.id), str(inp.get("content") or post.content_text or ""), str(job.user_id)],
        kwargs={
            "post_type": str(inp.get("post_type") or post.post_type or "video"),
            "custom_instructions": ci or None,
            "voice_style": inp.get("voice_style"),
            "bgm_mood": inp.get("bgm_mood"),
            "bgm_id": inp.get("bgm_id"),
            "subtitle_mode": sm,
            "requested_duration_sec": inp.get("requested_duration_sec"),
            "cover_orientation": inp.get("cover_orientation"),
            "target_sec": pf.get("target_sec"),
            "post_id": int(post.id),
            "draft_json": getattr(job, "draft_json", None),
        },
    )


@router.post("/admin/review/{check_id}/decision")
def admin_review_decide(
    check_id: int,
    body: ReviewDecisionIn,
    current_user: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    chk = db.query(AIModerationCheck).filter(AIModerationCheck.id == int(check_id)).first()
    if not chk:
        raise HTTPException(status_code=404, detail="not_found")
    if str(getattr(chk, "status", "")) not in {"pending"}:
        return {"status": getattr(chk, "status", "")}
    job = db.query(AIJob).filter(AIJob.id == str(chk.job_id)).first()
    if not job:
        raise HTTPException(status_code=404, detail="job_not_found")
    post = None
    if getattr(chk, "post_id", None) is not None:
        post = db.query(Post).filter(Post.id == int(chk.post_id)).first()
    if not post and getattr(job, "post_id", None) is not None:
        post = db.query(Post).filter(Post.id == int(job.post_id)).first()
    if not post:
        raise HTTPException(status_code=404, detail="post_not_found")

    act = str(body.action or "").strip().lower()
    note = str(body.note or "").strip()
    if act not in {"approve", "reject"}:
        raise HTTPException(status_code=400, detail="invalid_action")
    try:
        chk.status = "approved" if act == "approve" else "rejected"
        chk.decision_note = note or None
        chk.decided_by = int(getattr(current_user, "id", 0) or 0)
        chk.decided_at = datetime.now(timezone.utc)
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        raise HTTPException(status_code=400, detail="decision_failed")

    if act == "approve":
        try:
            job.status = "queued"
            job.stage = "dispatch_pending"
            job.stage_message = "审核通过，等待派发"
            job.error = None
            job.worker_task_id = None
            job.next_dispatch_at = datetime.now()
            post.status = "queued"
            post.error_message = None
            db.commit()
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
        try:
            _append_job_event(str(job.id), "review_approved", {"by": int(getattr(current_user, "id", 0) or 0)})
            _append_job_event(str(job.id), "dispatch_pending", {"post_id": int(post.id), "kind": "generate_video"})
        except Exception:
            pass
    else:
        try:
            job.status = "failed"
            job.stage = "rejected"
            job.stage_message = note or "审核拒绝"
            job.error = note or "审核拒绝"
            post.status = "failed"
            post.error_message = "审核拒绝"
            db.commit()
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
        try:
            _append_job_event(str(job.id), "review_rejected", {"by": int(getattr(current_user, "id", 0) or 0)})
        except Exception:
            pass
    return {"status": chk.status}
