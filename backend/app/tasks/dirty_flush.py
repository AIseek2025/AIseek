import time

from sqlalchemy import text

from app.core.celery_app import celery_app
from app.core.cache import cache
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.hot_counter_service import take_delta, write_mode, take_deltas
from app.services.counter_service import apply_post_counter_deltas

try:
    from prometheus_client import Counter, Histogram

    DIRTY_FLUSH_BATCHES = Counter("dirty_flush_batches_total", "Dirty flush batches", ["shard"])
    DIRTY_FLUSH_POSTS = Counter("dirty_flush_posts_total", "Dirty flush posts", ["shard"])
    DIRTY_FLUSH_LAT = Histogram("dirty_flush_seconds", "Dirty flush latency seconds", ["shard"], buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5))
except Exception:
    DIRTY_FLUSH_BATCHES = None
    DIRTY_FLUSH_POSTS = None
    DIRTY_FLUSH_LAT = None


def _pop_dirty(shard: int, batch: int) -> list[int]:
    r = cache._get_redis()  # noqa: SLF001
    if not r:
        return []
    try:
        pairs = r.zpopmin(f"post:dirty:{int(shard)}", batch)
        out = []
        for member, _score in pairs:
            try:
                out.append(int(member))
            except Exception:
                continue
        return out
    except Exception:
        return []


@celery_app.task(bind=True)
def flush_dirty_post_counters(self, shard: int = 0) -> int:
    if write_mode() != "redis":
        return 0

    s = get_settings()
    batch = int(getattr(s, "HOT_DIRTY_FLUSH_BATCH", 200) or 200)
    max_loops = int(getattr(s, "HOT_DIRTY_FLUSH_MAX_LOOPS", 20) or 20)
    budget_ms = int(getattr(s, "HOT_DIRTY_FLUSH_BUDGET_MS", 800) or 800)
    start = time.perf_counter()
    total = 0
    shard_s = str(int(shard))

    db = SessionLocal()
    try:
        for _ in range(max_loops):
            if (time.perf_counter() - start) * 1000.0 > float(budget_ms):
                break
            ids = _pop_dirty(int(shard), batch)
            if not ids:
                break
            if DIRTY_FLUSH_BATCHES is not None:
                try:
                    DIRTY_FLUSH_BATCHES.labels(shard_s).inc()
                except Exception:
                    pass
            total += len(ids)

            deltas_map = {}
            try:
                deltas_map = take_deltas(ids)
            except Exception:
                pass

            likes_updates = []
            favorites_updates = []
            comments_updates = []

            for pid in ids:
                d = deltas_map.get(pid)
                if d:
                    if d.get("likes"):
                        likes_updates.append({"pid": pid, "d": int(d["likes"])})
                    if d.get("favorites"):
                        favorites_updates.append({"pid": pid, "d": int(d["favorites"])})
                    if d.get("comments"):
                        comments_updates.append({"pid": pid, "d": int(d["comments"])})

            try:
                if likes_updates:
                    db.execute(
                        text(
                            "UPDATE posts SET likes_count = CASE WHEN COALESCE(likes_count,0) + :d < 0 THEN 0 ELSE COALESCE(likes_count,0) + :d END WHERE id=:pid"
                        ),
                        likes_updates,
                    )
                if favorites_updates:
                    db.execute(
                        text(
                            "UPDATE posts SET favorites_count = CASE WHEN COALESCE(favorites_count,0) + :d < 0 THEN 0 ELSE COALESCE(favorites_count,0) + :d END WHERE id=:pid"
                        ),
                        favorites_updates,
                    )
                if comments_updates:
                    db.execute(
                        text(
                            "UPDATE posts SET comments_count = CASE WHEN COALESCE(comments_count,0) + :d < 0 THEN 0 ELSE COALESCE(comments_count,0) + :d END WHERE id=:pid"
                        ),
                        comments_updates,
                    )
            except Exception:
                pass

            for pid in ids:
                try:
                    for _ in range(2):
                        n = apply_post_counter_deltas(db, int(pid), batch_size=2000)
                        if n == 0:
                            break
                except Exception:
                    pass

        try:
            db.commit()
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
        if DIRTY_FLUSH_POSTS is not None:
            try:
                DIRTY_FLUSH_POSTS.labels(shard_s).inc(total)
            except Exception:
                pass
        if DIRTY_FLUSH_LAT is not None:
            try:
                DIRTY_FLUSH_LAT.labels(shard_s).observe(time.perf_counter() - start)
            except Exception:
                pass
        return int(total)
    finally:
        try:
            db.close()
        except Exception:
            pass


@celery_app.task(bind=True)
def flush_all_dirty_post_counters(self) -> int:
    try:
        shards = int(get_settings().HOT_DIRTY_SHARDS or 8)
    except Exception:
        shards = 8
    total = 0
    for shard in range(max(1, shards)):
        try:
            total += int(flush_dirty_post_counters(shard=shard))
        except Exception:
            continue
    return int(total)
