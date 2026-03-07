import hashlib

from sqlalchemy.orm import Session

from app.models.all_models import ABAssignment


def get_variant(db: Session, *, user_id: int, experiment: str, variants=("A", "B")) -> str:
    if not user_id:
        return variants[0]
    row = db.query(ABAssignment).filter(ABAssignment.user_id == int(user_id), ABAssignment.experiment == experiment).first()
    if row and row.variant:
        return row.variant

    h = hashlib.sha256(f"{experiment}:{user_id}".encode("utf-8")).digest()
    bucket = int.from_bytes(h[:2], "big") % len(variants)
    v = variants[bucket]
    try:
        db.add(ABAssignment(user_id=int(user_id), experiment=experiment, variant=v))
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
    return v
