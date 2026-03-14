from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Any

from bunkermedia.library import MediaLibrary

VIDEO_EXTENSIONS = {
    ".mp4",
    ".mkv",
    ".webm",
    ".avi",
    ".mov",
    ".m4v",
}

AUDIO_EXTENSIONS = {
    ".mp3",
    ".m4a",
    ".flac",
    ".wav",
}

ARTWORK_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".gif",
    ".svg",
}


class ImportOrganizer:
    def __init__(
        self,
        library: MediaLibrary,
        import_watch_folders: list[Path],
        move_mode: str,
        scan_limit: int,
        logger: Any,
    ) -> None:
        self.library = library
        self.import_watch_folders = import_watch_folders
        self.move_mode = move_mode if move_mode in {"move", "copy"} else "move"
        self.scan_limit = max(1, int(scan_limit))
        self.logger = logger

    def organize_once(self) -> dict[str, object]:
        if not self.import_watch_folders:
            return {
                "status": "disabled",
                "scanned": 0,
                "organized": 0,
                "duplicates": 0,
                "skipped": 0,
                "errors": 0,
            }

        organized = 0
        duplicates = 0
        skipped = 0
        errors = 0
        scanned = 0
        imported: list[str] = []

        for root in self.import_watch_folders:
            if scanned >= self.scan_limit:
                break
            if not root.exists() or not root.is_dir():
                continue

            for path in root.rglob("*"):
                if scanned >= self.scan_limit:
                    break
                if not path.is_file():
                    continue
                if path.name.startswith("."):
                    continue

                scanned += 1
                media_type = self._classify(path)
                if media_type is None:
                    skipped += 1
                    continue

                try:
                    target = self._destination_for(root, path, media_type)
                    sidecars = self._related_artwork(path)
                    outcome = self._place_file(path, target)
                except OSError:
                    errors += 1
                    self.logger.exception("Import organize failed source=%s", path)
                    continue

                if outcome == "duplicate":
                    duplicates += 1
                    continue
                if outcome == "organized":
                    self._place_related_artwork(sidecars, target)
                    organized += 1
                    imported.append(str(target))
                    continue
                skipped += 1

        self.logger.info(
            "Import organizer complete scanned=%s organized=%s duplicates=%s skipped=%s errors=%s",
            scanned,
            organized,
            duplicates,
            skipped,
            errors,
        )
        return {
            "status": "ok",
            "mode": self.move_mode,
            "scanned": scanned,
            "organized": organized,
            "duplicates": duplicates,
            "skipped": skipped,
            "errors": errors,
            "organized_paths": imported[:50],
        }

    def _destination_for(self, root: Path, source: Path, media_type: str) -> Path:
        ext = source.suffix.lower()
        stem = self._sanitize_name(source.stem)
        collection = self._collection_name(root, source)
        target_dir = self.library.organized_library_root() / media_type / collection
        target_dir.mkdir(parents=True, exist_ok=True)
        base = target_dir / f"{stem}{ext}"
        if not base.exists():
            return base

        digest = hashlib.sha1(str(source.resolve()).encode("utf-8")).hexdigest()[:8]
        return target_dir / f"{stem} [{digest}]{ext}"

    def _place_file(self, source: Path, target: Path) -> str:
        if target.exists():
            if self._same_file(source, target):
                if self.move_mode == "move":
                    try:
                        source.unlink()
                    except OSError:
                        pass
                return "duplicate"
            return "skipped"

        if self.move_mode == "copy":
            shutil.copy2(source, target)
        else:
            shutil.move(str(source), str(target))
        return "organized"

    def _place_related_artwork(self, sidecars: list[Path], target_media: Path) -> None:
        for source in sidecars:
            if not source.exists() or not source.is_file():
                continue
            target = target_media.with_suffix(source.suffix.lower())
            if target.exists():
                continue
            try:
                if self.move_mode == "copy":
                    shutil.copy2(source, target)
                else:
                    shutil.move(str(source), str(target))
            except OSError:
                self.logger.warning("Import artwork move skipped source=%s target=%s", source, target)

    @staticmethod
    def _same_file(left: Path, right: Path) -> bool:
        try:
            if left.stat().st_size != right.stat().st_size:
                return False
        except OSError:
            return False

        try:
            return ImportOrganizer._sha1(left) == ImportOrganizer._sha1(right)
        except OSError:
            return False

    @staticmethod
    def _sha1(path: Path) -> str:
        digest = hashlib.sha1()
        with path.open("rb") as handle:
            while True:
                block = handle.read(1024 * 1024)
                if not block:
                    break
                digest.update(block)
        return digest.hexdigest()

    @staticmethod
    def _classify(path: Path) -> str | None:
        suffix = path.suffix.lower()
        if suffix in VIDEO_EXTENSIONS:
            return "video"
        if suffix in AUDIO_EXTENSIONS:
            return "audio"
        return None

    @staticmethod
    def _related_artwork(path: Path) -> list[Path]:
        matches: list[Path] = []
        for suffix in ARTWORK_EXTENSIONS:
            candidate = path.with_suffix(suffix)
            if candidate.exists() and candidate.is_file():
                matches.append(candidate)
        return matches

    @staticmethod
    def _collection_name(root: Path, source: Path) -> str:
        try:
            relative = source.parent.relative_to(root)
        except ValueError:
            relative = source.parent

        parts = [ImportOrganizer._sanitize_name(part) for part in relative.parts if part and part != "."]
        if parts:
            return parts[0]
        return "Unsorted"

    @staticmethod
    def _sanitize_name(raw: str) -> str:
        cleaned = "".join(ch if ch.isalnum() or ch in {" ", "-", "_", "."} else " " for ch in raw)
        cleaned = " ".join(cleaned.replace("_", " ").split())
        return cleaned[:120] if cleaned else "Untitled"
