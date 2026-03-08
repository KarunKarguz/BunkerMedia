from __future__ import annotations

import shutil
import tarfile
from datetime import datetime, timezone
from pathlib import Path

from bunkermedia.config import AppConfig


def backup_state(config: AppConfig, output_dir: Path | None = None) -> Path:
    out_dir = (output_dir or config.backup_path or (config.config_path.parent / "backups")).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive_path = out_dir / f"bunkermedia-backup-{stamp}.tar.gz"

    db_path = config.database_path
    wal_path = Path(f"{db_path}-wal")
    shm_path = Path(f"{db_path}-shm")

    with tarfile.open(archive_path, mode="w:gz") as tar:
        _safe_add(tar, config.config_path, arcname="config.yaml")
        _safe_add(tar, db_path, arcname="bunkermedia.db")
        _safe_add(tar, wal_path, arcname="bunkermedia.db-wal")
        _safe_add(tar, shm_path, arcname="bunkermedia.db-shm")
        _safe_add(tar, config.download_archive, arcname="archive.txt")

    return archive_path


def restore_state(config: AppConfig, archive_path: Path, force: bool = False) -> None:
    if not archive_path.exists():
        raise FileNotFoundError(f"Backup archive not found: {archive_path}")

    if config.database_path.exists() and not force:
        raise RuntimeError("Database already exists. Use --force to overwrite.")

    config.database_path.parent.mkdir(parents=True, exist_ok=True)
    config.download_archive.parent.mkdir(parents=True, exist_ok=True)

    temp_dir = config.config_path.parent / ".restore_tmp"
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        with tarfile.open(archive_path, mode="r:gz") as tar:
            tar.extractall(temp_dir)

        _replace_if_exists(temp_dir / "bunkermedia.db", config.database_path, force=force)
        _replace_if_exists(temp_dir / "bunkermedia.db-wal", Path(f"{config.database_path}-wal"), force=True)
        _replace_if_exists(temp_dir / "bunkermedia.db-shm", Path(f"{config.database_path}-shm"), force=True)
        _replace_if_exists(temp_dir / "archive.txt", config.download_archive, force=True)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def _replace_if_exists(src: Path, dst: Path, force: bool) -> None:
    if not src.exists():
        return
    if dst.exists() and not force:
        raise RuntimeError(f"Refusing to overwrite existing file: {dst}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _safe_add(tar: tarfile.TarFile, path: Path, arcname: str) -> None:
    if path.exists():
        tar.add(path, arcname=arcname)
