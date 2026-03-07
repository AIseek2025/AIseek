import re
import time
from typing import Any, Dict, List, Tuple, Optional

from app.core.cache import cache


_PII_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("phone", re.compile(r"(?:\+?86)?1[3-9]\d{9}")),
    ("id_card", re.compile(r"\b\d{17}[\dXx]\b")),
    ("email", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("qq", re.compile(r"(?:QQ|qq)[\\s:：]*([1-9]\\d{4,11})")),
    ("wechat", re.compile(r"(?:微信|wx|WX|vx|VX|wechat)[\\s:：]*([a-zA-Z][-_a-zA-Z0-9]{5,19})")),
    ("bank_card", re.compile(r"(?:银行卡|卡号)[\\s:：]*((?:\\d[ -]?){13,19})")),
]

_BLOCK_WORDS = {
    "恐怖袭击",
    "制毒",
    "买毒",
    "枪支弹药",
}

_RISK_WORDS: List[Tuple[str, List[str]]] = [
    ("porn", ["成人视频", "约炮", "强奸", "未成年色情", "裸聊"]),
    ("violence", ["杀人", "分尸", "爆炸物", "自杀教程"]),
    ("hate", ["种族灭绝", "纳粹", "极端仇恨"]),
    ("fraud", ["刷流水", "薅羊毛教程", "诈骗话术", "信用卡套现"]),
]

_AI_HINT_WORDS = {
    "AI",
    "人工智能",
    "大模型",
    "模型",
    "深度学习",
    "机器学习",
    "DeepSeek",
    "ChatGPT",
    "LLM",
    "提示词",
}

_REPORT_CONTEXT_WORDS = {
    "新闻",
    "报道",
    "通报",
    "公告",
    "警方",
    "公安",
    "法院",
    "检察院",
    "检方",
    "起诉",
    "审理",
    "判决",
    "拘留",
    "逮捕",
    "调查",
    "案件",
    "案发",
    "事故",
    "伤亡",
    "遇难",
    "受伤",
    "现场",
    "目击",
    "记者",
    "媒体",
    "发布会",
    "官方",
    "通告",
    "声明",
}

_HOWTO_RISK_WORDS = {
    "教程",
    "步骤",
    "怎么做",
    "如何做",
    "指南",
    "制作",
    "制造",
    "配方",
    "材料",
    "购买",
    "出售",
    "渠道",
    "联系方式",
    "加我",
    "私聊",
    "VX",
    "微信",
    "QQ",
    "telegram",
    "tg",
    "群",
}

_HOWTO_NEGATIONS = {
    "不含",
    "不包含",
    "不提供",
    "禁止",
    "请勿",
    "不要",
    "避免",
    "非教程",
    "不是教程",
}


