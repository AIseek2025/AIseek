from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import requests

from app.core.config import DATA_DIR, settings


@dataclass(frozen=True)
class PickResult:
    provider: str
    clip_id: str
    download_url: str
    width: int
    height: int
    duration: int


def _norm_keywords(keywords: list[str]) -> list[str]:
    out: list[str] = []
    for k in keywords or []:
        s = str(k or "").strip()
        if not s:
            continue
        s = re.sub(r"\\s+", " ", s)
        if len(s) > 80:
            s = s[:80]
        out.append(s)
    seen = set()
    dedup = []
    for x in out:
        if x.lower() in seen:
            continue
        seen.add(x.lower())
        dedup.append(x)
    return dedup[:6]


def _cache_root() -> Path:
    d = str(getattr(settings, "placeholder_cache_dir", "") or "").strip()
    if d:
        return Path(d).expanduser()
    return DATA_DIR / "placeholder_cache"


def _ensure_dir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p


def _hash(s: str) -> str:
    return hashlib.sha256(str(s or "").encode("utf-8")).hexdigest()[:24]


def _now() -> int:
    return int(time.time())


def _ttl_ok(path: Path, ttl_sec: int) -> bool:
    try:
        if not path.exists() or not path.is_file() or path.stat().st_size <= 0:
            return False
        age = _now() - int(path.stat().st_mtime)
        return age <= int(ttl_sec)
    except Exception:
        return False


def _evict_cache(max_bytes: int) -> None:
    root = _cache_root() / "videos"
    try:
        if not root.exists():
            return
        files = [p for p in root.rglob("*.mp4") if p.is_file()]
        sizes = []
        total = 0
        for p in files:
            try:
                st = p.stat()
                total += int(st.st_size)
                sizes.append((int(st.st_mtime), int(st.st_size), p))
            except Exception:
                continue
        if total <= max_bytes:
            return
        sizes.sort(key=lambda x: x[0])
        target = int(max_bytes * 0.85)
        for _, sz, p in sizes:
            try:
                p.unlink()
            except Exception:
                pass
            total -= int(sz)
            if total <= target:
                break
    except Exception:
        return


def _download_to_cache(url: str, provider: str, clip_id: str) -> Optional[Path]:
    if not url:
        return None
    root = _cache_root()
    out_dir = _ensure_dir(root / "videos" / provider)
    out = out_dir / f"{clip_id}_{_hash(url)}.mp4"
    ttl = int(getattr(settings, "placeholder_video_ttl_hours", 24) or 24) * 3600
    if _ttl_ok(out, ttl):
        return out
    try:
        with requests.get(url, stream=True, timeout=15) as r:
            if r.status_code != 200:
                return None
            tmp = out.with_suffix(".tmp")
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 256):
                    if not chunk:
                        continue
                    f.write(chunk)
        if tmp.exists() and tmp.stat().st_size > 0:
            tmp.replace(out)
            return out
    except Exception:
        try:
            if out.with_suffix(".tmp").exists():
                out.with_suffix(".tmp").unlink()
        except Exception:
            pass
    return None


