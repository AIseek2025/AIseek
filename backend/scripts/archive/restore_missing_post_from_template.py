import argparse
import json
import uuid

from sqlalchemy import desc

from app.db.session import SessionLocal
from app.models.all_models import Post, MediaAsset, AIJob


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--post-id", type=int, required=True)
    ap.add_argument("--source-post-id", type=int, required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    target_id = int(args.post_id or 0)
    source_id = int(args.source_post_id or 0)
    if target_id <= 0 or source_id <= 0:
        print("RESTORE_MISSING_POST_FAIL")
        print("invalid_post_id")
        return 1

    db = SessionLocal()
    try:
        exists = db.query(Post).filter(Post.id == target_id).first()
        if exists:
            print(json.dumps({"ok": False, "reason": "target_exists", "post_id": target_id}, ensure_ascii=False))
            print("RESTORE_MISSING_POST_OK")
            if args.dry_run:
                db.rollback()
            return 0

        src = db.query(Post).filter(Post.id == source_id).first()
        if not src:
            print("RESTORE_MISSING_POST_FAIL")
            print("source_post_not_found")
            return 1
        src_ma = db.query(MediaAsset).filter(MediaAsset.post_id == source_id).order_by(desc(MediaAsset.created_at)).first()
        src_job = None
        sjid = str(getattr(src, "ai_job_id", "") or "")
        if sjid:
            src_job = db.query(AIJob).filter(AIJob.id == sjid).first()
        if not src_job:
            src_job = db.query(AIJob).filter(AIJob.post_id == source_id).order_by(desc(AIJob.created_at)).first()
        if not src_ma or not src_job:
            print("RESTORE_MISSING_POST_FAIL")
            print("source_incomplete")
            return 1

        new_job_id = f"recovered-post-{target_id}-{uuid.uuid4().hex[:8]}"
        new_version = str(uuid.uuid4())
        p = Post(
            id=target_id,
            title=str(getattr(src, "title", "") or "AI Generated Video"),
            summary=getattr(src, "summary", None),
            category=getattr(src, "category", None),
            post_type=str(getattr(src, "post_type", "") or "video"),
            video_url=getattr(src, "video_url", None),
            images=getattr(src, "images", None),
            cover_url=getattr(src, "cover_url", None),
            source_key=getattr(src, "source_key", None),
            source_url=getattr(src, "source_url", None),
            processed_url=getattr(src, "processed_url", None),
            error_message=None,
            video_width=getattr(src, "video_width", None),
            video_height=getattr(src, "video_height", None),
            ai_job_id=new_job_id,
            custom_instructions=getattr(src, "custom_instructions", None),
            duration=getattr(src, "duration", None),
            content_text=getattr(src, "content_text", None),
            status="done",
            views_count=0,
            likes_count=0,
            comments_count=0,
            favorites_count=0,
            shares_count=0,
            downloads_count=0,
            download_enabled=bool(getattr(src, "download_enabled", True)),
            user_id=int(getattr(src, "user_id", 0) or 0),
        )
        db.add(p)
        db.flush()

        ma = MediaAsset(
            post_id=target_id,
            version=new_version,
            hls_url=getattr(src_ma, "hls_url", None),
            mp4_url=getattr(src_ma, "mp4_url", None),
            cover_url=getattr(src_ma, "cover_url", None),
            subtitle_tracks=getattr(src_ma, "subtitle_tracks", None),
            background_audit=getattr(src_ma, "background_audit", None),
            duration=getattr(src_ma, "duration", None),
            video_width=getattr(src_ma, "video_width", None),
            video_height=getattr(src_ma, "video_height", None),
        )
        db.add(ma)
        db.flush()
        p.active_media_asset_id = int(getattr(ma, "id", 0) or 0)

        j = AIJob(
            id=new_job_id,
            user_id=int(getattr(src_job, "user_id", 0) or int(getattr(src, "user_id", 0) or 0)),
            post_id=target_id,
            kind=getattr(src_job, "kind", None),
            status="done",
            progress=100,
            stage="done",
            stage_message="recovered_from_template",
            input_json=getattr(src_job, "input_json", None),
            draft_json=getattr(src_job, "draft_json", None),
            worker_task_id=None,
            result_json=getattr(src_job, "result_json", None),
            error=None,
        )
        db.add(j)

        if args.dry_run:
            db.rollback()
        else:
            db.commit()
        print(
            json.dumps(
                {
                    "ok": True,
                    "dry_run": bool(args.dry_run),
                    "post_id": int(target_id),
                    "source_post_id": int(source_id),
                    "job_id": str(new_job_id),
                    "media_version": str(new_version),
                },
                ensure_ascii=False,
            )
        )
        print("RESTORE_MISSING_POST_OK")
        return 0
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        print("RESTORE_MISSING_POST_FAIL")
        print(str(e))
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
