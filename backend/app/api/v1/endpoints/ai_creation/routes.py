from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import uuid
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.all_models import AIJob, Post
from app.core.config import get_settings

router = APIRouter()

class AICreateRequest(BaseModel):
    long_text: str
    prompt: Optional[str] = None
    category: Optional[str] = None
    user_id: int

@router.post("/create")
async def create_ai_job(req: AICreateRequest):
    try:
        s = get_settings()
        try:
            import redis
            from app.core.redis_scripts import TOKEN_BUCKET

            r = redis.Redis.from_url(
                s.REDIS_URL,
                decode_responses=True,
                socket_timeout=float(getattr(s, "REDIS_SOCKET_TIMEOUT_SEC", 0.6) or 0.6),
                socket_connect_timeout=float(getattr(s, "REDIS_CONNECT_TIMEOUT_SEC", 0.3) or 0.3),
                max_connections=int(getattr(s, "REDIS_MAX_CONNECTIONS", 200) or 200),
            )
            key = f"tb:ai_create:{int(req.user_id)}"
            rate = float(getattr(s, "AI_CREATE_RATE_PER_MIN", 20) or 20) / 60.0
            burst = float(getattr(s, "AI_CREATE_BURST", 10) or 10)
            now = float(__import__("time").time())
            ok = r.eval(TOKEN_BUCKET, 1, key, rate, burst, now, 1)
            if int(ok or 0) != 1:
                raise HTTPException(status_code=429, detail="rate_limited")
        except HTTPException:
            raise
        except Exception:
            pass
    except HTTPException:
        raise
    except Exception:
        pass

    job_id = str(uuid.uuid4())
    payload = req.dict()

    db: Session = SessionLocal()
    post_id = None
    try:
        from app.api.v1.endpoints.ai_jobs import _build_fallback_draft, _sanitize_rerun_draft

        # Create Post first
        post = Post(
            user_id=req.user_id,
            content_text=req.long_text,
            post_type="video",
            status="queued",
            category=req.category,
            custom_instructions=req.prompt,
            download_enabled=True,
            title="AI Generated Video"
        )
        db.add(post)
        db.flush() # get ID
        post_id = post.id

        fallback_draft = _sanitize_rerun_draft(_build_fallback_draft(str(req.long_text or ""), "AI Generated Video"))
        job = AIJob(
            id=job_id, 
            user_id=req.user_id, 
            post_id=post_id,
            status="queued", 
            progress=0,
            kind="generate",
            stage="dispatch_pending",
            stage_message="等待派发",
            input_json={
                "post_type": "video",
                "content": str(req.long_text or ""),
                "custom_instructions": req.prompt,
                "subtitle_mode": "zh",
            },
            draft_json=fallback_draft,
        )
        db.add(job)
        
        # Link job to post
        post.ai_job_id = job_id
        
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Database error")
    finally:
        try:
            db.close()
        except Exception:
            pass

    try:
        from app.services.queue_service import send_worker_task

        task_id = send_worker_task(
            "generate_video",
            args=[str(job_id), str(req.long_text or ""), str(req.user_id)],
            kwargs={
                "post_id": int(post_id) if post_id else None,
                "custom_instructions": req.prompt,
                "post_type": "video",
                "subtitle_mode": "zh",
                "draft_json": getattr(job, "draft_json", None),
            },
        )
        print(f"INFO: queued generate_video task_id={task_id} job_id={job_id}")
    except Exception as e:
        print(f"ERROR: Failed to send task: {e}")
        import traceback
        traceback.print_exc()
        # Fallback without context if needed, though apply_async_with_context handles exceptions internally too
        pass

    return {"success": True, "job_id": job_id, "post_id": post_id, "message": "AI任务已提交"}

@router.get("/status/{job_id}")
async def get_job_status(job_id: str):
    db: Session = SessionLocal()
    try:
        job = db.query(AIJob).filter(AIJob.id == job_id).first()
        if not job:
            return {"job_id": job_id, "status": "not_found", "progress": 0}
        result = job.result_json if isinstance(job.result_json, dict) else {}
        try:
            from app.api.v1.endpoints.ai_jobs import _resolve_best_script_for_job
            post = db.query(Post).filter(Post.id == int(getattr(job, "post_id", 0) or 0)).first()
            ps = _resolve_best_script_for_job(db, job, post)
            if isinstance(ps, dict) and ps:
                result = dict(result)
                result["production_script"] = ps
        except Exception:
            pass
        return {
            "job_id": job_id,
            "status": job.status,
            "progress": job.progress or 0,
            "result": result if isinstance(result, dict) else job.result_json,
            "error": job.error,
        }
    finally:
        try:
            db.close()
        except Exception:
            pass
