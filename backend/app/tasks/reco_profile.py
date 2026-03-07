from collections import Counter

from app.core.celery_app import celery_app
from app.db.session import SessionLocal
from app.models.all_models import ClientEvent, UserPersona


@celery_app.task(bind=True)
def rebuild_user_persona(self, user_id: int, limit: int = 500) -> bool:
    db = SessionLocal()
    try:
        uid = int(user_id)
        rows = (
            db.query(ClientEvent)
            .filter(ClientEvent.user_id == uid)
            .order_by(ClientEvent.ts.desc(), ClientEvent.id.desc())
            .limit(int(limit))
            .all()
        )
        tabs = Counter()
        names = Counter()
        cats = Counter()
        for r in rows:
            if r.tab:
                tabs[str(r.tab)] += 1
            if r.name:
                names[str(r.name)] += 1
            try:
                if r.data and isinstance(r.data, dict):
                    c = r.data.get("category")
                    if c:
                        cats[str(c)] += 1
            except Exception:
                pass

        tags = []
        for k, _ in tabs.most_common(5):
            tags.append(f"tab:{k}")
        for k, _ in cats.most_common(5):
            tags.append(f"cat:{k}")
        for k, _ in names.most_common(5):
            tags.append(f"ev:{k}")

        persona = db.query(UserPersona).filter(UserPersona.user_id == uid).first()
        if not persona:
            persona = UserPersona(user_id=uid, tags=tags, behavior_log=[])
            db.add(persona)
        else:
            persona.tags = tags
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
