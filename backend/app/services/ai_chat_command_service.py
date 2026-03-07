from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple


_RE_WS = re.compile(r"\s+")


def _norm(s: str) -> str:
    s2 = str(s or "")
    s2 = s2.replace("：", ":").replace("，", ",").replace("。", ".").replace("（", "(").replace("）", ")")
    s2 = _RE_WS.sub(" ", s2).strip()
    return s2


def _extract_after(text: str, keys: List[str]) -> Optional[str]:
    t = str(text or "")
    for k in keys:
        idx = t.find(k)
        if idx < 0:
            continue
        out = t[idx + len(k) :].strip()
        if out.startswith(":"):
            out = out[1:].strip()
        if out.startswith("："):
            out = out[1:].strip()
        if out:
            return out[:500]
    return None


def _parse_duration_sec(text: str) -> Optional[int]:
    t = str(text or "")
    m = re.search(r"(\d{1,4})\s*(秒|s)\b", t, flags=re.I)
    if m:
        n = int(m.group(1))
        return max(5, min(3600, n))
    m = re.search(r"(\d{1,3})\s*(分钟|min)\b", t, flags=re.I)
    if m:
        n = int(m.group(1)) * 60
        return max(5, min(3600, n))
    m = re.search(r"(最长|最多|不超过|上限)\s*(\d{1,4})\b", t)
    if m:
        n = int(m.group(2))
        if n <= 20:
            n = n * 60
        return max(5, min(3600, n))
    return None


def _parse_cover_orientation(text: str) -> Optional[str]:
    t = str(text or "")
    if any(x in t for x in ["竖屏", "竖版", "9:16", "9：16"]):
        return "portrait"
    if any(x in t for x in ["横屏", "横版", "16:9", "16：9"]):
        return "landscape"
    if any(x in t for x in ["方形", "1:1", "1：1", "正方形"]):
        return "square"
    return None


def _parse_subtitle_mode(text: str) -> Optional[str]:
    t = str(text or "")
    if any(x in t for x in ["不要字幕", "关闭字幕", "取消字幕", "无字幕"]):
        return "off"
    if any(x in t for x in ["双语字幕", "中英字幕", "中英双语"]):
        return "both"
    if any(x in t.lower() for x in ["英文字幕", "english subtitle", "en字幕"]):
        return "en"
    if any(x in t for x in ["中文字幕", "加字幕", "开启字幕", "打开字幕", "显示字幕"]):
        return "zh"
    return None


def _parse_voice_style(text: str) -> Optional[str]:
    t = str(text or "")
    tl = t.lower()
    if any(x in tl for x in ["en_female", "english female", "英文女声"]):
        return "en_female"
    if any(x in tl for x in ["en_male", "english male", "英文男声"]):
        return "en_male"
    if any(x in t for x in ["新闻", "播报", "主持", "主播"]):
        return "news"
    if any(x in t for x in ["故事", "叙述", "旁白", "讲述"]):
        return "story"
    if any(x in t for x in ["亲和", "口语", "温柔", "甜", "软"]):
        return "friendly"
    if any(x in t for x in ["清脆", "清晰", "少女", "年轻女声"]):
        return "clear_female"
    if any(x in t for x in ["成熟男", "大叔", "低沉", "磁性男声"]):
        return "mature_male"
    if any(x in t for x in ["女声", "女生", "女配音", "女播", "女旁白"]):
        return "energetic"
    if any(x in t for x in ["男声", "男生", "男配音", "男播", "男旁白"]):
        return "calm"
    return None


