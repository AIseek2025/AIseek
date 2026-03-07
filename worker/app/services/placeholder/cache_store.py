from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Optional

import requests

from app.core.config import DATA_DIR, settings


def _root() -> Path:
    d = str(getattr(settings, "placeholder_cache_dir", "") or "").strip()
    if d:
        return Path(d).expanduser()
    return DATA_DIR / "placeholder_cache"


def _ensure(p: Path) -> Path:
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


def get_json_cache(key: str, ttl_sec: int) -> Optional[dict]:
    p = _ensure(_root() / "search_cache") / f"{_hash(key)}.json"
    if _ttl_ok(p, ttl_sec):
        try:
            return json.loads(p.read_text("utf-8"))
        except Exception:
            return None
    return None


def set_json_cache(key: str, payload: dict) -> None:
    p = _ensure(_root() / "search_cache") / f"{_hash(key)}.json"
    try:
        p.write_text(json.dumps(payload, ensure_ascii=False), "utf-8")
    except Exception:
        return


def evict_videos(max_bytes: int) -> None:
    root = _root() / "videos"
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


def download_video(url: str, provider: str, clip_id: str, *, ttl_sec: int, max_bytes: int) -> Optional[Path]:
    u = str(url or "").strip()
    if not u:
        return None
    pr = str(provider or "x").strip().lower() or "x"
    cid = str(clip_id or "").strip() or _hash(u)
    out_dir = _ensure(_root() / "videos" / pr)
    out = out_dir / f"{cid}_{_hash(u)}.mp4"
    if _ttl_ok(out, ttl_sec):
        return out
    tmp = out.with_suffix(".tmp")
    try:
        with requests.get(u, stream=True, timeout=15, headers={"user-agent": "AIseekWorker/1.0"}) as r:
            if r.status_code != 200:
                return None
            ct = str(r.headers.get("content-type") or "")
            if ct and "video" not in ct and "octet-stream" not in ct:
                return None
            clen = r.headers.get("content-length")
            try:
                if clen is not None and int(clen) > int(max_bytes):
                    return None
            except Exception:
                pass
            got = 0
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 256):
                    if not chunk:
                        continue
                    got += len(chunk)
                    if got > int(max_bytes):
                        return None
                    f.write(chunk)
        if tmp.exists() and tmp.stat().st_size > 0:
            tmp.replace(out)
            return out
    except Exception:
        return None
    finally:
        try:
            if tmp.exists():
                tmp.unlink()
        except Exception:
            pass
    return None

