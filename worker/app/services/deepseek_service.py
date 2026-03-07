import json
import logging
import re
from app.core.config import settings, MAX_CONTENT_LENGTH
from app.core.utils import retry_sync

logger = logging.getLogger(__name__)

class DeepSeekService:
    def __init__(self):
        self.client = None
        try:
            key = str(getattr(settings, "deepseek_api_key", "") or "").strip()
            if not key:
                return
            try:
                from openai import OpenAI
            except Exception:
                self.client = None
                return
            self.client = OpenAI(api_key=key, base_url=settings.deepseek_base_url)
        except Exception:
            self.client = None

    def _fallback_video(self, content: str, custom_instructions: str = None) -> dict:
        raw = str(content or "").strip()
        if not raw:
            raw = "请根据用户输入生成一条知识类短视频口播稿。"
        title = (raw.splitlines()[0].strip() or "AI创作视频")[:40]
        summary = raw.replace("\n", " ").strip()[:80]
        if custom_instructions:
            summary = (summary + " " + str(custom_instructions).strip())[:120]
        parts = [p.strip() for p in raw.replace("。", "。\n").replace("！", "！\n").replace("？", "？\n").splitlines() if p.strip()]
        if not parts:
            parts = [summary]
        scenes = []
        for i, p in enumerate(parts[:8], start=1):
            scenes.append(
                {
                    "idx": i,
                    "duration_sec": 6,
                    "narration": p[:120],
                    "subtitle": p[:120],
                    "visual_prompt_en": "clean abstract background, tech style, simple icons",
                    "shot": "medium",
                    "transition": "cut",
                }
            )
        voice_text = "\n".join([s["narration"] for s in scenes]).strip()
        return {
            "title": title,
            "summary": summary,
            "production_script": {
                "scenes": scenes,
                "cover": {"visual_prompt_en": "abstract tech background, minimal", "title_text": title, "subtitle_text": ""},
                "music": {"mood": "tech", "tags": ["ambient", "soft"]},
            },
            "voice_text": voice_text,
            "subtitles": [{"text": s["subtitle"]} for s in scenes],
            "bgm_mood": "tech",
        }

    def _analyze_sync(self, content: str, post_type: str = "video", custom_instructions: str = None) -> dict:
        """Synchronous analysis logic to be wrapped in retry."""
        logger.info(f"Sending request to DeepSeek for {post_type}...")
        if not self.client:
            raise ValueError("deepseek_client_unavailable")
        
        # Base System Prompt
        if post_type == "image_text":
            system_prompt = (
                "你是一个社交媒体图文内容创作者。"
                "用户会给你一篇很长的文章，请你将其精简为一组适合手机滑动的图文卡片（Slide）。"
                "如果文字较短，生成1张；如果较长，生成多张（最多9张）。"
                "请用JSON格式严格返回，字段包括："
                "title（标题），summary（摘要），"
                "slides（数组，每项包含：text（卡片文案，精简有力），image_keyword（用于生成配图的英文关键词描述））。"
                "bgm_mood（字符串，如'cheerful', 'serious'）。"
                "只返回JSON。"
            )
        else:
            # Video Prompt
            system_prompt = (
                "你是一个中文知识类短视频脚本编剧。"
                "用户会给你一篇很长的文章，请你将其工程化为“可执行的创作脚本”，用于生成成品短视频。"
                "目标：一次性输出口播稿、分镜/编导版剧本、封面图方案、背景音乐方案。"
                "请用JSON格式严格返回，字段包括："
                "title（视频标题），summary（50字左右总结），"
                "production_script（对象，包含："
                "scenes（数组，每项包含：idx（从1开始），duration_sec（整数，建议3-12秒），narration（该段口播），subtitle（该段字幕），visual_prompt_en（用于生成/检索画面的英文描述），shot（镜头类型如 closeup/medium/wide），transition（转场如 cut/fade）），"
                "cover（对象：visual_prompt_en（封面英文描述），title_text（封面主标题），subtitle_text（封面副标题，可空）），"
                "music（对象：mood（背景音乐情绪，如'cheerful'|'serious'|'relaxing'|'tech'|'lofi'|'ambient'|'piano'|'acoustic'|'hiphop'|'edm'|'synthwave'|'orchestral'|'corporate'|'jazz'|'rock'），tags（数组，音乐标签，如'ambient','piano','trap'））"
                "），"
                "voice_text（完整口播文案，适合语音合成；如已提供 scenes，可为 scenes.narration 的拼接），"
                "subtitles（数组，每项包含 text 字段即可；可由 scenes.subtitle 汇总）。"
                "只返回JSON，不要包含任何额外说明。"
            )

        try:
            from app.prompts.studio_instruction_library import STUDIO_INSTRUCTION_LIBRARY_CN

            system_prompt = (system_prompt + "\n\n" + STUDIO_INSTRUCTION_LIBRARY_CN).strip()
        except Exception:
            pass
            
        # Append Custom Instructions if any
        if custom_instructions:
            system_prompt += f"\n\n用户额外要求：{custom_instructions}\n请务必在生成内容时遵守以上额外要求。"
        
        # Truncate content
        user_content = content[:MAX_CONTENT_LENGTH]
        
        response = self.client.chat.completions.create(
            model=settings.deepseek_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=2400
        )
        
        text = response.choices[0].message.content
        if not text:
            raise ValueError("Empty response from DeepSeek")

        def _try_parse(raw: str):
            try:
                return json.loads(raw)
            except Exception:
                pass
            s = str(raw or "")
            a = s.find("{")
            b = s.rfind("}")
            if a >= 0 and b > a:
                s2 = s[a : b + 1]
                s2 = re.sub(r",\\s*([}\\]])", r"\\1", s2)
                try:
                    return json.loads(s2)
                except Exception:
                    return None
            return None

        data = _try_parse(text)
        if data is None:
            if post_type == "image_text":
                return {"title": "AI图文", "summary": str(content or "")[:120], "slides": [{"text": str(content or "")[:200], "image_keyword": "abstract background"}], "bgm_mood": "neutral"}
            strict_prompt = (system_prompt + "\n\n输出必须是严格JSON，不要任何解释、不要多余字符、不要使用单引号。").strip()
            try:
                response2 = self.client.chat.completions.create(
                    model=settings.deepseek_model,
                    messages=[
                        {"role": "system", "content": strict_prompt},
                        {"role": "user", "content": user_content[:max(500, min(len(user_content), 5000))]},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.0,
                    max_tokens=2400,
                )
                text2 = response2.choices[0].message.content
                data = _try_parse(text2)
            except Exception:
                data = None
            if data is None:
                return self._fallback_video(content, custom_instructions=custom_instructions)
            
        # Validation
        if post_type == "video":
            ps = data.get("production_script") if isinstance(data, dict) else None
            if isinstance(ps, dict) and isinstance(ps.get("scenes"), list) and ps.get("scenes"):
                try:
                    scenes = [s for s in ps.get("scenes") if isinstance(s, dict)]
                    def _nrm(s: str) -> str:
                        t = str(s or "").lower()
                        t = re.sub(r"[\s，,。．.！!？?：:；;、】【\\[\\]（）()“”\"'‘’·`~@#$%^&*_+=|\\\\/<>]", "", t)
                        return t

                    for s in scenes:
                        nar = str(s.get("narration") or "").strip()
                        sub = str(s.get("subtitle") or "").strip()
                        if nar and (not sub or len(sub) < 2):
                            s["subtitle"] = nar
                            continue
                        if nar and sub:
                            a = _nrm(nar)
                            b = _nrm(sub)
                            if a and b:
                                inter = len(set(a) & set(b))
                                denom = max(1, min(len(a), len(b)))
                                sim = float(inter) / float(denom)
                                if sim < 0.55:
                                    s["subtitle"] = nar
                    if "voice_text" not in data or not str(data.get("voice_text") or "").strip():
                        data["voice_text"] = "\n".join([str(s.get("narration") or "").strip() for s in scenes if str(s.get("narration") or "").strip()]).strip()
                    if "subtitles" not in data or not isinstance(data.get("subtitles"), list):
                        data["subtitles"] = [{"text": str(s.get("subtitle") or "").strip()} for s in scenes if str(s.get("subtitle") or "").strip()]
                    if "bgm_mood" not in data:
                        music = ps.get("music") if isinstance(ps.get("music"), dict) else {}
                        m = (music.get("mood") if isinstance(music, dict) else None) or "neutral"
                        data["bgm_mood"] = m
                except Exception:
                    pass
            if "voice_text" not in data:
                if "summary" in data:
                    data["voice_text"] = data["summary"]
                else:
                    raise ValueError("Missing 'voice_text' in response")
                 
        if post_type == "image_text" and "slides" not in data:
            if "summary" in data:
                data["slides"] = [{"text": data["summary"], "image_keyword": "abstract background"}]
            else:
                raise ValueError("Missing 'slides' in response")
            
        return data

    async def analyze_text(self, content: str, post_type: str = "video", custom_instructions: str = None) -> dict:
        """
        Analyze text with retries.
        """
        logger.info(f"Analyzing text with DeepSeek (Async Wrapper)... Type: {post_type}")
        
        import asyncio
        loop = asyncio.get_event_loop()

        def run_with_retry():
            return retry_sync(lambda: self._analyze_sync(content, post_type, custom_instructions), max_retries=2)

        try:
            if str(getattr(settings, "deepseek_api_key", "") or "").strip():
                return await loop.run_in_executor(None, run_with_retry)
        except Exception:
            pass
        if str(post_type or "video") == "image_text":
            return {"title": "AI图文", "summary": str(content or "")[:120], "slides": [{"text": str(content or "")[:200], "image_keyword": "abstract background"}], "bgm_mood": "neutral"}
        return self._fallback_video(content, custom_instructions=custom_instructions)

    def _translate_subtitles_sync(self, subtitles: list[str], target_lang: str) -> list[str]:
        if not self.client:
            raise ValueError("deepseek_client_unavailable")
        subs = [str(s or "").strip() for s in (subtitles or []) if str(s or "").strip()]
        if not subs:
            return []
        tl = str(target_lang or "").strip().lower()
        if tl not in {"en", "zh"}:
            tl = "en"
        system_prompt = (
            "你是一个专业字幕翻译。"
            "把用户提供的一组字幕逐条翻译到目标语言，保持简洁、口语化、适合短视频字幕与口播。"
            "每条必须是完整句子/完整意思表达，不要只输出关键词或单词。"
            "不要添加额外解释，不要合并或拆分条目，输出严格 JSON。"
            "JSON 结构：{ \"subtitles\": [ {\"text\": \"...\"}, ... ] }。"
        )
        payload = {"target_lang": tl, "subtitles": [{"text": s} for s in subs]}
        response = self.client.chat.completions.create(
            model=settings.deepseek_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=1200,
        )
        text = response.choices[0].message.content
        if not text:
            raise ValueError("Empty response from DeepSeek")
        data = json.loads(text)
        arr = data.get("subtitles") if isinstance(data, dict) else None
        if not isinstance(arr, list):
            raise ValueError("translate_invalid_format")
        out: list[str] = []
        for it in arr:
            if isinstance(it, dict):
                out.append(str(it.get("text") or "").strip())
            else:
                out.append(str(it or "").strip())
        if len(out) != len(subs):
            out = (out + [""] * len(subs))[: len(subs)]
        return out

    async def translate_subtitles(self, subtitles: list[str], target_lang: str) -> list[str]:
        import asyncio

        loop = asyncio.get_event_loop()

        def run_with_retry():
            return retry_sync(lambda: self._translate_subtitles_sync(subtitles, target_lang), max_retries=2)

        try:
            if str(getattr(settings, "deepseek_api_key", "") or "").strip():
                return await loop.run_in_executor(None, run_with_retry)
        except Exception:
            return []
        return []

    def _refine_script_sync(
        self,
        content: str,
        post_type: str,
        custom_instructions: str,
        draft_json: dict,
        chat_messages: list,
    ) -> dict:
        system_prompt = (
            "你是一个中文短视频创作总监与编导。"
            "你会收到：原始文章、当前制作脚本production_script、用户的对话式修改要求。"
            "请在不偏离原文事实的前提下，给出一版更符合用户要求的production_script。"
            "输出必须是JSON，字段包括："
            "assistant_message（中文，给用户的简短建议/修改摘要，100-300字），"
            "production_script（对象，包含scenes/cover/music，结构与输入一致），"
            "apply_plan（对象，用于前端一键应用推荐改动，包含："
            "scene_idxs（数组，推荐应用的分镜idx），"
            "fields（数组，默认推荐应用字段，可选值：duration_sec,narration,subtitle,visual_prompt_en,title_text,mood），"
            "scene_fields（数组，每项包含 idx 与 fields，可选包含："
            "field_reasons（对象，key为字段名，value为中文理由，<=40字），"
            "reason（该分镜整体理由，<=60字），"
            "reason_tags（数组，1-3个短标签，用于解释推荐方向，例如：节奏/信息密度/口播顺滑/画面可生成性/风格一致）。"
            "；优先级高于 fields）。"
            "）。"
            "要求："
            "1) scenes必须为数组，idx从1开始，duration_sec为3-12秒的整数；"
            "2) 每个scene包含 narration/subtitle/visual_prompt_en；"
            "3) cover包含 title_text，music包含 mood；"
            "只返回JSON，不要包含任何额外说明。"
        )
        try:
            from app.prompts.studio_instruction_library import STUDIO_INSTRUCTION_LIBRARY_CN

            system_prompt = (system_prompt + "\n\n" + STUDIO_INSTRUCTION_LIBRARY_CN).strip()
        except Exception:
            pass
        payload = {
            "post_type": str(post_type or "video"),
            "content": str(content or "")[:MAX_CONTENT_LENGTH],
            "custom_instructions": str(custom_instructions or "").strip(),
            "production_script": draft_json or {},
            "chat_messages": [str(x) for x in (chat_messages or [])][-20:],
        }
        response = self.client.chat.completions.create(
            model=settings.deepseek_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            response_format={"type": "json_object"},
            temperature=0.6,
            max_tokens=2000,
        )
        text = response.choices[0].message.content
        if not text:
            raise ValueError("Empty response from DeepSeek")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON response: {e}")
        ps = data.get("production_script")
        if not isinstance(ps, dict):
            raise ValueError("Missing 'production_script' in response")
        msg = str(data.get("assistant_message") or "").strip()
        if not msg:
            msg = "已根据你的要求调整脚本，你可以在“脚本”里进一步微调后重做。"
        data["assistant_message"] = msg
        ap = data.get("apply_plan")
        if not isinstance(ap, dict):
            ap = {}
        try:
            si = ap.get("scene_idxs")
            if not isinstance(si, list):
                si = []
            si2 = []
            for x in si:
                try:
                    n = int(x)
                    if n > 0:
                        si2.append(n)
                except Exception:
                    pass
            ap["scene_idxs"] = si2[:200]
        except Exception:
            ap["scene_idxs"] = []
        try:
            fs = ap.get("fields")
            if not isinstance(fs, list):
                fs = []
            allow = {"duration_sec", "narration", "subtitle", "visual_prompt_en", "title_text", "mood"}
            fs2 = []
            for x in fs:
                s = str(x or "").strip()
                if s in allow:
                    fs2.append(s)
            ap["fields"] = fs2[:50]
        except Exception:
            ap["fields"] = []
        try:
            sf = ap.get("scene_fields")
            if not isinstance(sf, list):
                sf = []
            allow = {"duration_sec", "narration", "subtitle", "visual_prompt_en", "title_text", "mood"}
            out = []
            for it in sf[:200]:
                if not isinstance(it, dict):
                    continue
                try:
                    idx = int(it.get("idx"))
                except Exception:
                    continue
                if idx <= 0:
                    continue
                fs = it.get("fields")
                if not isinstance(fs, list):
                    fs = []
                fs2 = []
                for x in fs:
                    s = str(x or "").strip()
                    if s in allow:
                        fs2.append(s)
                rec = {"idx": idx, "fields": fs2[:50]}
                fr = it.get("field_reasons")
                if isinstance(fr, dict):
                    fr2 = {}
                    for k, v in fr.items():
                        kk = str(k or "").strip()
                        if kk in allow:
                            vv = str(v or "").strip()
                            if vv:
                                fr2[kk] = vv[:40]
                    if fr2:
                        rec["field_reasons"] = fr2
                rr = str(it.get("reason") or "").strip()
                if rr:
                    rec["reason"] = rr[:60]
                rt = it.get("reason_tags")
                if isinstance(rt, list):
                    tags = []
                    for x in rt:
                        s = str(x or "").strip()
                        if s:
                            tags.append(s[:10])
                    if tags:
                        rec["reason_tags"] = tags[:5]
                out.append(rec)
            ap["scene_fields"] = out
        except Exception:
            ap["scene_fields"] = []
        data["apply_plan"] = ap
        return data

    async def refine_script(
        self,
        content: str,
        post_type: str = "video",
        custom_instructions: str = None,
        draft_json: dict = None,
        chat_messages: list = None,
    ) -> dict:
        import asyncio

        loop = asyncio.get_event_loop()

        def run_with_retry():
            return retry_sync(
                lambda: self._refine_script_sync(content, post_type, custom_instructions, draft_json or {}, chat_messages or []),
                max_retries=3,
            )

        return await loop.run_in_executor(None, run_with_retry)

# Singleton
deepseek_service = DeepSeekService()
