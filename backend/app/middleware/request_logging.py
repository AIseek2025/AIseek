import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware

from app.core.request_context import set_request_context, set_user_id


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        start = time.perf_counter()
        rid = request.headers.get("x-request-id") or request.headers.get("X-Request-Id")
        if not rid:
            rid = uuid.uuid4().hex
        sid = request.headers.get("x-session-id")
        ip = request.client.host if request.client else None

        try:
            set_request_context(rid, sid)
        except Exception:
            pass
        try:
            auth = request.headers.get("authorization") or request.headers.get("Authorization")
            if auth and str(auth).startswith("Bearer "):
                tok = str(auth).replace("Bearer ", "").strip()
                uid = None
                if tok.startswith("fake-token-"):
                    try:
                        uid = int(tok.split("fake-token-")[1])
                    except Exception:
                        uid = None
                else:
                    try:
                        from app.core.security import decode_access_token

                        payload = decode_access_token(tok)
                        if payload and payload.get("sub"):
                            uid = int(payload.get("sub"))
                    except Exception:
                        uid = None
                set_user_id(uid)
        except Exception:
            pass

        response = None

        try:
            response = await call_next(request)
            return response
        finally:
            try:
                if response is not None:
                    response.headers["x-request-id"] = str(rid)
                    if sid:
                        response.headers["x-session-id"] = str(sid)
            except Exception:
                pass
            latency_ms = int((time.perf_counter() - start) * 1000)
            status = getattr(response, "status_code", None) if response is not None else None
            logger = logging.getLogger("aiseek.access")
            logger.info(
                "request",
                extra={
                    "request_id": rid,
                    "session_id": sid,
                    "method": request.method,
                    "path": request.url.path,
                    "status": status,
                    "latency_ms": latency_ms,
                    "ip": ip,
                },
            )
