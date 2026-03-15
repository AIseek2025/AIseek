#!/usr/bin/env python3
"""
诊断 AI 视频 Job 的口播稿来源：是否调用 DeepSeek、是否使用 draft_json、是否降级兜底。

用法:
  cd backend && python -m scripts.diagnose_job_script --job-id ff1e9c8b-92d8-4a78-973a-a4fad8c76c02
  cd backend && python -m scripts.diagnose_job_script --post-id 88
"""
import argparse
import json
import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import SessionLocal
from app.models.all_models import AIJob, Post


def _nrm(s: str) -> str:
    import re
    t = str(s or "").lower()
    return re.sub(r"[\s，,。．.！!？?：:；;、】【\[\]（）()""\"'‘'·`~@#$%^&*_+=|\\/<>-]", "", t)


def _sim(a: str, b: str) -> float:
    from difflib import SequenceMatcher
    aa = _nrm(a)
    bb = _nrm(b)
    if not aa or not bb:
        return 0.0
    try:
        return float(SequenceMatcher(None, aa, bb).ratio())
    except Exception:
        return 0.0


def main() -> int:
    ap = argparse.ArgumentParser(description="Diagnose AI job script source (DeepSeek vs draft vs fallback)")
    ap.add_argument("--job-id", type=str, help="AI Job UUID")
    ap.add_argument("--post-id", type=int, help="Post ID (will resolve ai_job_id)")
    ap.add_argument("--trace-dir", type=str, default=None, help="Worker trace dir (e.g. /app/outputs/traces)")
    args = ap.parse_args()

    db = SessionLocal()
    job = None
    post = None

    if args.job_id:
        job = db.query(AIJob).filter(AIJob.id == str(args.job_id).strip()).first()
        if job and getattr(job, "post_id", None):
            post = db.query(Post).filter(Post.id == int(job.post_id)).first()
    if args.post_id and not job:
        post = db.query(Post).filter(Post.id == int(args.post_id)).first()
        if post and getattr(post, "ai_job_id", None):
            job = db.query(AIJob).filter(AIJob.id == str(post.ai_job_id)).first()
        if not job and post:
            from sqlalchemy import desc
            job = (
                db.query(AIJob)
                .filter(AIJob.post_id == int(args.post_id))
                .order_by(desc(AIJob.created_at))
                .first()
            )

    if not job:
        print("未找到 Job")
        return 1

    inp = job.input_json if isinstance(getattr(job, "input_json", None), dict) else {}
    draft = getattr(job, "draft_json", None)
    res = getattr(job, "result_json", None)
    content = str(inp.get("content") or (post.content_text if post else "") or "").strip()

    # production_script
    ps = (res or {}).get("production_script") if isinstance(res, dict) else {}
    scenes = ps.get("scenes") if isinstance(ps, dict) and isinstance(ps.get("scenes"), list) else []
    voice_lines = [str(s.get("narration") or "").strip() for s in scenes if isinstance(s, dict) and str(s.get("narration") or "").strip()]
    voice_text = "\n".join(voice_lines).strip()

    # degraded?
    meta_top = (res or {}).get("_meta") if isinstance(res, dict) else {}
    meta_ps = (ps or {}).get("_meta") if isinstance(ps, dict) else {}
    degraded = bool(meta_top.get("degraded") or meta_ps.get("degraded"))
    degraded_reason = str(meta_top.get("degraded_reason") or meta_ps.get("degraded_reason") or "").strip()

    # similarity
    sim = _sim(voice_text, content) if voice_text and content else 0.0

    report = {
        "job_id": str(getattr(job, "id", "")),
        "post_id": int(getattr(job, "post_id", 0) or 0) or (int(getattr(post, "id", 0) or 0) if post else 0),
        "status": str(getattr(job, "status", "")),
        "stage": str(getattr(job, "stage", "")),
        "content_len": len(content),
        "content_preview": content[:200] + ("..." if len(content) > 200 else ""),
        "draft_json_at_dispatch": "有" if isinstance(draft, dict) and draft else "无",
        "draft_has_scenes": len((draft or {}).get("scenes") or []) if isinstance(draft, dict) else 0,
        "production_script_scenes": len(scenes),
        "voice_text_len": len(voice_text),
        "voice_text_preview": voice_text[:300] + ("..." if len(voice_text) > 300 else ""),
        "voice_vs_content_similarity": round(sim, 3),
        "degraded": degraded,
        "degraded_reason": degraded_reason or (None if not degraded else "unknown"),
        "inference": [],
    }
    report["inference"] = []

    if isinstance(draft, dict) and draft and (draft.get("scenes") or []):
        report["inference"].append("dispatch 时传入了 draft_json，worker 会直接使用，不调用 DeepSeek")
    else:
        report["inference"].append("dispatch 时无 draft_json，worker 会调用 DeepSeek.analyze_text()")

    if degraded:
        report["inference"].append(f"降级兜底：{degraded_reason or 'unknown'}（可能：无 API Key、解析失败、超时等）")
    else:
        report["inference"].append("未降级，应为 DeepSeek 正常返回")

    if sim >= 0.95 and len(voice_text) >= 200:
        report["inference"].append("口播稿与原文相似度≥95%，pipeline 会触发 Sanitizer 分段改写")
    elif sim >= 0.7:
        report["inference"].append("口播稿与原文相似度较高，可能仍偏照念原文")

    # Trace file
    trace_dir = args.trace_dir or os.getenv("TRACE_LOG_DIR") or "/app/outputs/traces"
    trace_path = Path(trace_dir) / f"job_{report['job_id']}_trace.json"
    if trace_path.exists():
        try:
            with open(trace_path, "r", encoding="utf-8") as f:
                trace = json.load(f)
            steps = trace.get("steps") or []
            analyze_steps = [s for s in steps if str(s.get("step") or "") == "analyze"]
            report["trace_analyze_steps"] = analyze_steps
            report["trace_file"] = str(trace_path)
        except Exception as e:
            report["trace_error"] = str(e)
    else:
        report["trace_file"] = str(trace_path)
        report["trace_exists"] = False

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
