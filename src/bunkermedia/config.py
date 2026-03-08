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
        )

    @staticmethod
    def _resolve_path(base_dir: Path, value: str | Path) -> Path:
        path = Path(value).expanduser()
        if not path.is_absolute():
            path = base_dir / path
        return path.resolve()

    @staticmethod
    def _read_yaml(path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        with path.open("r", encoding="utf-8") as file:
            data = yaml.safe_load(file) or {}
        if not isinstance(data, dict):
            raise ValueError(f"Invalid config format at {path}")
        return data
