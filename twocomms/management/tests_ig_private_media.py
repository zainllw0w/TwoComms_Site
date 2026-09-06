import os
import stat
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.core.files.base import ContentFile
from django.test import SimpleTestCase, override_settings


class PrivateMediaFdStorageTests(SimpleTestCase):
    def _root(self, directory: str) -> Path:
        root = Path(directory).resolve()
        os.chmod(root, 0o700)
        return root

    def test_save_avoids_unsupported_path_chmod_and_repeats_safely(self):
        from management.services.ig_private_media import private_media_storage

        with tempfile.TemporaryDirectory() as directory:
            root = self._root(directory)
            with override_settings(IG_PRIVATE_MEDIA_ROOT=str(root)), patch(
                "management.services.ig_private_media.os.chmod",
                side_effect=NotImplementedError(
                    "chmod: follow_symlinks unavailable on this platform"
                ),
            ) as path_chmod:
                storage = private_media_storage()
                first = storage.save("messages/client/photo.jpg", ContentFile(b"one"))
                second = storage.save("messages/client/photo.jpg", ContentFile(b"two"))

            path_chmod.assert_not_called()
            self.assertNotEqual(first, second)
            self.assertEqual((root / first).read_bytes(), b"one")
            self.assertEqual((root / second).read_bytes(), b"two")
            self.assertEqual(stat.S_IMODE(root.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE((root / "messages").stat().st_mode), 0o700)
            self.assertEqual(
                stat.S_IMODE((root / "messages" / "client").stat().st_mode),
                0o700,
            )
            self.assertEqual(stat.S_IMODE((root / first).stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE((root / second).stat().st_mode), 0o600)

    def test_save_rejects_symlink_directory_escape(self):
        from management.services.ig_private_media import private_media_storage

        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            root = self._root(directory)
            (root / "escape").symlink_to(Path(outside), target_is_directory=True)
            with override_settings(IG_PRIVATE_MEDIA_ROOT=str(root)):
                storage = private_media_storage()
                with self.assertRaises(OSError):
                    storage.save("escape/stolen.jpg", ContentFile(b"secret"))

            self.assertFalse((Path(outside) / "stolen.jpg").exists())

    def test_save_closes_and_removes_file_when_unlock_fails(self):
        from management.services.ig_private_media import private_media_storage

        with tempfile.TemporaryDirectory() as directory:
            root = self._root(directory)
            with override_settings(IG_PRIVATE_MEDIA_ROOT=str(root)), patch(
                "django.core.files.locks.unlock",
                side_effect=RuntimeError("unlock failed"),
            ) as unlock:
                with self.assertRaisesRegex(RuntimeError, "unlock failed"):
                    private_media_storage().save(
                        "messages/photo.jpg", ContentFile(b"image")
                    )

            descriptor = unlock.call_args.args[0]
            with self.assertRaises(OSError):
                os.fstat(descriptor)
            self.assertEqual(list(root.rglob("*.jpg")), [])

    def test_missing_nofollow_fails_readiness(self):
        from management.services.ig_private_media import private_media_storage

        with tempfile.TemporaryDirectory() as directory:
            root = self._root(directory)
            with override_settings(IG_PRIVATE_MEDIA_ROOT=str(root)), patch.object(
                os, "O_NOFOLLOW", 0
            ):
                with self.assertRaisesRegex(ImproperlyConfigured, "O_NOFOLLOW"):
                    private_media_storage()

    def test_open_rejects_fifo_without_blocking(self):
        from management.services.ig_private_media import private_media_storage

        with tempfile.TemporaryDirectory() as directory:
            root = self._root(directory)
            os.mkfifo(root / "pipe", 0o600)
            with override_settings(IG_PRIVATE_MEDIA_ROOT=str(root)):
                with self.assertRaises(PermissionError):
                    private_media_storage().open("pipe")

    def test_open_closes_descriptor_when_fdopen_fails(self):
        from management.services.ig_private_media import private_media_storage

        with tempfile.TemporaryDirectory() as directory:
            root = self._root(directory)
            (root / "photo.jpg").write_bytes(b"image")
            os.chmod(root / "photo.jpg", 0o600)
            with override_settings(IG_PRIVATE_MEDIA_ROOT=str(root)), patch(
                "management.services.ig_private_media.os.fdopen",
                side_effect=RuntimeError("fdopen failed"),
            ) as fdopen:
                with self.assertRaisesRegex(RuntimeError, "fdopen failed"):
                    private_media_storage().open("photo.jpg")

            descriptor = fdopen.call_args.args[0]
            with self.assertRaises(OSError):
                os.fstat(descriptor)
