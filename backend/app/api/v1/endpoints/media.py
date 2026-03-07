from __future__ import annotations

import os
import shutil
import subprocess
import threading
from pathlib import Path
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, Response
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.cache import cache
from app.models.all_models import Post

router = APIRouter()
_THUMB_BUILD_MAX_CONCURRENCY = max(1, min(16, int(str(os.getenv("THUMB_BUILD_MAX_CONCURRENCY", "3")).strip() or "3")))
_THUMB_BUILD_SEM = threading.BoundedSemaphore(_THUMB_BUILD_MAX_CONCURRENCY)


def _root_dir() -> Path:
    return Path(__file__).resolve().parents[4]

def _repo_root() -> Path:
    return Path(__file__).resolve().parents[5]


def _static_dir() -> Path:
    return _root_dir() / "static"


def _resolve_local_static_path(url: str) -> Path | None:
    if not url:
        return None
    u = str(url)
    if u.startswith("/static/"):
        return _static_dir() / u[len("/static/") :]
    if u.startswith("https://cdn.aiseek.com/") or u.startswith("http://cdn.aiseek.com/"):
        try:
            path = u.split("cdn.aiseek.com", 1)[1]
            if path.startswith("/uploads/"):
                return _static_dir() / path.lstrip("/")
        except Exception:
            return None
    if u.startswith("http://") or u.startswith("https://"):
        try:
            p = urlparse(u)
            if p.path and p.path.startswith("/static/"):
                return _static_dir() / p.path[len("/static/") :]
        except Exception:
            return None
    return None


def _thumb_path(post_id: int, v: int) -> Path:
    out_dir = _static_dir() / "uploads" / "thumbs"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / f"post_{int(post_id)}_v{int(v)}.jpg"


def _thumb_fallback_path() -> Path:
    return _static_dir() / "img" / "default_bg.svg"


def _pick_video_url(post: Post) -> str:
    if not post:
        return ""
    try:
        active = getattr(post, "active_media_asset", None)
        if active is not None:
            u2 = getattr(active, "mp4_url", None) or getattr(active, "hls_url", None)
            if u2:
                return str(u2)
    except Exception:
        pass
    u = getattr(post, "processed_url", None) or getattr(post, "video_url", None) or ""
    return str(u) if u else ""


def _ffmpeg_snapshot(inp: str, out_jpg: Path) -> bool:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return False
    out_jpg.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg,
        "-y",
        "-ss",
        "1.0",
        "-i",
        str(inp),
        "-frames:v",
        "1",
        "-vf",
        "scale=200:200:force_original_aspect_ratio=increase,crop=200:200",
        "-q:v",
        "4",
        str(out_jpg),
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return out_jpg.exists() and out_jpg.stat().st_size > 0
    except Exception:
        try:
            if out_jpg.exists():
                out_jpg.unlink()
        except Exception:
            pass
        return False


def _ffmpeg_thumb_from_image(inp: str, out_jpg: Path) -> bool:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return False
    out_jpg.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(inp),
        "-frames:v",
        "1",
        "-vf",
        "scale=200:200:force_original_aspect_ratio=increase,crop=200:200",
        "-q:v",
        "4",
        str(out_jpg),
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return out_jpg.exists() and out_jpg.stat().st_size > 0
    except Exception:
        try:
            if out_jpg.exists():
                out_jpg.unlink()
        except Exception:
            pass
        return False


def _try_generate_thumb(cover_url: str, video_url: str, out: Path) -> bool:
    try:
        if cover_url:
            local_cov = _resolve_local_static_path(cover_url)
            if local_cov and local_cov.exists():
                if _ffmpeg_thumb_from_image(str(local_cov), out):
                    return True
    except Exception:
        pass
    try:
        if video_url:
            local = _resolve_local_static_path(video_url)
            inp = str(local) if (local and local.exists()) else str(video_url)
            if _ffmpeg_snapshot(inp, out):
                return True
    except Exception:
        pass
    return False


