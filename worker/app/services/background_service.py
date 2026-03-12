import random
from pathlib import Path
from typing import List, Optional, Tuple

from app.core.config import PLACEHOLDER_VIDEO, settings
from app.services.placeholder.composer import compose_background
from app.services.placeholder.orchestrator import pick_background_video

from app.services.placeholder.orchestrator import pick_background_video

import asyncio
import logging

logger = logging.getLogger(__name__)


def _collect_dir_videos(d: Path) -> List[Path]:
    out: List[Path] = []
    try:
        if not d.exists() or not d.is_dir():
            logger.warning(f"Background dir {d} does not exist or is not a directory")
            return []
        for p in sorted(d.glob("*.mp4")):
            try:
                if p.is_file() and p.stat().st_size > 0:
                    out.append(p)
            except Exception:
                continue
    except Exception as e:
        logger.error(f"Error collecting videos from {d}: {e}")
        return []
    logger.info(f"Collected {len(out)} background videos from {d}")
    return out


def select_background_video(job_id: str, keywords: Optional[List[str]] = None) -> Optional[Path]:
    mode = str(getattr(settings, "video_bg_mode", "placeholder") or "placeholder").lower()
    logger.info(f"Selecting background video for job {job_id}, mode={mode}")
    
    # Try API first if configured
    if mode == "api" or (keywords and len(keywords) > 0):
         try:
             # Run async function in sync context
             loop = asyncio.new_event_loop()
             asyncio.set_event_loop(loop)
             
             async def _run():
                 return await pick_background_video(
                     user_id=0,
                     title=" ".join(keywords or []),
                     content="",
                     visual_prompts_en=keywords or [],
                     orientation="portrait",
                     min_w=1080,
                     min_h=1920,
                     target_sec=30
                 )
             
             res = loop.run_until_complete(_run())
             # loop.close() # Avoid closing loop if it causes issues, or handle gracefully
             
             if res.picked and res.picked.path:
                 p = Path(res.picked.path)
                 if p.exists():
                     logger.info(f"API selected background video: {p}")
                     return p
         except Exception as e:
             logger.error(f"API background selection failed: {e}")

    # Check for placeholder directory configuration
    d = getattr(settings, "video_bg_dir", None)
    if isinstance(d, str) and d.strip():
        dir_path = Path(d.strip())
        logger.info(f"Checking configured video_bg_dir: {dir_path}")
        items = _collect_dir_videos(dir_path)
        if items:
            # Use job_id + current time to ensure randomness even for same job retry
            import time
            seed_val = str(job_id or "") + str(time.time())
            r = random.Random(seed_val)
            selected = items[int(r.random() * len(items))]
            logger.info(f"Selected random background video: {selected}")
            return selected
        else:
            logger.warning(f"No valid videos found in {dir_path}")

    # Fallback to single placeholder file if configured
    p = getattr(settings, "video_bg_path", None)
    if isinstance(p, str) and p.strip():
        pp = Path(p.strip())
        try:
            if pp.exists() and pp.is_file() and pp.stat().st_size > 0:
                return pp
        except Exception:
            pass

    try:
        if PLACEHOLDER_VIDEO.exists() and PLACEHOLDER_VIDEO.is_file() and PLACEHOLDER_VIDEO.stat().st_size > 0:
            return PLACEHOLDER_VIDEO
    except Exception:
        pass
    return None


def ffmpeg_background_input_args(job_id: str, keywords: Optional[List[str]] = None) -> Tuple[List[str], int]:
    bg = select_background_video(job_id, keywords=keywords)
    if bg is not None:
        return ["-stream_loop", "-1", "-i", str(bg)], 0
    return ["-f", "lavfi", "-i", "testsrc2=size=1080x1920:rate=30"], 0


async def build_background_for_job(
    *,
    job_id: str,
    user_id: int,
    title: str,
    content: str,
    visual_prompts_en: list[str],
    scene_durations: list[int],
    target_sec: int,
) -> tuple[Optional[str], list[str], list[dict], Optional[dict]]:
    mode = str(getattr(settings, "video_bg_mode", "placeholder") or "placeholder").lower()
    if mode != "api":
        return None, [], [{"t": "mode", "value": mode}], None

    orientation = str(getattr(settings, "placeholder_orientation", "portrait") or "portrait")
    min_w = int(getattr(settings, "placeholder_min_width", 1080) or 1080)
    min_h = int(getattr(settings, "placeholder_min_height", 1920) or 1920)

    trace_all: list[dict] = []
    picks: list[str] = []
    picked_meta: list[dict] = []
    audit_segments: list[dict] = []

    durs = [int(d or 0) for d in (scene_durations or []) if int(d or 0) > 0]
    if len(durs) >= 3:
        for i, dur in enumerate(durs[:6], start=1):
            vp = []
            try:
                if i - 1 < len(visual_prompts_en):
                    s = str(visual_prompts_en[i - 1] or "").strip()
                    if s:
                        vp = [s]
            except Exception:
                vp = []
            res = await pick_background_video(
                user_id=int(user_id or 0),
                title=str(title or ""),
                content=str(content or ""),
                visual_prompts_en=vp or (visual_prompts_en or []),
                orientation=orientation,
                min_w=min_w,
                min_h=min_h,
                target_sec=int(max(15, min(120, dur))),
            )
            trace_all.append({"t": "pick_part", "i": i, "ok": bool(res.picked), "trace": res.trace[-6:]})
            if res.picked:
                picks.append(res.picked.path)
                picked_meta.append({"provider": res.picked.provider, "clip_id": res.picked.clip_id, "q": res.picked.query})
                try:
                    audit_segments.append(dict(res.picked.audit) if isinstance(res.picked.audit, dict) else {})
                except Exception:
                    audit_segments.append({})
        if len(picks) >= 3:
            out = compose_background(job_id, picks, durs[: len(picks)], out_w=min_w, out_h=min_h)
            if out:
                trace_all.append({"t": "compose_ok", "segments": len(picks), "meta": picked_meta[:4]})
                audit = {"type": "composed", "segments": audit_segments[: len(picks)], "orientation": orientation, "min_width": min_w, "min_height": min_h}
                return out, [out], trace_all, audit
            trace_all.append({"t": "compose_fail", "segments": len(picks)})

    res = await pick_background_video(
        user_id=int(user_id or 0),
        title=str(title or ""),
        content=str(content or ""),
        visual_prompts_en=visual_prompts_en or [],
        orientation=orientation,
        min_w=min_w,
        min_h=min_h,
        target_sec=int(target_sec or 0),
    )
    trace_all.append({"t": "pick_single", "ok": bool(res.picked), "trace": res.trace[-8:]})
    if res.picked:
        audit = dict(res.picked.audit) if isinstance(res.picked.audit, dict) else {}
        return res.picked.path, [], trace_all, audit
    return None, [], trace_all, None


def ffmpeg_background_filter(orientation: Optional[str] = None) -> str:
    o = str(orientation or "portrait").strip().lower()
    if o == "landscape":
        return "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,format=yuv420p,setsar=1"
    return "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,format=yuv420p,setsar=1"
