import os
import json
import time
import hmac
import hashlib
import httpx
from typing import List, Optional

from app.core.config import settings
from app.core.ai_stages import allow_draft_write, allow_assistant_message_write
from app.core.logger import get_logger
from app.core.utils import retry_async


logger = get_logger(__name__)

_HTTP: Optional[httpx.AsyncClient] = None
_LAST_CB: dict = {}


def _get_http() -> httpx.AsyncClient:
    global _HTTP
    if _HTTP is not None:
        return _HTTP
    _HTTP = httpx.AsyncClient(
        timeout=httpx.Timeout(10.0, connect=2.0, read=10.0, write=10.0),
        limits=httpx.Limits(max_connections=64, max_keepalive_connections=32, keepalive_expiry=30.0),
        headers={"connection": "keep-alive"},
    )
    return _HTTP


def _should_send(job_id: str, stage: Optional[str], progress: Optional[int], stage_message: Optional[str]) -> bool:
    try:
        jid = str(job_id or "").strip()
        if not jid:
            return True
        now = time.time()
        cur = _LAST_CB.get(jid)
        if not isinstance(cur, dict):
            cur = {}
        last_ts = float(cur.get("ts") or 0.0)
        last_stage = str(cur.get("stage") or "")
        last_msg = str(cur.get("msg") or "")
        last_prog = int(cur.get("prog") or -1)

        st = str(stage or "")
        msg = str(stage_message or "")
        prog = None if progress is None else int(progress)

        if st and st != last_stage:
            ok = True
        elif msg and msg != last_msg:
            ok = True
        elif prog is not None and (last_prog < 0 or abs(prog - last_prog) >= 2):
            ok = True
        else:
            ok = (now - last_ts) >= 1.2

        if ok:
            _LAST_CB[jid] = {"ts": now, "stage": st, "msg": msg, "prog": prog if prog is not None else last_prog}
            if len(_LAST_CB) > 5000:
                try:
                    for k in list(_LAST_CB.keys())[:1000]:
                        _LAST_CB.pop(k, None)
                except Exception:
                    pass
        return ok
    except Exception:
        return True


async def callback_web(
    job_data: dict,
    hls_url: str = None,
    mp4_url: str = None,
    cover_url: str = None,
    duration: int = None,
    video_width: int = None,
    video_height: int = None,
    media_version: str = None,
    images: List[str] = None,
    error: str = None,
    status: Optional[str] = None,
    progress: Optional[int] = None,
    stage: Optional[str] = None,
    stage_message: Optional[str] = None,
    draft_json: Optional[dict] = None,
    assistant_message: Optional[str] = None,
    no_post_status: Optional[bool] = None,
    subtitle_tracks: Optional[list] = None,
    placeholder_trace: Optional[list] = None,
    placeholder_audit: Optional[dict] = None,
    cover_trace: Optional[list] = None,
    cover_audit: Optional[dict] = None,
):
    if not settings.web_url:
        return

    callback_url = f"{settings.web_url.rstrip('/')}/api/v1/posts/callback"

    st = (status or "").strip() or ("failed" if error else "done")
    try:
        if stage and draft_json is not None and not allow_draft_write(stage):
            draft_json = None
    except Exception:
        pass
    try:
        if stage and assistant_message and not allow_assistant_message_write(stage):
            assistant_message = None
    except Exception:
        pass
    payload = {
        "job_id": job_data["job_id"],
        "post_id": job_data.get("post_id"),
        "status": st,
        "progress": progress,
        "stage": stage,
        "stage_message": stage_message,
        "draft_json": draft_json,
        "assistant_message": assistant_message,
        "no_post_status": bool(no_post_status) if no_post_status is not None else None,
        "video_url": hls_url or mp4_url,
        "hls_url": hls_url,
        "mp4_url": mp4_url,
        "cover_url": cover_url,
        "duration": duration,
        "video_width": video_width,
        "video_height": video_height,
        "media_version": media_version,
        "images": images,
        "error": error,
        "title": job_data.get("title"),
        "summary": job_data.get("summary"),
        "subtitle_tracks": subtitle_tracks,
        "placeholder_trace": placeholder_trace,
        "placeholder_audit": placeholder_audit,
        "cover_trace": cover_trace,
        "cover_audit": cover_audit,
    }

    async def _send():
        client = _get_http()
        headers = {}
        try:
            if settings.worker_secret:
                headers["x-worker-secret"] = str(settings.worker_secret)
        except Exception:
            pass
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        try:
            if settings.worker_secret:
                ts = str(int(time.time()))
                msg = ts.encode("utf-8") + b"." + body
                sig = hmac.new(str(settings.worker_secret).encode("utf-8"), msg=msg, digestmod=hashlib.sha256).hexdigest()
                headers["x-worker-ts"] = ts
                headers["x-worker-sig"] = sig
        except Exception:
            pass
        headers["content-type"] = "application/json"
        await client.post(callback_url, content=body, headers=headers or None)

    try:
        if not _should_send(str(job_data.get("job_id") or ""), stage, progress, stage_message):
            return
        await retry_async(_send, max_retries=3)
    except Exception as e:
        logger.warning(f"Failed to callback web: {e}")


def cleanup_job_files(job_id: str, *paths):
    for p in paths:
        if p and os.path.exists(p):
            try:
                if os.path.isdir(p):
                    import shutil

                    shutil.rmtree(p, ignore_errors=True)
                else:
                    os.remove(p)
            except OSError:
                pass
