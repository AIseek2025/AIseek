from __future__ import annotations

import json
import re
from typing import Any

from app.services.deepseek_service import deepseek_service
from app.core.config import settings
from app.services.placeholder.core_types import SearchPlan


def _clean_token(s: str) -> str:
    t = str(s or "").strip()
    t = re.sub(r"\s+", " ", t)
    t = t.replace("\u200b", "")
    return t


def _fallback_plans(title: str, visual_prompts: list[str], persona_tags: list[str], orientation: str, min_w: int, min_h: int) -> list[SearchPlan]:
    kws = []
    for x in [title] + (visual_prompts or []):
        t = _clean_token(x)
        if t:
            kws.append(t)
    for tg in persona_tags or []:
        t = _clean_token(tg)
        if t.startswith("cat:"):
            kws.append(t.split(":", 1)[1])
    q = " ".join([k for k in kws if k])[:100]
    if not q:
        q = "abstract background"
    return [SearchPlan(query=q, orientation=orientation, min_width=min_w, min_height=min_h, max_duration=90)]


async def build_search_plans(
    *,
    user_id: int,
    title: str,
    content: str,
    visual_prompts_en: list[str],
    persona_tags: list[str],
    orientation: str,
    min_w: int,
    min_h: int,
    target_sec: int,
) -> list[SearchPlan]:
    t = _clean_token(title)
    vp = [_clean_token(x) for x in (visual_prompts_en or []) if _clean_token(x)]
    tags = [_clean_token(x) for x in (persona_tags or []) if _clean_token(x)]

    if not getattr(deepseek_service, "client", None):
        return _fallback_plans(t, vp, tags, orientation, min_w, min_h)

    system_prompt = (
        "你是一个“视频素材检索提示词工程师 + 召回策略编排器”。"
        "目标：为短视频平台生成“可直接用于 Pixabay/Pexels 搜索”的精准英文 query，并给出备选 query。"
        "要求："
        "1) 输出严格 JSON，不要解释。"
        "2) query 必须为英文，<= 100 字符，避免品牌词与人名。"
        "3) 不要生成可能侵权/敏感/成人/暴力内容。"
        "4) 适配竖屏背景视频：优先 abstract background / b-roll / texture / minimal / gradient / city / nature / tech 等。"
        "5) 如果有用户偏好 tags（cat:xxx/tab:xxx/ev:xxx），用于轻量个性化：在不偏离主题前提下增加 1-2 个风格词。"
        "6) 给出 provider_preference：auto|pixabay|pexels，并说明原因（<= 30 字）。"
        "7) 给出 2-4 条 plans。"
        "JSON 结构："
        "{"
        "\"plans\":["
        "{"
        "\"query_en\":\"...\","
        "\"provider_preference\":[\"auto\"],"
        "\"orientation\":\"portrait\","
        "\"min_width\":1080,"
        "\"min_height\":1920,"
        "\"max_duration\":90,"
        "\"reason\":\"...\""
        "}"
        "]"
        "}"
    )

    payload = {
        "user_id": int(user_id or 0),
        "title": t,
        "content_hint": _clean_token(str(content or "")[:600]),
        "visual_prompts_en": vp[:6],
        "persona_tags": tags[:10],
        "constraints": {
            "orientation": str(orientation or "portrait"),
            "min_width": int(min_w),
            "min_height": int(min_h),
            "target_sec": int(target_sec or 0),
        },
    }
    try:
        response = deepseek_service.client.chat.completions.create(
            model=getattr(settings, "deepseek_model", "deepseek-chat"),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=900,
        )
        text = response.choices[0].message.content
        obj: Any = json.loads(text or "{}")
    except Exception:
        return _fallback_plans(t, vp, tags, orientation, min_w, min_h)

    plans = obj.get("plans") if isinstance(obj, dict) else None
    if not isinstance(plans, list) or not plans:
        return _fallback_plans(t, vp, tags, orientation, min_w, min_h)

    out: list[SearchPlan] = []
    for it in plans[:4]:
        if not isinstance(it, dict):
            continue
        q = _clean_token(it.get("query_en"))
        if not q:
            continue
        if len(q) > 100:
            q = q[:100]
        pref = it.get("provider_preference")
        if isinstance(pref, list):
            pref2 = tuple([str(x).strip().lower() for x in pref if str(x).strip()]) or ("auto",)
        else:
            pref2 = ("auto",)
        out.append(
            SearchPlan(
                query=q,
                orientation=str(it.get("orientation") or orientation or "portrait"),
                min_width=int(it.get("min_width") or min_w),
                min_height=int(it.get("min_height") or min_h),
                max_duration=int(it.get("max_duration") or 90),
                provider_preference=pref2,
                user_id=int(user_id or 0),
            )
        )
    if not out:
        return _fallback_plans(t, vp, tags, orientation, min_w, min_h)
    return out