def _parse_bgm_mood(text: str) -> Optional[str]:
    t = str(text or "")
    if any(x in t for x in ["无bgm", "无BGM", "不要bgm", "不要BGM", "关bgm", "关闭BGM", "不要背景音乐"]):
        return "none"
    if any(x in t for x in ["热门", "流行", "热歌", "爆款"]):
        return "hot"
    if any(x in t for x in ["欢快", "轻快", "活力", "元气"]):
        return "upbeat"
    if any(x in t for x in ["舒缓", "放松", "chill", "慵懒", "治愈"]):
        return "chill"
    if any(x in t for x in ["科技", "赛博", "未来"]):
        return "tech"
    if any(x in t for x in ["电影", "史诗", "大片", "震撼"]):
        return "cinematic"
    if any(x in t for x in ["严肃", "正式"]):
        return "serious"
    if any(x in t for x in ["lofi", "lo-fi", "学习", "工作"]):
        return "lofi"
    if any(x in t for x in ["氛围", "ambient"]):
        return "ambient"
    if any(x in t for x in ["钢琴"]):
        return "piano"
    if any(x in t for x in ["原声", "吉他"]):
        return "acoustic"
    if any(x in t for x in ["嘻哈", "hiphop", "hip-hop"]):
        return "hiphop"
    if any(x in t for x in ["电音", "edm", "电子"]):
        return "edm"
    if any(x in t for x in ["合成波", "synthwave"]):
        return "synthwave"
    if any(x in t for x in ["管弦", "交响", "orchestral"]):
        return "orchestral"
    if any(x in t for x in ["商务", "corporate"]):
        return "corporate"
    if any(x in t for x in ["爵士", "jazz"]):
        return "jazz"
    if any(x in t for x in ["摇滚", "rock"]):
        return "rock"
    return None


def parse_chat_commands(text: str) -> Dict[str, Any]:
    t = _norm(text)
    tl = t.lower()
    updates: Dict[str, Any] = {}
    post_updates: Dict[str, Any] = {}
    append_instructions: List[str] = []
    actions: List[str] = []
    ask_submit_status = False

    if any(x in t for x in ["为什么发不了", "发布不了", "无法发布", "不能发布", "发不出去", "提交失败"]):
        ask_submit_status = True

    voice = _parse_voice_style(t)
    if voice:
        updates["voice_style"] = voice
        actions.append("set_voice_style")

    bgm_mood = _parse_bgm_mood(t)
    if bgm_mood:
        updates["bgm_mood"] = bgm_mood
        actions.append("set_bgm_mood")

    if any(x in t for x in ["换bgm", "换BGM", "更换bgm", "更换BGM", "换首", "换一首", "换曲", "换音乐", "换背景音乐", "BGM曲目"]):
        after = _extract_after(t, ["bgm曲目", "BGM曲目", "bgm", "BGM", "背景音乐", "音乐"])
        if after and after.endswith(".mp3"):
            updates["bgm_id"] = after
            actions.append("set_bgm_id")

    sub = _parse_subtitle_mode(t)
    if sub:
        updates["subtitle_mode"] = sub
        actions.append("set_subtitle_mode")

    ori = _parse_cover_orientation(t)
    if ori:
        updates["cover_orientation"] = ori
        actions.append("set_cover_orientation")

    dur = _parse_duration_sec(t)
    if dur:
        updates["requested_duration_sec"] = dur
        actions.append("set_requested_duration_sec")

    new_title = _extract_after(t, ["标题", "改标题", "更改标题", "修改标题", "标题改成", "标题改为", "把标题改成", "把标题改为"])
    if new_title and len(new_title) <= 120:
        post_updates["title"] = new_title
        updates["title"] = new_title
        actions.append("set_title")

    new_cat = _extract_after(t, ["分类", "改分类", "更改分类", "修改分类", "分类改成", "分类改为", "把分类改成", "把分类改为"])
    if new_cat and len(new_cat) <= 64:
        post_updates["category"] = new_cat
        updates["category"] = new_cat
        actions.append("set_category")

    if any(x in t for x in ["附加指令", "额外要求", "补充要求", "追加要求", "补充一下", "再加一点"]):
        add = _extract_after(t, ["附加指令", "额外要求", "补充要求", "追加要求", "补充一下", "再加一点"])
        if add:
            append_instructions.append(add)
            actions.append("append_custom_instructions")

    if any(x in t for x in ["重跑", "重新跑", "重新生成", "重做", "再生成一次", "重新出一版"]):
        actions.append("rerun")

    if any(x in tl for x in ["/help", "help", "指令", "怎么用", "支持什么"]):
        actions.append("help")

    return {
        "updates": updates,
        "post_updates": post_updates,
        "append_instructions": append_instructions,
        "actions": actions,
        "ask_submit_status": ask_submit_status,
        "normalized": t,
    }


