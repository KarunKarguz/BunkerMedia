from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from bunkermedia.migrations import apply_migrations, get_schema_version, list_migrations
from bunkermedia.models import VideoMetadata


class Database:
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

    def upsert_video(self, meta: VideoMetadata) -> None:
        now = self._utc_now()
        with self._lock:
            self.conn.execute(
                """
                INSERT INTO videos (
                    video_id, title, channel, upload_date, source_url, local_path,
                    downloaded, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(video_id) DO UPDATE SET
                    title=excluded.title,
                    channel=excluded.channel,
                    upload_date=COALESCE(excluded.upload_date, videos.upload_date),
                    source_url=COALESCE(excluded.source_url, videos.source_url),
                    local_path=COALESCE(excluded.local_path, videos.local_path),
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
                    int(meta.downloaded),
                    now,
                    now,
                ),
            )
            self.conn.commit()

    def mark_downloaded(self, video_id: str, local_path: str) -> None:
        with self._lock:
            self.conn.execute(
                """
                UPDATE videos
                SET downloaded=1, local_path=?, updated_at=?
                WHERE video_id=?
                """,
                (local_path, self._utc_now(), video_id),
            )
            self.conn.commit()

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
        now = self._utc_now()
        with self._lock:
            self.conn.execute(
                """
                INSERT INTO watch_history (
                    video_id, watched_at, watch_seconds, completed, liked, disliked, rating, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
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

    def list_videos(self, limit: int = 100, search: str | None = None) -> list[dict[str, Any]]:
        query = """
            SELECT v.video_id, v.title, v.channel, v.upload_date, v.local_path, v.downloaded,
                   v.watched, v.liked, v.disliked, v.rating, v.rejected_reason, v.trending_score,
                   v.channel_preference, v.watch_score, v.source_url, v.updated_at,
                   COALESCE(i.transcript_source, 'none') AS transcript_source,
                   COALESCE(i.quality_score, 0.0) AS intelligence_quality
            FROM videos v
            LEFT JOIN video_intelligence i ON i.video_id=v.video_id
        """
        params: list[Any] = []
        if search:
            query += " WHERE v.title LIKE ? OR v.channel LIKE ? "
            wildcard = f"%{search}%"
            params.extend([wildcard, wildcard])
        query += " ORDER BY v.updated_at DESC LIMIT ?"
        params.append(limit)

        with self._lock:
            rows = self.conn.execute(query, tuple(params)).fetchall()
        return [dict(row) for row in rows]

    def get_video(self, video_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self.conn.execute(
                """
                SELECT v.video_id, v.title, v.channel, v.upload_date, v.local_path, v.downloaded,
                       v.watched, v.liked, v.disliked, v.rating, v.rejected_reason, v.trending_score,
                       v.channel_preference, v.watch_score, v.source_url,
                       COALESCE(i.transcript_source, 'none') AS transcript_source,
                       COALESCE(i.quality_score, 0.0) AS intelligence_quality
                FROM videos v
                LEFT JOIN video_intelligence i ON i.video_id=v.video_id
                WHERE v.video_id=?
                """,
                (video_id,),
            ).fetchone()
        return dict(row) if row else None

    def set_preference(
        self,
        pref_type: str,
        pref_key: str,
        pref_value: str | None = None,
        weight: float = 1.0,
    ) -> None:
        now = self._utc_now()
        pref_key = pref_key.strip().lower()
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
                (pref_type, pref_key, pref_value, weight, now),
            )
            self.conn.commit()

    def get_preferences(self, pref_type: str) -> dict[str, float]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT pref_key, weight FROM preferences WHERE pref_type=?",
                (pref_type,),
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

    def fetch_history_signal(self) -> dict[str, float]:
        with self._lock:
            rows = self.conn.execute(
                """
                SELECT
                    video_id,
                    SUM(CASE WHEN liked=1 THEN 1.0 WHEN disliked=1 THEN -1.0 ELSE 0 END)
                    + SUM(CASE WHEN completed=1 THEN 0.2 ELSE 0 END)
                    + COALESCE(AVG(rating) / 5.0, 0.0) AS signal
                FROM watch_history
                GROUP BY video_id
                """
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

    def get_profile_embedding_seeds(self, limit: int = 1000) -> list[dict[str, Any]]:
        with self._lock:
            rows = self.conn.execute(
                """
                SELECT v.video_id, v.watched, v.liked, v.disliked, v.rating,
                       COALESCE(h.completed, 0) AS completed,
                       i.embedding_json
                FROM videos v
                JOIN video_intelligence i ON i.video_id=v.video_id
                LEFT JOIN (
                    SELECT video_id, MAX(completed) AS completed
                    FROM watch_history
                    GROUP BY video_id
                ) h ON h.video_id=v.video_id
                WHERE v.watched=1 OR v.liked=1 OR v.disliked=1 OR v.rating > 0
                ORDER BY v.updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_recommendation_candidates(self, limit: int = 1000) -> list[dict[str, Any]]:
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
                    v.trending_score,
                    v.liked,
                    v.disliked,
                    v.rating,
                    v.watched,
                    v.rejected_reason,
                    v.source_url,
                    COALESCE(i.embedding_json, '') AS embedding_json,
                    COALESCE(i.transcript_source, 'none') AS transcript_source,
                    COALESCE(i.quality_score, 0.0) AS intelligence_quality
                FROM videos v
                LEFT JOIN video_intelligence i ON i.video_id=v.video_id
                ORDER BY v.updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def close(self) -> None:
        with self._lock:
            self.conn.close()
