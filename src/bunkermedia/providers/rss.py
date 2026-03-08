from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.request import urlopen

from bunkermedia.database import Database
from bunkermedia.downloader import Downloader
from bunkermedia.models import VideoMetadata
from bunkermedia.providers.base import Provider

TAG_RE = re.compile(r"\{[^}]+\}")


class RSSProvider(Provider):
    def __init__(self, db: Database, downloader: Downloader, logger: Any) -> None:
        self.db = db
        self.downloader = downloader
        self.logger = logger

    @property
    def name(self) -> str:
        return "rss"

    async def discover(self, source: str, limit: int = 50) -> list[VideoMetadata]:
        feed = source.strip()
        if not feed:
            return []
        return self._discover_sync(feed, limit)

    async def acquire(self, source: str, mode: str = "auto") -> list[VideoMetadata]:
        entries = await self.discover(source, limit=30)
        collected: list[VideoMetadata] = []
        for entry in entries:
            if not entry.source_url:
                continue
            try:
                items = await self.downloader.download_url(entry.source_url, target_type=mode)
                collected.extend(items)
            except Exception:
                self.logger.exception("RSS acquire failed link=%s", entry.source_url)
        return collected

    def _discover_sync(self, feed_url: str, limit: int) -> list[VideoMetadata]:
        xml_text = self._fetch_feed(feed_url)
        if not xml_text:
            return []

        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            self.logger.warning("Invalid RSS feed format url=%s", feed_url)
            return []

        channel_title = self._find_text(root, ["channel/title", "title"]) or "RSS"

        items = root.findall(".//item")
        if not items:
            items = root.findall(".//entry")

        results: list[VideoMetadata] = []
        for item in items[: max(1, limit)]:
            title = self._find_text(item, ["title"]) or "Untitled"
            link = self._find_text(item, ["link", "guid"])
            if not link:
                link = self._find_attr(item, ["link"], "href")
            if not link:
                continue

            upload_date = self._parse_date(self._find_text(item, ["pubDate", "updated", "published"]))
            guid = self._find_text(item, ["guid"]) or link
            vid = f"rss_{hashlib.sha1(guid.encode('utf-8')).hexdigest()[:16]}"

            meta = VideoMetadata(
                video_id=vid,
                title=title.strip(),
                channel=channel_title.strip(),
                upload_date=upload_date,
                source_url=link.strip(),
                downloaded=False,
            )
            self.db.upsert_video(meta)
            results.append(meta)

        self.logger.info("RSS discover complete url=%s count=%d", feed_url, len(results))
        return results

    @staticmethod
    def _fetch_feed(url: str) -> str | None:
        try:
            with urlopen(url, timeout=8) as response:
                raw = response.read(3_000_000)
        except Exception:
            return None
        return raw.decode("utf-8", errors="ignore")

    @staticmethod
    def _strip_tag(tag: str | None) -> str:
        if not tag:
            return ""
        return TAG_RE.sub("", tag)

    def _find_text(self, node: ET.Element, paths: list[str]) -> str | None:
        for path in paths:
            found = node.find(path)
            if found is not None and found.text:
                return found.text

            # Namespace-insensitive scan
            path_key = path.split("/")[-1]
            for child in node.iter():
                if self._strip_tag(child.tag) == path_key and child.text:
                    return child.text
        return None

    def _find_attr(self, node: ET.Element, paths: list[str], attr: str) -> str | None:
        for path in paths:
            found = node.find(path)
            if found is not None and found.attrib.get(attr):
                return found.attrib[attr]

            path_key = path.split("/")[-1]
            for child in node.iter():
                if self._strip_tag(child.tag) == path_key and child.attrib.get(attr):
                    return child.attrib[attr]
        return None

    @staticmethod
    def _parse_date(raw: str | None) -> str | None:
        if not raw:
            return None
        value = raw.strip()
        if not value:
            return None

        for parser in (
            lambda s: parsedate_to_datetime(s),
            lambda s: datetime.fromisoformat(s.replace("Z", "+00:00")),
        ):
            try:
                dt = parser(value)
                return dt.strftime("%Y%m%d")
            except Exception:
                continue
        return None
