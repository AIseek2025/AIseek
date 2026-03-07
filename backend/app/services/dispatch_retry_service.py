import asyncio
import hashlib
import random
from datetime import datetime, timedelta
from typing import Optional

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.all_models import AIJob, Post
from app.services.job_event_service import append_job_event


def _backoff_sec(attempt: int, base: int, max_sec: int) -> int:
    a = max(1, int(attempt or 1))
    b = int(base or 1)
    m = int(max_sec or 60)
    sec = min(m, b * (2 ** min(a - 1, 10)))
    jitter = random.randint(0, max(1, sec // 5))
    return int(min(m, sec + jitter))


def _dispatch_generate(job: AIJob, post: Post) -> str:
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
    return send_worker_task(
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
            "target_sec": pf.get("target_sec"),
            "post_id": int(post.id),
            "draft_json": getattr(job, "draft_json", None),
        },
    )


def dispatch_once(limit: int) -> int:
    s = get_settings()
    if not bool(getattr(s, "DISPATCH_RETRY_ENABLED", True)):
        return 0
    lim = max(1, min(int(limit or 50), int(getattr(s, "DISPATCH_RETRY_BATCH", 50) or 50)))
    now = datetime.now()
    n = 0
    db = SessionLocal()
    max_attempts = int(getattr(s, "DISPATCH_RETRY_MAX_ATTEMPTS", 8) or 8)
    stale_sec = 60
    shards = max(1, int(getattr(s, "DISPATCH_SHARDS", 1) or 1))
    shard_id = int(getattr(s, "DISPATCH_SHARD_ID", -1) or -1)
    try:
        ids = (
            db.query(AIJob.id)
            .filter(AIJob.status == "queued")
            .filter(AIJob.stage.in_(["dispatch_pending", "dispatch_failed", "dispatching"]))
            .filter(AIJob.dispatch_attempts < max_attempts)
            .filter((AIJob.next_dispatch_at == None) | (AIJob.next_dispatch_at <= now))
            .order_by(AIJob.next_dispatch_at.asc(), AIJob.updated_at.asc())
            .limit(lim)
            .all()
        )
    except Exception:
        ids = []

    if shard_id >= 0 and shards > 1:
        picked = []
        for row in ids:
            try:
                jid = str(getattr(row, "id", None) or (row[0] if isinstance(row, (tuple, list)) and row else "")).strip()
                if not jid:
                    continue
                hv = int(hashlib.md5(jid.encode("utf-8")).hexdigest()[:8], 16)
                if int(hv % shards) != int(shard_id):
                    continue
                picked.append(row)
            except Exception:
                continue
        ids = picked

    for row in ids:
        job_id = ""
        try:
            job_id = str(getattr(row, "id", None) or (row[0] if isinstance(row, (tuple, list)) and row else "")).strip()
            if not job_id:
                continue

            try:
                from sqlalchemy import or_

                ok = (
                    db.query(AIJob)
                    .filter(
                        AIJob.id == str(job_id),
                        AIJob.status == "queued",
                        AIJob.stage.in_(["dispatch_pending", "dispatch_failed", "dispatching"]),
                        AIJob.dispatch_attempts < max_attempts,
                        or_(AIJob.next_dispatch_at == None, AIJob.next_dispatch_at <= now),
                        or_(AIJob.stage != "dispatching", AIJob.last_dispatch_at == None, AIJob.last_dispatch_at <= now - timedelta(seconds=stale_sec)),
                    )
                    .update(
                        {
                            AIJob.stage: "dispatching",
                            AIJob.stage_message: "派发中",
                            AIJob.dispatch_attempts: (AIJob.dispatch_attempts + 1),
                            AIJob.last_dispatch_at: now,
                            AIJob.next_dispatch_at: None,
                        },
                        synchronize_session=False,
                    )
                )
                if int(ok or 0) != 1:
                    continue
                db.commit()
            except Exception:
                try:
                    db.rollback()
                except Exception:
                    pass
                continue

            job = db.query(AIJob).filter(AIJob.id == str(job_id)).first()
            if not job:
                continue
            post = None
            if getattr(job, "post_id", None) is not None:
                post = db.query(Post).filter(Post.id == int(job.post_id)).first()
            if not post:
                try:
                    job.stage = "dispatch_failed"
                    job.stage_message = "任务派发失败，可重试"
                    job.error = "post_not_found"
                    job.next_dispatch_at = now + timedelta(seconds=30)
                    db.commit()
                    append_job_event(str(job.id), "dispatch_failed", {"error": "post_not_found", "retry_in_sec": 30})
                except Exception:
                    try:
                        db.rollback()
                    except Exception:
                        pass
                continue

            task_id = _dispatch_generate(job, post)
            job.worker_task_id = str(task_id or "") or None
            job.stage = "queued"
            job.stage_message = "已派发，等待处理"
            job.error = None
            try:
                job.progress = max(1, int(getattr(job, "progress", 0) or 0))
            except Exception:
                job.progress = 1
            db.commit()
            append_job_event(str(job.id), "dispatch", {"post_id": int(post.id), "attempt": int(job.dispatch_attempts or 0), "worker_task_id": str(task_id or "")})
            n += 1
        except Exception as e:
            try:
                b = _backoff_sec(int(getattr(job, "dispatch_attempts", 1) or 1), int(getattr(s, "DISPATCH_RETRY_BASE_SEC", 5) or 5), int(getattr(s, "DISPATCH_RETRY_MAX_SEC", 120) or 120))
                try:
                    job2 = db.query(AIJob).filter(AIJob.id == str(job_id)).first()
                except Exception:
                    job2 = None
                if job2:
                    job2.stage = "dispatch_failed"
                    job2.stage_message = "任务派发失败，可重试"
                    job2.error = str(e)
                    job2.next_dispatch_at = now + timedelta(seconds=int(b))
                    db.commit()
                    append_job_event(str(job2.id), "dispatch_failed", {"error": str(e)[:200], "retry_in_sec": int(b)})
            except Exception:
                try:
                    db.rollback()
                except Exception:
                    pass
    try:
        db.close()
    except Exception:
        pass
    return n


async def dispatch_loop() -> None:
    s = get_settings()
    if not bool(getattr(s, "DISPATCH_RETRY_ENABLED", True)):
        return
    while True:
        try:
            lease_ok = True
            try:
                from app.core.cache import cache
                from datetime import datetime as _dt

                shards = max(1, int(getattr(s, "DISPATCH_SHARDS", 1) or 1))
                shard_id = int(getattr(s, "DISPATCH_SHARD_ID", -1) or -1)
                r = cache._get_redis()
                if r and shards > 1 and shard_id >= 0:
                    lk = f"lease:dispatch:{shards}:{shard_id}"
                    lease_ok = bool(r.set(lk, str(int(_dt.now().timestamp())), nx=True, ex=2))
            except Exception:
                lease_ok = True
            if lease_ok:
                dispatch_once(int(getattr(s, "DISPATCH_RETRY_BATCH", 50) or 50))
        except Exception:
            pass
        await asyncio.sleep(2.0)


def start_dispatch_loop() -> Optional[asyncio.Task]:
    s = get_settings()
    if not bool(getattr(s, "DISPATCH_RETRY_ENABLED", True)):
        return None
    try:
        return asyncio.create_task(dispatch_loop())
    except Exception:
        return None