def preflight_text(text: str, user_id: int = 0, requested_duration_sec: Optional[int] = None, queue_pressure: Optional[int] = None) -> Dict[str, Any]:
    raw = str(text or "").strip()
    issues: List[Dict[str, Any]] = []
    if not raw:
        return {"ok": False, "action": "reject", "issues": [{"kind": "empty"}], "sanitized_text": ""}

    uid = int(user_id or 0)
    try:
        if uid:
            cd = cache.get_json(f"ai:cooldown:{uid}") or {}
            until = int((cd or {}).get("until") or 0)
            if until and int(time.time()) < until:
                return {"ok": False, "action": "cooldown", "issues": [{"kind": "cooldown", "until": until}], "sanitized_text": ""}
    except Exception:
        pass
    if len(raw) > 30000:
        issues.append({"kind": "too_long", "max": 30000})
        raw = raw[:30000]

    for w in _BLOCK_WORDS:
        if w and w in raw:
            issues.append({"kind": "illegal", "hit": w})
            return {"ok": False, "action": "reject", "issues": issues, "sanitized_text": ""}

    for kind, words in _RISK_WORDS:
        for w in words:
            if w and w in raw:
                if str(kind) != "violence":
                    issues.append({"kind": "risk", "type": kind, "hit": w})
                    return {"ok": False, "action": "reject", "issues": issues, "sanitized_text": ""}
                low = raw.lower()
                howto = False
                try:
                    hit_pos = low.find(str(w or "").lower())
                    near = low
                    if hit_pos >= 0:
                        near = low[max(0, hit_pos - 80) : min(len(low), hit_pos + 120)]
                    for x in _HOWTO_RISK_WORDS:
                        t = str(x or "").strip()
                        if not t:
                            continue
                        t2 = t.lower()
                        pos = -1
                        if t2.isascii() and len(t2) <= 3:
                            try:
                                m2 = re.search(rf"(?<![a-z0-9]){re.escape(t2)}(?![a-z0-9])", near)
                                pos = int(m2.start()) if m2 else -1
                            except Exception:
                                pos = near.find(t2)
                        else:
                            pos = near.find(t2)
                        if pos < 0:
                            continue
                        window = near[max(0, pos - 10) : pos]
                        if any(n.lower() in window for n in _HOWTO_NEGATIONS):
                            continue
                        howto = True
                        break
                except Exception:
                    howto = any(x.lower() in low for x in _HOWTO_RISK_WORDS)
                report_ctx = any(x in raw for x in _REPORT_CONTEXT_WORDS) or ("http://" in low) or ("https://" in low)
                if howto:
                    issues.append({"kind": "risk", "type": "violence", "hit": w, "mode": "howto"})
                    return {"ok": False, "action": "reject", "issues": issues, "sanitized_text": ""}
                issues.append({"kind": "risk", "type": "violence", "hit": w, "mode": "reported_context" if report_ctx else "sensitive_context"})
                break
        else:
            continue
        break

    sanitized = raw
    for name, pat in _PII_PATTERNS:
        if pat.search(sanitized):
            issues.append({"kind": "pii", "type": name})
            sanitized = pat.sub("[REDACTED]", sanitized)

    try:
        short = len(sanitized) < 240
        if short and not any(k in sanitized for k in _AI_HINT_WORDS):
            low = str(sanitized or "").lower()
            allow_short = False
            try:
                if any(x in sanitized for x in _REPORT_CONTEXT_WORDS):
                    allow_short = True
                elif "http://" in low or "https://" in low:
                    allow_short = True
                elif any(x in sanitized for x in {"科普", "解读", "盘点", "总结", "介绍", "评论", "观点", "分析", "问答"}):
                    allow_short = True
            except Exception:
                allow_short = False
            if not allow_short:
                issues.append({"kind": "irrelevant"})
                return {"ok": False, "action": "reject", "issues": issues, "sanitized_text": ""}
            issues.append({"kind": "short"})
    except Exception:
        pass

    vlen = len(sanitized)
    if vlen >= 2500:
        value_tier = "high"
        base_target = 120
        base_scenes = 12
    elif vlen >= 900:
        value_tier = "mid"
        base_target = 60
        base_scenes = 8
    else:
        value_tier = "low"
        base_target = 30
        base_scenes = 5

    req = None
    try:
        if requested_duration_sec is not None:
            req = int(requested_duration_sec)
            if req <= 0:
                req = None
    except Exception:
        req = None
    try:
        if req is not None:
            req = max(30, min(3600, int(req)))
    except Exception:
        req = None

    qp = 0
    try:
        qp = int(queue_pressure or 0)
        if qp < 0:
            qp = 0
    except Exception:
        qp = 0
    if qp >= 200:
        pressure = 0.55
    elif qp >= 80:
        pressure = 0.75
    elif qp >= 30:
        pressure = 0.9
    else:
        pressure = 1.0

    target_sec = int(round(float(base_target) * float(pressure)))
    if req is not None:
        target_sec = min(int(req), int(max(30, target_sec)))
    else:
        target_sec = int(max(30, target_sec))
        if value_tier == "high" and pressure >= 1.0:
            target_sec = min(180, target_sec + 60)
        elif value_tier == "mid" and pressure >= 1.0:
            target_sec = min(120, target_sec + 30)

    if req is not None and req >= 600:
        target_sec = min(int(req), max(target_sec, 300))
    if req is not None and req >= 1800:
        target_sec = min(int(req), max(target_sec, 900))
    if req is not None and req >= 3600:
        target_sec = min(int(req), max(target_sec, 1200))

    scene_count = int(max(5, min(220, round(float(target_sec) / 8.0))))
    if scene_count < int(base_scenes):
        scene_count = int(base_scenes)
    if target_sec <= 90:
        scene_count = min(scene_count, 16)

    return {
        "ok": True,
        "action": "pass",
        "issues": issues,
        "sanitized_text": sanitized,
        "value_tier": value_tier,
        "target_sec": int(target_sec),
        "scene_count": int(scene_count),
        "requested_duration_sec": int(req) if req is not None else None,
        "queue_pressure": int(qp),
    }
