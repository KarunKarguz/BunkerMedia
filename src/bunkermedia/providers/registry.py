from __future__ import annotations

from bunkermedia.providers.base import Provider


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, Provider] = {}

    def register(self, provider: Provider) -> None:
        key = provider.name.strip().lower()
        if not key:
            raise ValueError("Provider name cannot be empty")
        self._providers[key] = provider

    def get(self, name: str) -> Provider:
        key = name.strip().lower()
        provider = self._providers.get(key)
        if not provider:
            raise KeyError(f"Unknown provider: {name}")
        return provider

    def list(self) -> list[str]:
        return sorted(self._providers.keys())
