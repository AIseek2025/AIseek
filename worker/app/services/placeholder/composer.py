from __future__ import annotations

import os
import random
import subprocess
from pathlib import Path

from app.core.config import OUTPUTS_DIR


def compose_background(job_id: str, clips: list[str], durs: list[int], out_w: int = 1080, out_h: int = 1920) -> str | None:
    if not clips or not durs or len(clips) != len(durs):
        return None
    items = [(str(p), int(d)) for p, d in zip(clips, durs) if str(p).strip() and int(d) > 0 and os.path.exists(str(p))]
    if not items:
        return None
    if len(items) > 12:
        items = items[:12]
    out = OUTPUTS_DIR / f"{job_id}_bg.mp4"
    cmd = ["ffmpeg", "-y"]
    for p, _ in items:
        cmd.extend(["-i", p])
    chains = []
    vouts = []
    for i, (_, d) in enumerate(items):
        start = float(random.random() * 0.5)
        chains.append(
            f"[{i}:v]trim=start={start}:duration={float(d)},setpts=PTS-STARTPTS,scale={out_w}:{out_h}:force_original_aspect_ratio=increase,crop={out_w}:{out_h},fps=30,format=yuv420p[v{i}]"
        )
        vouts.append(f"[v{i}]")
    chains.append("".join(vouts) + f"concat=n={len(vouts)}:v=1:a=0[vout]")
    cmd.extend(["-filter_complex", ";".join(chains)])
    cmd.extend(["-map", "[vout]", "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-movflags", "+faststart", str(out)])
    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
        if out.exists() and out.stat().st_size > 0:
            return str(out)
    except Exception:
        try:
            if out.exists():
                out.unlink()
        except Exception:
            pass
    return None

