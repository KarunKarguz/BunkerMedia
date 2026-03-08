from pathlib import Path
import asyncio

from bunkermedia.config import AppConfig
from bunkermedia.database import Database
from bunkermedia.intelligence import build_hash_embedding, cosine_similarity
from bunkermedia.maintenance import backup_state, restore_state
from bunkermedia.network import NetworkStateManager
from bunkermedia.service import BunkerService


def test_config_defaults(tmp_path: Path) -> None:
    cfg = AppConfig.from_yaml(tmp_path / "config.yaml")
    assert cfg.max_parallel_downloads >= 1


def test_database_init(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    db.initialize()
    assert db.get_schema_version() >= 3
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
    assert len(migrations) >= 3
    assert migrations[-1]["version"] >= 3
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
