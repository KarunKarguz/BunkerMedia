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
