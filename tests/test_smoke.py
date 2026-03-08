from pathlib import Path
import asyncio

from bunkermedia.config import AppConfig
from bunkermedia.database import Database
from bunkermedia.intelligence import build_hash_embedding, cosine_similarity
from bunkermedia.maintenance import backup_state, restore_state
from bunkermedia.models import Recommendation, VideoMetadata
from bunkermedia.network import NetworkStateManager
from bunkermedia.planner import OfflinePlanner
from bunkermedia.service import BunkerService
from bunkermedia.storage_policy import StoragePolicyManager


def test_config_defaults(tmp_path: Path) -> None:
    cfg = AppConfig.from_yaml(tmp_path / "config.yaml")
    assert cfg.max_parallel_downloads >= 1


def test_database_init(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    db.initialize()
    assert db.get_schema_version() >= 4
    db.close()


def test_embedding_shape_and_similarity() -> None:
    vec_a = build_hash_embedding("python async fastapi media", dim=64)
    vec_b = build_hash_embedding("python fastapi streaming", dim=64)
    vec_c = build_hash_embedding("gardening soil compost", dim=64)

    assert len(vec_a) == 64
    assert len(vec_b) == 64
    assert len(vec_c) == 64
    assert cosine_similarity(vec_a, vec_b) > cosine_similarity(vec_a, vec_c)


def test_download_retry_and_dead_letter_flow(tmp_path: Path) -> None:
    db = Database(tmp_path / "queue.db")
    db.initialize()

    job_id = db.queue_download("https://www.youtube.com/watch?v=abc123", target_type="single", priority=1)
    claimed = db.claim_pending_jobs(limit=5)
    assert len(claimed) == 1
    assert int(claimed[0]["id"]) == job_id
    assert int(claimed[0]["attempts"]) == 1

    db.requeue_job_with_backoff(job_id, error="temporary failure", delay_seconds=60)
    assert db.claim_pending_jobs(limit=5) == []

    pending_jobs = db.list_download_jobs(status="pending", limit=5)
    assert len(pending_jobs) == 1
    assert pending_jobs[0]["last_error"] == "temporary failure"
    assert pending_jobs[0]["next_run_at"] is not None

    db.dead_letter_job(job_id, error="permanent failure")
    dead_jobs = db.list_dead_letter_jobs(limit=5)
    assert len(dead_jobs) == 1
    assert int(dead_jobs[0]["original_job_id"]) == job_id
    assert dead_jobs[0]["last_error"] == "permanent failure"

    retried_job_id = db.retry_dead_letter(int(dead_jobs[0]["id"]))
    assert retried_job_id is not None
    assert retried_job_id != job_id

    db.close()


def test_backup_restore_roundtrip(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        "\n".join(
            [
                "download_path: ./media",
                "database_path: ./bunkermedia.db",
                "download_archive: ./archive.txt",
                "backup_path: ./backups",
            ]
        ),
        encoding="utf-8",
    )
    cfg = AppConfig.from_yaml(cfg_path)

    db = Database(cfg.database_path)
    db.initialize()
    db.queue_download("https://www.youtube.com/watch?v=seed", target_type="single")
    db.close()
    cfg.download_archive.write_text("seed\n", encoding="utf-8")

    backup_file = backup_state(cfg, output_dir=cfg.backup_path)
    assert backup_file.exists()

    cfg.database_path.unlink(missing_ok=True)
    restore_state(cfg, archive_path=backup_file, force=False)
    assert cfg.database_path.exists()


def test_sync_window_logic(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        "\n".join(
            [
                "download_path: ./media",
                "database_path: ./bunkermedia.db",
                "download_archive: ./archive.txt",
                "sync_windows:",
                "  - \"09:00-11:00\"",
                "  - \"22:00-02:00\"",
                "force_offline_mode: false",
            ]
        ),
        encoding="utf-8",
    )
    cfg = AppConfig.from_yaml(cfg_path)
    manager = NetworkStateManager(cfg, logger=type("L", (), {"info": lambda *a, **k: None})())

    from datetime import datetime

    assert manager.in_sync_window(datetime(2026, 3, 8, 9, 30).astimezone())
    assert not manager.in_sync_window(datetime(2026, 3, 8, 14, 30).astimezone())
    assert manager.in_sync_window(datetime(2026, 3, 8, 23, 30).astimezone())


def test_schema_migrations_list(tmp_path: Path) -> None:
    db = Database(tmp_path / "schema.db")
    db.initialize()
    migrations = db.list_schema_migrations()
    assert len(migrations) >= 4
    assert migrations[-1]["version"] >= 4
    db.close()


def test_service_provider_registry(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        "\n".join(
            [
                "download_path: ./media",
                "database_path: ./bunkermedia.db",
                "download_archive: ./archive.txt",
                "force_offline_mode: true",
                "auto_start_workers: false",
            ]
        ),
        encoding="utf-8",
    )

    async def _run() -> None:
        service = BunkerService(cfg_path)
        await service.initialize()
        providers = service.list_providers()
        assert "youtube" in providers
        health = service.get_health_state()
        assert int(health["schema_version"]) >= 3
        await service.shutdown()

    asyncio.run(_run())


def test_offline_planner_queues_to_target(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        "\n".join(
            [
                "download_path: ./media",
                "database_path: ./planner.db",
                "download_archive: ./archive.txt",
                "offline_target_hours: 1",
                "offline_planner_batch_size: 5",
                "offline_default_video_minutes: 20",
                "offline_queue_priority: 4",
            ]
        ),
        encoding="utf-8",
    )
    cfg = AppConfig.from_yaml(cfg_path)
    db = Database(cfg.database_path)
    db.initialize()
    db.upsert_video(
        VideoMetadata(
            video_id="seed_1",
            title="Seed 1",
            channel="Test",
            source_url="https://example.invalid/1",
            duration_seconds=1800,
            downloaded=False,
        )
    )
    db.upsert_video(
        VideoMetadata(
            video_id="seed_2",
            title="Seed 2",
            channel="Test",
            source_url="https://example.invalid/2",
            duration_seconds=2000,
            downloaded=False,
        )
    )

    class _FakeRecommender:
        async def recommend(self, limit: int = 20, explain: bool = False):
            return [
                Recommendation("seed_1", "Seed 1", "Test", 1.0, False, None),
                Recommendation("seed_2", "Seed 2", "Test", 0.9, False, None),
            ]

    planner = OfflinePlanner(cfg, db, _FakeRecommender(), logger=type("L", (), {"info": lambda *a, **k: None})())
    result = asyncio.run(planner.plan_once())
    assert result["status"] == "ok"
    assert int(result["queued_jobs"]) >= 2
    jobs = db.list_download_jobs(status="pending", limit=10)
    assert len(jobs) >= 2
    db.close()


def test_storage_policy_enforces_budget(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        "\n".join(
            [
                "download_path: ./media",
                "database_path: ./storage.db",
                "download_archive: ./archive.txt",
                "storage_max_gb: 0.000001",
                "storage_eviction_batch_size: 5",
                "storage_protect_liked: true",
                "storage_eviction_policy: watched_oldest",
            ]
        ),
        encoding="utf-8",
    )
    cfg = AppConfig.from_yaml(cfg_path)
    db = Database(cfg.database_path)
    db.initialize()

    media_root = tmp_path / "media"
    media_root.mkdir(parents=True, exist_ok=True)
    keep_file = media_root / "keep.mp4"
    evict_file = media_root / "evict.mp4"
    keep_file.write_bytes(b"a" * 800)
    evict_file.write_bytes(b"b" * 800)

    db.upsert_video(
        VideoMetadata(
            video_id="keep",
            title="Keep",
            channel="Test",
            local_path=str(keep_file),
            file_size_bytes=800,
            downloaded=True,
        )
    )
    db.mark_downloaded("keep", str(keep_file), file_size_bytes=800)
    db.mark_watched("keep", liked=True, completed=True, watch_seconds=120)

    db.upsert_video(
        VideoMetadata(
            video_id="evict",
            title="Evict",
            channel="Test",
            local_path=str(evict_file),
            file_size_bytes=800,
            downloaded=True,
        )
    )
    db.mark_downloaded("evict", str(evict_file), file_size_bytes=800)
    db.mark_watched("evict", liked=False, completed=True, watch_seconds=120)

    manager = StoragePolicyManager(cfg, db, logger=type("L", (), {"info": lambda *a, **k: None})())
    result = manager.enforce_once()
    assert result["status"] == "ok"
    assert int(result["evicted_files"]) >= 1
    assert keep_file.exists()
    assert not evict_file.exists()
    assert int(db.get_video("evict")["downloaded"]) == 0
    db.close()
