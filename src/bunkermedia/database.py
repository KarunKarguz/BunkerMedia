from __future__ import annotations

import json
import re
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from bunkermedia.migrations import apply_migrations, get_schema_version, list_migrations
from bunkermedia.models import UserProfile, VideoMetadata


class Database:
    DEFAULT_PROFILE_ID = "default"

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

    def initialize(self) -> None:
        with self._lock:
            self.conn.executescript(
                """
                PRAGMA journal_mode=WAL;
                PRAGMA synchronous=NORMAL;

                CREATE TABLE IF NOT EXISTS videos (
                    video_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    channel TEXT,
                    upload_date TEXT,
                    source_url TEXT,
                    local_path TEXT,
                    duration_seconds INTEGER,
                    file_size_bytes INTEGER DEFAULT 0,
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

                CREATE INDEX IF NOT EXISTS idx_videos_channel ON videos(channel);
                CREATE INDEX IF NOT EXISTS idx_videos_downloaded ON videos(downloaded);
                CREATE INDEX IF NOT EXISTS idx_jobs_status ON download_jobs(status);
                CREATE INDEX IF NOT EXISTS idx_history_video ON watch_history(video_id);
                """
            )
            apply_migrations(self.conn, utc_now=self._utc_now())
            self._ensure_profile_defaults()
            self.conn.commit()

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def get_schema_version(self) -> int:
        with self._lock:
            return get_schema_version(self.conn)

    def list_schema_migrations(self) -> list[dict[str, object]]:
        with self._lock:
            return list_migrations(self.conn)

    def _ensure_profile_defaults(self) -> None:
        now = self._utc_now()
        for profile_id, display_name, is_kids, color in [
            ("default", "Default", 0, "#d8b56a"),
            ("kids", "Kids", 1, "#63d79a"),
        ]:
            self.conn.execute(
                """
                INSERT OR IGNORE INTO profiles (profile_id, display_name, is_kids, avatar_color, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (profile_id, display_name, is_kids, color, now, now),
            )

    def list_profiles(self) -> list[dict[str, Any]]:
        active_profile_id = self.get_active_profile_id()
        with self._lock:
            rows = self.conn.execute(
                """
                SELECT
                    p.profile_id,
                    p.display_name,
                    p.is_kids,
                    p.avatar_color,
                    p.created_at,
                    p.updated_at,
                    COALESCE(COUNT(ps.video_id), 0) AS touched_items,
                    COALESCE(SUM(CASE WHEN ps.watched=1 THEN 1 ELSE 0 END), 0) AS watched_items
                FROM profiles p
                LEFT JOIN profile_video_state ps ON ps.profile_id=p.profile_id
                GROUP BY p.profile_id, p.display_name, p.is_kids, p.avatar_color, p.created_at, p.updated_at
                ORDER BY p.created_at ASC, p.profile_id ASC
                """
            ).fetchall()
        return [
            {
                "profile_id": str(row["profile_id"]),
                "display_name": str(row["display_name"]),
                "is_kids": bool(row["is_kids"]),
                "avatar_color": str(row["avatar_color"] or "#d8b56a"),
                "created_at": str(row["created_at"]),
                "updated_at": str(row["updated_at"]),
                "touched_items": int(row["touched_items"] or 0),
                "watched_items": int(row["watched_items"] or 0),
                "is_active": str(row["profile_id"]) == active_profile_id,
            }
            for row in rows
        ]

    def get_profile(self, profile_id: str) -> dict[str, Any] | None:
        normalized = (profile_id or "").strip().lower()
        if not normalized:
            return None
        with self._lock:
            row = self.conn.execute(
                """
                SELECT profile_id, display_name, is_kids, avatar_color, created_at, updated_at
                FROM profiles
                WHERE profile_id=?
                """,
                (normalized,),
            ).fetchone()
        if not row:
            return None
        return {
            "profile_id": str(row["profile_id"]),
            "display_name": str(row["display_name"]),
            "is_kids": bool(row["is_kids"]),
            "avatar_color": str(row["avatar_color"] or "#d8b56a"),
            "created_at": str(row["created_at"]),
            "updated_at": str(row["updated_at"]),
        }

    def create_profile(self, display_name: str, is_kids: bool = False) -> dict[str, Any]:
        now = self._utc_now()
        base_slug = self._slugify_profile_id(display_name) or f"profile-{int(datetime.now().timestamp())}"
        profile_id = base_slug
        suffix = 2
        with self._lock:
            while self.conn.execute("SELECT 1 FROM profiles WHERE profile_id=?", (profile_id,)).fetchone():
                profile_id = f"{base_slug}-{suffix}"
                suffix += 1
            color = "#63d79a" if is_kids else "#d8b56a"
            self.conn.execute(
                """
                INSERT INTO profiles (profile_id, display_name, is_kids, avatar_color, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (profile_id, display_name.strip(), int(is_kids), color, now, now),
            )
            self.conn.commit()
        return self.get_profile(profile_id) or {}

    def update_profile(
        self,
        profile_id: str,
        display_name: str | None = None,
        is_kids: bool | None = None,
    ) -> dict[str, Any] | None:
        normalized = (profile_id or "").strip().lower()
        current = self.get_profile(normalized)
        if not current:
            return None
        updated_name = display_name.strip() if display_name and display_name.strip() else current["display_name"]
        updated_is_kids = int(current["is_kids"] if is_kids is None else bool(is_kids))
        updated_color = "#63d79a" if updated_is_kids else str(current["avatar_color"] or "#d8b56a")
        with self._lock:
            self.conn.execute(
                """
                UPDATE profiles
                SET display_name=?, is_kids=?, avatar_color=?, updated_at=?
                WHERE profile_id=?
                """,
                (updated_name, updated_is_kids, updated_color, self._utc_now(), normalized),
            )
            self.conn.commit()
        return self.get_profile(normalized)

    def get_active_profile_id(self) -> str:
        with self._lock:
            row = self.conn.execute(
                """
                SELECT pref_value
                FROM preferences
                WHERE pref_type='system' AND pref_key='active_profile'
                LIMIT 1
                """
            ).fetchone()
        value = str(row["pref_value"]).strip().lower() if row and row["pref_value"] else self.DEFAULT_PROFILE_ID
        return value or self.DEFAULT_PROFILE_ID

    def set_active_profile(self, profile_id: str) -> dict[str, Any] | None:
        profile = self.get_profile(profile_id)
        if not profile:
            return None
        self.set_preference("system", "active_profile", pref_value=str(profile["profile_id"]), weight=1.0)
        return self.get_profile(str(profile["profile_id"]))

    @staticmethod
    def _slugify_profile_id(value: str) -> str:
        normalized = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
        return normalized[:40]

    def upsert_video(self, meta: VideoMetadata) -> None:
        now = self._utc_now()
        with self._lock:
            self.conn.execute(
                """
                INSERT INTO videos (
                    video_id, title, channel, upload_date, source_url, local_path,
                    duration_seconds, file_size_bytes, downloaded, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(video_id) DO UPDATE SET
                    title=excluded.title,
                    channel=excluded.channel,
                    upload_date=COALESCE(excluded.upload_date, videos.upload_date),
                    source_url=COALESCE(excluded.source_url, videos.source_url),
                    local_path=COALESCE(excluded.local_path, videos.local_path),
                    duration_seconds=COALESCE(excluded.duration_seconds, videos.duration_seconds),
                    file_size_bytes=MAX(videos.file_size_bytes, COALESCE(excluded.file_size_bytes, 0)),
                    downloaded=MAX(videos.downloaded, excluded.downloaded),
                    updated_at=excluded.updated_at
                """,
                (
                    meta.video_id,
                    meta.title,
                    meta.channel,
                    meta.upload_date,
                    meta.source_url,
                    meta.local_path,
                    int(meta.duration_seconds) if meta.duration_seconds is not None else None,
                    int(meta.file_size_bytes) if meta.file_size_bytes is not None else 0,
                    int(meta.downloaded),
                    now,
                    now,
                ),
            )
            self.conn.commit()

    def mark_downloaded(self, video_id: str, local_path: str, file_size_bytes: int | None = None) -> None:
        size = file_size_bytes
        if size is None:
            try:
                size = int(Path(local_path).stat().st_size)
            except OSError:
                size = 0
        with self._lock:
            self.conn.execute(
                """
                UPDATE videos
                SET downloaded=1, local_path=?, file_size_bytes=COALESCE(?, file_size_bytes), updated_at=?
                WHERE video_id=?
                """,
                (local_path, size, self._utc_now(), video_id),
            )
            self.conn.commit()

    def clear_downloaded_state(self, video_id: str) -> None:
        with self._lock:
            self.conn.execute(
                """
                UPDATE videos
                SET downloaded=0, local_path=NULL, file_size_bytes=0, updated_at=?
                WHERE video_id=?
                """,
                (self._utc_now(), video_id),
            )
            self.conn.commit()

    def mark_watched(
        self,
        video_id: str,
        profile_id: str = DEFAULT_PROFILE_ID,
        watch_seconds: int = 0,
        completed: bool = True,
        liked: bool | None = None,
        disliked: bool | None = None,
        rating: float | None = None,
        notes: str | None = None,
    ) -> None:
        now = self._utc_now()
        normalized_profile = (profile_id or self.DEFAULT_PROFILE_ID).strip().lower() or self.DEFAULT_PROFILE_ID
        with self._lock:
            self.conn.execute(
                """
                INSERT INTO watch_history (
                    profile_id, video_id, watched_at, watch_seconds, completed, liked, disliked, rating, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    normalized_profile,
                    video_id,
                    now,
                    watch_seconds,
                    int(completed),
                    int(bool(liked)) if liked is not None else 0,
                    int(bool(disliked)) if disliked is not None else 0,
                    rating,
                    notes,
                ),
            )
            existing = self.conn.execute(
                """
                SELECT watched, liked, disliked, rating, completed, rejected_reason, total_watch_seconds
                FROM profile_video_state
                WHERE profile_id=? AND video_id=?
                """,
                (normalized_profile, video_id),
            ).fetchone()
            total_watch_seconds = int(watch_seconds or 0)
            if existing:
                total_watch_seconds += int(existing["total_watch_seconds"] or 0)
            watched_value = 1 if completed or int(watch_seconds or 0) > 0 else int(existing["watched"] or 0) if existing else 0
            liked_value = int(bool(liked)) if liked is not None else int(existing["liked"] or 0) if existing else 0
            disliked_value = (
                int(bool(disliked)) if disliked is not None else int(existing["disliked"] or 0) if existing else 0
            )
            rating_value = rating if rating is not None else float(existing["rating"] or 0.0) if existing else 0.0
            completed_value = 1 if completed else int(existing["completed"] or 0) if existing else 0
            rejected_reason_value = str(existing["rejected_reason"]) if existing and existing["rejected_reason"] else None
            self.conn.execute(
                """
                INSERT INTO profile_video_state (
                    profile_id, video_id, watched, liked, disliked, rating, completed,
                    rejected_reason, total_watch_seconds, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(profile_id, video_id) DO UPDATE SET
                    watched=excluded.watched,
                    liked=excluded.liked,
                    disliked=excluded.disliked,
                    rating=excluded.rating,
                    completed=excluded.completed,
                    rejected_reason=COALESCE(profile_video_state.rejected_reason, excluded.rejected_reason),
                    total_watch_seconds=excluded.total_watch_seconds,
                    updated_at=excluded.updated_at
                """,
                (
                    normalized_profile,
                    video_id,
                    watched_value,
                    liked_value,
                    disliked_value,
                    rating_value,
                    completed_value,
                    rejected_reason_value,
                    total_watch_seconds,
                    now,
                ),
            )
            self.conn.execute(
                """
                UPDATE videos
                SET watched=1,
                    liked=COALESCE(?, liked),
                    disliked=COALESCE(?, disliked),
                    rating=COALESCE(?, rating),
                    updated_at=?
                WHERE video_id=?
                """,
                (
                    int(liked) if liked is not None else None,
                    int(disliked) if disliked is not None else None,
                    rating,
                    now,
                    video_id,
                ),
            )
            self.conn.commit()

    def queue_download(self, url: str, target_type: str = "auto", priority: int = 0) -> int:
        now = self._utc_now()
        with self._lock:
            existing = self.conn.execute(
                """
                SELECT id FROM download_jobs
                WHERE url=? AND status IN ('pending', 'processing')
                ORDER BY id DESC LIMIT 1
                """,
                (url,),
            ).fetchone()
            if existing:
                return int(existing["id"])

            cursor = self.conn.execute(
                """
                INSERT INTO download_jobs (
                    url, target_type, status, priority, attempts, next_run_at, added_at, updated_at
                )
                VALUES (?, ?, 'pending', ?, 0, ?, ?, ?)
                """,
                (url, target_type, priority, now, now, now),
            )
            self.conn.commit()
            return int(cursor.lastrowid)

    def claim_pending_jobs(self, limit: int) -> list[dict[str, Any]]:
        with self._lock:
            now = self._utc_now()
            rows = self.conn.execute(
                """
                SELECT id, url, target_type, status, priority, attempts, next_run_at
                FROM download_jobs
                WHERE status='pending' AND (next_run_at IS NULL OR next_run_at <= ?)
                ORDER BY priority DESC, id ASC
                LIMIT ?
                """,
                (now, limit),
            ).fetchall()
            if not rows:
                return []

            ids = [int(row["id"]) for row in rows]
            placeholders = ",".join("?" for _ in ids)
            params: list[Any] = [now, *ids]
            self.conn.execute(
                f"""
                UPDATE download_jobs
                SET status='processing', attempts=attempts + 1, next_run_at=NULL, updated_at=?
                WHERE id IN ({placeholders})
                """,
                params,
            )
            self.conn.commit()
            claimed: list[dict[str, Any]] = []
            for row in rows:
                record = dict(row)
                record["attempts"] = int(row["attempts"]) + 1
                claimed.append(record)
            return claimed

    def update_job_status(self, job_id: int, status: str, error: str | None = None) -> None:
        with self._lock:
            self.conn.execute(
                """
                UPDATE download_jobs
                SET status=?, last_error=?, next_run_at=NULL, updated_at=?
                WHERE id=?
                """,
                (status, error, self._utc_now(), job_id),
            )
            self.conn.commit()

    def set_job_priority(self, job_id: int, priority: int) -> bool:
        with self._lock:
            cursor = self.conn.execute(
                """
                UPDATE download_jobs
                SET priority=?, updated_at=?
                WHERE id=?
                """,
                (priority, self._utc_now(), job_id),
            )
            self.conn.commit()
            return cursor.rowcount > 0

    def pause_job(self, job_id: int) -> bool:
        with self._lock:
            cursor = self.conn.execute(
                """
                UPDATE download_jobs
                SET status='paused', updated_at=?
                WHERE id=? AND status='pending'
                """,
                (self._utc_now(), job_id),
            )
            self.conn.commit()
            return cursor.rowcount > 0

    def resume_job(self, job_id: int) -> bool:
        with self._lock:
            cursor = self.conn.execute(
                """
                UPDATE download_jobs
                SET status='pending', updated_at=?
                WHERE id=? AND status='paused'
                """,
                (self._utc_now(), job_id),
            )
            self.conn.commit()
            return cursor.rowcount > 0

    def requeue_job_with_backoff(self, job_id: int, error: str, delay_seconds: int) -> None:
        run_at = datetime.now(timezone.utc) + timedelta(seconds=max(1, delay_seconds))
        with self._lock:
            self.conn.execute(
                """
                UPDATE download_jobs
                SET status='pending', last_error=?, next_run_at=?, updated_at=?
                WHERE id=?
                """,
                (error, run_at.isoformat(), self._utc_now(), job_id),
            )
            self.conn.commit()

    def dead_letter_job(self, job_id: int, error: str) -> None:
        now = self._utc_now()
        with self._lock:
            row = self.conn.execute(
                """
                SELECT id, url, target_type, priority, attempts
                FROM download_jobs
                WHERE id=?
                """,
                (job_id,),
            ).fetchone()
            if not row:
                return

            self.conn.execute(
                """
                INSERT INTO dead_letter_jobs (
                    original_job_id, url, target_type, priority, attempts, last_error, failed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(row["id"]),
                    str(row["url"]),
                    str(row["target_type"]),
                    int(row["priority"]),
                    int(row["attempts"]),
                    error,
                    now,
                ),
            )
            self.conn.execute(
                """
                UPDATE download_jobs
                SET status='dead', last_error=?, next_run_at=NULL, updated_at=?
                WHERE id=?
                """,
                (error, now, job_id),
            )
            self.conn.commit()

    def list_download_jobs(self, status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        query = """
            SELECT id, url, target_type, status, priority, attempts, next_run_at,
                   last_error, added_at, updated_at
            FROM download_jobs
        """
        params: list[Any] = []
        if status:
            query += " WHERE status=? "
            params.append(status)
        query += " ORDER BY priority DESC, id DESC LIMIT ?"
        params.append(limit)
        with self._lock:
            rows = self.conn.execute(query, tuple(params)).fetchall()
        return [dict(row) for row in rows]

    def list_dead_letter_jobs(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            rows = self.conn.execute(
                """
                SELECT id, original_job_id, url, target_type, priority, attempts,
                       last_error, failed_at, retried_at
                FROM dead_letter_jobs
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def retry_dead_letter(self, dead_letter_id: int) -> int | None:
        now = self._utc_now()
        with self._lock:
            row = self.conn.execute(
                """
                SELECT id, url, target_type, priority
                FROM dead_letter_jobs
                WHERE id=?
                """,
                (dead_letter_id,),
            ).fetchone()
            if not row:
                return None

            existing = self.conn.execute(
                """
                SELECT id FROM download_jobs
                WHERE url=? AND status IN ('pending', 'processing')
                ORDER BY id DESC LIMIT 1
                """,
                (str(row["url"]),),
            ).fetchone()

            if existing:
                new_job_id = int(existing["id"])
            else:
                cursor = self.conn.execute(
                    """
                    INSERT INTO download_jobs (
                        url, target_type, status, priority, attempts, next_run_at, added_at, updated_at
                    ) VALUES (?, ?, 'pending', ?, 0, ?, ?, ?)
                    """,
                    (
                        str(row["url"]),
                        str(row["target_type"]),
                        int(row["priority"]),
                        now,
                        now,
                        now,
                    ),
                )
                new_job_id = int(cursor.lastrowid)

            self.conn.execute(
                """
                UPDATE dead_letter_jobs
                SET retried_at=?
                WHERE id=?
                """,
                (now, dead_letter_id),
            )
            self.conn.commit()
            return new_job_id

    def list_videos(
        self,
        limit: int = 100,
        search: str | None = None,
        profile_id: str = DEFAULT_PROFILE_ID,
    ) -> list[dict[str, Any]]:
        normalized_profile = (profile_id or self.DEFAULT_PROFILE_ID).strip().lower() or self.DEFAULT_PROFILE_ID
        is_default_profile = 1 if normalized_profile == self.DEFAULT_PROFILE_ID else 0
        query = """
            SELECT v.video_id, v.title, v.channel, v.upload_date, v.local_path, v.downloaded,
                   v.duration_seconds, v.file_size_bytes,
                   CASE WHEN ?=1 THEN COALESCE(ps.watched, v.watched) ELSE COALESCE(ps.watched, 0) END AS watched,
                   CASE WHEN ?=1 THEN COALESCE(ps.liked, v.liked) ELSE COALESCE(ps.liked, 0) END AS liked,
                   CASE WHEN ?=1 THEN COALESCE(ps.disliked, v.disliked) ELSE COALESCE(ps.disliked, 0) END AS disliked,
                   CASE WHEN ?=1 THEN COALESCE(ps.rating, v.rating) ELSE COALESCE(ps.rating, 0) END AS rating,
                   CASE WHEN ?=1 THEN COALESCE(ps.rejected_reason, v.rejected_reason) ELSE ps.rejected_reason END AS rejected_reason,
                   v.trending_score,
                   v.channel_preference, v.watch_score, v.source_url, v.updated_at,
                   COALESCE(i.transcript_source, 'none') AS transcript_source,
                   COALESCE(i.quality_score, 0.0) AS intelligence_quality,
                   COALESCE(ps.completed, 0) AS completed,
                   COALESCE(ps.total_watch_seconds, 0) AS total_watch_seconds
            FROM videos v
            LEFT JOIN video_intelligence i ON i.video_id=v.video_id
            LEFT JOIN profile_video_state ps ON ps.video_id=v.video_id AND ps.profile_id=?
        """
        params: list[Any] = [
            is_default_profile,
            is_default_profile,
            is_default_profile,
            is_default_profile,
            is_default_profile,
            normalized_profile,
        ]
        if search:
            query += " WHERE v.title LIKE ? OR v.channel LIKE ? "
            wildcard = f"%{search}%"
            params.extend([wildcard, wildcard])
        query += " ORDER BY v.updated_at DESC LIMIT ?"
        params.append(limit)

        with self._lock:
            rows = self.conn.execute(query, tuple(params)).fetchall()
        return [dict(row) for row in rows]

    def get_video(self, video_id: str, profile_id: str = DEFAULT_PROFILE_ID) -> dict[str, Any] | None:
        normalized_profile = (profile_id or self.DEFAULT_PROFILE_ID).strip().lower() or self.DEFAULT_PROFILE_ID
        is_default_profile = 1 if normalized_profile == self.DEFAULT_PROFILE_ID else 0
        with self._lock:
            row = self.conn.execute(
                """
                SELECT v.video_id, v.title, v.channel, v.upload_date, v.local_path, v.downloaded,
                       v.duration_seconds, v.file_size_bytes,
                       CASE WHEN ?=1 THEN COALESCE(ps.watched, v.watched) ELSE COALESCE(ps.watched, 0) END AS watched,
                       CASE WHEN ?=1 THEN COALESCE(ps.liked, v.liked) ELSE COALESCE(ps.liked, 0) END AS liked,
                       CASE WHEN ?=1 THEN COALESCE(ps.disliked, v.disliked) ELSE COALESCE(ps.disliked, 0) END AS disliked,
                       CASE WHEN ?=1 THEN COALESCE(ps.rating, v.rating) ELSE COALESCE(ps.rating, 0) END AS rating,
                       CASE WHEN ?=1 THEN COALESCE(ps.rejected_reason, v.rejected_reason) ELSE ps.rejected_reason END AS rejected_reason,
                       v.trending_score,
                       v.channel_preference, v.watch_score, v.source_url,
                       COALESCE(i.transcript_source, 'none') AS transcript_source,
                       COALESCE(i.quality_score, 0.0) AS intelligence_quality,
                       COALESCE(ps.completed, 0) AS completed,
                       COALESCE(ps.total_watch_seconds, 0) AS total_watch_seconds
                FROM videos v
                LEFT JOIN video_intelligence i ON i.video_id=v.video_id
                LEFT JOIN profile_video_state ps ON ps.video_id=v.video_id AND ps.profile_id=?
                WHERE v.video_id=?
                """,
                (
                    is_default_profile,
                    is_default_profile,
                    is_default_profile,
                    is_default_profile,
                    is_default_profile,
                    normalized_profile,
                    video_id,
                ),
            ).fetchone()
        return dict(row) if row else None

    def set_preference(
        self,
        pref_type: str,
        pref_key: str,
        pref_value: str | None = None,
        weight: float = 1.0,
        profile_id: str | None = None,
    ) -> None:
        now = self._utc_now()
        pref_key = pref_key.strip().lower()
        scoped_type = f"profile:{(profile_id or self.DEFAULT_PROFILE_ID).strip().lower()}:{pref_type}" if profile_id else pref_type
        with self._lock:
            self.conn.execute(
                """
                INSERT INTO preferences (pref_type, pref_key, pref_value, weight, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(pref_type, pref_key) DO UPDATE SET
                    pref_value=excluded.pref_value,
                    weight=excluded.weight,
                    updated_at=excluded.updated_at
                """,
                (scoped_type, pref_key, pref_value, weight, now),
            )
            self.conn.commit()

    def get_preferences(self, pref_type: str, profile_id: str | None = None) -> dict[str, float]:
        scoped_type = f"profile:{(profile_id or self.DEFAULT_PROFILE_ID).strip().lower()}:{pref_type}" if profile_id else pref_type
        with self._lock:
            rows = self.conn.execute(
                "SELECT pref_key, weight FROM preferences WHERE pref_type=?",
                (scoped_type,),
            ).fetchall()
        return {str(row["pref_key"]): float(row["weight"]) for row in rows}

    def set_trending_score(self, video_id: str, score: float) -> None:
        with self._lock:
            self.conn.execute(
                """
                UPDATE videos
                SET trending_score=?, updated_at=?
                WHERE video_id=?
                """,
                (score, self._utc_now(), video_id),
            )
            self.conn.commit()

    def update_video_signals(self, video_id: str, channel_preference: float, watch_score: float) -> None:
        with self._lock:
            self.conn.execute(
                """
                UPDATE videos
                SET channel_preference=?, watch_score=?, updated_at=?
                WHERE video_id=?
                """,
                (channel_preference, watch_score, self._utc_now(), video_id),
            )
            self.conn.commit()

    def fetch_history_signal(self, profile_id: str = DEFAULT_PROFILE_ID) -> dict[str, float]:
        normalized_profile = (profile_id or self.DEFAULT_PROFILE_ID).strip().lower() or self.DEFAULT_PROFILE_ID
        with self._lock:
            rows = self.conn.execute(
                """
                SELECT
                    video_id,
                    SUM(CASE WHEN liked=1 THEN 1.0 WHEN disliked=1 THEN -1.0 ELSE 0 END)
                    + SUM(CASE WHEN completed=1 THEN 0.2 ELSE 0 END)
                    + COALESCE(AVG(rating) / 5.0, 0.0) AS signal
                FROM watch_history
                WHERE profile_id=?
                GROUP BY video_id
                """,
                (normalized_profile,),
            ).fetchall()
        return {str(row["video_id"]): float(row["signal"] or 0.0) for row in rows}

    def upsert_video_intelligence(
        self,
        video_id: str,
        content_text: str,
        transcript_source: str,
        embedding: list[float],
        quality_score: float,
    ) -> None:
        now = self._utc_now()
        embedding_json = json.dumps(embedding, separators=(",", ":"))
        with self._lock:
            self.conn.execute(
                """
                INSERT INTO video_intelligence (
                    video_id, content_text, transcript_source, embedding_json,
                    embedding_dim, quality_score, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(video_id) DO UPDATE SET
                    content_text=excluded.content_text,
                    transcript_source=excluded.transcript_source,
                    embedding_json=excluded.embedding_json,
                    embedding_dim=excluded.embedding_dim,
                    quality_score=excluded.quality_score,
                    updated_at=excluded.updated_at
                """,
                (
                    video_id,
                    content_text,
                    transcript_source,
                    embedding_json,
                    len(embedding),
                    quality_score,
                    now,
                ),
            )
            self.conn.commit()

    def get_videos_missing_intelligence(self, limit: int = 200) -> list[dict[str, Any]]:
        with self._lock:
            rows = self.conn.execute(
                """
                SELECT v.video_id, v.title, v.channel, v.upload_date, v.source_url
                FROM videos v
                LEFT JOIN video_intelligence i ON i.video_id=v.video_id
                WHERE i.video_id IS NULL
                ORDER BY v.updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_profile_embedding_seeds(
        self,
        profile_id: str = DEFAULT_PROFILE_ID,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        normalized_profile = (profile_id or self.DEFAULT_PROFILE_ID).strip().lower() or self.DEFAULT_PROFILE_ID
        is_default_profile = 1 if normalized_profile == self.DEFAULT_PROFILE_ID else 0
        with self._lock:
            rows = self.conn.execute(
                """
                SELECT v.video_id,
                       CASE WHEN ?=1 THEN COALESCE(ps.watched, v.watched) ELSE COALESCE(ps.watched, 0) END AS watched,
                       CASE WHEN ?=1 THEN COALESCE(ps.liked, v.liked) ELSE COALESCE(ps.liked, 0) END AS liked,
                       CASE WHEN ?=1 THEN COALESCE(ps.disliked, v.disliked) ELSE COALESCE(ps.disliked, 0) END AS disliked,
                       CASE WHEN ?=1 THEN COALESCE(ps.rating, v.rating) ELSE COALESCE(ps.rating, 0) END AS rating,
                       COALESCE(ps.completed, 0) AS completed,
                       i.embedding_json
                FROM videos v
                JOIN video_intelligence i ON i.video_id=v.video_id
                LEFT JOIN profile_video_state ps ON ps.video_id=v.video_id AND ps.profile_id=?
                WHERE
                    CASE WHEN ?=1 THEN
                        COALESCE(ps.watched, v.watched)=1 OR COALESCE(ps.liked, v.liked)=1 OR COALESCE(ps.disliked, v.disliked)=1 OR COALESCE(ps.rating, v.rating) > 0
                    ELSE
                        COALESCE(ps.watched, 0)=1 OR COALESCE(ps.liked, 0)=1 OR COALESCE(ps.disliked, 0)=1 OR COALESCE(ps.rating, 0) > 0
                    END
                ORDER BY COALESCE(ps.updated_at, v.updated_at) DESC
                LIMIT ?
                """,
                (
                    is_default_profile,
                    is_default_profile,
                    is_default_profile,
                    is_default_profile,
                    normalized_profile,
                    is_default_profile,
                    limit,
                ),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_recommendation_candidates(
        self,
        profile_id: str = DEFAULT_PROFILE_ID,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        normalized_profile = (profile_id or self.DEFAULT_PROFILE_ID).strip().lower() or self.DEFAULT_PROFILE_ID
        is_default_profile = 1 if normalized_profile == self.DEFAULT_PROFILE_ID else 0
        with self._lock:
            rows = self.conn.execute(
                """
                SELECT
                    v.video_id,
                    v.title,
                    v.channel,
                    v.upload_date,
                    v.downloaded,
                    v.local_path,
                    v.duration_seconds,
                    v.file_size_bytes,
                    v.trending_score,
                    CASE WHEN ?=1 THEN COALESCE(ps.liked, v.liked) ELSE COALESCE(ps.liked, 0) END AS liked,
                    CASE WHEN ?=1 THEN COALESCE(ps.disliked, v.disliked) ELSE COALESCE(ps.disliked, 0) END AS disliked,
                    CASE WHEN ?=1 THEN COALESCE(ps.rating, v.rating) ELSE COALESCE(ps.rating, 0) END AS rating,
                    CASE WHEN ?=1 THEN COALESCE(ps.watched, v.watched) ELSE COALESCE(ps.watched, 0) END AS watched,
                    CASE WHEN ?=1 THEN COALESCE(ps.rejected_reason, v.rejected_reason) ELSE ps.rejected_reason END AS rejected_reason,
                    v.source_url,
                    COALESCE(i.embedding_json, '') AS embedding_json,
                    COALESCE(i.transcript_source, 'none') AS transcript_source,
                    COALESCE(i.quality_score, 0.0) AS intelligence_quality
                FROM videos v
                LEFT JOIN video_intelligence i ON i.video_id=v.video_id
                LEFT JOIN profile_video_state ps ON ps.video_id=v.video_id AND ps.profile_id=?
                ORDER BY COALESCE(ps.updated_at, v.updated_at) DESC
                LIMIT ?
                """,
                (
                    is_default_profile,
                    is_default_profile,
                    is_default_profile,
                    is_default_profile,
                    is_default_profile,
                    normalized_profile,
                    limit,
                ),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_pending_job_urls(self) -> set[str]:
        with self._lock:
            rows = self.conn.execute(
                """
                SELECT DISTINCT url
                FROM download_jobs
                WHERE status IN ('pending', 'processing')
                """
            ).fetchall()
        return {str(row["url"]) for row in rows if row["url"]}

    def get_offline_inventory_stats(self, profile_id: str = DEFAULT_PROFILE_ID) -> dict[str, int]:
        normalized_profile = (profile_id or self.DEFAULT_PROFILE_ID).strip().lower() or self.DEFAULT_PROFILE_ID
        is_default_profile = 1 if normalized_profile == self.DEFAULT_PROFILE_ID else 0
        with self._lock:
            row = self.conn.execute(
                """
                SELECT
                    COUNT(*) AS total_downloaded_items,
                    COALESCE(
                        SUM(
                            CASE
                                WHEN
                                    (CASE WHEN ?=1 THEN COALESCE(ps.watched, videos.watched) ELSE COALESCE(ps.watched, 0) END)=0
                                THEN COALESCE(videos.duration_seconds, 0)
                                ELSE 0
                            END
                        ),
                        0
                    ) AS unwatched_duration_seconds,
                    COALESCE(SUM(COALESCE(file_size_bytes, 0)), 0) AS downloaded_storage_bytes
                FROM videos
                LEFT JOIN profile_video_state ps ON ps.video_id=videos.video_id AND ps.profile_id=?
                WHERE videos.downloaded=1
                """
            ,
                (is_default_profile, normalized_profile),
            ).fetchone()
        if not row:
            return {
                "total_downloaded_items": 0,
                "unwatched_duration_seconds": 0,
                "downloaded_storage_bytes": 0,
            }
        return {
            "total_downloaded_items": int(row["total_downloaded_items"] or 0),
            "unwatched_duration_seconds": int(row["unwatched_duration_seconds"] or 0),
            "downloaded_storage_bytes": int(row["downloaded_storage_bytes"] or 0),
        }

    def list_storage_candidates(self, limit: int = 1000) -> list[dict[str, Any]]:
        with self._lock:
            rows = self.conn.execute(
                """
                SELECT video_id, local_path, file_size_bytes, watched, liked, disliked, rating,
                       rejected_reason, channel_preference, watch_score, trending_score, updated_at
                FROM videos
                WHERE downloaded=1 AND local_path IS NOT NULL AND local_path != ''
                ORDER BY updated_at ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def close(self) -> None:
        with self._lock:
            self.conn.close()
