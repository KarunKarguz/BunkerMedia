from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

CURRENT_SCHEMA_VERSION = 7


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
        Migration(4, "video_duration_and_file_size", _migration_video_duration_file_size),
        Migration(5, "profiles_and_profile_state", _migration_profiles_and_profile_state),
        Migration(6, "privacy_vault_support", _migration_privacy_vault_support),
        Migration(7, "download_batch_resume_support", _migration_download_batch_resume_support),
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


def _migration_video_duration_file_size(conn: "sqlite3.Connection") -> None:
    _add_column_if_missing(conn, "videos", "duration_seconds", "INTEGER")
    _add_column_if_missing(conn, "videos", "file_size_bytes", "INTEGER DEFAULT 0")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_videos_duration ON videos(duration_seconds)")


def _migration_profiles_and_profile_state(conn: "sqlite3.Connection") -> None:
    _add_column_if_missing(conn, "watch_history", "profile_id", "TEXT DEFAULT 'default'")
    conn.execute("UPDATE watch_history SET profile_id='default' WHERE profile_id IS NULL OR profile_id=''")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS profiles (
            profile_id TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            is_kids INTEGER DEFAULT 0,
            avatar_color TEXT DEFAULT '#d8b56a',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS profile_video_state (
            profile_id TEXT NOT NULL,
            video_id TEXT NOT NULL,
            watched INTEGER DEFAULT 0,
            liked INTEGER DEFAULT 0,
            disliked INTEGER DEFAULT 0,
            rating REAL DEFAULT 0,
            completed INTEGER DEFAULT 0,
            rejected_reason TEXT,
            total_watch_seconds INTEGER DEFAULT 0,
            updated_at TEXT NOT NULL,
            PRIMARY KEY(profile_id, video_id),
            FOREIGN KEY(profile_id) REFERENCES profiles(profile_id),
            FOREIGN KEY(video_id) REFERENCES videos(video_id)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_watch_history_profile_video ON watch_history(profile_id, video_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_profile_state_profile ON profile_video_state(profile_id, updated_at)")

    row = conn.execute("SELECT COALESCE(MAX(applied_at), '') AS applied_at FROM schema_migrations").fetchone()
    fallback_now = str(row["applied_at"] or "1970-01-01T00:00:00+00:00")
    for profile_id, display_name, is_kids, color in [
        ("default", "Default", 0, "#d8b56a"),
        ("kids", "Kids", 1, "#63d79a"),
    ]:
        conn.execute(
            """
            INSERT OR IGNORE INTO profiles (profile_id, display_name, is_kids, avatar_color, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (profile_id, display_name, is_kids, color, fallback_now, fallback_now),
        )

    conn.execute(
        """
        INSERT OR IGNORE INTO profile_video_state (
            profile_id, video_id, watched, liked, disliked, rating, completed, rejected_reason, total_watch_seconds, updated_at
        )
        SELECT
            'default',
            video_id,
            watched,
            liked,
            disliked,
            rating,
            watched,
            rejected_reason,
            0,
            COALESCE(updated_at, ?)
        FROM videos
        WHERE watched=1 OR liked=1 OR disliked=1 OR rating > 0 OR (rejected_reason IS NOT NULL AND rejected_reason != '')
        """,
        (fallback_now,),
    )


def _migration_privacy_vault_support(conn: "sqlite3.Connection") -> None:
    _add_column_if_missing(conn, "videos", "privacy_level", "TEXT DEFAULT 'standard'")
    conn.execute("UPDATE videos SET privacy_level='standard' WHERE privacy_level IS NULL OR privacy_level=''")
    _add_column_if_missing(conn, "profiles", "can_access_private", "INTEGER DEFAULT 0")
    _add_column_if_missing(conn, "profiles", "pin_hash", "TEXT")
    conn.execute("UPDATE profiles SET can_access_private=0 WHERE can_access_private IS NULL")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_videos_privacy_level ON videos(privacy_level)")


def _migration_download_batch_resume_support(conn: "sqlite3.Connection") -> None:
    _add_column_if_missing(conn, "download_jobs", "batch_id", "INTEGER")
    _add_column_if_missing(conn, "dead_letter_jobs", "batch_id", "INTEGER")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS download_batches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_url TEXT NOT NULL,
            batch_type TEXT NOT NULL,
            title TEXT,
            status TEXT DEFAULT 'queued',
            total_items INTEGER DEFAULT 0,
            completed_items INTEGER DEFAULT 0,
            failed_items INTEGER DEFAULT 0,
            resumed_runs INTEGER DEFAULT 0,
            last_error TEXT,
            last_job_id INTEGER,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS download_batch_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id INTEGER NOT NULL,
            video_id TEXT NOT NULL,
            title TEXT,
            source_url TEXT,
            item_index INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending',
            local_path TEXT,
            last_error TEXT,
            updated_at TEXT NOT NULL,
            UNIQUE(batch_id, video_id),
            FOREIGN KEY(batch_id) REFERENCES download_batches(id),
            FOREIGN KEY(video_id) REFERENCES videos(video_id)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_download_batches_status ON download_batches(status, updated_at)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_download_batch_items_batch ON download_batch_items(batch_id, status, item_index)"
    )


def _add_column_if_missing(conn: "sqlite3.Connection", table: str, column: str, column_spec: str) -> None:
    if _has_column(conn, table, column):
        return
    try:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_spec}")
    except Exception as exc:
        text = str(exc).lower()
        if "duplicate column name" in text:
            return
        raise


def _has_column(conn: "sqlite3.Connection", table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(str(row["name"]) == column for row in rows)
