from __future__ import annotations

from typing import Optional

import requests

from app.core.config import settings
from app.services.placeholder.cache_store import get_json_cache, set_json_cache
from app.services.placeholder.core_types import CandidateClip, SearchPlan
from app.services.placeholder.errors import PlaceholderError
from app.services.placeholder.rate_limit import allow


def _pick_orientation(plan: SearchPlan) -> str:
    o = str(plan.orientation or "portrait").lower().strip()
    if o in {"portrait", "vertical"}:
        return "portrait"
    if o in {"landscape", "horizontal"}:
        return "landscape"
    return "portrait"


def search_pixabay(plan: SearchPlan) -> list[CandidateClip]:
    if not allow("pixabay", 60, 100):
        raise PlaceholderError(code="rate_limited", provider="pixabay", retryable=True, http_status=429, detail="pixabay_window_limit")
    key = str(getattr(settings, "pixabay_api_key", "") or "").strip()
    if not key:
        return []
    q = str(plan.query or "").strip()
    if not q:
        return []
    if len(q) > 100:
        q = q[:100]
    o = _pick_orientation(plan)
    cache_ttl = int(getattr(settings, "placeholder_search_ttl_hours", 24) or 24) * 3600
    cache_key = f"pixabay|{q}|{o}|{int(plan.min_width)}|{int(plan.min_height)}|{int(plan.max_duration)}"
    cached = get_json_cache(cache_key, cache_ttl)
    data = cached
    if data is None:
        url = "https://pixabay.com/api/videos/"
        params = {
            "key": key,
            "q": q,
            "per_page": 20,
            "orientation": "vertical" if o == "portrait" else "horizontal",
        }
        try:
            r = requests.get(url, params=params, timeout=10, headers={"user-agent": "AIseekWorker/1.0"})
            if r.status_code == 429:
                raise PlaceholderError(code="rate_limited", provider="pixabay", retryable=True, http_status=429, detail="pixabay_429")
            if r.status_code != 200:
                raise PlaceholderError(code="http_error", provider="pixabay", retryable=r.status_code >= 500, http_status=r.status_code, detail="pixabay_non_200")
            data = r.json()
            if isinstance(data, dict):
                set_json_cache(cache_key, data)
        except PlaceholderError:
            raise
        except Exception as e:
            raise PlaceholderError(code="network_error", provider="pixabay", retryable=True, detail=str(e))
    hits = data.get("hits") if isinstance(data, dict) else None
    if not isinstance(hits, list):
        return []
    out: list[CandidateClip] = []
    for h in hits:
        if not isinstance(h, dict):
            continue
        vid = str(h.get("id") or "").strip()
        videos = h.get("videos")
        if not vid or not isinstance(videos, dict):
            continue
        dur = int(h.get("duration") or 0)
        if dur and (dur < int(plan.min_duration) or dur > int(plan.max_duration)):
            continue
        tags = tuple([t.strip() for t in str(h.get("tags") or "").split(",") if t.strip()])[:12]
        page_url = str(h.get("pageURL") or "").strip()
        title = page_url[:80]
        author = str(h.get("user") or "").strip()
        cand = []
        for k in ["large", "medium", "small", "tiny"]:
            v = videos.get(k)
            if not isinstance(v, dict):
                continue
            u = str(v.get("url") or "").strip()
            w = int(v.get("width") or 0)
            hh = int(v.get("height") or 0)
            if not u or w <= 0 or hh <= 0:
                continue
            cand.append((w * hh, u, w, hh))
        cand.sort(reverse=True)
        if not cand:
            continue
        _, u, w, hh = cand[0]
        if w < int(plan.min_width) or hh < int(plan.min_height):
            continue
        out.append(
            CandidateClip(
                provider="pixabay",
                clip_id=vid,
                download_url=u,
                width=w,
                height=hh,
                duration=dur,
                title=title,
                tags=tags,
                author=author,
                source_url=page_url,
                license_name="Pixabay Content License",
                license_url="https://pixabay.com/service/terms/",
                attribution_required=False,
                commercial_use=True,
                modifications_allowed=True,
            )
        )
    return out


