from __future__ import annotations

from bunkermedia.downloader import Downloader, infer_target_type
from bunkermedia.models import VideoMetadata
from bunkermedia.providers.base import Provider
from bunkermedia.scraper import Scraper


class YouTubeProvider(Provider):
    def __init__(self, scraper: Scraper, downloader: Downloader) -> None:
        self.scraper = scraper
        self.downloader = downloader

    @property
    def name(self) -> str:
        return "youtube"

    async def discover(self, source: str, limit: int = 50) -> list[VideoMetadata]:
        src = source.strip()
        if not src:
            return []
        if src.lower() == "trending":
            return await self.scraper.fetch_trending(limit=limit)

        target = infer_target_type(src)
        if target == "channel":
            return await self.scraper.fetch_channel_feed(src, limit=limit)

        return await self.scraper.fetch_playlist_metadata(src, limit=limit)

    async def acquire(self, source: str, mode: str = "auto") -> list[VideoMetadata]:
        src = source.strip()
        if not src:
            return []
        normalized_mode = mode.strip().lower() if mode else "auto"
        return await self.downloader.download_url(src, target_type=normalized_mode)
