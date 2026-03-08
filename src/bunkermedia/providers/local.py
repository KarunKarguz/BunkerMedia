from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from bunkermedia.database import Database
from bunkermedia.models import VideoMetadata
from bunkermedia.providers.base import Provider

MEDIA_EXTENSIONS = {
    ".mp4",
    ".mkv",
    ".webm",
    ".avi",
    ".mov",
    ".m4v",
    ".mp3",
    ".m4a",
    ".flac",
    ".wav",
}


class LocalFolderProvider(Provider):
    def __init__(self, db: Database, logger: Any, watch_folders: list[Path]) -> None:
        self.db = db
        self.logger = logger
        self.watch_folders = watch_folders

    @property
    def name(self) -> str:
        return "local"

    async def discover(self, source: str, limit: int = 50) -> list[VideoMetadata]:
        selected = self._resolve_roots(source)
        return self._discover_sync(selected, limit)

    async def acquire(self, source: str, mode: str = "auto") -> list[VideoMetadata]:
        return await self.discover(source, limit=500)

    def _resolve_roots(self, source: str) -> list[Path]:
        src = source.strip()
        if not src or src.lower() in {"default", "all"}:
            return list(self.watch_folders)
        return [Path(src).expanduser().resolve()]

    def _discover_sync(self, roots: list[Path], limit: int) -> list[VideoMetadata]:
        if not roots:
            return []

        results: list[VideoMetadata] = []
        target = max(1, limit)

        for root in roots:
            if not root.exists() or not root.is_dir():
                continue
            for path in root.rglob("*"):
                if not path.is_file():
                    continue
                if path.suffix.lower() not in MEDIA_EXTENSIONS:
                    continue

                rel = str(path.resolve())
                vid = f"local_{hashlib.sha1(rel.encode('utf-8')).hexdigest()[:16]}"
                upload_date = self._file_date(path)
                channel = path.parent.name or root.name or "Local"

                meta = VideoMetadata(
                    video_id=vid,
                    title=path.stem,
                    channel=channel,
                    upload_date=upload_date,
                    source_url=str(path),
                    local_path=str(path),
                    downloaded=True,
                )
                self.db.upsert_video(meta)
                self.db.mark_downloaded(meta.video_id, meta.local_path or str(path))
                results.append(meta)

                if len(results) >= target:
                    self.logger.info("Local discover complete roots=%d count=%d", len(roots), len(results))
                    return results

        self.logger.info("Local discover complete roots=%d count=%d", len(roots), len(results))
        return results

    @staticmethod
    def _file_date(path: Path) -> str | None:
        try:
            ts = path.stat().st_mtime
        except OSError:
            return None
        from datetime import datetime

        return datetime.fromtimestamp(ts).strftime("%Y%m%d")