def search_pexels(plan: SearchPlan) -> list[CandidateClip]:
    if not allow("pexels", 3600, 400):
        raise PlaceholderError(code="rate_limited", provider="pexels", retryable=True, http_status=429, detail="pexels_window_limit")
    key = str(getattr(settings, "pexels_api_key", "") or "").strip()
    if not key:
        return []
    q = str(plan.query or "").strip()
    if not q:
        return []
    o = _pick_orientation(plan)
    cache_ttl = int(getattr(settings, "placeholder_search_ttl_hours", 24) or 24) * 3600
    cache_key = f"pexels|{q}|{o}|{int(plan.min_width)}|{int(plan.min_height)}|{int(plan.max_duration)}"
    cached = get_json_cache(cache_key, cache_ttl)
    data = cached
    if data is None:
        url = "https://api.pexels.com/videos/v1/search"
        params = {"query": q, "per_page": 20, "orientation": "portrait" if o == "portrait" else "landscape"}
        try:
            r = requests.get(url, params=params, headers={"Authorization": key, "user-agent": "AIseekWorker/1.0"}, timeout=10)
            if r.status_code == 429:
                raise PlaceholderError(code="rate_limited", provider="pexels", retryable=True, http_status=429, detail="pexels_429")
            if r.status_code != 200:
                raise PlaceholderError(code="http_error", provider="pexels", retryable=r.status_code >= 500, http_status=r.status_code, detail="pexels_non_200")
            data = r.json()
            if isinstance(data, dict):
                set_json_cache(cache_key, data)
        except PlaceholderError:
            raise
        except Exception as e:
            raise PlaceholderError(code="network_error", provider="pexels", retryable=True, detail=str(e))
    vids = data.get("videos") if isinstance(data, dict) else None
    if not isinstance(vids, list):
        return []
    out: list[CandidateClip] = []
    for v in vids:
        if not isinstance(v, dict):
            continue
        vid = str(v.get("id") or "").strip()
        dur = int(v.get("duration") or 0)
        if not vid:
            continue
        if dur and (dur < int(plan.min_duration) or dur > int(plan.max_duration)):
            continue
        page_url = str(v.get("url") or "").strip()
        title = page_url[:80]
        author = ""
        try:
            uo = v.get("user")
            if isinstance(uo, dict):
                author = str(uo.get("name") or "").strip()
        except Exception:
            author = ""
        vf = v.get("video_files")
        if not isinstance(vf, list):
            continue
        best = None
        for f in vf:
            if not isinstance(f, dict):
                continue
            if str(f.get("file_type") or "").lower() != "video/mp4":
                continue
            w = int(f.get("width") or 0)
            hh = int(f.get("height") or 0)
            link = str(f.get("link") or "").strip()
            if not link or w <= 0 or hh <= 0:
                continue
            if w < int(plan.min_width) or hh < int(plan.min_height):
                continue
            score = w * hh
            ql = str(f.get("quality") or "")
            if ql == "hd":
                score += 10_000
            if best is None or score > best[0]:
                best = (score, link, w, hh)
        if not best:
            continue
        _, link, w, hh = best
        out.append(
            CandidateClip(
                provider="pexels",
                clip_id=vid,
                download_url=link,
                width=w,
                height=hh,
                duration=dur,
                title=title,
                tags=(),
                author=author,
                source_url=page_url,
                license_name="Pexels License",
                license_url="https://www.pexels.com/license/",
                attribution_required=False,
                commercial_use=True,
                modifications_allowed=True,
            )
        )
    return out


def search_provider(name: str, plan: SearchPlan) -> list[CandidateClip]:
    n = str(name or "").strip().lower()
    if n == "pixabay":
        return search_pixabay(plan)
    if n == "pexels":
        return search_pexels(plan)
    raise PlaceholderError(code="unknown_provider", provider=n, retryable=False, detail="unknown_provider")
