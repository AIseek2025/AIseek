import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.core.request_context import get_request_id, get_session_id, get_canary, get_user_id


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": int(record.created * 1000),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for k in (
            "request_id",
            "session_id",
            "user_id",
            "canary",
            "trace_id",
            "span_id",
            "method",
            "path",
            "status",
            "latency_ms",
            "ip",
        ):
            v = getattr(record, k, None)
            if v is not None:
                payload[k] = v
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


class ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            if getattr(record, "request_id", None) is None:
                rid = get_request_id()
                if rid:
                    record.request_id = str(rid)
        except Exception:
            pass
        try:
            if getattr(record, "session_id", None) is None:
                sid = get_session_id()
                if sid:
                    record.session_id = str(sid)
        except Exception:
            pass
        try:
            if getattr(record, "user_id", None) is None:
                uid = get_user_id()
                if uid is not None:
                    record.user_id = int(uid)
        except Exception:
            pass
        try:
            if getattr(record, "canary", None) is None:
                c = get_canary()
                if c is not None:
                    record.canary = 1 if c else 0
        except Exception:
            pass
        try:
            from opentelemetry.trace import get_current_span

            span = get_current_span()
            ctx = span.get_span_context() if span else None
            if ctx and getattr(ctx, "is_valid", False):
                if getattr(record, "trace_id", None) is None:
                    record.trace_id = format(int(ctx.trace_id), "032x")
                if getattr(record, "span_id", None) is None:
                    record.span_id = format(int(ctx.span_id), "016x")
        except Exception:
            pass
        return True


def configure_logging() -> None:
    root = logging.getLogger()
    if getattr(root, "__aiseek_configured", False):
        return

    log_dir = Path(__file__).resolve().parents[2] / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    root.setLevel(logging.INFO)

    fmt = JsonFormatter()
    flt = ContextFilter()

    access = RotatingFileHandler(log_dir / "access.log", maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8")
    access.setFormatter(fmt)
    access.setLevel(logging.INFO)
    access.addFilter(flt)

    app = RotatingFileHandler(log_dir / "app.log", maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8")
    app.setFormatter(fmt)
    app.setLevel(logging.INFO)
    app.addFilter(flt)

    logging.getLogger("aiseek.access").addHandler(access)
    logging.getLogger("aiseek.access").propagate = False

    logging.getLogger("aiseek").addHandler(app)
    logging.getLogger("aiseek").propagate = False

    root.addHandler(app)
    root.addFilter(flt)

    root.__aiseek_configured = True
