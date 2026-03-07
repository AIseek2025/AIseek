from app.core.celery_app import celery_app
from app.db.session import SessionLocal
from app.services.notification_service import backfill_user_notifications


@celery_app.task(bind=True)
def backfill_user_notifications_task(self, user_id: int, max_items: int = 400) -> bool:
    db = SessionLocal()
    try:
        uid = int(user_id or 0)
        if uid <= 0:
            return False
        backfill_user_notifications(db, uid, max_items=int(max_items or 400))
        return True
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        return False
    finally:
        try:
            db.close()
        except Exception:
            pass
