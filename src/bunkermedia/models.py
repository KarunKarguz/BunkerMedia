from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(slots=True)
class VideoMetadata:
    video_id: str
    title: str
    channel: str
    upload_date: Optional[str] = None
    source_url: Optional[str] = None
    local_path: Optional[str] = None
    duration_seconds: Optional[int] = None
    file_size_bytes: Optional[int] = None
    downloaded: bool = False


@dataclass(slots=True)
class Recommendation:
    video_id: str
    title: str
    channel: str
    score: float
    downloaded: bool
    local_path: Optional[str]
    explanation: Optional[dict[str, Any]] = None


@dataclass(slots=True)
class UserProfile:
    profile_id: str
    display_name: str
    is_kids: bool = False
    avatar_color: str = "#d8b56a"
