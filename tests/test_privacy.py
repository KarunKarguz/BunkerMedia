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

    def test_pin_rotation_and_channel_rules(self):
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
                    ]
                ),
                encoding="utf-8",
            )

            async def _run() -> None:
                service = BunkerService(cfg_path)
                await service.initialize()
                service.db.upsert_video(
                    VideoMetadata(video_id="allow-1", title="Alpha Show", channel="Alpha", downloaded=False)
                )
                service.db.upsert_video(
                    VideoMetadata(video_id="other-1", title="Beta Show", channel="Beta", downloaded=False)
                )
                service.db.upsert_video(
                    VideoMetadata(video_id="block-1", title="Blocked Show", channel="Blocked", downloaded=False)
                )

                profile = service.create_profile("Kids Locked", is_kids=True, pin="2468")
                self.assertIsNotNone(profile)
                self.assertIsNone(
                    service.update_profile(
                        str(profile["profile_id"]),
                        pin="1357",
                        current_pin="0000",
                    )
                )
                updated = service.update_profile(
                    str(profile["profile_id"]),
                    pin="1357",
                    current_pin="2468",
                    allow_channels=["Alpha"],
                    block_channels=["Blocked"],
                )
                self.assertIsNotNone(updated)
                self.assertEqual(updated["allowed_channels"], ["alpha"])
                self.assertEqual(updated["blocked_channels"], ["blocked"])

                self.assertIsNone(service.select_profile(str(profile["profile_id"]), pin="2468"))
                self.assertIsNotNone(service.select_profile(str(profile["profile_id"]), pin="1357"))

                visible = service.list_videos(limit=20)
                self.assertEqual([item["video_id"] for item in visible], ["allow-1"])
                await service.shutdown()

            asyncio.run(_run())

    def test_profile_rejection_does_not_leak_to_default_profile(self):
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
                    ]
                ),
                encoding="utf-8",
            )

            async def _run() -> None:
                service = BunkerService(cfg_path)
                await service.initialize()
                service.db.upsert_video(
                    VideoMetadata(video_id="reject-1", title="Quiet Documentary", channel="Calm", downloaded=False)
                )

                profile = service.create_profile("Second Viewer", is_kids=False, can_access_private=False)
                self.assertIsNotNone(profile)
                self.assertIsNotNone(service.select_profile(str(profile["profile_id"])))
                self.assertTrue(service.reject_video("reject-1", reason="not_interested"))

                scoped = service.get_video("reject-1")
                self.assertIsNotNone(scoped)
                self.assertEqual(scoped["rejected_reason"], "not_interested")

                self.assertIsNotNone(service.select_profile("default"))
                default_view = service.get_video("reject-1")
                self.assertIsNotNone(default_view)
                self.assertIsNone(default_view["rejected_reason"])
                await service.shutdown()

            asyncio.run(_run())


if __name__ == "__main__":
    unittest.main()
