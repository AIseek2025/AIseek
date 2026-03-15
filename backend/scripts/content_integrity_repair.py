import argparse
import json

from sqlalchemy import desc

from app.db.session import SessionLocal
from app.models.all_models import Post, AIJob
from app.api.v1.endpoints.ai_jobs import _resolve_best_script_for_job, _is_usable_draft


def _job_for_post(db, post_id: int, ai_job_id: str) -> AIJob | None:
    jid = str(ai_job_id or "").strip()
    if jid:
        j = db.query(AIJob).filter(AIJob.id == jid).first()
        if j:
            return j
    return (
        db.query(AIJob)
        .filter(AIJob.post_id == int(post_id))
        .order_by(desc(AIJob.created_at))
        .first()
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=1000)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    db = SessionLocal()
    lim = max(1, min(5000, int(args.limit or 1000)))
    scanned = 0
    bad = 0
    fixed_posts = 0
    linked_job = 0
    fixed_script = 0
    unresolved = 0
    samples = []
    try:
        rows = db.query(Post).order_by(desc(Post.id)).limit(lim).all()
        for p in rows:
            scanned += 1
            st = str(getattr(p, "status", "") or "")
            if st not in {"done", "preview"}:
                continue
            if not getattr(p, "video_url", None) or not getattr(p, "cover_url", None):
                continue
            j = _job_for_post(db, int(getattr(p, "id", 0) or 0), str(getattr(p, "ai_job_id", "") or ""))
            if not j:
                bad += 1
                unresolved += 1
                if len(samples) < 20:
                    samples.append({"post_id": int(getattr(p, "id", 0) or 0), "reason": "job_missing"})
                continue
            res = j.result_json if isinstance(j.result_json, dict) else {}
            ps = res.get("production_script") if isinstance(res.get("production_script"), dict) else None
            dj = j.draft_json if isinstance(j.draft_json, dict) else None
            ok = _is_usable_draft(ps) and _is_usable_draft(dj)
            if str(getattr(p, "status", "") or "") == "done" and ok and str(getattr(p, "ai_job_id", "") or "") == str(getattr(j, "id", "") or ""):
                continue
            bad += 1
            changed = False
            if str(getattr(p, "ai_job_id", "") or "") != str(getattr(j, "id", "") or ""):
                p.ai_job_id = str(getattr(j, "id", "") or "")
                linked_job += 1
                changed = True
            if str(getattr(p, "status", "") or "") != "done":
                p.status = "done"
                changed = True
            if not ok:
                best = _resolve_best_script_for_job(db, j, p)
                if _is_usable_draft(best):
                    if not _is_usable_draft(dj):
                        j.draft_json = best
                    if not _is_usable_draft(ps):
                        r2 = dict(res)
                        r2["production_script"] = best
                        j.result_json = r2
                    fixed_script += 1
                    changed = True
            if changed:
                fixed_posts += 1
                if len(samples) < 20:
                    samples.append(
                        {
                            "post_id": int(getattr(p, "id", 0) or 0),
                            "job_id": str(getattr(j, "id", "") or ""),
                            "status": str(getattr(p, "status", "") or ""),
                        }
                    )
            else:
                unresolved += 1
        if args.dry_run:
            db.rollback()
        else:
            db.commit()
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        print("CONTENT_INTEGRITY_REPAIR_FAIL")
        print(str(e))
        return 1
    finally:
        db.close()

    out = {
        "dry_run": bool(args.dry_run),
        "limit": int(lim),
        "scanned": int(scanned),
        "bad_candidates": int(bad),
        "fixed_posts": int(fixed_posts),
        "linked_job": int(linked_job),
        "fixed_script": int(fixed_script),
        "unresolved": int(unresolved),
        "samples": samples,
    }
    print(json.dumps(out, ensure_ascii=False))
    print("CONTENT_INTEGRITY_REPAIR_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
