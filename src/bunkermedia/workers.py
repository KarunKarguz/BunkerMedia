from __future__ import annotations

import asyncio
from typing import Any

from bunkermedia.config import AppConfig
from bunkermedia.database import Database
from bunkermedia.downloader import Downloader
from bunkermedia.intelligence import IntelligenceEngine
from bunkermedia.recommender import RecommendationEngine
from bunkermedia.scraper import Scraper


class WorkerManager:
    def __init__(
        self,
        config: AppConfig,
        db: Database,
        downloader: Downloader,
        scraper: Scraper,
        intelligence: IntelligenceEngine,
        recommender: RecommendationEngine,
        logger: Any,
    ) -> None:
        self.config = config
        self.db = db
        self.downloader = downloader
        self.scraper = scraper
        self.intelligence = intelligence
        self.recommender = recommender
        self.logger = logger
        self._stop_event = asyncio.Event()
        self._tasks: list[asyncio.Task[None]] = []

    async def start(self) -> None:
        if self._tasks:
            return
        self._stop_event.clear()
        intervals = self.config.update_intervals
        self._tasks = [
            asyncio.create_task(
                self._interval_loop(self._run_playlist_sync, intervals.playlist_sync_seconds, "playlist_sync")
            ),
            asyncio.create_task(
                self._interval_loop(self._run_trending_fetch, intervals.trending_fetch_seconds, "trending_fetch")
            ),
            asyncio.create_task(
                self._interval_loop(
                    self._run_intelligence_refresh,
                    intervals.intelligence_refresh_seconds,
                    "intelligence_refresh",
                )
            ),
            asyncio.create_task(
                self._interval_loop(
                    self._run_recommendation_refresh,
                    intervals.recommendation_update_seconds,
                    "recommendation_refresh",
                )
            ),
            asyncio.create_task(
                self._interval_loop(self.process_download_queue_once, intervals.download_queue_seconds, "download_queue")
            ),
        ]
        self.logger.info("Background workers started")

    async def stop(self) -> None:
        self._stop_event.set()
        if not self._tasks:
            return
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        self.logger.info("Background workers stopped")

    async def _interval_loop(self, fn: Any, interval_seconds: int, name: str) -> None:
        while not self._stop_event.is_set():
            try:
                await fn()
            except Exception:
                self.logger.exception("Worker failed name=%s", name)

            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=max(interval_seconds, 1))
            except TimeoutError:
                continue

    async def _run_trending_fetch(self) -> None:
        await self.scraper.fetch_trending(limit=50)

    async def _run_playlist_sync(self) -> None:
        for playlist_url in self.config.playlist_feeds:
            videos = await self.scraper.fetch_playlist_metadata(playlist_url, limit=100)
            for video in videos:
                existing = self.db.get_video(video.video_id)
                if existing and not int(existing.get("downloaded") or 0):
                    source = video.source_url or f"https://www.youtube.com/watch?v={video.video_id}"
                    self.db.queue_download(source, target_type="single", priority=1)

        for channel_url in self.config.channel_feeds:
            videos = await self.scraper.fetch_channel_feed(channel_url, limit=50)
            for video in videos:
                existing = self.db.get_video(video.video_id)
                if existing and not int(existing.get("downloaded") or 0):
                    source = video.source_url or f"https://www.youtube.com/watch?v={video.video_id}"
                    self.db.queue_download(source, target_type="single", priority=1)

    async def _run_intelligence_refresh(self) -> None:
        await self.intelligence.refresh_embeddings(limit=self.config.intelligence_batch_size)

    async def _run_recommendation_refresh(self) -> None:
        await self.recommender.refresh_scores()

    async def process_download_queue_once(self) -> None:
        jobs = self.db.claim_pending_jobs(limit=max(self.config.max_parallel_downloads, 1))
        if not jobs:
            return

        sem = asyncio.Semaphore(max(self.config.max_parallel_downloads, 1))
        tasks = [asyncio.create_task(self._process_single_job(job, sem)) for job in jobs]
        await asyncio.gather(*tasks)
        await self.intelligence.refresh_embeddings(limit=self.config.intelligence_batch_size)

    async def _process_single_job(self, job: dict[str, Any], sem: asyncio.Semaphore) -> None:
        async with sem:
            job_id = int(job["id"])
            url = str(job["url"])
            target_type = str(job.get("target_type") or "auto")
            try:
                await self.downloader.download_url(url, target_type=target_type)
                self.db.update_job_status(job_id, "done")
            except Exception as exc:
                self.db.update_job_status(job_id, "failed", error=str(exc))
                self.logger.exception("Download job failed id=%s url=%s", job_id, url)
