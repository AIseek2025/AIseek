from __future__ import annotations

from dataclasses import dataclass
import hashlib
import time
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session, joinedload

from app.core.cache import cache
from app.core.config import get_settings
from app.models.all_models import Interaction, Post
from app.services.feed_recall import get_runtime_kind, recall_candidates
from app.services.ab_service import get_variant
from app.services.post_presenter import decorate_flags, serialize_post_base, serialize_posts_base
from app.utils.cursor import decode_cursor, encode_cursor, cursor_datetime


@dataclass
class FeedResult:
    items: List[dict]
    next_cursor: str = ""
    ab_variant: str = ""


def _limit(limit: int) -> int:
    s = get_settings()
    max_lim = int(getattr(s, "FEED_PAGE_MAX_LIMIT", 50) or 50)
    if max_lim < 1:
        max_lim = 1
    if max_lim > 200:
        max_lim = 200
    if max_lim < 10:
        max_lim = 10
    if limit < 1:
        return 1
    if limit > max_lim:
        return max_lim
    return int(limit)


def _serialize_post_base(post: Post, db: Session) -> dict:
    return serialize_post_base(post)


def _serialize_posts_base(posts: List[Post], db: Session) -> List[dict]:
    return serialize_posts_base(posts)


def _get_liked_categories(db: Session, user_id: int, ab_variant: Optional[str]) -> List[str]:
    s = get_settings()
    ttl = int(getattr(s, "FEED_PREF_TTL_SEC", 60) or 60)
    if ttl < 1:
        ttl = 1
    if ttl > 3600:
        ttl = 3600
    pref_v = cache.version(f"pref:{int(user_id)}")
    pref_key = f"feedpref:v{pref_v}:u{int(user_id)}:ab{ab_variant or ''}"

    def _build_pref():
        q = db.query(Post.category).join(Interaction).filter(Interaction.user_id == user_id)
        if ab_variant == "B":
            q = q.filter(Interaction.type.in_(["like", "favorite"]))
        else:
            q = q.filter(Interaction.type == "like")
        liked_categories = q.distinct().all()
        lc = [c[0] for c in liked_categories if c and c[0]]
        if not lc:
            try:
                from app.models.all_models import UserPersona

                persona = db.query(UserPersona).filter(UserPersona.user_id == int(user_id)).first()
                tags = getattr(persona, "tags", None)
                if isinstance(tags, list):
                    for t in tags:
                        if isinstance(t, str) and t.startswith("cat:"):
                            lc.append(t.split(":", 1)[1])
            except Exception:
                pass
        return lc[:50]

    out = cache.get_or_set_json(pref_key, ttl=ttl, builder=_build_pref) or []
    return out if isinstance(out, list) else []


def _get_user_signals(db: Session, user_id: Optional[int]) -> tuple[str, List[str]]:
    ab_variant = ""
    liked_cats: List[str] = []
    if not user_id:
        return ab_variant, liked_cats
    try:
        ab_variant = get_variant(db, user_id=int(user_id), experiment="feed_rank_v1")
    except Exception:
        ab_variant = ""
    try:
        liked_cats = _get_liked_categories(db, int(user_id), ab_variant or None)
    except Exception:
        liked_cats = []
    return ab_variant, liked_cats


def _get_pending_items(db: Session, user_id: int, category: Optional[str], limit2: int) -> List[dict]:
    s = get_settings()
    max_pending = int(getattr(s, "FEED_PENDING_MAX", 5) or 5)
    if max_pending < 0:
        max_pending = 0
    if max_pending > 50:
        max_pending = 50
    pending_limit = min(max_pending, max(0, int(limit2) - 1))
    if not pending_limit:
        return []
    pq = (
        db.query(Post)
        .options(joinedload(Post.owner), joinedload(Post.active_media_asset))
        .filter(Post.user_id == int(user_id), Post.status.in_(["processing", "queued"]))
        .order_by(Post.created_at.desc(), Post.id.desc())
        .limit(pending_limit)
    )
    if category and category != "all":
        pq = pq.filter(Post.category == category)
    pend = pq.all()
    if not pend:
        return []
    pi = _serialize_posts_base(pend, db)
    return decorate_flags(pi, user_id, db)


def _get_candidates(db: Session, cat_key: str) -> List[Dict[str, Any]]:
    rr = recall_candidates(db, cat_key=cat_key)
    return rr.candidates if isinstance(rr.candidates, list) else []


def _priority_fn(cat_key: str, liked_cats: List[str]):
    def _priority(it: dict) -> int:
        if cat_key != "all":
            return 0
        if not liked_cats:
            return 0
        c = it.get("category")
        return 0 if (liked_cats and c in liked_cats) else 1

    return _priority


def _sort_candidates(candidates: List[dict], priority):
    try:
        candidates.sort(
            key=lambda it: (
                priority(it),
                -float(it.get("score") or 0),
                -float(it.get("created_at") or 0),
                -int(it.get("id") or 0),
            )
        )
    except Exception:
        pass


