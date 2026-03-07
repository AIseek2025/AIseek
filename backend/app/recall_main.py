import os
import time
from typing import Any, Dict, List, Optional

import asyncio
import random
import datetime
import math
from fastapi import FastAPI, Query, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.core.cache import cache
from app.core.config import settings
from app.db.session import SessionLocalRead
from app.middleware.metrics import MetricsMiddleware
from app.middleware.request_logging import RequestLoggingMiddleware
from app.models.all_models import Interaction, Post


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_redis = None


def _get_redis():
    global _redis
    if _redis is not None:
        return _redis
    try:
        import redis

        _redis = redis.Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_timeout=float(getattr(settings, "REDIS_SOCKET_TIMEOUT_SEC", 0.6) or 0.6),
            socket_connect_timeout=float(getattr(settings, "REDIS_CONNECT_TIMEOUT_SEC", 0.3) or 0.3),
            max_connections=int(getattr(settings, "REDIS_MAX_CONNECTIONS", 200) or 200),
        )
    except Exception:
        _redis = False
    return _redis


def _stats_incr(result: str, n: int = 1) -> None:
    r = _get_redis()
    if not r:
        return
    try:
        r.hincrby("stats:recall_cache", str(result), int(n))
    except Exception:
        return


def _limit(v: int) -> int:
    try:
        n = int(v)
    except Exception:
        n = 200
    if n < 10:
        n = 10
    if n > 5000:
        n = 5000
    return n


