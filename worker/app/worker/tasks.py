import asyncio
import logging
import os
import uuid
from pathlib import Path
from app.worker_callback import callback_web, cleanup_job_files
from app.core.database import db
from app.core.logger import get_logger
from app.core.config import settings
from app.services.video_service import video_service
from app.services.storage_service import storage_service

logger = get_logger(__name__)

async def process_transcode_video(job_id: str):
    """
    Process a video upload: Transcode -> Upload -> Callback
    """
    logger.info(f"Starting video transcoding for job {job_id}...")
    
    # Get job info from DB (or pass relevant info)
    # Since we don't have direct DB access to the 'video_url' yet in the worker's local DB copy (if separate),
    # we might need to fetch it or pass it.
    # But wait, the worker's DB is SQLite, but the main backend uses Postgres.
    # The worker logic `process_job` used local SQLite.
    # In the new architecture, we should ideally use the shared Postgres if possible, or pass all data in arguments.
    # For now, let's assume we pass the input_url as an argument to the task to be safe and stateless.
    pass 

async def process_transcode_video_task_logic(job_id: str, input_url: str, user_id: str, post_id: str = None):
    transcoded_path = None
    final_video_url = None
    final_hls_url = None
    hls_root = None
    cover_dir = None
    
    try:
        src = (input_url or "").strip()
        if src and not src.startswith("http"):
            signed = storage_service.presigned_get_url(src, expiration=3600)
            if signed:
                src = signed
        # 1. Transcode
        transcoded_path = video_service.transcode_video(job_id, src)
        meta = video_service.probe_video_meta(transcoded_path)
        duration = int(meta.get("duration") or 0)
        width = int(meta.get("width") or 0)
        height = int(meta.get("height") or 0)
        cover = video_service.generate_cover(job_id, transcoded_path)
        cover_dir = cover.get("dir") if isinstance(cover, dict) else None
        
        # 2. Upload Transcoded
        ver = str(uuid.uuid4())
        cache_ctl = "public, max-age=31536000, immutable"
        final_video_url = storage_service.upload_file(transcoded_path, f"videos/{job_id}/{ver}.mp4", content_type="video/mp4", cache_control=cache_ctl)

        cover_url = None
        try:
            if isinstance(cover, dict):
                if cover.get("webp"):
                    cover_url = storage_service.upload_file(str(cover["webp"]), f"covers/{job_id}/{ver}.webp", content_type="image/webp", cache_control=cache_ctl)
                elif cover.get("jpg"):
                    cover_url = storage_service.upload_file(str(cover["jpg"]), f"covers/{job_id}/{ver}.jpg", content_type="image/jpeg", cache_control=cache_ctl)
        except Exception:
            cover_url = None

        master_path = video_service.package_hls(job_id, transcoded_path)
        hls_root = Path(master_path).parent
        prefix = f"hls/{job_id}/{ver}"
        for root, _, files in os.walk(str(hls_root)):
            for fn in files:
                fp = Path(root) / fn
                rel = fp.relative_to(hls_root).as_posix()
                key = f"{prefix}/{rel}"
                ct = "application/octet-stream"
                low = fn.lower()
                if low.endswith(".m3u8"):
                    ct = "application/vnd.apple.mpegurl"
                elif low.endswith(".m4s"):
                    ct = "video/iso.segment"
                elif low.endswith(".mp4"):
                    ct = "video/mp4"
                elif low.endswith(".ts"):
                    ct = "video/mp2t"
                storage_service.upload_file(str(fp), key, content_type=ct, cache_control=cache_ctl)

        final_hls_url = f"{settings.r2_public_url.rstrip('/')}/{prefix}/master.m3u8" if getattr(settings, "r2_public_url", None) else None
        
        # 3. Callback
        # We reuse the callback mechanism.
        # Note: We don't have a local SQLite record for this upload job in the worker, 
        # so we skip `db.update_job` for local DB, but we MUST call back the backend.
        await callback_web(
            {"job_id": job_id, "user_id": user_id, "post_id": post_id, "title": "Processed Video"},
            hls_url=final_hls_url,
            mp4_url=final_video_url,
            cover_url=cover_url,
            duration=int(duration or 0),
            video_width=int(width or 0),
            video_height=int(height or 0),
            media_version=ver,
            status="done",
        )
        
    except Exception as e:
        logger.error(f"Transcoding failed: {e}")
        await callback_web(
            {"job_id": job_id, "post_id": post_id}, 
            error=str(e),
            status="failed",
        )
    finally:
        cleanup_job_files(job_id, transcoded_path, str(hls_root) if hls_root else None, str(cover_dir) if cover_dir else None)
