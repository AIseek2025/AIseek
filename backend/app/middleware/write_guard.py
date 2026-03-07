import base64
import hashlib
import json
import time
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.cache import cache
from app.core.config import get_settings
from app.core.redis_scripts import TOKEN_BUCKET
from app.services.hot_counter_service import allow_post_write

try:
    from prometheus_client import Counter

    WRITE_GUARD_RATE_LIMITED = Counter("write_guard_rate_limited_total", "Write guard rate limited", ["path"])
    WRITE_GUARD_ALLOWED = Counter("write_guard_allowed_total", "Write guard allowed", ["path"])
    WRITE_GUARD_BLOCKED = Counter("write_guard_blocked_total", "Write guard blocked", ["path", "reason"])
    IDEMPOTENCY_HIT = Counter("idempotency_hit_total", "Idempotency cache hits", ["path"])
    HOT_SHED_DROPPED_MW = Counter("hot_shed_dropped_mw_total", "Hot shed dropped writes (middleware)", ["path"])
except Exception:
    WRITE_GUARD_RATE_LIMITED = None
    WRITE_GUARD_ALLOWED = None
    WRITE_GUARD_BLOCKED = None
    IDEMPOTENCY_HIT = None
    HOT_SHED_DROPPED_MW = None


class WriteGuardMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, enabled: bool = True):
        super().__init__(app)
        self.enabled = enabled
        self._mem = {}
        self._mem_counts = {}
        self._mem_locks = {}
        self._ticks = 0

    def _mem_get(self, key: str) -> Optional[str]:
        v = self._mem.get(key)
        if not v:
            return None
        exp, raw = v
        if exp and exp < time.time():
            try:
                del self._mem[key]
            except Exception:
                pass
            return None
        return raw

    def _mem_setex(self, key: str, ttl: int, raw: str) -> None:
        exp = time.time() + int(ttl) if ttl else 0
        self._mem[key] = (exp, raw)

    def _mem_incr(self, key: str, ttl: int) -> int:
        now = time.time()
        v = self._mem_counts.get(key)
        if not v:
            self._mem_counts[key] = (now + ttl, 1)
            return 1
        exp, n = v
        if exp and exp < now:
            self._mem_counts[key] = (now + ttl, 1)
            return 1
        n2 = int(n) + 1
        self._mem_counts[key] = (exp, n2)
        return n2

    def _mem_bucket(self, key: str, rate_per_sec: float, burst: int, cost: int = 1) -> bool:
        now = time.time()
        v = self._mem_counts.get(key)
        if not v:
            tokens = float(burst)
            ts = now
        else:
            ts, tokens = v
            if ts and ts < now:
                tokens = float(tokens)
                refill = (now - float(ts)) * float(rate_per_sec)
                tokens = min(float(burst), tokens + refill)
                ts = now
        ok = tokens >= float(cost)
        if ok:
            tokens -= float(cost)
        self._mem_counts[key] = (ts, tokens)
        return ok

    def _mem_lock(self, key: str, ttl: int) -> bool:
        now = time.time()
        v = self._mem_locks.get(key)
        if v and v > now:
            return False
        self._mem_locks[key] = now + int(ttl)
        return True

    def _mem_unlock(self, key: str) -> None:
        try:
            del self._mem_locks[key]
        except Exception:
            pass

    def _mem_gc(self, max_keys: int) -> None:
        now = time.time()

        try:
            if len(self._mem) > max_keys:
                for k, (exp, _raw) in list(self._mem.items()):
                    if exp and exp < now:
                        try:
                            del self._mem[k]
                        except Exception:
                            pass
        except Exception:
            pass

        try:
            if len(self._mem_locks) > max_keys:
                for k, exp in list(self._mem_locks.items()):
                    if exp and exp < now:
                        try:
                            del self._mem_locks[k]
                        except Exception:
                            pass
        except Exception:
            pass

        try:
            if len(self._mem_counts) > max_keys:
                for k, v in list(self._mem_counts.items()):
                    try:
                        exp = v[0]
                        if exp and exp < now:
                            del self._mem_counts[k]
                    except Exception:
                        continue
        except Exception:
            pass

    def _identity(self, request: Request) -> Optional[str]:
        sid = request.headers.get("x-session-id") or request.headers.get("x-request-id")
        if sid:
            return sid
        ip = request.client.host if request.client else None
        if ip:
            return ip
        return None

    async def _read_body_and_replay(self, request: Request) -> tuple[bytes, Request]:
        body = await request.body()

        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}

        req2 = Request(request.scope, receive)
        return body, req2

    async def _buffer_response(self, resp: Response) -> bytes:
        chunks = []
        async for c in resp.body_iterator:
            chunks.append(c)
        return b"".join(chunks)

    async def dispatch(self, request: Request, call_next):
        if not self.enabled:
            return await call_next(request)

        s = get_settings()
        self._ticks += 1
        if (self._ticks & 1023) == 0:
            try:
                self._mem_gc(int(getattr(s, "WRITE_GUARD_MEM_MAX_KEYS", 20000) or 20000))
            except Exception:
                pass
        if not getattr(s, "WRITE_GUARD_ENABLED", True):
            return await call_next(request)

        if request.method not in {"POST", "PUT", "DELETE"}:
            return await call_next(request)

        identity = self._identity(request)
        r = cache._get_redis()  # noqa: SLF001
        if not identity:
            return await call_next(request)

        path = request.url.path
        should_read_body = False
        if bool(getattr(s, "HOT_SHED_ENABLED", False)) and path in {
            "/api/v1/interaction/like",
            "/api/v1/interaction/favorite",
            "/api/v1/interaction/comment",
        }:
            should_read_body = True
        if bool(getattr(s, "IDEMPOTENCY_ENABLED", True)) and (
            request.headers.get("idempotency-key") or request.headers.get("x-idempotency-key")
        ):
            should_read_body = True

        body = b""
        req2 = request
        if should_read_body:
            body, req2 = await self._read_body_and_replay(request)

        rate_per_min = float(getattr(s, "WRITE_GUARD_RATE_PER_MIN", 600) or 600)
        burst = int(getattr(s, "WRITE_GUARD_BURST", 120) or 120)
        rate_per_sec = max(0.001, rate_per_min / 60.0)
        rl_key = f"tb:{identity}:{path}"

        allowed = True
        try:
            if r:
                ok = cache.eval_cached(TOKEN_BUCKET, keys=[rl_key], args=[str(rate_per_sec), str(burst), str(time.time()), "1"])
                allowed = bool(int(ok) == 1)
            else:
                allowed = self._mem_bucket(rl_key, rate_per_sec, burst, 1)
        except Exception:
            allowed = True

        if not allowed:
            if WRITE_GUARD_RATE_LIMITED is not None:
                try:
                    WRITE_GUARD_RATE_LIMITED.labels(path).inc()
                except Exception:
                    pass
            if WRITE_GUARD_BLOCKED is not None:
                try:
                    WRITE_GUARD_BLOCKED.labels(path, "rate_limited").inc()
                except Exception:
                    pass
            return Response(content=b'{"detail":"rate_limited"}', status_code=429, media_type="application/json")

        if bool(getattr(s, "HOT_SHED_ENABLED", False)) and path in {
            "/api/v1/interaction/like",
            "/api/v1/interaction/favorite",
            "/api/v1/interaction/comment",
        }:
            try:
                data = json.loads(body.decode("utf-8")) if body else {}
                pid = int(data.get("post_id"))
                if not allow_post_write(pid):
                    if HOT_SHED_DROPPED_MW is not None:
                        try:
                            HOT_SHED_DROPPED_MW.labels(path).inc()
                        except Exception:
                            pass
                    return Response(content=b'{"detail":"hot_shed"}', status_code=429, media_type="application/json")
            except Exception:
                pass

        if WRITE_GUARD_ALLOWED is not None:
            try:
                WRITE_GUARD_ALLOWED.labels(path).inc()
            except Exception:
                pass

        if not bool(getattr(s, "IDEMPOTENCY_ENABLED", True)):
            return await call_next(req2)

        idem = req2.headers.get("idempotency-key") or req2.headers.get("x-idempotency-key")
        if not idem:
            return await call_next(req2)

        digest = hashlib.sha1(body).hexdigest()[:12]
        key = f"idem:{identity}:{req2.method}:{path}:{idem}:{digest}"
        ttl = int(getattr(s, "IDEMPOTENCY_TTL_SEC", 30) or 30)
        cached = None
        try:
            if r:
                cached = r.get(key)
            else:
                cached = self._mem_get(key)
        except Exception:
            cached = None
        if cached:
            try:
                obj = json.loads(cached)
                status = int(obj.get("status") or 200)
                ct = obj.get("content_type") or "application/json"
                b64 = obj.get("body") or ""
                out = base64.b64decode(b64.encode("ascii")) if b64 else b""
                if IDEMPOTENCY_HIT is not None:
                    try:
                        IDEMPOTENCY_HIT.labels(path).inc()
                    except Exception:
                        pass
                if WRITE_GUARD_ALLOWED is not None:
                    try:
                        WRITE_GUARD_ALLOWED.labels(path).inc()
                    except Exception:
                        pass
                return Response(content=out, status_code=status, media_type=ct)
            except Exception:
                pass

        lock_key = f"lock:{key}"
        got_lock = False
        try:
            if r:
                got_lock = bool(r.set(lock_key, "1", nx=True, ex=max(1, ttl)))
            else:
                got_lock = self._mem_lock(lock_key, max(1, ttl))
        except Exception:
            got_lock = False

        if not got_lock:
            try:
                if r:
                    cached2 = r.get(key)
                else:
                    cached2 = self._mem_get(key)
                if cached2:
                    obj = json.loads(cached2)
                    status = int(obj.get("status") or 200)
                    ct = obj.get("content_type") or "application/json"
                    b64 = obj.get("body") or ""
                    out = base64.b64decode(b64.encode("ascii")) if b64 else b""
                    return Response(content=out, status_code=status, media_type=ct)
            except Exception:
                pass
            return await call_next(req2)

        resp = await call_next(req2)
        body_out = await self._buffer_response(resp)
        max_body = int(getattr(s, "IDEMPOTENCY_MAX_BODY_BYTES", 262144) or 262144)
        if max_body > 0 and len(body_out) > max_body:
            headers = dict(resp.headers)
            try:
                if r:
                    r.delete(lock_key)
                else:
                    self._mem_unlock(lock_key)
            except Exception:
                pass
            return Response(content=body_out, status_code=resp.status_code, headers=headers, media_type=resp.media_type)
        ct = resp.headers.get("content-type") or resp.media_type or "application/json"
        payload = {
            "status": int(resp.status_code),
            "content_type": ct,
            "body": base64.b64encode(body_out).decode("ascii"),
        }
        try:
            raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
            if r:
                r.setex(key, ttl, raw)
            else:
                self._mem_setex(key, ttl, raw)
        except Exception:
            pass
        try:
            if r:
                r.delete(lock_key)
            else:
                self._mem_unlock(lock_key)
        except Exception:
            pass

        headers = dict(resp.headers)
        return Response(content=body_out, status_code=resp.status_code, headers=headers, media_type=resp.media_type)
