from __future__ import annotations

import asyncio
import hashlib
import json
import math
import re
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

from yt_dlp import YoutubeDL

from bunkermedia.database import Database

TOKEN_RE = re.compile(r"[a-zA-Z0-9']{2,}")
HTML_TAG_RE = re.compile(r"<[^>]+>")


class IntelligenceEngine:
    def __init__(
        self,
        db: Database,
        logger: Any,
        embedding_dim: int = 128,
        max_text_chars: int = 12000,
    ) -> None:
        self.db = db
        self.logger = logger
        self.embedding_dim = max(32, embedding_dim)
        self.max_text_chars = max(2000, max_text_chars)

    async def refresh_embeddings(self, limit: int = 50) -> int:
        rows = self.db.get_videos_missing_intelligence(limit=limit)
        if not rows:
            return 0

        prepared = await asyncio.to_thread(self._prepare_embeddings_sync, rows)
        updated = 0
        for item in prepared:
            self.db.upsert_video_intelligence(
                video_id=item["video_id"],
                content_text=item["content_text"],
                transcript_source=item["transcript_source"],
                embedding=item["embedding"],
                quality_score=float(item["quality_score"]),
            )
            updated += 1

        self.logger.info("Intelligence refresh complete updated=%d", updated)
        return updated

    def _prepare_embeddings_sync(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        prepared: list[dict[str, Any]] = []
        for row in rows:
            try:
                content_text, source = self._build_content_text(row)
                embedding = build_hash_embedding(content_text, self.embedding_dim)
                quality_score = min(1.0, len(tokenize(content_text)) / 300.0)
                prepared.append(
                    {
                        "video_id": str(row["video_id"]),
                        "content_text": content_text,
                        "transcript_source": source,
                        "embedding": embedding,
                        "quality_score": quality_score,
                    }
                )
            except Exception:
                self.logger.exception("Failed to build intelligence for video_id=%s", row.get("video_id"))
        return prepared

    def _build_content_text(self, row: dict[str, Any]) -> tuple[str, str]:
        video_id = str(row.get("video_id") or "").strip()
        title = str(row.get("title") or "")
        channel = str(row.get("channel") or "")
        source_url = str(row.get("source_url") or "").strip()
        if source_url and not source_url.startswith("http") and video_id:
            source_url = f"https://www.youtube.com/watch?v={video_id}"
        if not source_url and video_id:
            source_url = f"https://www.youtube.com/watch?v={video_id}"

        extra_text = ""
        source = "metadata"
        if source_url:
            transcript, metadata = self._fetch_transcript_and_metadata(source_url)
            if transcript:
                extra_text = transcript
                source = metadata.get("transcript_source", "transcript")
            else:
                description = metadata.get("description") or ""
                tags = metadata.get("tags") or ""
                extra_text = f"{description}\n{tags}".strip()

        if not extra_text:
            extra_text = source_url

        content_text = f"{title}\n{channel}\n{extra_text}".strip()
        if len(content_text) > self.max_text_chars:
            content_text = content_text[: self.max_text_chars]
        return content_text, source

    def _fetch_transcript_and_metadata(self, url: str) -> tuple[str | None, dict[str, str]]:
        opts = {
            "quiet": True,
            "no_warnings": True,
            "ignoreerrors": True,
            "skip_download": True,
            "writesubtitles": False,
            "writeautomaticsub": False,
        }
        metadata: dict[str, str] = {}
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)

        if not isinstance(info, dict):
            return None, metadata

        metadata["description"] = str(info.get("description") or "")
        tags = info.get("tags")
        if isinstance(tags, list):
            metadata["tags"] = " ".join(str(tag) for tag in tags)

        subtitle_url, source = self._select_subtitle_track(info)
        if not subtitle_url:
            return None, metadata

        transcript = self._download_subtitle_text(subtitle_url)
        if transcript:
            metadata["transcript_source"] = source
            return transcript, metadata
        return None, metadata

    def _select_subtitle_track(self, info: dict[str, Any]) -> tuple[str | None, str]:
        manual = info.get("subtitles")
        auto = info.get("automatic_captions")

        selected_url = self._pick_track_url(manual)
        if selected_url:
            return selected_url, "manual_subtitle"

        selected_url = self._pick_track_url(auto)
        if selected_url:
            return selected_url, "auto_subtitle"

        return None, "metadata"

    def _pick_track_url(self, tracks: Any) -> str | None:
        if not isinstance(tracks, dict):
            return None

        preferred_order = [
            "en",
            "en-US",
            "en-GB",
            "en-orig",
            "en-US-orig",
        ]

        for lang in preferred_order:
            entries = tracks.get(lang)
            url = self._pick_entry_url(entries)
            if url:
                return url

        for lang, entries in tracks.items():
            if str(lang).lower().startswith("en"):
                url = self._pick_entry_url(entries)
                if url:
                    return url

        for entries in tracks.values():
            url = self._pick_entry_url(entries)
            if url:
                return url

        return None

    @staticmethod
    def _pick_entry_url(entries: Any) -> str | None:
        if not isinstance(entries, list):
            return None

        preferred_ext = ["vtt", "srv3", "json3", "ttml"]
        for ext in preferred_ext:
            for item in entries:
                if not isinstance(item, dict):
                    continue
                if str(item.get("ext") or "").lower() == ext and item.get("url"):
                    return str(item["url"])

        for item in entries:
            if isinstance(item, dict) and item.get("url"):
                return str(item["url"])

        return None

    def _download_subtitle_text(self, url: str) -> str | None:
        try:
            with urlopen(url, timeout=8) as response:
                raw = response.read(2_000_000)
        except (TimeoutError, URLError, ValueError):
            return None

        if not raw:
            return None

        text = raw.decode("utf-8", errors="ignore")
        if text.lstrip().startswith("{"):
            extracted = _extract_json3_text(text)
            if extracted:
                return extracted[: self.max_text_chars]

        lines: list[str] = []
        last_line = ""
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.upper().startswith("WEBVTT"):
                continue
            if "-->" in stripped:
                continue
            if stripped.isdigit():
                continue

            stripped = HTML_TAG_RE.sub("", stripped)
            stripped = stripped.replace("&nbsp;", " ").replace("&amp;", "&")
            if not stripped:
                continue

            if stripped == last_line:
                continue
            lines.append(stripped)
            last_line = stripped

        if not lines:
            return None
        return " ".join(lines)[: self.max_text_chars]


