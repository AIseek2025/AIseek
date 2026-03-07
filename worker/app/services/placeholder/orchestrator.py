from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

import asyncio

from app.core.config import settings
from app.services.placeholder.cache_store import download_video, evict_videos
from app.services.placeholder.circuit_breaker import is_open, mark_failure, mark_success
from app.services.placeholder.core_types import CandidateClip, PickedBackground, SearchPlan
from app.services.placeholder.errors import PlaceholderError
from app.services.placeholder.persona_client import fetch_persona_tags
from app.services.placeholder.prompt_service import build_search_plans
from app.services.placeholder.providers import search_provider
from app.services.placeholder.scoring import score_clip


@dataclass(frozen=True)
class OrchestratorResult:
    picked: Optional[PickedBackground]
    trace: list[dict]


def _providers_from_plan(plan: SearchPlan) -> list[str]:
    pref = [str(x).strip().lower() for x in (plan.provider_preference or ("auto",)) if str(x).strip()]
    if not pref:
        pref = ["auto"]
    out = []
    for p in pref:
        if p == "auto":
            out.extend(["pixabay", "pexels"])
        elif p in {"pixabay", "pexels"}:
            out.append(p)
    seen = set()
    uniq = []
    for x in out:
        if x in seen:
            continue
        seen.add(x)
        uniq.append(x)
    return uniq[:3]


def _max_download_bytes() -> int:
    mb = int(getattr(settings, "placeholder_max_video_mb", 80) or 80)
    if mb < 10:
        mb = 10
    if mb > 300:
        mb = 300
    return int(mb) * 1024 * 1024


async def pick_background_video(
    *,
    user_id: int,
    title: str,
    content: str,
    visual_prompts_en: list[str],
    orientation: str,
    min_w: int,
    min_h: int,
    target_sec: int,
) -> OrchestratorResult:
    trace: list[dict] = []
    uid = int(user_id or 0)
    tags = fetch_persona_tags(uid) if uid > 0 else []
    trace.append({"t": "persona", "tags": tags[:10]})

    plans = await build_search_plans(
        user_id=uid,
        title=title,
        content=content,
        visual_prompts_en=visual_prompts_en,
        persona_tags=tags,
        orientation=orientation,
        min_w=min_w,
        min_h=min_h,
        target_sec=target_sec,
    )
    trace.append({"t": "plans", "n": len(plans), "queries": [p.query for p in plans[:3]]})

    ttl_v = int(getattr(settings, "placeholder_video_ttl_hours", 24) or 24) * 3600
    max_bytes = _max_download_bytes()
    cache_max_mb = int(getattr(settings, "placeholder_cache_max_mb", 1024) or 1024)
    evict_videos(int(cache_max_mb) * 1024 * 1024)

    best: Optional[tuple[float, CandidateClip, SearchPlan]] = None
    last_err = None

    for plan in plans[:4]:
        provs = _providers_from_plan(plan)
        provs = [p for p in provs if not is_open(p)]
        for prov in [p for p in _providers_from_plan(plan) if is_open(p)]:
            trace.append({"t": "skip_open", "provider": prov})

        async def _search_one(pname: str) -> tuple[str, list[CandidateClip], Optional[Exception], int]:
            started = time.time()
            try:
                clips = await asyncio.get_running_loop().run_in_executor(None, lambda: search_provider(pname, plan))
                return pname, clips, None, int((time.time() - started) * 1000)
            except Exception as e:
                return pname, [], e, int((time.time() - started) * 1000)

        tasks = [_search_one(p) for p in provs[:2]]
        results = []
        if tasks:
            results = await asyncio.gather(*tasks)

        for prov, clips, err, ms in results:
            if err is None:
                trace.append({"t": "search_ok", "provider": prov, "ms": ms, "hits": len(clips), "q": plan.query})
                if not clips:
                    mark_failure(prov, hard=False)
                    continue
                mark_success(prov)
                for c in clips[:20]:
                    s = score_clip(c, plan)
                    if best is None or float(s) > float(best[0]):
                        best = (float(s), c, plan)
                continue
            if isinstance(err, PlaceholderError):
                last_err = err
                trace.append({"t": "search_err", "provider": prov, "ms": ms, "e": err.as_dict(), "q": plan.query})
                mark_failure(prov, hard=(err.http_status == 401))
                continue
            last_err = err
            trace.append({"t": "search_err", "provider": prov, "ms": ms, "e": {"code": "unknown", "detail": str(err)[:200]}, "q": plan.query})
            mark_failure(prov, hard=False)

        if best is not None and float(best[0]) >= 0.8:
            break

    if best is None:
        if isinstance(last_err, PlaceholderError):
            trace.append({"t": "final", "ok": False, "reason": last_err.as_dict()})
        else:
            trace.append({"t": "final", "ok": False, "reason": str(last_err)[:120] if last_err else "no_hits"})
        return OrchestratorResult(picked=None, trace=trace)

    _, clip, plan = best
    started = time.time()
    path = download_video(clip.download_url, clip.provider, clip.clip_id, ttl_sec=ttl_v, max_bytes=max_bytes)
    trace.append({"t": "download", "provider": clip.provider, "clip_id": clip.clip_id, "ok": bool(path), "ms": int((time.time() - started) * 1000)})
    if not path:
        mark_failure(clip.provider, hard=False)
        return OrchestratorResult(picked=None, trace=trace)
    mark_success(clip.provider)
    audit = {
        "provider": str(clip.provider),
        "clip_id": str(clip.clip_id),
        "source_url": str(getattr(clip, "source_url", "") or ""),
        "author": str(getattr(clip, "author", "") or ""),
        "license_name": str(getattr(clip, "license_name", "") or ""),
        "license_url": str(getattr(clip, "license_url", "") or ""),
        "attribution_required": bool(getattr(clip, "attribution_required", False)),
        "commercial_use": bool(getattr(clip, "commercial_use", True)),
        "modifications_allowed": bool(getattr(clip, "modifications_allowed", True)),
        "query": str(plan.query),
        "picked_reason": "score_best",
        "downloaded": True,
    }
    picked = PickedBackground(
        path=str(path),
        provider=str(clip.provider),
        clip_id=str(clip.clip_id),
        reason="score_best",
        query=str(plan.query),
        width=int(clip.width),
        height=int(clip.height),
        duration=int(clip.duration),
        audit=audit,
    )
    trace.append({"t": "final", "ok": True, "picked": {"provider": picked.provider, "clip_id": picked.clip_id, "path": picked.path}})
    return OrchestratorResult(picked=picked, trace=trace)
