from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload
from app.api.deps import get_current_user_optional, get_db, get_read_db
from app.core.config import get_settings
from app.models.all_models import Danmaku, Interaction, Post, User, Follow, Comment, FriendRequest, Message, CommentReaction
from typing import List, Optional
from pydantic import BaseModel
import time

from app.core.cache import cache

router = APIRouter()


def _count_cache_ttl_sec() -> int:
    try:
        s = get_settings()
        ttl = int(getattr(s, "LIST_TOTAL_COUNT_CACHE_TTL_SEC", 15) or 15)
    except Exception:
        ttl = 15
    if ttl < 3:
        ttl = 3
    if ttl > 300:
        ttl = 300
    return ttl


def _set_total_count_cached(response: Response, key: str, builder) -> None:
    try:
        ttl = _count_cache_ttl_sec()
        val = cache.get_or_set_json(str(key), ttl=ttl, builder=lambda: int(builder()), lock_ttl=2)
        response.headers["x-total-count"] = str(max(0, int(val or 0)))
        return
    except Exception:
        pass
    try:
        response.headers["x-total-count"] = str(max(0, int(builder() or 0)))
    except Exception:
        pass

def _norm_media_url(u):
    try:
        if not isinstance(u, str):
            return u
        out = u
        if out.startswith("https://cdn.aiseek.com/") or out.startswith("http://cdn.aiseek.com/"):
            path = out.split("cdn.aiseek.com", 1)[1]
            if path.startswith("/uploads/"):
                out = "/static" + path
        return out
    except Exception:
        return u

class DanmakuCreate(BaseModel):
    post_id: int
    content: str
    timestamp: float
    color: str = "#FFFFFF"
    position: int = 0
    user_id: Optional[int] = None

class DanmakuOut(BaseModel):
    id: int
    content: str
    timestamp: float
    color: str
    position: int
    
    class Config:
        orm_mode = True

@router.get("/danmaku/{post_id}", response_model=List[DanmakuOut])
def get_danmaku(post_id: int, db: Session = Depends(get_read_db)):
    """Get danmaku for a video."""
    return db.query(Danmaku).filter(Danmaku.post_id == post_id).order_by(Danmaku.timestamp).all()