def create_app() -> FastAPI:
    app = FastAPI(title="AIseek Feed Recall", openapi_url="/openapi.json")
    build_id = os.getenv("AISEEK_BUILD_ID") or time.strftime("%Y-%m-%d.%H%M%S")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_middleware(RequestLoggingMiddleware)
    try:
        app.add_middleware(GZipMiddleware, minimum_size=800)
    except Exception:
        pass
    try:
        app.add_middleware(MetricsMiddleware)
    except Exception:
        pass

    try:
        from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
        from starlette.responses import Response

        @app.get("/metrics")
        def metrics():
            payload = generate_latest()
            try:
                r = _get_redis()
                hit = 0
                miss = 0
                if r:
                    obj = r.hgetall("stats:recall_cache") or {}
                    try:
                        hit = int(obj.get("hit") or 0)
                    except Exception:
                        hit = 0
                    try:
                        miss = int(obj.get("miss") or 0)
                    except Exception:
                        miss = 0
                extra = (
                    "\n# HELP aiseek_recall_cache_stats_total Recall cache hit/miss\n"
                    "# TYPE aiseek_recall_cache_stats_total counter\n"
                    f'aiseek_recall_cache_stats_total{{result="hit"}} {float(hit)}\n'
                    f'aiseek_recall_cache_stats_total{{result="miss"}} {float(miss)}\n'
                ).encode("utf-8")
                payload = payload + extra
            except Exception:
                pass
            return Response(payload, media_type=CONTENT_TYPE_LATEST)
    except Exception:
        pass

    @app.get("/healthz")
    def healthz():
        ok = True
        try:
            ok = ok and bool(cache.redis_enabled())
        except Exception:
            pass
        return {"ok": bool(ok), "build_id": build_id}

    def _parse_prewarm_cats() -> List[str]:
        raw = str(getattr(settings, "FEED_RECALL_PREWARM_CATS", "all") or "all")
        parts = [p.strip() for p in raw.split(",")]
        out = []
        for p in parts:
            if not p:
                continue
            out.append(p)
        if not out:
            out = ["all"]
        return out[:50]

    def _recent_candidates(db, *, cat_key: str, limit2: int) -> List[Dict[str, Any]]:
        qq = db.query(Post.id, Post.category, Post.created_at).filter(Post.status == "done")
        if cat_key != "all":
            qq = qq.filter(Post.category == cat_key)
        rows = qq.order_by(Post.created_at.desc(), Post.id.desc()).limit(limit2).all()
        out: List[Dict[str, Any]] = []
        for pid, category, created_at in rows:
            ts = float(created_at.timestamp()) if created_at is not None else 0.0
            out.append({"id": int(pid), "category": category or "", "created_at": ts, "score": 0.0})
        return out

    def _hot_candidates(db, *, cat_key: str, limit2: int) -> List[Dict[str, Any]]:
        r = _get_redis()
        if r:
            try:
                bucket_sec = int(getattr(settings, "FEED_RECALL_HOT_BUCKET_SEC", 300) or 300)
                if bucket_sec < 5:
                    bucket_sec = 5
                if bucket_sec > 3600:
                    bucket_sec = 3600
                window = int(getattr(settings, "FEED_RECALL_HOT_WINDOW_SEC", 86400) or 86400)
                if window < 60:
                    window = 60
                if window > 2592000:
                    window = 2592000
                n_buckets = int(window // bucket_sec) + 1
                now = int(time.time())
                cur = now // bucket_sec
                keys = [f"hot:z:{bucket_sec}:{cur - i}" for i in range(n_buckets)]
                decay = bool(getattr(settings, "FEED_RECALL_HOT_DECAY_ENABLED", False)) or False
                weighted = None
                if decay:
                    half = int(getattr(settings, "FEED_RECALL_HOT_DECAY_HALF_LIFE_SEC", 900) or 900)
                    if half < 1:
                        half = 1
                    weighted = {}
                    for i in range(n_buckets):
                        age = float(i * bucket_sec)
                        w = math.pow(0.5, age / float(half))
                        if w < 1e-6:
                            w = 1e-6
                        weighted[keys[i]] = float(w)
                tmp = f"hot:tmp:{bucket_sec}:{cur}"
                pipe = r.pipeline()
                pipe.zunionstore(tmp, weighted if weighted else keys)
                pipe.expire(tmp, 3)
                fetch_n = int(limit2) * (5 if cat_key != "all" else 2)
                if fetch_n < limit2:
                    fetch_n = limit2
                if fetch_n > 5000:
                    fetch_n = 5000
                pipe.zrevrange(tmp, 0, fetch_n - 1, withscores=True)
                res = pipe.execute()
                ids_raw = res[-1] if res and isinstance(res, list) else []
                ids = []
                scores = {}
                for pair in ids_raw or []:
                    try:
                        pid = int(pair[0])
                        sc = float(pair[1])
                        ids.append(pid)
                        scores[pid] = sc
                    except Exception:
                        continue
                if ids:
                    qq = db.query(Post.id, Post.category, Post.created_at).filter(Post.status == "done", Post.id.in_(ids))
                    if cat_key != "all":
                        qq = qq.filter(Post.category == cat_key)
                    rows = qq.all()
                    m = {int(pid): (cat or "", created_at) for pid, cat, created_at in rows}
                    out: List[Dict[str, Any]] = []
                    for pid in ids:
                        v = m.get(int(pid))
                        if not v:
                            continue
                        cat, created_at = v
                        ts = float(created_at.timestamp()) if created_at is not None else 0.0
                        out.append({"id": int(pid), "category": cat or "", "created_at": ts, "score": float(scores.get(int(pid)) or 0.0)})
                        if len(out) >= limit2:
                            break
                    return out
            except Exception:
                pass

        from sqlalchemy import func

        window = int(getattr(settings, "FEED_RECALL_HOT_WINDOW_SEC", 86400) or 86400)
        if window < 60:
            window = 60
        if window > 2592000:
            window = 2592000
        min_ts = time.time() - float(window)
        min_dt = datetime.datetime.fromtimestamp(min_ts, tz=datetime.timezone.utc)

        qq = (
            db.query(Post.id, Post.category, Post.created_at, func.count(Interaction.id).label("c"))
            .join(Interaction, Interaction.post_id == Post.id)
            .filter(Post.status == "done", Interaction.type.in_(["like", "favorite"]), Interaction.created_at >= min_dt)
        )
        if cat_key != "all":
            qq = qq.filter(Post.category == cat_key)
        rows = qq.group_by(Post.id).order_by(func.count(Interaction.id).desc(), Post.created_at.desc(), Post.id.desc()).limit(limit2).all()
        out: List[Dict[str, Any]] = []
        for pid, category, created_at, c in rows:
            ts = float(created_at.timestamp()) if created_at is not None else 0.0
            try:
                sc = float(c or 0)
            except Exception:
                sc = 0.0
            out.append({"id": int(pid), "category": category or "", "created_at": ts, "score": float(sc)})
        return out

    def _cache_key(cat_key: str, kind: str) -> str:
        k = (kind or "recent").strip().lower()
        if k not in {"recent", "hot"}:
            k = "recent"
        v = cache.version(f"recall:{k}:{cat_key}")
        return f"recall:{k}:cand:v{v}:cat{cat_key}"

    def _dedupe_merge(primary: List[Dict[str, Any]], secondary: List[Dict[str, Any]], limit2: int) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        seen = set()
        for it in primary + secondary:
            if not isinstance(it, dict):
                continue
            pid = it.get("id")
            if not pid:
                continue
            try:
                pid_i = int(pid)
            except Exception:
                continue
            if pid_i in seen:
                continue
            seen.add(pid_i)
            out.append(it)
            if len(out) >= limit2:
                break
        return out

    def _get_or_build(db, *, cat_key: str, kind: str, limit2: int) -> List[Dict[str, Any]]:
        ttl = int(getattr(settings, "FEED_CAND_TTL_SEC", 5) or 5)
        if ttl < 1:
            ttl = 1
        if ttl > 600:
            ttl = 600
        if kind == "hot":
            ttl2 = int(getattr(settings, "FEED_RECALL_HOT_TTL_SEC", 20) or 20)
            if ttl2 < 1:
                ttl2 = 1
            if ttl2 > 600:
                ttl2 = 600
            ttl = ttl2

        key = _cache_key(cat_key, kind)
        hit = False
        arr = None
        try:
            cached = cache.get_json(key)
            if isinstance(cached, list):
                hit = True
                arr = cached
        except Exception:
            arr = None
        if arr is None:
            if kind == "hot":
                arr = _hot_candidates(db, cat_key=cat_key, limit2=limit2)
            else:
                arr = _recent_candidates(db, cat_key=cat_key, limit2=limit2)
            try:
                cache.set_json(key, arr, ttl=ttl)
            except Exception:
                pass
        _stats_incr("hit" if hit else "miss", 1)
        if not isinstance(arr, list):
            return []
        return arr[:limit2]

    @app.on_event("startup")
    async def _startup_prewarm() -> None:
        enabled = bool(getattr(settings, "FEED_RECALL_PREWARM_ENABLED", False)) or False
        if not enabled:
            return
        interval = int(getattr(settings, "FEED_RECALL_PREWARM_INTERVAL_SEC", 30) or 30)
        if interval < 5:
            interval = 5
        if interval > 600:
            interval = 600
        limit2 = _limit(int(getattr(settings, "FEED_RECALL_PREWARM_LIMIT", 500) or 500))
        cats = _parse_prewarm_cats()
        ttl = int(getattr(settings, "FEED_CAND_TTL_SEC", 5) or 5)
        if ttl < 1:
            ttl = 1
        if ttl > 600:
            ttl = 600
        max_cats = int(getattr(settings, "FEED_RECALL_PREWARM_MAX_CATS_PER_TICK", 1) or 1)
        if max_cats < 1:
            max_cats = 1
        if max_cats > 50:
            max_cats = 50
        budget_ms = int(getattr(settings, "FEED_RECALL_PREWARM_DB_BUDGET_MS", 150) or 150)
        if budget_ms < 10:
            budget_ms = 10
        if budget_ms > 5000:
            budget_ms = 5000
        state = {"i": 0}

        async def loop():
            while True:
                start = time.time()
                db = SessionLocalRead()
                try:
                    n = len(cats)
                    if n <= 0:
                        await asyncio.sleep(interval)
                        continue
                    start_i = int(state.get("i") or 0) % n
                    processed = 0
                    for step in range(n):
                        if processed >= max_cats:
                            break
                        if (time.time() - start) * 1000.0 >= float(budget_ms):
                            break
                        idx = (start_i + step) % n
                        cat_key = cats[idx]
                        try:
                            _get_or_build(db, cat_key=cat_key, kind="recent", limit2=limit2)
                            processed += 1
                        except Exception:
                            continue
                    state["i"] = int(start_i + processed) % n
                finally:
                    try:
                        db.close()
                    except Exception:
                        pass
                await asyncio.sleep(max(1, interval + random.random()))

        asyncio.create_task(loop())

    def _enforce_signed(request: Request) -> None:
        required = bool(getattr(settings, "FEED_RECALL_SIGNED_REQUIRED", False)) or False
        secret = str(getattr(settings, "FEED_RECALL_SHARED_SECRET", "") or "").strip()
        if not (required and secret):
            return
        ts = request.headers.get("x-aiseek-ts") or request.headers.get("X-Aiseek-Ts")
        sig = request.headers.get("x-aiseek-sig") or request.headers.get("X-Aiseek-Sig")
        if not ts or not sig:
            raise HTTPException(status_code=401, detail="missing_signature")
        try:
            ts_i = int(ts)
        except Exception:
            raise HTTPException(status_code=401, detail="bad_signature")
        window = int(getattr(settings, "FEED_RECALL_SIG_WINDOW_SEC", 30) or 30)
        if window < 3:
            window = 3
        if window > 600:
            window = 600
        now = int(time.time())
        if abs(now - ts_i) > window:
            raise HTTPException(status_code=401, detail="expired_signature")
        try:
            import hmac
            import hashlib

            msg = f"{ts_i}\n{request.method.upper()}\n{request.url.path}".encode("utf-8")
            exp = hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(str(sig), str(exp)):
                raise HTTPException(status_code=401, detail="bad_signature")
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=401, detail="bad_signature")

    def _rate_limit(request: Request) -> None:
        limit = int(getattr(settings, "FEED_RECALL_SERVER_RATE_PER_MIN", 3000) or 3000)
        if limit <= 0:
            return
        if limit < 10:
            limit = 10
        if limit > 200000:
            limit = 200000
        try:
            ip = request.headers.get("x-forwarded-for") or ""
            ip = ip.split(",", 1)[0].strip() if ip else ""
        except Exception:
            ip = ""
        if not ip:
            try:
                ip = request.client.host if request.client else ""
            except Exception:
                ip = ""
        if not ip:
            return
        r = None
        try:
            import redis

            r = redis.Redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_timeout=float(getattr(settings, "REDIS_SOCKET_TIMEOUT_SEC", 0.6) or 0.6),
                socket_connect_timeout=float(getattr(settings, "REDIS_CONNECT_TIMEOUT_SEC", 0.3) or 0.3),
                max_connections=int(getattr(settings, "REDIS_MAX_CONNECTIONS", 200) or 200),
            )
        except Exception:
            r = None
        if not r:
            return
        now = int(time.time())
        window = 60
        bucket = now // window
        key = f"rl:recall:{bucket}:{ip}"
        try:
            n = r.incr(key)
            if n == 1:
                r.expire(key, window + 5)
            if int(n) > limit:
                raise HTTPException(status_code=429, detail="rate_limited")
        except HTTPException:
            raise
        except Exception:
            return

    @app.get("/recall")
    def recall(
        request: Request,
        cat: str = Query("all"),
        limit: int = Query(500),
        v: int = Query(0),
        kind: str = Query("recent"),
    ) -> Any:
        _enforce_signed(request)
        _rate_limit(request)
        cat_key = (cat or "all").strip() or "all"
        kind2 = (kind or "recent").strip().lower()
        if kind2 not in {"recent", "hot", "blend"}:
            kind2 = "recent"
        limit2 = _limit(limit)
        db = SessionLocalRead()
        try:
            if kind2 == "blend":
                hot_lim = int(getattr(settings, "FEED_RECALL_BLEND_HOT_LIMIT", 50) or 50)
                if hot_lim < 0:
                    hot_lim = 0
                if hot_lim > limit2:
                    hot_lim = limit2
                hot = _get_or_build(db, cat_key=cat_key, kind="hot", limit2=max(10, hot_lim or 10))
                recent = _get_or_build(db, cat_key=cat_key, kind="recent", limit2=limit2)
                items = _dedupe_merge(hot[:hot_lim], recent, limit2)
            else:
                items = _get_or_build(db, cat_key=cat_key, kind=kind2, limit2=limit2)
            if int(v or 0) == 1:
                return {
                    "version": 1,
                    "cat": cat_key,
                    "items": items,
                    "kind": kind2,
                    "generated_at": int(time.time()),
                }
            return items
        finally:
            try:
                db.close()
            except Exception:
                pass

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "5999") or "5999")
    uvicorn.run("app.recall_main:app", host="0.0.0.0", port=port, reload=False)
