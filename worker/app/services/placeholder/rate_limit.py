from __future__ import annotations

import time
from typing import Optional

import redis


def _redis_client() -> Optional["redis.Redis"]:
    try:
        url = str((__import__("os").getenv("REDIS_URL") or __import__("os").getenv("CELERY_BROKER_URL") or "")).strip()
        if not url:
            url = "redis://localhost:6379/0"
        r = redis.Redis.from_url(url, decode_responses=True, socket_timeout=0.4, socket_connect_timeout=0.2)
        r.ping()
        return r
    except Exception:
        return None


def allow(provider: str, window_sec: int, limit: int) -> bool:
    p = str(provider or "").strip().lower()
    if not p:
        return True
    w = max(1, int(window_sec or 60))
    lim = max(1, int(limit or 1))
    r = _redis_client()
    if r is None:
        return True
    now = int(time.time())
    k = f"ph:rl:{p}:{now // w}"
    try:
        n = int(r.incr(k))
        if n == 1:
            r.expire(k, w + 3)
        return n <= lim
    except Exception:
        return True

