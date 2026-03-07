import json
import time
from typing import Any, Dict, List

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.cache import cache
from app.models.all_models import Comment, Follow, FriendRequest, Message, Post, User, Interaction, NotificationEvent


def emit_notification_event(
    db: Session,
    *,
    user_id: int,
    event_type: str,
    event_key: str,
    payload: Dict[str, Any],
) -> bool:
    if not user_id or not event_type or not event_key:
        return False
    try:
        ts = float(payload.get("created_at") or now_ts())
        ev = NotificationEvent(
            user_id=int(user_id),
            event_type=str(event_type),
            event_key=str(event_key),
            payload=payload,
            created_at_ts=ts,
        )
        db.add(ev)
        db.commit()
        try:
            cache.delete(f"cnt:notifications:unread:{int(user_id)}")
        except Exception:
            pass
        return True
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        return False


def emit_notification_event_ignore(
    db: Session,
    *,
    user_id: int,
    event_type: str,
    event_key: str,
    payload: Dict[str, Any],
    created_at_ts: float,
) -> bool:
    dialect = getattr(getattr(db, "bind", None), "dialect", None)
    name = getattr(dialect, "name", "") or ""
    try:
        created_at = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(created_at_ts))
        if name == "sqlite":
            db.execute(
                text(
                    "INSERT OR IGNORE INTO notification_events(user_id,event_type,event_key,payload,created_at,created_at_ts) "
                    "VALUES (:user_id,:event_type,:event_key,:payload,:created_at,:created_at_ts)"
                ),
                {
                    "user_id": int(user_id),
                    "event_type": str(event_type),
                    "event_key": str(event_key),
                    "payload": json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                    "created_at": created_at,
                    "created_at_ts": float(created_at_ts),
                },
            )
            return True
    except Exception:
        return False
    return False


def build_actor(user) -> Dict[str, Any]:
    if not user:
        return {"id": None, "nickname": None, "avatar": None, "aiseek_id": None}
    return {
        "id": user.id,
        "nickname": user.nickname or user.username,
        "avatar": getattr(user, "avatar", None),
        "aiseek_id": getattr(user, "aiseek_id", None),
    }


def now_ts() -> float:
    return float(time.time())


def _post_cover_url(post: Post) -> str:
    if not post:
        return ""
    try:
        cu = getattr(post, "cover_url", None)
        if cu:
            return str(cu)
        imgs = getattr(post, "images", None)
        if isinstance(imgs, list) and imgs and imgs[0]:
            return str(imgs[0])
        ama = getattr(post, "active_media_asset", None)
        acu = getattr(ama, "cover_url", None) if ama else None
        if acu:
            return str(acu)
    except Exception:
        pass
    return ""


def _post_video_url(post: Post) -> str:
    if not post:
        return ""
    try:
        v = getattr(post, "processed_url", None) or getattr(post, "video_url", None)
        return str(v) if v else ""
    except Exception:
        return ""


