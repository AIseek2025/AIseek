import json
from datetime import datetime
from typing import Any, Optional, Tuple

from app.core.cache import cache


def stream_enabled() -> bool:
    try:
        return bool(cache.redis_enabled())
    except Exception:
        return False


def append_job_event(job_id: str, kind: str, payload: Any = None, ttl: int = 3600) -> Optional[int]:
    jid = str(job_id or "").strip()
    if not jid:
        return None
    stream_key = f"ai:job:events_stream:{jid}"
    seq_key = f"ai:job:events_seq:{jid}"
    list_key = f"ai:job:events:{jid}"

    ts = int(datetime.now().timestamp())
    ev = {"ts": ts, "type": str(kind or "event"), "data": payload}
    r = None
    try:
        r = cache._get_redis()
    except Exception:
        r = None

    seq: Optional[int] = None
    if r:
        try:
            seq = int(r.incr(seq_key))
            try:
                r.expire(seq_key, int(ttl))
            except Exception:
                pass
            sid = f"{seq}-0"
            fields = {"ts": str(ts), "type": ev["type"], "data": json.dumps(payload, ensure_ascii=False, separators=(",", ":"))}
            try:
                r.xadd(stream_key, fields, id=sid, maxlen=2000, approximate=True)
            except Exception:
                r.xadd(stream_key, fields, id=sid)
            try:
                r.expire(stream_key, int(ttl))
            except Exception:
                pass
        except Exception:
            seq = None

    if seq is None:
        try:
            arr = cache.get_json(list_key)
            if not isinstance(arr, list):
                arr = []
            seq = int(arr[-1].get("id") or 0) + 1 if arr else 1
        except Exception:
            seq = int(ts)

    ev["id"] = int(seq)

    try:
        arr = cache.get_json(list_key)
        if not isinstance(arr, list):
            arr = []
        arr.append(ev)
        if len(arr) > 200:
            arr = arr[-200:]
        cache.set_json(list_key, arr, ttl=ttl)
    except Exception:
        try:
            cache.set_json(list_key, [ev], ttl=ttl)
        except Exception:
            pass

    return int(seq)


def xread_job_events(job_id: str, last_id: int, block_ms: int = 15000, count: int = 50) -> Tuple[int, list]:
    jid = str(job_id or "").strip()
    if not jid:
        return last_id, []
    stream_key = f"ai:job:events_stream:{jid}"
    try:
        r = cache._get_redis()
    except Exception:
        r = None
    if not r:
        return last_id, []
    start = f"{int(last_id or 0)}-0"
    try:
        out = r.xread({stream_key: start}, count=int(count or 50), block=int(block_ms or 0))
    except Exception:
        return last_id, []
    if not out:
        return last_id, []
    items = []
    cur = int(last_id or 0)
    try:
        for _stream, entries in out:
            for sid, fields in entries:
                try:
                    seq = int(str(sid).split("-", 1)[0])
                except Exception:
                    continue
                if seq <= cur:
                    continue
                cur = seq
                try:
                    ts = int(fields.get("ts") or 0)
                except Exception:
                    ts = 0
                t = str(fields.get("type") or "event")
                raw = fields.get("data")
                try:
                    data = json.loads(raw) if isinstance(raw, str) else raw
                except Exception:
                    data = raw
                items.append({"id": seq, "ts": ts, "type": t, "data": data})
    except Exception:
        return int(last_id or 0), []
    return cur, items
