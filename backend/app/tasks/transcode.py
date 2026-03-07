import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

from app.core.celery_app import celery_app
from app.db.session import SessionLocal
from app.models.all_models import Post
from app.services.storage import storage_service


@celery_app.task(bind=True)
def transcode_to_hls(self, post_id: int, input_key: str) -> dict:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return {"ok": False, "error": "ffmpeg_not_found"}

    key = str(input_key or "").strip().lstrip("/")
    if not key:
        return {"ok": False, "error": "invalid_key"}

    base_dir = Path(__file__).resolve().parents[3]
    static_dir = base_dir / "static"
    use_s3 = bool(getattr(storage_service, "s3_client", None))
    inp = static_dir / key
    tmp_in = None
    if key.startswith("uploads/") and inp.exists():
        pass
    else:
        if not use_s3:
            return {"ok": False, "error": "input_missing"}
        tmp_in = tempfile.TemporaryDirectory(prefix="aiseek_in_")
        ext = Path(key).suffix or ".mp4"
        inp = Path(tmp_in.name) / f"input{ext}"
        ok = storage_service.download_file(key, str(inp))
        if not ok or not inp.exists():
            try:
                tmp_in.cleanup()
            except Exception:
                pass
            return {"ok": False, "error": "input_missing"}

    out_uuid = str(uuid.uuid4())
    tmp_out = None
    if use_s3:
        tmp_out = tempfile.TemporaryDirectory(prefix="aiseek_out_")
        out_dir = Path(tmp_out.name) / out_uuid
        out_dir.mkdir(parents=True, exist_ok=True)
        playlist = out_dir / "index.m3u8"
    else:
        out_dir = static_dir / "uploads" / "hls" / out_uuid
        out_dir.mkdir(parents=True, exist_ok=True)
        playlist = out_dir / "index.m3u8"

    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(inp),
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        "-f",
        "hls",
        "-hls_time",
        "4",
        "-hls_playlist_type",
        "vod",
        str(playlist),
    ]

    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        try:
            if tmp_out:
                tmp_out.cleanup()
        except Exception:
            pass
        try:
            if tmp_in:
                tmp_in.cleanup()
        except Exception:
            pass
        return {"ok": False, "error": "ffmpeg_failed"}

    if use_s3:
        prefix = f"uploads/hls/{out_uuid}"
        ok_all = True
        for p in out_dir.iterdir():
            if not p.is_file():
                continue
            name = p.name.lower()
            if name.endswith(".m3u8"):
                ct = "application/vnd.apple.mpegurl"
                cc = "public, max-age=60"
            elif name.endswith(".ts"):
                ct = "video/MP2T"
                cc = "public, max-age=31536000, immutable"
            else:
                ct = "application/octet-stream"
                cc = "public, max-age=31536000, immutable"
            ok = storage_service.upload_file(str(p), f"{prefix}/{p.name}", content_type=ct, cache_control=cc)
            if not ok:
                ok_all = False
                break
        if not ok_all:
            try:
                tmp_out.cleanup()
            except Exception:
                pass
            try:
                if tmp_in:
                    tmp_in.cleanup()
            except Exception:
                pass
            return {"ok": False, "error": "upload_failed"}
        rel = f"{str(getattr(storage_service, 'public_url', '') or '').rstrip('/')}/{prefix}/index.m3u8"
    else:
        rel = "/static/" + str(playlist.relative_to(static_dir)).replace("\\", "/")

    db = SessionLocal()
    try:
        post = db.query(Post).filter(Post.id == int(post_id)).first()
        if post:
            post.video_url = rel
            post.status = "done"
            db.commit()
    finally:
        try:
            db.close()
        except Exception:
            pass
        try:
            if tmp_out:
                tmp_out.cleanup()
        except Exception:
            pass
        try:
            if tmp_in:
                tmp_in.cleanup()
        except Exception:
            pass

    return {"ok": True, "video_url": rel}
