import asyncio
import tempfile
import unittest
from pathlib import Path

from bunkermedia.models import VideoMetadata
from bunkermedia.service import BunkerService
from bunkermedia.storage_privacy import StoragePrivacyMonitor


class PrivacyTests(unittest.TestCase):
    def test_storage_privacy_marker_compliance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            media_root = root / "media"
            media_root.mkdir(parents=True, exist_ok=True)

            monitor = StoragePrivacyMonitor(
                media_root=media_root,
                private_mode_enabled=True,
                require_encrypted_store=True,
                marker_filename=".vault-marker",
            )
            warning = monitor.snapshot()
            self.assertEqual(warning["status"], "warning")

            (media_root / ".vault-marker").write_text("ok", encoding="utf-8")
            ready = monitor.snapshot()
            self.assertEqual(ready["status"], "ok")
            self.assertTrue(ready["marker_present"])

    def test_private_video_hidden_without_vault_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg_path = root / "config.yaml"
            cfg_path.write_text(
                "\n".join(
                    [
                        "download_path: ./media",
                        "database_path: ./bunkermedia.db",
                        "download_archive: ./archive.txt",
                        "auto_start_workers: false",
                        "force_offline_mode: true",
                        "private_mode_enabled: true",
                        "private_require_encrypted_store: true",
                    ]
                ),
                encoding="utf-8",
            )

            async def _run() -> None:
                service = BunkerService(cfg_path)
                await service.initialize()
                (service.config.download_path / service.config.private_storage_marker_file).write_text(
                    "verified",
                    encoding="utf-8",
                )

                media_file = service.config.download_path / "youtube" / "single" / "secret.mp4"
                media_file.parent.mkdir(parents=True, exist_ok=True)
                media_file.write_bytes(b"secret")
                service.db.upsert_video(
                    VideoMetadata(
                        video_id="secret-1",
                        title="Secret Clip",
                        channel="Vault",
                        source_url="https://example.invalid/secret",
                        local_path=str(media_file),
                        downloaded=True,
                    )
                )
                service.db.mark_downloaded("secret-1", str(media_file))

                created = service.create_profile("Vault", can_access_private=True, pin="2468")
                self.assertTrue(created["pin_required"])
                self.assertIsNone(service.select_profile(created["profile_id"], pin="0000"))
                selected = service.select_profile(created["profile_id"], pin="2468")
                self.assertIsNotNone(selected)
                self.assertTrue(service.set_video_privacy("secret-1", "private"))

                visible = service.list_videos(limit=20, search="Secret")
                self.assertEqual(len(visible), 1)
                self.assertEqual(visible[0]["privacy_level"], "private")

                service.select_profile("default")
                default_visible = service.list_videos(limit=20, search="Secret")
                self.assertEqual(len(default_visible), 0)
                self.assertEqual(service.get_privacy_state()["status"], "ok")
                await service.shutdown()

            asyncio.run(_run())


if __name__ == "__main__":
    unittest.main()
