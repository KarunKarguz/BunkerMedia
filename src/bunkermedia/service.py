from __future__ import annotations

from pathlib import Path

from bunkermedia.config import AppConfig
from bunkermedia.database import Database
from bunkermedia.downloader import Downloader
from bunkermedia.intelligence import IntelligenceEngine
from bunkermedia.library import MediaLibrary
from bunkermedia.logging_utils import setup_logging
from bunkermedia.maintenance import backup_state, restore_state
from bunkermedia.metrics import MetricsRegistry
from bunkermedia.network import NetworkStateManager
from bunkermedia.providers import LocalFolderProvider, ProviderRegistry, RSSProvider, YouTubeProvider
from bunkermedia.recommender import RecommendationEngine
from bunkermedia.scraper import Scraper
from bunkermedia.workers import WorkerManager


class BunkerService:
    def __init__(self, config_path: str | Path = "config.yaml") -> None:
        self.config = AppConfig.from_yaml(config_path)
        self.logger = setup_logging(self.config.logs_dir, mode=self.config.log_format)
        self.metrics = MetricsRegistry()
        self.db = Database(self.config.database_path)
        self.library = MediaLibrary(self.config.download_path)
        self.network = NetworkStateManager(self.config, self.logger)
        self.downloader = Downloader(self.config, self.db, self.library, self.logger)
        self.scraper = Scraper(self.db, self.logger)
        self.intelligence = IntelligenceEngine(
            self.db,
            self.logger,
            embedding_dim=self.config.embedding_dim,
            max_text_chars=self.config.transcript_max_chars,
        )
        self.recommender = RecommendationEngine(self.db, self.logger)
        self.providers = ProviderRegistry()
        self.providers.register(YouTubeProvider(self.scraper, self.downloader))
        self.providers.register(RSSProvider(self.db, self.downloader, self.logger))
        self.providers.register(LocalFolderProvider(self.db, self.logger, self.config.local_watch_folders))
        self.workers = WorkerManager(
            self.config,
            self.db,
            self.downloader,
            self.scraper,
            self.intelligence,
            self.recommender,
            self.logger,
            self.network,
            self.metrics,
        )
        self._initialized = False

    async def initialize(self) -> None:
        if self._initialized:
            return
        self.library.ensure_layout()
        self.db.initialize()
        self.config.download_archive.parent.mkdir(parents=True, exist_ok=True)
        self.config.download_archive.touch(exist_ok=True)
        await self.network.refresh()
        self.metrics.set_gauge("network_online", 1.0 if self.network.is_online else 0.0)
        self._initialized = True
        self.metrics.inc("service_init_total")
        self.logger.info("Service initialized")

    async def shutdown(self) -> None:
        await self.workers.stop()
        self.db.close()
        self._initialized = False

    async def add_url(self, url: str, target_type: str = "auto", priority: int = 0) -> int:
        job_id = self.db.queue_download(url, target_type=target_type, priority=priority)
        self.metrics.inc("download_jobs_queued_total")
        return job_id

    async def sync_once(self) -> None:
        await self.network.refresh()
        self.metrics.set_gauge("network_online", 1.0 if self.network.is_online else 0.0)
        if not self.network.is_online:
            self.logger.warning("Sync skipped: offline mode")
            self.metrics.inc("sync_skipped_offline_total")
            return
        if not self.network.in_sync_window():
            self.logger.info("Sync skipped: outside sync window")
            self.metrics.inc("sync_skipped_window_total")
            return

        self.metrics.inc("sync_started_total")
        await self.scraper.fetch_trending(limit=50)

        for channel in self.config.channel_feeds:
            await self.scraper.fetch_channel_feed(channel, limit=50)

        for playlist in self.config.playlist_feeds:
            await self.scraper.fetch_playlist_metadata(playlist, limit=100)

        for rss in self.config.rss_feeds:
            items = await self.discover(provider="rss", source=rss, limit=100)
            for item in items:
                existing = self.get_video(item.video_id)
                if not existing:
                    continue
                if int(existing.get("downloaded") or 0):
                    continue
                if item.source_url:
                    await self.add_url(item.source_url, target_type="auto", priority=1)

        if self.config.local_watch_folders:
            await self.discover(provider="local", source="default", limit=2000)

        await self.workers.process_download_queue_once()
        await self.intelligence.refresh_embeddings(limit=self.config.intelligence_batch_size)
        await self.recommender.refresh_scores()
        self.metrics.inc("sync_completed_total")

    async def recommend(self, limit: int = 20, explain: bool = False):
        return await self.recommender.recommend(limit=limit, explain=explain)

    def list_download_jobs(self, status: str | None = None, limit: int = 100):
        return self.db.list_download_jobs(status=status, limit=limit)

    def list_dead_letter_jobs(self, limit: int = 100):
        return self.db.list_dead_letter_jobs(limit=limit)

    def retry_dead_letter(self, dead_letter_id: int) -> int | None:
        return self.db.retry_dead_letter(dead_letter_id)

    def list_videos(self, limit: int = 100, search: str | None = None):
        return self.db.list_videos(limit=limit, search=search)

    def list_providers(self) -> list[str]:
        return self.providers.list()

    async def discover(self, provider: str, source: str, limit: int = 50):
        selected = self.providers.get(provider)
        items = await selected.discover(source, limit=limit)
        self.metrics.inc(f"provider_discover_{selected.name}_total")
        return items

    async def acquire(self, provider: str, source: str, mode: str = "auto"):
        selected = self.providers.get(provider)
        items = await selected.acquire(source, mode=mode)
        self.metrics.inc(f"provider_acquire_{selected.name}_total")
        return items

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

    async def refresh_network_state(self) -> bool:
        online = await self.network.refresh()
        self.metrics.set_gauge("network_online", 1.0 if online else 0.0)
        return online

    def get_health_state(self) -> dict[str, object]:
        return {
            "status": "ok",
            "online": self.network.is_online,
            "in_sync_window": self.network.in_sync_window(),
            "schema_version": self.db.get_schema_version(),
            "providers": self.list_providers(),
        }

    def render_metrics(self) -> str:
        self.metrics.set_gauge("queue_pending", float(len(self.db.list_download_jobs(status="pending", limit=5000))))
        self.metrics.set_gauge("queue_processing", float(len(self.db.list_download_jobs(status="processing", limit=5000))))
        self.metrics.set_gauge("queue_dead", float(len(self.db.list_download_jobs(status="dead", limit=5000))))
        self.metrics.set_gauge("deadletter_items", float(len(self.db.list_dead_letter_jobs(limit=5000))))
        self.metrics.set_gauge("schema_version", float(self.db.get_schema_version()))
        return self.metrics.render_prometheus()

    def backup(self, output_dir: Path | None = None) -> Path:
        return backup_state(self.config, output_dir=output_dir)

    def restore(self, archive_path: Path, force: bool = False) -> None:
        restore_state(self.config, archive_path=archive_path, force=force)

    def get_schema_version(self) -> int:
        return self.db.get_schema_version()

    def list_schema_migrations(self) -> list[dict[str, object]]:
        return self.db.list_schema_migrations()
