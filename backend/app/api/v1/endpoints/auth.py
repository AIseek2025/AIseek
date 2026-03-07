from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.api.deps import get_db
from app.models.all_models import User
from pydantic import BaseModel
from typing import Optional

router = APIRouter()

# Schemas
class UserCreate(BaseModel):
    username: str
    password: str
    email: Optional[str] = None
    phone: Optional[str] = None

class UserOut(BaseModel):
    id: int
    username: str
    nickname: str = None
    
    class Config:
        orm_mode = True

AISEEK_ID_WIDTH = 10

def fmt_aiseek_id(user_id: int) -> str:
    return str(user_id).zfill(AISEEK_ID_WIDTH)

@router.post("/register", response_model=UserOut)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    # Check existing username
    user = db.query(User).filter(User.username == user_in.username).first()
    if user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    # Check existing phone if provided
    if user_in.phone:
        user_phone = db.query(User).filter(User.phone == user_in.phone).first()
        if user_phone:
            raise HTTPException(status_code=400, detail="Phone already registered")
            
    from app.core.security import get_password_hash

    db_user = User(
        username=user_in.username,
        email=user_in.email,
        phone=user_in.phone,
        password_hash=get_password_hash(user_in.password),
        nickname=user_in.username,
        followers_count=0,
        following_count=0,
        likes_received_count=0
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    db_user.aiseek_id = fmt_aiseek_id(db_user.id)
    db.commit()
    db.refresh(db_user)
    return db_user

@router.post("/login")
def login(user_in: UserCreate, db: Session = Depends(get_db)):
    from app.core.security import create_access_token, verify_password

    ident = (user_in.username or "").strip()
    user = db.query(User).filter(
        or_(
            User.username == ident,
            User.email == ident,
            User.phone == ident,
        )
    ).first()
    ok = bool(user and verify_password(user_in.password, user.password_hash))
    if not ok and user and isinstance(user.password_hash, str) and user.password_hash.endswith("_hashed"):
        ok = bool(user.password_hash == str(user_in.password or "") + "_hashed")
    if not user or not ok:
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    if getattr(user, "is_active", True) is False:
        raise HTTPException(status_code=403, detail="Account disabled")
    
    return {
        "access_token": create_access_token(subject=str(user.id)),
        "token_type": "bearer",
        "user_id": user.id,
        "username": user.username
    }
