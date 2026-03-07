from functools import lru_cache

from celery import Celery

from app.core.config import get_settings


@lru_cache
def get_worker_celery() -> Celery:
    s = get_settings()
    broker = s.CELERY_BROKER_URL or s.REDIS_URL
    return Celery("aiseek-worker", broker=broker)


def send_worker_task(name: str, args=None, kwargs=None) -> str:
    app = get_worker_celery()
    q = None
    try:
        n = str(name or "")
        if n in {"generate_video", "refine_script", "generate_cover_only"}:
            q = "ai"
        elif n in {"process_upload_video"}:
            q = "transcode"
    except Exception:
        q = None
    res = app.send_task(name, args=args or [], kwargs=kwargs or {}, queue=q) if q else app.send_task(name, args=args or [], kwargs=kwargs or {})
    try:
        return str(getattr(res, "id", "") or "")
    except Exception:
        return ""
