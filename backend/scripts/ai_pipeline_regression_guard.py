import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
VIDEO_PIPELINE = ROOT / "worker/app/pipeline/video_pipeline.py"
DEEPSEEK = ROOT / "worker/app/services/deepseek_service.py"
DISPATCH_RETRY = ROOT / "backend/app/services/dispatch_retry_service.py"
AI_JOBS = ROOT / "backend/app/api/v1/endpoints/ai_jobs.py"
SANITIZER = ROOT / "worker/app/pipeline/sanitizer.py"
SUBTITLE = ROOT / "worker/app/services/subtitle_service.py"
POSTS = ROOT / "backend/app/api/v1/endpoints/posts.py"
OPS = ROOT / "backend/app/api/v1/endpoints/ops.py"
RUNTIME_AI_PRODUCTION = ROOT / "backend/app/observability/runtime_ai_production.py"
WORKER_CALLBACK = ROOT / "worker/app/worker_callback.py"
BACKEND_STAGES = ROOT / "backend/app/core/ai_stages.py"
WORKER_STAGES = ROOT / "worker/app/core/ai_stages.py"
AI_CREATE_ROUTES = ROOT / "backend/app/api/v1/endpoints/ai_creation/routes.py"
DUAL_ENTRY_GUARD = ROOT / "backend/scripts/dual_entry_guard.py"


def _must_contain(text: str, needle: str, label: str, errs: list[str]) -> None:
    if needle not in text:
        errs.append(f"{label}: missing `{needle}`")


