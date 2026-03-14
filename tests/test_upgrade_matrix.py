from __future__ import annotations

import sqlite3
from pathlib import Path

from bunkermedia.database import Database
from bunkermedia.migrations import CURRENT_SCHEMA_VERSION, _ensure_migration_table, _ordered_migrations

BASE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS videos (
    video_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    channel TEXT,
    upload_date TEXT,
    source_url TEXT,
    local_path TEXT,
    downloaded INTEGER DEFAULT 0,
    watched INTEGER DEFAULT 0,
    liked INTEGER DEFAULT 0,
    disliked INTEGER DEFAULT 0,
    rating REAL DEFAULT 0,
    rejected_reason TEXT,
    trending_score REAL DEFAULT 0,
    channel_preference REAL DEFAULT 0,
    watch_score REAL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS watch_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id TEXT NOT NULL,
    watched_at TEXT NOT NULL,
    watch_seconds INTEGER DEFAULT 0,
    completed INTEGER DEFAULT 0,
    liked INTEGER DEFAULT 0,
    disliked INTEGER DEFAULT 0,
    rating REAL,
    notes TEXT,
    FOREIGN KEY(video_id) REFERENCES videos(video_id)
);

CREATE TABLE IF NOT EXISTS preferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pref_type TEXT NOT NULL,
    pref_key TEXT NOT NULL,
    pref_value TEXT,
    weight REAL DEFAULT 1.0,
    updated_at TEXT NOT NULL,
    UNIQUE(pref_type, pref_key)
);

CREATE TABLE IF NOT EXISTS download_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL,
    target_type TEXT DEFAULT 'auto',
    status TEXT DEFAULT 'pending',
    priority INTEGER DEFAULT 0,
    attempts INTEGER DEFAULT 0,
    last_error TEXT,
    added_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def _seed_video(conn: sqlite3.Connection) -> None:
    columns = [str(row[1]) for row in conn.execute("PRAGMA table_info(videos)").fetchall()]
    values: dict[str, object] = {
        "video_id": "seed-video",
        "title": "Upgrade Seed",
        "channel": "Migration Lab",
        "upload_date": "20260314",
        "source_url": "https://example.invalid/seed",
        "local_path": None,
        "thumbnail_url": None,
        "artwork_path": None,
        "duration_seconds": 123,
        "file_size_bytes": 456,
        "downloaded": 0,
        "watched": 0,
        "liked": 0,
        "disliked": 0,
        "rating": 0.0,
        "rejected_reason": None,
        "privacy_level": "standard",
        "trending_score": 0.0,
        "channel_preference": 0.0,
        "watch_score": 0.0,
        "created_at": "2026-03-14T00:00:00+00:00",
        "updated_at": "2026-03-14T00:00:00+00:00",
    }
    selected_columns = [column for column in columns if column in values]
    placeholders = ", ".join("?" for _ in selected_columns)
    conn.execute(
        f"INSERT INTO videos ({', '.join(selected_columns)}) VALUES ({placeholders})",
        [values[column] for column in selected_columns],
    )


def _build_snapshot(path: Path, version: int) -> None:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(BASE_SCHEMA_SQL)
    _ensure_migration_table(conn)
    applied_at = "2026-03-14T00:00:00+00:00"
    for migration in _ordered_migrations():
        if migration.version > version:
            break
        migration.fn(conn)
        conn.execute(
            "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
            (migration.version, migration.name, applied_at),
        )
    _seed_video(conn)
    conn.commit()
    conn.close()


def test_upgrade_matrix_historical_versions(tmp_path: Path) -> None:
    for version in range(0, CURRENT_SCHEMA_VERSION):
        db_path = tmp_path / f"schema_v{version}.db"
        _build_snapshot(db_path, version)
        db = Database(db_path)
        db.initialize()
        assert db.get_schema_version() == CURRENT_SCHEMA_VERSION
        video = db.get_video("seed-video")
        assert video is not None
        assert video["title"] == "Upgrade Seed"
        assert len(db.list_profiles()) >= 2
        migrations = db.list_schema_migrations()
        assert migrations[-1]["version"] == CURRENT_SCHEMA_VERSION
        db.close()
