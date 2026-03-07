from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class CandidateClip:
    provider: str
    clip_id: str
    download_url: str
    width: int
    height: int
    duration: int
    title: str = ""
    tags: tuple[str, ...] = ()
    author: str = ""
    source_url: str = ""
    license_name: str = ""
    license_url: str = ""
    attribution_required: bool = False
    commercial_use: bool = True
    modifications_allowed: bool = True


@dataclass(frozen=True)
class SearchPlan:
    query: str
    keywords_en: tuple[str, ...] = ()
    keywords_zh: tuple[str, ...] = ()
    negative: tuple[str, ...] = ()
    orientation: str = "portrait"
    min_width: int = 1080
    min_height: int = 1920
    min_duration: int = 3
    max_duration: int = 90
    provider_preference: tuple[str, ...] = ("auto",)
    user_id: Optional[int] = None
    purpose: str = "background"


@dataclass(frozen=True)
class PickedBackground:
    path: str
    provider: str
    clip_id: str
    reason: str
    query: str
    width: int
    height: int
    duration: int
    audit: dict
