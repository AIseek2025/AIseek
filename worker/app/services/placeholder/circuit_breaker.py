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


def is_open(provider: str) -> bool:
    p = str(provider or "").strip().lower()
    if not p:
        return False
    r = _redis_client()
    if r is None:
        return False
    k = f"ph:cb:open_until:{p}"
    try:
        until = int(r.get(k) or 0)
        return until and int(time.time()) < until
    except Exception:
        return False


def mark_success(provider: str) -> None:
    p = str(provider or "").strip().lower()
    if not p:
        return
    r = _redis_client()
    if r is None:
        return
    try:
        r.delete(f"ph:cb:fail:{p}")
        r.delete(f"ph:cb:open_until:{p}")
    except Exception:
        return


def mark_failure(provider: str, *, hard: bool = False) -> None:
    p = str(provider or "").strip().lower()
    if not p:
        return
    r = _redis_client()
    if r is None:
        return
    try:
        fk = f"ph:cb:fail:{p}"
        n = int(r.incr(fk))
        if n == 1:
            r.expire(fk, 300)
        if hard or n >= 4:
            backoff = 60 if n < 6 else 180 if n < 10 else 600
            until = int(time.time()) + int(backoff)
            ok = r.set(f"ph:cb:open_until:{p}", str(until), ex=int(backoff), nx=True)
            if not ok:
                r.expire(f"ph:cb:open_until:{p}", int(backoff))
    except Exception:
        return

