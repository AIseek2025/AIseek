from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import case, func, or_
from app.api.deps import get_current_user, get_db, get_read_db
from app.models.all_models import Message, User
from typing import List, Optional
from pydantic import BaseModel
import datetime

router = APIRouter()

class MessageCreate(BaseModel):
    sender_id: int
    receiver_id: int
    content: str

class MessageOut(BaseModel):
    id: int
    sender_id: int
    receiver_id: int
    content: str
    is_read: bool
    created_at: datetime.datetime
    
    class Config:
        orm_mode = True

@router.post("/send", response_model=MessageOut)
def send_message(msg: MessageCreate, authorization: Optional[str] = Header(None), db: Session = Depends(get_db)):
    u = get_current_user(authorization=authorization, db=db)
    uid = int(getattr(u, "id", 0) or 0)
    if uid <= 0:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if int(msg.receiver_id) == int(uid):
        raise HTTPException(status_code=400, detail="Cannot message yourself")
    peer = db.query(User).filter(User.id == int(msg.receiver_id)).first()
    if not peer:
        raise HTTPException(status_code=404, detail="User not found")
    content = str(msg.content or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="empty")
    if len(content) > 2000:
        content = content[:2000]
        
    db_msg = Message(
        sender_id=int(uid),
        receiver_id=int(msg.receiver_id),
        content=content
    )
    db.add(db_msg)
    db.commit()
    db.refresh(db_msg)

    try:
        from app.services.notification_service import build_actor, emit_notification_event

        sender = u
        name = (sender.nickname if sender else None) or (sender.username if sender else None) or f"用户{msg.sender_id}"
        payload = {
            "type": "dm",
            "created_at": db_msg.created_at.timestamp() if getattr(db_msg, "created_at", None) else datetime.datetime.utcnow().timestamp(),
            "peer_id": msg.sender_id,
            "message_id": db_msg.id,
            "actor": build_actor(sender),
            "text": f"{name}: {msg.content}",
        }
        emit_notification_event(db, user_id=int(db_msg.receiver_id), event_type="dm", event_key=f"dm:{db_msg.id}", payload=payload)
    except Exception:
        pass
    return db_msg

@router.get("/list", response_model=List[MessageOut])
def get_messages(
    user_id: int,
    other_id: int,
    since_id: Optional[int] = None,
    limit: Optional[int] = None,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_read_db),
):
    u = get_current_user(authorization=authorization, db=db)
    uid = int(getattr(u, "id", 0) or 0)
    if uid <= 0 or int(user_id) != int(uid):
        raise HTTPException(status_code=403, detail="forbidden")
    # Get conversation between two users
    q = db.query(Message).filter(
        ((Message.sender_id == user_id) & (Message.receiver_id == other_id)) |
        ((Message.sender_id == other_id) & (Message.receiver_id == user_id))
    )
    sid = int(since_id or 0)
    if sid > 0:
        q = q.filter(Message.id > sid)
    lim = int(limit or 200)
    if lim < 1:
        lim = 1
    if lim > 500:
        lim = 500
    if sid > 0:
        return q.order_by(Message.id.asc()).limit(lim).all()
    rows = q.order_by(Message.id.desc()).limit(lim).all()
    rows.reverse()
    return rows

@router.get("/conversations")
def get_conversations(user_id: int, authorization: Optional[str] = Header(None), db: Session = Depends(get_read_db)):
    u = get_current_user(authorization=authorization, db=db)
    uid = int(getattr(u, "id", 0) or 0)
    if uid <= 0 or int(user_id) != int(uid):
        raise HTTPException(status_code=403, detail="forbidden")
    peer_id = case(
        (Message.sender_id == user_id, Message.receiver_id),
        else_=Message.sender_id,
    ).label("peer_id")

    latest = (
        db.query(peer_id, func.max(Message.created_at).label("last_at"))
        .filter(or_(Message.sender_id == user_id, Message.receiver_id == user_id))
        .group_by(peer_id)
        .subquery()
    )

    rows = (
        db.query(User, latest.c.last_at)
        .join(latest, latest.c.peer_id == User.id)
        .order_by(latest.c.last_at.desc(), User.id.desc())
        .all()
    )

    out = []
    for u, _last in rows:
        out.append({
            "id": u.id,
            "username": u.username,
            "nickname": u.nickname,
            "avatar": u.avatar,
            "aiseek_id": u.aiseek_id,
            "last_at": _last.timestamp() if _last else None,
        })
    return out
