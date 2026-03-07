from fastapi import FastAPI, HTTPException, Header, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import threading
import uuid
import uvicorn
import os

from app.core.config import settings
from app.core.queue import job_queue
from app.core.database import db
from app.core.logger import setup_logging, get_logger, log_job
from app.job_worker import run_worker

# Initialize Logging
setup_logging(level=settings.log_level)
logger = get_logger("aiseek.api")

app = FastAPI(title=settings.app_name, version="2.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models
class JobRequest(BaseModel):
    content: str
    user_id: Optional[str] = None
    job_id: Optional[str] = None
    callback_url: Optional[str] = None

class JobResponse(BaseModel):
    job_id: str
    status: str
    video_url: Optional[str] = None
    error: Optional[str] = None
    title: Optional[str] = None
    summary: Optional[str] = None
    created_at: Optional[str] = None

# Auth Dependency
def check_auth(authorization: Optional[str] = Header(None)):
    if not settings.has_auth:
        return
    
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    
    token = authorization[7:].strip()
    if token != settings.worker_secret:
        raise HTTPException(status_code=401, detail="Invalid token")

@app.on_event("startup")
async def startup_event():
    """Start the worker thread on startup."""
    worker_thread = threading.Thread(target=run_worker, daemon=True)
    worker_thread.start()
    logger.info("Worker thread started in background.")
    
    # Reload queued jobs from DB
    queued_jobs = db.get_jobs_by_status("queued")
    if queued_jobs:
        logger.info(f"Reloading {len(queued_jobs)} pending jobs from database...")
        for job in queued_jobs:
            job_queue.add_job(job)


@app.post("/trigger", response_model=JobResponse)
async def trigger_job(job: JobRequest, auth: None = Depends(check_auth)):
    """
    Trigger a new video generation job.
    """
    if len(job.content) < 10:
        raise HTTPException(status_code=400, detail="Content too short (min 10 chars)")
        
    if not job.job_id:
        job.job_id = str(uuid.uuid4())
    
    # Check if job exists
    if db.get_job(job.job_id):
        raise HTTPException(status_code=400, detail="Job ID already exists")

    # Add to DB
    success = db.create_job(job.job_id, job.user_id, job.content)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to create job record")

    # Add to Queue
    job_data = job.dict()
    queue_success = job_queue.add_job(job_data)
    
    if not queue_success:
        db.update_job(job.job_id, status="failed", error="Queue full or error")
        raise HTTPException(status_code=503, detail="Queue full")
    
    log_job(logger, job.job_id, "Job queued via API", user_id=job.user_id)
    
    return db.get_job(job.job_id)

@app.get("/status/{job_id}", response_model=JobResponse)
async def get_status(job_id: str, auth: None = Depends(check_auth)):
    """Check job status."""
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@app.get("/jobs/{user_id}", response_model=List[JobResponse])
async def get_user_jobs(user_id: str, limit: int = 20, auth: None = Depends(check_auth)):
    """Get jobs for a specific user."""
    return db.get_jobs_by_user(user_id, limit)

@app.get("/health")
async def health_check(auth: None = Depends(check_auth)):
    """Health check endpoint."""
    return {
        "status": "healthy",
        "worker": "running",
        "queue_stats": db.get_queue_stats(),
        "config": {
            "auth_enabled": settings.has_auth,
            "r2_enabled": settings.has_r2_config
        }
    }

if __name__ == "__main__":
    uvicorn.run("app.main:app", host=settings.worker_host, port=settings.worker_port, reload=True)
