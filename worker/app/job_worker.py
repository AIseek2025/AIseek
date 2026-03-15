import asyncio
import nest_asyncio
nest_asyncio.apply()
import logging
import time
import os
import uuid
import math
import requests
import redis
from pathlib import Path
from typing import List, Optional
from app.core.queue import job_queue
from app.core.database import db
from app.core.logger import JobLogger, get_logger
from app.core.config import settings, OUTPUTS_DIR, MAX_QUEUE_SIZE
from app.core.utils import retry_async
from app.services.deepseek_service import deepseek_service
from app.services.tts_service import tts_service
from app.services.video_service import video_service
from app.services.storage_service import storage_service
from app.services.browser_service import browser_service
from app.services.bgm_service import bgm_service
from app.services.subtitle_service import build_vtt, build_vtt_from_cues
from app.services.background_service import build_background_for_job
from app.services.cover_service import CoverService, build_cover_plan
from app.worker_callback import callback_web, cleanup_job_files
from app.pipeline.video_pipeline import VideoPipeline

logger = get_logger(__name__)
cover_service = CoverService()

_redis_client = None

def _get_redis():
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    try:
        url = os.getenv("REDIS_URL") or os.getenv("CELERY_BROKER_URL") or "redis://localhost:6379/0"
        r = redis.Redis.from_url(url, decode_responses=True, socket_timeout=0.4, socket_connect_timeout=0.2)
        r.ping()
        _redis_client = r
    except Exception:
        _redis_client = False
    return _redis_client

def _is_cancelled(job_id: str) -> bool:
    r = _get_redis()
    if not r:
        return False
    try:
        return bool(r.get(f"ai:cancel:{str(job_id)}"))
    except Exception:
        return False

async def process_job(job_data: dict):
    """
    Main entry point for video generation jobs.
    Delegates to VideoPipeline for the actual work.
    """
    try:
        pipeline = VideoPipeline(job_data)
        await pipeline.run()
    except Exception as e:
        logger.error(f"Critical error in process_job wrapper: {e}", exc_info=True)
        # Attempt last-ditch callback if pipeline didn't catch it
        try:
            await callback_web(job_data, status="failed", error=str(e), stage="failed")
        except:
            pass

async def refine_script_job(job_data: dict):
    job_id = job_data.get("job_id")
    content = job_data.get("content")
    post_type = job_data.get("post_type", "video")
    custom_instructions = job_data.get("custom_instructions")
    draft_in = job_data.get("draft_json")
    chat_messages = job_data.get("chat_messages") or []
    if not isinstance(chat_messages, list):
        chat_messages = []
    if not isinstance(draft_in, dict):
        draft_in = {}

    job_logger = JobLogger(logger, job_id)
    job_logger.start(queue_size=job_queue.get_status(job_id))
    try:
        await callback_web(job_data, status="processing", stage="chat_ai", progress=5, stage_message="AI正在生成建议", no_post_status=True)
        if _is_cancelled(str(job_id)):
            await callback_web(job_data, status="cancelled", stage="cancelled", progress=5, stage_message="用户取消", no_post_status=True)
            return
        out = await deepseek_service.refine_script(content, post_type, custom_instructions, draft_in, chat_messages)
        ps = out.get("production_script") if isinstance(out, dict) else None
        msg = str(out.get("assistant_message") or "").strip() if isinstance(out, dict) else ""
        if not isinstance(ps, dict):
            raise ValueError("missing_production_script")
        try:
            ap = out.get("apply_plan") if isinstance(out, dict) else None
            if isinstance(ap, dict):
                meta = ps.get("_meta") if isinstance(ps.get("_meta"), dict) else {}
                meta2 = dict(meta)
                meta2["apply_plan"] = ap
                ps["_meta"] = meta2
        except Exception:
            pass
        await callback_web(
            job_data,
            status="done",
            stage="chat_ai_done",
            progress=100,
            stage_message="建议已生成",
            draft_json=ps,
            assistant_message=msg,
            no_post_status=True,
        )
    except Exception as e:
        await callback_web(job_data, status="failed", stage="chat_ai_failed", progress=100, stage_message="建议生成失败", error=str(e), no_post_status=True)


