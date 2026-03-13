from __future__ import annotations

import os
import platform
import shutil
from pathlib import Path
from typing import Any


class SystemMonitor:
    def __init__(self, media_root: Path, logger: Any) -> None:
        self.media_root = media_root
        self.logger = logger

    def snapshot(self) -> dict[str, object]:
        media_usage = self._disk_usage_for(self.media_root)
        root_usage = self._disk_usage_for(Path("/"))
        memory = self._memory_snapshot()
        load = self._load_snapshot()
        cpu_temp_c = self._cpu_temp_c()

        return {
            "platform": {
                "system": platform.system(),
                "release": platform.release(),
                "machine": platform.machine(),
                "python_version": platform.python_version(),
                "hostname": platform.node(),
            },
            "media_disk": media_usage,
            "root_disk": root_usage,
            "memory": memory,
            "load": load,
            "cpu_temp_c": cpu_temp_c,
            "is_raspberry_pi": self._is_raspberry_pi(),
        }

    def _disk_usage_for(self, path: Path) -> dict[str, int] | None:
        target = path if path.exists() else path.parent
        try:
            usage = shutil.disk_usage(target)
        except OSError:
            return None
        return {
            "total_bytes": int(usage.total),
            "used_bytes": int(usage.used),
            "free_bytes": int(usage.free),
        }

    @staticmethod
    def _memory_snapshot() -> dict[str, int] | None:
        meminfo = Path("/proc/meminfo")
        if not meminfo.exists():
            return None
        values: dict[str, int] = {}
        try:
            for line in meminfo.read_text(encoding="utf-8").splitlines():
                if ":" not in line:
                    continue
                key, raw = line.split(":", 1)
                fields = raw.strip().split()
                if not fields or not fields[0].isdigit():
                    continue
                values[key] = int(fields[0]) * 1024
        except OSError:
            return None

        total = int(values.get("MemTotal", 0))
        available = int(values.get("MemAvailable", 0))
        used = max(0, total - available)
        return {
            "total_bytes": total,
            "available_bytes": available,
            "used_bytes": used,
        }

    @staticmethod
    def _load_snapshot() -> dict[str, float] | None:
        try:
            avg1, avg5, avg15 = os.getloadavg()
        except (AttributeError, OSError):
            return None
        cpu_count = max(1, os.cpu_count() or 1)
        return {
            "load1": float(avg1),
            "load5": float(avg5),
            "load15": float(avg15),
            "cpu_count": float(cpu_count),
            "normalized_load1": float(avg1 / cpu_count),
        }

    @staticmethod
    def _cpu_temp_c() -> float | None:
        thermal = Path("/sys/class/thermal/thermal_zone0/temp")
        if not thermal.exists():
            return None
        try:
            raw = thermal.read_text(encoding="utf-8").strip()
            return round(int(raw) / 1000.0, 1)
        except (OSError, ValueError):
            return None

    @staticmethod
    def _is_raspberry_pi() -> bool:
        model_path = Path("/sys/firmware/devicetree/base/model")
        if model_path.exists():
            try:
                return "raspberry pi" in model_path.read_text(encoding="utf-8", errors="ignore").lower()
            except OSError:
                return False
        return "arm" in platform.machine().lower() and platform.system().lower() == "linux"
