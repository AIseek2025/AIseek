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
    # STYLE block removed to improve compatibility with some players
    # lines.append("STYLE")
    # lines.append("::cue {")
    # lines.append("  color: #fff;")
    # lines.append("  background: rgba(0,0,0,0.55);")
    # lines.append("  text-shadow: 0 2px 8px rgba(0,0,0,0.65);")
    # lines.append("  font-weight: 700;")
    # lines.append("}")
    # lines.append("")

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
    # STYLE block removed to improve compatibility
    # lines.append("STYLE")
    # lines.append("::cue {")
    # lines.append("  color: #fff;")
    # lines.append("  background: rgba(0,0,0,0.55);")
    # lines.append("  text-shadow: 0 2px 8px rgba(0,0,0,0.65);")
    # lines.append("  font-weight: 700;")
    # lines.append("}")
    # lines.append("")

    for i, (start, end, seg) in enumerate(items, start=1):
        txt = _wrap_two_lines(seg, max_chars=max_chars_per_line)
        if not txt:
            continue
        lines.append(str(i))
        lines.append(f"{_fmt_ts(start)} --> {_fmt_ts(end)} line:{position_line} align:{align} position:50%")
        lines.append(txt)
        lines.append("")

    return "\n".join(lines).strip() + "\n"
