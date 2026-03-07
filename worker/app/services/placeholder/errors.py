from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class PlaceholderError(Exception):
    code: str
    provider: str = ""
    retryable: bool = False
    http_status: Optional[int] = None
    detail: str = ""

    def as_dict(self) -> dict:
        return {
            "code": str(self.code or ""),
            "provider": str(self.provider or ""),
            "retryable": bool(self.retryable),
            "http_status": int(self.http_status) if self.http_status is not None else None,
            "detail": str(self.detail or "")[:300],
        }

