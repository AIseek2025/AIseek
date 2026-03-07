import base64
import json
from datetime import datetime, timezone
from typing import Any, Optional


def encode_cursor(payload: Any) -> str:
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_cursor(cursor: Optional[str]) -> Optional[Any]:
    if not cursor:
        return None
    try:
        cur = str(cursor)
        pad = "=" * ((4 - (len(cur) % 4)) % 4)
        raw = base64.urlsafe_b64decode((cur + pad).encode("ascii"))
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return None


def cursor_datetime(payload: Any, key: str = "created_at") -> Optional[datetime]:
    if not isinstance(payload, dict):
        return None
    v = payload.get(key)
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return datetime.fromtimestamp(float(v), tz=timezone.utc)
    if isinstance(v, str):
        try:
            dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            return None
    return None
