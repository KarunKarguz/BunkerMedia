from pathlib import Path

from bunkermedia.config import AppConfig
from bunkermedia.database import Database
from bunkermedia.intelligence import build_hash_embedding, cosine_similarity


def test_config_defaults(tmp_path: Path) -> None:
    cfg = AppConfig.from_yaml(tmp_path / "config.yaml")
    assert cfg.max_parallel_downloads >= 1


def test_database_init(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    db.initialize()
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
