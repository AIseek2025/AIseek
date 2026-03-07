from __future__ import annotations

from typing import Dict, Iterable, List

from app.core.cache import cache


def _to_int(v) -> int:
    try:
        return int(float(v or 0))
    except Exception:
        return 0


def get_search_ctr_map(post_ids: Iterable[int]) -> Dict[int, float]:
    ids = []
    for x in post_ids:
        try:
            i = int(x)
            if i > 0:
                ids.append(i)
        except Exception:
            continue
    if not ids:
        return {}
    r = cache.redis()
    if not r:
        return {}
    pipe = r.pipeline()
    for pid in ids[:1000]:
        pipe.hmget(f"eng:post:{int(pid)}", "search_impr", "search_click")
    out = pipe.execute()
    m: Dict[int, float] = {}
    for pid, row in zip(ids[:1000], out or []):
        try:
            if not isinstance(row, list) or len(row) < 2:
                m[int(pid)] = 0.0
                continue
            impr = _to_int(row[0])
            clk = _to_int(row[1])
            ctr = float(clk + 1) / float(impr + 10) if impr >= 0 and clk >= 0 else 0.0
            if ctr < 0:
                ctr = 0.0
            if ctr > 1:
                ctr = 1.0
            m[int(pid)] = float(ctr)
        except Exception:
            m[int(pid)] = 0.0
    return m


def get_feed_impression_map(post_ids: Iterable[int]) -> Dict[int, int]:
    ids = []
    for x in post_ids:
        try:
            i = int(x)
            if i > 0:
                ids.append(i)
        except Exception:
            continue
    if not ids:
        return {}
    r = cache.redis()
    if not r:
        return {}
    pipe = r.pipeline()
    for pid in ids[:2000]:
        pipe.hget(f"eng:post:{int(pid)}", "feed_impr")
    out = pipe.execute()
    m: Dict[int, int] = {}
    for pid, v in zip(ids[:2000], out or []):
        m[int(pid)] = _to_int(v)
    return m


def exposure_adjusted_score(raw_score: float, impressions: int, smoothing: int) -> float:
    try:
        s = float(raw_score or 0.0)
    except Exception:
        s = 0.0
    if s <= 0:
        return 0.0
    imp = impressions if isinstance(impressions, int) else _to_int(impressions)
    if imp < 0:
        imp = 0
    k = int(smoothing or 0)
    if k < 1:
        k = 1
    if k > 1_000_000:
        k = 1_000_000
    try:
        return float(s) / float(1.0 + float(imp) / float(k))
    except Exception:
        return float(s)


def rerank_in_groups(ids: List[int], score_map: Dict[int, float], group_size: int) -> List[int]:
    g = int(group_size or 0)
    if g < 2:
        return ids
    if g > 50:
        g = 50
    out: List[int] = []
    for i in range(0, len(ids), g):
        chunk = ids[i : i + g]
        chunk2 = sorted(chunk, key=lambda pid: (-float(score_map.get(int(pid), 0.0) or 0.0), int(pid)))
        out.extend(chunk2)
    return out
