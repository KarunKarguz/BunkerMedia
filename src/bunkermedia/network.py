from __future__ import annotations

import asyncio
import socket
from datetime import datetime
from typing import Any

from bunkermedia.config import AppConfig


class NetworkStateManager:
    def __init__(self, config: AppConfig, logger: Any) -> None:
        self.config = config
        self.logger = logger
        self._online: bool = not config.force_offline_mode

    @property
    def is_online(self) -> bool:
        if self.config.force_offline_mode:
            return False
        return self._online

    async def refresh(self) -> bool:
        if self.config.force_offline_mode:
            self._online = False
            return self._online

        host = self.config.connectivity_check_host
        port = self.config.connectivity_check_port
        timeout = self.config.connectivity_check_timeout_seconds
        result = await _check_tcp_connectivity_async(host, port, timeout)
        if result != self._online:
            self._online = result
            state = "online" if self._online else "offline"
            self.logger.info("Network state changed state=%s", state)
        return self._online

    def in_sync_window(self, now: datetime | None = None) -> bool:
        windows = self.config.sync_windows
        if not windows:
            return True

        local_now = now or datetime.now().astimezone()
        current_minutes = local_now.hour * 60 + local_now.minute

        for window in windows:
            bounds = _parse_window(window)
            if not bounds:
                continue
            start_min, end_min = bounds
            if start_min <= end_min:
                if start_min <= current_minutes <= end_min:
                    return True
            else:
                if current_minutes >= start_min or current_minutes <= end_min:
                    return True
        return False


async def _check_tcp_connectivity_async(host: str, port: int, timeout: float) -> bool:
    try:
        fut = asyncio.open_connection(host=host, port=port)
        reader, writer = await asyncio.wait_for(fut, timeout=max(0.2, timeout))
        writer.close()
        await writer.wait_closed()
        return True
    except (OSError, TimeoutError, socket.gaierror):
        return False


def _parse_window(raw: str) -> tuple[int, int] | None:
    value = raw.strip()
    if "-" not in value:
        return None
    left, right = value.split("-", 1)
    start = _hhmm_to_minutes(left.strip())
    end = _hhmm_to_minutes(right.strip())
    if start is None or end is None:
        return None
    return start, end


def _hhmm_to_minutes(raw: str) -> int | None:
    if ":" not in raw:
        return None
    hours_raw, mins_raw = raw.split(":", 1)
    if not (hours_raw.isdigit() and mins_raw.isdigit()):
        return None
    hour = int(hours_raw)
    minute = int(mins_raw)
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return hour * 60 + minute
