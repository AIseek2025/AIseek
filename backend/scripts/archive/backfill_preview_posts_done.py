import argparse
import json

from sqlalchemy import desc

from app.db.session import SessionLocal
from app.models.all_models import Post, AIJob


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=1000)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    db = SessionLocal()
    scanned = 0
    updated = 0
    linked_job = 0
    skipped = 0
    samples = []
    try:
        rows = db.query(Post).order_by(desc(Post.id)).limit(max(1, int(args.limit or 1000))).all()
        for p in rows:
            scanned += 1
            if str(getattr(p, "status", "") or "") != "preview":
                skipped += 1
                continue
            if not getattr(p, "video_url", None) or not getattr(p, "cover_url", None):
                skipped += 1
                continue
            jid = str(getattr(p, "ai_job_id", "") or "")
            j = db.query(AIJob).filter(AIJob.id == jid).first() if jid else None
            if not j:
                j = db.query(AIJob).filter(AIJob.post_id == int(getattr(p, "id", 0) or 0)).order_by(desc(AIJob.created_at)).first()
            if not j or str(getattr(j, "status", "") or "") != "done":
                skipped += 1
                continue
            if not jid:
                p.ai_job_id = str(getattr(j, "id", "") or "")
                linked_job += 1
            p.status = "done"
            updated += 1
            if len(samples) < 20:
                samples.append({"post_id": int(getattr(p, "id", 0) or 0), "job_id": str(getattr(j, "id", "") or "")})
        if args.dry_run:
            db.rollback()
        else:
            db.commit()
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        print("BACKFILL_PREVIEW_POSTS_DONE_FAIL")
        print(str(e))
        return 1
    finally:
        db.close()

    print(
        json.dumps(
            {
                "dry_run": bool(args.dry_run),
                "scanned": int(scanned),
                "updated": int(updated),
                "linked_job": int(linked_job),
                "skipped": int(skipped),
                "samples": samples,
            },
            ensure_ascii=False,
        )
    )
    print("BACKFILL_PREVIEW_POSTS_DONE_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
