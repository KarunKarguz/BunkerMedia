from __future__ import annotations

import asyncio
import hashlib
from dataclasses import asdict
from pathlib import Path

from bunkermedia.artwork import ArtworkManager
from bunkermedia.config import AppConfig
from bunkermedia.database import Database
from bunkermedia.downloader import Downloader
from bunkermedia.import_organizer import ImportOrganizer
from bunkermedia.intelligence import IntelligenceEngine
from bunkermedia.library import MediaLibrary
from bunkermedia.logging_utils import setup_logging
from bunkermedia.maintenance import backup_state, restore_state
from bunkermedia.metrics import MetricsRegistry
from bunkermedia.network import NetworkStateManager
from bunkermedia.planner import OfflinePlanner
from bunkermedia.providers import LocalFolderProvider, ProviderRegistry, RSSProvider, YouTubeProvider
from bunkermedia.recommender import RecommendationEngine
from bunkermedia.scraper import Scraper
from bunkermedia.storage_policy import StoragePolicyManager
from bunkermedia.storage_privacy import StoragePrivacyMonitor
from bunkermedia.system_monitor import SystemMonitor
from bunkermedia.workers import WorkerManager


class BunkerService:
    KIDS_BLOCK_KEYWORDS = {
        "kill",
        "killing",
        "murder",
        "violent",
        "violence",
        "gore",
        "blood",
        "horror",
        "terror",
        "nsfw",
        "adult",
        "explicit",
        "weapon",
        "war",
        "crime",
        "drugs",
    }

    def __init__(self, config_path: str | Path = "config.yaml") -> None:
        self.config = AppConfig.from_yaml(config_path)
        self.logger = setup_logging(self.config.logs_dir, mode=self.config.log_format)
        self.metrics = MetricsRegistry()
        self.db = Database(self.config.database_path)
        self.library = MediaLibrary(self.config.download_path)
        self.artwork = ArtworkManager(self.library, self.db, self.logger)
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
        self.offline_planner = OfflinePlanner(self.config, self.db, self.recommender, self.logger)
        self.storage_policy = StoragePolicyManager(self.config, self.db, self.logger)
        self.system_monitor = SystemMonitor(self.config.download_path, self.logger)
        self.storage_privacy = StoragePrivacyMonitor(
            self.config.download_path,
            self.config.private_mode_enabled,
            self.config.private_require_encrypted_store,
            self.config.private_storage_marker_file,
        )
        self.import_organizer = ImportOrganizer(
            self.library,
            self.config.import_watch_folders,
            self.config.import_move_mode,
            self.config.import_scan_limit,
            self.logger,
        )
        self.providers = ProviderRegistry()
        watch_folders = self._local_watch_folders()
        self.providers.register(YouTubeProvider(self.scraper, self.downloader))
        self.providers.register(RSSProvider(self.db, self.downloader, self.logger))
        self.providers.register(LocalFolderProvider(self.db, self.logger, watch_folders))
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
            self.offline_planner,
            self.storage_policy,
            self.import_organizer,
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
        await asyncio.to_thread(self.artwork.backfill_missing, 48, False)
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

        if self.config.auto_organize_imports and self.config.import_watch_folders:
            organized = await self.organize_imports()
            if int(organized.get("organized") or 0) > 0:
                self.metrics.inc("imports_organized_total", float(int(organized.get("organized") or 0)))

        if self._local_watch_folders():
            await self.discover(provider="local", source="default", limit=2000)

        await asyncio.to_thread(self.artwork.backfill_missing, 120, self.network.is_online)

        storage_before = self.enforce_storage_policy()
        if str(storage_before.get("status")) == "ok":
            self.metrics.inc("storage_enforcement_total")

        plan = await self.plan_offline_queue()
        if int(plan.get("queued_jobs") or 0) > 0:
            self.metrics.inc("offline_planner_runs_total")
            self.metrics.inc("offline_planner_queued_jobs_total", int(plan.get("queued_jobs") or 0))

        await self.workers.process_download_queue_once()
        storage_after = self.enforce_storage_policy()
        if str(storage_after.get("status")) == "ok":
            self.metrics.inc("storage_enforcement_total")

        await self.intelligence.refresh_embeddings(limit=self.config.intelligence_batch_size)
        await self.recommender.refresh_scores()
        self.metrics.inc("sync_completed_total")

    async def recommend(self, limit: int = 20, explain: bool = False):
        active = self.get_active_profile()
        profile_id = str(active.get("profile_id") or self.db.DEFAULT_PROFILE_ID)
        is_kids = bool(active.get("is_kids"))
        can_access_private = bool(active.get("can_access_private"))
        return await self.recommender.recommend(
            limit=limit,
            explain=explain,
            profile_id=profile_id,
            is_kids=is_kids,
            can_access_private=can_access_private,
        )

    def list_download_jobs(self, status: str | None = None, limit: int = 100):
        return self.db.list_download_jobs(status=status, limit=limit)

    def list_download_batches(self, status: str | None = None, limit: int = 100):
        return self.db.list_download_batches(limit=limit, status=status)

    def get_download_batch(self, batch_id: int):
        return self.db.get_download_batch(batch_id)

    def list_dead_letter_jobs(self, limit: int = 100):
        return self.db.list_dead_letter_jobs(limit=limit)

    def clear_dead_letter_jobs(self, retried_only: bool = False) -> int:
        return self.db.clear_dead_letter_jobs(retried_only=retried_only)

    def retry_dead_letter(self, dead_letter_id: int) -> int | None:
        return self.db.retry_dead_letter(dead_letter_id)

    def pause_download_job(self, job_id: int) -> bool:
        return self.db.pause_job(job_id)

    def resume_download_job(self, job_id: int) -> bool:
        return self.db.resume_job(job_id)

    def set_download_job_priority(self, job_id: int, priority: int) -> bool:
        return self.db.set_job_priority(job_id, priority)

    def list_videos(
        self,
        limit: int = 100,
        search: str | None = None,
        channel: str | None = None,
        downloaded_only: bool = False,
        freshness_days: int | None = None,
        duration_min: int | None = None,
        duration_max: int | None = None,
    ):
        active = self.get_active_profile()
        upload_date_after = None
        if freshness_days is not None and int(freshness_days) > 0:
            from datetime import datetime, timedelta

            threshold = datetime.utcnow() - timedelta(days=int(freshness_days))
            upload_date_after = threshold.strftime("%Y%m%d")
        rows = self.db.list_videos(
            limit=max(limit * 4, limit),
            search=search,
            profile_id=str(active["profile_id"]),
            channel=channel,
            downloaded_only=downloaded_only,
            upload_date_after=upload_date_after,
            duration_min=duration_min,
            duration_max=duration_max,
        )
        filtered = [row for row in rows if self._video_allowed_for_profile(row, active)]
        return [self._decorate_video_payload(row) for row in filtered[:limit]]

    def list_providers(self) -> list[str]:
        return self.providers.list()

    async def discover(self, provider: str, source: str, limit: int = 50):
        selected = self.providers.get(provider)
        items = await selected.discover(source, limit=limit)
        if items:
            await asyncio.to_thread(
                lambda: [self.artwork.ensure_for_video(asdict(item), allow_remote=False) for item in items[:24]]
            )
        self.metrics.inc(f"provider_discover_{selected.name}_total")
        return items

    async def acquire(self, provider: str, source: str, mode: str = "auto"):
        selected = self.providers.get(provider)
        items = await selected.acquire(source, mode=mode)
        if items:
            await asyncio.to_thread(
                lambda: [self.artwork.ensure_for_video(asdict(item), allow_remote=False) for item in items[:24]]
            )
        self.metrics.inc(f"provider_acquire_{selected.name}_total")
        return items

    def get_video(self, video_id: str):
        active = self.get_active_profile()
        video = self.db.get_video(video_id, profile_id=str(active["profile_id"]))
        if not video or not self._video_allowed_for_profile(video, active):
            return None
        return self._decorate_video_payload(video)

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
        profile = self.get_active_profile()
        self.db.mark_watched(
            video_id,
            profile_id=str(profile["profile_id"]),
            watch_seconds=watch_seconds,
            completed=completed,
            liked=liked,
            disliked=disliked,
            rating=rating,
            notes=notes,
        )
        video = self.db.get_video(video_id, profile_id=str(profile["profile_id"]))
        channel_name = str(video.get("channel") or "").strip().lower() if video else ""
        if channel_name:
            weight: float | None = None
            if liked is True:
                weight = 1.0
            elif disliked is True:
                weight = -1.0
            elif rating is not None:
                weight = max(-1.0, min(1.0, (float(rating) - 2.5) / 2.5))
            if weight is not None:
                self.db.set_preference("channel", channel_name, weight=weight, profile_id=str(profile["profile_id"]))

    def get_stream_path(self, video_id: str) -> Path | None:
        video = self.get_video(video_id)
        if not video:
            return None
        local_path = video.get("local_path")
        if not local_path:
            return None
        path = Path(local_path)
        if not path.exists():
            return None
        return path

    async def get_artwork_bytes(self, video_id: str) -> tuple[bytes, str] | None:
        active = self.get_active_profile()
        video = self.db.get_video(video_id, profile_id=str(active["profile_id"]))
        if not video or not self._video_allowed_for_profile(video, active):
            return None
        artwork_path = await asyncio.to_thread(self.artwork.ensure_for_video, video, self.network.is_online)
        if artwork_path is None or not artwork_path.exists():
            return None
        return artwork_path.read_bytes(), self.artwork.media_type_for_path(artwork_path)

    async def refresh_network_state(self) -> bool:
        online = await self.network.refresh()
        self.metrics.set_gauge("network_online", 1.0 if online else 0.0)
        return online

    async def plan_offline_queue(self) -> dict[str, object]:
        result = await self.offline_planner.plan_once()
        self.metrics.set_gauge("offline_available_seconds", float(int(result.get("available_seconds") or 0)))
        self.metrics.set_gauge("offline_target_seconds", float(int(result.get("target_seconds") or 0)))
        self.metrics.set_gauge("offline_queued_seconds_last", float(int(result.get("queued_duration_seconds") or 0)))
        return result

    def enforce_storage_policy(self) -> dict[str, object]:
        result = self.storage_policy.enforce_once()
        self.metrics.set_gauge("storage_freed_bytes_last", float(int(result.get("freed_bytes") or 0)))
        self.metrics.set_gauge("storage_evicted_files_last", float(int(result.get("evicted_files") or 0)))
        return result

    def get_offline_inventory(self) -> dict[str, int]:
        active = self.get_active_profile()
        rows = self.db.list_videos(limit=5000, search=None, profile_id=str(active["profile_id"]))
        visible = [row for row in rows if self._video_allowed_for_profile(row, active) and int(row.get("downloaded") or 0) == 1]
        return {
            "total_downloaded_items": len(visible),
            "private_items": sum(
                1 for row in visible if str(row.get("privacy_level") or "standard") in {"private", "explicit"}
            ),
            "unwatched_duration_seconds": sum(
                int(row.get("duration_seconds") or 0) for row in visible if int(row.get("watched") or 0) == 0
            ),
            "downloaded_storage_bytes": sum(int(row.get("file_size_bytes") or 0) for row in visible),
        }

    def list_profiles(self) -> list[dict[str, object]]:
        return [self._public_profile(profile) for profile in self.db.list_profiles()]

    def get_active_profile(self) -> dict[str, object]:
        profile = self.db.get_profile(self.db.get_active_profile_id())
        if profile:
            return self._public_profile(profile)
        fallback = self.db.set_active_profile(self.db.DEFAULT_PROFILE_ID)
        return self._public_profile(fallback or {
            "profile_id": self.db.DEFAULT_PROFILE_ID,
            "display_name": "Default",
            "is_kids": False,
            "can_access_private": False,
            "pin_required": False,
            "avatar_color": "#d8b56a",
        })

    def create_profile(
        self,
        display_name: str,
        is_kids: bool = False,
        can_access_private: bool = False,
        pin: str | None = None,
    ) -> dict[str, object]:
        profile = self.db.create_profile(
            display_name=display_name,
            is_kids=is_kids,
            can_access_private=can_access_private,
            pin_hash=self._hash_pin(pin) if pin else None,
        )
        return self._public_profile(profile)

    def update_profile(
        self,
        profile_id: str,
        display_name: str | None = None,
        is_kids: bool | None = None,
        can_access_private: bool | None = None,
        pin: str | None = None,
        clear_pin: bool = False,
    ) -> dict[str, object] | None:
        pin_hash: str | None = None
        if clear_pin:
            pin_hash = ""
        elif pin:
            pin_hash = self._hash_pin(pin)
        profile = self.db.update_profile(
            profile_id=profile_id,
            display_name=display_name,
            is_kids=is_kids,
            can_access_private=can_access_private,
            pin_hash=pin_hash,
        )
        return self._public_profile(profile) if profile else None

    def select_profile(self, profile_id: str, pin: str | None = None) -> dict[str, object] | None:
        profile = self.db.get_profile(profile_id)
        if not profile:
            return None
        expected_hash = str(profile.get("pin_hash") or "")
        if expected_hash:
            if not pin or self._hash_pin(pin) != expected_hash:
                return None
        selected = self.db.set_active_profile(profile_id)
        return self._public_profile(selected) if selected else None

    def get_system_state(self) -> dict[str, object]:
        return self.system_monitor.snapshot()

    def get_privacy_state(self) -> dict[str, object]:
        active = self.get_active_profile()
        snapshot = self.storage_privacy.snapshot()
        snapshot["active_profile"] = {
            "profile_id": active.get("profile_id"),
            "display_name": active.get("display_name"),
            "can_access_private": active.get("can_access_private", False),
            "pin_required": active.get("pin_required", False),
        }
        snapshot["private_items_visible"] = bool(active.get("can_access_private"))
        return snapshot

    def set_video_privacy(self, video_id: str, privacy_level: str) -> bool:
        active = self.get_active_profile()
        if not bool(active.get("can_access_private")):
            return False
        return self.db.set_video_privacy(video_id, privacy_level)

    async def organize_imports(self) -> dict[str, object]:
        result = self.import_organizer.organize_once()
        if int(result.get("organized") or 0) > 0 and self._local_watch_folders():
            await self.discover(provider="local", source="default", limit=2000)
        return result

    def get_health_state(self) -> dict[str, object]:
        return {
            "status": "ok",
            "online": self.network.is_online,
            "in_sync_window": self.network.in_sync_window(),
            "schema_version": self.db.get_schema_version(),
            "providers": self.list_providers(),
            "batches_active": len(self.db.list_download_batches(limit=5000, status="running")),
            "batches_partial": len(self.db.list_download_batches(limit=5000, status="partial")),
            "offline_inventory": self.get_offline_inventory(),
            "active_profile": self.get_active_profile(),
            "privacy": self.get_privacy_state(),
            "system": self.get_system_state(),
        }

    def _local_watch_folders(self) -> list[Path]:
        ordered: list[Path] = []
        seen: set[str] = set()
        for path in [*self.config.local_watch_folders, *self.library.organized_watch_folders()]:
            key = str(path.resolve())
            if key in seen:
                continue
            seen.add(key)
            ordered.append(path)
        return ordered

    @staticmethod
    def _decorate_video_payload(video: dict[str, object]) -> dict[str, object]:
        payload = dict(video)
        video_id = str(payload.get("video_id") or "").strip()
        payload["artwork_url"] = f"/artwork/{video_id}" if video_id else None
        return payload

    def render_metrics(self) -> str:
        self.metrics.set_gauge("queue_pending", float(len(self.db.list_download_jobs(status="pending", limit=5000))))
        self.metrics.set_gauge("queue_processing", float(len(self.db.list_download_jobs(status="processing", limit=5000))))
        self.metrics.set_gauge("queue_dead", float(len(self.db.list_download_jobs(status="dead", limit=5000))))
        self.metrics.set_gauge("deadletter_items", float(len(self.db.list_dead_letter_jobs(limit=5000))))
        self.metrics.set_gauge("download_batches_running", float(len(self.db.list_download_batches(limit=5000, status="running"))))
        self.metrics.set_gauge("download_batches_partial", float(len(self.db.list_download_batches(limit=5000, status="partial"))))
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

    def _video_allowed_for_profile(self, video: dict[str, object], profile: dict[str, object]) -> bool:
        privacy_level = str(video.get("privacy_level") or "standard").lower()
        if privacy_level in {"private", "explicit"} and not bool(profile.get("can_access_private")):
            return False
        if bool(profile.get("is_kids")) and privacy_level == "explicit":
            return False
        if not bool(profile.get("is_kids")):
            return True
        text = " ".join(
            [
                str(video.get("title") or ""),
                str(video.get("channel") or ""),
                str(video.get("source_url") or ""),
                str(video.get("rejected_reason") or ""),
            ]
        ).lower()
        return not any(keyword in text for keyword in self.KIDS_BLOCK_KEYWORDS)

    def _hash_pin(self, pin: str) -> str:
        salt = str(self.config.database_path).encode("utf-8")
        derived = hashlib.pbkdf2_hmac("sha256", pin.strip().encode("utf-8"), salt, 120000)
        return derived.hex()

    @staticmethod
    def _public_profile(profile: dict[str, object] | None) -> dict[str, object]:
        if not profile:
            return {}
        payload = dict(profile)
        payload.pop("pin_hash", None)
        return payload
