import asyncio
import logging
import time
import os
import uuid
import math
import requests
import redis
from pathlib import Path
from typing import List, Optional
from app.core.queue import job_queue
from app.core.database import db
from app.core.logger import JobLogger, get_logger
from app.core.config import settings, OUTPUTS_DIR, MAX_QUEUE_SIZE
from app.core.utils import retry_async
from app.services.deepseek_service import deepseek_service
from app.services.tts_service import tts_service
from app.services.video_service import video_service
from app.services.storage_service import storage_service
from app.services.browser_service import browser_service
from app.services.bgm_service import bgm_service
from app.services.subtitle_service import build_vtt
from app.services.subtitle_service import build_vtt
from app.services.background_service import build_background_for_job
from app.services.cover_service import CoverService, build_cover_plan
from app.services.subtitle_service import build_vtt_from_cues
from app.worker_callback import callback_web, cleanup_job_files

logger = get_logger(__name__)
cover_service = CoverService()

_redis_client = None


def _get_redis():
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    try:
        url = os.getenv("REDIS_URL") or os.getenv("CELERY_BROKER_URL") or "redis://localhost:6379/0"
        r = redis.Redis.from_url(url, decode_responses=True, socket_timeout=0.4, socket_connect_timeout=0.2)
        r.ping()
        _redis_client = r
    except Exception:
        _redis_client = False
    return _redis_client


def _is_cancelled(job_id: str) -> bool:
    r = _get_redis()
    if not r:
        return False
    try:
        return bool(r.get(f"ai:cancel:{str(job_id)}"))
    except Exception:
        return False


