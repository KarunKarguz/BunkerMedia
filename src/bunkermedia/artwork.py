from __future__ import annotations

import hashlib
import html
import mimetypes
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from bunkermedia.database import Database
from bunkermedia.library import MediaLibrary

IMAGE_EXTENSIONS = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
}


class ArtworkManager:
    def __init__(self, library: MediaLibrary, db: Database, logger: Any) -> None:
        self.library = library
        self.db = db
        self.logger = logger
        self.max_remote_bytes = 3_000_000
        self.remote_timeout_seconds = 8

    def ensure_for_video(self, video: dict[str, Any], allow_remote: bool = True) -> Path | None:
        video_id = str(video.get("video_id") or "").strip()
        if not video_id:
            return None

        existing = str(video.get("artwork_path") or "").strip()
        if existing:
            current = Path(existing)
            if current.exists() and current.is_file():
                thumbnail_url = str(video.get("thumbnail_url") or "").strip() or None
                if allow_remote and thumbnail_url and self._is_generated_artwork(current):
                    refreshed = self._download_remote_artwork(video_id, thumbnail_url)
                    if refreshed is not None:
                        self.db.set_video_artwork(video_id, thumbnail_url=thumbnail_url, artwork_path=str(refreshed))
                        return refreshed
                return current

        thumbnail_url = str(video.get("thumbnail_url") or "").strip() or None
        if allow_remote and thumbnail_url:
            downloaded = self._download_remote_artwork(video_id, thumbnail_url)
            if downloaded is not None:
                self.db.set_video_artwork(video_id, thumbnail_url=thumbnail_url, artwork_path=str(downloaded))
                return downloaded

        generated = self._generate_placeholder(
            video_id=video_id,
            title=str(video.get("title") or "Untitled"),
            channel=str(video.get("channel") or "Unknown"),
            privacy_level=str(video.get("privacy_level") or "standard"),
        )
        self.db.set_video_artwork(video_id, thumbnail_url=thumbnail_url, artwork_path=str(generated))
        return generated

    def backfill_missing(self, limit: int = 120, allow_remote: bool = False) -> int:
        rows = self.db.list_artwork_candidates(limit=max(1, int(limit)))
        refreshed = 0
        for row in rows:
            if self.ensure_for_video(row, allow_remote=allow_remote) is not None:
                refreshed += 1
        if refreshed:
            self.logger.info("Artwork backfill complete refreshed=%s allow_remote=%s", refreshed, allow_remote)
        return refreshed

    @staticmethod
    def media_type_for_path(path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix in IMAGE_EXTENSIONS:
            return IMAGE_EXTENSIONS[suffix]
        guessed, _ = mimetypes.guess_type(str(path))
        return guessed or "application/octet-stream"

    def _download_remote_artwork(self, video_id: str, thumbnail_url: str) -> Path | None:
        destination_base = self.library.artwork_cache_root() / video_id
        try:
            request = Request(
                thumbnail_url,
                headers={"User-Agent": "BunkerMedia/0.2"},
            )
            with urlopen(request, timeout=self.remote_timeout_seconds) as response:
                content_type = response.headers.get_content_type()
                payload = response.read(self.max_remote_bytes + 1)
        except Exception:
            self.logger.warning("Artwork download failed video_id=%s", video_id)
            return None

        if len(payload) > self.max_remote_bytes:
            self.logger.warning("Artwork payload too large video_id=%s bytes=%s", video_id, len(payload))
            return None

        extension = self._image_extension(content_type, thumbnail_url)
        destination = destination_base.with_suffix(extension)
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(payload)
        except OSError:
            self.logger.warning("Artwork cache write failed video_id=%s path=%s", video_id, destination)
            return None
        return destination

    def _generate_placeholder(self, video_id: str, title: str, channel: str, privacy_level: str) -> Path:
        digest = hashlib.sha1(f"{video_id}:{channel}:{title}".encode("utf-8")).hexdigest()
        hue = int(digest[:3], 16) % 360
        accent = "#d8b56a" if privacy_level == "standard" else "#e06a6a"
        initials = self._initials(channel or title or "BM")
        safe_title = html.escape((title or "Untitled")[:34])
        safe_channel = html.escape((channel or "Unknown")[:24])
        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 360" role="img" aria-label="{safe_title}">
<defs>
  <linearGradient id="bg" x1="0" x2="1" y1="0" y2="1">
    <stop offset="0%" stop-color="hsl({hue} 68% 48%)"/>
    <stop offset="100%" stop-color="#0b0b0d"/>
  </linearGradient>
  <linearGradient id="fade" x1="0" x2="0" y1="0" y2="1">
    <stop offset="0%" stop-color="rgba(255,255,255,0.08)"/>
    <stop offset="100%" stop-color="rgba(6,6,7,0.88)"/>
  </linearGradient>
</defs>
<rect width="640" height="360" fill="url(#bg)"/>
<rect width="640" height="360" fill="url(#fade)"/>
<circle cx="120" cy="102" r="78" fill="rgba(255,255,255,0.08)"/>
<circle cx="560" cy="48" r="96" fill="rgba(255,255,255,0.05)"/>
<rect x="34" y="34" width="120" height="120" rx="24" fill="rgba(6,6,7,0.34)" stroke="rgba(255,255,255,0.12)"/>
<text x="94" y="112" text-anchor="middle" fill="#f9f5ec" font-family="Avenir Next,Arial,sans-serif" font-size="52" font-weight="700">{html.escape(initials)}</text>
<text x="38" y="264" fill="{accent}" font-family="Avenir Next,Arial,sans-serif" font-size="18" letter-spacing="2.5">{safe_channel.upper()}</text>
<text x="38" y="308" fill="#f7f2e8" font-family="Avenir Next,Arial,sans-serif" font-size="34" font-weight="700">{safe_title}</text>
</svg>
"""
        destination = self.library.generated_artwork_root() / f"{video_id}.svg"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(svg, encoding="utf-8")
        return destination

    def _is_generated_artwork(self, path: Path) -> bool:
        try:
            return path.resolve().is_relative_to(self.library.generated_artwork_root().resolve())
        except AttributeError:
            return str(self.library.generated_artwork_root().resolve()) in str(path.resolve())

    @staticmethod
    def _image_extension(content_type: str | None, thumbnail_url: str) -> str:
        if content_type:
            guessed = mimetypes.guess_extension(content_type, strict=False)
            if guessed in IMAGE_EXTENSIONS:
                return guessed
        parsed = Path(urlparse(thumbnail_url).path).suffix.lower()
        if parsed in IMAGE_EXTENSIONS:
            return parsed
        return ".jpg"

    @staticmethod
    def _initials(text: str) -> str:
        parts = [part[:1].upper() for part in text.split() if part]
        value = "".join(parts[:2])
        return value or "BM"
