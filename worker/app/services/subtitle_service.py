from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class SubtitleTrack:
    lang: str
    label: str
    format: str
    url: str
    kind: str = "subtitles"
    is_default: bool = False


def _fmt_ts(sec: float) -> str:
    if sec < 0:
        sec = 0.0
    ms = int(round(sec * 1000.0))
    h = ms // 3_600_000
    ms -= h * 3_600_000
    m = ms // 60_000
    ms -= m * 60_000
    s = ms // 1000
    ms -= s * 1000
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def _sanitize_lines(text: str) -> list[str]:
    t = str(text or "").replace("\r", "\n")
    parts = [p.strip() for p in t.split("\n") if p.strip()]
    out: list[str] = []
    for p in parts:
        p2 = p.replace("-->", "→").strip()
        if p2:
            out.append(p2)
    return out


def _wrap_two_lines(text: str, max_chars: int) -> str:
    t = str(text or "").strip()
    if not t:
        return ""
    
    # Simple split strategy: 
    # If text is too long, split it by punctuation or length
    if len(t) <= max_chars:
        return t
        
    # Try splitting by common punctuation
    punctuations = ["，", "。", "！", "？", ",", ".", "!", "?"]
    best_split = -1
    
    # Find the punctuation closest to the middle
    mid = len(t) // 2
    min_dist = len(t)
    
    for p in punctuations:
        idx = t.find(p)
        while idx != -1:
            dist = abs(idx - mid)
            if dist < min_dist:
                min_dist = dist
                best_split = idx + 1 # Include punctuation in first line
            idx = t.find(p, idx + 1)
            
    if best_split != -1 and best_split < len(t):
        return t[:best_split].strip() + "\n" + t[best_split:].strip()
        
    # Fallback: Split by length
    cut = max(1, min(len(t) - 1, max_chars))
    return t[:cut].strip() + "\n" + t[cut:].strip()


def build_vtt(
    segments: Iterable[str],
    total_duration_sec: float,
    position_line: str = "88%",
    align: str = "center",
    max_chars_per_line: int = 18,
) -> str:
    segs = [str(x or "").strip() for x in (segments or []) if str(x or "").strip()]
    dur = float(total_duration_sec or 0.0)
    if dur <= 0.2 or not segs:
        return "WEBVTT\n\n"

    weights = [max(1, len(s)) for s in segs]
    wsum = float(sum(weights)) or 1.0
    min_seg = 1.2
    max_seg = 6.5
    gap = 0.06
    total_gaps = gap * max(0, len(segs) - 1)
    usable = max(0.2, dur - total_gaps)

    raw = [(w / wsum) * usable for w in weights]
    clamped = [max(min_seg, min(max_seg, x)) for x in raw]

    sum_c = float(sum(clamped))
    if sum_c <= 0:
        clamped = raw
        sum_c = float(sum(clamped)) or 1.0
    scale = usable / sum_c
    clamped = [max(0.3, x * scale) for x in clamped]

    lines: list[str] = []
    lines.append("WEBVTT")
    lines.append("")
    lines.append("STYLE")
    lines.append("::cue {")
    lines.append("  color: #fff;")
    lines.append("  background: rgba(0,0,0,0.55);")
    lines.append("  text-shadow: 0 2px 8px rgba(0,0,0,0.65);")
    lines.append("  font-weight: 700;")
    lines.append("  font-size: 1.1em;")
    lines.append("  line-height: 1.4;")
    lines.append("}")
    lines.append("")

    t = 0.0
    for i, (seg, seg_dur) in enumerate(zip(segs, clamped), start=1):
        start = t
        end = min(dur, start + float(seg_dur))
        if end <= start:
            continue
        txt = _wrap_two_lines(seg, max_chars=max_chars_per_line)
        if not txt:
            t = end + gap
            continue
        lines.append(str(i))
        lines.append(f"{_fmt_ts(start)} --> {_fmt_ts(end)} line:{position_line} align:{align} position:50%")
        lines.append(txt)
        lines.append("")
        t = end + gap
        if t >= dur:
            break

    return "\n".join(lines).strip() + "\n"