async def process_job(job_data: dict):
    job_id = job_data.get("job_id")
    user_id = job_data.get("user_id")
    content = job_data.get("content")
    post_type = job_data.get("post_type", "video")
    custom_instructions = job_data.get("custom_instructions")
    voice_style = job_data.get("voice_style")
    bgm_mood_override = job_data.get("bgm_mood")
    post_id = job_data.get("post_id")
    draft_in = job_data.get("draft_json")

    # Initialize variables early to avoid UnboundLocalError in finally block
    voice_path = None
    video_path = None
    video_url = None
    image_paths = []
    uploaded_images = []
    bg_tmp_files = []
    subtitle_files = []
    subtitle_zh_segments = []
    subtitle_times = []
    subtitle_en_segments = []
    cover_image_path = None
    cover_trace = None
    cover_audit = None

    job_logger = JobLogger(logger, job_id)
    job_logger.start(queue_size=job_queue.get_status(job_id))

    db.update_job(job_id, status="processing")

    try:
        await callback_web(job_data, status="processing", stage="start", progress=1, stage_message="任务开始")
        if _is_cancelled(job_id):
            await callback_web(job_data, status="cancelled", stage="cancelled", progress=1, stage_message="用户取消")
            return
        analysis = None
        if isinstance(draft_in, dict) and draft_in:
            ps = draft_in
            scenes = ps.get("scenes") if isinstance(ps.get("scenes"), list) else []
            voice_text = "\n".join([str(s.get("narration") or "").strip() for s in scenes if isinstance(s, dict) and str(s.get("narration") or "").strip()]).strip()
            subs = [{"text": str(s.get("subtitle") or "").strip()} for s in scenes if isinstance(s, dict) and str(s.get("subtitle") or "").strip()]
            music = ps.get("music") if isinstance(ps.get("music"), dict) else {}
            cover = ps.get("cover") if isinstance(ps.get("cover"), dict) else {}
            title2 = str(cover.get("title_text") or "") or "Untitled"
            analysis = {
                "title": title2,
                "summary": "",
                "production_script": ps,
                "voice_text": voice_text or "",
                "subtitles": subs,
                "bgm_mood": str(music.get("mood") or "neutral"),
            }
            await callback_web(job_data | {"title": title2, "summary": ""}, status="processing", stage="draft_loaded", progress=10, stage_message="已加载脚本", draft_json=ps)
        else:
            job_logger.info(f"Starting DeepSeek analysis for {post_type}...")
            want_sec = 0
            try:
                want_sec = int(job_data.get("target_sec") or 0)
            except Exception:
                want_sec = 0
            try:
                req = int(job_data.get("requested_duration_sec") or 0)
                if req > 0:
                    want_sec = max(want_sec, req)
            except Exception:
                pass
            if want_sec < 0:
                want_sec = 0
            if want_sec > 3600:
                want_sec = 3600

            raw_text = str(content or "").strip()

            def _split_chunks(txt: str, max_len: int) -> list[str]:
                t = str(txt or "").strip()
                if not t:
                    return []
                parts = [p.strip() for p in t.replace("\r", "\n").split("\n") if p.strip()]
                if not parts:
                    parts = [t]
                out = []
                buf = ""
                for p in parts:
                    if not buf:
                        buf = p
                        continue
                    if len(buf) + 1 + len(p) <= max_len:
                        buf = buf + "\n" + p
                    else:
                        out.append(buf)
                        buf = p
                if buf:
                    out.append(buf)
                return out

            chunks = _split_chunks(raw_text, 5200)
            need_parts = 1
            if want_sec >= 180 and len(raw_text) >= 2600:
                need_parts = int(min(8, max(2, math.ceil(float(want_sec) / 120.0))))
            if need_parts > 1 and len(chunks) > 1:
                chunks = chunks[:need_parts]
                per_sec = int(max(60, min(600, round(float(want_sec) / float(len(chunks) or 1)))))
                merged = None
                idx_off = 0
                all_scenes = []
                all_subs = []
                all_voice = []
                for i, ch in enumerate(chunks, start=1):
                    ci = str(custom_instructions or "").strip()
                    sys_line = f"系统参数：本段目标时长约{per_sec}秒；本段编号{i}/{len(chunks)}；总目标时长上限{want_sec}秒。"
                    ci = (ci + ("\n\n" if ci else "") + sys_line).strip()
                    ai = await deepseek_service.analyze_text(ch, post_type, ci)
                    if not isinstance(ai, dict):
                        continue
                    if merged is None:
                        merged = ai
                    ps = ai.get("production_script") if isinstance(ai.get("production_script"), dict) else {}
                    scenes = ps.get("scenes") if isinstance(ps.get("scenes"), list) else []
                    for s in scenes:
                        if not isinstance(s, dict):
                            continue
                        try:
                            s2 = dict(s)
                            s2["idx"] = int(s2.get("idx") or 0) + idx_off
                            all_scenes.append(s2)
                        except Exception:
                            continue
                    idx_off = len(all_scenes)
                    subs = ai.get("subtitles") if isinstance(ai.get("subtitles"), list) else []
                    for it in subs:
                        if isinstance(it, dict):
                            t = str(it.get("text") or "").strip()
                        else:
                            t = str(it or "").strip()
                        if t:
                            all_subs.append({"text": t})
                    vt = str(ai.get("voice_text") or "").strip()
                    if vt:
                        all_voice.append(vt)
                if merged is None:
                    analysis = await deepseek_service.analyze_text(content, post_type, custom_instructions)
                else:
                    title_m = str(merged.get("title") or "Untitled")
                    summary_m = str(merged.get("summary") or "")
                    cover = {}
                    music = {}
                    try:
                        ps0 = merged.get("production_script") if isinstance(merged.get("production_script"), dict) else {}
                        cover = ps0.get("cover") if isinstance(ps0.get("cover"), dict) else {}
                        music = ps0.get("music") if isinstance(ps0.get("music"), dict) else {}
                    except Exception:
                        cover = {}
                        music = {}
                    analysis = {
                        "title": title_m,
                        "summary": summary_m,
                        "production_script": {"scenes": all_scenes, "cover": cover, "music": music},
                        "voice_text": "\n".join(all_voice).strip(),
                        "subtitles": all_subs,
                        "bgm_mood": str(music.get("mood") or "neutral"),
                    }
            else:
                analysis = await deepseek_service.analyze_text(content, post_type, custom_instructions)
        title = analysis.get("title", "Untitled")
        summary = analysis.get("summary", "")

        # IMPORTANT: If analysis provides refined voice_text (from DeepSeek's production_script), use it!
        # Do not overwrite it with raw content unless it's missing.
        # This fixes the issue where TTS reads raw content instead of refined script.
        
        db.update_job(job_id, title=title, summary=summary)
        job_logger.processing(step="deepseek_analyzed", title=title)
        draft = None
        try:
            if isinstance(analysis, dict) and isinstance(analysis.get("production_script"), dict):
                draft = analysis.get("production_script")
        except Exception:
            draft = None

        try:
            scenes0 = draft.get("scenes") if isinstance(draft, dict) else None
            if isinstance(scenes0, list) and scenes0:
                segs = []
                for s in scenes0:
                    if not isinstance(s, dict):
                        continue
                    nar = str(s.get("narration") or "").strip()
                    if nar:
                        segs.append(nar)
                        try:
                            s["subtitle"] = nar
                        except Exception:
                            pass
                subtitle_zh_segments = segs[:400]
                if subtitle_zh_segments:
                    # Force split large segments even if from production script
                    import re
                    fixed_segments = []
                    for seg in subtitle_zh_segments:
                        if len(seg) > 50:
                            parts = re.split(r'([。！？；!?;])', seg)
                            buf = ""
                            for p in parts:
                                if p in "。！？；!?;":
                                    buf += p
                                    if buf.strip():
                                        fixed_segments.append(buf.strip())
                                    buf = ""
                                else:
                                    if len(buf) + len(p) > 50:
                                         if buf.strip():
                                             fixed_segments.append(buf.strip())
                                         buf = p
                                    else:
                                         buf += p
                            if buf.strip():
                                fixed_segments.append(buf.strip())
                        else:
                            fixed_segments.append(seg)
                    subtitle_zh_segments = fixed_segments
                    analysis["subtitles"] = [{"text": x} for x in subtitle_zh_segments]
                    analysis["voice_text"] = "\n".join(subtitle_zh_segments).strip()
        except Exception:
            pass
        await callback_web(
            job_data | {"title": title, "summary": summary},
            status="processing",
            stage="deepseek",
            progress=15,
            stage_message="文稿解析完成",
            draft_json=draft,
        )
        if _is_cancelled(job_id):
            await callback_web(job_data, status="cancelled", stage="cancelled", progress=15, stage_message="用户取消")
            return

        if post_type == "image_text":
            slides = analysis.get("slides", [])
            job_logger.processing(step="generating_slides")
            await callback_web(job_data | {"title": title, "summary": summary}, status="processing", stage="generating_slides", progress=30, stage_message="生成图文页...")

            for idx, slide in enumerate(slides):
                if _is_cancelled(job_id):
                    await callback_web(job_data, status="cancelled", stage="cancelled", progress=30, stage_message="用户取消")
                    return
                keyword = slide.get("image_keyword", "AI")
                img_path = await browser_service.generate_image(keyword, f"{job_id}_{idx}")
                image_paths.append(img_path)
                object_name = f"images/{job_id}/{idx}.png"
                url = storage_service.upload_file(img_path, object_name, content_type="image/png")
                uploaded_images.append(url)

            await callback_web(
                job_data | {"title": title, "summary": summary},
                status="done",
                stage="done",
                progress=100,
                stage_message="图文生成完成",
                post_type="image_text",
                images=uploaded_images,
            )
            return

        # Use refined voice_text if available, fallback to summary, then raw content
        voice_text = analysis.get("voice_text")
        if not voice_text:
             voice_text = analysis.get("summary")
             
        voice_text = str(voice_text or "").strip()
        if not voice_text:
            # Only fallback to raw content if absolutely nothing came back from analysis
            voice_text = str(content or "").strip()[:600] or "AI生成短视频。"
            
        # Ensure voice_text is not a giant blob
        if len(voice_text) > 100 and "\n" not in voice_text:
             import re
             # Split by punctuation
             parts = re.split(r'([。！？；!?;])', voice_text)
             buf = ""
             lines = []
             for p in parts:
                 if p in "。！？；!?;":
                     buf += p
                     if buf.strip():
                         lines.append(buf.strip())
                     buf = ""
                 else:
                     if len(buf) + len(p) > 60:
                          if buf.strip():
                              lines.append(buf.strip())
                          buf = p
                     else:
                          buf += p
             if buf.strip():
                 lines.append(buf.strip())
             if lines:
                 voice_text = "\n".join(lines)
            
        if not subtitle_zh_segments:
            # If no subtitles from analysis, split voice_text by lines
            raw_lines = [str(x).strip() for x in str(voice_text or "").splitlines() if str(x).strip()]
            subtitle_zh_segments = []
            import re
            for line in raw_lines:
                # Split by punctuation to avoid huge subtitles
                parts = re.split(r'([。！？；!?;])', line)
                buf = ""
                for p in parts:
                    if p in "。！？；!?;":
                        buf += p
                        if buf.strip():
                            subtitle_zh_segments.append(buf.strip())
                        buf = ""
                    else:
                        if len(buf) + len(p) > 50: # Force split if too long
                             if buf.strip():
                                 subtitle_zh_segments.append(buf.strip())
                             buf = p
                        else:
                             buf += p
                if buf.strip():
                    subtitle_zh_segments.append(buf.strip())
        try:
            import re

            def _split_sentences(s: str) -> list[str]:
                t = str(s or "").replace("\r", "\n").strip()
                if not t:
                    return []
                t = re.sub(r"[ \t]+", " ", t)
                parts = []
                for line in [x.strip() for x in t.split("\n") if x.strip()]:
                    buf = ""
                    for ch in line:
                        buf += ch
                        if ch in "。！？；!?;":
                            if buf.strip():
                                parts.append(buf.strip())
                            buf = ""
                    if buf.strip():
                        parts.append(buf.strip())
                out = [p for p in [x.strip() for x in parts] if p]
                return out

            sent = []
            for seg in [str(x or "").strip() for x in subtitle_zh_segments if str(x or "").strip()]:
                sent.extend(_split_sentences(seg) or [])
            sent = [x for x in sent if x]
            if sent:
                subtitle_zh_segments = sent[:260]
                voice_text = "\n".join(subtitle_zh_segments).strip()
        except Exception:
            pass
        job_logger.processing(step="tts_generating")
        await callback_web(job_data | {"title": title, "summary": summary}, status="processing", stage="tts", progress=30, stage_message="生成配音...")
        mode0 = ""
        try:
            mode0 = str(job_data.get("subtitle_mode") or "zh").strip().lower()
        except Exception:
            mode0 = "zh"
        vs0 = str(voice_style or "").strip().lower()
        is_en_voice = bool(vs0) and (vs0.startswith("en_") or "english" in vs0)
        need_en = is_en_voice or (mode0 in {"en", "both", "bilingual", "zh-en"})
        if need_en and subtitle_zh_segments:
            try:
                subtitle_en_segments = await deepseek_service.translate_subtitles(subtitle_zh_segments, "en")
                subtitle_en_segments = [str(x or "").strip() for x in (subtitle_en_segments or [])]
                if len(subtitle_en_segments) != len(subtitle_zh_segments):
                    subtitle_en_segments = (subtitle_en_segments + [""] * len(subtitle_zh_segments))[: len(subtitle_zh_segments)]
                if any(not s for s in subtitle_en_segments):
                    fixed = []
                    for zh, en in zip(subtitle_zh_segments, subtitle_en_segments):
                        if en:
                            fixed.append(en)
                            continue
                        one = await deepseek_service.translate_subtitles([zh], "en")
                        fixed.append(str((one or [""])[0] or "").strip())
                    subtitle_en_segments = fixed
            except Exception:
                subtitle_en_segments = []
        speech_segments = subtitle_en_segments if (is_en_voice and subtitle_en_segments and len(subtitle_en_segments) == len(subtitle_zh_segments)) else subtitle_zh_segments
        voice_path, subtitle_times = await tts_service.generate_speech_segments(speech_segments, job_id, voice_style=voice_style)
        if not voice_path:
            voice_path = await tts_service.generate_speech(voice_text, job_id, voice_style=voice_style)
        await callback_web(job_data | {"title": title, "summary": summary}, status="processing", stage="tts_done", progress=45, stage_message="配音完成")


        if _is_cancelled(job_id):
            await callback_web(job_data, status="cancelled", stage="cancelled", progress=45, stage_message="用户取消")
            return

        bgm_mood = bgm_mood_override or analysis.get("bgm_mood", "neutral")
        bgm_id = job_data.get("bgm_id") if isinstance(job_data, dict) else None
        bgm_path = bgm_service.get_bgm(bgm_mood, bgm_id=bgm_id)
        bg_keywords = [str(title or "").strip()]
        bg_visuals = []
        bg_scene_durs = []
        try:
            if isinstance(draft, dict) and isinstance(draft.get("scenes"), list):
                for s in [x for x in draft.get("scenes") if isinstance(x, dict)][:2]:
                    vp = str(s.get("visual_prompt_en") or "").strip()
                    if vp:
                        bg_keywords.append(vp)
                        bg_visuals.append(vp)
                for s in [x for x in draft.get("scenes") if isinstance(x, dict)][:12]:
                    try:
                        bg_scene_durs.append(int(s.get("duration_sec") or 0))
                    except Exception:
                        continue
        except Exception:
            pass
        want_sec = 0
        try:
            want_sec = int(job_data.get("target_sec") or 0)
        except Exception:
            want_sec = 0
        try:
            req = int(job_data.get("requested_duration_sec") or 0)
            if req > 0:
                want_sec = max(want_sec, req)
        except Exception:
            pass
        if want_sec <= 0:
            try:
                want_sec = int(sum([d for d in bg_scene_durs if int(d) > 0]) or 0)
            except Exception:
                want_sec = 0
        if want_sec <= 0:
            want_sec = 30

        try:
            plan = build_cover_plan(
                analysis,
                fallback_title=str(title or ""),
                fallback_summary=str(summary or ""),
                orientation=str(job_data.get("cover_orientation") or "portrait"),
            )
            cres = cover_service.generate_cover_image(str(job_id), plan)
            if cres.ok and cres.image_path and os.path.exists(str(cres.image_path)):
                cover_image_path = str(cres.image_path)
                cover_trace = cres.trace
                cover_audit = {"provider": cres.provider, "embedded": True, "type": "generated"}
                logger.info(f"cover_generated job_id={job_id} provider={cres.provider} path={cover_image_path}")
            else:
                logger.warning(f"cover_generation_failed_but_no_exception job_id={job_id} trace={cres.trace}")
                cover_trace = cres.trace
        except Exception as e:
            logger.warning(f"cover_generate_failed job_id={job_id}: {e}")

        bg_path = None
        bg_trace = None
        bg_audit = None
        try:
            bg_path, bg_files, bg_trace, bg_audit = await build_background_for_job(
                job_id=str(job_id),
                user_id=int(job_data.get("user_id") or 0),
                title=str(title or ""),
                content=str(content or ""),
                visual_prompts_en=bg_visuals or bg_keywords[1:],
                scene_durations=bg_scene_durs,
                target_sec=want_sec,
                orientation=str(job_data.get("cover_orientation") or "portrait"),
            )
            if bg_files:
                bg_tmp_files.extend(bg_files)
            if bg_trace:
                logger.info(f"bg_api_trace job_id={job_id}: {str(bg_trace)[-800:]}")
        except Exception as e:
            logger.warning(f"bg_api_failed job_id={job_id}: {e}")

        job_logger.processing(step="video_creating")
        await callback_web(job_data | {"title": title, "summary": summary}, status="processing", stage="video", progress=55, stage_message="合成视频...")
        use_storyboard = False
        scenes = []
        try:
            if isinstance(draft, dict) and isinstance(draft.get("scenes"), list):
                scenes = [s for s in draft.get("scenes") if isinstance(s, dict)]
        except Exception:
            scenes = []
        try:
            for s in scenes:
                p = str(s.get("image_path") or "").strip()
                if p and os.path.exists(p):
                    use_storyboard = True
                    break
        except Exception:
            use_storyboard = False
        if use_storyboard:
            video_path = video_service.create_storyboard_video(
                job_id,
                voice_path,
                scenes,
                bgm_path=bgm_path,
                cover_image_path=cover_image_path,
                cover_orientation=str(job_data.get("cover_orientation") or "portrait"),
            )
        else:
            video_path = video_service.create_video(
                job_id,
                voice_path,
                title,
                bgm_path=bgm_path,
                bg_keywords=bg_keywords,
                bg_path=bg_path,
                cover_image_path=cover_image_path,
                cover_orientation=str(job_data.get("cover_orientation") or "portrait"),
            )

        if _is_cancelled(job_id):
            await callback_web(job_data, status="cancelled", stage="cancelled", progress=55, stage_message="用户取消")
            return

        job_logger.processing(step="uploading_video")
        await callback_web(job_data | {"title": title, "summary": summary}, status="processing", stage="uploading", progress=70, stage_message="上传视频...")
        object_name = f"videos/{job_id}/{uuid.uuid4()}.mp4"
        mp4_url = storage_service.upload_file(video_path, object_name, content_type="video/mp4")
        video_url = mp4_url

        meta = video_service.probe_video_meta(video_path)
        duration = int((meta or {}).get("duration") or 0)
        video_width = int((meta or {}).get("width") or 0)
        video_height = int((meta or {}).get("height") or 0)

        cover_dir = None
        cover_url = None
        try:
            cov = None
            # Prioritize AI generated cover if available
            if cover_image_path and os.path.exists(str(cover_image_path)):
                try:
                    p = Path(str(cover_image_path))
                    cov = {
                        "dir": str(p.parent),
                        "webp": str(p) if p.suffix.lower() == ".webp" else None,
                        "jpg": str(p) if p.suffix.lower() in {".jpg", ".jpeg"} else None,
                        "png": str(p) if p.suffix.lower() == ".png" else None,
                    }
                    # Explicitly mark as AI generated to prevent overwrite
                    logger.info(f"Using AI generated cover: {cover_image_path}")
                except Exception:
                    cov = None
            
            # Only fallback to video snapshot if NO AI cover exists
            if not cov:
                logger.info("No AI cover found, falling back to video snapshot...")
                cov = video_service.generate_cover(job_id, video_path, orientation=str(job_data.get("cover_orientation") or "portrait"))
            
            cover_dir = str((cov or {}).get("dir") or "").strip() or None
            cover_path = str((cov or {}).get("webp") or (cov or {}).get("jpg") or (cov or {}).get("png") or "").strip()
            
            if cover_path and os.path.exists(cover_path):
                ct = "image/webp" if cover_path.lower().endswith(".webp") else "image/png" if cover_path.lower().endswith(".png") else "image/jpeg"
                ext = ".webp" if ct == "image/webp" else ".png" if ct == "image/png" else ".jpg"
                cover_url = storage_service.upload_file(cover_path, f"covers/{job_id}/{uuid.uuid4()}{ext}", content_type=ct, cache_control="public, max-age=31536000")
                logger.info(f"Cover uploaded successfully: {cover_url}")
        except Exception as e:
            logger.error(f"Cover generation/upload failed: {e}")
            cover_url = None

        hls_root = None
        hls_url = None
        try:
            logger.info(f"Starting HLS packaging for job {job_id}")
            master = video_service.package_hls(job_id, video_path)
            if master and os.path.exists(master):
                hls_root = str(Path(master).parent)
                logger.info(f"HLS package created at {hls_root}, uploading...")
                hls_url = storage_service.upload_directory(hls_root, f"hls/{job_id}/{uuid.uuid4()}")
                logger.info(f"HLS uploaded successfully: {hls_url}")
            else:
                logger.error(f"HLS master file not found at {master}")
        except Exception as e:
            logger.error(f"HLS packaging failed: {e}")
            hls_url = None
        if hls_url:
            video_url = hls_url

        ver = str(int(time.time()))

        subtitle_tracks = []
        subtitle_files = []
        try:
            mode = str(job_data.get("subtitle_mode") or "zh").strip().lower()
        except Exception:
            mode = "zh"
        try:
            if mode not in {"off", "none", "no"}:
                zh_segments = []
                if subtitle_zh_segments:
                    zh_segments = [str(x).strip() for x in subtitle_zh_segments if str(x).strip()]
                else:
                    zh_segments = [str(x).strip() for x in str(voice_text or "").splitlines() if str(x).strip()]

                en_segments = []
                if (mode in {"en", "both", "bilingual", "zh-en"} or is_en_voice) and zh_segments:
                    if subtitle_en_segments and len(subtitle_en_segments) == len(zh_segments):
                        en_segments = [str(x or "").strip() for x in subtitle_en_segments]
                    else:
                        en_segments = await deepseek_service.translate_subtitles(zh_segments, "en")
                        en_segments = [str(x or "").strip() for x in (en_segments or [])]
                        if len(en_segments) != len(zh_segments):
                            en_segments = (en_segments + [""] * len(zh_segments))[: len(zh_segments)]

                vtt_specs = []
                if mode in {"zh", "both"} and zh_segments:
                    vtt_specs.append(("zh", "中文字幕", zh_segments, True))
                if mode in {"en", "both"} and en_segments:
                    vtt_specs.append(("en", "English", en_segments, mode == "en"))
                if mode in {"bilingual", "both", "zh-en"} and en_segments:
                    bi = []
                    for a, b in zip(zh_segments, en_segments):
                        bi.append((str(a).strip() + "\n" + str(b).strip()).strip())
                    vtt_specs.append(("zh-en", "中英双语", bi, mode in {"bilingual", "zh-en"}))

                t_off = 0.0
                try:
                    if str(video_path or "").endswith(".main.mp4"):
                        t_off = 0.0
                    else:
                        t_off = float(getattr(settings, "cover_embed_duration_sec", 1.0) or 1.0)
                        if t_off < 0:
                            t_off = 0.0
                        if t_off > 5.0:
                            t_off = 5.0
                except Exception:
                    t_off = 0.0

                for lang, label, segs, is_default in vtt_specs:
                    vtt_text = None
                    try:
                        base_len = 0
                        if is_en_voice and en_segments and len(en_segments) == len(zh_segments):
                            base_len = len(en_segments)
                        else:
                            base_len = len(zh_segments)
                        if subtitle_times and len(subtitle_times) == base_len and len(segs) == len(zh_segments):
                            cues = []
                            for (st, ed), txt in zip(subtitle_times, segs):
                                cues.append((float(st) + t_off, float(ed) + t_off, str(txt)))
                            vtt_text = build_vtt_from_cues(cues, max_chars_per_line=18 if lang != "zh-en" else 80)
                    except Exception:
                        vtt_text = None
                    if not vtt_text:
                        vtt_text = build_vtt(segs, float(duration or 0))
                    out_path = str(OUTPUTS_DIR / f"{job_id}_{lang}.vtt")
                    with open(out_path, "w", encoding="utf-8") as f:
                        f.write(vtt_text)
                    subtitle_files.append(out_path)
                    object_name = f"subtitles/{job_id}/{uuid.uuid4()}.{lang}.vtt"
                    url = storage_service.upload_file(out_path, object_name, content_type="text/vtt", cache_control="public, max-age=31536000")
                    subtitle_tracks.append({"lang": lang, "label": label, "format": "vtt", "url": url, "kind": "subtitles", "is_default": bool(is_default)})
        except Exception as e:
            logger.warning(f"subtitle_generation_failed job_id={job_id}: {e}")
            subtitle_tracks = []

        await callback_web(
            job_data | {"title": title, "summary": summary},
            status="done",
            stage="done",
            progress=100,
            stage_message="生成完成",
            hls_url=hls_url,
            mp4_url=mp4_url,
            cover_url=cover_url,
            duration=duration,
            video_width=video_width,
            video_height=video_height,
            media_version=ver,
            subtitle_tracks=subtitle_tracks,
            placeholder_trace=bg_trace if isinstance(bg_trace, list) else None,
            placeholder_audit=bg_audit if isinstance(bg_audit, dict) else None,
            cover_trace=cover_trace if isinstance(cover_trace, list) else None,
            cover_audit=cover_audit if isinstance(cover_audit, dict) else None,
        )

    except Exception as e:
        error_msg = str(e)
        job_logger.error_occurred(e)
        db.update_job(job_id, status="error", error=error_msg)
        await callback_web(job_data, error=error_msg, status="failed", stage="failed", progress=100, stage_message="生成失败")

    finally:
        try:
            if "cover_dir" in locals() and cover_dir:
                cleanup_job_files(job_id, str(cover_dir))
        except Exception:
            pass
        try:
            if "hls_root" in locals() and hls_root:
                cleanup_job_files(job_id, str(hls_root))
        except Exception:
            pass
        cleanup_job_files(job_id, voice_path, video_path, *image_paths, *subtitle_files, *bg_tmp_files)


