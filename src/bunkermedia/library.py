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
        ]:
            (self.root / rel).mkdir(parents=True, exist_ok=True)

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
