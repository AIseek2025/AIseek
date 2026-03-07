from celery import Celery
import os
import asyncio
from app.job_worker import process_job, refine_script_job, generate_cover_only_job
from app.worker.tasks import process_transcode_video_task_logic

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

celery_app = Celery(
    "worker",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    result_expires=60 * 60,
    broker_transport_options={
        "visibility_timeout": 60 * 60,
    },
    task_default_queue="default",
    task_soft_time_limit=int(os.getenv("AI_TASK_SOFT_TIME_LIMIT_SEC", "1500") or 1500),
    task_time_limit=int(os.getenv("AI_TASK_TIME_LIMIT_SEC", "1800") or 1800),
    task_routes={
        "generate_video": {"queue": "ai"},
        "refine_script": {"queue": "ai"},
        "generate_cover_only": {"queue": "ai"},
        "process_upload_video": {"queue": "transcode"},
    },
)


def _run(coro):
    try:
        asyncio.run(coro)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            loop.run_until_complete(coro)
        finally:
            try:
                loop.close()
            except Exception:
                pass


@celery_app.task(name="generate_video")
def generate_video_task(job_id: str, content: str, user_id: str, post_id: str = None, post_type: str = "video", custom_instructions: str = None, voice_style: str = None, bgm_mood: str = None, bgm_id: str = None, subtitle_mode: str = None, requested_duration_sec: int = None, target_sec: int = None, draft_json: dict = None, cover_orientation: str = None):
    # Bridge to existing async logic
    job_data = {
        "job_id": job_id,
        "post_id": post_id,
        "content": content,
        "user_id": user_id,
        "post_type": post_type,
        "custom_instructions": custom_instructions,
        "voice_style": voice_style,
        "bgm_mood": bgm_mood,
        "bgm_id": bgm_id,
        "subtitle_mode": subtitle_mode,
        "requested_duration_sec": requested_duration_sec,
        "target_sec": target_sec,
        "draft_json": draft_json,
        "cover_orientation": cover_orientation,
    }
    
    _run(process_job(job_data))
    
    return {"status": "completed", "job_id": job_id}

@celery_app.task(name="process_upload_video")
def process_upload_video_task(job_id: str, input_url: str, user_id: str, post_id: str = None):
    """
    Celery task to handle uploaded video processing (transcoding).
    """
    _run(process_transcode_video_task_logic(job_id, input_url, user_id, post_id=post_id))
    return {"status": "transcoded", "job_id": job_id}


@celery_app.task(name="refine_script")
def refine_script_task(job_id: str, content: str, user_id: str, post_id: str = None, post_type: str = "video", custom_instructions: str = None, draft_json: dict = None, chat_messages: list = None):
    job_data = {
        "job_id": job_id,
        "post_id": post_id,
        "content": content,
        "user_id": user_id,
        "post_type": post_type,
        "custom_instructions": custom_instructions,
        "draft_json": draft_json,
        "chat_messages": chat_messages or [],
    }
    _run(refine_script_job(job_data))
    return {"status": "completed", "job_id": job_id}


@celery_app.task(name="generate_cover_only")
def generate_cover_only_task(job_id: str, user_id: str, post_id: str = None, title: str = None, summary: str = None, mp4_url: str = None, hls_url: str = None, cover_orientation: str = None):
    job_data = {
        "job_id": job_id,
        "post_id": post_id,
        "user_id": user_id,
        "title": title,
        "summary": summary,
        "mp4_url": mp4_url,
        "hls_url": hls_url,
        "cover_orientation": cover_orientation,
        "post_type": "video",
        "content": "",
    }
    _run(generate_cover_only_job(job_data))
    return {"status": "completed", "job_id": job_id}