@router.post("/danmaku", response_model=DanmakuOut)
def send_danmaku(dm: DanmakuCreate, current_user: User = Depends(get_current_user_optional), db: Session = Depends(get_db)):
    """Send a danmaku."""
    uid = int(getattr(current_user, "id", 0) or 0) if current_user else int(dm.user_id or 0)
    if uid <= 0:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if current_user and int(dm.user_id or 0) and int(dm.user_id) != int(uid):
        raise HTTPException(status_code=403, detail="forbidden")
    post = db.query(Post).filter(Post.id == dm.post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
        
    db_dm = Danmaku(
        post_id=dm.post_id,
        user_id=uid,
        content=dm.content,
        timestamp=dm.timestamp,
        color=dm.color,
        position=dm.position
    )
    db.add(db_dm)
    db.commit()
    db.refresh(db_dm)
    return db_dm


@router.get("/notifications/{user_id}")
def get_notifications(
    user_id: int,
    response: Response,
    limit: int = 120,
    cursor: Optional[str] = None,
    db: Session = Depends(get_db),
):
    from sqlalchemy import and_, or_
    from app.utils.cursor import decode_cursor, encode_cursor

    lim = int(limit or 120)
    if lim < 1:
        lim = 1
    if lim > 200:
        lim = 200

    cur = decode_cursor(cursor)
    cur_ts = float(cur.get("created_at") or 0) if isinstance(cur, dict) else 0.0
    cur_id = cur.get("id") if isinstance(cur, dict) else None

    try:
        from app.models.all_models import NotificationEvent

        if not cursor:
            try:
                has_any = db.query(NotificationEvent.id).filter(NotificationEvent.user_id == user_id).limit(1).first()
                if not has_any:
                    from app.core.celery_app import apply_async_with_context
                    from app.tasks.notification_backfill import backfill_user_notifications_task

                    apply_async_with_context(
                        backfill_user_notifications_task,
                        args=[int(user_id)],
                        dedupe_key=f"notif_backfill:{int(user_id)}",
                        dedupe_ttl=30,
                        max_queue_depth=10000,
                        drop_when_overloaded=True,
                    )
            except Exception:
                pass

        q = db.query(NotificationEvent).filter(NotificationEvent.user_id == user_id)
        if cur_ts and isinstance(cur_id, int):
            q = q.filter(
                or_(
                    NotificationEvent.created_at_ts < float(cur_ts),
                    and_(NotificationEvent.created_at_ts == float(cur_ts), NotificationEvent.id < int(cur_id)),
                )
            )
        from sqlalchemy import func

        evs = q.order_by(func.coalesce(NotificationEvent.created_at_ts, 0).desc(), NotificationEvent.id.desc()).limit(lim).all()

        parsed = []
        need_post_ids = set()
        for e in evs:
            try:
                raw = e.payload
                if isinstance(raw, str):
                    try:
                        import json

                        raw = json.loads(raw)
                    except Exception:
                        raw = {}
                item = dict(raw or {})
                try:
                    pid = int(item.get("post_id") or 0)
                except Exception:
                    pid = 0
                if pid:
                    cov = item.get("post_cover_url") or ""
                    cov = str(cov) if cov is not None else ""
                    if (not cov) or cov.endswith("/static/img/default_cover.jpg") or (not item.get("post_video_url")):
                        need_post_ids.add(int(pid))
                parsed.append((e, item, int(pid or 0)))
            except Exception:
                continue

        by_post = {}
        if need_post_ids:
            try:
                posts = (
                    db.query(Post)
                    .options(joinedload(Post.active_media_asset))
                    .filter(Post.id.in_(list(need_post_ids)))
                    .all()
                )
                by_post = {int(p.id): p for p in posts if p}
            except Exception:
                by_post = {}

        out = []
        for e, item, pid in parsed:
            try:
                if pid and pid in by_post:
                    p = by_post.get(pid)
                    cov = item.get("post_cover_url") or ""
                    cov = str(cov) if cov is not None else ""
                    if (not cov) or cov.endswith("/static/img/default_cover.jpg"):
                        cu = getattr(p, "cover_url", None)
                        if cu:
                            item["post_cover_url"] = str(cu)
                        else:
                            imgs = getattr(p, "images", None)
                            if isinstance(imgs, list) and imgs and imgs[0]:
                                item["post_cover_url"] = str(imgs[0])
                            else:
                                ama = getattr(p, "active_media_asset", None)
                                acu = getattr(ama, "cover_url", None) if ama else None
                                if acu:
                                    item["post_cover_url"] = str(acu)
                    if not item.get("post_video_url"):
                        vv = getattr(p, "processed_url", None) or getattr(p, "video_url", None)
                        if vv:
                            item["post_video_url"] = str(vv)
                ts = getattr(e, "created_at_ts", None)
                item["created_at"] = float(ts) if ts is not None else (e.created_at.timestamp() if getattr(e, "created_at", None) else time.time())
                try:
                    if item.get("post_cover_url"):
                        item["post_cover_url"] = _norm_media_url(item.get("post_cover_url"))
                    if item.get("post_video_url"):
                        item["post_video_url"] = _norm_media_url(item.get("post_video_url"))
                except Exception:
                    pass
                out.append(item)
            except Exception:
                continue

        if evs:
            last = evs[-1]
            ts = getattr(last, "created_at_ts", None)
            if ts is None and getattr(last, "created_at", None) is not None:
                ts = float(last.created_at.timestamp())
            if ts is not None:
                response.headers["x-next-cursor"] = encode_cursor({"created_at": float(ts), "id": int(last.id)})
        return out
    except Exception:
        response.headers["x-next-cursor"] = ""
        return []


@router.get("/notifications_unread/{user_id}")
def notifications_unread(user_id: int, db: Session = Depends(get_read_db)):
    def _build():
        try:
            from app.models.all_models import NotificationEvent, NotificationRead
            from sqlalchemy import func

            st = db.query(NotificationRead).filter(NotificationRead.user_id == user_id).first()
            last = float(getattr(st, "last_read_ts", 0) or 0)
            q = db.query(func.count(NotificationEvent.id)).filter(
                NotificationEvent.user_id == user_id,
                func.coalesce(NotificationEvent.created_at_ts, 0) > last,
            )
            n = q.scalar() or 0
            return {"user_id": int(user_id), "unread": int(n), "last_read_ts": float(last)}
        except Exception:
            return {"user_id": int(user_id), "unread": 0, "last_read_ts": 0}

    try:
        s = get_settings()
        ttl = int(getattr(s, "NOTIFICATIONS_UNREAD_CACHE_TTL_SEC", 3) or 3)
    except Exception:
        ttl = 3
    if ttl < 1:
        ttl = 1
    if ttl > 30:
        ttl = 30
    try:
        out = cache.get_or_set_json(f"cnt:notifications:unread:{int(user_id)}", ttl=ttl, builder=_build, lock_ttl=1)
        if isinstance(out, dict):
            return out
    except Exception:
        pass
    return _build()


class MarkNotificationsReadIn(BaseModel):
    user_id: int
    last_read_ts: Optional[float] = None


@router.post("/notifications_mark_read")
def notifications_mark_read(payload: MarkNotificationsReadIn, db: Session = Depends(get_db)):
    try:
        from app.models.all_models import NotificationRead

        ts = float(payload.last_read_ts) if payload.last_read_ts is not None else time.time()
        st = db.query(NotificationRead).filter(NotificationRead.user_id == payload.user_id).first()
        if not st:
            st = NotificationRead(user_id=payload.user_id, last_read_ts=ts)
            db.add(st)
        else:
            st.last_read_ts = ts
        db.commit()
        try:
            cache.set_json(
                f"cnt:notifications:unread:{int(payload.user_id)}",
                {"user_id": int(payload.user_id), "unread": 0, "last_read_ts": float(ts)},
                ttl=5,
            )
        except Exception:
            pass
        return {"ok": True, "user_id": payload.user_id, "last_read_ts": float(st.last_read_ts or 0)}
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        return {"ok": False}

class LikeCreate(BaseModel):
    post_id: int
    user_id: Optional[int] = None

@router.post("/like")
def like_post(like: LikeCreate, current_user: User = Depends(get_current_user_optional), db: Session = Depends(get_db)):
    """Like or Unlike a post."""
    uid = int(getattr(current_user, "id", 0) or 0) if current_user else int(like.user_id or 0)
    if uid <= 0:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if current_user and int(like.user_id or 0) and int(like.user_id) != int(uid):
        raise HTTPException(status_code=403, detail="forbidden")
    existing = db.query(Interaction).filter(
        Interaction.post_id == like.post_id,
        Interaction.user_id == uid,
        Interaction.type == "like"
    ).first()
    
    post = db.query(Post).filter(Post.id == like.post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    user = db.query(User).filter(User.id == post.user_id).first()
    
    from app.services.counter_service import record_post_counter_event
    from app.tasks.counters import flush_post_counters
    from app.core.celery_app import apply_async_with_context
    from app.services.hot_counter_service import mark_dirty, shard_for_post, should_schedule_dirty_flush, should_schedule_flush, write_mode

    if existing:
        interaction_id = int(existing.id)
        try:
            db.delete(existing)
            if write_mode() != "redis":
                db.execute(
                    text("UPDATE posts SET likes_count = CASE WHEN COALESCE(likes_count,0) - 1 < 0 THEN 0 ELSE COALESCE(likes_count,0) - 1 END WHERE id=:pid"),
                    {"pid": int(like.post_id)},
                )
                if user:
                    db.execute(
                        text("UPDATE users SET likes_received_count = CASE WHEN COALESCE(likes_received_count,0) - 1 < 0 THEN 0 ELSE COALESCE(likes_received_count,0) - 1 END WHERE id=:uid"),
                        {"uid": int(user.id)},
                    )
            record_post_counter_event(
                db,
                post_id=int(like.post_id),
                counter="likes",
                delta=-1,
                event_key=f"like:-:{interaction_id}",
            )
            try:
                from app.services.hot_counter_service import add_delta, add_hot_rank

                add_delta(int(like.post_id), likes=-1)
                add_hot_rank(int(like.post_id), likes=-1)
            except Exception:
                pass

            if write_mode() == "redis":
                pass
            db.commit()
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
        if should_schedule_flush(int(like.post_id)):
            apply_async_with_context(flush_post_counters, args=[int(like.post_id)], dedupe_key=f"flush_post:{int(like.post_id)}", dedupe_ttl=2, max_queue_depth=50000, drop_when_overloaded=True)
        try:
            shard = shard_for_post(int(like.post_id))
            if mark_dirty(int(like.post_id)) and should_schedule_dirty_flush(shard):
                from app.tasks.dirty_flush import flush_dirty_post_counters

                apply_async_with_context(flush_dirty_post_counters, args=[int(shard)], dedupe_key=f"flush_dirty_shard:{int(shard)}", dedupe_ttl=2, max_queue_depth=20000, drop_when_overloaded=True)
        except Exception:
            pass
        db.refresh(post)
        try:
            cache.bump(f"post:{int(like.post_id)}")
            cache.bump(f"pref:{int(uid)}")
        except Exception:
            pass
        if write_mode() == "redis":
            try:
                from app.services.hot_counter_service import get_delta

                d = get_delta(int(like.post_id))
                return {"status": "unliked", "count": max(0, int(getattr(post, "likes_count", 0) or 0) + int(d.get("likes") or 0))}
            except Exception:
                return {"status": "unliked", "count": int(getattr(post, "likes_count", 0) or 0)}
        return {"status": "unliked", "count": int(getattr(post, "likes_count", 0) or 0)}

    new_like = Interaction(post_id=like.post_id, user_id=uid, type="like")
    try:
        db.add(new_like)
        db.flush()
    except IntegrityError:
        try:
            db.rollback()
        except Exception:
            pass
        return {"status": "liked", "count": int(getattr(post, "likes_count", 0) or 0)}

    try:
        if write_mode() != "redis":
            db.execute(
                text("UPDATE posts SET likes_count = COALESCE(likes_count,0) + 1 WHERE id=:pid"),
                {"pid": int(like.post_id)},
            )
            if user:
                db.execute(
                    text("UPDATE users SET likes_received_count = COALESCE(likes_received_count,0) + 1 WHERE id=:uid"),
                    {"uid": int(user.id)},
                )
        record_post_counter_event(
            db,
            post_id=int(like.post_id),
            counter="likes",
            delta=1,
            event_key=f"like:+:{int(new_like.id)}",
        )
        try:
            from app.services.hot_counter_service import add_delta, add_hot_rank

            add_delta(int(like.post_id), likes=1)
            add_hot_rank(int(like.post_id), likes=1)
        except Exception:
            pass
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
    if should_schedule_flush(int(like.post_id)):
        apply_async_with_context(flush_post_counters, args=[int(like.post_id)], dedupe_key=f"flush_post:{int(like.post_id)}", dedupe_ttl=2, max_queue_depth=50000, drop_when_overloaded=True)
    try:
        shard = shard_for_post(int(like.post_id))
        if mark_dirty(int(like.post_id)) and should_schedule_dirty_flush(shard):
            from app.tasks.dirty_flush import flush_dirty_post_counters

            apply_async_with_context(flush_dirty_post_counters, args=[int(shard)], dedupe_key=f"flush_dirty_shard:{int(shard)}", dedupe_ttl=2, max_queue_depth=20000, drop_when_overloaded=True)
    except Exception:
        pass
    db.refresh(post)
    try:
        cache.bump(f"post:{int(like.post_id)}")
        cache.bump(f"pref:{int(uid)}")
    except Exception:
        pass
    try:
        if int(getattr(post, "user_id", 0) or 0) and int(post.user_id) != int(uid):
            from app.services.notification_service import build_actor, emit_notification_event

            actor = current_user if current_user else db.query(User).filter(User.id == int(uid)).first()
            name = (actor.nickname if actor else None) or (actor.username if actor else None) or f"用户{uid}"
            cover = getattr(post, "cover_url", None) or (post.images[0] if getattr(post, "images", None) else None) or "/static/img/default_cover.jpg"
            payload = {
                "type": "like",
                "created_at": time.time(),
                "post_id": int(like.post_id),
                "post_cover_url": cover,
                "post_title": getattr(post, "title", None),
                "actor": build_actor(actor),
                "text": f"{name} 点赞了你的视频",
            }
            emit_notification_event(db, user_id=int(post.user_id), event_type="like", event_key=f"like:{int(new_like.id)}", payload=payload)
    except Exception:
        pass
    if write_mode() == "redis":
        try:
            from app.services.hot_counter_service import get_delta

            d = get_delta(int(like.post_id))
            return {"status": "liked", "count": max(0, int(getattr(post, "likes_count", 0) or 0) + int(d.get("likes") or 0))}
        except Exception:
            return {"status": "liked", "count": int(getattr(post, "likes_count", 0) or 0)}
    return {"status": "liked", "count": int(getattr(post, "likes_count", 0) or 0)}

class FavoriteCreate(BaseModel):
    post_id: int
    user_id: Optional[int] = None


class RepostCreate(BaseModel):
    post_id: int
    user_id: Optional[int] = None

@router.post("/favorite")
def favorite_post(fav: FavoriteCreate, current_user: User = Depends(get_current_user_optional), db: Session = Depends(get_db)):
    """Favorite or Unfavorite a post."""
    uid = int(getattr(current_user, "id", 0) or 0) if current_user else int(fav.user_id or 0)
    if uid <= 0:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if current_user and int(fav.user_id or 0) and int(fav.user_id) != int(uid):
        raise HTTPException(status_code=403, detail="forbidden")
    post = db.query(Post).filter(Post.id == fav.post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    existing = db.query(Interaction).filter(
        Interaction.post_id == fav.post_id,
        Interaction.user_id == uid,
        Interaction.type == "favorite"
    ).first()
    
    from app.services.counter_service import record_post_counter_event
    from app.tasks.counters import flush_post_counters
    from app.core.celery_app import apply_async_with_context
    from app.services.hot_counter_service import mark_dirty, shard_for_post, should_schedule_dirty_flush, should_schedule_flush, write_mode

    if existing:
        interaction_id = int(existing.id)
        try:
            db.delete(existing)
            if write_mode() != "redis":
                db.execute(
                    text("UPDATE posts SET favorites_count = CASE WHEN COALESCE(favorites_count,0) - 1 < 0 THEN 0 ELSE COALESCE(favorites_count,0) - 1 END WHERE id=:pid"),
                    {"pid": int(fav.post_id)},
                )
            record_post_counter_event(
                db,
                post_id=int(fav.post_id),
                counter="favorites",
                delta=-1,
                event_key=f"favorite:-:{interaction_id}",
            )
            try:
                from app.services.hot_counter_service import add_delta, add_hot_rank

                add_delta(int(fav.post_id), favorites=-1)
                add_hot_rank(int(fav.post_id), favorites=-1)
            except Exception:
                pass
            db.commit()
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
        if should_schedule_flush(int(fav.post_id)):
            apply_async_with_context(flush_post_counters, args=[int(fav.post_id)], dedupe_key=f"flush_post:{int(fav.post_id)}", dedupe_ttl=2, max_queue_depth=50000, drop_when_overloaded=True)
        try:
            shard = shard_for_post(int(fav.post_id))
            if mark_dirty(int(fav.post_id)) and should_schedule_dirty_flush(shard):
                from app.tasks.dirty_flush import flush_dirty_post_counters

                apply_async_with_context(flush_dirty_post_counters, args=[int(shard)], dedupe_key=f"flush_dirty_shard:{int(shard)}", dedupe_ttl=2, max_queue_depth=20000, drop_when_overloaded=True)
        except Exception:
            pass
        db.refresh(post)
        try:
            cache.bump(f"post:{int(fav.post_id)}")
            cache.bump(f"pref:{int(uid)}")
        except Exception:
            pass
        if write_mode() == "redis":
            try:
                from app.services.hot_counter_service import get_delta

                d = get_delta(int(fav.post_id))
                return {"status": "unfavorited", "count": max(0, int(getattr(post, "favorites_count", 0) or 0) + int(d.get("favorites") or 0))}
            except Exception:
                return {"status": "unfavorited", "count": int(getattr(post, "favorites_count", 0) or 0)}
        return {"status": "unfavorited", "count": int(getattr(post, "favorites_count", 0) or 0)}

    new_fav = Interaction(post_id=fav.post_id, user_id=uid, type="favorite")
    try:
        db.add(new_fav)
        db.flush()
    except IntegrityError:
        try:
            db.rollback()
        except Exception:
            pass
        return {"status": "favorited", "count": int(getattr(post, "favorites_count", 0) or 0)}

    try:
        if write_mode() != "redis":
            db.execute(
                text("UPDATE posts SET favorites_count = COALESCE(favorites_count,0) + 1 WHERE id=:pid"),
                {"pid": int(fav.post_id)},
            )
        record_post_counter_event(
            db,
            post_id=int(fav.post_id),
            counter="favorites",
            delta=1,
            event_key=f"favorite:+:{int(new_fav.id)}",
        )
        try:
            from app.services.hot_counter_service import add_delta, add_hot_rank

            add_delta(int(fav.post_id), favorites=1)
            add_hot_rank(int(fav.post_id), favorites=1)
        except Exception:
            pass
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
    if should_schedule_flush(int(fav.post_id)):
        apply_async_with_context(flush_post_counters, args=[int(fav.post_id)], dedupe_key=f"flush_post:{int(fav.post_id)}", dedupe_ttl=2, max_queue_depth=50000, drop_when_overloaded=True)
    try:
        shard = shard_for_post(int(fav.post_id))
        if mark_dirty(int(fav.post_id)) and should_schedule_dirty_flush(shard):
            from app.tasks.dirty_flush import flush_dirty_post_counters

            apply_async_with_context(flush_dirty_post_counters, args=[int(shard)], dedupe_key=f"flush_dirty_shard:{int(shard)}", dedupe_ttl=2, max_queue_depth=20000, drop_when_overloaded=True)
    except Exception:
        pass
    db.refresh(post)
    try:
        cache.bump(f"post:{int(fav.post_id)}")
        cache.bump(f"pref:{int(uid)}")
    except Exception:
        pass
    try:
        if int(getattr(post, "user_id", 0) or 0) and int(post.user_id) != int(uid):
            from app.services.notification_service import build_actor, emit_notification_event

            actor = current_user if current_user else db.query(User).filter(User.id == int(uid)).first()
            name = (actor.nickname if actor else None) or (actor.username if actor else None) or f"用户{uid}"
            cover = getattr(post, "cover_url", None) or (post.images[0] if getattr(post, "images", None) else None) or "/static/img/default_cover.jpg"
            payload = {
                "type": "favorite",
                "created_at": time.time(),
                "post_id": int(fav.post_id),
                "post_cover_url": cover,
                "post_title": getattr(post, "title", None),
                "actor": build_actor(actor),
                "text": f"{name} 收藏了你的视频",
            }
            emit_notification_event(db, user_id=int(post.user_id), event_type="favorite", event_key=f"favorite:{int(new_fav.id)}", payload=payload)
    except Exception:
        pass
    if write_mode() == "redis":
        try:
            from app.services.hot_counter_service import get_delta

            d = get_delta(int(fav.post_id))
            return {"status": "favorited", "count": max(0, int(getattr(post, "favorites_count", 0) or 0) + int(d.get("favorites") or 0))}
        except Exception:
            return {"status": "favorited", "count": int(getattr(post, "favorites_count", 0) or 0)}
    return {"status": "favorited", "count": int(getattr(post, "favorites_count", 0) or 0)}


@router.post("/repost")
def repost_post(payload: RepostCreate, current_user: User = Depends(get_current_user_optional), db: Session = Depends(get_db)):
    uid = int(getattr(current_user, "id", 0) or 0) if current_user else int(payload.user_id or 0)
    if uid <= 0:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if current_user and int(payload.user_id or 0) and int(payload.user_id) != int(uid):
        raise HTTPException(status_code=403, detail="forbidden")
    post = db.query(Post).filter(Post.id == payload.post_id).first()
    if not post or getattr(post, "status", "done") != "done":
        raise HTTPException(status_code=404, detail="Post not found")

    existing = (
        db.query(Interaction)
        .filter(
            Interaction.post_id == payload.post_id,
            Interaction.user_id == uid,
            Interaction.type == "repost",
        )
        .first()
    )
    if existing:
        try:
            try:
                db.execute(
                    text(
                        "UPDATE posts SET shares_count = CASE WHEN COALESCE(shares_count,0) > 0 THEN COALESCE(shares_count,0) - 1 ELSE 0 END WHERE id=:pid"
                    ),
                    {"pid": int(payload.post_id)},
                )
            except Exception:
                pass
            db.delete(existing)
            db.commit()
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
            return {"status": "unreposted", "count": int(getattr(post, "shares_count", 0) or 0)}

        try:
            from app.services.hot_counter_service import add_hot_rank

            add_hot_rank(int(payload.post_id), shares=-1, user_id=int(uid))
        except Exception:
            pass

        try:
            cache.bump(f"post:{int(payload.post_id)}")
            cache.bump(f"pref:{int(uid)}")
        except Exception:
            pass
        try:
            post2 = db.query(Post).filter(Post.id == payload.post_id).first()
            c = int(getattr(post2, "shares_count", 0) or 0) if post2 else 0
        except Exception:
            c = 0
        return {"status": "unreposted", "count": int(c)}

    new_it = Interaction(post_id=payload.post_id, user_id=int(uid), type="repost")
    db.add(new_it)
    try:
        try:
            db.execute(
                text("UPDATE posts SET shares_count = COALESCE(shares_count,0) + 1 WHERE id=:pid"),
                {"pid": int(payload.post_id)},
            )
        except Exception:
            pass
        db.commit()
        db.refresh(new_it)
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        return {"status": "reposted", "count": int(getattr(post, "shares_count", 0) or 0)}

    try:
        from app.services.hot_counter_service import add_hot_rank

        add_hot_rank(int(payload.post_id), shares=1, user_id=int(uid))
    except Exception:
        pass

    try:
        cache.bump(f"post:{int(payload.post_id)}")
        cache.bump(f"pref:{int(uid)}")
    except Exception:
        pass

    try:
        if int(getattr(post, "user_id", 0) or 0) and int(post.user_id) != int(uid):
            from app.services.notification_service import build_actor, emit_notification_event

            actor = current_user if current_user else db.query(User).filter(User.id == int(uid)).first()
            name = (actor.nickname if actor else None) or (actor.username if actor else None) or f"用户{uid}"
            cover = getattr(post, "cover_url", None) or (post.images[0] if getattr(post, "images", None) else None) or "/static/img/default_cover.jpg"
            payload2 = {
                "type": "repost",
                "created_at": time.time(),
                "post_id": int(payload.post_id),
                "post_cover_url": cover,
                "post_title": getattr(post, "title", None),
                "actor": build_actor(actor),
                "text": f"{name} 转发了你的视频",
            }
            emit_notification_event(db, user_id=int(post.user_id), event_type="repost", event_key=f"repost:{int(new_it.id)}", payload=payload2)
    except Exception:
        pass

    try:
        post2 = db.query(Post).filter(Post.id == payload.post_id).first()
        c = int(getattr(post2, "shares_count", 0) or 0) if post2 else 0
    except Exception:
        c = 0
    return {"status": "reposted", "count": int(c)}

@router.get("/favorites/{user_id}")
def get_favorites(
    user_id: int,
    response: Response,
    limit: Optional[int] = None,
    cursor: Optional[str] = None,
    db: Session = Depends(get_read_db),
):
    from sqlalchemy import and_, or_
    from sqlalchemy.orm import joinedload

    from app.services.post_presenter import decorate_flags, serialize_posts_base
    from app.utils.cursor import decode_cursor, encode_cursor, cursor_datetime

    base_query = db.query(Interaction).filter(Interaction.user_id == user_id, Interaction.type == "favorite")
    if not cursor:
        _set_total_count_cached(response, f"cnt:favorites:{int(user_id)}", lambda: base_query.count())

    cur = decode_cursor(cursor)
    cur_dt = cursor_datetime(cur, "created_at")
    cur_id = cur.get("id") if isinstance(cur, dict) else None
    q = base_query
    if cur_dt is not None and isinstance(cur_id, int):
        q = q.filter(or_(Interaction.created_at < cur_dt, and_(Interaction.created_at == cur_dt, Interaction.id < cur_id)))

    lim = int(limit or 80)
    if lim < 1:
        lim = 1
    if lim > 200:
        lim = 200

    rows = q.order_by(Interaction.created_at.desc(), Interaction.id.desc()).limit(lim).all()
    if rows:
        last = rows[-1]
        if getattr(last, "created_at", None) is not None:
            response.headers["x-next-cursor"] = encode_cursor({"created_at": float(last.created_at.timestamp()), "id": int(last.id)})

    seen = set()
    ids = []
    for r in rows:
        pid = int(getattr(r, "post_id", 0) or 0)
        if not pid or pid in seen:
            continue
        seen.add(pid)
        ids.append(pid)

    if not ids:
        return []

    posts = db.query(Post).options(joinedload(Post.owner), joinedload(Post.active_media_asset)).filter(Post.id.in_(ids), Post.status == "done").all()
    by_id = {int(p.id): p for p in posts if p}
    items = serialize_posts_base([by_id[i] for i in ids if i in by_id])
    return decorate_flags(items, user_id, db)

@router.get("/likes/{user_id}")
def get_likes(
    user_id: int,
    response: Response,
    limit: Optional[int] = None,
    cursor: Optional[str] = None,
    db: Session = Depends(get_read_db),
):
    from sqlalchemy import and_, or_
    from sqlalchemy.orm import joinedload

    from app.services.post_presenter import decorate_flags, serialize_posts_base
    from app.utils.cursor import decode_cursor, encode_cursor, cursor_datetime

    base_query = db.query(Interaction).filter(Interaction.user_id == user_id, Interaction.type == "like")
    if not cursor:
        _set_total_count_cached(response, f"cnt:likes:{int(user_id)}", lambda: base_query.count())

    cur = decode_cursor(cursor)
    cur_dt = cursor_datetime(cur, "created_at")
    cur_id = cur.get("id") if isinstance(cur, dict) else None
    q = base_query
    if cur_dt is not None and isinstance(cur_id, int):
        q = q.filter(or_(Interaction.created_at < cur_dt, and_(Interaction.created_at == cur_dt, Interaction.id < cur_id)))

    lim = int(limit or 80)
    if lim < 1:
        lim = 1
    if lim > 200:
        lim = 200

    rows = q.order_by(Interaction.created_at.desc(), Interaction.id.desc()).limit(lim).all()
    if rows:
        last = rows[-1]
        if getattr(last, "created_at", None) is not None:
            response.headers["x-next-cursor"] = encode_cursor({"created_at": float(last.created_at.timestamp()), "id": int(last.id)})

    seen = set()
    ids = []
    for r in rows:
        pid = int(getattr(r, "post_id", 0) or 0)
        if not pid or pid in seen:
            continue
        seen.add(pid)
        ids.append(pid)

    if not ids:
        return []

    posts = db.query(Post).options(joinedload(Post.owner), joinedload(Post.active_media_asset)).filter(Post.id.in_(ids), Post.status == "done").all()
    by_id = {int(p.id): p for p in posts if p}
    items = serialize_posts_base([by_id[i] for i in ids if i in by_id])
    return decorate_flags(items, user_id, db)


class HistoryCreate(BaseModel):
    post_id: int
    user_id: Optional[int] = None
    watch_time_sec: Optional[float] = None
    duration_sec: Optional[float] = None
    completed: Optional[bool] = None
    dwell_ms: Optional[int] = None


@router.post("/history")
def add_history(payload: HistoryCreate, current_user: User = Depends(get_current_user_optional), db: Session = Depends(get_db)):
    uid = int(getattr(current_user, "id", 0) or 0) if current_user else int(payload.user_id or 0)
    if uid <= 0:
        raise HTTPException(status_code=401, detail="Not authenticated")
    post = db.query(Post).filter(Post.id == payload.post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    existing = db.query(Interaction).filter(
        Interaction.user_id == uid,
        Interaction.post_id == payload.post_id,
        Interaction.type == "view",
    ).first()
    should_inc_views = False
    if existing:
        try:
            old = getattr(existing, "created_at", None)
            if old is not None:
                import datetime

                now = datetime.datetime.utcnow().replace(tzinfo=getattr(old, "tzinfo", None))
                dt = old
                if hasattr(dt, "tzinfo") and dt.tzinfo is None:
                    dt = dt.replace(tzinfo=now.tzinfo)
                if hasattr(now, "tzinfo") and now.tzinfo is None:
                    now = now.replace(tzinfo=dt.tzinfo)
                if hasattr(dt, "__sub__"):
                    if (now - dt).total_seconds() >= 600:
                        should_inc_views = True
        except Exception:
            pass
        try:
            from sqlalchemy import func

            existing.created_at = func.now()
            db.commit()
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
    else:
        try:
            db.add(Interaction(user_id=uid, post_id=payload.post_id, type="view"))
            db.commit()
            should_inc_views = True
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
            raise
    if should_inc_views:
        try:
            from app.tasks.counters import flush_post_counters
            from app.core.celery_app import apply_async_with_context
            from app.services.hot_counter_service import add_delta, mark_dirty, shard_for_post, should_schedule_dirty_flush, should_schedule_flush

            add_delta(int(payload.post_id), views=1)
            if should_schedule_flush(int(payload.post_id)):
                apply_async_with_context(flush_post_counters, args=[int(payload.post_id)], dedupe_key=f"flush_post:{int(payload.post_id)}", dedupe_ttl=2, max_queue_depth=50000, drop_when_overloaded=True)
            try:
                shard = shard_for_post(int(payload.post_id))
                if mark_dirty(int(payload.post_id)) and should_schedule_dirty_flush(shard):
                    from app.tasks.dirty_flush import flush_dirty_post_counters

                    apply_async_with_context(flush_dirty_post_counters, args=[int(shard)], dedupe_key=f"flush_dirty_shard:{int(shard)}", dedupe_ttl=2, max_queue_depth=20000, drop_when_overloaded=True)
            except Exception:
                pass
        except Exception:
            pass
    try:
        from app.services.hot_counter_service import add_hot_rank, compute_view_points

        pts = compute_view_points(
            watch_time_sec=payload.watch_time_sec,
            duration_sec=payload.duration_sec,
            completed=bool(payload.completed) if payload.completed is not None else False,
            dwell_ms=payload.dwell_ms,
        )
        if pts > 0:
            add_hot_rank(int(payload.post_id), views=float(pts), user_id=int(uid))
    except Exception:
        pass
    return {"status": "ok"}


class WatchCreate(BaseModel):
    post_id: int
    user_id: Optional[int] = None
    watch_time_sec: Optional[float] = None
    duration_sec: Optional[float] = None
    completed: Optional[bool] = None
    dwell_ms: Optional[int] = None


@router.post("/watch")
def watch_event(payload: WatchCreate, current_user: User = Depends(get_current_user_optional), db: Session = Depends(get_db)):
    uid = int(getattr(current_user, "id", 0) or 0) if current_user else int(payload.user_id or 0)
    if uid <= 0:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        from app.services.hot_counter_service import add_hot_rank, compute_view_points

        pts = compute_view_points(
            watch_time_sec=payload.watch_time_sec,
            duration_sec=payload.duration_sec,
            completed=bool(payload.completed) if payload.completed is not None else False,
            dwell_ms=payload.dwell_ms,
        )
        if pts > 0:
            add_hot_rank(int(payload.post_id), views=float(pts), user_id=int(uid))
    except Exception:
        pass
    return {"status": "ok"}


@router.get("/history/{user_id}")
def get_history(
    user_id: int,
    response: Response,
    limit: Optional[int] = None,
    cursor: Optional[str] = None,
    db: Session = Depends(get_read_db),
):
    from sqlalchemy import and_, or_
    from sqlalchemy.orm import joinedload
    from app.services.post_presenter import decorate_flags, serialize_posts_base
    from app.utils.cursor import decode_cursor, encode_cursor, cursor_datetime

    base_query = db.query(Interaction).filter(
        Interaction.user_id == user_id,
        Interaction.type == "view",
    )
    if not cursor:
        _set_total_count_cached(response, f"cnt:history:{int(user_id)}", lambda: base_query.count())

    cur = decode_cursor(cursor)
    cur_dt = cursor_datetime(cur, "created_at")
    cur_id = cur.get("id") if isinstance(cur, dict) else None
    q = base_query
    if cur_dt is not None and isinstance(cur_id, int):
        q = q.filter(or_(Interaction.created_at < cur_dt, and_(Interaction.created_at == cur_dt, Interaction.id < cur_id)))

    lim = int(limit or 80)
    if lim < 1:
        lim = 1
    if lim > 200:
        lim = 200

    row_lim = lim * 3
    if row_lim > 600:
        row_lim = 600

    rows = q.order_by(Interaction.created_at.desc(), Interaction.id.desc()).limit(row_lim).all()
    if rows:
        last = rows[-1]
        if getattr(last, "created_at", None) is not None:
            response.headers["x-next-cursor"] = encode_cursor({"created_at": float(last.created_at.timestamp()), "id": int(last.id)})

    seen = set()
    ids = []
    for r in rows:
        pid = int(getattr(r, "post_id", 0) or 0)
        if not pid or pid in seen:
            continue
        seen.add(pid)
        ids.append(pid)
        if len(ids) >= lim:
            break
    if not ids:
        return []
    posts = (
        db.query(Post)
        .options(joinedload(Post.owner), joinedload(Post.active_media_asset))
        .filter(Post.id.in_(ids), Post.status == "done")
        .all()
    )
    by_id = {int(p.id): p for p in posts if p}
    out = serialize_posts_base([by_id[i] for i in ids if i in by_id])
    return decorate_flags(out, user_id, db)

class CommentCreate(BaseModel):
    post_id: int
    user_id: Optional[int] = None
    content: str
    parent_id: Optional[int] = None

class CommentOut(BaseModel):
    id: int
    content: str
    user_id: int
    user_nickname: Optional[str]
    user_avatar: Optional[str]
    location: Optional[str] = None
    parent_id: Optional[int] = None
    reply_to_nickname: Optional[str] = None
    created_at: float # Timestamp
    likes_count: int = 0
    dislikes_count: int = 0

class CommentReactIn(BaseModel):
    comment_id: int
    user_id: int
    reaction: str  # like | dislike

@router.get("/comments/{post_id}", response_model=List[CommentOut])
def get_comments(
    post_id: int,
    response: Response,
    limit: Optional[int] = None,
    cursor: Optional[str] = None,
    db: Session = Depends(get_read_db),
):
    from sqlalchemy import and_, or_
    from sqlalchemy import func

    from app.utils.cursor import decode_cursor, encode_cursor, cursor_datetime

    base_query = db.query(Comment).filter(Comment.post_id == post_id)
    query = base_query
    cur = decode_cursor(cursor)
    cur_dt = cursor_datetime(cur, "created_at")
    cur_id = cur.get("id") if isinstance(cur, dict) else None
    if cur_dt is not None and isinstance(cur_id, int):
        query = query.filter(or_(Comment.created_at < cur_dt, and_(Comment.created_at == cur_dt, Comment.id < cur_id)))

    if not cursor:
        _set_total_count_cached(response, f"cnt:comments:{int(post_id)}", lambda: base_query.count())

    ordered = query.options(joinedload(Comment.author)).order_by(Comment.created_at.desc(), Comment.id.desc())
    if limit is None and not cursor:
        comments = ordered.all()
    else:
        lim = int(limit or 80)
        if lim < 1:
            lim = 1
        if lim > 200:
            lim = 200
        comments = ordered.limit(lim).all()
    
    res = []
    comment_ids = [int(getattr(c, "id", 0) or 0) for c in comments if c]
    parent_ids = [int(getattr(c, "parent_id", 0) or 0) for c in comments if getattr(c, "parent_id", None)]
    likes_map = {}
    dislikes_map = {}
    if comment_ids:
        try:
            rr = (
                db.query(CommentReaction.comment_id, CommentReaction.reaction, func.count(CommentReaction.id))
                .filter(CommentReaction.comment_id.in_(comment_ids), CommentReaction.reaction.in_(["like", "dislike"]))
                .group_by(CommentReaction.comment_id, CommentReaction.reaction)
                .all()
            )
            for cid, rt, cnt in rr:
                if str(rt) == "like":
                    likes_map[int(cid)] = int(cnt or 0)
                elif str(rt) == "dislike":
                    dislikes_map[int(cid)] = int(cnt or 0)
        except Exception:
            pass
    parent_name_map = {}
    if parent_ids:
        try:
            pr = (
                db.query(Comment.id, User.nickname, User.username)
                .outerjoin(User, User.id == Comment.user_id)
                .filter(Comment.id.in_(list(set(parent_ids))))
                .all()
            )
            for pid, nn, un in pr:
                parent_name_map[int(pid)] = str(nn or un or "")
        except Exception:
            pass
    for c in comments:
        reply_to_nickname = None
        if c.parent_id:
            reply_to_nickname = parent_name_map.get(int(c.parent_id), None)

        likes_count = int(likes_map.get(int(c.id), 0))
        dislikes_count = int(dislikes_map.get(int(c.id), 0))

        location = None
        if c.author and getattr(c.author, "location", None):
            location = c.author.location
        created_ts = time.time()
        try:
            if c.created_at:
                from datetime import timezone

                dt = c.created_at
                if getattr(dt, "tzinfo", None) is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                created_ts = float(dt.astimezone(timezone.utc).timestamp())
        except Exception:
            created_ts = c.created_at.timestamp() if c.created_at else time.time()
        res.append({
            "id": c.id,
            "content": c.content,
            "user_id": c.user_id,
            "user_nickname": c.author.nickname if c.author else "User",
            "user_avatar": c.author.avatar if c.author else None,
            "location": location,
            "parent_id": c.parent_id,
            "reply_to_nickname": reply_to_nickname,
            "created_at": created_ts,
            "likes_count": likes_count,
            "dislikes_count": dislikes_count,
        })
    if comments:
        last = comments[-1]
        if getattr(last, "created_at", None) is not None:
            last_ts = float(last.created_at.timestamp())
            try:
                from datetime import timezone

                dt2 = last.created_at
                if getattr(dt2, "tzinfo", None) is None:
                    dt2 = dt2.replace(tzinfo=timezone.utc)
                last_ts = float(dt2.astimezone(timezone.utc).timestamp())
            except Exception:
                last_ts = float(last.created_at.timestamp())
            response.headers["x-next-cursor"] = encode_cursor({
                "created_at": last_ts,
                "id": int(last.id),
            })
    return res

@router.post("/comment")
def post_comment(comment: CommentCreate, current_user: User = Depends(get_current_user_optional), db: Session = Depends(get_db)):
    uid = int(getattr(current_user, "id", 0) or 0) if current_user else int(comment.user_id or 0)
    if uid <= 0:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if current_user and int(comment.user_id or 0) and int(comment.user_id) != int(uid):
        raise HTTPException(status_code=403, detail="forbidden")
    post = db.query(Post).filter(Post.id == comment.post_id).first()
    if not post: raise HTTPException(status_code=404)
    
    c = Comment(post_id=comment.post_id, user_id=uid, content=comment.content, parent_id=comment.parent_id)
    db.add(c)
    from app.services.counter_service import record_post_counter_event
    from app.tasks.counters import flush_post_counters
    from app.core.celery_app import apply_async_with_context
    from app.services.hot_counter_service import mark_dirty, shard_for_post, should_schedule_dirty_flush, should_schedule_flush, write_mode

    try:
        db.flush()
        if write_mode() != "redis":
            db.execute(
                text("UPDATE posts SET comments_count = COALESCE(comments_count,0) + 1 WHERE id=:pid"),
                {"pid": int(comment.post_id)},
            )
        record_post_counter_event(db, post_id=int(comment.post_id), counter="comments", delta=1, event_key=f"comment:+:{int(c.id)}")
        try:
            from app.services.hot_counter_service import add_delta, add_hot_rank

            add_delta(int(comment.post_id), comments=1)
            add_hot_rank(int(comment.post_id), comments=1, user_id=int(uid))
        except Exception:
            pass
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        raise

    try:
        if should_schedule_flush(int(comment.post_id)):
            apply_async_with_context(flush_post_counters, args=[int(comment.post_id)], dedupe_key=f"flush_post:{int(comment.post_id)}", dedupe_ttl=2, max_queue_depth=50000, drop_when_overloaded=True)
    except Exception:
        pass

    try:
        shard = shard_for_post(int(comment.post_id))
        if mark_dirty(int(comment.post_id)) and should_schedule_dirty_flush(shard):
            from app.tasks.dirty_flush import flush_dirty_post_counters

            apply_async_with_context(flush_dirty_post_counters, args=[int(shard)], dedupe_key=f"flush_dirty_shard:{int(shard)}", dedupe_ttl=2, max_queue_depth=20000, drop_when_overloaded=True)
    except Exception:
        pass

    try:
        cache.bump(f"post:{int(comment.post_id)}")
    except Exception:
        pass

    try:
        if int(post.user_id) != int(uid):
            from app.services.notification_service import build_actor, emit_notification_event

            actor = current_user if current_user else db.query(User).filter(User.id == int(uid)).first()
            name = (actor.nickname if actor else None) or (actor.username if actor else None) or f"用户{uid}"
            cover = getattr(post, "cover_url", None) or (post.images[0] if getattr(post, "images", None) else None) or "/static/img/default_cover.jpg"
            payload = {
                "type": "comment",
                "created_at": c.created_at.timestamp() if getattr(c, "created_at", None) else time.time(),
                "post_id": comment.post_id,
                "post_cover_url": cover,
                "post_title": getattr(post, "title", None),
                "comment_id": c.id,
                "content": comment.content,
                "actor": build_actor(actor),
                "text": f"{name} 评论了你的视频",
            }
            emit_notification_event(db, user_id=int(post.user_id), event_type="comment", event_key=f"comment:{c.id}", payload=payload)
    except Exception:
        pass
    return {"status": "ok"}


@router.post("/comment/react")
def react_comment(payload: CommentReactIn, current_user: User = Depends(get_current_user_optional), db: Session = Depends(get_db)):
    uid = int(getattr(current_user, "id", 0) or 0) if current_user else int(payload.user_id or 0)
    if uid <= 0:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if current_user and int(payload.user_id or 0) and int(payload.user_id) != int(uid):
        raise HTTPException(status_code=403, detail="forbidden")
    reaction = (payload.reaction or "").strip().lower()
    if reaction not in {"like", "dislike"}:
        raise HTTPException(status_code=400, detail="Invalid reaction")

    comment = db.query(Comment).filter(Comment.id == payload.comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    existing = db.query(CommentReaction).filter(
        CommentReaction.comment_id == payload.comment_id,
        CommentReaction.user_id == uid,
    ).first()

    if existing and existing.reaction == reaction:
        db.delete(existing)
    elif existing:
        existing.reaction = reaction
    else:
        db.add(CommentReaction(user_id=uid, comment_id=payload.comment_id, reaction=reaction))

    db.commit()

    from sqlalchemy import func

    likes_count = 0
    dislikes_count = 0
    try:
        rows = (
            db.query(CommentReaction.reaction, func.count(CommentReaction.id))
            .filter(CommentReaction.comment_id == payload.comment_id, CommentReaction.reaction.in_(["like", "dislike"]))
            .group_by(CommentReaction.reaction)
            .all()
        )
        for rt, cnt in rows:
            if str(rt) == "like":
                likes_count = int(cnt or 0)
            elif str(rt) == "dislike":
                dislikes_count = int(cnt or 0)
    except Exception:
        pass

    return {"status": "ok", "likes_count": likes_count, "dislikes_count": dislikes_count}
