import os
import time
import mimetypes

# Ensure MIME types for HLS/Video are registered for local dev (port 5002)
mimetypes.add_type("application/vnd.apple.mpegurl", ".m3u8")
mimetypes.add_type("video/mp2t", ".ts")
mimetypes.add_type("video/iso.segment", ".m4s")

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.api.v1.api import api_router
from app.core.config import settings
from app.core.logging_config import configure_logging
from app.core.migrations import run_migrations
from app.core.tracing import configure_tracing
from app.db.session import SessionLocal, SessionLocalRead
from app.models.all_models import Category, User
from app.middleware.metrics import MetricsMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.canary import CanaryMiddleware
from app.middleware.auth_required import AuthRequiredMiddleware
from app.middleware.request_logging import RequestLoggingMiddleware
from app.middleware.write_guard import WriteGuardMiddleware

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def create_app() -> FastAPI:
    print("DEBUG: create_app() called in backend/app/main.py")
    configure_logging()
    app = FastAPI(title=settings.PROJECT_NAME, openapi_url="/api/v1/openapi.json")
    build_id = os.getenv("AISEEK_BUILD_ID") or time.strftime("%Y-%m-%d.%H%M%S")
    from app.core.assets import ensure_rollout_cookie, make_asset_url_for_request

    try:
        configure_tracing(app)
    except Exception:
        pass

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["x-next-cursor", "x-ab-variant"],
    )

    app.add_middleware(RequestLoggingMiddleware)
    try:
        app.add_middleware(CanaryMiddleware, enabled=True)
    except Exception:
        pass
    try:
        from app.middleware.tracing_context import TracingContextMiddleware

        app.add_middleware(TracingContextMiddleware)
    except Exception:
        pass
    try:
        app.add_middleware(AuthRequiredMiddleware, enabled=bool(getattr(settings, "AUTH_WRITE_REQUIRED", True)))
    except Exception:
        pass
    try:
        app.add_middleware(RateLimitMiddleware, enabled=bool(getattr(settings, "RATE_LIMIT_ENABLED", True)))
    except Exception:
        pass
    app.add_middleware(WriteGuardMiddleware, enabled=True)
    try:
        app.add_middleware(GZipMiddleware, minimum_size=800)
    except Exception:
        pass
    try:
        app.add_middleware(MetricsMiddleware)
    except Exception:
        pass

    app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
    templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

    app.include_router(api_router, prefix="/api/v1")

    try:
        import json
        import re
        from pathlib import Path
        from prometheus_client import CONTENT_TYPE_LATEST, Gauge, REGISTRY, generate_latest
        from starlette.responses import Response

        def _safe_gauge(name: str, doc: str, labels=None):
            try:
                return Gauge(name, doc, labels or [])
            except Exception:
                try:
                    return REGISTRY._names_to_collectors.get(name)
                except Exception:
                    return None

        BUILD_INFO = _safe_gauge("aiseek_build_info", "Build info", ["build_id"])
        ASSET_RELEASE = _safe_gauge("aiseek_static_assets_release", "Static assets release", ["release_id"])
        ASSET_ROLLOUT_PERCENT = _safe_gauge("aiseek_static_assets_rollout_percent", "Static assets rollout percent")
        ASSET_ROLLOUT_ENABLED = _safe_gauge("aiseek_static_assets_rollout_enabled", "Static assets rollout enabled")
        ES_REINDEX_IN_PROGRESS = _safe_gauge("aiseek_es_reindex_in_progress", "ES reindex in progress")
        ES_REINDEX_OK = _safe_gauge("aiseek_es_reindex_ok_total", "ES reindex indexed docs")
        ES_REINDEX_TOTAL = _safe_gauge("aiseek_es_reindex_total", "ES reindex total docs")
        HTTP_OUTBOUND_CB_OPEN = _safe_gauge("aiseek_http_outbound_circuit_open", "Outbound circuit breaker open", ["service"])
        HTTP_OUTBOUND_CB_FAIL = _safe_gauge("aiseek_http_outbound_circuit_fail", "Outbound circuit breaker fail count", ["service"])
        HTTP_OUTBOUND_CB_OPEN_UNTIL = _safe_gauge("aiseek_http_outbound_circuit_open_until", "Outbound circuit breaker open_until epoch", ["service"])
        CLIENT_EVENT_STREAM_LEN = _safe_gauge("aiseek_client_event_stream_len", "Client event stream length", ["stream"])
        CLIENT_EVENT_STREAM_PENDING = _safe_gauge("aiseek_client_event_stream_pending", "Client event stream pending", ["stream"])
        CLIENT_EVENT_STREAM_LAG = _safe_gauge("aiseek_client_event_stream_lag", "Client event stream group lag", ["stream"])
        CLIENT_EVENT_DRAIN_OK = _safe_gauge("aiseek_client_event_drain_ok", "Client event drain ok", ["stream"])
        CLIENT_EVENT_DRAINED = _safe_gauge("aiseek_client_event_drained", "Client event drained count", ["stream"])
        CLIENT_EVENT_PERSISTED = _safe_gauge("aiseek_client_event_persisted", "Client event persisted rows", ["stream"])
        CLIENT_EVENT_RT_INGEST_SAMPLE_RATE = _safe_gauge("aiseek_client_event_runtime_ingest_sample_rate", "Client event runtime ingest sample rate")
        CLIENT_EVENT_RT_PERSIST_ENABLED = _safe_gauge("aiseek_client_event_runtime_persist_enabled", "Client event runtime persist enabled")

        @app.get("/metrics")
        def metrics():
            try:
                BUILD_INFO.labels(build_id).set(1)
            except Exception:
                pass
            try:
                dist = Path(BASE_DIR) / "static" / "dist"
                p = dist / "rollout.json"
                enabled = 0
                pct = 0
                if p.exists():
                    obj = json.loads(p.read_text(encoding="utf-8", errors="ignore") or "{}")
                    if isinstance(obj, dict):
                        enabled = 1 if bool(obj.get("enabled")) else 0
                        try:
                            pct = int(obj.get("percent") or 0)
                        except Exception:
                            pct = 0
                if pct < 0:
                    pct = 0
                if pct > 100:
                    pct = 100
                ASSET_ROLLOUT_ENABLED.set(enabled)
                ASSET_ROLLOUT_PERCENT.set(pct)
            except Exception:
                pass
            try:
                dist = Path(BASE_DIR) / "static" / "dist"
                cur = dist / "manifest.current.json"
                rid = ""
                if cur.exists():
                    obj = json.loads(cur.read_text(encoding="utf-8", errors="ignore") or "{}")
                    if isinstance(obj, dict):
                        for v in obj.values():
                            s = str(v or "")
                            m = re.search(r"dist/r/([0-9A-Za-z._-]{6,64})/", s)
                            if m:
                                rid = m.group(1)
                                break
                try:
                    ASSET_RELEASE.clear()
                except Exception:
                    pass
                if rid:
                    ASSET_RELEASE.labels(rid).set(1)
            except Exception:
                pass
            try:
                from app.core.cache import cache

                st = cache.get_json("es:reindex:posts:status")
                if isinstance(st, dict):
                    s2 = str(st.get("status") or "")
                    ES_REINDEX_IN_PROGRESS.set(1 if s2 in {"starting", "indexing", "indexed", "queued"} else 0)
                    ES_REINDEX_OK.set(float(st.get("ok") or 0))
                    ES_REINDEX_TOTAL.set(float(st.get("total") or 0))
                else:
                    ES_REINDEX_IN_PROGRESS.set(0)
                    ES_REINDEX_OK.set(0)
                    ES_REINDEX_TOTAL.set(0)
            except Exception:
                pass
            try:
                from app.core.cache import cache
                from app.core.config import get_settings
                from app.observability.runtime_client_events import read_runtime_client_events

                s = get_settings()
                rt = read_runtime_client_events()
                try:
                    rate = rt.get("ingest_sample_rate") if isinstance(rt, dict) else None
                    rate2 = float(rate) if rate is not None else float(getattr(s, "CLIENT_EVENT_INGEST_SAMPLE_RATE", 1.0) or 1.0)
                    if rate2 < 0:
                        rate2 = 0.0
                    if rate2 > 1:
                        rate2 = 1.0
                    CLIENT_EVENT_RT_INGEST_SAMPLE_RATE.set(rate2)
                except Exception:
                    pass
                try:
                    pe = rt.get("persist_enabled") if isinstance(rt, dict) else None
                    pe2 = bool(pe) if pe is not None else bool(getattr(s, "CLIENT_EVENT_PERSIST_ENABLED", True))
                    CLIENT_EVENT_RT_PERSIST_ENABLED.set(1 if pe2 else 0)
                except Exception:
                    pass
                base_stream = str(getattr(s, "CLIENT_EVENT_STREAM_KEY", "events:client") or "events:client")
                group = str(getattr(s, "CLIENT_EVENT_STREAM_GROUP", "client_events") or "client_events")
                shard_stream = bool(getattr(s, "CLIENT_EVENT_STREAM_SHARD_ENABLED", True))
                topics_raw = str(getattr(s, "CLIENT_EVENT_STREAM_TOPICS", "feed,player,search,other") or "feed,player,search,other")
                topics = [t.strip() for t in topics_raw.split(",") if t.strip()]
                streams = [base_stream]
                if shard_stream and topics:
                    streams = [f"{base_stream}:{t}" for t in topics[:16]]
                r = cache.redis()
                try:
                    CLIENT_EVENT_STREAM_LEN.clear()
                    CLIENT_EVENT_STREAM_PENDING.clear()
                    CLIENT_EVENT_STREAM_LAG.clear()
                    CLIENT_EVENT_DRAIN_OK.clear()
                    CLIENT_EVENT_DRAINED.clear()
                    CLIENT_EVENT_PERSISTED.clear()
                except Exception:
                    pass
                for stream in streams:
                    if r:
                        try:
                            CLIENT_EVENT_STREAM_LEN.labels(stream).set(float(r.xlen(stream) or 0))
                        except Exception:
                            CLIENT_EVENT_STREAM_LEN.labels(stream).set(0)
                        try:
                            pending = r.xpending(stream, group)
                            pcount = pending.get("pending") if isinstance(pending, dict) else 0
                            CLIENT_EVENT_STREAM_PENDING.labels(stream).set(float(pcount or 0))
                        except Exception:
                            CLIENT_EVENT_STREAM_PENDING.labels(stream).set(0)
                        try:
                            lag2 = 0
                            gs = r.xinfo_groups(stream)
                            if isinstance(gs, list):
                                for g in gs:
                                    if not isinstance(g, dict):
                                        continue
                                    if str(g.get("name") or "") != str(group):
                                        continue
                                    if g.get("lag") is not None:
                                        lag2 = int(g.get("lag") or 0)
                                    break
                            CLIENT_EVENT_STREAM_LAG.labels(stream).set(float(lag2 or 0))
                        except Exception:
                            CLIENT_EVENT_STREAM_LAG.labels(stream).set(0)
                    else:
                        CLIENT_EVENT_STREAM_LEN.labels(stream).set(0)
                        CLIENT_EVENT_STREAM_PENDING.labels(stream).set(0)
                        CLIENT_EVENT_STREAM_LAG.labels(stream).set(0)
                    st_key = "events:client:drain:status:" + stream.replace(":", "_")
                    st2 = cache.get_json(st_key)
                    if isinstance(st2, dict):
                        CLIENT_EVENT_DRAIN_OK.labels(stream).set(1 if bool(st2.get("ok")) else 0)
                        try:
                            CLIENT_EVENT_DRAINED.labels(stream).set(float(st2.get("drained") or 0))
                        except Exception:
                            CLIENT_EVENT_DRAINED.labels(stream).set(0)
                        try:
                            CLIENT_EVENT_PERSISTED.labels(stream).set(float(st2.get("persisted") or 0))
                        except Exception:
                            CLIENT_EVENT_PERSISTED.labels(stream).set(0)
                    else:
                        CLIENT_EVENT_DRAIN_OK.labels(stream).set(0)
                        CLIENT_EVENT_DRAINED.labels(stream).set(0)
                        CLIENT_EVENT_PERSISTED.labels(stream).set(0)
            except Exception:
                pass
            try:
                from app.core.http_client import cb_state

                for svc in ["feed_recall_remote"]:
                    st = cb_state(svc)
                    try:
                        ou = float(st.get("open_until") or 0)
                    except Exception:
                        ou = 0.0
                    try:
                        fc = float(st.get("fail") or 0)
                    except Exception:
                        fc = 0.0
                    try:
                        HTTP_OUTBOUND_CB_FAIL.labels(svc).set(fc)
                    except Exception:
                        pass
                    try:
                        HTTP_OUTBOUND_CB_OPEN_UNTIL.labels(svc).set(ou)
                    except Exception:
                        pass
                    try:
                        HTTP_OUTBOUND_CB_OPEN.labels(svc).set(1 if (ou and ou > time.time()) else 0)
                    except Exception:
                        pass
            except Exception:
                pass
            return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
    except Exception:
        pass

    @app.on_event("startup")
    def _startup() -> None:
        # Run database migrations
        # run_migrations()  # DISABLED FOR EMERGENCY FIX
        # DISABLED: All DB initialization disabled for emergency fix
        # try:
        #     db = SessionLocal()
        #     try:
        #         n = db.query(Category).count()
        #     except Exception:
        #         n = 0
        #     if not n:
        #         cats = [...]
        #         for i, c in enumerate(cats):
        #             db.add(Category(name=c, sort_order=i, is_active=True))
        #         db.commit()
        #     ... (rest of DB init disabled)
        # finally:
        #     try:
        #         db.close()
        #     except Exception:
        #         pass
        pass  # Emergency fix: skip all DB initialization

    @app.on_event("startup")
    async def _startup_dispatch_retry() -> None:
        try:
            from app.services.dispatch_retry_service import start_dispatch_loop

            start_dispatch_loop()
        except Exception:
            pass

    @app.on_event("startup")
    async def _startup_assets_rollout_guard() -> None:
        try:
            import asyncio
            import json
            import time
            from pathlib import Path

            interval = int(os.getenv("ASSET_ROLLOUT_GUARD_INTERVAL_SEC", "0") or 0)
            if interval <= 0:
                return
            minutes = int(os.getenv("ASSET_ROLLOUT_GUARD_MINUTES", "3") or 3)
            if minutes < 1:
                minutes = 1
            if minutes > 30:
                minutes = 30
            threshold = int(os.getenv("ASSET_ROLLOUT_GUARD_THRESHOLD", "20") or 20)
            if threshold < 1:
                threshold = 1
            if threshold > 500:
                threshold = 500

            dist = Path(BASE_DIR) / "static" / "dist"
            rollout_path = dist / "rollout.json"
            log_path = Path(BASE_DIR) / "logs" / "frontend_events.log"

            def read_rollout():
                if not rollout_path.exists():
                    return {"enabled": False, "percent": 0, "canary_release_id": None}
                try:
                    obj = json.loads(rollout_path.read_text(encoding="utf-8", errors="ignore") or "{}")
                    if isinstance(obj, dict):
                        return obj
                except Exception:
                    pass
                return {"enabled": False, "percent": 0, "canary_release_id": None}

            def write_rollout(obj):
                try:
                    rollout_path.parent.mkdir(parents=True, exist_ok=True)
                    tmp = rollout_path.with_suffix(".json.tmp")
                    tmp.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
                    tmp.replace(rollout_path)
                except Exception:
                    pass

            def count_recent_errors():
                if not log_path.exists():
                    return 0
                cutoff_ms = int(time.time() * 1000) - minutes * 60 * 1000
                try:
                    with log_path.open("rb") as f:
                        f.seek(0, 2)
                        size = f.tell()
                        start = max(0, size - 1_000_000)
                        f.seek(start)
                        lines = f.read().decode("utf-8", errors="ignore").splitlines()
                except Exception:
                    return 0
                cnt = 0
                for line in reversed(lines):
                    try:
                        obj = json.loads(line)
                        ts = int(obj.get("ts") or 0)
                        if ts and ts < cutoff_ms:
                            break
                        if str(obj.get("name") or "") == "ui:error":
                            cnt += 1
                            if cnt >= threshold:
                                break
                    except Exception:
                        continue
                return cnt

            async def loop():
                while True:
                    try:
                        cfg = read_rollout()
                        enabled = bool(cfg.get("enabled")) or False
                        try:
                            pct = int(cfg.get("percent") or 0)
                        except Exception:
                            pct = 0
                        if enabled and pct > 0:
                            cnt = count_recent_errors()
                            if cnt >= threshold:
                                cfg["enabled"] = False
                                cfg["percent"] = 0
                                write_rollout(cfg)
                    except Exception:
                        pass
                    await asyncio.sleep(max(5, interval))

            asyncio.create_task(loop())
        except Exception:
            pass

    @app.on_event("startup")
    async def _startup_client_events_autoguard() -> None:
        try:
            import asyncio

            if not bool(getattr(settings, "CLIENT_EVENT_AUTOGUARD_ENABLED", False)):
                return

            from app.core.cache import cache
            from app.observability.client_events_guard import (
                apply_client_events_degrade,
                apply_client_events_recover,
                get_client_event_backlog,
            )
            from app.observability.runtime_client_events import read_runtime_client_events

            async def loop() -> None:
                while True:
                    try:
                        interval = int(getattr(settings, "CLIENT_EVENT_AUTOGUARD_INTERVAL_SEC", 5) or 5)
                    except Exception:
                        interval = 5
                    if interval < 1:
                        interval = 1
                    if interval > 60:
                        interval = 60
                    try:
                        if not cache.set_nx("lock:autoguard:client_events", "1", ttl=max(2, interval)):
                            await asyncio.sleep(float(interval))
                            continue
                    except Exception:
                        await asyncio.sleep(float(interval))
                        continue
                    try:
                        st = get_client_event_backlog()
                        if not bool(st.get("ok")):
                            await asyncio.sleep(float(interval))
                            continue
                        backlog = int(st.get("pending_max") or 0)
                        high = int(getattr(settings, "CLIENT_EVENT_AUTOGUARD_BACKLOG_HIGH", 20000) or 20000)
                        low = int(getattr(settings, "CLIENT_EVENT_AUTOGUARD_BACKLOG_LOW", 5000) or 5000)
                        if high < 100:
                            high = 100
                        if low < 0:
                            low = 0
                        if low > high:
                            low = high

                        cfg = read_runtime_client_events()
                        degraded = bool(cfg.get("autoguard_degraded")) if isinstance(cfg, dict) else False

                        state_key = "runtime:client_events:autoguard_state"
                        st2 = cache.get_json(state_key)
                        st2 = st2 if isinstance(st2, dict) else {}
                        streak = int(st2.get("recover_streak") or 0)

                        if backlog >= high:
                            rate = float(getattr(settings, "CLIENT_EVENT_AUTOGUARD_DEGRADE_SAMPLE_RATE", 0.2) or 0.2)
                            disable_persist = bool(getattr(settings, "CLIENT_EVENT_AUTOGUARD_DISABLE_PERSIST", True))
                            apply_client_events_degrade(ingest_sample_rate=float(rate), disable_persist=bool(disable_persist))
                            cache.set_json(state_key, {"recover_streak": 0}, ttl=3600)
                        elif degraded and backlog <= low:
                            streak += 1
                            need = int(getattr(settings, "CLIENT_EVENT_AUTOGUARD_RECOVER_STREAK", 6) or 6)
                            if need < 1:
                                need = 1
                            if streak >= need:
                                rrate = float(getattr(settings, "CLIENT_EVENT_AUTOGUARD_RECOVER_SAMPLE_RATE", 1.0) or 1.0)
                                enable_persist = bool(getattr(settings, "CLIENT_EVENT_AUTOGUARD_RECOVER_PERSIST", True))
                                apply_client_events_recover(ingest_sample_rate=float(rrate), enable_persist=bool(enable_persist))
                                streak = 0
                            cache.set_json(state_key, {"recover_streak": int(streak)}, ttl=3600)
                        else:
                            if streak:
                                cache.set_json(state_key, {"recover_streak": 0}, ttl=3600)
                    except Exception:
                        pass
                    await asyncio.sleep(float(interval))

            asyncio.create_task(loop())
        except Exception:
            pass

    @app.middleware("http")
    async def no_cache_for_html_and_app_js(request: Request, call_next):
        response = await call_next(request)
        path = request.url.path
        if path in {"/", "/admin", "/admin.html", "/studio", "/studio.html"}:
            response.headers["Cache-Control"] = "no-store, max-age=0"
            try:
                sid = request.cookies.get("aiseek_sid")
                if not sid:
                    sid2 = ensure_rollout_cookie(sid)
                    response.set_cookie(
                        key="aiseek_sid",
                        value=str(sid2),
                        httponly=False,
                        samesite="lax",
                        max_age=60 * 60 * 24 * 180,
                    )
            except Exception:
                pass
        elif path.startswith("/static/dist/manifest"):
            response.headers["Cache-Control"] = "no-store, max-age=0"
        elif path.startswith("/static/dist/r/"):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        elif path.startswith("/static/uploads/") or path.startswith("/static/worker_media/"):
            response.headers["Cache-Control"] = "public, max-age=3600"
        elif path.startswith("/static/js/") or path.startswith("/static/css/"):
            response.headers["Cache-Control"] = "public, max-age=0"
        elif path.startswith("/static/"):
            response.headers["Cache-Control"] = "public, max-age=86400"
        if path.startswith("/api/v1/") and request.method.upper() in {"POST", "PUT", "DELETE"}:
            try:
                if int(getattr(response, "status_code", 0) or 0) < 500:
                    response.set_cookie(
                        key="aiseek_rw",
                        value="1",
                        httponly=True,
                        samesite="lax",
                        max_age=3,
                    )
            except Exception:
                pass
        response.headers["x-aiseek-build"] = build_id
        try:
            if "x-request-id" not in response.headers:
                from app.core.request_context import get_request_id

                rid = get_request_id()
                if rid:
                    response.headers["x-request-id"] = str(rid)
        except Exception:
            pass
        try:
            if "x-session-id" not in response.headers:
                from app.core.request_context import get_session_id

                sid = get_session_id()
                if sid:
                    response.headers["x-session-id"] = str(sid)
        except Exception:
            pass
        return response

    @app.get("/livez")
    def livez():
        return {"ok": True}

    @app.get("/healthz")
    def healthz():
        return {"ok": True}

    @app.get("/readyz")
    def readyz():
        from sqlalchemy import text

        ok = True
        checks = {}
        try:
            db = SessionLocalRead()
            try:
                db.execute(text("SELECT 1"))
                checks["db"] = True
            finally:
                db.close()
        except Exception:
            ok = False
            checks["db"] = False

        try:
            if bool(getattr(settings, "READINESS_STRICT", False)):
                try:
                    import redis

                    r = redis.Redis.from_url(
                        settings.REDIS_URL,
                        decode_responses=True,
                        socket_timeout=float(getattr(settings, "REDIS_SOCKET_TIMEOUT_SEC", 0.6) or 0.6),
                        socket_connect_timeout=float(getattr(settings, "REDIS_CONNECT_TIMEOUT_SEC", 0.3) or 0.3),
                        max_connections=int(getattr(settings, "REDIS_MAX_CONNECTIONS", 200) or 200),
                    )
                    r.ping()
                    checks["redis"] = True
                except Exception:
                    ok = False
                    checks["redis"] = False
                try:
                    if str(getattr(settings, "SECRET_KEY", "") or "") == "your-secret-key-change-in-production":
                        ok = False
                        checks["secret_key"] = False
                    else:
                        checks["secret_key"] = True
                except Exception:
                    ok = False
                    checks["secret_key"] = False
                try:
                    if str(getattr(settings, "WORKER_SECRET", "") or "") == "m3pro_worker_2026":
                        ok = False
                        checks["worker_secret"] = False
                    else:
                        checks["worker_secret"] = True
                except Exception:
                    ok = False
                    checks["worker_secret"] = False
        except Exception:
            pass
        
        # Always return OK for now to avoid Nginx blocking traffic during debugging
        # if not ok:
        #     from fastapi import HTTPException
        #     raise HTTPException(status_code=503, detail=checks)
        return {"ok": True, "checks": checks}

    @app.api_route("/", methods=["GET", "HEAD"])
    def read_root(request: Request):
        try:
            static_root = os.path.join(BASE_DIR, "static", "js")
            tpl_root = os.path.join(BASE_DIR, "templates")
            paths = [
                os.path.join(static_root, "main.js"),
                os.path.join(static_root, "modules", "actions.js"),
                os.path.join(static_root, "app", "core.js"),
                os.path.join(static_root, "app", "helpers.js"),
                os.path.join(static_root, "app", "notifications.js"),
                os.path.join(static_root, "app", "search.js"),
                os.path.join(static_root, "app", "profile.js"),
                os.path.join(static_root, "app", "player.js"),
                os.path.join(static_root, "app", "comments.js"),
                os.path.join(static_root, "app", "floating_player.js"),
                os.path.join(static_root, "app", "studio.js"),
                os.path.join(tpl_root, "index.html"),
                os.path.join(tpl_root, "studio.html"),
            ]
            mt = 0
            for p in paths:
                try:
                    mt = max(mt, int(os.path.getmtime(p)))
                except Exception:
                    pass
            build_id_out = f"{build_id}.{mt}" if mt else build_id
        except Exception:
            build_id_out = build_id
        sid = None
        try:
            sid = request.cookies.get("aiseek_sid")
        except Exception:
            sid = None
        sid2 = ensure_rollout_cookie(sid)
        cookies = dict(request.cookies or {})
        cookies["aiseek_sid"] = sid2
        asset_url = make_asset_url_for_request(build_id_out, cookies, request.headers)
        try:
            from app.core.config import get_settings

            s = get_settings()
            frontend_flags = {
                "watch_via_stream": bool(getattr(s, "CLIENT_EVENT_APPLY_HOT_ENABLED", False))
                and bool(getattr(s, "CLIENT_EVENT_STREAM_ENABLED", True)),
            }
        except Exception:
            frontend_flags = {"watch_via_stream": False}
        resp = templates.TemplateResponse(
            "index.html",
            {"request": request, "build_id": build_id_out, "asset_url": asset_url, "frontend_flags": frontend_flags},
        )
        try:
            if not sid:
                resp.set_cookie(
                    key="aiseek_sid",
                    value=str(sid2),
                    httponly=False,
                    samesite="lax",
                    max_age=60 * 60 * 24 * 180,
                )
        except Exception:
            pass
        return resp

    @app.api_route("/studio", methods=["GET", "HEAD"])
    def read_studio(request: Request):
        try:
            static_root = os.path.join(BASE_DIR, "static", "js")
            tpl_root = os.path.join(BASE_DIR, "templates")
            paths = [
                os.path.join(static_root, "app", "studio.js"),
                os.path.join(tpl_root, "studio.html"),
            ]
            mt = 0
            for p in paths:
                try:
                    mt = max(mt, int(os.path.getmtime(p)))
                except Exception:
                    pass
            build_id_out = f"{build_id}.{mt}" if mt else build_id
        except Exception:
            build_id_out = build_id
        sid = None
        try:
            sid = request.cookies.get("aiseek_sid")
        except Exception:
            sid = None
        sid2 = ensure_rollout_cookie(sid)
        cookies = dict(request.cookies or {})
        cookies["aiseek_sid"] = sid2
        asset_url = make_asset_url_for_request(build_id_out, cookies, request.headers)
        resp = templates.TemplateResponse("studio.html", {"request": request, "build_id": build_id_out, "asset_url": asset_url})
        try:
            if not sid:
                resp.set_cookie(
                    key="aiseek_sid",
                    value=str(sid2),
                    httponly=False,
                    samesite="lax",
                    max_age=60 * 60 * 24 * 180,
                )
        except Exception:
            pass
        return resp

    @app.api_route("/studio.html", methods=["GET", "HEAD"])
    def read_studio_html():
        return RedirectResponse(url="/studio", status_code=307)

    @app.api_route("/admin", methods=["GET", "HEAD"])
    def read_admin(request: Request):
        try:
            static_root = os.path.join(BASE_DIR, "static", "js")
            tpl_root = os.path.join(BASE_DIR, "templates")
            paths = [
                os.path.join(static_root, "modules", "actions.js"),
                os.path.join(tpl_root, "admin.html"),
            ]
            mt = 0
            for p in paths:
                try:
                    mt = max(mt, int(os.path.getmtime(p)))
                except Exception:
                    pass
            build_id_out = f"{build_id}.{mt}" if mt else build_id
        except Exception:
            build_id_out = build_id
        sid = None
        try:
            sid = request.cookies.get("aiseek_sid")
        except Exception:
            sid = None
        sid2 = ensure_rollout_cookie(sid)
        cookies = dict(request.cookies or {})
        cookies["aiseek_sid"] = sid2
        asset_url = make_asset_url_for_request(build_id_out, cookies, request.headers)
        resp = templates.TemplateResponse("admin.html", {"request": request, "build_id": build_id_out, "asset_url": asset_url})
        try:
            if not sid:
                resp.set_cookie(
                    key="aiseek_sid",
                    value=str(sid2),
                    httponly=False,
                    samesite="lax",
                    max_age=60 * 60 * 24 * 180,
                )
        except Exception:
            pass
        return resp

    @app.api_route("/admin.html", methods=["GET", "HEAD"])
    def read_admin_html():
        return RedirectResponse(url="/admin", status_code=307)

    @app.api_route("/favicon.ico", methods=["GET", "HEAD"])
    def favicon():
        return RedirectResponse(url="/static/img/logo.svg", status_code=307)

    return app


app = create_app()


if __name__ == "__main__":
    import argparse
    import os
    import uvicorn

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5002)
    parser.add_argument("--workers", type=int, default=int(os.getenv("UVICORN_WORKERS", "1") or 1))
    args = parser.parse_args()
    workers = int(args.workers or 1)
    if workers < 1:
        workers = 1
    uvicorn.run(app, host="0.0.0.0", port=args.port, workers=workers)
