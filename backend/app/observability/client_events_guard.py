from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

from app.core.cache import cache
from app.core.config import get_settings
from app.observability.runtime_client_events import patch_runtime_client_events, read_runtime_client_events

try:
    from prometheus_client import Counter

    CLIENT_EVENT_AUTOGUARD_TOTAL = Counter(
        "aiseek_client_event_autoguard_total",
        "Client events autoguard actions",
        ["action"],
    )
except Exception:
    CLIENT_EVENT_AUTOGUARD_TOTAL = None


def _streams_and_group() -> Tuple[List[str], str]:
    s = get_settings()
    base_stream = str(getattr(s, "CLIENT_EVENT_STREAM_KEY", "events:client") or "events:client")
    group = str(getattr(s, "CLIENT_EVENT_STREAM_GROUP", "client_events") or "client_events")
    shard_stream = bool(getattr(s, "CLIENT_EVENT_STREAM_SHARD_ENABLED", True))
    topics_raw = str(getattr(s, "CLIENT_EVENT_STREAM_TOPICS", "feed,player,search,other") or "feed,player,search,other")
    topics = [t.strip() for t in topics_raw.split(",") if t.strip()]
    streams = [base_stream]
    if shard_stream and topics:
        streams = [f"{base_stream}:{t}" for t in topics[:16]]
    return streams, group


def _group_backlog(r, stream: str, group: str) -> int:
    pending = 0
    lag = None
    try:
        gs = r.xinfo_groups(stream)
        if isinstance(gs, list):
            for g in gs:
                if not isinstance(g, dict):
                    continue
                if str(g.get("name") or "") != str(group):
                    continue
                try:
                    pending = int(g.get("pending") or 0)
                except Exception:
                    pending = 0
                if g.get("lag") is not None:
                    try:
                        lag = int(g.get("lag") or 0)
                    except Exception:
                        lag = 0
                break
    except Exception:
        lag = None
    if lag is None:
        try:
            pending2 = r.xpending(stream, group)
            pending = int(pending2.get("pending") or 0) if isinstance(pending2, dict) else pending
        except Exception:
            pass
        try:
            xlen = int(r.xlen(stream) or 0)
        except Exception:
            xlen = 0
        return max(pending, xlen)
    return max(int(pending), int(lag))


def get_client_event_backlog() -> Dict[str, Any]:
    streams, group = _streams_and_group()
    r = cache.redis()
    if not r:
        return {"ok": False, "error": "redis_unavailable", "streams": streams, "group": group}
    by_stream: Dict[str, int] = {}
    max_backlog = 0
    for st in streams:
        b = 0
        try:
            b = int(_group_backlog(r, st, group))
        except Exception:
            b = 0
        by_stream[st] = int(b)
        if b > max_backlog:
            max_backlog = int(b)
    return {"ok": True, "pending": by_stream, "pending_max": int(max_backlog), "streams": streams, "group": group}


def apply_client_events_degrade(*, ingest_sample_rate: float, disable_persist: bool) -> Dict[str, Any]:
    cur = read_runtime_client_events()
    try:
        cur_rate = float(cur.get("ingest_sample_rate")) if cur.get("ingest_sample_rate") is not None else 1.0
    except Exception:
        cur_rate = 1.0
    r2 = float(ingest_sample_rate)
    if r2 < 0:
        r2 = 0.0
    if r2 > 1:
        r2 = 1.0
    delta: Dict[str, Any] = {"ingest_sample_rate": float(min(cur_rate, r2)), "autoguard_ts": int(time.time())}
    if disable_persist:
        delta["persist_enabled"] = False
        delta["persist_strict"] = False
    delta["autoguard_degraded"] = True
    out = patch_runtime_client_events(delta)
    try:
        if CLIENT_EVENT_AUTOGUARD_TOTAL:
            CLIENT_EVENT_AUTOGUARD_TOTAL.labels("degrade").inc(1)
    except Exception:
        pass
    return out if isinstance(out, dict) else {}


def apply_client_events_recover(*, ingest_sample_rate: float, enable_persist: bool) -> Dict[str, Any]:
    r2 = float(ingest_sample_rate)
    if r2 < 0:
        r2 = 0.0
    if r2 > 1:
        r2 = 1.0
    delta: Dict[str, Any] = {"ingest_sample_rate": float(r2), "autoguard_ts": int(time.time()), "autoguard_degraded": False}
    if enable_persist:
        delta["persist_enabled"] = True
    out = patch_runtime_client_events(delta)
    try:
        if CLIENT_EVENT_AUTOGUARD_TOTAL:
            CLIENT_EVENT_AUTOGUARD_TOTAL.labels("recover").inc(1)
    except Exception:
        pass
    return out if isinstance(out, dict) else {}