def build_ack_message(parsed: Dict[str, Any]) -> str:
    actions = list(parsed.get("actions") or [])
    updates = parsed.get("updates") or {}
    post_updates = parsed.get("post_updates") or {}
    append_instructions = parsed.get("append_instructions") or []
    normalized = str(parsed.get("normalized") or "")

    if "help" in actions and not updates and not post_updates and not append_instructions:
        return (
            "我可以直接把你的对话转换为可执行的修改指令。示例：\n"
            "- 换个女生配音 / 男声 / 新闻播报\n"
            "- BGM改成热门/欢快/舒缓/科技/电影感，或指定曲目（xxx.mp3）\n"
            "- 开启字幕/关闭字幕/中英字幕\n"
            "- 竖屏/横屏/方形，最长90秒/2分钟\n"
            "- 标题改为：...\n"
            "- 分类改为：...\n"
            "- 附加指令：...\n"
            "- 重跑/重新生成\n"
        )

    lines: List[str] = []
    if "set_voice_style" in actions:
        vs = str(updates.get("voice_style") or "")
        m = {
            "calm": "沉稳（男声）",
            "energetic": "热情（女声）",
            "news": "新闻播报（男声）",
            "story": "故事叙述（女声）",
            "friendly": "亲和口语（女声）",
            "mature_male": "成熟低沉（男声）",
            "clear_female": "清脆清晰（女声）",
            "en_female": "English·Female",
            "en_male": "English·Male",
        }.get(vs, vs)
        lines.append(f"已切换配音：{m}")

    if "set_bgm_mood" in actions:
        bm = str(updates.get("bgm_mood") or "")
        lines.append(f"已更新BGM氛围：{bm}")
    if "set_bgm_id" in actions:
        bid = str(updates.get("bgm_id") or "")
        lines.append(f"已指定BGM曲目：{bid}")

    if "set_subtitle_mode" in actions:
        sm = str(updates.get("subtitle_mode") or "")
        lines.append(f"已更新字幕：{sm}")

    if "set_cover_orientation" in actions:
        co = str(updates.get("cover_orientation") or "")
        lines.append(f"已更新封面比例：{co}")

    if "set_requested_duration_sec" in actions:
        d = int(updates.get("requested_duration_sec") or 0)
        lines.append(f"已更新最长时长：{d}秒")

    if "set_title" in actions and post_updates.get("title"):
        lines.append(f"已更新标题：{str(post_updates.get('title'))}")

    if "set_category" in actions and post_updates.get("category"):
        lines.append(f"已更新分类：{str(post_updates.get('category'))}")

    if "append_custom_instructions" in actions and append_instructions:
        lines.append("已添加附加指令")

    if "rerun" in actions:
        if any(x in normalized for x in ["封面", "cover", "封图"]):
            lines.append("好的，我已经准备好帮你重新做封面。你还有想调整的地方吗？确认后点“生成新版本/重跑”就能开始。")
        else:
            lines.append("好的，我可以帮你生成一个新版本来应用这些修改。你还有想调整的吗？确认后点“生成新版本/重跑”就能开始。")

    if not lines:
        return "好的，我记下了。我会把你的话整理成修改并应用到当前草稿。你还有想调整的吗？准备好后点“生成新版本”就能开始。"
    return "\n".join(lines)
