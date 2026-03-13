from __future__ import annotations

from pathlib import Path
from typing import Any


class StoragePrivacyMonitor:
    ENCRYPTED_FS_TYPES = {
        "ecryptfs",
        "fuse.gocryptfs",
        "fuse.cryfs",
        "fuse.encfs",
        "encfs",
        "securefs",
    }

    def __init__(
        self,
        media_root: Path,
        private_mode_enabled: bool,
        require_encrypted_store: bool,
        marker_filename: str,
    ) -> None:
        self.media_root = media_root
        self.private_mode_enabled = bool(private_mode_enabled)
        self.require_encrypted_store = bool(require_encrypted_store)
        self.marker_filename = marker_filename or ".bunkermedia-private-store"

    def snapshot(self) -> dict[str, Any]:
        root = self.media_root.resolve()
        marker_path = root / self.marker_filename
        mount_info = self._mount_info(root)
        encrypted_hint = self._is_mount_encrypted(mount_info)
        marker_present = marker_path.exists()
        compliant = (not self.private_mode_enabled) or marker_present or encrypted_hint or (not self.require_encrypted_store)

        if not self.private_mode_enabled:
            status = "disabled"
        elif compliant:
            status = "ok"
        else:
            status = "warning"

        return {
            "private_mode_enabled": self.private_mode_enabled,
            "require_encrypted_store": self.require_encrypted_store,
            "status": status,
            "media_root": str(root),
            "marker_path": str(marker_path),
            "marker_present": marker_present,
            "encrypted_mount_detected": encrypted_hint,
            "mount_source": mount_info.get("source"),
            "mount_point": mount_info.get("target"),
            "mount_type": mount_info.get("fstype"),
            "notes": self._notes(status, marker_present, encrypted_hint),
        }

    def _mount_info(self, target: Path) -> dict[str, str]:
        best: dict[str, str] = {}
        best_len = -1
        try:
            lines = Path("/proc/mounts").read_text(encoding="utf-8").splitlines()
        except OSError:
            return {}

        for line in lines:
            parts = line.split()
            if len(parts) < 3:
                continue
            source, mount_point, fstype = parts[0], parts[1], parts[2]
            mount_path = Path(mount_point)
            try:
                target.relative_to(mount_path)
            except ValueError:
                continue
            mount_len = len(str(mount_path))
            if mount_len > best_len:
                best_len = mount_len
                best = {
                    "source": source,
                    "target": str(mount_path),
                    "fstype": fstype,
                }
        return best

    def _is_mount_encrypted(self, mount_info: dict[str, str]) -> bool:
        source = str(mount_info.get("source") or "").lower()
        fstype = str(mount_info.get("fstype") or "").lower()
        if fstype in self.ENCRYPTED_FS_TYPES:
            return True
        if any(token in source for token in ("crypt", "mapper", "gocryptfs", "cryfs", "encfs", "securefs")):
            return True
        return False

    def _notes(self, status: str, marker_present: bool, encrypted_hint: bool) -> list[str]:
        notes: list[str] = []
        if not self.private_mode_enabled:
            notes.append("Private mode is disabled.")
            return notes
        if marker_present:
            notes.append("Encrypted-store marker file is present.")
        if encrypted_hint:
            notes.append("Mount source/type suggests encrypted storage.")
        if not marker_present and not encrypted_hint:
            notes.append("No encrypted-mount hint detected. LUKS-backed ext4 may require the marker file.")
        if status == "warning":
            notes.append("Private mode is active but storage could not be verified as private.")
        return notes
