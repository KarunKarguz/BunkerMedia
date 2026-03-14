from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from yt_dlp import YoutubeDL  # type: ignore[import-untyped]

from bunkermedia.config import AppConfig
from bunkermedia.database import Database
from bunkermedia.library import MediaLibrary
from bunkermedia.models import VideoMetadata


def infer_target_type(url: str) -> str:
    lowered = url.lower()
    if "feed/trending" in lowered:
        return "trending"
    if "list=" in lowered or "/playlist" in lowered:
        return "playlist"
    if any(token in lowered for token in ("/channel/", "/@", "/user/", "/c/")):
        return "channel"
    return "single"


class Downloader:
    def __init__(self, config: AppConfig, db: Database, library: MediaLibrary, logger: Any) -> None:
        self.config = config
        self.db = db
        self.library = library
        self.logger = logger

    async def download_url(self, url: str, target_type: str = "auto", batch_id: int | None = None) -> list[VideoMetadata]:
        mode = infer_target_type(url) if target_type == "auto" else target_type
        videos = await asyncio.to_thread(self._download_sync, url, mode, batch_id)
        for meta in videos:
            self.db.upsert_video(meta)
            if meta.local_path:
                self.db.mark_downloaded(meta.video_id, meta.local_path, file_size_bytes=meta.file_size_bytes)
            if batch_id is not None and meta.local_path:
                self.db.mark_batch_item_done(batch_id, meta.video_id, meta.local_path)
        return videos

    def _download_sync(self, url: str, target_type: str, batch_id: int | None = None) -> list[VideoMetadata]:
        finished_paths: dict[str, str] = {}

        def progress_hook(data: dict[str, Any]) -> None:
            if data.get("status") != "finished":
                return
            info_dict = data.get("info_dict") or {}
            video_id = info_dict.get("id")
            filename = data.get("filename")
            if video_id and filename:
                finished_paths[str(video_id)] = str(filename)
                if batch_id is not None:
                    self.db.mark_batch_item_done(batch_id, str(video_id), str(filename))

        opts: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "ignoreerrors": True,
            "restrictfilenames": True,
            "download_archive": str(self.config.download_archive),
            "outtmpl": self.library.output_template(target_type),
            "progress_hooks": [progress_hook],
            "concurrent_fragment_downloads": 1 if self.config.prefer_low_power_mode else 3,
            "format": (
                "bestvideo[height<=720]+bestaudio/best[height<=720]/best"
                if self.config.prefer_low_power_mode
                else "bv*+ba/b"
            ),
            "merge_output_format": "mp4",
            "noplaylist": target_type == "single",
        }

        self.logger.info("Download started url=%s mode=%s", url, target_type)
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)

        videos: list[VideoMetadata] = []
        for entry in self._flatten_entries(info):
            video_id = str(entry.get("id") or "").strip()
            if not video_id:
                continue

            title = str(entry.get("title") or "Untitled")
            channel = str(entry.get("channel") or entry.get("uploader") or "Unknown")
            source_url = str(entry.get("webpage_url") or entry.get("url") or url)
            if source_url and not source_url.startswith("http"):
                source_url = f"https://www.youtube.com/watch?v={video_id}"
            upload_date = entry.get("upload_date")
            local_path = finished_paths.get(video_id) or entry.get("_filename")
            duration_seconds = None
            raw_duration = entry.get("duration")
            if raw_duration is not None:
                try:
                    duration_seconds = max(0, int(raw_duration))
                except (TypeError, ValueError):
                    duration_seconds = None

            file_size_bytes = None
            raw_size = entry.get("filesize") or entry.get("filesize_approx")
            if raw_size is not None:
                try:
                    file_size_bytes = max(0, int(raw_size))
                except (TypeError, ValueError):
                    file_size_bytes = None
            if local_path and (file_size_bytes is None or file_size_bytes <= 0):
                try:
                    file_size_bytes = int(Path(str(local_path)).stat().st_size)
                except OSError:
                    file_size_bytes = None

            meta = VideoMetadata(
                video_id=video_id,
                title=title,
                channel=channel,
                upload_date=str(upload_date) if upload_date else None,
                source_url=source_url,
                local_path=str(local_path) if local_path else None,
                thumbnail_url=self._extract_thumbnail_url(entry, video_id),
                playlist_index=self._coerce_int(entry.get("playlist_index")),
                duration_seconds=duration_seconds,
                file_size_bytes=file_size_bytes,
                downloaded=bool(local_path),
            )
            videos.append(meta)

        self.logger.info("Download finished url=%s videos=%d", url, len(videos))
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

    @staticmethod
    def _extract_thumbnail_url(entry: dict[str, Any], video_id: str) -> str | None:
        candidate = entry.get("thumbnail")
        if isinstance(candidate, str) and candidate.startswith("http"):
            return candidate
        thumbnails = entry.get("thumbnails")
        if isinstance(thumbnails, list):
            for item in reversed(thumbnails):
                url = item.get("url") if isinstance(item, dict) else None
                if isinstance(url, str) and url.startswith("http"):
                    return url
        if video_id:
            return f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
        return None
