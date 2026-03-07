import json
import time
from pathlib import Path

from starlette.middleware.base import BaseHTTPMiddleware

from app.core.assets import _bucket_0_99
from app.core.request_context import set_canary


class CanaryMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, enabled: bool = True):
        super().__init__(app)
        self.enabled = bool(enabled)
        self._cfg = {}
        self._next_reload_ts = 0.0
        self._path = Path(__file__).resolve().parents[2] / "static" / "dist" / "rollout.json"

    def _get_cfg(self) -> dict:
        now = time.time()
        if now < float(self._next_reload_ts or 0):
            return self._cfg if isinstance(self._cfg, dict) else {}
        self._next_reload_ts = now + 2.0
        try:
            if self._path.exists():
                obj = json.loads(self._path.read_text(encoding="utf-8", errors="ignore") or "{}")
                if isinstance(obj, dict):
                    self._cfg = obj
        except Exception:
            pass
        return self._cfg if isinstance(self._cfg, dict) else {}

    async def dispatch(self, request, call_next):
        canary = False
        if self.enabled:
            cfg = self._get_cfg()
            enabled = bool(cfg.get("enabled")) or False
            try:
                pct = int(cfg.get("percent") or 0)
            except Exception:
                pct = 0
            if pct < 0:
                pct = 0
            if pct > 100:
                pct = 100
            if enabled and pct > 0:
                sid = str(request.cookies.get("aiseek_sid") or "").strip() or str(request.headers.get("x-session-id") or "").strip()
                if sid and _bucket_0_99(sid) < pct:
                    canary = True
        try:
            from app.core.config import get_settings

            s = get_settings()
            if bool(getattr(s, "CANARY_OVERRIDE_ENABLED", False)) or False:
                hv = str(request.headers.get("x-canary") or request.headers.get("X-Canary") or "").strip()
                if hv in {"1", "true", "TRUE", "yes", "YES"}:
                    canary = True
                elif hv in {"0", "false", "FALSE", "no", "NO"}:
                    canary = False
        except Exception:
            pass
        try:
            request.state.canary = bool(canary)
        except Exception:
            pass
        try:
            set_canary(bool(canary))
        except Exception:
            pass

        resp = await call_next(request)
        try:
            resp.headers["x-canary"] = "1" if canary else "0"
        except Exception:
            pass
        return resp
