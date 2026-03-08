from __future__ import annotations

from abc import ABC, abstractmethod

from bunkermedia.models import VideoMetadata


class Provider(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    async def discover(self, source: str, limit: int = 50) -> list[VideoMetadata]:
        raise NotImplementedError

    @abstractmethod
    async def acquire(self, source: str, mode: str = "auto") -> list[VideoMetadata]:
        raise NotImplementedError
