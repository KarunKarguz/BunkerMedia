from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

CURRENT_SCHEMA_VERSION = 3


@dataclass(frozen=True, slots=True)
class Migration:
    version: int
    name: str
    fn: Callable[["sqlite3.Connection"], None]


def apply_migrations(conn: "sqlite3.Connection", utc_now: str) -> int:
    _ensure_migration_table(conn)
    applied = _get_applied_versions(conn)

    for migration in _ordered_migrations():
        if migration.version in applied:
            continue
        migration.fn(conn)
        conn.execute(
            """
            INSERT INTO schema_migrations (version, name, applied_at)
            VALUES (?, ?, ?)
            """,
            (migration.version, migration.name, utc_now),
        )

    row = conn.execute("SELECT COALESCE(MAX(version), 0) AS v FROM schema_migrations").fetchone()
    return int(row["v"] if row and row["v"] is not None else 0)


def get_schema_version(conn: "sqlite3.Connection") -> int:
    _ensure_migration_table(conn)
    row = conn.execute("SELECT COALESCE(MAX(version), 0) AS v FROM schema_migrations").fetchone()
    return int(row["v"] if row and row["v"] is not None else 0)


def list_migrations(conn: "sqlite3.Connection") -> list[dict[str, object]]:
    _ensure_migration_table(conn)
    rows = conn.execute(
        "SELECT version, name, applied_at FROM schema_migrations ORDER BY version ASC"
    ).fetchall()
    return [
        {
            "version": int(row["version"]),
            "name": str(row["name"]),
            "applied_at": str(row["applied_at"]),
        }
        for row in rows
    ]


def _ordered_migrations() -> list[Migration]:
    return [
        Migration(1, "create_video_intelligence", _migration_create_video_intelligence),
        Migration(2, "download_retry_and_deadletter", _migration_download_retry_deadletter),
        Migration(3, "download_next_run_index", _migration_next_run_index),
    ]


def _ensure_migration_table(conn: "sqlite3.Connection") -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL
        )
        """
    )


def _get_applied_versions(conn: "sqlite3.Connection") -> set[int]:
    rows = conn.execute("SELECT version FROM schema_migrations").fetchall()
    return {int(row["version"]) for row in rows}


def _migration_create_video_intelligence(conn: "sqlite3.Connection") -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS video_intelligence (
            video_id TEXT PRIMARY KEY,
            content_text TEXT NOT NULL,
            transcript_source TEXT DEFAULT 'metadata',
            embedding_json TEXT NOT NULL,
            embedding_dim INTEGER NOT NULL,
            quality_score REAL DEFAULT 0,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(video_id) REFERENCES videos(video_id)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_intel_quality ON video_intelligence(quality_score)")


def _migration_download_retry_deadletter(conn: "sqlite3.Connection") -> None:
    if not _has_column(conn, "download_jobs", "next_run_at"):
        conn.execute("ALTER TABLE download_jobs ADD COLUMN next_run_at TEXT")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS dead_letter_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_job_id INTEGER,
            url TEXT NOT NULL,
            target_type TEXT DEFAULT 'auto',
            priority INTEGER DEFAULT 0,
            attempts INTEGER DEFAULT 0,
            last_error TEXT,
            failed_at TEXT NOT NULL,
            retried_at TEXT
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_dead_failed_at ON dead_letter_jobs(failed_at)")


def _migration_next_run_index(conn: "sqlite3.Connection") -> None:
    conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_next_run ON download_jobs(next_run_at)")


def _has_column(conn: "sqlite3.Connection", table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(str(row["name"]) == column for row in rows)