def build_vtt_from_cues(
    cues: Iterable[tuple[float, float, str]],
    position_line: str = "88%",
    align: str = "center",
    max_chars_per_line: int = 18,
) -> str:
    items = []
    for it in cues or []:
        try:
            s, e, t = it
        except Exception:
            continue
        try:
            start = float(s)
            end = float(e)
        except Exception:
            continue
        txt = str(t or "").strip()
        if not txt:
            continue
        if end <= start:
            continue
        items.append((max(0.0, start), max(0.0, end), txt))
    if not items:
        return "WEBVTT\n\n"
    items.sort(key=lambda x: x[0])

    lines: list[str] = []
    lines.append("WEBVTT")
    lines.append("")
    lines.append("STYLE")
    lines.append("::cue {")
    lines.append("  color: #fff;")
    lines.append("  background: rgba(0,0,0,0.55);")
    lines.append("  text-shadow: 0 2px 8px rgba(0,0,0,0.65);")
    lines.append("  font-weight: 700;")
    lines.append("  font-size: 1.1em;")
    lines.append("  line-height: 1.4;")
    lines.append("}")
    lines.append("")

    for i, (start, end, seg) in enumerate(items, start=1):
        txt = _wrap_two_lines(seg, max_chars=max_chars_per_line)
        if not txt:
            continue
        lines.append(str(i))
        lines.append(f"{_fmt_ts(start)} --> {_fmt_ts(end)} line:{position_line} align:{align} position:50%")
        lines.append(txt)
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def build_cues_by_duration(
    segments: Iterable[str],
    total_duration_sec: float,
    *,
    offset_sec: float = 0.0,
    min_seg_sec: float = 0.45,
    max_seg_sec: float = 8.0,
    gap_sec: float = 0.04,
) -> list[tuple[float, float, str]]:
    segs = [str(x or "").strip() for x in (segments or []) if str(x or "").strip()]
    dur = max(0.2, float(total_duration_sec or 0.0))
    if not segs:
        return []
    if len(segs) == 1:
        txt = segs[0]
        st = max(0.0, float(offset_sec or 0.0))
        return [(st, st + dur, txt)]

    weights = [max(1, len(s)) for s in segs]
    wsum = float(sum(weights)) or 1.0
    total_gaps = float(gap_sec) * max(0, len(segs) - 1)
    usable = max(0.2, dur - total_gaps)
    raw = [(w / wsum) * usable for w in weights]
    clamped = [max(float(min_seg_sec), min(float(max_seg_sec), float(x))) for x in raw]
    s0 = float(sum(clamped)) or 1.0
    scale = usable / s0
    clamped = [max(0.25, float(x) * scale) for x in clamped]

    cues: list[tuple[float, float, str]] = []
    t = max(0.0, float(offset_sec or 0.0))
    for seg, d in zip(segs, clamped):
        st = t
        ed = st + float(d)
        if ed <= st:
            continue
        cues.append((st, ed, seg))
        t = ed + float(gap_sec)
    return cues


def evaluate_subtitle_quality(
    cues: Iterable[tuple[float, float, str]],
    *,
    max_line_soft: int = 22,
    cps_soft: float = 8.0,
) -> dict:
    items = []
    for it in cues or []:
        try:
            s, e, t = it
            st = float(s)
            ed = float(e)
            txt = str(t or "").strip()
            if txt and ed > st:
                items.append((st, ed, txt))
        except Exception:
            continue
    if not items:
        return {
            "cue_count": 0,
            "max_line_len": 0,
            "avg_line_len": 0.0,
            "avg_cps": 0.0,
            "dense_ratio": 0.0,
            "long_line_ratio": 0.0,
            "score": 0,
            "grade": "D",
        }
    lens = []
    cps_vals = []
    dense = 0
    long_line = 0
    for st, ed, txt in items:
        lines = [x.strip() for x in str(txt).split("\n") if x.strip()] or [str(txt)]
        ln = max(len(x) for x in lines)
        lens.append(ln)
        dur = max(0.1, float(ed) - float(st))
        cps = float(len("".join(lines))) / dur
        cps_vals.append(cps)
        if cps > float(cps_soft):
            dense += 1
        if ln > int(max_line_soft):
            long_line += 1
    n = max(1, len(items))
    max_len = max(lens) if lens else 0
    avg_len = float(sum(lens)) / float(max(1, len(lens)))
    avg_cps = float(sum(cps_vals)) / float(max(1, len(cps_vals)))
    dense_ratio = float(dense) / float(n)
    long_ratio = float(long_line) / float(n)
    score = 100.0
    score -= max(0.0, float(max_len - int(max_line_soft)) * 2.2)
    score -= max(0.0, (avg_cps - float(cps_soft)) * 8.0)
    score -= dense_ratio * 25.0
    score -= long_ratio * 35.0
    score_i = int(max(0.0, min(100.0, round(score))))
    grade = "A" if score_i >= 90 else "B" if score_i >= 78 else "C" if score_i >= 62 else "D"
    return {
        "cue_count": int(len(items)),
        "max_line_len": int(max_len),
        "avg_line_len": round(avg_len, 3),
        "avg_cps": round(avg_cps, 3),
        "dense_ratio": round(dense_ratio, 3),
        "long_line_ratio": round(long_ratio, 3),
        "score": int(score_i),
        "grade": grade,
    }
