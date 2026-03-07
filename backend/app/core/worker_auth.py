from __future__ import annotations

from typing import Optional, Tuple

from fastapi import HTTPException, Request


def _ensure_worker_secret_configured(secret: str) -> None:
    from app.core.config import settings

    if getattr(settings, "READINESS_STRICT", False) and str(secret or "") == "m3pro_worker_2026":
        raise HTTPException(status_code=500, detail="misconfigured_worker_secret")


async def verify_worker_request(
    request: Request,
    *,
    x_worker_ts: Optional[str] = None,
    x_worker_sig: Optional[str] = None,
    x_worker_secret: Optional[str] = None,
    require_signed: bool = False,
) -> Tuple[bool, bytes]:
    from app.core.config import settings
    import hmac
    import hashlib
    import time

    secret = str(getattr(settings, "WORKER_SECRET", "") or "")
    _ensure_worker_secret_configured(secret)

    raw = b""
    if x_worker_ts and x_worker_sig:
        try:
            ts = int(str(x_worker_ts).strip())
        except Exception:
            ts = 0
        now = int(time.time())
        window = int(getattr(settings, "WORKER_SIG_WINDOW_SEC", 300) or 300)
        if window < 30:
            window = 30
        if ts <= 0 or abs(now - ts) > window:
            raise HTTPException(status_code=401, detail="Unauthorized")
        raw = await request.body()
        msg = str(ts).encode("utf-8") + b"." + raw
        exp = hmac.new(secret.encode("utf-8"), msg=msg, digestmod=hashlib.sha256).hexdigest()
        if not hmac.compare_digest(exp, str(x_worker_sig).strip()):
            raise HTTPException(status_code=401, detail="Unauthorized")
        return True, raw

    if require_signed:
        raise HTTPException(status_code=401, detail="Unauthorized")

    if not x_worker_secret:
        raise HTTPException(status_code=401, detail="Unauthorized")
    import hmac as _hmac

    if not _hmac.compare_digest(str(x_worker_secret), secret):
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        raw = await request.body()
    except Exception:
        raw = b""
    return False, raw