def main() -> int:
    errs: list[str] = []
    vp = VIDEO_PIPELINE.read_text(encoding="utf-8")
    ds = DEEPSEEK.read_text(encoding="utf-8")
    dr = DISPATCH_RETRY.read_text(encoding="utf-8")
    aj = AI_JOBS.read_text(encoding="utf-8")
    sz = SANITIZER.read_text(encoding="utf-8")
    sb = SUBTITLE.read_text(encoding="utf-8")
    ps = POSTS.read_text(encoding="utf-8")
    op = OPS.read_text(encoding="utf-8")
    rap = RUNTIME_AI_PRODUCTION.read_text(encoding="utf-8")
    wc = WORKER_CALLBACK.read_text(encoding="utf-8")
    bst = BACKEND_STAGES.read_text(encoding="utf-8")
    wst = WORKER_STAGES.read_text(encoding="utf-8")
    acr = AI_CREATE_ROUTES.read_text(encoding="utf-8")
    deg = DUAL_ENTRY_GUARD.read_text(encoding="utf-8")

    _must_contain(vp, '"premium_en" in vs', "video_pipeline.py", errs)
    _must_contain(vp, "en_ratio >= 0.6", "video_pipeline.py", errs)
    _must_contain(vp, "en_translation_unavailable", "video_pipeline.py", errs)
    _must_contain(vp, "analysis_audit", "video_pipeline.py", errs)
    _must_contain(vp, "subtitle_audit", "video_pipeline.py", errs)
    _must_contain(vp, "generation_quality", "video_pipeline.py", errs)
    _must_contain(vp, "build_cues_by_duration", "video_pipeline.py", errs)
    _must_contain(vp, "def _subtitle_from_narration(", "video_pipeline.py", errs)
    _must_contain(vp, "using_draft", "video_pipeline.py", errs)
    _must_contain(vp, "draft_json=analysis.get(\"production_script\")", "video_pipeline.py", errs)
    _must_contain(vp, "stage=\"done\"", "video_pipeline.py", errs)

    _must_contain(ds, '"degraded_reason": str(degraded_reason or "fallback_video")', "deepseek_service.py", errs)
    _must_contain(ds, "deepseek_parse_failed", "deepseek_service.py", errs)
    _must_contain(ds, "deepseek_unavailable", "deepseek_service.py", errs)
    _must_contain(ds, "def _sanitize_video_payload(", "deepseek_service.py", errs)
    _must_contain(ds, "def _subtitle_from_narration(", "deepseek_service.py", errs)

    _must_contain(dr, '"cover_orientation": _norm_cover_orientation(inp.get("cover_orientation"))', "dispatch_retry_service.py", errs)
    _must_contain(dr, 'if bool(rt.get("dispatch_hold_enabled", False)):', "dispatch_retry_service.py", errs)
    _must_contain(dr, '"dispatch_hold"', "dispatch_retry_service.py", errs)
    _must_contain(dr, "def _auto_release_dispatch_hold(", "dispatch_retry_service.py", errs)
    _must_contain(dr, "auto_release_batch_size", "dispatch_retry_service.py", errs)
    _must_contain(dr, "auto_release_interval_sec", "dispatch_retry_service.py", errs)
    _must_contain(dr, "auto_release_adaptive_enabled", "dispatch_retry_service.py", errs)
    _must_contain(dr, "last_auto_release_adaptive_mode", "dispatch_retry_service.py", errs)
    _must_contain(dr, "def _auto_hold_by_queue_pressure(", "dispatch_retry_service.py", errs)
    _must_contain(dr, '"queue_pressure_auto_hold"', "dispatch_retry_service.py", errs)
    _must_contain(aj, '"cover_orientation": _norm_cover_orientation(inp.get("cover_orientation"))', "ai_jobs.py", errs)
    _must_contain(aj, "def _sanitize_rerun_draft(", "ai_jobs.py", errs)
    _must_contain(aj, "draft = _sanitize_rerun_draft(draft)", "ai_jobs.py", errs)
    _must_contain(aj, "def _latest_draft_from_versions(", "ai_jobs.py", errs)
    _must_contain(aj, "def _build_fallback_draft(", "ai_jobs.py", errs)
    _must_contain(aj, "def _resolve_best_script_for_job(", "ai_jobs.py", errs)
    _must_contain(aj, "if not _is_usable_draft(draft):", "ai_jobs.py", errs)
    _must_contain(aj, "def _apply_dispatch_gate(", "ai_jobs.py", errs)
    _must_contain(aj, '"stage": "dispatch_hold"', "ai_jobs.py", errs)
    _must_contain(aj, 'str(gate.get("event") or "dispatch_pending")', "ai_jobs.py", errs)
    _must_contain(aj, '@router.post("/admin/jobs/{job_id}/release-hold")', "ai_jobs.py", errs)
    _must_contain(op, '@router.get("/ai-production/runtime"', "ops.py", errs)
    _must_contain(op, '@router.post("/ai-production/runtime"', "ops.py", errs)
    _must_contain(op, '@router.post("/ai-production/guard")', "ops.py", errs)
    _must_contain(op, '@router.post("/ai-production/release-hold")', "ops.py", errs)
    _must_contain(op, '@router.get("/ai-production/backfill-missing-scripts/preview")', "ops.py", errs)
    _must_contain(op, '@router.post("/ai-production/backfill-missing-scripts/execute")', "ops.py", errs)
    _must_contain(op, 'if phrase != "BACKFILL_AI_MISSING_SCRIPTS":', "ops.py", errs)
    _must_contain(op, '@router.get("/ai-production/content-integrity-repair/preview")', "ops.py", errs)
    _must_contain(op, '@router.post("/ai-production/content-integrity-repair/execute")', "ops.py", errs)
    _must_contain(op, 'if phrase != "CONTENT_INTEGRITY_REPAIR":', "ops.py", errs)
    _must_contain(op, '@router.get("/post-recovery/preview")', "ops.py", errs)
    _must_contain(op, '@router.post("/post-recovery/execute")', "ops.py", errs)
    _must_contain(op, 'if phrase != "RECOVER_POST_BY_ID":', "ops.py", errs)
    _must_contain(op, '@router.get("/ai-production/status")', "ops.py", errs)
    _must_contain(op, '@router.post("/ai-production/release-tick")', "ops.py", errs)
    _must_contain(op, '@router.post("/ai-production/adaptive-suggestion/apply")', "ops.py", errs)
    _must_contain(op, '@router.post("/ai-production/adaptive-rollback/check")', "ops.py", errs)
    _must_contain(op, '@router.get("/ai-production/audit")', "ops.py", errs)
    _must_contain(op, '@router.get("/ai-production/audit/export")', "ops.py", errs)
    _must_contain(op, '@router.get("/ai-production/audit/summary")', "ops.py", errs)
    _must_contain(op, '"auto_release_on_disable": bool(_f("auto_release_on_disable", True))', "ops.py", errs)
    _must_contain(op, '"auto_release_interval_sec": int(_f("auto_release_interval_sec", 15))', "ops.py", errs)
    _must_contain(op, '"auto_release_adaptive_enabled": bool(_f("auto_release_adaptive_enabled", True))', "ops.py", errs)
    _must_contain(op, '"auto_release_adaptive_apply_min_confidence": float(_f("auto_release_adaptive_apply_min_confidence", 0.4))', "ops.py", errs)
    _must_contain(op, '"auto_release_rollback_enabled": bool(_f("auto_release_rollback_enabled", True))', "ops.py", errs)
    _must_contain(op, '"adaptive_suggestion_apply": {"can_apply": bool(can_apply)', "ops.py", errs)
    _must_contain(op, "def _maybe_apply_adaptive_rollback(", "ops.py", errs)
    _must_contain(op, "def _append_adaptive_rollback_history(", "ops.py", errs)
    _must_contain(op, "def _append_adaptive_apply_history(", "ops.py", errs)
    _must_contain(op, "def _audit_reason_value(", "ops.py", errs)
    _must_contain(op, "def _ai_production_adaptive_suggestion(", "ops.py", errs)
    _must_contain(op, "def _release_dispatch_hold_jobs(", "ops.py", errs)
    _must_contain(rap, 'return "runtime:ai_production"', "runtime_ai_production.py", errs)

    _must_contain(sz, "max_len = 22", "sanitizer.py", errs)
    _must_contain(sz, 'ch in "，。！？；：,.!?;:"', "sanitizer.py", errs)
    _must_contain(sb, "def evaluate_subtitle_quality(", "subtitle_service.py", errs)
    _must_contain(wc, "def _sanitize_draft_payload(", "worker_callback.py", errs)
    _must_contain(wc, "draft_json = _sanitize_draft_payload(draft_json)", "worker_callback.py", errs)
    _must_contain(bst, "ALLOW_DRAFT_STAGES = {\"deepseek\", \"draft_loaded\", \"chat_ai_done\", \"done\"}", "backend ai_stages.py", errs)
    _must_contain(wst, "ALLOW_DRAFT_STAGES = {\"deepseek\", \"draft_loaded\", \"chat_ai_done\", \"done\"}", "worker ai_stages.py", errs)
    _must_contain(ps, "def _sanitize_callback_draft(", "posts.py", errs)
    _must_contain(ps, 'st_post = "failed" if st == "cancelled" else st', "posts.py", errs)
    _must_contain(ps, "if post and not getattr(post, \"ai_job_id\", None):", "posts.py", errs)
    _must_contain(ps, "post.ai_job_id = str(getattr(job, \"id\"))", "posts.py", errs)
    _must_contain(ps, "job.draft_json = dj", "posts.py", errs)
    _must_contain(ps, "cur[\"production_script\"] = dj", "posts.py", errs)
    _must_contain(aj, '"generation_quality": obs.get("generation_quality")', "ai_jobs.py", errs)
    _must_contain(ps, '"generation_quality": obs_evt.get("generation_quality")', "posts.py", errs)
    _must_contain(acr, "from app.api.v1.endpoints.ai_jobs import _resolve_best_script_for_job", "ai_creation/routes.py", errs)
    _must_contain(acr, 'result["production_script"] = ps', "ai_creation/routes.py", errs)
    _must_contain(deg, "max_probe_age", "dual_entry_guard.py", errs)
    _must_contain(deg, "client_probe_fresh", "dual_entry_guard.py", errs)

    if errs:
        sys.stdout.write("AI_PIPELINE_REGRESSION_GUARD_FAIL\n")
        for e in errs:
            sys.stdout.write(f"- {e}\n")
        return 1
    sys.stdout.write("AI_PIPELINE_REGRESSION_GUARD_OK\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
