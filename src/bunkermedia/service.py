from __future__ import annotations

from pathlib import Path

from bunkermedia.config import AppConfig
from bunkermedia.database import Database
from bunkermedia.downloader import Downloader
from bunkermedia.intelligence import IntelligenceEngine
from bunkermedia.library import MediaLibrary
from bunkermedia.logging_utils import setup_logging
from bunkermedia.recommender import RecommendationEngine
from bunkermedia.scraper import Scraper
from bunkermedia.workers import WorkerManager


class BunkerService:
    def __init__(self, config_path: str | Path = "config.yaml") -> None:
        self.config = AppConfig.from_yaml(config_path)
        self.logger = setup_logging(self.config.logs_dir)
        self.db = Database(self.config.database_path)
        self.library = MediaLibrary(self.config.download_path)
        self.downloader = Downloader(self.config, self.db, self.library, self.logger)
        self.scraper = Scraper(self.db, self.logger)
        self.intelligence = IntelligenceEngine(
            self.db,
            self.logger,
            embedding_dim=self.config.embedding_dim,
            max_text_chars=self.config.transcript_max_chars,
        )
        self.recommender = RecommendationEngine(self.db, self.logger)
        self.workers = WorkerManager(
            self.config,
            self.db,
            self.downloader,
            self.scraper,
            self.intelligence,
            self.recommender,
            self.logger,
        )
        self._initialized = False

    async def initialize(self) -> None:
        if self._initialized:
            return
        self.library.ensure_layout()
        self.db.initialize()
        self.config.download_archive.parent.mkdir(parents=True, exist_ok=True)
        self.config.download_archive.touch(exist_ok=True)
        self._initialized = True
        self.logger.info("Service initialized")

    async def shutdown(self) -> None:
        await self.workers.stop()
        self.db.close()
        self._initialized = False

    async def add_url(self, url: str, target_type: str = "auto", priority: int = 0) -> int:
        return self.db.queue_download(url, target_type=target_type, priority=priority)

    async def sync_once(self) -> None:
        await self.scraper.fetch_trending(limit=50)

        for channel in self.config.channel_feeds:
            await self.scraper.fetch_channel_feed(channel, limit=50)

        for playlist in self.config.playlist_feeds:
            await self.scraper.fetch_playlist_metadata(playlist, limit=100)

        await self.workers.process_download_queue_once()
        await self.intelligence.refresh_embeddings(limit=self.config.intelligence_batch_size)
        await self.recommender.refresh_scores()

    async def recommend(self, limit: int = 20, explain: bool = False):
        return await self.recommender.recommend(limit=limit, explain=explain)

    def list_videos(self, limit: int = 100, search: str | None = None):
        return self.db.list_videos(limit=limit, search=search)

    def get_video(self, video_id: str):
        return self.db.get_video(video_id)

    def mark_watched(
        self,
        video_id: str,
        watch_seconds: int = 0,
        completed: bool = True,
        liked: bool | None = None,
        disliked: bool | None = None,
        rating: float | None = None,
        notes: str | None = None,
    ) -> None:
        self.db.mark_watched(
            video_id,
            watch_seconds=watch_seconds,
            completed=completed,
            liked=liked,
            disliked=disliked,
            rating=rating,
            notes=notes,
        )

    def get_stream_path(self, video_id: str) -> Path | None:
        video = self.db.get_video(video_id)
        if not video:
            return None
        local_path = video.get("local_path")
        if not local_path:
            return None
        path = Path(local_path)
        if not path.exists():
            return None
        return path
