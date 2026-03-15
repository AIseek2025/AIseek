import asyncio
import hashlib
import random
from datetime import datetime, timedelta
from typing import List, Optional

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.all_models import AIJob, Post
from app.services.job_event_service import append_job_event


def _read_ai_production_runtime() -> dict:
    try:
        from app.observability.runtime_ai_production import read_runtime_ai_production

        cfg = read_runtime_ai_production()
        return cfg if isinstance(cfg, dict) else {}
    except Exception:
        return {}


def _write_ai_production_runtime(cfg: dict) -> None:
    try:
        from app.observability.runtime_ai_production import write_runtime_ai_production

        write_runtime_ai_production(cfg if isinstance(cfg, dict) else {})
    except Exception:
        pass


def _auto_release_dispatch_hold(db, rt: dict, now: datetime) -> int:
    cfg = rt if isinstance(rt, dict) else {}
    if not bool(cfg.get("auto_release_on_disable", True)):
        return 0
    batch = int(cfg.get("auto_release_batch_size", 200) or 200)
    if batch < 1:
        batch = 1
    if batch > 1000:
        batch = 1000
    adaptive_mode = "normal"
    fail_ratio = 0.0
    if bool(cfg.get("auto_release_adaptive_enabled", True)):
        ratio_thr = float(cfg.get("auto_release_adaptive_fail_ratio", 0.35) or 0.35)
        if ratio_thr < 0:
            ratio_thr = 0.0
        if ratio_thr > 1:
            ratio_thr = 1.0
        mul_pct = int(cfg.get("auto_release_adaptive_multiplier_pct", 50) or 50)
        if mul_pct < 5:
            mul_pct = 5
        if mul_pct > 100:
            mul_pct = 100
        from sqlalchemy import func

        rows = (
            db.query(AIJob.stage, func.count(AIJob.id))
            .filter(AIJob.status == "queued")
            .filter(AIJob.stage.in_(["dispatch_pending", "dispatching", "dispatch_failed"]))
            .group_by(AIJob.stage)
            .all()
        )
        p = 0
        d = 0
        f = 0
        for st, cnt in rows:
            s = str(st or "")
            if s == "dispatch_pending":
                p += int(cnt or 0)
            elif s == "dispatching":
                d += int(cnt or 0)
            elif s == "dispatch_failed":
                f += int(cnt or 0)
        den = p + d + f
        if den > 0:
            fail_ratio = float(f / den)
        if fail_ratio >= ratio_thr:
            adaptive_mode = "throttled"
            batch = max(1, int(batch * mul_pct / 100))
    interval_sec = int(cfg.get("auto_release_interval_sec", 15) or 15)
    if interval_sec < 1:
        interval_sec = 1
    if interval_sec > 3600:
        interval_sec = 3600
    now_ts = int(now.timestamp())
    last_ts = int(cfg.get("last_auto_release_ts", 0) or 0)
    if last_ts > 0 and int(now_ts - last_ts) < interval_sec:
        return 0
    ids = (
        db.query(AIJob.id)
        .filter(AIJob.status == "queued")
        .filter(AIJob.stage == "dispatch_hold")
        .order_by(AIJob.updated_at.asc())
        .limit(int(batch))
        .all()
    )
    release_ids: List[str] = []
    for row in ids:
        jid = str(getattr(row, "id", None) or (row[0] if isinstance(row, (tuple, list)) and row else "")).strip()
        if jid:
            release_ids.append(jid)
    released = 0
    if release_ids:
        released = int(
            db.query(AIJob)
            .filter(AIJob.id.in_(release_ids))
            .filter(AIJob.status == "queued")
            .filter(AIJob.stage == "dispatch_hold")
            .update(
                {
                    AIJob.stage: "dispatch_pending",
                    AIJob.stage_message: "等待派发",
                    AIJob.next_dispatch_at: now,
                },
                synchronize_session=False,
            )
            or 0
        )
        db.commit()
        for jid in release_ids[:released]:
            try:
                append_job_event(str(jid), "dispatch_released", {"reason": "auto_release_on_disable"})
                append_job_event(str(jid), "dispatch_pending", {"reason": "auto_release_on_disable", "released": True})
            except Exception:
                pass
    cfg["last_auto_release_ts"] = int(now_ts)
    cfg["last_auto_release_count"] = int(released)
    cfg["last_auto_release_effective_batch"] = int(batch)
    cfg["last_auto_release_adaptive_mode"] = str(adaptive_mode)
    cfg["last_auto_release_fail_ratio"] = float(fail_ratio)
    arr = cfg.get("auto_release_history")
    hist = arr if isinstance(arr, list) else []
    hist2 = [x for x in hist if isinstance(x, dict)]
    hist2.append(
        {
            "ts": int(now_ts),
            "released": int(released),
            "effective_batch": int(batch),
            "fail_ratio": float(fail_ratio),
            "mode": str(adaptive_mode),
        }
    )
    if len(hist2) > 120:
        hist2 = hist2[-120:]
    cfg["auto_release_history"] = hist2
    _write_ai_production_runtime(cfg)
    return int(released)


def _norm_cover_orientation(v) -> str:
    s = str(v or "").strip().lower()
    if s == "landscape":
        return "landscape"
    return "portrait"


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
            "cover_orientation": _norm_cover_orientation(inp.get("cover_orientation")),
            "target_sec": pf.get("target_sec"),
            "post_id": int(post.id),
            "draft_json": getattr(job, "draft_json", None),
        },
    )


def _auto_hold_by_queue_pressure(db, rt: dict) -> dict:
    cfg = rt if isinstance(rt, dict) else {}
    if bool(cfg.get("dispatch_hold_enabled", False)):
        return cfg
    if not bool(cfg.get("auto_hold_enabled", True)):
        return cfg
    thr = int(cfg.get("auto_hold_queue_threshold", 2000) or 2000)
    if thr < 10:
        thr = 10
    queued = int(
        db.query(AIJob.id)
        .filter(AIJob.status == "queued")
        .filter(AIJob.stage.in_(["dispatch_pending", "dispatch_failed", "dispatching"]))
        .count()
        or 0
    )
    if queued < thr:
        return cfg
    cfg["dispatch_hold_enabled"] = True
    cfg["dispatch_hold_reason"] = "queue_pressure_auto_hold"
    _write_ai_production_runtime(cfg)
    return cfg


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
    rt = _read_ai_production_runtime()
    try:
        rt = _auto_hold_by_queue_pressure(db, rt=rt)
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
    if bool(rt.get("dispatch_hold_enabled", False)):
        try:
            db.close()
        except Exception:
            pass
        return 0
    try:
        _auto_release_dispatch_hold(db, rt=rt, now=now)
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
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
