import subprocess
import uuid
from pathlib import Path
import os
import logging
from typing import List, Optional
from pathlib import Path
from app.core.config import settings, OUTPUTS_DIR, PLACEHOLDER_VIDEO
import shutil
from app.services.background_service import ffmpeg_background_filter, ffmpeg_background_input_args

logger = logging.getLogger(__name__)

class VideoService:
    def _video_encoder(self) -> str:
        cached = getattr(self, "_cached_encoder", None)
        if isinstance(cached, str) and cached:
            return cached
        # Force libx264 for Linux Docker environment to avoid h264_videotoolbox issues
        want = "libx264"
        selected = "libx264"
        if want == "libx264":
            selected = want
        else:
            try:
                p = subprocess.run(
                    ["ffmpeg", "-hide_banner", "-encoders"],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=3,
                )
                txt = (p.stdout or "") + "\n" + (p.stderr or "")
                import re

                pat = rf"(?m)^\s*[A-Z\.]{{6}}\s+{re.escape(want)}(?:\s|$)"
                if re.search(pat, txt):
                    selected = want
            except Exception:
                selected = "libx264"
        setattr(self, "_cached_encoder", selected)
        return selected

    def _canvas_size(self, orientation: Optional[str]) -> tuple[int, int]:
        o = str(orientation or "portrait").strip().lower()
        if o == "landscape":
            return 1920, 1080
        return 1080, 1920

    def _prepend_cover(
        self,
        job_id: str,
        main_video_path: str,
        cover_image_path: str,
        duration_sec: float,
        orientation: Optional[str] = None,
    ) -> str:
        in_main = str(main_video_path)
        in_cover = str(cover_image_path)
        if not os.path.exists(in_main):
            return in_main
        if not in_cover or not os.path.exists(in_cover):
            return in_main
        out_path = OUTPUTS_DIR / f"{job_id}.mp4"
        tmp_path = OUTPUTS_DIR / f"{job_id}.tmp.mp4"
        dur = float(duration_sec or 1.0)
        if dur < 0.4:
            dur = 0.4
        if dur > 3.0:
            dur = 3.0
        cw, ch = self._canvas_size(orientation)
        cmd = [
            "ffmpeg",
            "-y",
            "-loop",
            "1",
            "-t",
            str(dur),
            "-i",
            in_cover,
            "-i",
            in_main,
            "-filter_complex",
            f"[0:v]scale={cw}:{ch}:force_original_aspect_ratio=increase,crop={cw}:{ch},format=yuv420p,setsar=1[v0];"
            f"[1:v]format=yuv420p,setsar=1[v1];"
            f"anullsrc=r=44100:cl=stereo:d={dur}[a0];"
            f"[1:a]aresample=44100[a1];"
            f"[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]",
            "-map",
            "[v]",
            "-map",
            "[a]",
            "-c:v",
            self._video_encoder(),
            "-b:v",
            "5M",
            "-c:a",
            "aac",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(tmp_path),
        ]
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            if tmp_path.exists() and tmp_path.stat().st_size > 50_000:
                try:
                    shutil.move(str(tmp_path), str(out_path))
                except Exception:
                    try:
                        shutil.copy(str(tmp_path), str(out_path))
                    except Exception:
                        return in_main
                return str(out_path)
        except Exception:
            return in_main
        return in_main

    def create_video(
        self, 
        job_id: str, 
        voice_path: str, 
        title: str, 
        bgm_path: Optional[str] = None,
        image_paths: Optional[List[str]] = None,
        bg_keywords: Optional[List[str]] = None,
        bg_path: Optional[str] = None,
        cover_image_path: Optional[str] = None,
        cover_orientation: Optional[str] = None,
    ) -> str:
        """
        Synthesize video with BGM and Title.
        Supports hardware acceleration on Mac M3 Pro.
        """
        output_path = OUTPUTS_DIR / f"{job_id}.main.mp4"
        logger.info(f"Creating video for job {job_id}...")
        
        if not os.path.exists(voice_path):
             raise FileNotFoundError(f"Voice file not found at {voice_path}")

        # Command construction
        cmd = ["ffmpeg", "-y"]
        
        if bg_path and os.path.exists(str(bg_path)):
            cmd.extend(["-stream_loop", "-1", "-i", str(bg_path)])
        else:
            bg_input_args, _bg_v_idx = ffmpeg_background_input_args(str(job_id), keywords=bg_keywords)
            cmd.extend(bg_input_args)
        
        # Input 1: Voice (The master duration)
        cmd.extend(["-i", voice_path])
        
        # Input 2: BGM (Optional, Loop it)
        has_bgm = False
        if bgm_path and os.path.exists(bgm_path):
            cmd.extend(["-stream_loop", "-1", "-i", bgm_path])
            has_bgm = True
            
        # Filters
        filter_chains = []
        
        # Audio Mixing
        # Map 1:a (Voice) and 2:a (BGM)
        if has_bgm:
            # Voice at 100%, BGM at 10%
            # amix inputs=2:duration=first (stop when voice ends)
            audio_filter = "[1:a]volume=1.0[voice];[2:a]volume=0.1[bgm];[voice][bgm]amix=inputs=2:duration=first[aout]"
            filter_chains.append(audio_filter)
            audio_map = "[aout]"
        else:
            audio_map = "1:a"
            
        # Video Filters
        # NOTE: Many Homebrew builds omit drawtext. Keep the pipeline drawtext-free by default.
        video_filter = ffmpeg_background_filter(cover_orientation)
        
        # Ensure aspect ratio is correct for mobile players (sometimes they stretch if SAR is missing)
        # Force SAR 1:1
        if "setsar=1" not in video_filter:
            video_filter += ",setsar=1"

        if has_bgm:
            # We already have audio filter in filter_chains[0]
            video_filter_complex = f"[0:v]{video_filter}[vout]"
            filter_chains.append(video_filter_complex)
            
            full_filter_complex = ";".join(filter_chains)
            cmd.extend(["-filter_complex", full_filter_complex])
            
            cmd.extend(["-map", "[vout]", "-map", "[aout]"])
        else:
            # No complex filter needed for audio, just use -vf for video
            cmd.extend(["-vf", video_filter])
            cmd.extend(["-map", "0:v", "-map", "1:a"])

        # Encoding settings
        cmd.extend([
            "-c:v", self._video_encoder(),
            "-b:v", "5M",
            "-c:a", "aac",
            "-shortest", # Stop when shortest input ends (should be voice due to amix duration=first, but good safety)
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(output_path)
        ])
        
        try:
            # Execute
            logger.info(f"Running FFmpeg: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            if not output_path.exists():
                raise FileNotFoundError(f"FFmpeg failed to create output file: {result.stderr}")
                
            logger.info(f"Video created successfully at {output_path}")
            cov = str(cover_image_path or "").strip()
            if not cov:
                try:
                    g = self.generate_cover(job_id, str(output_path))
                    cov = str((g or {}).get("webp") or (g or {}).get("jpg") or "").strip()
                except Exception:
                    cov = ""
            final_path = self._prepend_cover(
                job_id,
                str(output_path),
                cov,
                float(getattr(settings, "cover_embed_duration_sec", 1.0) or 1.0),
                cover_orientation,
            )
            try:
                if str(final_path) != str(output_path) and output_path.exists():
                    output_path.unlink(missing_ok=True)
            except Exception:
                pass
            return str(final_path)
            
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg failed with error: {e.stderr}")
            cw, ch = self._canvas_size(cover_orientation)
            fallback_cmd = [
                "ffmpeg",
                "-y",
                "-f",
                "lavfi",
                "-i",
                f"color=c=black:s={cw}x{ch}:r=30",
                "-i",
                voice_path,
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "23",
                "-c:a",
                "aac",
                "-shortest",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                str(output_path),
            ]
            try:
                subprocess.run(fallback_cmd, capture_output=True, text=True, check=True)
                if output_path.exists():
                    return str(output_path)
            except Exception:
                pass
            raise Exception(f"Video generation failed: {e.stderr}")

    def create_storyboard_video(
        self,
        job_id: str,
        voice_path: str,
        scenes: List[dict],
        bgm_path: Optional[str] = None,
        cover_image_path: Optional[str] = None,
        cover_orientation: Optional[str] = None,
    ) -> str:
        output_path = OUTPUTS_DIR / f"{job_id}.main.mp4"
        if not os.path.exists(voice_path):
            raise FileNotFoundError(f"Voice file not found at {voice_path}")
        if not scenes:
            raise ValueError("scenes required")

        pics = []
        durs = []
        for s in scenes:
            if not isinstance(s, dict):
                continue
            p = str(s.get("image_path") or "").strip()
            if not p or not os.path.exists(p):
                continue
            dur = int(s.get("duration_sec") or 0)
            if dur <= 0:
                dur = 6
            pics.append(p)
            durs.append(dur)
        if not pics:
            raise ValueError("no_valid_scene_images")

        cmd = ["ffmpeg", "-y"]
        for i, p in enumerate(pics):
            cmd.extend(["-loop", "1", "-t", str(int(durs[i])), "-i", p])
        cmd.extend(["-i", voice_path])

        has_bgm = False
        if bgm_path and os.path.exists(bgm_path):
            cmd.extend(["-stream_loop", "-1", "-i", bgm_path])
            has_bgm = True

        cw, ch = self._canvas_size(cover_orientation)
        v_filters = []
        for i in range(len(pics)):
            v_filters.append(
                f"[{i}:v]scale={cw}:{ch}:force_original_aspect_ratio=increase,"
                f"crop={cw}:{ch},format=yuv420p,setsar=1[v{i}]"
            )
        v_in = "".join([f"[v{i}]" for i in range(len(pics))])
        v_filters.append(f"{v_in}concat=n={len(pics)}:v=1:a=0[vv]")

        a_voice_idx = len(pics)
        if has_bgm:
            a_bgm_idx = len(pics) + 1
            v_filters.append(f"[{a_voice_idx}:a]volume=1.0[voice]")
            v_filters.append(f"[{a_bgm_idx}:a]volume=0.1[bgm]")
            v_filters.append("[voice][bgm]amix=inputs=2:duration=first[aout]")
            a_map = "[aout]"
        else:
            a_map = f"{a_voice_idx}:a"

        cmd.extend(["-filter_complex", ";".join(v_filters)])
        cmd.extend(["-map", "[vv]", "-map", a_map])
        cmd.extend(
            [
                "-c:v",
                self._video_encoder(),
                "-b:v",
                "5M",
                "-c:a",
                "aac",
                "-shortest",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                str(output_path),
            ]
        )

        try:
            logger.info(f"Running FFmpeg storyboard: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            if not output_path.exists():
                raise FileNotFoundError(f"FFmpeg failed to create output file: {result.stderr}")
            cov = str(cover_image_path or "").strip()
            if not cov:
                try:
                    g = self.generate_cover(job_id, str(output_path))
                    cov = str((g or {}).get("webp") or (g or {}).get("jpg") or "").strip()
                except Exception:
                    cov = ""
            final_path = self._prepend_cover(
                job_id,
                str(output_path),
                cov,
                float(getattr(settings, "cover_embed_duration_sec", 1.0) or 1.0),
                cover_orientation,
            )
            try:
                if str(final_path) != str(output_path) and output_path.exists():
                    output_path.unlink(missing_ok=True)
            except Exception:
                pass
            return str(final_path)
        except subprocess.CalledProcessError as e:
            raise Exception(f"Video generation failed: {e.stderr}")

    def transcode_video(self, job_id: str, input_url: str) -> str:
        """
        Transcode an uploaded video to a standardized format (MP4/H.264).
        If input_url is remote (http), ffmpeg can read it directly.
        """
        output_path = OUTPUTS_DIR / f"{job_id}_transcoded.mp4"
        logger.info(f"Transcoding video for job {job_id} from {input_url}...")
        
        # Basic transcoding command: standardize to 720p, h264, aac
        cmd = [
            "ffmpeg", "-y",
            "-i", input_url,
            "-vf", "scale=-2:720", # Resize to 720p height, keep aspect ratio
            "-c:v", self._video_encoder(),
            "-b:v", "2M",
            "-c:a", "aac",
            "-b:a", "128k",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(output_path)
        ]
        
        try:
            logger.info(f"Running Transcode: {' '.join(cmd)}")
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            if not output_path.exists():
                raise FileNotFoundError("Transcoding failed to produce output")
                
            return str(output_path)
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Transcode failed: {e.stderr}")
            raise Exception(f"Transcoding failed: {e.stderr}")

    def probe_duration(self, input_path: str) -> int:
        try:
            cmd = [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(input_path),
            ]
            p = subprocess.run(cmd, capture_output=True, text=True, check=True)
            s = (p.stdout or "").strip()
            v = float(s) if s else 0.0
            if v < 0:
                v = 0.0
            return int(round(v))
        except Exception:
            return 0

    def probe_video_meta(self, input_path: str) -> dict:
        out = {"duration": 0, "width": 0, "height": 0}
        try:
            cmd = [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height",
                "-show_entries",
                "format=duration",
                "-of",
                "json",
                str(input_path),
            ]
            p = subprocess.run(cmd, capture_output=True, text=True, check=True)
            import json

            obj = json.loads(p.stdout or "{}")
            streams = obj.get("streams") or []
            if streams and isinstance(streams[0], dict):
                out["width"] = int(streams[0].get("width") or 0)
                out["height"] = int(streams[0].get("height") or 0)
            fmt = obj.get("format") or {}
            d = float(fmt.get("duration") or 0.0) if isinstance(fmt, dict) else 0.0
            if d <= 0 and streams and isinstance(streams[0], dict):
                d = float(streams[0].get("duration") or 0.0)
            if d < 0:
                d = 0.0
            out["duration"] = int(round(d))
            return out
        except Exception:
            return out

    def _probe_signalstats(self, input_path: str, at_sec: float, vf: str) -> dict:
        out = {"yavg": -1.0, "ymin": -1.0, "ymax": -1.0}
        try:
            t = float(at_sec or 0.0)
            if t < 0:
                t = 0.0
            cmd = [
                "ffmpeg",
                "-v",
                "error",
                "-ss",
                str(t),
                "-i",
                str(input_path),
                "-frames:v",
                "1",
                "-vf",
                str(vf),
                "-f",
                "null",
                "-",
            ]
            p = subprocess.run(cmd, capture_output=True, text=True, check=True)
            s = (p.stderr or "") + "\n" + (p.stdout or "")
            import re

            m = re.findall(r"lavfi\\.signalstats\\.YAVG=([0-9]+(?:\\.[0-9]+)?)", s)
            if m:
                out["yavg"] = float(m[-1])
            m = re.findall(r"lavfi\\.signalstats\\.YMIN=([0-9]+(?:\\.[0-9]+)?)", s)
            if m:
                out["ymin"] = float(m[-1])
            m = re.findall(r"lavfi\\.signalstats\\.YMAX=([0-9]+(?:\\.[0-9]+)?)", s)
            if m:
                out["ymax"] = float(m[-1])
        except Exception:
            return out
        return out

    def _probe_luma_stats(self, input_path: str, at_sec: float) -> dict:
        return self._probe_signalstats(
            input_path,
            at_sec,
            "scale=320:-2,format=gray,signalstats,metadata=print",
        )

    def _probe_edge_density(self, input_path: str, at_sec: float, region: str) -> float:
        if region == "center":
            crop = "crop=iw*0.62:ih*0.62:(iw-ow)/2:(ih-oh)/2"
        elif region == "bottom":
            crop = "crop=iw*0.90:ih*0.28:(iw-ow)/2:ih*0.68"
        else:
            crop = None
        vf = []
        if crop:
            vf.append(crop)
        vf.append("scale=320:-2")
        vf.append("edgedetect=low=0.1:high=0.4")
        vf.append("format=gray")
        vf.append("signalstats")
        vf.append("metadata=print")
        st = self._probe_signalstats(input_path, at_sec, ",".join(vf))
        try:
            return float(st.get("yavg") or -1.0)
        except Exception:
            return -1.0

    def _select_cover_time(self, input_path: str, duration: int) -> float:
        dur = int(duration or 0)
        candidates = [0.35, 0.7, 1.2, 2.0, 3.0, 4.0]
        if dur >= 6:
            candidates.extend([dur * 0.08, dur * 0.16, dur * 0.28, dur * 0.42])
        if dur >= 12:
            candidates.extend([dur * 0.55, dur * 0.7])
        uniq = []
        for t in candidates:
            try:
                tt = float(t)
            except Exception:
                continue
            if dur > 0 and tt > max(0.0, dur - 0.2):
                continue
            if tt < 0:
                continue
            tt = round(tt, 3)
            if tt not in uniq:
                uniq.append(tt)

        best_t = 0.6
        best_score = -1e18
        for t in uniq[:12]:
            luma = self._probe_luma_stats(input_path, t)
            yavg = float(luma.get("yavg") or -1.0)
            ymin = float(luma.get("ymin") or -1.0)
            ymax = float(luma.get("ymax") or -1.0)
            if yavg < 0:
                continue
            if yavg < 15 or yavg > 245:
                continue
            contrast = max(0.0, ymax - ymin) if ymin >= 0 and ymax >= 0 else 0.0
            if contrast < 12:
                continue

            edge_full = self._probe_edge_density(input_path, t, "full")
            edge_center = self._probe_edge_density(input_path, t, "center")
            edge_bottom = self._probe_edge_density(input_path, t, "bottom")
            if edge_full >= 0 and edge_full < 2.2:
                continue

            score = 0.0
            score += (min(max(yavg, 0.0), 255.0) - 20.0) / 235.0 * 60.0
            score += min(max(contrast, 0.0), 90.0) * 0.35
            if edge_full >= 0:
                score += min(edge_full, 24.0) * 1.6
            if edge_center >= 0:
                score -= max(edge_center - 22.0, 0.0) * 2.2
            if edge_bottom >= 0:
                score -= max(edge_bottom - 26.0, 0.0) * 1.2

            if score > best_score:
                best_score = score
                best_t = float(t)

        return best_t

    def generate_cover(self, job_id: str, input_path: str, orientation: str = "portrait") -> dict:
        out_dir = OUTPUTS_DIR / "covers" / str(job_id) / str(uuid.uuid4())
        out_dir.mkdir(parents=True, exist_ok=True)
        jpg = out_dir / "cover.jpg"
        webp = out_dir / "cover.webp"
        meta = self.probe_video_meta(input_path)
        at = self._select_cover_time(input_path, int(meta.get("duration") or 0))
        ori = str(orientation or "").strip().lower() or "portrait"
        if ori == "landscape":
            vf_cover = "scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720"
        else:
            vf_cover = "scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280"

        def _run(out_path: Path, fmt: str) -> bool:
            cmd = [
                "ffmpeg",
                "-y",
                "-ss",
                str(at),
                "-i",
                str(input_path),
                "-frames:v",
                "1",
                "-vf",
                vf_cover,
                "-q:v",
                "3",
                str(out_path),
            ]
            try:
                subprocess.run(cmd, capture_output=True, text=True, check=True)
                return out_path.exists()
            except Exception:
                return False

        ok_jpg = _run(jpg, "jpg")
        ok_webp = False
        try:
            cmd = [
                "ffmpeg",
                "-y",
                "-ss",
                str(at),
                "-i",
                str(input_path),
                "-frames:v",
                "1",
                "-vf",
                vf_cover,
                "-quality",
                "80",
                str(webp),
            ]
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            ok_webp = webp.exists()
        except Exception:
            ok_webp = False

        out = {"dir": str(out_dir), "jpg": str(jpg) if ok_jpg else None, "webp": str(webp) if ok_webp else None}
        return out

    def package_hls(self, job_id: str, input_path: str) -> str:
        base = OUTPUTS_DIR / "hls" / str(job_id) / str(uuid.uuid4())
        base.mkdir(parents=True, exist_ok=True)

        seg = base / "v%v"
        seg.mkdir(parents=True, exist_ok=True)

        master = base / "master.m3u8"

        # HLS Packaging: Force SAR 1:1 for each stream to fix stretching on some players
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(input_path),
            "-filter_complex",
            "[0:v]split=3[v0][v1][v2];"
            "[v0]scale=w=-2:h=360:force_original_aspect_ratio=decrease,pad=ceil(iw/2)*2:ceil(ih/2)*2,format=yuv420p,setsar=1[v0o];"
            "[v1]scale=w=-2:h=540:force_original_aspect_ratio=decrease,pad=ceil(iw/2)*2:ceil(ih/2)*2,format=yuv420p,setsar=1[v1o];"
            "[v2]scale=w=-2:h=720:force_original_aspect_ratio=decrease,pad=ceil(iw/2)*2:ceil(ih/2)*2,format=yuv420p,setsar=1[v2o]",
            "-map",
            "[v0o]",
            "-map",
            "0:a:0?",
            "-map",
            "[v1o]",
            "-map",
            "0:a:0?",
            "-map",
            "[v2o]",
            "-map",
            "0:a:0?",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "21",
            "-b:v:0",
            "800k",
            "-maxrate:v:0",
            "920k",
            "-bufsize:v:0",
            "1600k",
            "-b:v:1",
            "1500k",
            "-maxrate:v:1",
            "1725k",
            "-bufsize:v:1",
            "3000k",
            "-b:v:2",
            "2500k",
            "-maxrate:v:2",
            "2875k",
            "-bufsize:v:2",
            "5000k",
            "-c:a",
            "aac",
            "-b:a",
            "96k",
            "-g",
            "48",
            "-keyint_min",
            "48",
            "-sc_threshold",
            "0",
            "-force_key_frames",
            "expr:gte(t,n_forced*4)",
            "-f",
            "hls",
            "-hls_time",
            "4",
            "-hls_playlist_type",
            "vod",
            "-hls_segment_type",
            "fmp4",
            "-hls_flags",
            "independent_segments",
            "-master_pl_name",
            "master.m3u8",
            "-var_stream_map",
            "v:0,a:0 v:1,a:1 v:2,a:2",
            "-hls_segment_filename",
            str(base / "v%v" / "seg_%05d.m4s"),
            str(base / "v%v" / "index.m3u8"),
        ]

        try:
            logger.info(f"Running HLS package: {' '.join(cmd)}")
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            if not master.exists():
                raise FileNotFoundError("HLS packaging failed to produce master playlist")
            return str(master)
        except subprocess.CalledProcessError as e:
            logger.error(f"HLS package failed: {e.stderr}")
            raise Exception(f"HLS packaging failed: {e.stderr}")

video_service = VideoService()
