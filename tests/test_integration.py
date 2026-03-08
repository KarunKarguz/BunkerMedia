import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from httpx import ASGITransport, AsyncClient

from bunkermedia.config import AppConfig
from bunkermedia.database import Database
from bunkermedia.metrics import MetricsRegistry
from bunkermedia.models import VideoMetadata
from bunkermedia.network import NetworkStateManager
from bunkermedia.server import create_app
from bunkermedia.workers import WorkerManager
from bunkermedia.providers.local import LocalFolderProvider
from bunkermedia.providers.rss import RSSProvider


class _FakeDownloader:
    async def download_url(self, url: str, target_type: str = "auto"):
        raise RuntimeError("mock download failure")


class _FakeScraper:
    async def fetch_playlist_metadata(self, playlist_url: str, limit: int = 100):
        return []

    async def fetch_channel_feed(self, channel_url: str, limit: int = 50):
        return []

    async def fetch_trending(self, limit: int = 50):
        return []


class _FakeIntelligence:
    async def refresh_embeddings(self, limit: int = 40):
        return 0


class _FakeRecommender:
    async def refresh_scores(self):
        return None


class _FakeLogger:
    def info(self, *args, **kwargs):
        return None

    def warning(self, *args, **kwargs):
        return None

    def exception(self, *args, **kwargs):
        return None


class _AlwaysOnline:
    async def refresh(self):
        return True

    def in_sync_window(self):
        return True