def _schedule_thumb_build(post_id: int, v: int, cover_url: str, video_url: str) -> None:
    lock_key = f"lock:post_thumb:{int(post_id)}:{int(v)}"
    try:
        if not cache.set_nx(lock_key, "1", ttl=90):
            return
    except Exception:
        return
    out = _thumb_path(int(post_id), int(v))
    got_slot = False
    try:
        got_slot = bool(_THUMB_BUILD_SEM.acquire(blocking=False))
    except Exception:
        got_slot = False
    if not got_slot:
        return

    def _runner():
        try:
            _try_generate_thumb(str(cover_url or ""), str(video_url or ""), out)
        except Exception:
            pass
        finally:
            try:
                _THUMB_BUILD_SEM.release()
            except Exception:
                pass

    try:
        t = threading.Thread(target=_runner, daemon=True)
        t.start()
    except Exception:
        try:
            _THUMB_BUILD_SEM.release()
        except Exception:
            pass


@router.get("/post-thumb/{post_id}")
def post_thumb(post_id: int, response: Response, v: int = 2, db: Session = Depends(get_db)):
    post = db.query(Post).filter(Post.id == int(post_id)).first()
    if not post:
        return Response(status_code=404)

    out = _thumb_path(int(post_id), int(v))
    try:
        if out.exists() and out.stat().st_size > 0:
            response.headers["cache-control"] = "public, max-age=300"
            return FileResponse(str(out), media_type="image/jpeg")
    except Exception:
        pass

    cover_url = str(getattr(post, "cover_url", "") or "")
    video_url = _pick_video_url(post)
    _schedule_thumb_build(int(post_id), int(v), cover_url, video_url)
    fb = _thumb_fallback_path()
    if fb.exists():
        response.headers["cache-control"] = "public, max-age=30"
        return FileResponse(str(fb))
    return Response(status_code=404)


@router.get("/options")
def media_options():
    repo = _repo_root()
    bgm_dir = repo / "worker" / "assets" / "bgm"
    tracks = []
    try:
        items = sorted([p.name for p in bgm_dir.glob("*.mp3") if p.is_file() and p.stat().st_size > 0])
    except Exception:
        items = []
    if not items:
        items = [
            "tech_1.mp3",
            "cheerful_1.mp3",
            "serious_1.mp3",
            "relaxing_1.mp3",
            "warm_1.mp3",
            "cinematic_1.mp3",
            "lofi_1.mp3",
            "ambient_1.mp3",
            "piano_1.mp3",
            "acoustic_1.mp3",
            "hiphop_1.mp3",
            "edm_1.mp3",
            "synthwave_1.mp3",
            "orchestral_1.mp3",
            "corporate_1.mp3",
            "jazz_1.mp3",
            "rock_1.mp3",
        ]
    for it in items:
        try:
            base = it.rsplit(".", 1)[0].replace("_", " ").strip()
            base = " ".join([x for x in base.split(" ") if x])
            lab = base.title() if base else it
        except Exception:
            lab = it
        tracks.append({"id": it, "label": lab})

    voices = [
        {"id": "premium_female", "label": "高拟真女声（中文）"},
        {"id": "premium_male", "label": "高拟真男声（中文）"},
        {"id": "premium_news", "label": "专业播报（中文）"},
        {"id": "premium_en", "label": "高拟真女声（EN）"},
    ]

    moods = [
        {"id": "", "label": "默认"},
        {"id": "none", "label": "无BGM"},
        {"id": "hot", "label": "热门"},
        {"id": "tech", "label": "科技感"},
        {"id": "cheerful", "label": "轻快"},
        {"id": "upbeat", "label": "欢快"},
        {"id": "serious", "label": "严肃"},
        {"id": "relaxing", "label": "舒缓"},
        {"id": "chill", "label": "舒缓（Chill）"},
        {"id": "warm", "label": "温暖"},
        {"id": "cinematic", "label": "电影感"},
        {"id": "lofi", "label": "LoFi"},
        {"id": "ambient", "label": "氛围"},
        {"id": "piano", "label": "钢琴"},
        {"id": "acoustic", "label": "原声吉他"},
        {"id": "hiphop", "label": "嘻哈节奏"},
        {"id": "edm", "label": "电子/EDM"},
        {"id": "synthwave", "label": "合成波"},
        {"id": "orchestral", "label": "史诗管弦"},
        {"id": "corporate", "label": "商务轻快"},
        {"id": "jazz", "label": "爵士"},
        {"id": "rock", "label": "摇滚"},
    ]

    return {"bgm": {"moods": moods, "tracks": tracks}, "voice": {"profiles": voices}}