def tokenize(text: str) -> list[str]:
    return [tok.lower() for tok in TOKEN_RE.findall(text)]


def build_hash_embedding(text: str, dim: int) -> list[float]:
    vec = [0.0] * dim
    tokens = tokenize(text)
    if not tokens:
        return vec

    term_freq: dict[str, int] = {}
    for token in tokens:
        term_freq[token] = term_freq.get(token, 0) + 1

    for token, freq in term_freq.items():
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        idx = int.from_bytes(digest[:4], byteorder="little", signed=False) % dim
        sign = 1.0 if (digest[4] & 1) == 0 else -1.0
        vec[idx] += sign * float(freq)

    norm = math.sqrt(sum(x * x for x in vec))
    if norm <= 0:
        return vec
    return [round(x / norm, 6) for x in vec]


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    if len(vec_a) != len(vec_b) or not vec_a:
        return 0.0
    return sum(a * b for a, b in zip(vec_a, vec_b))


def parse_embedding(raw: str) -> list[float]:
    if not raw:
        return []
    try:
        values = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(values, list):
        return []

    vector: list[float] = []
    for value in values:
        try:
            vector.append(float(value))
        except (TypeError, ValueError):
            return []
    return vector


def _extract_json3_text(raw: str) -> str | None:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None

    events = data.get("events")
    if not isinstance(events, list):
        return None

    chunks: list[str] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        segs = event.get("segs")
        if not isinstance(segs, list):
            continue
        for seg in segs:
            if isinstance(seg, dict) and seg.get("utf8"):
                text = str(seg["utf8"]).strip()
                if text:
                    chunks.append(text)

    if not chunks:
        return None
    return " ".join(chunks)
