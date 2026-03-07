from fastapi import APIRouter, Depends, HTTPException, Body, Query, Response
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from app.api.deps import get_current_user, get_current_user_optional, get_db, get_read_db
from app.core.cache import cache
from app.core.config import get_settings
from app.models.all_models import User, FriendRequest, Follow, Post
from typing import List, Optional
from pydantic import BaseModel
import datetime
import time

router = APIRouter()

try:
    from prometheus_client import Counter

    SEARCH_USERS_CACHE_TOTAL = Counter("aiseek_search_users_cache_total", "Search users cache total", ["layer", "outcome", "has_cursor"])
except Exception:
    SEARCH_USERS_CACHE_TOTAL = None

_SEARCH_USERS_POLICY_CACHE_AT = 0.0
_SEARCH_USERS_POLICY_CACHE_VAL = None


def _search_users_policy():
    global _SEARCH_USERS_POLICY_CACHE_AT, _SEARCH_USERS_POLICY_CACHE_VAL
    now_ts = time.monotonic()
    cached = _SEARCH_USERS_POLICY_CACHE_VAL
    if isinstance(cached, dict) and (now_ts - float(_SEARCH_USERS_POLICY_CACHE_AT or 0.0)) < 2.0:
        return cached

    def _int_opt(s, name, default, lo, hi):
        try:
            v = int(getattr(s, name, default) or default)
        except Exception:
            v = default
        if v < lo:
            return lo
        if v > hi:
            return hi
        return v

    val = {
        "cache_key_q_max_len": 64,
        "exact_ttl": 15,
        "exact_lock_ttl": 2,
        "fuzzy_min_len": 1,
        "ttl_ids": 8,
        "ttl_ids_cursor": 4,
        "ttl_items": 8,
        "ttl_items_cursor": 4,
        "lock_ttl": 2,
        "lock_ttl_cursor": 1,
    }
    try:
        s = get_settings()
        val["cache_key_q_max_len"] = _int_opt(s, "SEARCH_USERS_CACHE_KEY_QUERY_MAX_LEN", 64, 8, 128)
        val["exact_ttl"] = _int_opt(s, "SEARCH_USERS_EXACT_CACHE_TTL_SEC", 15, 1, 300)
        val["exact_lock_ttl"] = _int_opt(s, "SEARCH_USERS_EXACT_CACHE_LOCK_TTL_SEC", 2, 1, 15)
        val["fuzzy_min_len"] = _int_opt(s, "SEARCH_USERS_FUZZY_MIN_QUERY_LEN", 1, 1, 8)
        val["ttl_ids"] = _int_opt(s, "SEARCH_USERS_CACHE_TTL_SEC", 8, 1, 120)
        val["ttl_ids_cursor"] = _int_opt(s, "SEARCH_USERS_CURSOR_CACHE_TTL_SEC", 4, 1, 60)
        val["ttl_items"] = _int_opt(s, "SEARCH_USERS_ITEMS_CACHE_TTL_SEC", 8, 1, 120)
        val["ttl_items_cursor"] = _int_opt(s, "SEARCH_USERS_CURSOR_ITEMS_CACHE_TTL_SEC", 4, 1, 60)
        val["lock_ttl"] = _int_opt(s, "SEARCH_USERS_CACHE_LOCK_TTL_SEC", 2, 1, 15)
        val["lock_ttl_cursor"] = _int_opt(s, "SEARCH_USERS_CURSOR_CACHE_LOCK_TTL_SEC", 1, 1, 10)
    except Exception:
        pass

    _SEARCH_USERS_POLICY_CACHE_AT = now_ts
    _SEARCH_USERS_POLICY_CACHE_VAL = val
    return val


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


