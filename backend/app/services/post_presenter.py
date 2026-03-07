from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.all_models import Follow, Interaction, Post


def _normalize_media_url(u: Any) -> Any:
    if not isinstance(u, str):
        return u
    out = u
    if "/static//static/" in out:
        out = out.replace("/static//static/", "/static/")

    s = get_settings()
    pub = getattr(s, "R2_PUBLIC_URL", None)
    if isinstance(pub, str) and pub:
        pub2 = pub.rstrip("/")
        if out.startswith(pub2 + "/"):
            path = out[len(pub2) :]
            if path.startswith("/uploads/"):
                out = "/static" + path

    if out.startswith("https://cdn.aiseek.com/") or out.startswith("http://cdn.aiseek.com/"):
        path = out.split("cdn.aiseek.com", 1)[1]
        if path.startswith("/uploads/"):
            out = "/static" + path

    return out


def serialize_post_base(post: Post, delta: Optional[Dict[str, int]] = None) -> Dict[str, Any]:
    nickname = f"User{post.user_id}"
    avatar = None
    if getattr(post, "owner", None):
        nickname = post.owner.nickname or post.owner.username
        avatar = post.owner.avatar

    video_url_raw = getattr(post, "video_url", None)
    video_url = _normalize_media_url(video_url_raw)

    active = getattr(post, "active_media_asset", None)
    media_version = None
    hls_url = None
    mp4_url = None
    cover_url = _normalize_media_url(getattr(post, "cover_url", None))
    subtitle_tracks = None
    duration = int(getattr(post, "duration", 0) or 0) if getattr(post, "duration", None) is not None else None
    video_width = int(getattr(post, "video_width", 0) or 0) if getattr(post, "video_width", None) is not None else None
    video_height = int(getattr(post, "video_height", 0) or 0) if getattr(post, "video_height", None) is not None else None

    if active is not None:
        try:
            media_version = getattr(active, "version", None)
            hls_url = _normalize_media_url(getattr(active, "hls_url", None))
            mp4_url = _normalize_media_url(getattr(active, "mp4_url", None))
            cov2 = _normalize_media_url(getattr(active, "cover_url", None))
            if cov2:
                cover_url = cov2
            subtitle_tracks = getattr(active, "subtitle_tracks", None)
            if getattr(active, "duration", None) is not None:
                duration = int(getattr(active, "duration", 0) or 0)
            if getattr(active, "video_width", None) is not None:
                video_width = int(getattr(active, "video_width", 0) or 0)
            if getattr(active, "video_height", None) is not None:
                video_height = int(getattr(active, "video_height", 0) or 0)
        except Exception:
            pass

    if not hls_url and not mp4_url:
        processed_url = _normalize_media_url(getattr(post, "processed_url", None))
        try:
            if isinstance(video_url_raw, str) and video_url_raw.lower().endswith(".m3u8"):
                hls_url = video_url
            if isinstance(processed_url, str) and processed_url:
                mp4_url = processed_url
            elif isinstance(video_url, str) and video_url and not (isinstance(video_url_raw, str) and video_url_raw.lower().endswith(".m3u8")):
                mp4_url = video_url
        except Exception:
            pass
    images = getattr(post, "images", None)
    if isinstance(images, list):
        images = [_normalize_media_url(x) for x in images]

    try:
        if not cover_url:
            if isinstance(images, list) and images and images[0]:
                cover_url = images[0]
            else:
                post_type = getattr(post, "post_type", None) or "video"
                is_video = bool(post_type == "video" or hls_url or mp4_url or (isinstance(video_url, str) and video_url))
                if is_video:
                    thumb_v = int(post.id)
                    try:
                        aid = getattr(active, "id", None) if active is not None else None
                        if isinstance(aid, int) and aid > 0:
                            thumb_v = int(aid)
                        else:
                            pid = getattr(post, "active_media_asset_id", None)
                            if isinstance(pid, int) and pid > 0:
                                thumb_v = int(pid)
                    except Exception:
                        thumb_v = int(post.id)
                    cover_url = f"/api/v1/media/post-thumb/{int(post.id)}?v={thumb_v}"
    except Exception:
        pass

    favorites_count = getattr(post, "favorites_count", None)
    if favorites_count is None:
        favorites_count = 0

    likes_count = int(getattr(post, "likes_count", 0) or 0)
    comments_count = int(getattr(post, "comments_count", 0) or 0)
    favorites_count = int(favorites_count or 0)
    shares_count = int(getattr(post, "shares_count", 0) or 0)
    downloads_count = int(getattr(post, "downloads_count", 0) or 0)
    try:
        de = getattr(post, "download_enabled", None)
        download_enabled = True if de is None else bool(de)
    except Exception:
        download_enabled = True
    views_count = int(getattr(post, "views_count", 0) or 0)
    try:
        d = delta
        if d is None:
            from app.services.hot_counter_service import get_delta

            d = get_delta(int(post.id))
        likes_count = max(0, likes_count + int(d.get("likes") or 0))
        favorites_count = max(0, favorites_count + int(d.get("favorites") or 0))
        comments_count = max(0, comments_count + int(d.get("comments") or 0))
        views_count = max(0, views_count + int(d.get("views") or 0))
    except Exception:
        pass

    created_at = getattr(post, "created_at", None)
    if created_at is not None and hasattr(created_at, "isoformat"):
        try:
            from datetime import timezone

            if getattr(created_at, "tzinfo", None) is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            created_at_out = created_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        except Exception:
            created_at_out = created_at.isoformat()
    else:
        created_at_out = None

    return {
        "id": int(post.id),
        "title": getattr(post, "title", None),
        "summary": getattr(post, "summary", None),
        "post_type": getattr(post, "post_type", "video") or "video",
        "video_url": hls_url or mp4_url or video_url,
        "hls_url": hls_url,
        "mp4_url": mp4_url,
        "images": images,
        "cover_url": cover_url,
        "subtitle_tracks": subtitle_tracks,
        "duration": duration,
        "video_width": video_width,
        "video_height": video_height,
        "media_version": media_version,
        "created_at": created_at_out,
        "views_count": int(views_count),
        "likes_count": int(likes_count),
        "status": getattr(post, "status", "") or "",
        "category": getattr(post, "category", None),
        "ai_job_id": getattr(post, "ai_job_id", None),
        "user_id": int(getattr(post, "user_id", 0) or 0),
        "user_nickname": nickname,
        "user_avatar": _normalize_media_url(avatar),
        "content_text": getattr(post, "content_text", None),
        "comments_count": int(comments_count),
        "favorites_count": int(favorites_count),
        "shares_count": int(shares_count),
        "downloads_count": int(downloads_count),
        "download_enabled": bool(download_enabled),
        "is_liked": False,
        "is_favorited": False,
        "is_reposted": False,
        "is_following": False,
        "error_message": getattr(post, "error_message", None),
    }


