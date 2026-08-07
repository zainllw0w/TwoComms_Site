"""Contracts for the reproducible, build-time-only http-ece wheel."""

from __future__ import annotations

import gzip
import hashlib
import io
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path
import re

from scripts.build_http_ece_wheel import (
    DEFAULT_SOURCE_DATE_EPOCH,
    EXPECTED_SDIST_SHA256,
    EXPECTED_WHEEL_SHA256,
    build_wheel,
    update_lock_hashes,
)


ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = ROOT / "twocomms" / "requirements.lock"


def _tar_bytes(files: dict[str, bytes | None]) -> bytes:
    raw = io.BytesIO()
    with gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode="w") as archive:
            for name, content in sorted(files.items()):
                member = tarfile.TarInfo(name)
                member.mode = 0o644
                member.mtime = 0
                if content is None:
                    member.type = tarfile.DIRTYPE
                    member.mode = 0o755
                    archive.addfile(member)
                else:
                    member.size = len(content)
                    archive.addfile(member, io.BytesIO(content))
    return raw.getvalue()


def _fixture_sdist_bytes(
    *, unsafe_name: str | None = None, include_directories: bool = False
) -> bytes:
    package_name = unsafe_name or "http_ece-1.2.1/http_ece/__init__.py"
    files: dict[str, bytes | None] = {
            "http_ece-1.2.1/PKG-INFO": (
                b"Metadata-Version: 2.1\n"
                b"Name: http_ece\n"
                b"Version: 1.2.1\n"
                b"Summary: Encrypted Content Encoding for HTTP\n"
                b"Requires-Dist: cryptography>=2.5\n\n"
                b"Encipher HTTP Messages\n"
            ),
            package_name: b"SENTINEL = 'offline-wheel'\n",
    }
    if include_directories:
        files["http_ece-1.2.1"] = None
        files["http_ece-1.2.1/http_ece"] = None
    return _tar_bytes(files)


class HttpEceWheelBuilderTests(unittest.TestCase):
    def test_rejects_sdist_with_wrong_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sdist = root / "http_ece-1.2.1.tar.gz"
            sdist.write_bytes(_fixture_sdist_bytes())

            with self.assertRaisesRegex(ValueError, "sdist SHA256 mismatch"):
                build_wheel(
                    sdist,
                    root / "wheelhouse",
                    expected_sdist_sha256="0" * 64,
                )

    def test_rejects_unsafe_archive_members(self):
        archive_bytes = _fixture_sdist_bytes(
            unsafe_name="http_ece-1.2.1/../outside.py"
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sdist = root / "http_ece-1.2.1.tar.gz"
            sdist.write_bytes(archive_bytes)

            with self.assertRaisesRegex(ValueError, "unsafe archive member"):
                build_wheel(
                    sdist,
                    root / "wheelhouse",
                    expected_sdist_sha256=hashlib.sha256(archive_bytes).hexdigest(),
                )

    def test_accepts_safe_directory_members_from_real_sdist_shape(self):
        archive_bytes = _fixture_sdist_bytes(include_directories=True)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sdist = root / "http_ece-1.2.1.tar.gz"
            sdist.write_bytes(archive_bytes)

            wheel = build_wheel(
                sdist,
                root / "wheelhouse",
                expected_sdist_sha256=hashlib.sha256(archive_bytes).hexdigest(),
            )

            self.assertTrue(wheel.is_file())

    def test_build_is_byte_for_byte_reproducible(self):
        archive_bytes = _fixture_sdist_bytes()
        source_hash = hashlib.sha256(archive_bytes).hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sdist = root / "http_ece-1.2.1.tar.gz"
            sdist.write_bytes(archive_bytes)

            first = build_wheel(
                sdist,
                root / "first",
                expected_sdist_sha256=source_hash,
            )
            second = build_wheel(
                sdist,
                root / "second",
                expected_sdist_sha256=source_hash,
            )

            self.assertEqual(first.name, "http_ece-1.2.1-py2.py3-none-any.whl")
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with zipfile.ZipFile(first) as wheel:
                self.assertEqual(
                    wheel.namelist(),
                    [
                        "http_ece/__init__.py",
                        "http_ece-1.2.1.dist-info/METADATA",
                        "http_ece-1.2.1.dist-info/WHEEL",
                        "http_ece-1.2.1.dist-info/RECORD",
                    ],
                )
                timestamps = {item.date_time for item in wheel.infolist()}
                self.assertEqual(len(timestamps), 1)
                self.assertEqual(next(iter(timestamps)), (1980, 1, 1, 0, 0, 0))
                self.assertIn(
                    "Tag: py2-none-any\nTag: py3-none-any\n",
                    wheel.read("http_ece-1.2.1.dist-info/WHEEL").decode(),
                )

    def test_repo_lock_contains_source_and_reproducible_wheel_hashes(self):
        self.assertRegex(EXPECTED_SDIST_SHA256, r"^[0-9a-f]{64}$")
        self.assertRegex(EXPECTED_WHEEL_SHA256, r"^[0-9a-f]{64}$")
        self.assertNotEqual(EXPECTED_WHEEL_SHA256, "0" * 64)
        lock = LOCK_PATH.read_text(encoding="utf-8")
        block_match = re.search(
            r"http-ece==1\.2\.1.*?(?=\n[A-Za-z0-9][A-Za-z0-9_.-]*==)",
            lock,
            re.DOTALL,
        )
        self.assertIsNotNone(block_match)
        block = block_match.group(0)
        self.assertIn(f"--hash=sha256:{EXPECTED_SDIST_SHA256}", block)
        self.assertIn(f"--hash=sha256:{EXPECTED_WHEEL_SHA256}", block)

    def test_offline_binary_only_hash_install_accepts_built_wheel(self):
        archive_bytes = _fixture_sdist_bytes()
        source_hash = hashlib.sha256(archive_bytes).hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sdist = root / "http_ece-1.2.1.tar.gz"
            sdist.write_bytes(archive_bytes)
            wheel = build_wheel(
                sdist,
                root / "wheelhouse",
                expected_sdist_sha256=source_hash,
            )
            wheel_hash = hashlib.sha256(wheel.read_bytes()).hexdigest()
            lock = root / "install.lock"
            lock.write_text(
                "http-ece==1.2.1 \\\n"
                f"    --hash=sha256:{source_hash} \\\n"
                f"    --hash=sha256:{wheel_hash}\n",
                encoding="utf-8",
            )
            update_lock_hashes(lock, wheel, expected_sdist_sha256=source_hash)
            target = root / "target"

            install = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "--disable-pip-version-check",
                    "--no-index",
                    "--find-links",
                    str(wheel.parent),
                    "--only-binary",
                    ":all:",
                    "--require-hashes",
                    "--no-deps",
                    "--target",
                    str(target),
                    "-r",
                    str(lock),
                ],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(install.returncode, 0, install.stdout + install.stderr)
            imported = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    (
                        "import sys; "
                        f"sys.path.insert(0, {str(target)!r}); "
                        "import http_ece; print(http_ece.SENTINEL)"
                    ),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(imported.returncode, 0, imported.stderr)
            self.assertEqual(imported.stdout.strip(), "offline-wheel")

    def test_default_source_date_epoch_is_zip_portable(self):
        self.assertEqual(DEFAULT_SOURCE_DATE_EPOCH, 315532800)


if __name__ == "__main__":
    unittest.main()
