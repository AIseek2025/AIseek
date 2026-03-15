import re
import logging

logger = logging.getLogger(__name__)

class Sanitizer:
    @staticmethod
    def sanitize_voice_text(text: str) -> str:
        """
        Ensures voice text is not one giant blob.
        Splits by punctuation and inserts newlines.
        """
        if not text:
            return ""
        
        # Already has newlines? Good.
        if "\n" in text.strip() and len(text) / (text.count("\n") + 1) < 100:
            return text

        # Aggressive split
        parts = re.split(r'([。！？；!?;])', text)
        lines = []
        buf = ""
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
            
        return "\n".join(lines)

    @staticmethod
    def sanitize_subtitles(subtitles: list[dict]) -> list[dict]:
        out = []
        max_len = 22
        for s in subtitles:
            txt = str(s.get("text") or "").strip()
            if not txt:
                continue
            txt = re.sub(r"\s+", " ", txt).strip()
            if len(txt) <= max_len:
                out.append({"text": txt})
                continue

            parts = []
            buf = ""
            for ch in txt:
                buf += ch
                cut = False
                if len(buf) >= max_len:
                    cut = True
                elif ch in "，。！？；：,.!?;:" and len(buf) >= 12:
                    cut = True
                if cut:
                    p = buf.strip(" ，。！？；：,.!?;:")
                    if p:
                        parts.append(p)
                    buf = ""
            if buf.strip():
                parts.append(buf.strip(" ，。！？；：,.!?;:"))

            for p in parts:
                if len(p) <= max_len:
                    out.append({"text": p})
                    continue
                start = 0
                while start < len(p):
                    seg = p[start : start + max_len]
                    if seg.strip():
                        out.append({"text": seg.strip()})
                    start += max_len

        return out
