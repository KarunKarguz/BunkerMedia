from __future__ import annotations

from pathlib import Path
from typing import Any

from bunkermedia.config import AppConfig
from bunkermedia.database import Database

GIB = 1024**3


class StoragePolicyManager:
    def __init__(self, config: AppConfig, db: Database, logger: Any) -> None:
        self.config = config
        self.db = db
        self.logger = logger

    def enforce_once(self) -> dict[str, int | str | bool]:
        max_gb = max(0.0, float(self.config.storage_max_gb))
        if max_gb <= 0:
            return {"status": "disabled", "evicted_files": 0, "freed_bytes": 0}

        hard_limit_bytes = int(max_gb * GIB)
        inventory = self.db.get_offline_inventory_stats()
        current_bytes = int(inventory["downloaded_storage_bytes"])
        if current_bytes <= hard_limit_bytes:
            return {
                "status": "within_budget",
                "evicted_files": 0,
                "freed_bytes": 0,
                "storage_bytes": current_bytes,
                "storage_limit_bytes": hard_limit_bytes,
            }

        candidates = self.db.list_storage_candidates(limit=max(200, int(self.config.storage_eviction_batch_size) * 20))
        ordered = self._order_candidates(candidates)
        batch_limit = max(1, int(self.config.storage_eviction_batch_size))

        evicted = 0
        freed = 0
        errors = 0

        for item in ordered:
            if evicted >= batch_limit:
                break
            if current_bytes - freed <= hard_limit_bytes:
                break
            if bool(self.config.storage_protect_liked) and int(item.get("liked") or 0) == 1:
                continue

            video_id = str(item.get("video_id") or "").strip()
            local_path = str(item.get("local_path") or "").strip()
            if not video_id:
                continue
            if not local_path:
                self.db.clear_downloaded_state(video_id)
                continue

            path = Path(local_path)
            size = self._resolve_size_bytes(item, path)
            if path.exists():
                try:
                    path.unlink()
                except OSError:
                    errors += 1
                    continue

            self.db.clear_downloaded_state(video_id)
            evicted += 1
            freed += size

        self.logger.info(
            "Storage policy complete evicted=%s freed_bytes=%s limit_bytes=%s current_bytes=%s errors=%s",
            evicted,
            freed,
            hard_limit_bytes,
            current_bytes,
            errors,
        )

        return {
            "status": "ok",
            "evicted_files": evicted,
            "freed_bytes": freed,
            "errors": errors,
            "storage_bytes": current_bytes,
            "storage_limit_bytes": hard_limit_bytes,
            "remaining_overage_bytes": max(0, current_bytes - freed - hard_limit_bytes),
        }

    def _order_candidates(self, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        policy = str(self.config.storage_eviction_policy or "watched_oldest").strip().lower()
        if policy == "low_score":
            return sorted(candidates, key=self._low_score_key)
        return sorted(candidates, key=self._watched_oldest_key)

    @staticmethod
    def _watched_oldest_key(item: dict[str, Any]) -> tuple[Any, ...]:
        rejected_rank = 0 if str(item.get("rejected_reason") or "").strip() else 1
        disliked_rank = 0 if int(item.get("disliked") or 0) == 1 else 1
        watched_rank = 0 if int(item.get("watched") or 0) == 1 else 1
        liked_rank = 1 if int(item.get("liked") or 0) == 1 else 0
        updated_at = str(item.get("updated_at") or "")
        return (rejected_rank, disliked_rank, watched_rank, liked_rank, updated_at)

    @staticmethod
    def _low_score_key(item: dict[str, Any]) -> tuple[Any, ...]:
        rejected_rank = 0 if str(item.get("rejected_reason") or "").strip() else 1
        disliked_rank = 0 if int(item.get("disliked") or 0) == 1 else 1
        liked_rank = 1 if int(item.get("liked") or 0) == 1 else 0
        score = (
            float(item.get("rating") or 0.0)
            + float(item.get("channel_preference") or 0.0)
            + float(item.get("watch_score") or 0.0)
            + float(item.get("trending_score") or 0.0)
        )
        updated_at = str(item.get("updated_at") or "")
        return (rejected_rank, disliked_rank, liked_rank, score, updated_at)

    @staticmethod
    def _resolve_size_bytes(item: dict[str, Any], path: Path) -> int:
        raw = item.get("file_size_bytes")
        if raw is not None:
            try:
                value = int(raw)
                if value > 0:
                    return value
            except (TypeError, ValueError):
                pass
        try:
            return int(path.stat().st_size)
        except OSError:
            return 0
