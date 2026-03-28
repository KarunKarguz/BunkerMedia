#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from bunkermedia.models import VideoMetadata  # noqa: E402
from bunkermedia.service import BunkerService  # noqa: E402


def _stable_token(value: str, size: int = 12) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:size]


class _AlwaysOnline:
    def __init__(self) -> None:
        self.is_online = True

    async def refresh(self) -> bool:
        self.is_online = True
        return True

    def in_sync_window(self, *_args: Any, **_kwargs: Any) -> bool:
        return True


class _NoopIntelligence:
    async def refresh_embeddings(self, limit: int = 40) -> int:
        return min(limit, 0)


class _SoakScraper:
    @staticmethod
    def _entries(seed: str, label: str, channel: str, count: int) -> list[VideoMetadata]:
        rows: list[VideoMetadata] = []
        for index in range(1, count + 1):
            token = _stable_token(f"{seed}:{index}")
            rows.append(
                VideoMetadata(
                    video_id=f"batch_{token}",
                    title=f"{label} Item {index}",
                    channel=channel,
                    source_url=f"https://example.invalid/watch/{token}",
                    playlist_index=index,
                    upload_date="20260328",
                    duration_seconds=900 + (index * 60),
                )
            )
        return rows

    async def fetch_playlist_metadata(self, playlist_url: str, limit: int = 100) -> list[VideoMetadata]:
        return self._entries(playlist_url, "Playlist", "Playlist Feed", min(limit, 6))

    async def fetch_channel_feed(self, channel_url: str, limit: int = 50) -> list[VideoMetadata]:
        return self._entries(channel_url, "Channel", "Channel Feed", min(limit, 5))

    async def fetch_trending(self, limit: int = 50) -> list[VideoMetadata]:
        return self._entries("trending", "Trending", "Trending Feed", min(limit, 4))


class _SoakDownloader:
    def __init__(self, service: BunkerService) -> None:
        self.service = service

    async def download_url(self, url: str, target_type: str = "auto", batch_id: int | None = None) -> list[VideoMetadata]:
        rows: list[dict[str, Any]] = []
        if batch_id is not None:
            entries = self.service.db.conn.execute(
                """
                SELECT video_id, title, source_url, item_index
                FROM download_batch_items
                WHERE batch_id=?
                ORDER BY item_index ASC, video_id ASC
                """,
                (batch_id,),
            ).fetchall()
            rows = [dict(row) for row in entries]

        if not rows:
            token = _stable_token(url)
            rows = [
                {
                    "video_id": f"single_{token}",
                    "title": f"Soak Item {token[:6]}",
                    "source_url": url,
                    "item_index": 1,
                }
            ]

        written: list[VideoMetadata] = []
        channel = {
            "playlist": "Playlist Feed",
            "channel": "Channel Feed",
            "trending": "Trending Feed",
        }.get(target_type, "Soak Feed")

        for row in rows:
            video_id = str(row["video_id"])
            title = str(row.get("title") or video_id)
            source_url = str(row.get("source_url") or url)
            local_path = self.service.config.download_path / "soak" / channel.lower().replace(" ", "-") / f"{video_id}.mp4"
            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_bytes((video_id * 3).encode("utf-8"))
            metadata = VideoMetadata(
                video_id=video_id,
                title=title,
                channel=channel,
                source_url=source_url,
                upload_date="20260328",
                local_path=str(local_path),
                downloaded=True,
                duration_seconds=1200 + (int(row.get("item_index") or 1) * 45),
                file_size_bytes=local_path.stat().st_size,
            )
            self.service.db.upsert_video(metadata)
            self.service.db.mark_downloaded(video_id, str(local_path))
            if batch_id is not None:
                self.service.db.mark_batch_item_done(batch_id, video_id, str(local_path))
            written.append(metadata)
        return written


def _write_config(root: Path) -> Path:
    config_path = root / "config.yaml"
    import_root = root / "imports"
    config_path.write_text(
        "\n".join(
            [
                "download_path: ./media",
                "database_path: ./bunkermedia.db",
                "download_archive: ./archive.txt",
                "auto_start_workers: false",
                "force_offline_mode: false",
                "auto_organize_imports: true",
                "import_watch_folders:",
                f"  - {import_root}",
                "update_intervals:",
                "  import_watch_seconds: 5",
            ]
        ),
        encoding="utf-8",
    )
    return config_path


def _drop_import_file(import_root: Path, index: int) -> None:
    suffix = ".mp4" if index % 2 else ".mp3"
    file_path = import_root / f"arrival-{index:03d}{suffix}"
    if not file_path.exists():
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(f"import-{index}".encode("utf-8"))


async def _wire_test_doubles(service: BunkerService) -> None:
    always_online = _AlwaysOnline()
    service.network = always_online
    service.workers.network = always_online
    service.scraper = _SoakScraper()
    service.workers.scraper = service.scraper
    service.intelligence = _NoopIntelligence()
    service.workers.intelligence = service.intelligence
    service.downloader = _SoakDownloader(service)
    service.workers.downloader = service.downloader