def _pixabay_search(query: str, orientation: str, min_w: int, min_h: int) -> list[PickResult]:
    key = str(getattr(settings, "pixabay_api_key", "") or "").strip()
    if not key:
        return []
    root = _cache_root()
    cache_dir = _ensure_dir(root / "search_cache")
    cache_key = _hash(f"pixabay|{query}|{orientation}|{min_w}|{min_h}")
    cache_path = cache_dir / f"{cache_key}.json"
    ttl = int(getattr(settings, "placeholder_search_ttl_hours", 24) or 24) * 3600
    data = None
    if _ttl_ok(cache_path, ttl):
        try:
            data = json.loads(cache_path.read_text("utf-8"))
        except Exception:
            data = None
    if data is None:
        url = "https://pixabay.com/api/videos/"
        params = {
            "key": key,
            "q": query,
            "per_page": 20,
            "orientation": "vertical" if orientation == "portrait" else "horizontal" if orientation == "landscape" else "all",
        }
        try:
            r = requests.get(url, params=params, timeout=10)
            if r.status_code != 200:
                return []
            data = r.json()
            cache_path.write_text(json.dumps(data, ensure_ascii=False), "utf-8")
        except Exception:
            return []
    hits = data.get("hits") if isinstance(data, dict) else None
    if not isinstance(hits, list):
        return []
    out: list[PickResult] = []
    for h in hits:
        if not isinstance(h, dict):
            continue
        vid = str(h.get("id") or "").strip()
        videos = h.get("videos")
        if not vid or not isinstance(videos, dict):
            continue
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
        if w < min_w or hh < min_h:
            continue
        dur = int(h.get("duration") or 0)
        out.append(PickResult(provider="pixabay", clip_id=vid, download_url=u, width=w, height=hh, duration=dur))
    return out


def _pexels_search(query: str, orientation: str, min_w: int, min_h: int) -> list[PickResult]:
    key = str(getattr(settings, "pexels_api_key", "") or "").strip()
    if not key:
        return []
    root = _cache_root()
    cache_dir = _ensure_dir(root / "search_cache")
    cache_key = _hash(f"pexels|{query}|{orientation}|{min_w}|{min_h}")
    cache_path = cache_dir / f"{cache_key}.json"
    ttl = int(getattr(settings, "placeholder_search_ttl_hours", 24) or 24) * 3600
    data = None
    if _ttl_ok(cache_path, ttl):
        try:
            data = json.loads(cache_path.read_text("utf-8"))
        except Exception:
            data = None
    if data is None:
        url = "https://api.pexels.com/videos/v1/search"
        params = {"query": query, "per_page": 20, "orientation": "portrait" if orientation == "portrait" else "landscape"}
        try:
            r = requests.get(url, params=params, headers={"Authorization": key}, timeout=10)
            if r.status_code != 200:
                return []
            data = r.json()
            cache_path.write_text(json.dumps(data, ensure_ascii=False), "utf-8")
        except Exception:
            return []
    vids = data.get("videos") if isinstance(data, dict) else None
    if not isinstance(vids, list):
        return []
    out: list[PickResult] = []
    for v in vids:
        if not isinstance(v, dict):
            continue
        vid = str(v.get("id") or "").strip()
        dur = int(v.get("duration") or 0)
        vf = v.get("video_files")
        if not vid or not isinstance(vf, list):
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
            if w < min_w or hh < min_h:
                continue
            score = w * hh
            q = str(f.get("quality") or "")
            if q == "hd":
                score += 10_000
            if best is None or score > best[0]:
                best = (score, link, w, hh)
        if not best:
            continue
        _, link, w, hh = best
        out.append(PickResult(provider="pexels", clip_id=vid, download_url=link, width=w, height=hh, duration=dur))
    return out


def pick_and_cache_background(keywords: list[str], orientation: str = "portrait", min_w: int = 1080, min_h: int = 1920) -> Optional[Path]:
    kws = _norm_keywords(keywords)
    if not kws:
        return None
    q = " ".join(kws[:3])
    provider = str(getattr(settings, "placeholder_provider", "pixabay") or "pixabay").strip().lower()
    results: list[PickResult] = []
    if provider in {"pixabay", "auto"}:
        results.extend(_pixabay_search(q, orientation, min_w, min_h))
    if provider in {"pexels", "auto"}:
        results.extend(_pexels_search(q, orientation, min_w, min_h))
    if not results:
        return None

    results.sort(key=lambda x: (x.width * x.height, x.duration), reverse=True)
    pick = results[0]
    out = _download_to_cache(pick.download_url, pick.provider, pick.clip_id)
    max_mb = int(getattr(settings, "placeholder_cache_max_mb", 1024) or 1024)
    _evict_cache(max_mb * 1024 * 1024)
    return out

