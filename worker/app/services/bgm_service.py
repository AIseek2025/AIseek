import os
import random
import logging
import subprocess
import shutil
from pathlib import Path
from typing import Optional
from app.core.config import ASSETS_DIR

logger = logging.getLogger(__name__)

class BGMService:
    def __init__(self):
        self.bgm_dir = ASSETS_DIR / "bgm"
        self.bgm_dir.mkdir(parents=True, exist_ok=True)
        
        self.defaults = {
            "hot": ["edm_2.mp3", "hiphop_2.mp3", "rock_2.mp3", "synthwave_2.mp3", "cheerful_1.mp3"],
            "cheerful": ["cheerful_1.mp3", "upbeat.mp3"],
            "upbeat": ["cheerful_1.mp3", "upbeat.mp3"],
            "serious": ["serious_1.mp3", "news.mp3"],
            "relaxing": ["relaxing_1.mp3", "ambient.mp3"],
            "chill": ["relaxing_1.mp3", "ambient.mp3"],
            "tech": ["tech_1.mp3", "cyber.mp3"],
            "warm": ["warm_1.mp3"],
            "cinematic": ["cinematic_1.mp3"],
            "lofi": ["lofi_1.mp3", "lofi_2.mp3"],
            "ambient": ["ambient_1.mp3", "ambient_2.mp3"],
            "piano": ["piano_1.mp3", "piano_2.mp3"],
            "acoustic": ["acoustic_1.mp3", "acoustic_2.mp3"],
            "hiphop": ["hiphop_1.mp3", "hiphop_2.mp3"],
            "edm": ["edm_1.mp3", "edm_2.mp3"],
            "synthwave": ["synthwave_1.mp3", "synthwave_2.mp3"],
            "orchestral": ["orchestral_1.mp3", "orchestral_2.mp3"],
            "corporate": ["corporate_1.mp3", "corporate_2.mp3"],
            "jazz": ["jazz_1.mp3", "jazz_2.mp3"],
            "rock": ["rock_1.mp3", "rock_2.mp3"],
        }

    def list_bgms(self) -> list[str]:
        try:
            items = [p.name for p in self.bgm_dir.glob("*.mp3") if p.is_file() and p.stat().st_size > 0]
        except Exception:
            items = []
        items = sorted(list({str(x) for x in items if str(x)}))
        return items

    def resolve_bgm_id(self, bgm_id: Optional[str]) -> Optional[str]:
        bid = str(bgm_id or "").strip()
        if not bid:
            return None
        if bid.lower() in {"none", "off", "no", "null"}:
            return None
        try:
            p = (self.bgm_dir / bid).resolve()
            if self.bgm_dir.resolve() not in p.parents:
                return None
            if p.exists() and p.is_file() and p.stat().st_size > 0:
                return str(p)
        except Exception:
            return None
        return None

    def get_bgm(self, mood: str = "neutral", bgm_id: Optional[str] = None) -> Optional[str]:
        """
        Get a random BGM file path for the given mood.
        """
        try:
            self.ensure_placeholders()
        except Exception:
            pass
        direct = self.resolve_bgm_id(bgm_id)
        if direct:
            return direct

        mood = str(mood or "").lower().strip()
        if mood in {"none", "off", "no"}:
            return None
        candidates = self.defaults.get(mood, self.defaults.get("tech"))
        
        if not candidates:
            return None
            
        # Try to find a real file
        for filename in candidates:
            path = self.bgm_dir / filename
            if path.exists():
                return str(path)
                
        # Fallback: check any mp3 in directory
        all_mp3 = list(self.bgm_dir.glob("*.mp3"))
        if all_mp3:
            return str(random.choice(all_mp3))
            
        logger.warning(f"No BGM found for mood {mood} in {self.bgm_dir}")
        return None

    def ensure_placeholders(self):
        """Create dummy BGM files for testing if empty."""
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            ffmpeg = None
        if not ffmpeg:
            logger.info("No BGM files found. Please add mp3 files to worker/assets/bgm/")
            return

        specs = [
            ("tech_1.mp3", "sine=f=220:b=4,asetrate=44100"),
            ("cheerful_1.mp3", "sine=f=523:b=4,asetrate=44100"),
            ("serious_1.mp3", "sine=f=330:b=4,asetrate=44100"),
            ("relaxing_1.mp3", "sine=f=196:b=4,asetrate=44100"),
            ("warm_1.mp3", "sine=f=262:b=4,asetrate=44100"),
            ("cinematic_1.mp3", "sine=f=110:b=4,asetrate=44100"),
            ("lofi_1.mp3", "sine=f=247:b=4,asetrate=44100"),
            ("lofi_2.mp3", "sine=f=185:b=4,asetrate=44100"),
            ("ambient_1.mp3", "sine=f=174:b=4,asetrate=44100"),
            ("ambient_2.mp3", "sine=f=146:b=4,asetrate=44100"),
            ("piano_1.mp3", "sine=f=440:b=4,asetrate=44100"),
            ("piano_2.mp3", "sine=f=392:b=4,asetrate=44100"),
            ("acoustic_1.mp3", "sine=f=294:b=4,asetrate=44100"),
            ("acoustic_2.mp3", "sine=f=330:b=4,asetrate=44100"),
            ("hiphop_1.mp3", "sine=f=98:b=4,asetrate=44100"),
            ("hiphop_2.mp3", "sine=f=110:b=4,asetrate=44100"),
            ("edm_1.mp3", "sine=f=660:b=4,asetrate=44100"),
            ("edm_2.mp3", "sine=f=784:b=4,asetrate=44100"),
            ("synthwave_1.mp3", "sine=f=311:b=4,asetrate=44100"),
            ("synthwave_2.mp3", "sine=f=233:b=4,asetrate=44100"),
            ("orchestral_1.mp3", "sine=f=131:b=4,asetrate=44100"),
            ("orchestral_2.mp3", "sine=f=147:b=4,asetrate=44100"),
            ("corporate_1.mp3", "sine=f=349:b=4,asetrate=44100"),
            ("corporate_2.mp3", "sine=f=392:b=4,asetrate=44100"),
            ("jazz_1.mp3", "sine=f=415:b=4,asetrate=44100"),
            ("jazz_2.mp3", "sine=f=466:b=4,asetrate=44100"),
            ("rock_1.mp3", "sine=f=370:b=4,asetrate=44100"),
            ("rock_2.mp3", "sine=f=440:b=4,asetrate=44100"),
        ]
        for name, src in specs:
            out = self.bgm_dir / name
            try:
                if out.exists() and out.is_file() and out.stat().st_size > 0:
                    continue
                cmd = [ffmpeg, "-y", "-f", "lavfi", "-i", src, "-t", "30", "-c:a", "libmp3lame", "-q:a", "4", str(out)]
                subprocess.run(cmd, capture_output=True, text=True, check=True)
            except Exception:
                try:
                    if out.exists():
                        out.unlink()
                except Exception:
                    pass

# Singleton
bgm_service = BGMService()