async def refine_script_job(job_data: dict):
    job_id = job_data.get("job_id")
    content = job_data.get("content")
    post_type = job_data.get("post_type", "video")
    custom_instructions = job_data.get("custom_instructions")
    draft_in = job_data.get("draft_json")
    chat_messages = job_data.get("chat_messages") or []
    if not isinstance(chat_messages, list):
        chat_messages = []
    if not isinstance(draft_in, dict):
        draft_in = {}

    job_logger = JobLogger(logger, job_id)
    job_logger.start(queue_size=job_queue.get_status(job_id))
    try:
        await callback_web(job_data, status="processing", stage="chat_ai", progress=5, stage_message="AI正在生成建议", no_post_status=True)
        if _is_cancelled(str(job_id)):
            await callback_web(job_data, status="cancelled", stage="cancelled", progress=5, stage_message="用户取消", no_post_status=True)
            return
        out = await deepseek_service.refine_script(content, post_type, custom_instructions, draft_in, chat_messages)
        ps = out.get("production_script") if isinstance(out, dict) else None
        msg = str(out.get("assistant_message") or "").strip() if isinstance(out, dict) else ""
        if not isinstance(ps, dict):
            raise ValueError("missing_production_script")
        try:
            ap = out.get("apply_plan") if isinstance(out, dict) else None
            if isinstance(ap, dict):
                meta = ps.get("_meta") if isinstance(ps.get("_meta"), dict) else {}
                meta2 = dict(meta)
                meta2["apply_plan"] = ap
                ps["_meta"] = meta2
        except Exception:
            pass
        await callback_web(
            job_data,
            status="done",
            stage="chat_ai_done",
            progress=100,
            stage_message="建议已生成",
            draft_json=ps,
            assistant_message=msg,
            no_post_status=True,
        )
    except Exception as e:
        await callback_web(job_data, status="failed", stage="chat_ai_failed", progress=100, stage_message="建议生成失败", error=str(e), no_post_status=True)


