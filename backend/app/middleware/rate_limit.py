import time
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.config import get_settings
from app.core.redis_scripts import TOKEN_BUCKET
from app.core.cache import cache
from app.core.security import decode_access_token


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, enabled: bool = True):
        super().__init__(app)
        self.enabled = enabled
        self._redis = None
        self._ident_cache = {}
        self._es_down_key = ""
        self._es_down_key_exp = 0.0

    def _get_redis(self):
        if self._redis is not None:
            return self._redis
        try:
            import redis

            s = get_settings()
            url = s.REDIS_URL
            self._redis = redis.Redis.from_url(
                url,
                decode_responses=True,
                socket_timeout=float(getattr(s, "REDIS_SOCKET_TIMEOUT_SEC", 0.6) or 0.6),
                socket_connect_timeout=float(getattr(s, "REDIS_CONNECT_TIMEOUT_SEC", 0.3) or 0.3),
                max_connections=int(getattr(s, "REDIS_MAX_CONNECTIONS", 200) or 200),
            )
        except Exception:
            self._redis = False
        return self._redis

    def _ident_cache_ttl(self) -> int:
        try:
            s = get_settings()
            ttl = int(getattr(s, "RATE_LIMIT_IDENT_CACHE_TTL_SEC", 30) or 30)
        except Exception:
            ttl = 30
        if ttl < 5:
            ttl = 5
        if ttl > 300:
            ttl = 300
        return ttl

    def _ident_from_auth(self, auth: Optional[str]) -> Optional[str]:
        if not auth or not str(auth).startswith("Bearer "):
            return None
        token = str(auth).replace("Bearer ", "").strip()
        if not token:
            return None
        now = time.time()
        hit = self._ident_cache.get(token)
        if hit:
            exp, ident = hit
            if float(exp or 0) > now:
                return str(ident or "") or None
            try:
                self._ident_cache.pop(token, None)
            except Exception:
                pass
        ident = None
        if token.startswith("fake-token-"):
            try:
                ident = f"u{int(token.split('fake-token-')[1])}"
            except Exception:
                ident = None
        else:
            payload = decode_access_token(token)
            if payload and payload.get("sub"):
                try:
                    ident = f"u{int(payload.get('sub'))}"
                except Exception:
                    ident = None
        if ident:
            ttl = int(self._ident_cache_ttl())
            self._ident_cache[token] = (now + ttl, str(ident))
            if len(self._ident_cache) > 20000:
                try:
                    self._ident_cache.clear()
                except Exception:
                    pass
        return ident

    def _es_down_key_cached(self) -> str:
        now = time.time()
        if self._es_down_key and self._es_down_key_exp > now:
            return self._es_down_key
        try:
            s = get_settings()
            url2 = str(getattr(s, "ELASTICSEARCH_URL", "") or "").strip()
            idx2 = str(getattr(s, "ELASTICSEARCH_INDEX", "") or "").strip()
            if not (url2 and idx2):
                self._es_down_key = ""
                self._es_down_key_exp = now + 10.0
                return ""
            try:
                from app.core.cache import stable_sig

                sk = stable_sig(["es", url2, idx2])[:16]
            except Exception:
                sk = "default"
            self._es_down_key = f"es:down_until:{sk}"
            self._es_down_key_exp = now + 30.0
            return self._es_down_key
        except Exception:
            self._es_down_key = ""
            self._es_down_key_exp = now + 10.0
            return ""

    async def dispatch(self, request, call_next):
        if not self.enabled:
            return await call_next(request)

        path = request.url.path
        method = request.method.upper()

        is_feed = path.startswith("/api/v1/posts/feed")
        is_auth = path.startswith("/api/v1/auth/")
        is_write = method in {"POST", "PUT", "DELETE"} and path.startswith("/api/v1/")
        is_search_posts = method == "GET" and path in {"/api/v1/search/posts", "/api/v1/posts/search"}
        is_search_users = method == "GET" and path == "/api/v1/users/search-user"
        is_search_hot = method == "GET" and path == "/api/v1/search/hot"
        is_search = bool(is_search_posts or is_search_users or is_search_hot)

        if not (is_feed or is_auth or is_write or is_search):
            return await call_next(request)

        r = self._get_redis()
        use_local = not bool(r)

        auth = request.headers.get("authorization") or request.headers.get("Authorization")
        ident = self._ident_from_auth(auth)
        if not ident:
            ident = request.headers.get("x-aiseek-sid") or request.headers.get("x-session-id")
            if ident:
                ident = f"s{str(ident)}"
        if not ident:
            try:
                ip = request.headers.get("x-forwarded-for") or ""
                ident = ip.split(",", 1)[0].strip() or None
                if not ident:
                    ident = getattr(getattr(request, "client", None), "host", None)
                if ident:
                    ident = f"ip{ident}"
            except Exception:
                ident = None
        if not ident:
            return await call_next(request)

        route = request.scope.get("route")
        route_path = getattr(route, "path", None) or path

        s = get_settings()
        now = int(time.time())
        window = int(getattr(s, "RATE_LIMIT_WINDOW_SEC", 60) or 60)
        if window < 5:
            window = 5
        if window > 600:
            window = 600
        bucket = now // window
        key = f"rl:{bucket}:{ident}:{method}:{route_path}"

        if is_feed and method == "GET":
            limit = int(getattr(s, "RATE_LIMIT_FEED_PER_MIN", 180) or 180)
        elif is_auth:
            limit = int(getattr(s, "RATE_LIMIT_AUTH_PER_MIN", 30) or 30)
        elif is_search:
            if str(ident).startswith("u"):
                limit = int(getattr(s, "RATE_LIMIT_SEARCH_PER_MIN_AUTH", 240) or 240)
            else:
                limit = int(getattr(s, "RATE_LIMIT_SEARCH_PER_MIN_ANON", 60) or 60)
        else:
            limit = int(getattr(s, "RATE_LIMIT_WRITE_PER_MIN", 600) or 600)
        if limit < 1:
            limit = 1
        try:
            if use_local:
                n = cache.hincrby(key, "n", 1, ttl=window + 5)
            else:
                n = r.incr(key)
                if n == 1:
                    r.expire(key, window + 5)
            if int(n or 0) > limit:
                return JSONResponse({"detail": "rate_limited"}, status_code=429)
        except Exception:
            return await call_next(request)

        if is_search and cache.redis_enabled():
            try:
                qp = request.query_params
                q = (qp.get("query") or qp.get("q") or "").strip()
                cur = (qp.get("cursor") or "").strip()
                try:
                    lim = int(qp.get("limit") or 0)
                except Exception:
                    lim = 0
                if lim < 0:
                    lim = 0
                if lim > 200:
                    lim = 200
                cost = 1
                if q:
                    cost += min(4, max(0, len(q) // 24))
                if lim:
                    cost += min(4, max(0, lim // 50))
                if cur:
                    cost += 1

                if is_search_posts and path == "/api/v1/search/posts":
                    try:
                        down_key = self._es_down_key_cached()
                        if down_key:
                            v2 = cache.get_json(down_key)
                            if v2 is not None and float(v2) > time.time():
                                cost += 3
                    except Exception:
                        pass
                if cost < 1:
                    cost = 1
                if cost > 20:
                    cost = 20
                if str(ident).startswith("u"):
                    rate = float(getattr(s, "SEARCH_BUDGET_RATE_PER_SEC_AUTH", 10.0) or 10.0)
                    burst = float(getattr(s, "SEARCH_BUDGET_BURST_AUTH", 60.0) or 60.0)
                else:
                    rate = float(getattr(s, "SEARCH_BUDGET_RATE_PER_SEC_ANON", 4.0) or 4.0)
                    burst = float(getattr(s, "SEARCH_BUDGET_BURST_ANON", 20.0) or 20.0)
                    if cost >= 6:
                        rate = float(rate) * 0.8
                        burst = float(burst) * 0.8
                if rate <= 0:
                    rate = 0.1
                if burst < 1:
                    burst = 1.0
                rl_key = f"rl:tb:{ident}:{route_path}"
                ok = cache.eval_cached(TOKEN_BUCKET, keys=[rl_key], args=[str(rate), str(burst), str(time.time()), str(cost)])
                try:
                    ok_i = int(ok)
                except Exception:
                    ok_i = 1
                if ok_i != 1:
                    return JSONResponse({"detail": "rate_limited"}, status_code=429)
            except Exception:
                pass

        return await call_next(request)