async def generate_cover_only_job(job_data: dict):
    job_id = str(job_data.get("job_id") or "").strip()
    if not job_id:
        return
    post_id = job_data.get("post_id")
    user_id = job_data.get("user_id")
    title = str(job_data.get("title") or "").strip()
    summary = str(job_data.get("summary") or "").strip()
    cover_orientation = str(job_data.get("cover_orientation") or "portrait")
    mp4_url = str(job_data.get("mp4_url") or "").strip()
    hls_url = str(job_data.get("hls_url") or "").strip()
    video_inp = mp4_url or hls_url
    try:
        if video_inp and str(video_inp).startswith("/static/"):
            repo_root = Path(__file__).resolve().parents[3]
            st_root = repo_root / "backend" / "static"
            cand = st_root / str(video_inp)[len("/static/") :]
            if cand.exists():
                video_inp = str(cand)
            else:
                base = str(getattr(settings, "web_url", "") or "").rstrip("/")
                if base:
                    video_inp = base + str(video_inp)
    except Exception:
        pass

    cover_trace = None
    cover_audit = None
    cover_image_path = None
    try:
        plan = build_cover_plan({}, fallback_title=title, fallback_summary=summary, orientation=cover_orientation)
        cres = cover_service.generate_cover_image(str(job_id), plan)
        cover_trace = cres.trace
        if cres.ok and cres.image_path and os.path.exists(str(cres.image_path)):
            cover_image_path = str(cres.image_path)
            cover_audit = {"provider": cres.provider, "embedded": False, "type": "generated"}
    except Exception as e:
        logger.warning(f"cover_only_generate_failed job_id={job_id}: {e}")

    try:
        if not cover_image_path and video_inp:
            cov = video_service.generate_cover(str(job_id), str(video_inp), orientation=cover_orientation)
            cover_trace = [{"t": "frame_fallback", "ok": True, "src": str(video_inp)[:200]}]
            cover_audit = {"provider": "frame", "embedded": False, "type": "snapshot"}
            cover_image_path = str((cov or {}).get("webp") or (cov or {}).get("jpg") or "").strip() or None
    except Exception:
        cover_image_path = None

    cover_url = None
    try:
        if cover_image_path and os.path.exists(str(cover_image_path)):
            ct = "image/webp" if str(cover_image_path).lower().endswith(".webp") else "image/png" if str(cover_image_path).lower().endswith(".png") else "image/jpeg"
            ext = ".webp" if ct == "image/webp" else ".png" if ct == "image/png" else ".jpg"
            cover_url = storage_service.upload_file(str(cover_image_path), f"covers/{job_id}/{uuid.uuid4()}{ext}", content_type=ct, cache_control="public, max-age=31536000")
    except Exception as e:
        logger.warning(f"cover_only_upload_failed job_id={job_id}: {e}")
        cover_url = None

    await callback_web(
        {"job_id": job_id, "post_id": post_id, "user_id": user_id},
        status="done",
        cover_url=cover_url,
        stage="cover_only",
        stage_message="封面已生成",
        no_post_status=True,
        cover_trace=cover_trace if isinstance(cover_trace, list) else None,
        cover_audit=cover_audit if isinstance(cover_audit, dict) else None,
    )


def run_worker():
    logger.info(f"🚀 Worker started. Queue limit: {MAX_QUEUE_SIZE}")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    while True:
        try:
            job_data = job_queue.get_job()
            if job_data is None:
                break

            loop.run_until_complete(process_job(job_data))
            job_queue.task_done()

        except Exception as e:
            logger.error(f"Worker loop error: {e}")
            time.sleep(1)
