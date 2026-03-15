import logging
import asyncio
import os
import uuid
import time
import math
import subprocess
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import List, Optional, Dict, Any

from app.core.config import settings, OUTPUTS_DIR
from app.core.database import db
from app.core.logger import JobLogger, get_logger
from app.services.deepseek_service import deepseek_service
from app.services.tts_service import tts_service
from app.services.video_service import video_service
from app.services.storage_service import storage_service
from app.services.background_service import build_background_for_job, select_background_video
from app.services.cover_service import CoverService, build_cover_plan, has_any_ai_cover_provider
from app.services.bgm_service import bgm_service
from app.services.subtitle_service import build_vtt_from_cues, build_cues_by_duration, evaluate_subtitle_quality
from app.worker_callback import callback_web, cleanup_job_files
from app.pipeline.trace_logger import TraceLogger
from app.pipeline.sanitizer import Sanitizer

logger = get_logger(__name__)
cover_service = CoverService()

class VideoPipeline:
    def __init__(self, job_data: dict):
        self.job_data = job_data
        self.job_id = str(job_data.get("job_id"))
        self.content = str(job_data.get("content") or "").strip()
        self.post_type = job_data.get("post_type", "video")
        self.tracer = TraceLogger(self.job_id)
        self.context: Dict[str, Any] = {
            "analysis": {},
            "analysis_audit": None,
            "subtitle_audit": None,
            "generation_quality": None,
            "voice_path": None,
            "bg_path": None,
            "cover_path": None,
            "video_path": None,
            "files_to_cleanup": [],
            "subtitle_files": [],
            "image_paths": [],
            "uploaded_images": [],
            "bg_tmp_files": []
        }
        self.job_logger = JobLogger(logger, self.job_id)

    def _tight_line(self, s: str, max_len: int = 58) -> str:
        t = re.sub(r"\s+", " ", str(s or "").strip())
        if not t:
            return ""
        if len(t) <= int(max_len):
            return t
        parts = re.split(r"[，。！？；,.!?;:：]\s*", t)
        out = ""
        for p in parts:
            p = str(p or "").strip()
            if not p:
                continue
            cand = (out + ("，" if out else "") + p).strip()
            if len(cand) <= int(max_len):
                out = cand
            else:
                if not out:
                    out = p[: int(max_len)]
                break
        if not out:
            out = t[: int(max_len)]
        return out.strip("，。！？；：,.!?;:")

    def _subtitle_from_narration(self, nar: str, max_len: int = 28) -> str:
        n = self._tight_line(nar, max_len=max_len)
        if not n:
            return ""
        n = n.strip("，。！？；：,.!?;:")
        if len(n) <= int(max_len):
            return n
        return n[: int(max_len)].strip()

    def _generate_gradient_cover(self, title: str) -> Optional[str]:
        """Last-resort: generate a gradient cover image with FFmpeg."""
        out_dir = OUTPUTS_DIR / "covers" / str(self.job_id)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "gradient_cover.jpg"
        title_safe = str(title or "AIseek")[:20].replace("'", "").replace('"', '')
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"color=c=0x1a1a2e:s=720x1280:d=1",
            "-vf", (
                f"drawbox=x=0:y=0:w=720:h=1280:c=0x16213e@0.6:t=fill,"
                f"drawtext=text='{title_safe}':"
                f"fontsize=48:fontcolor=white:"
                f"x=(w-text_w)/2:y=(h-text_h)/2:"
                f"shadowcolor=black:shadowx=2:shadowy=2"
            ),
            "-frames:v", "1",
            "-q:v", "3",
            str(out_path),
        ]
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=10)
            if out_path.exists() and out_path.stat().st_size > 500:
                logger.info(f"Gradient cover generated: {out_path}")
                return str(out_path)
        except Exception as e:
            logger.error(f"Gradient cover failed: {e}")
        return None

    async def run(self):
        try:
            self.tracer.log_step("start", "ok", {"content_len": len(self.content), "post_type": self.post_type})
            self.job_logger.start()
            
            # Step 1: Analyze (Script & content)
            await self._step_analyze()
            
            if self.post_type == "image_text":
                await self._step_slides()
                return

            # Step 2: Audio (TTS & Subtitles)
            await self._step_audio()
            
            # Step 3: Visuals (Background + Cover)
            await self._step_visuals()
            
            # Step 4: Assemble (Video + HLS + Upload)
            await self._step_assemble()
            
            self.tracer.log_step("finish", "ok")
            
        except Exception as e:
            logger.error(f"Pipeline failed: {e}", exc_info=True)
            self.tracer.error("pipeline_fatal", str(e))
            db.update_job(self.job_id, status="error", error=str(e))
            await callback_web(self.job_data, status="failed", error=str(e), stage="failed")
            # Don't re-raise, handled here
        finally:
            self._cleanup()

    async def _step_analyze(self):
        self.tracer.log_step("analyze", "running")
        await callback_web(self.job_data, status="processing", progress=10, stage_message="正在分析文案...")
        
        draft_in = self.job_data.get("draft_json")
        custom_instructions = self.job_data.get("custom_instructions")
        
        analysis = {}
        
        if isinstance(draft_in, dict) and draft_in:
            # Case 1: Pre-defined draft (e.g. from editor)
            self.tracer.log_step("analyze", "using_draft")
            ps = draft_in
            scenes = ps.get("scenes") if isinstance(ps.get("scenes"), list) else []
            src_norm = re.sub(r"\s+", "", str(self.content or ""))
            fixed_scenes = []
            for s in scenes:
                if not isinstance(s, dict):
                    continue
                nar_raw = str(s.get("narration") or "").strip()
                sub_raw = str(s.get("subtitle") or "").strip()
                nar = self._tight_line(nar_raw, max_len=80) if len(nar_raw) > 80 else nar_raw
                sub = self._tight_line(sub_raw, max_len=28) if sub_raw else self._subtitle_from_narration(nar, max_len=28)
                s2 = dict(s)
                s2["narration"] = nar
                s2["subtitle"] = sub
                fixed_scenes.append(s2)
            scenes = fixed_scenes
            ps2 = dict(ps)
            ps2["scenes"] = scenes
            ps = ps2
            
            # Extract voice text from scenes
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
        else:
            # Case 2: DeepSeek Analysis
            self.tracer.log_step("analyze", "calling_deepseek")
            # Handle long content chunking if needed
            # For simplicity in this refactor, we assume standard length or handled by service
            # If extremely long, we truncate or split. Ideally service handles it.
            
            analysis = await deepseek_service.analyze_text(
                self.content, 
                self.post_type,
                custom_instructions
            )
            
        voice_text = analysis.get("voice_text", "")
        src_norm = re.sub(r"\s+", "", str(self.content or ""))
        vt_norm = re.sub(r"\s+", "", str(voice_text or ""))
        sim = 0.0
        if src_norm and vt_norm:
            try:
                sim = float(SequenceMatcher(None, src_norm, vt_norm).ratio())
            except Exception:
                sim = 0.0
        if sim >= 0.95 and len(str(voice_text or "")) >= 200:
            logger.warning(f"DeepSeek returned near-raw content (sim={sim:.2f}). Applying segmented rewrite.")
            forced = Sanitizer.sanitize_voice_text(self.content)
            forced_lines = [x.strip()[:80] for x in forced.splitlines() if x.strip()]
            voice_text = "\n".join(forced_lines[:16]) if forced_lines else forced[:400]
            analysis["voice_text"] = voice_text
        else:
            analysis["voice_text"] = Sanitizer.sanitize_voice_text(voice_text)

        if not analysis.get("subtitles"):
            lines = [str(x or "").strip() for x in analysis["voice_text"].splitlines() if str(x or "").strip()]
            analysis["subtitles"] = [{"text": l[:28]} for l in lines if l]

        analysis["subtitles"] = Sanitizer.sanitize_subtitles(analysis["subtitles"])
        
        meta_top = analysis.get("_meta") if isinstance(analysis.get("_meta"), dict) else {}
        ps2 = analysis.get("production_script") if isinstance(analysis.get("production_script"), dict) else {}
        meta_ps = ps2.get("_meta") if isinstance(ps2.get("_meta"), dict) else {}
        degraded = bool(meta_top.get("degraded") or meta_ps.get("degraded"))
        degraded_reason = str(meta_top.get("degraded_reason") or meta_ps.get("degraded_reason") or "").strip()
        if degraded:
            self.context["analysis_audit"] = {"degraded": True, "degraded_reason": degraded_reason or "unknown"}
            self.tracer.log_step("analyze", "degraded", {"reason": degraded_reason or "unknown"})
        self.context["analysis"] = analysis
        
        # Update DB
        title = analysis.get("title", "Untitled")
        summary = analysis.get("summary", "")
        db.update_job(self.job_id, title=title, summary=summary)
        
        self.tracer.log_step("analyze", "ok", {"title": title, "voice_len": len(analysis["voice_text"])})
        msg = "文案分析完成"
        if isinstance(self.context.get("analysis_audit"), dict):
            msg = "文案分析完成（降级兜底）"
        await callback_web(self.job_data | {"title": title, "summary": summary}, status="processing", progress=20, stage_message=msg, analysis_audit=self.context.get("analysis_audit") if isinstance(self.context.get("analysis_audit"), dict) else None)

    async def _step_slides(self):
        # Implementation for image_text post_type
        self.tracer.log_step("slides", "running")
        analysis = self.context["analysis"]
        slides = analysis.get("slides", [])
        
        from app.services.browser_service import browser_service
        
        uploaded_images = []
        for idx, slide in enumerate(slides):
            keyword = slide.get("image_keyword", "AI")
            img_path = await browser_service.generate_image(keyword, f"{self.job_id}_{idx}")
            self.context["image_paths"].append(img_path)
            
            object_name = f"images/{self.job_id}/{idx}.png"
            url = storage_service.upload_file(img_path, object_name, content_type="image/png")
            uploaded_images.append(url)
            
        await callback_web(
            self.job_data,
            status="done",
            stage="done",
            progress=100,
            stage_message="图文生成完成",
            post_type="image_text",
            images=uploaded_images
        )
        self.tracer.log_step("slides", "ok", {"count": len(uploaded_images)})

    def _extract_narration_segments(self, analysis: dict) -> List[str]:
        """Extract full narration texts from production_script scenes for TTS."""
        ps = analysis.get("production_script") if isinstance(analysis.get("production_script"), dict) else {}
        scenes = ps.get("scenes") if isinstance(ps.get("scenes"), list) else []
        narrations = []
        for s in scenes:
            if not isinstance(s, dict):
                continue
            nar = str(s.get("narration") or "").strip()
            if nar:
                narrations.append(nar)
        if narrations:
            return narrations
        vt = str(analysis.get("voice_text") or "").strip()
        if vt:
            lines = [x.strip() for x in vt.splitlines() if x.strip()]
            if lines:
                return lines
        return [str(s.get("text") or "").strip() for s in (analysis.get("subtitles") or []) if str(s.get("text") or "").strip()]

    def _map_narration_times_to_subtitles(self, narration_segments: List[str], narration_times: list, subtitle_segments: List[str]) -> list:
        """Distribute narration timing across corresponding subtitle segments.
        
        Each narration may correspond to multiple shorter subtitle entries.
        We split the narration's time window proportionally among matching subtitles.
        """
        if not narration_times or not subtitle_segments:
            return []
        if len(narration_times) == len(subtitle_segments):
            return narration_times

        nar_texts = [str(n or "").strip() for n in narration_segments]
        sub_texts = [str(s or "").strip() for s in subtitle_segments]
        nar_to_subs: List[List[int]] = [[] for _ in nar_texts]

        si = 0
        for ni, nar in enumerate(nar_texts):
            if si >= len(sub_texts):
                break
            nar_norm = re.sub(r"\s+", "", nar)
            consumed = 0
            while si < len(sub_texts) and consumed < len(nar_norm):
                nar_to_subs[ni].append(si)
                consumed += len(re.sub(r"\s+", "", sub_texts[si]))
                si += 1
            if not nar_to_subs[ni] and si < len(sub_texts):
                nar_to_subs[ni].append(si)
                si += 1

        while si < len(sub_texts):
            if nar_to_subs:
                nar_to_subs[-1].append(si)
            si += 1

        out_times = [None] * len(sub_texts)
        for ni, sub_indices in enumerate(nar_to_subs):
            if ni >= len(narration_times) or not sub_indices:
                continue
            nar_st, nar_ed = narration_times[ni]
            total_dur = float(nar_ed) - float(nar_st)
            weights = [max(1, len(sub_texts[j])) for j in sub_indices]
            wsum = float(sum(weights)) or 1.0
            t = float(nar_st)
            for k, j in enumerate(sub_indices):
                seg_dur = (weights[k] / wsum) * total_dur
                out_times[j] = (t, t + seg_dur)
                t += seg_dur

        filled = [(t[0], t[1]) if t else (0.0, 0.0) for t in out_times]
        return filled

    async def _step_audio(self):
        self.tracer.log_step("audio", "running")
        await callback_web(self.job_data, status="processing", progress=30, stage_message="生成配音...")
        
        analysis = self.context["analysis"]
        voice_text = analysis["voice_text"]
        voice_style = self.job_data.get("voice_style")
        subtitle_mode = str(self.job_data.get("subtitle_mode") or "zh").strip().lower()
        
        vs = str(voice_style or "").strip().lower()
        is_en_voice = bool(vs) and (vs.startswith("en_") or vs.endswith("_en") or "english" in vs or "premium_en" in vs or "en-" in vs)
        need_en_subs = is_en_voice or (subtitle_mode in {"en", "both", "bilingual", "zh-en"})
        
        narration_segments = self._extract_narration_segments(analysis)
        subtitle_segments = [s["text"] for s in analysis["subtitles"]]
        
        if not narration_segments:
            narration_segments = subtitle_segments[:]
        
        self.tracer.log_step("audio", "segments_prepared", {
            "narration_count": len(narration_segments),
            "subtitle_count": len(subtitle_segments),
            "narration_sample": narration_segments[0][:40] if narration_segments else "",
        })
        
        en_segments = []
        if need_en_subs:
            self.tracer.log_step("audio", "translating_subs")
            try:
                en_segments = await deepseek_service.translate_subtitles(subtitle_segments, "en")
                if len(en_segments) != len(subtitle_segments):
                    en_segments = (en_segments + [""] * len(subtitle_segments))[:len(subtitle_segments)]
            except Exception as e:
                self.tracer.error("audio_translation", str(e))
                en_segments = []
        
        if is_en_voice:
            en_narrations = []
            if en_segments:
                try:
                    en_narrations = await deepseek_service.translate_subtitles(narration_segments, "en")
                except Exception:
                    en_narrations = []
            en_non_empty = [x for x in en_narrations if str(x or "").strip()]
            en_ratio = len(en_non_empty) / len(narration_segments) if narration_segments else 0.0
            en_valid = en_ratio >= 0.6
            speech_segments = en_narrations if en_valid else narration_segments
            if not en_valid:
                self.tracer.log_step("audio", "fallback_base_language", {"reason": "en_translation_unavailable"})
                aa = self.context.get("analysis_audit") if isinstance(self.context.get("analysis_audit"), dict) else {}
                fr = aa.get("fallback_reasons") if isinstance(aa.get("fallback_reasons"), list) else []
                if "en_translation_unavailable" not in fr:
                    fr.append("en_translation_unavailable")
                aa["fallback_reasons"] = fr
                self.context["analysis_audit"] = aa
        else:
            speech_segments = narration_segments
        
        voice_path, narration_times = await tts_service.generate_speech_segments(
            speech_segments, 
            self.job_id, 
            voice_style=voice_style
        )
        
        if not voice_path or not os.path.exists(voice_path):
             self.tracer.log_step("audio", "fallback_monolithic")
             voice_path = await tts_service.generate_speech(voice_text, self.job_id, voice_style=voice_style)
             narration_times = []

        def _probe_audio_duration_sec(path: str) -> float:
            p = str(path or "").strip()
            if not p or (not os.path.exists(p)):
                return 0.0
            cmd = [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=nw=1:nk=1", p,
            ]
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, check=True)
                return max(0.0, float(str(r.stdout or "").strip() or 0.0))
            except Exception:
                return 0.0

        valid_narration_times = isinstance(narration_times, list) and len(narration_times) == len(speech_segments)
        
        if valid_narration_times:
            subtitle_times = self._map_narration_times_to_subtitles(
                narration_segments, narration_times, subtitle_segments
            )
            if not subtitle_times or len(subtitle_times) != len(subtitle_segments):
                valid_narration_times = False
        
        if not valid_narration_times:
            aud = _probe_audio_duration_sec(voice_path)
            cues = build_cues_by_duration(subtitle_segments, aud if aud > 0.2 else 30.0)
            subtitle_times = [(float(st), float(ed)) for st, ed, _ in cues]
            self.tracer.log_step("audio", "subtitle_times_rebuilt", {
                "count": len(subtitle_times), "audio_sec": round(aud, 2)
            })
             
        self.context["voice_path"] = voice_path
        self.context["subtitle_times"] = subtitle_times
        self.context["base_segments"] = subtitle_segments
        self.context["en_segments"] = en_segments
        self.context["files_to_cleanup"].append(voice_path)
        
        self.tracer.log_step("audio", "ok", {"path": voice_path, "speech_seg_count": len(speech_segments)})
        await callback_web(self.job_data, status="processing", progress=45, stage_message="配音完成")

    async def _step_visuals(self):
        self.tracer.log_step("visuals", "running")
        await callback_web(self.job_data, status="processing", progress=55, stage_message="生成画面...")
        
        analysis = self.context["analysis"]
        title = analysis.get("title", "")
        
        # 1. Background Video
        bg_keywords = [title]
        # Try to get visual prompts from scenes
        scenes = analysis.get("production_script", {}).get("scenes", [])
        for s in scenes[:2]: # First 2 scenes
             if s.get("visual_prompt_en"):
                 bg_keywords.append(s["visual_prompt_en"])
        
        # Determine duration
        target_sec = int(self.job_data.get("target_sec") or 30)
        
        bg_path, bg_files, bg_trace, bg_audit = await build_background_for_job(
            job_id=self.job_id,
            user_id=int(self.job_data.get("user_id") or 0),
            title=title,
            content=self.content,
            visual_prompts_en=bg_keywords,
            scene_durations=[], # Let auto-calc
            target_sec=target_sec
        )
        
        self.context["bg_path"] = bg_path
        self.context["bg_trace"] = bg_trace
        self.context["bg_audit"] = bg_audit
        if not self.context["bg_path"]:
            try:
                local_bg = select_background_video(self.job_id, keywords=bg_keywords)
                if local_bg:
                    self.context["bg_path"] = str(local_bg)
                    ext_trace = self.context.get("bg_trace") if isinstance(self.context.get("bg_trace"), list) else []
                    ext_trace.append({"t": "local_bg_fallback", "ok": True, "path": str(local_bg)})
                    self.context["bg_trace"] = ext_trace
                    self.context["bg_audit"] = {"provider": "local", "type": "placeholder"}
            except Exception:
                pass
        if bg_files:
            self.context["bg_tmp_files"].extend(bg_files)
        self.tracer.log_step("visuals_bg", "ok" if self.context.get("bg_path") else "fallback", {"bg_path": self.context.get("bg_path")})

        # 2. BGM
        bgm_mood = self.job_data.get("bgm_mood") or analysis.get("bgm_mood", "neutral")
        bgm_id = self.job_data.get("bgm_id")
        bgm_path = bgm_service.get_bgm(bgm_mood, bgm_id=bgm_id)
        self.context["bgm_path"] = bgm_path

        # 3. Cover (Wanx with fallback)
        cover_path = None
        try:
            if bool(getattr(settings, "cover_fast_degrade_no_key", True)) and not has_any_ai_cover_provider():
                self.context["cover_trace"] = [{"t": "cover_short_circuit", "reason": "all_ai_no_key", "defer": "frame"}]
                self.context["cover_audit"] = {"provider": "frame", "type": "defer_no_key"}
                self.tracer.log_step("visuals_cover", "defer_no_key", {"reason": "all_ai_no_key"})
            else:
                plan = build_cover_plan(analysis, fallback_title=title, orientation=str(self.job_data.get("cover_orientation") or "portrait"))
                cres = cover_service.generate_cover_image(self.job_id, plan)
                if cres.ok and cres.image_path:
                    cover_path = cres.image_path
                    self.context["cover_trace"] = cres.trace
                    self.context["cover_audit"] = {"provider": cres.provider, "embedded": True, "type": "generated"}
                    self.tracer.log_step("visuals_cover", "ok", {"provider": cres.provider})
                else:
                    self.context["cover_trace"] = cres.trace
                    self.tracer.log_step("visuals_cover", "failed_provider", {"trace": cres.trace})
        except Exception as e:
            self.tracer.error("visuals_cover_exception", str(e))
            
        self.context["cover_path"] = cover_path
        # Note: If cover_path is None, we will generate from video frame in assemble step

    async def _step_assemble(self):
        self.tracer.log_step("assemble", "running")
        await callback_web(self.job_data, status="processing", progress=70, stage_message="合成视频...")
        
        analysis = self.context["analysis"]
        title = analysis.get("title", "")
        
        # 1. Video Generation
        # Check if we use storyboard (from draft images)
        use_storyboard = False
        scenes = analysis.get("production_script", {}).get("scenes", [])
        for s in scenes:
            if s.get("image_path") and os.path.exists(s.get("image_path")):
                use_storyboard = True
                break
                
        video_path = None
        if use_storyboard:
            video_path = video_service.create_storyboard_video(
                self.job_id,
                self.context["voice_path"],
                scenes,
                bgm_path=self.context.get("bgm_path"),
                cover_image_path=self.context.get("cover_path"),
                cover_orientation=str(self.job_data.get("cover_orientation") or "portrait")
            )
        else:
            video_path = video_service.create_video(
                self.job_id,
                self.context["voice_path"],
                title,
                bgm_path=self.context.get("bgm_path"),
                bg_keywords=[], # Already used in build_background
                bg_path=self.context.get("bg_path"),
                cover_image_path=self.context.get("cover_path"),
                cover_orientation=str(self.job_data.get("cover_orientation") or "portrait")
            )
            
        self.context["video_path"] = video_path
        self.context["files_to_cleanup"].append(video_path)
        
        # 2. Upload Video
        mp4_url = storage_service.upload_file(video_path, f"videos/{self.job_id}/{uuid.uuid4()}.mp4", content_type="video/mp4")
        
        # 3. HLS Packaging
        hls_url = None
        try:
            master = video_service.package_hls(self.job_id, video_path)
            if master and os.path.exists(master):
                hls_root = str(Path(master).parent)
                self.context["files_to_cleanup"].append(hls_root)
                hls_url = storage_service.upload_directory(hls_root, f"hls/{self.job_id}/{uuid.uuid4()}")
        except Exception as e:
            self.tracer.error("hls_packaging", str(e))
            
        # 4. Cover Fallback & Upload
        cover_path = self.context.get("cover_path")
        if not cover_path:
             self.tracer.log_step("assemble", "cover_fallback_frame")
             try:
                 cov = video_service.generate_cover(self.job_id, video_path, orientation=str(self.job_data.get("cover_orientation") or "portrait"))
                 cover_path = (cov or {}).get("webp") or (cov or {}).get("jpg") or (cov or {}).get("png")
                 if cover_path:
                     logger.info(f"Cover frame extracted: {cover_path}")
                 else:
                     logger.warning("Cover frame extraction returned no path")
             except Exception as e:
                 logger.error(f"Cover frame extraction failed: {e}")
                 self.tracer.error("cover_frame_fallback", str(e))
        
        if not cover_path or not os.path.exists(str(cover_path)):
            self.tracer.log_step("assemble", "cover_fallback_gradient")
            try:
                cover_path = self._generate_gradient_cover(title)
            except Exception as e:
                logger.error(f"Gradient cover generation failed: {e}")
                cover_path = None
        
        cover_url = None
        if cover_path and os.path.exists(cover_path):
            ext = Path(cover_path).suffix
            ct = "image/webp" if ext == ".webp" else "image/jpeg"
            cover_url = storage_service.upload_file(cover_path, f"covers/{self.job_id}/{uuid.uuid4()}{ext}", content_type=ct)
            if cover_url:
                logger.info(f"Cover uploaded: {cover_url}")
            else:
                logger.warning(f"Cover upload returned None for {cover_path}")
            
        # 5. Subtitles (VTT)
        subtitle_tracks = await self._generate_vtt_files(video_path)
        
        meta = video_service.probe_video_meta(video_path)
        duration = int((meta or {}).get("duration") or 0)
        
        self.job_logger.info(
            f"Final callback: mp4={bool(mp4_url)} hls={bool(hls_url)} "
            f"cover={bool(cover_url)} subs={len(subtitle_tracks)} dur={duration}s"
        )
        
        if not mp4_url:
            logger.error(f"mp4_url is None for job {self.job_id}, video may not have uploaded")
        
        await callback_web(
            self.job_data | {"title": title}, 
            status="done", 
            stage="done",
            progress=100, 
            stage_message="完成",
            draft_json=analysis.get("production_script") if isinstance(analysis.get("production_script"), dict) else None,
            mp4_url=mp4_url,
            hls_url=hls_url or mp4_url,
            cover_url=cover_url,
            duration=duration,
            subtitle_tracks=subtitle_tracks,
            analysis_audit=self.context.get("analysis_audit") if isinstance(self.context.get("analysis_audit"), dict) else None,
            subtitle_audit=self.context.get("subtitle_audit") if isinstance(self.context.get("subtitle_audit"), dict) else None,
            generation_quality=self.context.get("generation_quality") if isinstance(self.context.get("generation_quality"), dict) else None,
            placeholder_trace=self.context.get("bg_trace") if isinstance(self.context.get("bg_trace"), list) else None,
            placeholder_audit=self.context.get("bg_audit") if isinstance(self.context.get("bg_audit"), dict) else None,
            cover_trace=self.context.get("cover_trace") if isinstance(self.context.get("cover_trace"), list) else None,
            cover_audit=self.context.get("cover_audit") if isinstance(self.context.get("cover_audit"), dict) else None
        )
        self.tracer.log_step("assemble", "ok", {
            "mp4": mp4_url, "hls": hls_url,
            "cover": cover_url, "subtitle_count": len(subtitle_tracks),
        })

    async def _generate_vtt_files(self, video_path: str):
        subtitle_tracks = []
        subtitle_audit = {"langs": {}, "best": None}
        mode = str(self.job_data.get("subtitle_mode") or "zh").strip().lower()
        if mode in {"off", "none", "no"}:
            self.context["subtitle_audit"] = {"langs": {}, "best": None, "off": True}
            self.context["generation_quality"] = {"subtitle_quality_score": 0, "subtitle_quality_grade": "D", "subtitle_mode": mode}
            return []
            
        base_segments = self.context.get("base_segments", [])
        en_segments = self.context.get("en_segments", [])
        times = self.context.get("subtitle_times", [])
        
        # Calculate offset (if cover embedded)
        t_off = 0.0
        if not str(video_path).endswith(".main.mp4"):
             t_off = float(getattr(settings, "cover_embed_duration_sec", 1.0))
             
        # Prepare specs
        specs = []
        if mode in {"zh", "both"} and base_segments:
            specs.append(("zh", "中文字幕", base_segments, True))
        if mode in {"en", "both"} and en_segments:
            specs.append(("en", "English", en_segments, mode == "en"))
        if mode in {"bilingual", "both", "zh-en"} and en_segments:
            bi = [(f"{a}\n{b}").strip() for a, b in zip(base_segments, en_segments)]
            specs.append(("zh-en", "中英双语", bi, mode in {"bilingual", "zh-en"}))
            
        for lang, label, segs, is_default in specs:
            vtt_text = None
            quality = None
            if times and len(times) == len(segs):
                cues = []
                for (st, ed), txt in zip(times, segs):
                    cues.append((float(st) + t_off, float(ed) + t_off, txt))
                vtt_text = build_vtt_from_cues(cues)
                quality = evaluate_subtitle_quality(cues)
            else:
                duration = 30
                try:
                    meta = video_service.probe_video_meta(video_path)
                    duration = int(meta.get("duration") or 30)
                except Exception:
                    duration = 30
                usable = max(0.2, float(duration) - float(t_off))
                cues = build_cues_by_duration(segs, usable, offset_sec=float(t_off))
                vtt_text = build_vtt_from_cues(cues)
                quality = evaluate_subtitle_quality(cues)
            if isinstance(quality, dict):
                subtitle_audit["langs"][str(lang)] = quality
                
            out_path = str(OUTPUTS_DIR / f"{self.job_id}_{lang}.vtt")
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(vtt_text)
                
            url = storage_service.upload_file(out_path, f"subtitles/{self.job_id}/{uuid.uuid4()}.{lang}.vtt", content_type="text/vtt")
            subtitle_tracks.append({
                "lang": lang, "label": label, "url": url, "kind": "subtitles", "is_default": is_default
            })
            self.context["subtitle_files"].append(out_path)
        best = None
        for _, q in (subtitle_audit.get("langs") or {}).items():
            if not isinstance(q, dict):
                continue
            if best is None or int(q.get("score") or 0) > int(best.get("score") or 0):
                best = q
        subtitle_audit["best"] = best
        self.context["subtitle_audit"] = subtitle_audit
        self.context["generation_quality"] = {
            "subtitle_quality_score": int((best or {}).get("score") or 0),
            "subtitle_quality_grade": str((best or {}).get("grade") or "D"),
            "subtitle_mode": mode,
        }
        return subtitle_tracks

    def _cleanup(self):
        # Clean up all temporary files
        all_files = (
            self.context.get("files_to_cleanup", []) + 
            self.context.get("subtitle_files", []) + 
            self.context.get("bg_tmp_files", []) + 
            self.context.get("image_paths", [])
        )
        cleanup_job_files(self.job_id, *all_files)
