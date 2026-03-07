from __future__ import annotations

import time
from typing import Any, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

pwd_context = CryptContext(schemes=["pbkdf2_sha256", "bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bool(pwd_context.verify(plain_password or "", hashed_password or ""))
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    return str(pwd_context.hash(password or ""))


def create_access_token(*, subject: str, expires_minutes: Optional[int] = None, extra: Optional[dict[str, Any]] = None) -> str:
    s = get_settings()
    now = int(time.time())
    exp_min = int(expires_minutes if expires_minutes is not None else int(getattr(s, "ACCESS_TOKEN_EXPIRE_MINUTES", 60 * 24 * 7) or 0))
    if exp_min < 1:
        exp_min = 60
    to_encode: dict[str, Any] = {"sub": str(subject), "iat": now, "exp": now + exp_min * 60}
    if extra and isinstance(extra, dict):
        for k, v in extra.items():
            if k in {"sub", "iat", "exp"}:
                continue
            to_encode[str(k)] = v
    alg = str(getattr(s, "JWT_ALGORITHM", "HS256") or "HS256")
    return str(jwt.encode(to_encode, str(s.SECRET_KEY), algorithm=alg))


def decode_access_token(token: str) -> Optional[dict[str, Any]]:
    if not token:
        return None
    s = get_settings()
    alg = str(getattr(s, "JWT_ALGORITHM", "HS256") or "HS256")
    try:
        payload = jwt.decode(token, str(s.SECRET_KEY), algorithms=[alg])
        if not isinstance(payload, dict):
            return None
        return payload
    except JWTError:
        return None