async def _run_phase(
    service: BunkerService,
    *,
    cycles: int,
    queue_start: int,
    queue_count: int,
    batch_jobs: int,
    import_start: int,
) -> dict[str, int]:
    import_root = service.config.import_watch_folders[0]

    for index in range(queue_start, queue_start + queue_count):
        target_type = "single"
        if batch_jobs > 0 and index < queue_start + batch_jobs:
            target_type = "playlist" if index % 2 else "channel"
        await service.add_url(f"https://example.invalid/source/{index}", target_type=target_type, priority=2)

    dropped_imports = 0
    for cycle in range(cycles):
        if cycle % 6 == 0:
            _drop_import_file(import_root, import_start + dropped_imports)
            dropped_imports += 1
        if cycle % 11 == 0:
            await service.add_url(f"https://example.invalid/trending/{queue_start + cycle}", target_type="single", priority=1)
        await service.workers.process_download_queue_once()
        await service.workers._run_import_watch()
        await service.workers._run_recommendation_refresh()

    drain_loops = 0
    while service.list_download_jobs(status="pending", limit=100):
        await service.workers.process_download_queue_once()
        drain_loops += 1
        if drain_loops > max(10, cycles):
            break

    return {"dropped_imports": dropped_imports, "drain_loops": drain_loops}


async def _run_soak(args: argparse.Namespace) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="bunkermedia-soak-") as tmp:
        root = Path(tmp)
        config_path = _write_config(root)
        total_imports = 0
        drain_loops = 0
        summary: dict[str, Any] = {}

        for phase in range(args.restarts + 1):
            service = BunkerService(config_path=config_path)
            await service.initialize()
            await _wire_test_doubles(service)
            outcome = await _run_phase(
                service,
                cycles=args.cycles,
                queue_start=(phase * args.seed_jobs),
                queue_count=args.seed_jobs,
                batch_jobs=args.batch_jobs,
                import_start=phase * max(1, args.cycles // 6 + 1),
            )
            total_imports += int(outcome["dropped_imports"])
            drain_loops += int(outcome["drain_loops"])

            if phase == args.restarts:
                recommendations = await service.recommend(limit=12, explain=True)
                videos = service.list_videos(limit=500)
                health = service.get_health_state()
                jobs = {
                    state: len(service.list_download_jobs(status=state, limit=500))
                    for state in ("pending", "processing", "paused", "done", "dead")
                }
                deadletters = len(service.list_dead_letter_jobs(limit=500))
                batches = service.list_download_batches(limit=500)
                summary = {
                    "status": "ok",
                    "cycles_per_phase": args.cycles,
                    "restart_count": args.restarts,
                    "seed_jobs_per_phase": args.seed_jobs,
                    "seed_batch_jobs_per_phase": args.batch_jobs,
                    "imports_written": total_imports,
                    "drain_loops": drain_loops,
                    "video_count": len(videos),
                    "downloaded_count": sum(1 for item in videos if int(item.get("downloaded") or 0) == 1),
                    "queue": jobs,
                    "deadletters": deadletters,
                    "batches": {
                        "count": len(batches),
                        "completed": sum(1 for batch in batches if batch.get("status") == "completed"),
                        "partial": sum(1 for batch in batches if batch.get("status") == "partial"),
                    },
                    "offline_inventory": service.get_offline_inventory(),
                    "health": {
                        "status": health.get("status"),
                        "schema_version": health.get("schema_version"),
                        "import_watch_enabled": health.get("import_watch_enabled"),
                    },
                    "recommendation_count": len(recommendations),
                    "sample_recommendations": [item.video_id for item in recommendations[:5]],
                }
            await service.shutdown()

        if summary["deadletters"] != 0:
            raise RuntimeError("Soak validation failed: dead-letter queue is not empty")
        if summary["queue"]["pending"] != 0 or summary["queue"]["processing"] != 0:
            raise RuntimeError("Soak validation failed: queue did not drain cleanly")
        if summary["video_count"] < args.seed_jobs:
            raise RuntimeError("Soak validation failed: too few videos were retained")
        if summary["health"]["status"] != "ok":
            raise RuntimeError("Soak validation failed: service health is not ok")
        return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a deterministic BunkerMedia soak validation pass.")
    parser.add_argument("--cycles", type=int, default=45, help="worker cycles per phase")
    parser.add_argument("--seed-jobs", type=int, default=12, help="queued jobs per phase")
    parser.add_argument("--batch-jobs", type=int, default=4, help="playlist/channel jobs per phase")
    parser.add_argument("--restarts", type=int, default=1, help="restart count during the run")
    parser.add_argument("--output", type=Path, default=None, help="optional JSON summary output path")
    args = parser.parse_args()

    summary = asyncio.run(_run_soak(args))
    payload = json.dumps(summary, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