@router.get("/all")
def list_all_users(q: Optional[str] = None, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not getattr(current_user, 'is_superuser', False):
        raise HTTPException(status_code=403, detail='Forbidden')
    query = db.query(User)
    if q and q.strip():
        qq = q.strip()
        query = query.filter(or_(User.username.contains(qq), User.nickname.contains(qq), User.email.contains(qq), User.phone.contains(qq), User.aiseek_id.contains(qq)))
    users = query.order_by(User.id.asc()).limit(500).all()
    return [user_to_dict(u) for u in users]


@router.get("/me/submit_status")
def my_submit_status(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.services.reputation_service import check_submit_allowed, effective_reputation_score

    ok, deny = check_submit_allowed(db, current_user)
    score = int(effective_reputation_score(current_user) or 0)
    return {"ok": bool(ok), "score": score, "deny": deny}

# --- Schemas ---
class UserAdminOut(BaseModel):
    id: int
    username: str
    nickname: Optional[str] = None
    phone: Optional[str] = None
    followers_count: Optional[int] = 0
    created_at: Optional[datetime.datetime] = None
    
    class Config:
        from_attributes = True

class PasswordChange(BaseModel):
    user_id: int
    old_password: str
    new_password: str

class SettingsUpdate(BaseModel):
    user_id: int
    settings: dict

class ProfileUpdate(BaseModel):
    user_id: int
    nickname: Optional[str] = None
    bio: Optional[str] = None
    gender: Optional[str] = None
    birthday: Optional[str] = None
    location: Optional[str] = None
    avatar: Optional[str] = None
    background: Optional[str] = None

class ContactUpdate(BaseModel):
    user_id: int
    phone: Optional[str] = None
    email: Optional[str] = None

class FollowRequest(BaseModel):
    user_id: int
    target_id: int

class FriendReqCreate(BaseModel):
    from_user_id: int
    to_user_id: int

class FriendReqAction(BaseModel):
    request_id: int
    status: str # accepted, rejected

# --- Helpers ---
def user_to_dict(u):
    if not u: return None
    from app.services.reputation_service import effective_reputation_score

    active = getattr(u, "is_active", True)
    if active is None:
        active = True
    rep = int(effective_reputation_score(u) or 0)
    ban_until = getattr(u, "submit_banned_until", None)
    ban_until_out = None
    try:
        if ban_until is not None and hasattr(ban_until, "isoformat"):
            ban_until_out = ban_until.isoformat()
    except Exception:
        ban_until_out = None
    return {
        "id": u.id,
        "username": u.username,
        "email": getattr(u, 'email', None),
        "phone": getattr(u, 'phone', None),
        "nickname": u.nickname or u.username,
        "avatar": u.avatar,
        "background": getattr(u, 'background', None),
        "bio": u.bio,
        "gender": u.gender,
        "birthday": u.birthday,
        "location": u.location,
        "followers_count": u.followers_count or 0,
        "following_count": u.following_count or 0,
        "likes_received_count": u.likes_received_count or 0,
        "aiseek_id": u.aiseek_id,
        "is_active": bool(active),
        "is_superuser": bool(getattr(u, "is_superuser", False)),
        "reputation_score": rep,
        "submit_banned_until": ban_until_out,
    }


class BanUserIn(BaseModel):
    reason: Optional[str] = None


@router.post("/{user_id}/ban")
def admin_ban_user(user_id: int, body: BanUserIn = Body(None), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not getattr(current_user, 'is_superuser', False):
        raise HTTPException(status_code=403, detail='Forbidden')
    u = db.query(User).filter(User.id == int(user_id)).first()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    if int(u.id) == int(current_user.id):
        raise HTTPException(status_code=400, detail="Cannot ban self")
    u.is_active = False
    db.commit()
    return {"ok": True, "user_id": int(u.id), "is_active": False}

class ReputationAdminIn(BaseModel):
    reputation_score: int
    reason: Optional[str] = None
    clear_ban: bool = True
    reactivate: bool = True


@router.post("/{user_id}/reputation")
def admin_set_reputation(user_id: int, body: ReputationAdminIn, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not getattr(current_user, 'is_superuser', False):
        raise HTTPException(status_code=403, detail='Forbidden')
    u = db.query(User).filter(User.id == int(user_id)).first()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    from app.services.reputation_service import set_reputation_manual

    eff = set_reputation_manual(
        db,
        u,
        new_score=int(body.reputation_score),
        admin_user_id=int(current_user.id),
        reason=body.reason,
        clear_ban=bool(body.clear_ban),
        reactivate=bool(body.reactivate),
    )
    db.refresh(u)
    return {"ok": True, "user": user_to_dict(u), "effective_reputation_score": int(eff)}


@router.post("/{user_id}/unban")
def admin_unban_user(user_id: int, body: BanUserIn = Body(None), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not getattr(current_user, 'is_superuser', False):
        raise HTTPException(status_code=403, detail='Forbidden')
    u = db.query(User).filter(User.id == int(user_id)).first()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    u.is_active = True
    db.commit()
    return {"ok": True, "user_id": int(u.id), "is_active": True}


class BulkBanIn(BaseModel):
    q: str
    limit: int = 2000


@router.post("/bulk_ban")
def admin_bulk_ban(body: BulkBanIn, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not getattr(current_user, 'is_superuser', False):
        raise HTTPException(status_code=403, detail='Forbidden')
    q = (getattr(body, "q", "") or "").strip()
    if not q:
        raise HTTPException(status_code=400, detail="Missing q")
    lim = int(getattr(body, "limit", 2000) or 2000)
    if lim < 1:
        lim = 1
    if lim > 5000:
        lim = 5000
    ids = [int(x[0]) for x in db.query(User.id).filter(or_(User.username.contains(q), User.nickname.contains(q), User.email.contains(q), User.phone.contains(q), User.aiseek_id.contains(q))).order_by(User.id.asc()).limit(lim).all()]
    if not ids:
        return {"ok": True, "count": 0, "user_ids": []}
    ids = [i for i in ids if int(i) != int(current_user.id)]
    if not ids:
        return {"ok": True, "count": 0, "user_ids": []}
    db.query(User).filter(User.id.in_(ids)).update({User.is_active: False}, synchronize_session=False)
    db.commit()
    return {"ok": True, "count": len(ids), "user_ids": ids}

# --- Endpoints ---

@router.get("/profile/{user_id}")
def get_profile(user_id: int, current_user_id: Optional[int] = None, db: Session = Depends(get_read_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    is_owner = bool(current_user_id and int(current_user_id) == int(user_id))
    if is_owner:
        works_count = int(db.query(func.count(Post.id)).filter(Post.user_id == user_id, Post.status != "failed").scalar() or 0)
    else:
        works_count = int(db.query(func.count(Post.id)).filter(Post.user_id == user_id, Post.status == "done").scalar() or 0)
        
    is_following = False
    is_friend = False
    
    if current_user_id:
        # Check follow status
        f = db.query(Follow).filter(Follow.follower_id == current_user_id, Follow.following_id == user_id).first()
        if f: is_following = True
        
        # Check friend status (mutual follow)
        f2 = db.query(Follow).filter(Follow.follower_id == user_id, Follow.following_id == current_user_id).first()
        if f and f2: is_friend = True

    u = user_to_dict(user)
    if not is_owner:
        try:
            if isinstance(u, dict):
                u.pop("reputation_score", None)
        except Exception:
            pass
    return {
        "user": u,
        "works_count": works_count,
        "is_following": is_following,
        "is_friend": is_friend
    }

@router.get("/search-user")
def search_user(
    response: Response,
    query: str = Query(..., min_length=1, max_length=128),
    limit: int = Query(10, ge=1, le=50),
    cursor: Optional[str] = Query(None, max_length=512),
    db: Session = Depends(get_read_db),
):
    from app.core.cache import cache
    from app.utils.cursor import decode_cursor, encode_cursor
    from sqlalchemy import and_, or_

    q = str(query or "").strip()
    if not q:
        return []
    q_lc = q.lower()
    pol = _search_users_policy()
    cache_key_q_max_len = int(pol.get("cache_key_q_max_len", 64) or 64)
    q_key = q_lc[:cache_key_q_max_len]
    q_fuzzy = q[:cache_key_q_max_len]
    decoded_cur = None
    if cursor:
        try:
            decoded_cur = decode_cursor(cursor)
            if decoded_cur is None:
                raise HTTPException(status_code=400, detail="invalid_cursor")
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=400, detail="invalid_cursor")
    try:
        lim = int(limit or 10)
    except Exception:
        lim = 10
    if lim < 1:
        lim = 1
    if lim > 50:
        lim = 50

    def _pack_user_row(row):
        if not row:
            return None
        return {
            "id": int(row[0] or 0),
            "username": row[1],
            "nickname": row[2] or row[1],
            "avatar": row[3],
            "followers_count": int(row[4] or 0),
            "aiseek_id": row[5],
        }

    def _user_rows_query():
        return db.query(
            User.id,
            User.username,
            User.nickname,
            User.avatar,
            User.followers_count,
            User.aiseek_id,
        )

    def _query_exact_items():
        if q.isdigit():
            row = _user_rows_query().filter(User.id == int(q)).first()
            it = _pack_user_row(row)
            return [it] if it else []
        row = _user_rows_query().filter(User.aiseek_id == q).first()
        if row:
            it = _pack_user_row(row)
            return [it] if it else []
        return None

    if not cursor:
        exact_ttl = int(pol.get("exact_ttl", 15) or 15)
        exact_lock_ttl = int(pol.get("exact_lock_ttl", 2) or 2)
        try:
            from app.core.cache import stable_sig

            key_exact = f"search:users:exact:v1:{stable_sig(['exact', q_key])}"
            built_exact = {"v": False}

            def _build_exact_items_marked():
                built_exact["v"] = True
                return _query_exact_items()

            exact_items = cache.get_or_set_json(key_exact, ttl=int(exact_ttl), builder=_build_exact_items_marked, lock_ttl=int(exact_lock_ttl))
            if SEARCH_USERS_CACHE_TOTAL is not None:
                try:
                    SEARCH_USERS_CACHE_TOTAL.labels("exact_items", "miss" if built_exact["v"] else "hit", "0").inc()
                except Exception:
                    pass
        except Exception:
            exact_items = _query_exact_items()
        if isinstance(exact_items, list):
            return exact_items

    cur = str(cursor or "")
    fuzzy_min_len = int(pol.get("fuzzy_min_len", 1) or 1)
    if len(q) < fuzzy_min_len:
        if SEARCH_USERS_CACHE_TOTAL is not None:
            try:
                SEARCH_USERS_CACHE_TOTAL.labels("fuzzy_gate", "skip", "1" if cur else "0").inc()
            except Exception:
                pass
        return []
    ttl_ids = int(pol.get("ttl_ids", 8) or 8)
    ttl_ids_cursor = int(pol.get("ttl_ids_cursor", 4) or 4)
    ttl_items = int(pol.get("ttl_items", 8) or 8)
    ttl_items_cursor = int(pol.get("ttl_items_cursor", 4) or 4)
    lock_ttl = int(pol.get("lock_ttl", 2) or 2)
    lock_ttl_cursor = int(pol.get("lock_ttl_cursor", 1) or 1)
    use_ttl_ids = ttl_ids_cursor if cur else ttl_ids
    use_ttl_items = ttl_items_cursor if cur else ttl_items
    use_lock_ttl = lock_ttl_cursor if cur else lock_ttl

    key_items = ""
    key = ""
    try:
        from app.core.cache import stable_sig

        sig = stable_sig(['users', q_key, int(lim), cur])
        key_items = f"search:users:items:v2:{sig}"
        key = f"search:users:v3:{sig}"
    except Exception:
        key_items = ""
        key = ""

    dialect_name = ""
    try:
        dialect_name = str(getattr(getattr(db, "bind", None), "dialect", None).name or "")
    except Exception:
        dialect_name = ""
    use_ilike = (dialect_name == "postgresql")
    q_fuzzy_like = f"%{q_fuzzy}%"

    def build():
        cur_fc = decoded_cur.get("fc") if isinstance(decoded_cur, dict) else None
        cur_id = decoded_cur.get("id") if isinstance(decoded_cur, dict) else None

        if use_ilike:
            base = db.query(User.id, User.followers_count).filter(or_(User.nickname.ilike(q_fuzzy_like), User.username.ilike(q_fuzzy_like)))
        else:
            base = db.query(User.id, User.followers_count).filter(or_(User.nickname.contains(q_fuzzy), User.username.contains(q_fuzzy)))
        if isinstance(cur_fc, int) and isinstance(cur_id, int):
            base = base.filter(or_(User.followers_count < cur_fc, and_(User.followers_count == cur_fc, User.id < cur_id)))
        rows = base.order_by(User.followers_count.desc(), User.id.desc()).limit(int(lim)).all()
        ids = []
        nxt = None
        if rows:
            for uid, _ in rows:
                try:
                    ids.append(int(uid))
                except Exception:
                    pass
            last = rows[-1]
            try:
                nxt = encode_cursor({"fc": int(last[1] or 0), "id": int(last[0])})
            except Exception:
                nxt = None
        return {"ids": ids, "next_cursor": nxt}

    def _materialize_items(ids):
        if not ids:
            return []
        rows2 = _user_rows_query().filter(User.id.in_(ids)).all()
        by_id = {}
        for r in rows2 or []:
            try:
                by_id[int(r[0])] = r
            except Exception:
                continue
        items2 = []
        for i in ids:
            row2 = by_id.get(int(i))
            if not row2:
                continue
            it = _pack_user_row(row2)
            if it:
                items2.append(it)
        return items2

    if key_items:
        def _build_items_cached():
            out2 = build()
            ids2 = out2.get("ids") if isinstance(out2, dict) else []
            nxt2 = out2.get("next_cursor") if isinstance(out2, dict) else None
            return {"items": _materialize_items(ids2), "next_cursor": nxt2}

        built_items = {"v": False}

        def _build_items_cached_marked():
            built_items["v"] = True
            return _build_items_cached()

        payload = cache.get_or_set_json(key_items, ttl=int(use_ttl_items), builder=_build_items_cached_marked, lock_ttl=int(use_lock_ttl))
        if SEARCH_USERS_CACHE_TOTAL is not None:
            try:
                SEARCH_USERS_CACHE_TOTAL.labels("items", "miss" if built_items["v"] else "hit", "1" if cur else "0").inc()
            except Exception:
                pass
        if isinstance(payload, dict) and isinstance(payload.get("items"), list):
            nxt = payload.get("next_cursor")
            if nxt:
                response.headers["x-next-cursor"] = str(nxt)
            return payload.get("items")

    out = None
    if key:
        built_ids = {"v": False}

        def _build_ids_marked():
            built_ids["v"] = True
            return build()

        out = cache.get_or_set_json(key, ttl=int(use_ttl_ids), builder=_build_ids_marked, lock_ttl=int(use_lock_ttl))
        if SEARCH_USERS_CACHE_TOTAL is not None:
            try:
                SEARCH_USERS_CACHE_TOTAL.labels("ids", "miss" if built_ids["v"] else "hit", "1" if cur else "0").inc()
            except Exception:
                pass
    if not isinstance(out, dict):
        out = build()

    ids = out.get("ids") if isinstance(out, dict) else []
    nxt = out.get("next_cursor") if isinstance(out, dict) else None
    if nxt:
        response.headers["x-next-cursor"] = str(nxt)
    return _materialize_items(ids)

@router.get("/search-all")
def search_all(query: str, db: Session = Depends(get_read_db)):
    q = str(query or "").strip()
    if not q:
        return {"users": [], "posts": []}

    def _build():
        rows_u = (
            db.query(
                User.id,
                User.username,
                User.email,
                User.phone,
                User.nickname,
                User.avatar,
                User.background,
                User.bio,
                User.gender,
                User.birthday,
                User.location,
                User.followers_count,
                User.following_count,
                User.likes_received_count,
                User.is_active,
                User.aiseek_id,
                User.submit_banned_until,
                User.is_superuser,
                User.reputation_score,
            )
            .filter((User.nickname.contains(q)) | (User.username.contains(q)) | (User.aiseek_id == q))
            .limit(5)
            .all()
        )
        users_out = []
        for r in rows_u or []:
            try:
                ban_until = r[16]
                ban_until_out = ban_until.isoformat() if ban_until is not None and hasattr(ban_until, "isoformat") else None
            except Exception:
                ban_until_out = None
            active = r[14]
            if active is None:
                active = True
            users_out.append(
                {
                    "id": int(r[0] or 0),
                    "username": r[1],
                    "email": r[2],
                    "phone": r[3],
                    "nickname": r[4] or r[1],
                    "avatar": r[5],
                    "background": r[6],
                    "bio": r[7],
                    "gender": r[8],
                    "birthday": r[9],
                    "location": r[10],
                    "followers_count": int(r[11] or 0),
                    "following_count": int(r[12] or 0),
                    "likes_received_count": int(r[13] or 0),
                    "aiseek_id": r[15],
                    "is_active": bool(active),
                    "is_superuser": bool(r[17]),
                    "reputation_score": int(r[18] or 0),
                    "submit_banned_until": ban_until_out,
                }
            )
        rows_p = (
            db.query(Post.id)
            .filter(
                (Post.title.contains(q)) |
                (Post.content_text.contains(q)) |
                (Post.category.contains(q))
            )
            .filter(Post.status == "done")
            .limit(20)
            .all()
        )
        posts_out = []
        for r in rows_p or []:
            try:
                posts_out.append(int(r[0]))
            except Exception:
                pass
        return {"users": users_out, "posts": posts_out}

    try:
        from app.core.cache import stable_sig

        key = f"search:all:v2:{stable_sig(['q', q.lower()])}"
        out = cache.get_or_set_json(key, ttl=8, builder=_build, lock_ttl=2)
    except Exception:
        out = _build()
    if not isinstance(out, dict):
        return {"users": [], "posts": []}
    users_v = out.get("users")
    posts_v = out.get("posts")
    return {
        "users": users_v if isinstance(users_v, list) else [],
        "posts": posts_v if isinstance(posts_v, list) else [],
    }

@router.post("/update-profile")
def update_profile(data: ProfileUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    uid = int(getattr(current_user, "id", 0) or 0)
    if uid <= 0:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if int(data.user_id) != uid:
        raise HTTPException(status_code=403, detail="forbidden")
    user = db.query(User).filter(User.id == data.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if data.nickname is not None: user.nickname = data.nickname
    if data.bio is not None: user.bio = data.bio
    if data.gender is not None: user.gender = data.gender
    if data.birthday is not None: user.birthday = data.birthday
    if data.location is not None: user.location = data.location
    if data.avatar is not None: user.avatar = data.avatar
    if data.background is not None: user.background = data.background
    
    db.commit()
    db.refresh(user)
    return {"status": "ok", "user": user_to_dict(user)}

@router.post("/update-contact")
def update_contact(data: ContactUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    uid = int(getattr(current_user, "id", 0) or 0)
    if uid <= 0:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if int(data.user_id) != uid:
        raise HTTPException(status_code=403, detail="forbidden")
    user = db.query(User).filter(User.id == data.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    phone = (data.phone or '').strip() or None
    email = (data.email or '').strip() or None

    if phone:
        exists = db.query(User).filter(User.phone == phone, User.id != user.id).first()
        if exists:
            raise HTTPException(status_code=400, detail="Phone already registered")
    if email:
        exists = db.query(User).filter(User.email == email, User.id != user.id).first()
        if exists:
            raise HTTPException(status_code=400, detail="Email already registered")

    user.phone = phone
    user.email = email
    db.commit()
    db.refresh(user)
    return {"status": "ok", "user": user_to_dict(user)}

@router.post("/change-password")
def change_password(data: PasswordChange, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    uid = int(getattr(current_user, "id", 0) or 0)
    if uid <= 0:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if int(data.user_id) != uid:
        raise HTTPException(status_code=403, detail="forbidden")
    user = db.query(User).filter(User.id == data.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Mock hash check
    if user.password_hash != data.old_password + "_hashed":
         # Allow plain text for older test accounts
         if user.password_hash != data.old_password:
             raise HTTPException(status_code=400, detail="Old password incorrect")
        
    user.password_hash = data.new_password + "_hashed"
    db.commit()
    return {"status": "ok", "message": "Password updated"}

@router.post("/follow")
def follow_user(data: FollowRequest, current_user: User = Depends(get_current_user_optional), db: Session = Depends(get_db)):
    uid = int(getattr(current_user, "id", 0) or 0) if current_user else 0
    if uid <= 0:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if int(data.user_id or 0) and int(data.user_id) != int(uid):
        raise HTTPException(status_code=403, detail="forbidden")
    if uid == int(data.target_id):
        raise HTTPException(status_code=400, detail="Cannot follow yourself")
        
    existing = db.query(Follow).filter(Follow.follower_id == uid, Follow.following_id == data.target_id).first()
    if existing:
        # Unfollow logic if toggle desired, or just return
        db.delete(existing)
        msg = "Unfollowed"
        # Decrement
        me = db.query(User).filter(User.id == uid).first()
        target = db.query(User).filter(User.id == data.target_id).first()
        if me and me.following_count > 0: me.following_count -= 1
        if target and target.followers_count > 0: target.followers_count -= 1
    else:
        # Follow
        follow = Follow(follower_id=uid, following_id=data.target_id)
        db.add(follow)
        msg = "Followed"
        # Increment
        me = db.query(User).filter(User.id == uid).first()
        target = db.query(User).filter(User.id == data.target_id).first()
        if me: 
            if me.following_count is None: me.following_count = 0
            me.following_count += 1
        if target: 
            if target.followers_count is None: target.followers_count = 0
            target.followers_count += 1
            
    db.commit()

    try:
        if msg == "Followed":
            from app.services.notification_service import build_actor, emit_notification_event, now_ts

            actor = db.query(User).filter(User.id == uid).first()
            payload = {
                "type": "follow",
                "created_at": now_ts(),
                "actor": build_actor(actor),
                "text": f"{(actor.nickname if actor else None) or (actor.username if actor else None) or f'用户{uid}'} 关注了你",
            }
            key = f"follow:{uid}:{data.target_id}:{int(payload['created_at']*1000)}"
            emit_notification_event(db, user_id=data.target_id, event_type="follow", event_key=key, payload=payload)
    except Exception:
        pass
    return {"status": "ok", "message": msg}

# --- Friend Requests ---

@router.post("/friend-request/send")
def send_friend_request(data: FriendReqCreate, db: Session = Depends(get_db)):
    # Check if already friends (mutual follow)
    f1 = db.query(Follow).filter(Follow.follower_id == data.from_user_id, Follow.following_id == data.to_user_id).first()
    f2 = db.query(Follow).filter(Follow.follower_id == data.to_user_id, Follow.following_id == data.from_user_id).first()
    if f1 and f2:
        return {"status": "error", "message": "Already friends"}

    # Check pending
    existing = db.query(FriendRequest).filter(
        FriendRequest.sender_id == data.from_user_id,
        FriendRequest.receiver_id == data.to_user_id,
        FriendRequest.status == "pending"
    ).first()
    
    if existing:
        return {"status": "error", "message": "Request already pending"}
        
    req = FriendRequest(sender_id=data.from_user_id, receiver_id=data.to_user_id, status='pending')
    db.add(req)
    db.commit()
    try:
        from app.services.notification_service import build_actor, emit_notification_event

        sender = db.query(User).filter(User.id == data.from_user_id).first()
        sender_name = (sender.nickname if sender else None) or (sender.username if sender else None) or f"用户{data.from_user_id}"
        payload = {
            "type": "friend_request",
            "created_at": req.created_at.timestamp() if getattr(req, "created_at", None) else datetime.datetime.utcnow().timestamp(),
            "request_id": req.id,
            "status": req.status,
            "actor": build_actor(sender),
            "text": f"{sender_name} 请求添加你为好友",
        }
        emit_notification_event(db, user_id=data.to_user_id, event_type="friend_request", event_key=f"friend_request:{req.id}", payload=payload)
    except Exception:
        pass
    return {"status": "ok", "message": "Request sent"}

@router.get("/friend-request/list")
def get_friend_requests(user_id: int, db: Session = Depends(get_db)):
    reqs = db.query(FriendRequest).filter(FriendRequest.receiver_id == user_id, FriendRequest.status == "pending").all()
    sender_ids = [int(r.sender_id) for r in reqs if r and getattr(r, "sender_id", None) is not None]
    if not sender_ids:
        return []
    users = db.query(User.id, User.nickname, User.username).filter(User.id.in_(sender_ids)).all()
    by_id = {int(uid): (str(nn or ""), str(un or "")) for uid, nn, un in users}
    out = []
    for r in reqs:
        sid = int(getattr(r, "sender_id", 0) or 0)
        hit = by_id.get(sid)
        if not hit:
            continue
        nn, un = hit
        out.append({
            "id": r.id,
            "from_user_id": sid,
            "sender_nickname": nn or un,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "status": r.status
        })
    return out

@router.post("/friend-request/handle")
def handle_friend_request(data: FriendReqAction, db: Session = Depends(get_db)):
    req = db.query(FriendRequest).filter(FriendRequest.id == data.request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
        
    req.status = data.status # accepted / rejected
    
    if data.status == 'accepted':
        # Mutual follow
        f1 = Follow(follower_id=req.sender_id, following_id=req.receiver_id)
        f2 = Follow(follower_id=req.receiver_id, following_id=req.sender_id)
        
        # Check existing
        if not db.query(Follow).filter(Follow.follower_id==req.sender_id, Follow.following_id==req.receiver_id).first():
            db.add(f1)
        if not db.query(Follow).filter(Follow.follower_id==req.receiver_id, Follow.following_id==req.sender_id).first():
            db.add(f2)
            
    db.commit()
    return {"status": "ok", "message": f"Request {data.status}"}

@router.get("/{user_id}/following")
def list_following(
    user_id: int,
    response: Response,
    limit: Optional[int] = None,
    cursor: Optional[str] = None,
    db: Session = Depends(get_read_db),
):
    from sqlalchemy import and_, or_

    from app.utils.cursor import decode_cursor, encode_cursor, cursor_datetime

    base_query = db.query(Follow).filter(Follow.follower_id == user_id)
    if not cursor:
        _set_total_count_cached(response, f"cnt:following:{int(user_id)}", lambda: base_query.count())

    cur = decode_cursor(cursor)
    cur_dt = cursor_datetime(cur, "created_at")
    cur_id = cur.get("id") if isinstance(cur, dict) else None
    q = base_query
    if cur_dt is not None and isinstance(cur_id, int):
        q = q.filter(or_(Follow.created_at < cur_dt, and_(Follow.created_at == cur_dt, Follow.following_id < cur_id)))

    lim = int(limit or 200)
    if lim < 1:
        lim = 1
    if lim > 500:
        lim = 500

    rows = q.order_by(Follow.created_at.desc(), Follow.following_id.desc()).limit(lim).all()
    if rows:
        last = rows[-1]
        if getattr(last, "created_at", None) is not None:
            response.headers["x-next-cursor"] = encode_cursor({"created_at": float(last.created_at.timestamp()), "id": int(last.following_id)})

    ids = [int(r.following_id) for r in rows if r and getattr(r, "following_id", None) is not None]
    if not ids:
        return []

    users = db.query(User).filter(User.id.in_(ids)).all()
    by_id = {int(u.id): u for u in users if u}
    return [user_to_dict(by_id[i]) for i in ids if i in by_id]

@router.get("/{user_id}/followers")
def list_followers(
    user_id: int,
    response: Response,
    limit: Optional[int] = None,
    cursor: Optional[str] = None,
    db: Session = Depends(get_read_db),
):
    from sqlalchemy import and_, or_

    from app.utils.cursor import decode_cursor, encode_cursor, cursor_datetime

    base_query = db.query(Follow).filter(Follow.following_id == user_id)
    if not cursor:
        _set_total_count_cached(response, f"cnt:followers:{int(user_id)}", lambda: base_query.count())

    cur = decode_cursor(cursor)
    cur_dt = cursor_datetime(cur, "created_at")
    cur_id = cur.get("id") if isinstance(cur, dict) else None
    q = base_query
    if cur_dt is not None and isinstance(cur_id, int):
        q = q.filter(or_(Follow.created_at < cur_dt, and_(Follow.created_at == cur_dt, Follow.follower_id < cur_id)))

    lim = int(limit or 200)
    if lim < 1:
        lim = 1
    if lim > 500:
        lim = 500

    rows = q.order_by(Follow.created_at.desc(), Follow.follower_id.desc()).limit(lim).all()
    if rows:
        last = rows[-1]
        if getattr(last, "created_at", None) is not None:
            response.headers["x-next-cursor"] = encode_cursor({"created_at": float(last.created_at.timestamp()), "id": int(last.follower_id)})

    ids = [int(r.follower_id) for r in rows if r and getattr(r, "follower_id", None) is not None]
    if not ids:
        return []

    users = db.query(User).filter(User.id.in_(ids)).all()
    by_id = {int(u.id): u for u in users if u}
    return [user_to_dict(by_id[i]) for i in ids if i in by_id]

@router.get("/friends/list")
def list_friends(user_id: int, db: Session = Depends(get_read_db)):
    """Return mutual follows (friends) for the given user."""
    f2 = db.query(Follow.follower_id.label("uid")).filter(Follow.following_id == user_id).subquery()
    rows = db.query(Follow.following_id).join(f2, f2.c.uid == Follow.following_id).filter(Follow.follower_id == user_id).all()
    mutual_ids = [int(x[0]) for x in rows if x and x[0] is not None]
    if not mutual_ids:
        return []
    users = db.query(User).filter(User.id.in_(mutual_ids)).all()
    by_id = {int(u.id): u for u in users if u}
    return [user_to_dict(by_id[i]) for i in mutual_ids if i in by_id]
