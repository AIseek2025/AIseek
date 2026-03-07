from app.core.celery_app import celery_app
from app.db.session import SessionLocal
from sqlalchemy import text

from app.services.counter_service import apply_post_counter_deltas
from app.services.hot_counter_service import take_delta


@celery_app.task(bind=True)
def flush_post_counters(self, post_id: int) -> bool:
    db = SessionLocal()
    try:
        pid = int(post_id)

        try:
            d = take_delta(pid)
            if d:
                if d.get("likes"):
                    db.execute(
                        text("UPDATE posts SET likes_count = CASE WHEN COALESCE(likes_count,0) + :d < 0 THEN 0 ELSE COALESCE(likes_count,0) + :d END WHERE id=:pid"),
                        {"d": int(d["likes"]), "pid": pid},
                    )
                if d.get("favorites"):
                    db.execute(
                        text("UPDATE posts SET favorites_count = CASE WHEN COALESCE(favorites_count,0) + :d < 0 THEN 0 ELSE COALESCE(favorites_count,0) + :d END WHERE id=:pid"),
                        {"d": int(d["favorites"]), "pid": pid},
                    )
                if d.get("comments"):
                    db.execute(
                        text("UPDATE posts SET comments_count = CASE WHEN COALESCE(comments_count,0) + :d < 0 THEN 0 ELSE COALESCE(comments_count,0) + :d END WHERE id=:pid"),
                        {"d": int(d["comments"]), "pid": pid},
                    )
                if d.get("views"):
                    db.execute(
                        text("UPDATE posts SET views_count = CASE WHEN COALESCE(views_count,0) + :d < 0 THEN 0 ELSE COALESCE(views_count,0) + :d END WHERE id=:pid"),
                        {"d": int(d["views"]), "pid": pid},
                    )
        except Exception:
            pass

        applied = 0
        for _ in range(3):
            n = apply_post_counter_deltas(db, pid, batch_size=2000)
            applied += n
            if n == 0:
                break
        db.commit()
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
