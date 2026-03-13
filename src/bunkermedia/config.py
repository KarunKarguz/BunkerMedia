from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(slots=True)
class UpdateIntervals:
    trending_fetch_seconds: int = 3600
    playlist_sync_seconds: int = 1800
    recommendation_update_seconds: int = 900
    download_queue_seconds: int = 20
    intelligence_refresh_seconds: int = 1200


@dataclass(slots=True)
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = 8080
    enable_metrics: bool = True


@dataclass(slots=True)
class AppConfig:
    config_path: Path
    download_path: Path
    database_path: Path
    download_archive: Path
    max_parallel_downloads: int = 2
    update_intervals: UpdateIntervals = field(default_factory=UpdateIntervals)
    server: ServerConfig = field(default_factory=ServerConfig)
    channel_feeds: list[str] = field(default_factory=list)
    playlist_feeds: list[str] = field(default_factory=list)
    rss_feeds: list[str] = field(default_factory=list)
    local_watch_folders: list[Path] = field(default_factory=list)
    import_watch_folders: list[Path] = field(default_factory=list)
    auto_organize_imports: bool = True
    import_move_mode: str = "move"
    import_scan_limit: int = 500
    prefer_low_power_mode: bool = True
    auto_start_workers: bool = True
    embedding_dim: int = 128
    intelligence_batch_size: int = 40
    transcript_max_chars: int = 12000
    max_download_attempts: int = 4
    retry_base_seconds: int = 30
    retry_max_seconds: int = 1800
    retry_jitter: float = 0.15
    log_format: str = "text"
    force_offline_mode: bool = False
    connectivity_check_host: str = "1.1.1.1"
    connectivity_check_port: int = 53
    connectivity_check_timeout_seconds: float = 2.0
    sync_windows: list[str] = field(default_factory=list)
    backup_path: Path | None = None
    offline_target_hours: float = 8.0
    offline_planner_max_candidates: int = 200
    offline_planner_batch_size: int = 20
    offline_default_video_minutes: int = 20
    offline_estimated_mbps: float = 1.2
    offline_queue_priority: int = 2
    storage_max_gb: float = 0.0
    storage_reserve_gb: float = 1.0
    storage_eviction_policy: str = "watched_oldest"
    storage_protect_liked: bool = True
    storage_eviction_batch_size: int = 25
    private_mode_enabled: bool = False
    private_require_encrypted_store: bool = False
    private_storage_marker_file: str = ".bunkermedia-private-store"

    @property
    def logs_dir(self) -> Path:
        return self.config_path.parent / "logs"

    @classmethod
    def from_yaml(cls, config_file: str | Path) -> "AppConfig":
        cfg_path = Path(config_file).expanduser().resolve()
        raw = cls._read_yaml(cfg_path)
        base_dir = cfg_path.parent

        intervals = UpdateIntervals(**(raw.get("update_intervals") or {}))
        server = ServerConfig(**(raw.get("server") or {}))

        return cls(
            config_path=cfg_path,
            download_path=cls._resolve_path(base_dir, raw.get("download_path", "./media")),
            database_path=cls._resolve_path(base_dir, raw.get("database_path", "./bunkermedia.db")),
            download_archive=cls._resolve_path(base_dir, raw.get("download_archive", "./archive.txt")),
            max_parallel_downloads=int(raw.get("max_parallel_downloads", 2)),
            update_intervals=intervals,
            server=server,
            channel_feeds=list(raw.get("channel_feeds", [])),
            playlist_feeds=list(raw.get("playlist_feeds", [])),
            rss_feeds=list(raw.get("rss_feeds", [])),
            local_watch_folders=cls._resolve_paths(base_dir, raw.get("local_watch_folders", [])),
            import_watch_folders=cls._resolve_paths(base_dir, raw.get("import_watch_folders", [])),
            auto_organize_imports=bool(raw.get("auto_organize_imports", True)),
            import_move_mode=str(raw.get("import_move_mode", "move")).strip().lower(),
            import_scan_limit=int(raw.get("import_scan_limit", 500)),
            prefer_low_power_mode=bool(raw.get("prefer_low_power_mode", True)),
            auto_start_workers=bool(raw.get("auto_start_workers", True)),
            embedding_dim=int(raw.get("embedding_dim", 128)),
            intelligence_batch_size=int(raw.get("intelligence_batch_size", 40)),
            transcript_max_chars=int(raw.get("transcript_max_chars", 12000)),
            max_download_attempts=int(raw.get("max_download_attempts", 4)),
            retry_base_seconds=int(raw.get("retry_base_seconds", 30)),
            retry_max_seconds=int(raw.get("retry_max_seconds", 1800)),
            retry_jitter=float(raw.get("retry_jitter", 0.15)),
            log_format=str(raw.get("log_format", "text")).lower(),
            force_offline_mode=bool(raw.get("force_offline_mode", False)),
            connectivity_check_host=str(raw.get("connectivity_check_host", "1.1.1.1")),
            connectivity_check_port=int(raw.get("connectivity_check_port", 53)),
            connectivity_check_timeout_seconds=float(raw.get("connectivity_check_timeout_seconds", 2.0)),
            sync_windows=list(raw.get("sync_windows", [])),
            backup_path=(
                cls._resolve_path(base_dir, raw.get("backup_path"))
                if raw.get("backup_path")
                else cls._resolve_path(base_dir, "./backups")
            ),
            offline_target_hours=float(raw.get("offline_target_hours", 8.0)),
            offline_planner_max_candidates=int(raw.get("offline_planner_max_candidates", 200)),
            offline_planner_batch_size=int(raw.get("offline_planner_batch_size", 20)),
            offline_default_video_minutes=int(raw.get("offline_default_video_minutes", 20)),
            offline_estimated_mbps=float(raw.get("offline_estimated_mbps", 1.2)),
            offline_queue_priority=int(raw.get("offline_queue_priority", 2)),
            storage_max_gb=float(raw.get("storage_max_gb", 0.0)),
            storage_reserve_gb=float(raw.get("storage_reserve_gb", 1.0)),
            storage_eviction_policy=str(raw.get("storage_eviction_policy", "watched_oldest")).strip().lower(),
            storage_protect_liked=bool(raw.get("storage_protect_liked", True)),
            storage_eviction_batch_size=int(raw.get("storage_eviction_batch_size", 25)),
            private_mode_enabled=bool(raw.get("private_mode_enabled", False)),
            private_require_encrypted_store=bool(raw.get("private_require_encrypted_store", False)),
            private_storage_marker_file=str(raw.get("private_storage_marker_file", ".bunkermedia-private-store")).strip()
            or ".bunkermedia-private-store",
        )

    @staticmethod
    def _resolve_path(base_dir: Path, value: str | Path) -> Path:
        path = Path(value).expanduser()
        if not path.is_absolute():
            path = base_dir / path
        return path.resolve()

    @classmethod
    def _resolve_paths(cls, base_dir: Path, values: Any) -> list[Path]:
        if not isinstance(values, list):
            return []
        paths: list[Path] = []
        for value in values:
            if value is None:
                continue
            paths.append(cls._resolve_path(base_dir, value))
        return paths

    @staticmethod
    def _read_yaml(path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        with path.open("r", encoding="utf-8") as file:
            data = yaml.safe_load(file) or {}
        if not isinstance(data, dict):
            raise ValueError(f"Invalid config format at {path}")
        return data