def serialize_posts_base(posts: List[Post]) -> List[Dict[str, Any]]:
    if not posts:
        return []
    out = []
    deltas = {}
    try:
        from app.services.hot_counter_service import get_deltas

        ids = [int(getattr(p, "id", 0) or 0) for p in posts if p]
        deltas = get_deltas(ids)
    except Exception:
        deltas = {}
    for p in posts:
        if not p:
            continue
        try:
            pid = int(getattr(p, "id", 0) or 0)
        except Exception:
            pid = 0
        out.append(serialize_post_base(p, delta=deltas.get(pid)))
    return out


def decorate_flags(items: List[Dict[str, Any]], current_user_id: Optional[int], db: Session) -> List[Dict[str, Any]]:
    if not current_user_id or not items:
        return items
    post_ids = []
    owner_ids = []
    for it in items:
        try:
            post_ids.append(int(it.get("id")))
        except Exception:
            continue
        try:
            owner_ids.append(int(it.get("user_id")))
        except Exception:
            pass
    post_ids = list({p for p in post_ids})
    owner_ids = list({u for u in owner_ids})

    liked = set()
    fav = set()
    rep = set()
    rows = (
        db.query(Interaction.post_id, Interaction.type)
        .filter(Interaction.user_id == current_user_id, Interaction.post_id.in_(post_ids), Interaction.type.in_(["like", "favorite", "repost"]))
        .all()
    )
    for pid, t in rows:
        if t == "like":
            liked.add(int(pid))
        elif t == "favorite":
            fav.add(int(pid))
        elif t == "repost":
            rep.add(int(pid))

    following = set()
    if owner_ids:
        fr = (
            db.query(Follow.following_id)
            .filter(Follow.follower_id == current_user_id, Follow.following_id.in_(owner_ids))
            .all()
        )
        following = {int(x[0]) for x in fr if x and x[0] is not None}

    out = []
    for it in items:
        try:
            pid = int(it.get("id"))
        except Exception:
            out.append(it)
            continue
        try:
            uid = int(it.get("user_id"))
        except Exception:
            uid = None
        it2 = dict(it)
        it2["is_liked"] = pid in liked
        it2["is_favorited"] = pid in fav
        it2["is_reposted"] = pid in rep
        it2["is_following"] = (uid in following) if uid is not None else False
        out.append(it2)
    return out
