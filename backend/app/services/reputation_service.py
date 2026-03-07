from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.all_models import Post, User, UserReputationEvent


def _now() -> datetime:
    return datetime.utcnow()


def is_violation_issues(issues: List[Dict[str, Any]]) -> bool:
    for it in issues or []:
        if not isinstance(it, dict):
            continue
        k = str(it.get("kind") or "")
        if k in {"illegal", "risk", "pii"}:
            return True
    return False


def effective_reputation_score(user: User, now: Optional[datetime] = None) -> int:
    t = now or _now()
    base_score = int(getattr(user, "reputation_score", 100) or 100)
    if base_score >= 100:
        return 100
    if base_score < 0:
        base_score = 0

    ban_until = getattr(user, "submit_banned_until", None)
    updated_at = getattr(user, "reputation_updated_at", None)
    if updated_at is None:
        updated_at = getattr(user, "created_at", None)
    if updated_at is None:
        updated_at = t

    base_time = updated_at
    if ban_until is not None and ban_until > base_time:
        base_time = ban_until

    days = (t.date() - base_time.date()).days
    if days <= 0:
        return int(base_score)
    return int(min(100, base_score + int(days)))


def _tier(score: int) -> str:
    s = int(score or 0)
    if s < 60:
        return "banned_permanent"
    if s < 70:
        return "banned_30d"
    if s < 80:
        return "banned_7d"
    if s == 90:
        return "banned_1d"
    if s < 100:
        return "limit_1_per_day"
    return "normal"


def _ensure_ban_until(user: User, now: datetime) -> None:
    s = int(getattr(user, "reputation_score", 100) or 100)
    cur = getattr(user, "submit_banned_until", None)
    if s < 60:
        user.submit_banned_until = now + timedelta(days=365 * 100)
        try:
            user.is_active = False
        except Exception:
            pass
        return
    if s < 70:
        cand = now + timedelta(days=30)
        if cur is None or cur < cand:
            user.submit_banned_until = cand
        return
    if s < 80:
        cand = now + timedelta(days=7)
        if cur is None or cur < cand:
            user.submit_banned_until = cand
        return
    if s == 90:
        cand = now + timedelta(days=1)
        if cur is None or cur < cand:
            user.submit_banned_until = cand
        return


def check_submit_allowed(db: Session, user: User) -> Tuple[bool, Optional[Dict[str, Any]]]:
    now = _now()
    score = effective_reputation_score(user, now)
    tier = _tier(score)

    until = getattr(user, "submit_banned_until", None)
    if until is not None and until > now:
        return False, {"kind": "banned", "until": until.isoformat(), "score": score}

    if tier == "limit_1_per_day":
        start = datetime(now.year, now.month, now.day)
        end = start + timedelta(days=1)
        n = int(
            db.query(Post.id)
            .filter(Post.user_id == int(user.id), Post.created_at >= start, Post.created_at < end)
            .count()
            or 0
        )
        if n >= 1:
            return False, {"kind": "daily_limit", "limit": 1, "score": score}

    if tier == "banned_permanent":
        return False, {"kind": "banned_permanent", "score": score}

    return True, None


def penalty_for_issues(issues: List[Dict[str, Any]]) -> int:
    if not is_violation_issues(issues):
        return 0
    return -10


def summarize_issues_cn(issues: List[Dict[str, Any]]) -> str:
    parts: List[str] = []
    for it in issues or []:
        if not isinstance(it, dict):
            continue
        k = str(it.get("kind") or "")
        if k == "empty":
            parts.append("内容为空")
        elif k == "too_long":
            parts.append("内容过长")
        elif k == "illegal":
            parts.append("包含违法内容")
        elif k == "risk":
            t = str(it.get("type") or "")
            if t == "porn":
                parts.append("包含色情内容")
            elif t == "violence":
                parts.append("包含暴力/危险内容")
            elif t == "hate":
                parts.append("包含仇恨/极端内容")
            elif t == "fraud":
                parts.append("包含诈骗/违法获利内容")
            else:
                parts.append("包含不合规内容")
        elif k == "pii":
            parts.append("包含个人敏感信息")
        elif k == "irrelevant":
            parts.append("不符合可创作视频的内容范围")
        else:
            parts.append("内容不合规")
    out = "；".join([p for p in parts if p])
    return out or "内容不合规"


def apply_penalty(db: Session, user: User, post_id: Optional[int], issues: List[Dict[str, Any]]) -> int:
    now = _now()
    before = effective_reputation_score(user, now)
    delta = penalty_for_issues(issues)
    after = max(0, min(100, before + int(delta)))
    user.reputation_score = int(after)
    user.reputation_updated_at = now
    _ensure_ban_until(user, now)
    ev = UserReputationEvent(
        user_id=int(user.id),
        post_id=int(post_id) if post_id is not None else None,
        delta=int(delta),
        score_after=int(after),
        reasons={"issues": issues or []},
    )
    db.add(ev)
    db.commit()
    return int(after)


def set_reputation_manual(
    db: Session,
    user: User,
    new_score: int,
    admin_user_id: Optional[int] = None,
    reason: Optional[str] = None,
    clear_ban: bool = True,
    reactivate: bool = True,
) -> int:
    now = _now()
    before_eff = effective_reputation_score(user, now)
    score = max(0, min(100, int(new_score)))
    user.reputation_score = int(score)
    user.reputation_updated_at = now
    if clear_ban:
        try:
            user.submit_banned_until = None
        except Exception:
            pass
    if reactivate and score >= 60:
        try:
            user.is_active = True
        except Exception:
            pass
    _ensure_ban_until(user, now)
    after_eff = effective_reputation_score(user, now)
    ev = UserReputationEvent(
        user_id=int(user.id),
        post_id=None,
        delta=int(after_eff - before_eff),
        score_after=int(after_eff),
        reasons={"manual": True, "admin_user_id": int(admin_user_id) if admin_user_id is not None else None, "reason": str(reason or "").strip() or None},
    )
    db.add(ev)
    db.commit()
    return int(after_eff)