class IntegrationTests(unittest.TestCase):
    def test_worker_deadletters_with_mock_downloader(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = AppConfig.from_yaml(root / "config.yaml")
            cfg.max_download_attempts = 1
            cfg.retry_base_seconds = 1
            cfg.retry_max_seconds = 1
            cfg.max_parallel_downloads = 1

            db = Database(root / "jobs.db")
            db.initialize()
            job_id = db.queue_download("https://example.invalid/test", target_type="single")

            worker = WorkerManager(
                cfg,
                db,
                _FakeDownloader(),
                _FakeScraper(),
                _FakeIntelligence(),
                _FakeRecommender(),
                _FakeLogger(),
                _AlwaysOnline(),
                MetricsRegistry(),
            )

            asyncio.run(worker.process_download_queue_once())
            dead = db.list_dead_letter_jobs(limit=10)
            self.assertEqual(len(dead), 1)
            self.assertEqual(int(dead[0]["original_job_id"]), job_id)
            statuses = db.list_download_jobs(status="dead", limit=10)
            self.assertEqual(len(statuses), 1)
            db.close()

    def test_rss_provider_parses_feed(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Database(Path(tmp) / "rss.db")
            db.initialize()

            class _NoopDownloader:
                async def download_url(self, url: str, target_type: str = "auto"):
                    return []

            provider = RSSProvider(db=db, downloader=_NoopDownloader(), logger=_FakeLogger())
            feed = """
            <rss><channel><title>TestFeed</title>
            <item><title>Alpha</title><link>https://example.com/a.mp4</link><pubDate>Mon, 01 Jan 2024 10:00:00 GMT</pubDate></item>
            <item><title>Beta</title><guid>https://example.com/b.mp4</guid></item>
            </channel></rss>
            """

            with patch.object(RSSProvider, "_fetch_feed", return_value=feed):
                items = asyncio.run(provider.discover("https://example.com/feed.xml", limit=10))

            self.assertEqual(len(items), 2)
            self.assertTrue(items[0].video_id.startswith("rss_"))
            db.close()

    def test_local_provider_discovers_media_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            media_dir = root / "watch"
            media_dir.mkdir(parents=True, exist_ok=True)
            file1 = media_dir / "clip.mp4"
            file1.write_bytes(b"00")
            file2 = media_dir / "song.mp3"
            file2.write_bytes(b"11")

            db = Database(root / "local.db")
            db.initialize()
            provider = LocalFolderProvider(db=db, logger=_FakeLogger(), watch_folders=[media_dir])
            items = asyncio.run(provider.discover("default", limit=10))
            self.assertGreaterEqual(len(items), 2)
            rows = db.list_videos(limit=10)
            self.assertGreaterEqual(len(rows), 2)
            db.close()

    def test_network_manager_force_offline(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg_path = Path(tmp) / "config.yaml"
            cfg_path.write_text(
                "\n".join(
                    [
                        "download_path: ./media",
                        "database_path: ./db.sqlite",
                        "download_archive: ./archive.txt",
                        "force_offline_mode: true",
                    ]
                ),
                encoding="utf-8",
            )
            cfg = AppConfig.from_yaml(cfg_path)
            manager = NetworkStateManager(cfg, logger=_FakeLogger())
            online = asyncio.run(manager.refresh())
            self.assertFalse(online)
            self.assertFalse(manager.is_online)

    def test_api_startup_and_route_surface(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            media_dir = root / "local_media"
            media_dir.mkdir(parents=True, exist_ok=True)
            clip = media_dir / "episode.mp4"
            clip.write_bytes(b"1234")

            cfg_path = root / "config.yaml"
            cfg_path.write_text(
                "\n".join(
                    [
                        "download_path: ./media",
                        "database_path: ./db.sqlite",
                        "download_archive: ./archive.txt",
                        "auto_start_workers: false",
                        "force_offline_mode: true",
                        "local_watch_folders:",
                        f"  - {media_dir}",
                    ]
                ),
                encoding="utf-8",
            )

            app = create_app(cfg_path)
            paths = {route.path for route in app.routes}
            self.assertIn("/providers", paths)
            self.assertIn("/discover", paths)
            self.assertIn("/acquire", paths)
            self.assertIn("/schema", paths)
            self.assertIn("/metrics", paths)
            self.assertIn("/offline/inventory", paths)
            self.assertIn("/offline/plan", paths)
            self.assertIn("/storage/enforce", paths)

            async def _exercise_api() -> None:
                async with app.router.lifespan_context(app):
                    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
                        providers = await client.get("/providers")
                        self.assertEqual(providers.status_code, 200)
                        listed = providers.json()["providers"]
                        self.assertIn("local", listed)
                        self.assertIn("rss", listed)
                        self.assertIn("youtube", listed)

                        discovered = await client.get(
                            "/discover",
                            params={"provider": "local", "source": "", "limit": 10},
                        )
                        self.assertEqual(discovered.status_code, 200)
                        payload = discovered.json()
                        self.assertGreaterEqual(len(payload), 1)
                        self.assertTrue(str(payload[0]["video_id"]).startswith("local_"))

                        inventory = await client.get("/offline/inventory")
                        self.assertEqual(inventory.status_code, 200)
                        self.assertIn("downloaded_storage_bytes", inventory.json())

                        planned = await client.post("/offline/plan")
                        self.assertEqual(planned.status_code, 200)
                        self.assertIn("status", planned.json())

                        storage = await client.post("/storage/enforce")
                        self.assertEqual(storage.status_code, 200)
                        self.assertIn("status", storage.json())

            asyncio.run(_exercise_api())

    def test_api_queue_worker_recommendation_flow_with_mocked_downloader(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg_path = root / "config.yaml"
            cfg_path.write_text(
                "\n".join(
                    [
                        "download_path: ./media",
                        "database_path: ./db.sqlite",
                        "download_archive: ./archive.txt",
                        "auto_start_workers: false",
                        "force_offline_mode: true",
                    ]
                ),
                encoding="utf-8",
            )
            app = create_app(cfg_path)

            async def _exercise_flow() -> None:
                async with app.router.lifespan_context(app):
                    service = app.state.service

                    async def _always_allowed() -> bool:
                        return True

                    async def _mock_refresh_embeddings(limit: int = 40) -> int:
                        return 0

                    async def _mock_process_single_job(job, sem) -> None:
                        async with sem:
                            job_id = int(job["id"])
                            url = str(job["url"])
                        file_path = root / "media" / "youtube" / "channel" / "mock-video.mp4"
                        file_path.parent.mkdir(parents=True, exist_ok=True)
                        file_path.write_bytes(b"mock")
                        meta = VideoMetadata(
                            video_id="mockvid123",
                            title="Mock Video",
                            channel="Mock Channel",
                            upload_date="20260308",
                            source_url=url,
                            local_path=str(file_path),
                            downloaded=True,
                        )
                        service.db.upsert_video(meta)
                        service.db.mark_downloaded(meta.video_id, meta.local_path or str(file_path))
                        service.db.update_job_status(job_id, "done")

                    service.workers._allow_online_sync = _always_allowed  # type: ignore[method-assign]
                    service.workers._process_single_job = _mock_process_single_job  # type: ignore[method-assign]
                    service.intelligence.refresh_embeddings = _mock_refresh_embeddings  # type: ignore[method-assign]
                    service.workers.intelligence = service.intelligence

                    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
                        queued = await client.post(
                            "/queue",
                            json={
                                "url": "https://example.invalid/video",
                                "target_type": "single",
                                "priority": 5,
                            },
                        )
                        self.assertEqual(queued.status_code, 200)
                        self.assertEqual(queued.json().get("status"), "queued")

                        pending = await client.get("/jobs", params={"status": "pending", "limit": 10})
                        self.assertEqual(pending.status_code, 200)
                        self.assertGreaterEqual(len(pending.json()), 1)

                        await service.workers.process_download_queue_once()

                        done = await client.get("/jobs", params={"status": "done", "limit": 10})
                        self.assertEqual(done.status_code, 200)
                        self.assertGreaterEqual(len(done.json()), 1)

                        videos = await client.get("/videos", params={"search": "Mock", "limit": 10})
                        self.assertEqual(videos.status_code, 200)
                        self.assertGreaterEqual(len(videos.json()), 1)

                        recs = await client.get("/recommendations", params={"limit": 5, "explain": "true"})
                        self.assertEqual(recs.status_code, 200)
                        self.assertGreaterEqual(len(recs.json()), 1)

            asyncio.run(_exercise_flow())


if __name__ == "__main__":
    unittest.main()
