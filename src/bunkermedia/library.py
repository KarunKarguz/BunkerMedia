from __future__ import annotations

from pathlib import Path


class MediaLibrary:
    def __init__(self, root: Path) -> None:
        self.root = root

    def ensure_layout(self) -> None:
        for rel in [
            "youtube/channel",
            "youtube/single",
            "playlists",
            "trending",
            "artwork/cache",
            "artwork/generated",
            "library/video",
            "library/audio",
            "library/mixed",
            "imports",
        ]:
            (self.root / rel).mkdir(parents=True, exist_ok=True)

    def organized_library_root(self) -> Path:
        return self.root / "library"

    def organized_watch_folders(self) -> list[Path]:
        return [
            self.root / "library" / "video",
            self.root / "library" / "audio",
            self.root / "library" / "mixed",
        ]

    def artwork_cache_root(self) -> Path:
        return self.root / "artwork" / "cache"

    def generated_artwork_root(self) -> Path:
        return self.root / "artwork" / "generated"

    def output_template(self, target_type: str) -> str:
        templates = {
            "single": self.root / "youtube" / "single" / "%(title).150B [%(id)s].%(ext)s",
            "playlist": self.root
            / "playlists"
            / "%(playlist).120B"
            / "%(playlist_index)s - %(title).150B [%(id)s].%(ext)s",
            "channel": self.root
            / "youtube"
            / "channel"
            / "%(channel).120B"
            / "%(title).150B [%(id)s].%(ext)s",
            "trending": self.root
            / "trending"
            / "%(upload_date>%Y-%m-%d)s"
            / "%(title).150B [%(id)s].%(ext)s",
        }
        return str(templates.get(target_type, templates["single"]))
