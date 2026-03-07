from __future__ import annotations

import math

from app.services.placeholder.core_types import CandidateClip, SearchPlan


def _tok(s: str) -> set[str]:
    t = str(s or "").lower().replace("-", " ").replace("_", " ")
    parts = [p.strip() for p in t.split() if p.strip()]
    out = set()
    for p in parts:
        if len(p) < 2:
            continue
        out.add(p)
    return out


def score_clip(clip: CandidateClip, plan: SearchPlan) -> float:
    w = float(max(1, int(clip.width)))
    h = float(max(1, int(clip.height)))
    ar = w / h
    target_ar = 9.0 / 16.0 if str(plan.orientation or "portrait").lower().startswith("p") else 16.0 / 9.0
    ar_pen = abs(math.log(max(0.01, ar) / max(0.01, target_ar)))
    res = w * h
    min_res = float(max(1, int(plan.min_width) * int(plan.min_height)))
    res_bonus = min(1.0, math.log(max(res, 1.0) / min_res + 1.0))
    dur = float(max(0, int(clip.duration)))
    target_d = float(max(3, min(int(plan.max_duration), 60)))
    dur_pen = abs(dur - target_d) / max(8.0, target_d)
    q = _tok(plan.query)
    tags = _tok(" ".join(clip.tags)) | _tok(clip.title)
    hit = len(q & tags)
    hit_bonus = min(1.0, float(hit) / 4.0)
    score = 1.2 * res_bonus + 0.9 * hit_bonus - 1.1 * ar_pen - 0.7 * dur_pen
    return float(score)

