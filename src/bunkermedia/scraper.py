from __future__ import annotations

import asyncio
from typing import Any

from yt_dlp import YoutubeDL

from bunkermedia.database import Database
from bunkermedia.models import VideoMetadata


class Scraper:
    def __init__(self, db: Database, logger: Any) -> None:
        self.db = db
        self.logger = logger

    async def fetch_trending(self, limit: int = 50) -> list[VideoMetadata]:
        info = await asyncio.to_thread(self._extract_sync, "https://www.youtube.com/feed/trending", limit)
        videos = self._store_entries(info, default_source="https://www.youtube.com/feed/trending")
        if videos:
            total = len(videos)
            for idx, video in enumerate(videos):
                score = max(0.0, (total - idx) / max(total, 1))
                self.db.set_trending_score(video.video_id, score)
        self.logger.info("Trending fetch complete count=%d", len(videos))
        return videos

    async def fetch_channel_feed(self, channel_url: str, limit: int = 50) -> list[VideoMetadata]:
        info = await asyncio.to_thread(self._extract_sync, channel_url, limit)
        videos = self._store_entries(info, default_source=channel_url)
        self.logger.info("Channel feed fetched url=%s count=%d", channel_url, len(videos))
        return videos

    async def fetch_playlist_metadata(self, playlist_url: str, limit: int = 100) -> list[VideoMetadata]:
        info = await asyncio.to_thread(self._extract_sync, playlist_url, limit)
        videos = self._store_entries(info, default_source=playlist_url)
        self.logger.info("Playlist metadata fetched url=%s count=%d", playlist_url, len(videos))
        return videos

    def _extract_sync(self, url: str, limit: int) -> dict[str, Any] | None:
        opts = {
            "quiet": True,
            "no_warnings": True,
            "ignoreerrors": True,
            "extract_flat": True,
            "skip_download": True,
            "playlistend": limit,
        }
        with YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False)

    def _store_entries(self, info: dict[str, Any] | None, default_source: str) -> list[VideoMetadata]:
        entries = self._flatten_entries(info)
        videos: list[VideoMetadata] = []
        for entry in entries:
            video_id = str(entry.get("id") or "").strip()
            if not video_id:
                continue

            title = str(entry.get("title") or "Untitled")
            channel = str(entry.get("channel") or entry.get("uploader") or "Unknown")
            source_url = str(entry.get("webpage_url") or entry.get("url") or default_source)
            if source_url and not source_url.startswith("http"):
                source_url = f"https://www.youtube.com/watch?v={video_id}"
            upload_date = entry.get("upload_date")
            duration_seconds = None
            if entry.get("duration") is not None:
                try:
                    duration_seconds = max(0, int(entry.get("duration")))
                except (TypeError, ValueError):
                    duration_seconds = None

            meta = VideoMetadata(
                video_id=video_id,
                title=title,
                channel=channel,
                upload_date=str(upload_date) if upload_date else None,
                source_url=source_url,
                playlist_index=self._coerce_int(entry.get("playlist_index")),
                duration_seconds=duration_seconds,
                downloaded=False,
            )
            self.db.upsert_video(meta)
            videos.append(meta)
        return videos

    @staticmethod
    def _flatten_entries(info: dict[str, Any] | None) -> list[dict[str, Any]]:
        if not info:
            return []
        entries = info.get("entries")
        if entries and isinstance(entries, list):
            return [entry for entry in entries if isinstance(entry, dict)]
        return [info] if isinstance(info, dict) else []

    @staticmethod
    def _coerce_int(value: Any) -> int | None:
        try:
            if value is None:
                return None
            return int(value)
        except (TypeError, ValueError):
            return None
