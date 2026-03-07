from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import uuid
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.all_models import AIJob
from app.tasks.ai_creation import run_ai_pipeline
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
    try:
        job = AIJob(id=job_id, user_id=req.user_id, status="queued", progress=0)
        db.add(job)
        db.commit()
    finally:
        try:
            db.close()
        except Exception:
            pass

    try:
        from app.core.celery_app import apply_async_with_context

        apply_async_with_context(run_ai_pipeline, args=[job_id, payload])
    except Exception:
        run_ai_pipeline.delay(job_id, payload)

    return {"success": True, "job_id": job_id, "message": "AI任务已提交"}

@router.get("/status/{job_id}")
async def get_job_status(job_id: str):
    db: Session = SessionLocal()
    try:
        job = db.query(AIJob).filter(AIJob.id == job_id).first()
        if not job:
            return {"job_id": job_id, "status": "not_found", "progress": 0}
        return {
            "job_id": job_id,
            "status": job.status,
            "progress": job.progress or 0,
            "result": job.result_json,
            "error": job.error,
        }
    finally:
        try:
            db.close()
        except Exception:
            pass
