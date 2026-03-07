from starlette.middleware.base import BaseHTTPMiddleware

from app.core.request_context import get_canary, get_request_id, get_session_id, get_user_id


class TracingContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        try:
            from opentelemetry import trace

            span = trace.get_current_span()
            if span is not None:
                try:
                    rid = get_request_id()
                    if rid:
                        span.set_attribute("app.request_id", str(rid))
                except Exception:
                    pass
                try:
                    sid = get_session_id()
                    if sid:
                        span.set_attribute("app.session_id", str(sid))
                except Exception:
                    pass
                try:
                    uid = get_user_id()
                    if uid is not None:
                        span.set_attribute("app.user_id", int(uid))
                except Exception:
                    pass
                try:
                    c = get_canary()
                    if c is not None:
                        span.set_attribute("app.canary", bool(c))
                except Exception:
                    pass
        except Exception:
            pass
        return await call_next(request)

