import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "worker"))

from app.pipeline.sanitizer import Sanitizer
from app.services.subtitle_service import build_cues_by_duration, evaluate_subtitle_quality


def _fail(msg: str) -> int:
    sys.stdout.write("AI_LONG_TEXT_QUALITY_REGRESSION_FAIL\n")
    sys.stdout.write(f"- {msg}\n")
    return 1


def main() -> int:
    long_sub = "这是一个非常非常长的字幕句子，它没有被合理切分的话，就会在画面上遮挡大量信息并影响观看体验。"
    out = Sanitizer.sanitize_subtitles([{"text": long_sub}])
    if not out or len(out) < 3:
        return _fail("sanitize_subtitles did not split long subtitle")
    if any(len(str(x.get("text") or "")) > 22 for x in out):
        return _fail("sanitize_subtitles produced subtitle longer than 22 chars")

    segs = [x["text"] for x in out]
    cues = build_cues_by_duration(segs, 18.0, offset_sec=1.0)
    if len(cues) != len(segs):
        return _fail("build_cues_by_duration length mismatch")
    prev = -1.0
    for st, ed, txt in cues:
        if not txt:
            return _fail("empty cue text generated")
        if st < prev:
            return _fail("cue start is not monotonic")
        if ed <= st:
            return _fail("cue end must be greater than start")
        prev = st
    qa = evaluate_subtitle_quality(cues)
    if int((qa or {}).get("score") or 0) <= 0:
        return _fail("evaluate_subtitle_quality produced invalid score")
    if str((qa or {}).get("grade") or "") not in {"A", "B", "C", "D"}:
        return _fail("evaluate_subtitle_quality produced invalid grade")

    chat_file = ROOT / "backend/app/services/ai_chat_command_service.py"
    chat_text = chat_file.read_text(encoding="utf-8")
    if 'if any(x in t for x in ["方形", "1:1", "1：1", "正方形"]):' not in chat_text:
        return _fail("cover orientation parser for square command not found")
    if "return \"portrait\"" not in chat_text:
        return _fail("square cover command should normalize to portrait")

    sys.stdout.write("AI_LONG_TEXT_QUALITY_REGRESSION_OK\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