def _diversify_items(items: List[dict], max_per_author: int) -> List[dict]:
    m = int(max_per_author or 0)
    if m < 1:
        return items
    if m > 20:
        m = 20
    buckets = {}
    order: List[int] = []
    for it in items:
        try:
            uid = int(it.get("user_id") or 0)
        except Exception:
            uid = 0
        if uid <= 0:
            uid = -len(order) - 1
        if uid not in buckets:
            buckets[uid] = []
            order.append(uid)
        buckets[uid].append(it)

    out: List[dict] = []
    used = {}
    while len(out) < len(items):
        progressed = False
        for uid in order:
            q = buckets.get(uid) or []
            if not q:
                continue
            if int(used.get(uid, 0)) >= m and uid > 0:
                continue
            out.append(q.pop(0))
            used[uid] = int(used.get(uid, 0)) + 1
            progressed = True
            if len(out) >= len(items):
                break
        if progressed:
            continue
        for uid in order:
            q = buckets.get(uid) or []
            if not q:
                continue
            out.append(q.pop(0))
            if len(out) >= len(items):
                break
    return out


def _paginate_candidates(candidates: List[dict], *, limit_done: int, priority, cursor_obj: Optional[dict], rs: Optional[int] = None):
    cur_p = cursor_obj.get("p") if isinstance(cursor_obj, dict) else None
    try:
        cur_score = float(cursor_obj.get("score") or 0) if isinstance(cursor_obj, dict) else 0.0
    except Exception:
        cur_score = 0.0
    try:
        cur_created_at = float(cursor_obj.get("created_at") or 0) if isinstance(cursor_obj, dict) else 0.0
    except Exception:
        cur_created_at = 0.0
    cur_id = cursor_obj.get("id") if isinstance(cursor_obj, dict) else None

    def key_tuple(it: dict):
        return (
            int(priority(it)),
            -float(it.get("score") or 0),
            -float(it.get("created_at") or 0),
            -int(it.get("id") or 0),
        )

    if isinstance(cur_p, int) and isinstance(cur_id, int):
        cur_key = (int(cur_p), -float(cur_score), -float(cur_created_at), -int(cur_id))
        filtered = [it for it in candidates if key_tuple(it) > cur_key]
    else:
        filtered = candidates

    page = filtered[: max(0, int(limit_done))]
    next_cur = ""
    if page:
        last = page[-1]
        next_cur = encode_cursor(
            {
                "p": int(priority(last)),
                "score": float(last.get("score") or 0),
                "created_at": float(last.get("created_at") or 0),
                "id": int(last.get("id") or 0),
                "rs": int(rs) if isinstance(rs, int) else None,
            }
        )
    ids = [int(it.get("id")) for it in page if it and it.get("id")]
    return ids, next_cur


def _hydrate_posts(db: Session, ids: List[int]) -> List[Post]:
    if not ids:
        return []
    posts2 = (
        db.query(Post)
        .options(joinedload(Post.owner), joinedload(Post.active_media_asset))
        .filter(Post.status == "done", Post.id.in_(ids))
        .all()
    )
    by_id = {int(p.id): p for p in posts2}
    return [by_id[i] for i in ids if i in by_id]


