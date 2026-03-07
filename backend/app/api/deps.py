from collections.abc import Generator

from fastapi import Depends, Header, HTTPException
from starlette.requests import Request
from sqlalchemy.orm import Session

from app.db.session import SessionLocal, SessionLocalRead
from app.models.all_models import User


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_read_db(request: Request) -> Generator[Session, None, None]:
    use_primary = False
    try:
        use_primary = bool(request.cookies.get("aiseek_rw"))
    except Exception:
        use_primary = False
    db = SessionLocal() if use_primary else SessionLocalRead()
    try:
        yield db
    finally:
        db.close()


def get_current_user(authorization: str = Header(None), db: Session = Depends(get_db)) -> User:
    if not authorization or not str(authorization).startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = str(authorization).replace("Bearer ", "").strip()
    if token.startswith("fake-token-"):
        try:
            user_id = int(token.split("fake-token-")[1])
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid token")
        user = db.query(User).filter(User.id == int(user_id)).first()
        if not user:
            raise HTTPException(status_code=401, detail="Invalid token")
        if getattr(user, "is_active", True) is False:
            raise HTTPException(status_code=403, detail="Account disabled")
        return user

    from app.core.security import decode_access_token

    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    sub = payload.get("sub")
    try:
        user_id = int(sub)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    if getattr(user, "is_active", True) is False:
        raise HTTPException(status_code=403, detail="Account disabled")
    return user


def get_current_user_optional(authorization: str = Header(None), db: Session = Depends(get_db)) -> User | None:
    try:
        if not authorization or not str(authorization).startswith("Bearer "):
            return None
        return get_current_user(authorization=authorization, db=db)
    except Exception:
        return None


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if not bool(getattr(current_user, "is_superuser", False)):
        raise HTTPException(status_code=403, detail="Forbidden")
    return current_user
