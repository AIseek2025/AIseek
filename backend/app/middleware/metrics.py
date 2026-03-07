import time

from prometheus_client import Counter, Histogram
from starlette.middleware.base import BaseHTTPMiddleware


REQUESTS = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)

LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["method", "path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        start = time.perf_counter()
        response = None
        try:
            response = await call_next(request)
            return response
        finally:
            try:
                path = None
                try:
                    rt = request.scope.get("route")
                    path = getattr(rt, "path", None)
                except Exception:
                    path = None
                if not path:
                    path = request.url.path
                status = str(getattr(response, "status_code", 500))
                REQUESTS.labels(request.method, path, status).inc()
                LATENCY.labels(request.method, path).observe(time.perf_counter() - start)
            except Exception:
                pass
