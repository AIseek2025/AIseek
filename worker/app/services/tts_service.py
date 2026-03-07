import os
import logging
import subprocess
import uuid
from pathlib import Path
from app.core.config import settings, OUTPUTS_DIR
from app.core.utils import retry_async
from app.services.voice_profiles import VOICE_PROFILES

logger = logging.getLogger(__name__)

try:
    import edge_tts  # type: ignore
except Exception:
    edge_tts = None

class EdgeTTSService:
    async def generate_speech(self, text: str, job_id: str, voice: str = "zh-CN-XiaoxiaoNeural", voice_style: str = None) -> str:
        """
        Generate speech from text using Edge-TTS.
        """
        vs = str(voice_style or "").strip()
        prof = VOICE_PROFILES.get(vs) if vs and "Neural" not in vs else None
        selected_voice = (prof.get("voice") if prof else vs) or voice
        rate = prof.get("rate") if prof else None
        pitch = prof.get("pitch") if prof else None
        
        output_path = OUTPUTS_DIR / f"{job_id}.mp3"
        logger.info(f"Generating speech for job {job_id} using {selected_voice} at {output_path}...")
        
        async def _generate():
            if edge_tts:
                try:
                    communicate = edge_tts.Communicate(text, selected_voice, rate=rate, pitch=pitch)
                except TypeError:
                    communicate = edge_tts.Communicate(text, selected_voice)
                await communicate.save(str(output_path))
            else:
                t = str(text or "").strip()
                n = len(t)
                dur = max(4, min(3600, int(round(n / 12.0)) if n else 6))
                cmd = [
                    "ffmpeg",
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    "anullsrc=r=44100:cl=mono",
                    "-t",
                    str(int(dur)),
                    "-q:a",
                    "6",
                    str(output_path),
                ]
                subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            if not output_path.exists():
                raise FileNotFoundError(f"Failed to generate speech at {output_path}")
            return str(output_path)
            
        try:
            return await retry_async(_generate, max_retries=3)
        except Exception as e:
            logger.error(f"TTS generation failed: {e}")
            raise

    async def generate_speech_segments(self, segments: list[str], job_id: str, voice: str = "zh-CN-XiaoxiaoNeural", voice_style: str = None) -> tuple[str, list[tuple[float, float]]]:
        segs = [str(x or "").strip() for x in (segments or []) if str(x or "").strip()]
        if not segs:
            p = await self.generate_speech("", job_id, voice=voice, voice_style=voice_style)
            return p, []

        vs = str(voice_style or "").strip()
        prof = VOICE_PROFILES.get(vs) if vs and "Neural" not in vs else None
        selected_voice = (prof.get("voice") if prof else vs) or voice
        rate = prof.get("rate") if prof else None
        pitch = prof.get("pitch") if prof else None

        out_dir = OUTPUTS_DIR / "tts_parts" / str(job_id) / str(uuid.uuid4())
        out_dir.mkdir(parents=True, exist_ok=True)
        parts: list[Path] = []
        lens: list[int] = []

        async def _gen_one(i: int, txt: str) -> Path:
            out_path = out_dir / f"{i:04d}.mp3"
            if edge_tts:
                try:
                    communicate = edge_tts.Communicate(txt, selected_voice, rate=rate, pitch=pitch)
                except TypeError:
                    communicate = edge_tts.Communicate(txt, selected_voice)
                await communicate.save(str(out_path))
            else:
                t = str(txt or "").strip()
                n = len(t)
                dur = max(1, min(60, int(round(n / 10.0)) if n else 2))
                cmd = [
                    "ffmpeg",
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    "anullsrc=r=44100:cl=mono",
                    "-t",
                    str(float(dur)),
                    "-q:a",
                    "6",
                    str(out_path),
                ]
                subprocess.run(cmd, capture_output=True, text=True, check=True)
            if not out_path.exists():
                raise FileNotFoundError(f"Failed to generate speech part at {out_path}")
            return out_path

        def _probe_dur(p: Path) -> float:
            cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(p)]
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, check=True)
                s = str(r.stdout or "").strip()
                return float(s) if s else 0.0
            except Exception:
                return 0.0

        async def _generate_all():
            for i, txt in enumerate(segs, start=1):
                p = await _gen_one(i, txt)
                parts.append(p)
                lens.append(len(str(txt or "").strip()))
            if not parts:
                raise FileNotFoundError("no_tts_parts")
            list_path = out_dir / "concat.txt"
            with open(list_path, "w", encoding="utf-8") as f:
                for p in parts:
                    pp = str(p).replace("'", "")
                    f.write("file '" + pp + "'\n")
            out_audio = OUTPUTS_DIR / f"{job_id}.mp3"
            cmd = [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(list_path),
                "-c:a",
                "libmp3lame",
                "-q:a",
                "4",
                str(out_audio),
            ]
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            if not out_audio.exists():
                raise FileNotFoundError(f"Failed to concat speech at {out_audio}")

            times: list[tuple[float, float]] = []
            t = 0.0
            for p, ln in zip(parts, lens):
                d = float(_probe_dur(p) or 0.0)
                if d <= 0.01:
                    d = max(0.25, min(6.5, float(max(1, int(ln))) / 10.0))
                start = t
                end = t + d
                times.append((start, end))
                t = end
            return str(out_audio), times

        try:
            return await retry_async(_generate_all, max_retries=2)
        except Exception as e:
            logger.error(f"TTS segmented generation failed: {e}")
            p = await self.generate_speech("\n".join(segs), job_id, voice=voice, voice_style=voice_style)
            return p, []

# Singleton instance
tts_service = EdgeTTSService()
