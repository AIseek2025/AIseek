import time

from app.core.celery_app import celery_app
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.all_models import Post
from app.services.search_service import index_post_to_es, rebuild_posts_index


@celery_app.task(bind=True)
def index_post(self, post_id: int) -> bool:
    s = get_settings()
    if not s.ELASTICSEARCH_URL:
        return False
    db = SessionLocal()
    try:
        post = db.query(Post).filter(Post.id == post_id).first()
        if not post:
            return False
        return index_post_to_es(post)
    finally:
        try:
            db.close()
        except Exception:
            pass


@celery_app.task(bind=True)
def reindex_posts(self, limit: int = 5000) -> int:
    s = get_settings()
    if not s.ELASTICSEARCH_URL:
        return 0
    db = SessionLocal()
    try:
        out = rebuild_posts_index(db, limit=int(limit))
        return int((out or {}).get("ok") or 0)
    finally:
        try:
            db.close()
        except Exception:
            pass


@celery_app.task(bind=True)
def rebuild_posts_index_job(self, job_id: str, limit: int = 5000) -> int:
    s = get_settings()
    if not s.ELASTICSEARCH_URL:
        return 0

    status_key = "es:reindex:posts:status"
    lock_key = "lock:es:reindex:posts"
    cancel_key = "es:reindex:posts:cancel"
    lock_ttl = 60 * 30

    acquired = False
    r = None
    try:
        import redis

        r = redis.Redis.from_url(
            s.REDIS_URL,
            decode_responses=True,
            socket_timeout=float(getattr(s, "REDIS_SOCKET_TIMEOUT_SEC", 0.6) or 0.6),
            socket_connect_timeout=float(getattr(s, "REDIS_CONNECT_TIMEOUT_SEC", 0.3) or 0.3),
            max_connections=int(getattr(s, "REDIS_MAX_CONNECTIONS", 200) or 200),
        )
        acquired = bool(r.set(lock_key, str(job_id), nx=True, ex=int(lock_ttl)))
    except Exception:
        acquired = False
        r = None
    if not acquired:
        try:
            from app.core.cache import cache

            cache.set_json(status_key, {"job_id": str(job_id), "status": "locked"}, ttl=600)
        except Exception:
            pass
        return 0

    from app.core.cache import cache
    from app.models.all_models import ESReindexJob

    def progress(obj: dict) -> None:
        payload = {"job_id": str(job_id), **(obj or {})}
        cache.set_json(status_key, payload, ttl=86400)

    cache.set_json(status_key, {"job_id": str(job_id), "status": "starting"}, ttl=86400)
    try:
        cache.set_json(cancel_key, None, ttl=1)
    except Exception:
        pass

    db = SessionLocal()
    last_db_ts = 0.0
    try:
        try:
            row = db.query(ESReindexJob).filter(ESReindexJob.id == str(job_id)).first()
            if not row:
                row = ESReindexJob(id=str(job_id))
                db.add(row)
            row.alias = str(getattr(s, "ELASTICSEARCH_INDEX", "") or "")
            row.status = "starting"
            row.ok = 0
            row.total = 0
            row.cancelled = False
            row.error = None
            db.commit()
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass

        def is_cancelled() -> bool:
            try:
                return cache.get_json(cancel_key) is not None
            except Exception:
                return False

        def progress2(obj: dict) -> None:
            nonlocal last_db_ts
            progress(obj)
            try:
                now = time.time()
                if now - float(last_db_ts or 0) < 2.0:
                    return
                last_db_ts = now
                row = db.query(ESReindexJob).filter(ESReindexJob.id == str(job_id)).first()
                if not row:
                    return
                row.status = str(obj.get("status") or row.status or "")
                row.new_index = str(obj.get("new_index") or row.new_index or "")
                try:
                    row.ok = int(obj.get("ok") or row.ok or 0)
                except Exception:
                    pass
                try:
                    row.total = int(obj.get("total") or row.total or 0)
                except Exception:
                    pass
                db.commit()
            except Exception:
                try:
                    db.rollback()
                except Exception:
                    pass

        out = rebuild_posts_index(db, limit=int(limit), progress=progress2, is_cancelled=is_cancelled)
        cache.set_json(status_key, {"job_id": str(job_id), **(out or {}), "status": "done"}, ttl=86400)
        try:
            row = db.query(ESReindexJob).filter(ESReindexJob.id == str(job_id)).first()
            if row:
                row.status = "done"
                row.new_index = str((out or {}).get("new_index") or row.new_index or "")
                row.cancelled = bool((out or {}).get("cancelled") or False)
                try:
                    row.ok = int((out or {}).get("ok") or row.ok or 0)
                except Exception:
                    pass
                try:
                    row.total = int((out or {}).get("total") or row.total or 0)
                except Exception:
                    pass
                db.commit()
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
        return int((out or {}).get("ok") or 0)
    finally:
        try:
            db.close()
        except Exception:
            pass
        try:
            if r:
                r.delete(lock_key)
        except Exception:
            pass
