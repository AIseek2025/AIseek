import hashlib
import json
import time
from typing import Any, Callable, Dict, Optional, Tuple

from app.core.config import get_settings


class Cache:
    def __init__(self):
        self._redis = None
        self._local: Dict[str, Tuple[float, str]] = {}
        self._local_hash: Dict[str, Tuple[float, Dict[str, int]]] = {}
        self._versions: Dict[str, int] = {}
        self._script_shas: Dict[str, str] = {}
        try:
            s = get_settings()
        except Exception:
            s = None
        try:
            self._local_cap = int(getattr(s, "CACHE_LOCAL_MAX_KEYS", 50000) or 50000)
        except Exception:
            self._local_cap = 50000
        if self._local_cap < 1000:
            self._local_cap = 1000
        try:
            self._local_hash_cap = int(getattr(s, "CACHE_LOCAL_HASH_MAX_KEYS", 20000) or 20000)
        except Exception:
            self._local_hash_cap = 20000
        if self._local_hash_cap < 500:
            self._local_hash_cap = 500

    def _get_redis(self):
        if self._redis is not None:
            return self._redis
        try:
            import redis

            s = get_settings()
            r = redis.Redis.from_url(
                s.REDIS_URL,
                decode_responses=True,
                socket_timeout=float(getattr(s, "REDIS_SOCKET_TIMEOUT_SEC", 0.6) or 0.6),
                socket_connect_timeout=float(getattr(s, "REDIS_CONNECT_TIMEOUT_SEC", 0.3) or 0.3),
                max_connections=int(getattr(s, "REDIS_MAX_CONNECTIONS", 200) or 200),
            )
            r.ping()
            self._redis = r
        except Exception:
            self._redis = False
        return self._redis

    def redis_enabled(self) -> bool:
        return bool(self._get_redis())

    def redis(self):
        r = self._get_redis()
        return r if r else None

    def set_nx(self, key: str, value: str, ttl: int) -> bool:
        r = self._get_redis()
        if r:
            try:
                return bool(r.set(str(key), str(value), nx=True, ex=int(ttl or 0) or None))
            except Exception:
                return False
        return False

    def _now(self) -> float:
        return time.time()

    def _local_get(self, key: str) -> Optional[str]:
        v = self._local.get(key)
        if not v:
            return None
        exp, raw = v
        if exp and exp < self._now():
            try:
                del self._local[key]
            except Exception:
                pass
            return None
        return raw

    def _local_set(self, key: str, raw: str, ttl: int) -> None:
        exp = self._now() + int(ttl) if ttl else 0
        self._local[key] = (exp, raw)
        try:
            n = len(self._local)
            if n > int(self._local_cap):
                target = max(int(self._local_cap * 0.9), 1)
                for k, (e, _) in list(self._local.items()):
                    if e and e < self._now():
                        self._local.pop(k, None)
                if len(self._local) > target:
                    over = len(self._local) - target
                    for k in list(self._local.keys())[:over]:
                        self._local.pop(k, None)
        except Exception:
            pass

    def _local_hash_get(self, key: str) -> Optional[Dict[str, int]]:
        v = self._local_hash.get(key)
        if not v:
            return None
        exp, obj = v
        if exp and exp < self._now():
            try:
                del self._local_hash[key]
            except Exception:
                pass
            return None
        if not isinstance(obj, dict):
            return None
        return obj

    def _local_hash_set(self, key: str, obj: Dict[str, int], ttl: int) -> None:
        exp = self._now() + int(ttl) if ttl else 0
        self._local_hash[key] = (exp, obj)
        try:
            n = len(self._local_hash)
            if n > int(self._local_hash_cap):
                target = max(int(self._local_hash_cap * 0.9), 1)
                for k, (e, _) in list(self._local_hash.items()):
                    if e and e < self._now():
                        self._local_hash.pop(k, None)
                if len(self._local_hash) > target:
                    over = len(self._local_hash) - target
                    for k in list(self._local_hash.keys())[:over]:
                        self._local_hash.pop(k, None)
        except Exception:
            pass

    def get_json(self, key: str) -> Optional[Any]:
        r = self._get_redis()
        raw = None
        if r:
            try:
                raw = r.get(key)
            except Exception:
                raw = None
        if raw is None:
            raw = self._local_get(key)
        if not raw:
            return None
        try:
            return json.loads(raw)
        except Exception:
            return None

    def set_json(self, key: str, value: Any, ttl: int) -> None:
        raw = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        r = self._get_redis()
        if r:
            try:
                r.setex(key, int(ttl), raw)
                return
            except Exception:
                pass
        self._local_set(key, raw, ttl)

    def get_or_set_json(self, key: str, ttl: int, builder: Callable[[], Any], lock_ttl: int = 5) -> Any:
        v = self.get_json(key)
        if v is not None:
            return v

        lock_key = f"lock:{key}"
        r = self._get_redis()
        got = False
        if r:
            try:
                got = bool(r.set(lock_key, "1", nx=True, ex=int(lock_ttl)))
            except Exception:
                got = False

        if not got and r:
            wait_until = time.time() + float(max(1, min(int(lock_ttl or 5), 8)))
            step = 0
            while time.time() < wait_until:
                v2 = self.get_json(key)
                if v2 is not None:
                    return v2
                try:
                    time.sleep(min(0.02 + step * 0.01, 0.1))
                except Exception:
                    pass
                step += 1
                if r:
                    try:
                        got = bool(r.set(lock_key, "1", nx=True, ex=int(lock_ttl)))
                        if got:
                            break
                    except Exception:
                        pass

        out = builder()
        try:
            self.set_json(key, out, ttl)
        except Exception:
            pass
        if got and r:
            try:
                r.delete(lock_key)
            except Exception:
                pass
        return out

    def version(self, ns: str) -> int:
        key = f"v:{ns}"
        r = self._get_redis()
        if r:
            try:
                v = r.get(key)
                if v is None:
                    r.set(key, "1")
                    return 1
                return int(v)
            except Exception:
                pass
        v2 = self._versions.get(key)
        if not v2:
            self._versions[key] = 1
            return 1
        return int(v2)

    def bump(self, ns: str) -> int:
        key = f"v:{ns}"
        r = self._get_redis()
        if r:
            try:
                return int(r.incr(key))
            except Exception:
                pass
        self._versions[key] = int(self._versions.get(key) or 1) + 1
        return int(self._versions[key])

    def hincrby(self, key: str, field: str, delta: int, ttl: int = 0) -> Optional[int]:
        r = self._get_redis()
        if r:
            try:
                v = r.hincrby(key, field, int(delta))
                if ttl:
                    try:
                        r.expire(key, int(ttl))
                    except Exception:
                        pass
                return int(v)
            except Exception:
                pass
        try:
            obj = self._local_hash_get(key) or {}
            f = str(field or "")
            cur = int(obj.get(f) or 0) + int(delta)
            obj[f] = int(cur)
            self._local_hash_set(key, obj, ttl=int(ttl or 0))
            return int(cur)
        except Exception:
            return None

    def hgetall(self, key: str) -> Optional[Dict[str, str]]:
        r = self._get_redis()
        if r:
            try:
                out = r.hgetall(key)
                if not isinstance(out, dict):
                    return None
                return {str(k): str(v) for k, v in out.items()}
            except Exception:
                pass
        try:
            obj = self._local_hash_get(key)
            if not obj:
                return {}
            return {str(k): str(v) for k, v in obj.items()}
        except Exception:
            return None

    def eval(self, script: str, keys=None, args=None):
        r = self._get_redis()
        if not r:
            return None
        try:
            return r.eval(script, len(keys or []), *(keys or []), *(args or []))
        except Exception:
            return None

    def script_load(self, script: str) -> Optional[str]:
        r = self._get_redis()
        if not r:
            return None
        try:
            return str(r.script_load(script))
        except Exception:
            return None

    def evalsha(self, sha: str, keys=None, args=None):
        r = self._get_redis()
        if not r:
            return None
        try:
            return r.evalsha(sha, len(keys or []), *(keys or []), *(args or []))
        except Exception as e:
            msg = str(e)
            if "NOSCRIPT" in msg:
                return "__NOSCRIPT__"
            return None

    def eval_cached(self, script: str, keys=None, args=None) -> Any:
        r = self._get_redis()
        if not r:
            return None
        sig = hashlib.sha1(script.encode("utf-8")).hexdigest()
        sha = self._script_shas.get(sig)
        if sha:
            res = self.evalsha(sha, keys=keys, args=args)
            if res != "__NOSCRIPT__":
                return res
        sha2 = self.script_load(script)
        if sha2:
            self._script_shas[sig] = sha2
            res = self.evalsha(sha2, keys=keys, args=args)
            if res != "__NOSCRIPT__":
                return res
        return self.eval(script, keys=keys, args=args)


cache = Cache()


def stable_sig(parts: Any) -> str:
    raw = json.dumps(parts, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]
