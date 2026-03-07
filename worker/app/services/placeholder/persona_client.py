from __future__ import annotations

import time
from typing import Optional

import requests

from app.core.config import settings


_CACHE = {}


def _cache_get(uid: int) -> Optional[list]:
    try:
        it = _CACHE.get(int(uid))
        if not it:
            return None
        ts, tags = it
        if int(time.time()) - int(ts) > 300:
            return None
        return tags
    except Exception:
        return None


def _cache_set(uid: int, tags: list) -> None:
    try:
        _CACHE[int(uid)] = (int(time.time()), tags)
    except Exception:
        return


def fetch_persona_tags(user_id: int) -> list[str]:
    uid = int(user_id or 0)
    if uid <= 0:
        return []
    cached = _cache_get(uid)
    if cached is not None:
        return [str(x) for x in cached if str(x).strip()]
    base = str(getattr(settings, "web_url", "") or "").strip()
    secret = str(getattr(settings, "worker_secret", "") or "").strip()
    if not base or not secret:
        return []
    url = f"{base.rstrip('/')}/api/v1/ai/worker/users/{uid}/persona-tags"
    try:
        r = requests.get(url, headers={"x-worker-secret": secret, "user-agent": "AIseekWorker/1.0"}, timeout=8)
        if r.status_code != 200:
            return []
        obj = r.json()
        tags = obj.get("tags") if isinstance(obj, dict) else None
        if not isinstance(tags, list):
            return []
        out = [str(x).strip() for x in tags if str(x).strip()]
        _cache_set(uid, out)
        return out
    except Exception:
        return []

