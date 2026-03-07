import time
from typing import Dict

from sqlalchemy.orm import Session
from sqlalchemy import text


def record_post_counter_event(
    db: Session,
    *,
    post_id: int,
    counter: str,
    delta: int,
    event_key: str,
) -> bool:
    if not post_id or not counter or not event_key or not isinstance(delta, int):
        return False
    try:
        dialect = getattr(getattr(db, "bind", None), "dialect", None)
        name = getattr(dialect, "name", "") or ""
        if name == "sqlite":
            db.execute(
                text(
                    "INSERT OR IGNORE INTO post_counter_events(post_id,counter,delta,event_key,created_at) "
                    "VALUES (:post_id,:counter,:delta,:event_key,:created_at)"
                ),
                {
                    "post_id": int(post_id),
                    "counter": str(counter),
                    "delta": int(delta),
                    "event_key": str(event_key),
                    "created_at": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
                },
            )
            return True
    except Exception:
        return False
    return False


def apply_post_counter_deltas(db: Session, post_id: int, batch_size: int = 2000) -> int:
    rows = db.execute(
        text(
            "SELECT id, counter, delta FROM post_counter_events WHERE post_id=:pid ORDER BY id ASC LIMIT :lim"
        ),
        {"pid": int(post_id), "lim": int(batch_size)},
    ).fetchall()

    if not rows:
        return 0

    deltas: Dict[str, int] = {"likes": 0, "favorites": 0, "comments": 0}
    max_id = 0
    for rid, counter, delta in rows:
        if int(rid) > max_id:
            max_id = int(rid)
        if counter in deltas:
            deltas[counter] += int(delta or 0)

    db.execute(
        text(
            "INSERT OR IGNORE INTO post_counters(post_id,likes_count,favorites_count,comments_count) VALUES (:pid,0,0,0)"
        ),
        {"pid": int(post_id)},
    )

    for counter, d in deltas.items():
        if not d:
            continue
        col = f"{counter}_count"
        db.execute(
            text(
                f"UPDATE post_counters SET {col}=CASE WHEN COALESCE({col},0) + :d < 0 THEN 0 ELSE COALESCE({col},0) + :d END, updated_at=CURRENT_TIMESTAMP WHERE post_id=:pid"
            ),
            {"d": int(d), "pid": int(post_id)},
        )

    db.execute(
        text("DELETE FROM post_counter_events WHERE post_id=:pid AND id<=:max_id"),
        {"pid": int(post_id), "max_id": int(max_id)},
    )
    return len(rows)
