import argparse
import json
import sys

from sqlalchemy import desc

from app.db.session import SessionLocal
from app.models.all_models import AIJob, Post
from app.api.v1.endpoints.ai_jobs import _resolve_best_script_for_job, _is_usable_draft


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=500)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    db = SessionLocal()
    scanned = 0
    updated = 0
    fixed_result = 0
    fixed_draft = 0
    skipped = 0
    failed = 0
    try:
        rows = (
            db.query(AIJob)
            .filter(AIJob.status == "done")
            .order_by(desc(AIJob.created_at))
            .limit(max(1, int(args.limit or 500)))
            .all()
        )
        for j in rows:
            scanned += 1
            res = j.result_json if isinstance(j.result_json, dict) else {}
            ps = res.get("production_script") if isinstance(res.get("production_script"), dict) else None
            dj = j.draft_json if isinstance(j.draft_json, dict) else None
            if _is_usable_draft(ps) and _is_usable_draft(dj):
                skipped += 1
                continue
            p = db.query(Post).filter(Post.id == int(getattr(j, "post_id", 0) or 0)).first()
            best = _resolve_best_script_for_job(db, j, p)
            if not _is_usable_draft(best):
                failed += 1
                continue
            changed = False
            if not _is_usable_draft(dj):
                j.draft_json = best
                fixed_draft += 1
                changed = True
            if not _is_usable_draft(ps):
                r2 = dict(res)
                r2["production_script"] = best
                j.result_json = r2
                fixed_result += 1
                changed = True
            if changed:
                updated += 1
        if args.dry_run:
            db.rollback()
        else:
            db.commit()
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        print("BACKFILL_AI_MISSING_SCRIPTS_FAIL")
        print(str(e))
        return 1
    finally:
        try:
            db.close()
        except Exception:
            pass

    out = {
        "dry_run": bool(args.dry_run),
        "scanned": scanned,
        "updated_jobs": updated,
        "fixed_result_script": fixed_result,
        "fixed_draft_script": fixed_draft,
        "skipped_already_ok": skipped,
        "failed_unresolved": failed,
    }
    print(json.dumps(out, ensure_ascii=False))
    print("BACKFILL_AI_MISSING_SCRIPTS_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