async def generate_cover_only_job(job_data: dict):
    job_id = str(job_data.get("job_id") or "").strip()
    if not job_id:
        return
    post_id = job_data.get("post_id")
    user_id = job_data.get("user_id")
    title = str(job_data.get("title") or "").strip()
    summary = str(job_data.get("summary") or "").strip()
    cover_orientation = str(job_data.get("cover_orientation") or "portrait")
    mp4_url = str(job_data.get("mp4_url") or "").strip()
    hls_url = str(job_data.get("hls_url") or "").strip()
    video_inp = mp4_url or hls_url
    try:
        if video_inp and str(video_inp).startswith("/static/"):
            repo_root = Path(__file__).resolve().parents[3]
            st_root = repo_root / "backend" / "static"
            cand = st_root / str(video_inp)[len("/static/") :]
            if cand.exists():
                video_inp = str(cand)
            else:
                base = str(getattr(settings, "web_url", "") or "").rstrip("/")
                if base:
                    video_inp = base + str(video_inp)
    except Exception:
        pass

    cover_trace = None
    cover_audit = None
    cover_image_path = None
    try:
        plan = build_cover_plan({}, fallback_title=title, fallback_summary=summary, orientation=cover_orientation)
        cres = cover_service.generate_cover_image(str(job_id), plan)
        cover_trace = cres.trace
        if cres.ok and cres.image_path and os.path.exists(str(cres.image_path)):
            cover_image_path = str(cres.image_path)
            cover_audit = {"provider": cres.provider, "embedded": False, "type": "generated"}
    except Exception as e:
        logger.warning(f"cover_only_generate_failed job_id={job_id}: {e}")

    try:
        if not cover_image_path and video_inp:
            cov = video_service.generate_cover(str(job_id), str(video_inp), orientation=cover_orientation)
            cover_trace = [{"t": "frame_fallback", "ok": True, "src": str(video_inp)[:200]}]
            cover_audit = {"provider": "frame", "embedded": False, "type": "snapshot"}
            cover_image_path = str((cov or {}).get("webp") or (cov or {}).get("jpg") or "").strip() or None
    except Exception:
        cover_image_path = None

    cover_url = None
    try:
        if cover_image_path and os.path.exists(str(cover_image_path)):
            ct = "image/webp" if str(cover_image_path).lower().endswith(".webp") else "image/png" if str(cover_image_path).lower().endswith(".png") else "image/jpeg"
            ext = ".webp" if ct == "image/webp" else ".png" if ct == "image/png" else ".jpg"
            cover_url = storage_service.upload_file(str(cover_image_path), f"covers/{job_id}/{uuid.uuid4()}{ext}", content_type=ct, cache_control="public, max-age=31536000")
    except Exception as e:
        logger.warning(f"cover_only_upload_failed job_id={job_id}: {e}")
        cover_url = None

    await callback_web(
        {"job_id": job_id, "post_id": post_id, "user_id": user_id},
        status="done",
        cover_url=cover_url,
        stage="cover_only",
        stage_message="封面已生成",
        no_post_status=True,
        cover_trace=cover_trace if isinstance(cover_trace, list) else None,
        cover_audit=cover_audit if isinstance(cover_audit, dict) else None,
    )


def run_worker():
    logger.info(f"🚀 Worker started. Queue limit: {MAX_QUEUE_SIZE}")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    while True:
        try:
            job_data = job_queue.get_job()
            if job_data is None:
                break

            loop.run_until_complete(process_job(job_data))
            job_queue.task_done()

        except Exception as e:
            logger.error(f"Worker loop error: {e}")
            time.sleep(1)
