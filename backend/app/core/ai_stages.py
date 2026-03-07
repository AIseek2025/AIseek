from typing import Dict


STAGE_RANK: Dict[str, int] = {
    "start": 10,
    "draft_loaded": 15,
    "deepseek": 20,
    "deepseek_analyzed": 20,
    "chat_ai": 25,
    "tts": 35,
    "bgm": 40,
    "synthesis": 55,
    "render": 55,
    "video": 55,
    "upload_mp4": 75,
    "upload_images": 85,
    "package_hls": 90,
    "upload": 90,
    "chat_ai_done": 100,
    "done": 100,
    "failed": 100,
    "cancelled": 100,
    "chat_ai_failed": 100,
}


ALLOW_DRAFT_STAGES = {"deepseek", "draft_loaded", "chat_ai_done"}
ALLOW_ASSISTANT_MESSAGE_STAGES = {"chat_ai_done"}


def stage_rank(stage: str) -> int:
    s = str(stage or "").strip().lower()
    return int(STAGE_RANK.get(s, 0))


def allow_draft_write(stage: str) -> bool:
    return str(stage or "").strip().lower() in ALLOW_DRAFT_STAGES


def allow_assistant_message_write(stage: str) -> bool:
    return str(stage or "").strip().lower() in ALLOW_ASSISTANT_MESSAGE_STAGES