def get_feed(db: Session, *, category: Optional[str], user_id: Optional[int], limit: int, cursor: Optional[str]) -> FeedResult:
    from sqlalchemy import and_, case, or_

    limit2 = _limit(limit)

    cur = decode_cursor(cursor)
    cur_dt = cursor_datetime(cur, "created_at")
    cur_id = cur.get("id") if isinstance(cur, dict) else None
    cur_p = cur.get("p") if isinstance(cur, dict) else None
    has_cursor = cur_dt is not None and isinstance(cur_id, int)

    q = db.query(Post).options(joinedload(Post.owner), joinedload(Post.active_media_asset)).filter(Post.status == "done")

    pending_items: List[dict] = []
    if user_id and not cursor:
        try:
            pending_items = _get_pending_items(db, int(user_id), category, limit2)
        except Exception:
            pending_items = []

    ab_variant, liked_cats = _get_user_signals(db, user_id)

    if category and category != "all":
        q = q.filter(Post.category == category)
        priority_expr = case((Post.id == Post.id, 0), else_=0)
        cat_key = category
    elif liked_cats:
        priority_expr = case((Post.category.in_(liked_cats), 0), else_=1)
        cat_key = "all"
    else:
        priority_expr = case((Post.id == Post.id, 0), else_=0)
        cat_key = "all"

    if has_cursor:
        if isinstance(cur_p, int):
            q = q.filter(
                or_(
                    priority_expr > cur_p,
                    and_(
                        priority_expr == cur_p,
                        or_(
                            Post.created_at < cur_dt,
                            and_(Post.created_at == cur_dt, Post.id < cur_id),
                        ),
                    ),
                )
            )
        else:
            q = q.filter(or_(Post.created_at < cur_dt, and_(Post.created_at == cur_dt, Post.id < cur_id)))

    kind = get_runtime_kind()
    if cursor and kind == "recent":
        posts = q.order_by(priority_expr.asc(), Post.created_at.desc(), Post.id.desc()).limit(limit2).all()
        next_cur = ""
        if posts:
            last = posts[-1]
            if getattr(last, "created_at", None) is not None:
                last_p = 0
                if liked_cats and cat_key == "all":
                    last_p = 0 if (last.category in liked_cats) else 1
                next_cur = encode_cursor({
                    "p": int(last_p),
                    "created_at": float(last.created_at.timestamp()),
                    "id": int(last.id),
                })
        items = _serialize_posts_base(posts, db)
        return FeedResult(items=decorate_flags(items, user_id, db), next_cursor=next_cur, ab_variant=ab_variant)

    candidates = _get_candidates(db, cat_key)
    try:
        if candidates and len(candidates) < int(limit2):
            candidates = []
    except Exception:
        pass
    if not candidates:
        posts = q.order_by(priority_expr.asc(), Post.created_at.desc(), Post.id.desc()).limit(limit2).all()
        next_cur = ""
        if posts:
            last = posts[-1]
            if getattr(last, "created_at", None) is not None:
                last_p = 0
                if liked_cats and cat_key == "all":
                    last_p = 0 if (last.category in liked_cats) else 1
                next_cur = encode_cursor(
                    {
                        "p": int(last_p),
                        "created_at": float(last.created_at.timestamp()),
                        "id": int(last.id),
                    }
                )
        items = _serialize_posts_base(posts, db)
        return FeedResult(items=pending_items + decorate_flags(items, user_id, db), next_cursor=next_cur, ab_variant=ab_variant)

    rs_used = None
    try:
        s = get_settings()
        if bool(getattr(s, "FEED_RERANK_ENABLED", True)):
            from app.services.engagement_service import exposure_adjusted_score, get_feed_impression_map

            snap_sec = int(getattr(s, "FEED_RERANK_SNAPSHOT_SEC", 5) or 5)
            if snap_sec < 1:
                snap_sec = 1
            if snap_sec > 60:
                snap_sec = 60
            try:
                rs = int(cur.get("rs")) if isinstance(cur, dict) and cur.get("rs") is not None else None
            except Exception:
                rs = None
            if not isinstance(rs, int) or rs <= 0:
                rs = int(time.time()) // int(snap_sec)
            rs_used = int(rs)

            ids2 = [int(it.get("id") or 0) for it in candidates if it and it.get("id")]
            sig = ""
            try:
                sig = hashlib.sha1(",".join(str(x) for x in ids2[:2000]).encode("utf-8")).hexdigest()[:12]
            except Exception:
                sig = ""
            ttl = int(getattr(s, "FEED_RERANK_SNAPSHOT_TTL_SEC", 90) or 90)
            if ttl < 5:
                ttl = 5
            if ttl > 3600:
                ttl = 3600

            def _build_impr():
                return get_feed_impression_map(ids2)

            impr = cache.get_or_set_json(f"feed:rerank:impr:rs{int(rs)}:sig{sig}", ttl=ttl, builder=_build_impr) or {}
            if not isinstance(impr, dict):
                impr = {}
            smooth = int(getattr(s, "FEED_RERANK_EXPOSURE_SMOOTHING", 200) or 200)
            for it in candidates:
                try:
                    pid = int(it.get("id") or 0)
                    if pid <= 0:
                        continue
                    it["score"] = float(exposure_adjusted_score(float(it.get("score") or 0.0), int(impr.get(pid, 0)), smooth))
                except Exception:
                    continue
    except Exception:
        pass

    priority = _priority_fn(cat_key, liked_cats)
    _sort_candidates(candidates, priority)

    limit_done = max(0, int(limit2) - len(pending_items))
    rs2 = None
    try:
        rs2 = int(cur.get("rs")) if isinstance(cur, dict) and cur.get("rs") is not None else None
    except Exception:
        rs2 = None
    if not isinstance(rs2, int) and isinstance(rs_used, int):
        rs2 = int(rs_used)
    ids, next_cur = _paginate_candidates(
        candidates,
        limit_done=limit_done,
        priority=priority,
        cursor_obj=cur if isinstance(cur, dict) else None,
        rs=rs2,
    )
    if not ids:
        return FeedResult(items=pending_items, next_cursor=next_cur, ab_variant=ab_variant)

    ordered = _hydrate_posts(db, ids)
    items = _serialize_posts_base(ordered, db)
    try:
        s = get_settings()
        if bool(getattr(s, "FEED_DIVERSITY_ENABLED", True)):
            max_per = int(getattr(s, "FEED_DIVERSITY_MAX_PER_AUTHOR", 2) or 2)
            items = _diversify_items(items, max_per_author=max_per)
    except Exception:
        pass
    return FeedResult(items=pending_items + decorate_flags(items, user_id, db), next_cursor=next_cur, ab_variant=ab_variant)
