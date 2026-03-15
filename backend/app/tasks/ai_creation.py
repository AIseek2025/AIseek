from app.core.celery_app import celery_app
from typing import Optional, Dict

@celery_app.task(name="generate_video")
def generate_video(
    job_id: str,
    content: str,
    user_id: str,
    post_id: Optional[str] = None,
    post_type: str = "video",
    custom_instructions: Optional[str] = None,
    voice_style: Optional[str] = None,
    bgm_mood: Optional[str] = None,
    bgm_id: Optional[str] = None,
    subtitle_mode: Optional[str] = None,
    requested_duration_sec: Optional[int] = None,
    target_sec: Optional[int] = None,
    draft_json: Optional[Dict] = None,
    cover_orientation: Optional[str] = None,
):
    raise RuntimeError("generate_video must be dispatched to worker service, not executed in backend celery")

# Keep this for backward compatibility if needed, but it should not be used
run_ai_pipeline = generate_video