def backfill_user_notifications(db: Session, user_id: int, max_items: int = 400) -> int:
    items: List[Dict[str, Any]] = []

    reqs = (
        db.query(FriendRequest)
        .filter(FriendRequest.receiver_id == user_id)
        .order_by(FriendRequest.created_at.desc())
        .limit(120)
        .all()
    )
    for r in reqs:
        sender = db.query(User).filter(User.id == r.sender_id).first()
        sender_name = (sender.nickname if sender else None) or (sender.username if sender else None) or f"用户{r.sender_id}"
        ts = r.created_at.timestamp() if r.created_at else now_ts()
        items.append(
            {
                "type": "friend_request",
                "ts": ts,
                "key": f"friend_request:{r.id}",
                "payload": {
                    "type": "friend_request",
                    "created_at": ts,
                    "request_id": r.id,
                    "status": r.status,
                    "actor": build_actor(sender),
                    "text": f"{sender_name} 请求添加你为好友",
                },
            }
        )

    follows = (
        db.query(Follow)
        .filter(Follow.following_id == user_id)
        .order_by(Follow.created_at.desc())
        .limit(160)
        .all()
    )
    for f in follows:
        u = db.query(User).filter(User.id == f.follower_id).first()
        name = (u.nickname if u else None) or (u.username if u else None) or f"用户{f.follower_id}"
        ts = f.created_at.timestamp() if f.created_at else now_ts()
        items.append(
            {
                "type": "follow",
                "ts": ts,
                "key": f"follow:{f.follower_id}:{user_id}:{int(ts*1000)}",
                "payload": {
                    "type": "follow",
                    "created_at": ts,
                    "actor": build_actor(u),
                    "text": f"{name} 关注了你",
                },
            }
        )

    comments = (
        db.query(Comment)
        .join(Post, Comment.post_id == Post.id)
        .filter(Post.user_id == user_id)
        .order_by(Comment.created_at.desc())
        .limit(200)
        .all()
    )
    for c in comments:
        if c.user_id == user_id:
            continue
        name = (c.author.nickname if c.author else None) or (c.author.username if c.author else None) or f"用户{c.user_id}"
        try:
            p = db.query(Post).filter(Post.id == c.post_id).first()
            cover = _post_cover_url(p)
            ptitle = getattr(p, "title", None) if p else None
        except Exception:
            cover = None
            ptitle = None
        ts = c.created_at.timestamp() if c.created_at else now_ts()
        items.append(
            {
                "type": "comment",
                "ts": ts,
                "key": f"comment:{c.id}",
                "payload": {
                    "type": "comment",
                    "created_at": ts,
                    "post_id": c.post_id,
                    "post_cover_url": cover,
                    "post_video_url": _post_video_url(p),
                    "post_title": ptitle,
                    "comment_id": c.id,
                    "content": c.content,
                    "actor": build_actor(c.author),
                    "text": f"{name} 评论了你的视频",
                },
            }
        )

    interactions = (
        db.query(Interaction)
        .join(Post, Interaction.post_id == Post.id)
        .filter(
            Post.user_id == user_id,
            Interaction.user_id != user_id,
            Interaction.type.in_(["like", "favorite", "repost"]),
        )
        .order_by(Interaction.created_at.desc())
        .limit(260)
        .all()
    )
    for it in interactions:
        try:
            p = db.query(Post).filter(Post.id == it.post_id).first()
            cover = _post_cover_url(p)
            ptitle = getattr(p, "title", None) if p else None
        except Exception:
            cover = None
            ptitle = None
        actor = db.query(User).filter(User.id == it.user_id).first()
        name = (actor.nickname if actor else None) or (actor.username if actor else None) or f"用户{it.user_id}"
        ts = it.created_at.timestamp() if getattr(it, "created_at", None) else now_ts()
        t = (it.type or "").strip().lower()
        if t == "like":
            txt = f"{name} 点赞了你的视频"
        elif t == "favorite":
            txt = f"{name} 收藏了你的视频"
        else:
            txt = f"{name} 转发了你的视频"
        items.append(
            {
                "type": t,
                "ts": ts,
                "key": f"{t}:{int(getattr(it,'id',0) or 0)}",
                "payload": {
                    "type": t,
                    "created_at": ts,
                    "post_id": int(it.post_id),
                    "post_cover_url": cover,
                    "post_video_url": _post_video_url(p),
                    "post_title": ptitle,
                    "actor": build_actor(actor),
                    "text": txt,
                },
            }
        )

    msgs = (
        db.query(Message)
        .filter(Message.receiver_id == user_id)
        .order_by(Message.created_at.desc())
        .limit(200)
        .all()
    )
    for m in msgs:
        sender = db.query(User).filter(User.id == m.sender_id).first()
        name = (sender.nickname if sender else None) or (sender.username if sender else None) or f"用户{m.sender_id}"
        ts = m.created_at.timestamp() if m.created_at else now_ts()
        items.append(
            {
                "type": "dm",
                "ts": ts,
                "key": f"dm:{m.id}",
                "payload": {
                    "type": "dm",
                    "created_at": ts,
                    "peer_id": m.sender_id,
                    "message_id": m.id,
                    "actor": build_actor(sender),
                    "text": f"{name}: {m.content}",
                },
            }
        )

    items.sort(key=lambda x: (float(x.get("ts") or 0), str(x.get("key") or "")), reverse=True)
    items = items[: int(max_items or 400)]

    ok = 0
    for it in items:
        if emit_notification_event_ignore(
            db,
            user_id=user_id,
            event_type=str(it.get("type")),
            event_key=str(it.get("key")),
            payload=it.get("payload") or {},
            created_at_ts=float(it.get("ts") or now_ts()),
        ):
            ok += 1
    try:
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
    return ok
