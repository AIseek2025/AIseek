from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.api.deps import get_current_user
from app.db.session import SessionLocalRead


class AuthRequiredMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, enabled: bool = True):
        super().__init__(app)
        self.enabled = bool(enabled)

    async def dispatch(self, request, call_next):
        if not self.enabled:
            return await call_next(request)

        path = request.url.path
        method = request.method.upper()

        if not path.startswith("/api/v1/"):
            return await call_next(request)

        if method not in {"POST", "PUT", "DELETE"}:
            return await call_next(request)

        if path.startswith("/api/v1/auth/"):
            return await call_next(request)

        if path == "/api/v1/observability/events":
            return await call_next(request)

        if path == "/api/v1/posts/callback":
            return await call_next(request)

        auth = request.headers.get("authorization") or request.headers.get("Authorization")
        if not auth:
            return JSONResponse({"detail": "Not authenticated"}, status_code=401)

        db = None
        try:
            db = SessionLocalRead()
            u = get_current_user(authorization=str(auth), db=db)
            uid = int(getattr(u, "id", 0) or 0)
            try:
                request.state.user_id = int(uid)
            except Exception:
                pass
        except Exception:
            return JSONResponse({"detail": "Invalid token"}, status_code=401)
        finally:
            try:
                if db:
                    db.close()
            except Exception:
                pass

        try:
            ctype = str(request.headers.get("content-type") or "").lower()
            if "application/json" in ctype:
                body = await request.body()
                if body:
                    try:
                        import json

                        obj = json.loads(body.decode("utf-8", errors="ignore") or "{}")
                    except Exception:
                        obj = None
                    if isinstance(obj, dict) and "user_id" in obj:
                        try:
                            buid = int(obj.get("user_id") or 0)
                        except Exception:
                            buid = 0
                        if buid and int(buid) != int(uid):
                            return JSONResponse({"detail": "forbidden"}, status_code=403)

                    async def receive():
                        return {"type": "http.request", "body": body, "more_body": False}

                    request._receive = receive  # noqa: SLF001
        except Exception:
            pass

        return await call_next(request)
