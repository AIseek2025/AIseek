from celery import Celery, Task

from app.core.cache import cache
from app.core.config import get_settings
from app.core.request_context import get_request_id, get_session_id, set_request_context


def make_celery() -> Celery:
    s = get_settings()
    broker = s.CELERY_BROKER_URL or s.REDIS_URL
    backend = s.CELERY_RESULT_BACKEND or s.CELERY_BROKER_URL
    eager = False
    env = str(getattr(s, "ENV", "dev") or "dev").lower()
    allow_eager_fallback = env not in {"prod", "production"}
    try:
        if str(broker).startswith("redis://"):
            import redis

            r = redis.Redis.from_url(
                s.REDIS_URL,
                decode_responses=True,
                socket_timeout=float(getattr(s, "REDIS_SOCKET_TIMEOUT_SEC", 0.6) or 0.6),
                socket_connect_timeout=float(getattr(s, "REDIS_CONNECT_TIMEOUT_SEC", 0.3) or 0.3),
                max_connections=int(getattr(s, "REDIS_MAX_CONNECTIONS", 200) or 200),
            )
            r.ping()
    except Exception:
        if allow_eager_fallback:
            broker = "memory://"
            backend = "cache+memory://"
            eager = True

    class ContextTask(Task):
        abstract = True

        def __call__(self, *args, **kwargs):
            try:
                h = getattr(getattr(self, "request", None), "headers", None) or {}
                rid = h.get("x-request-id") if isinstance(h, dict) else None
                sid = h.get("x-session-id") if isinstance(h, dict) else None
                set_request_context(rid, sid)
            except Exception:
                pass

            tracer = None
            ctx = None
            try:
                from opentelemetry import trace
                from opentelemetry.propagate import extract

                h2 = getattr(getattr(self, "request", None), "headers", None) or {}
                if isinstance(h2, dict):
                    ctx = extract(h2)
                tracer = trace.get_tracer("aiseek.celery")
            except Exception:
                tracer = None

            if tracer and ctx is not None:
                try:
                    with tracer.start_as_current_span(f"celery.{self.name}", context=ctx):
                        return self.run(*args, **kwargs)
                except Exception:
                    return self.run(*args, **kwargs)

            return self.run(*args, **kwargs)

    celery = Celery(
        "aiseek",
        broker=broker,
        backend=backend,
        task_cls=ContextTask,
        include=[
            "app.tasks.ai_creation",
            "app.tasks.search_index",
            "app.tasks.counters",
            "app.tasks.reco_profile",
            "app.tasks.transcode",
            "app.tasks.dirty_flush",
            "app.tasks.client_events",
            "app.tasks.notification_backfill",
        ],
    )

    celery.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        task_track_started=True,
        task_time_limit=60 * 30,
        broker_connection_retry_on_startup=True,
        worker_prefetch_multiplier=1,
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        result_expires=60 * 60,
        broker_transport_options={
            "visibility_timeout": 60 * 60,
        },
        task_always_eager=bool(eager),
        task_ignore_result=bool(eager),
    )

    return celery


celery_app = make_celery()


def apply_async_with_context(
    task,
    args=None,
    kwargs=None,
    *,
    dedupe_key: str = "",
    dedupe_ttl: int = 0,
    queue: str = "",
    countdown: int = 0,
    max_queue_depth: int = 0,
    drop_when_overloaded: bool = False,
):
    if dedupe_key:
        ttl = int(dedupe_ttl or 0)
        if ttl < 1:
            ttl = 1
        if ttl > 3600:
            ttl = 3600
        try:
            if not cache.set_nx(f"celery:dedupe:{str(dedupe_key)}", "1", ttl=ttl):
                return None
        except Exception:
            pass
    headers = {}
    rid = get_request_id()
    sid = get_session_id()
    if rid:
        headers["x-request-id"] = rid
    if sid:
        headers["x-session-id"] = sid
    try:
        import os

        if os.getenv("ENABLE_TRACING", "0") in {"1", "true", "TRUE", "yes", "YES"}:
            from opentelemetry.propagate import inject

            inject(headers)
    except Exception:
        pass
    try:
        s = get_settings()
    except Exception:
        s = None
    q = str(queue or (getattr(s, "CELERY_DEFAULT_QUEUE", "ai") if s is not None else "ai") or "ai")
    if drop_when_overloaded and int(max_queue_depth or 0) > 0:
        try:
            md = int(max_queue_depth or 0)
            if md < 100:
                md = 100
            if md > 1000000:
                md = 1000000
            r = cache.redis()
            if r:
                depth = int(r.llen(q) or 0)
                if depth >= md:
                    return None
        except Exception:
            pass
    try:
        opts = {}
        opts["queue"] = q
        if countdown and int(countdown) > 0:
            opts["countdown"] = int(countdown)
        if headers:
            return task.apply_async(args=args or [], kwargs=kwargs or {}, headers=headers, **opts)
        return task.apply_async(args=args or [], kwargs=kwargs or {}, **opts)
    except Exception as e:
        print(f"ERROR in apply_async_with_context: {e}")
        import traceback
        traceback.print_exc()
        return None
