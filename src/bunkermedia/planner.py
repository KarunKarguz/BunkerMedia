from __future__ import annotations

from typing import Any

from bunkermedia.config import AppConfig
from bunkermedia.database import Database
from bunkermedia.recommender import RecommendationEngine

BYTES_PER_MEGABIT = 125_000
GIB = 1024**3


class OfflinePlanner:
    def __init__(self, config: AppConfig, db: Database, recommender: RecommendationEngine, logger: Any) -> None:
        self.config = config
        self.db = db
        self.recommender = recommender
        self.logger = logger

    async def plan_once(self) -> dict[str, int | str | bool]:
        target_seconds = int(max(0.0, float(self.config.offline_target_hours)) * 3600)
        if target_seconds <= 0:
            return {
                "status": "disabled",
                "queued_jobs": 0,
                "queued_duration_seconds": 0,
                "queued_estimated_bytes": 0,
            }

        inventory = self.db.get_offline_inventory_stats()
        unwatched_seconds = int(inventory["unwatched_duration_seconds"])
        current_storage_bytes = int(inventory["downloaded_storage_bytes"])

        deficit_seconds = max(0, target_seconds - unwatched_seconds)
        if deficit_seconds <= 0:
            return {
                "status": "satisfied",
                "queued_jobs": 0,
                "queued_duration_seconds": 0,
                "queued_estimated_bytes": 0,
                "target_seconds": target_seconds,
                "available_seconds": unwatched_seconds,
            }

        pending_urls = self.db.list_pending_job_urls()
        recs = await self.recommender.recommend(limit=max(1, self.config.offline_planner_max_candidates), explain=False)
        capacity_limit = self._effective_storage_limit_bytes()

        queued_jobs = 0
        queued_duration = 0
        queued_bytes = 0
        batch_limit = max(1, int(self.config.offline_planner_batch_size))

        for rec in recs:
            if deficit_seconds <= 0 or queued_jobs >= batch_limit:
                break

            video = self.db.get_video(rec.video_id)
            if not video:
                continue
            if int(video.get("downloaded") or 0):
                continue
            if video.get("rejected_reason"):
                continue

            source_url = str(video.get("source_url") or "").strip()
            if not source_url or source_url in pending_urls:
                continue

            duration_seconds = self._resolve_duration_seconds(video)
            estimated_size = self._estimate_bytes(video, duration_seconds)
            if capacity_limit is not None and current_storage_bytes + estimated_size > capacity_limit:
                continue

            self.db.queue_download(source_url, target_type="auto", priority=int(self.config.offline_queue_priority))
            pending_urls.add(source_url)

            queued_jobs += 1
            queued_duration += duration_seconds
            queued_bytes += estimated_size
            deficit_seconds -= duration_seconds
            current_storage_bytes += estimated_size

        self.logger.info(
            "Offline planner complete queued_jobs=%s queued_duration=%s target_seconds=%s available_seconds=%s",
            queued_jobs,
            queued_duration,
            target_seconds,
            unwatched_seconds,
        )
        return {
            "status": "ok",
            "queued_jobs": queued_jobs,
            "queued_duration_seconds": queued_duration,
            "queued_estimated_bytes": queued_bytes,
            "target_seconds": target_seconds,
            "available_seconds": unwatched_seconds,
        }

    def _resolve_duration_seconds(self, video: dict[str, Any]) -> int:
        raw = video.get("duration_seconds")
        if raw is not None:
            try:
                value = int(raw)
                if value > 0:
                    return value
            except (TypeError, ValueError):
                pass
        fallback_minutes = max(1, int(self.config.offline_default_video_minutes))
        return fallback_minutes * 60

    def _estimate_bytes(self, video: dict[str, Any], duration_seconds: int) -> int:
        raw_size = video.get("file_size_bytes")
        if raw_size is not None:
            try:
                size = int(raw_size)
                if size > 0:
                    return size
            except (TypeError, ValueError):
                pass

        mbps = max(0.2, float(self.config.offline_estimated_mbps))
        return int(duration_seconds * mbps * BYTES_PER_MEGABIT)

    def _effective_storage_limit_bytes(self) -> int | None:
        max_gb = max(0.0, float(self.config.storage_max_gb))
        if max_gb <= 0:
            return None
        reserve_gb = max(0.0, float(self.config.storage_reserve_gb))
        usable_gb = max(0.0, max_gb - reserve_gb)
        return int(usable_gb * GIB)
