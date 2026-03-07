import argparse
import os

from sqlalchemy.orm import joinedload

from app.db.session import SessionLocal
from app.models.all_models import Post
from app.services.queue_service import send_worker_task


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    limit = int(args.limit or 200)
    if limit < 1:
        limit = 1
    if limit > 5000:
        limit = 5000

    db = SessionLocal()
    try:
        q = (
            db.query(Post)
            .options(joinedload(Post.active_media_asset))
            .filter(Post.status == "done")
            .filter(Post.post_type == "video")
            .filter((Post.cover_url == None) | (Post.cover_url == ""))
            .order_by(Post.id.desc())
            .limit(limit)
        )
        items = q.all()
        print(f"found={len(items)}")
        for p in items:
            jid = str(getattr(p, "ai_job_id", "") or "").strip()
            if not jid:
                continue
            mp4_url = None
            hls_url = None
            try:
                a = getattr(p, "active_media_asset", None)
                if a is not None:
                    mp4_url = getattr(a, "mp4_url", None)
                    hls_url = getattr(a, "hls_url", None)
            except Exception:
                pass
            if not mp4_url:
                mp4_url = getattr(p, "processed_url", None)
            if not hls_url:
                u = getattr(p, "video_url", None)
                if isinstance(u, str) and u.lower().endswith(".m3u8"):
                    hls_url = u
            if not mp4_url and not hls_url:
                continue
            payload = {
                "job_id": str(jid),
                "user_id": str(int(getattr(p, "user_id", 0) or 0)),
                "post_id": str(int(getattr(p, "id", 0) or 0)),
                "title": str(getattr(p, "title", None) or ""),
                "summary": str(getattr(p, "summary", None) or ""),
                "mp4_url": str(mp4_url or "") or None,
                "hls_url": str(hls_url or "") or None,
            }
            if args.dry_run:
                print(f"dry_run post_id={p.id} job_id={jid}")
                continue
            tid = send_worker_task("generate_cover_only", kwargs=payload)
            print(f"queued post_id={p.id} job_id={jid} task_id={tid}")
    finally:
        db.close()


if __name__ == "__main__":
    main()

