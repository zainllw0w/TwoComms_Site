"""Contracts for the immutable production wheelhouse builder."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import build_release_wheelhouse as builder
from scripts.build_release_wheelhouse import (
    CFFI_SDIST_SHA256,
    build_manifest,
    replace_package_hashes,
)


class ReleaseWheelhouseTests(unittest.TestCase):
    def test_cffi_install_hash_replaces_published_artifacts_without_version_drift(self):
        source_hash = CFFI_SDIST_SHA256
        wheel_hash = "a" * 64
        lock = (
            "alpha==1.0 \\\n"
            f"    --hash=sha256:{'1' * 64}\n"
            "cffi==2.1.1 \\\n"
            f"    --hash=sha256:{'2' * 64} \\\n"
            f"    --hash=sha256:{source_hash}\n"
            "omega==3.0 \\\n"
            f"    --hash=sha256:{'3' * 64}\n"
        )

        updated = replace_package_hashes(
            lock,
            package="cffi",
            version="2.1.1",
            required_source_hash=source_hash,
            wheel_hash=wheel_hash,
        )

        self.assertIn("alpha==1.0", updated)
        self.assertIn("omega==3.0", updated)
        cffi_block = updated.split("cffi==2.1.1", 1)[1].split("omega==3.0", 1)[0]
        self.assertIn(source_hash, cffi_block)
        self.assertIn(wheel_hash, cffi_block)
        self.assertNotIn("2" * 64, cffi_block)

    def test_cffi_hash_rewrite_rejects_missing_verified_sdist(self):
        lock = "cffi==2.1.1 \\\n    --hash=sha256:" + "2" * 64 + "\n"

        with self.assertRaisesRegex(ValueError, "verified source hash"):
            replace_package_hashes(
                lock,
                package="cffi",
                version="2.1.1",
                required_source_hash=CFFI_SDIST_SHA256,
                wheel_hash="a" * 64,
            )

    def test_manifest_is_target_bound_and_hashes_every_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            wheelhouse = Path(directory)
            (wheelhouse / "b.whl").write_bytes(b"b")
            (wheelhouse / "a.whl").write_bytes(b"a")
            (wheelhouse / "requirements.install.lock").write_text(
                "a==1 --hash=sha256:" + "0" * 64 + "\n",
                encoding="utf-8",
            )
            target_sha = "f" * 40
            source_lock_sha256 = "e" * 64

            manifest_path = build_manifest(
                wheelhouse,
                target_sha=target_sha,
                source_lock_sha256=source_lock_sha256,
            )

            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["target_sha"], target_sha)
            self.assertEqual(payload["source_lock_sha256"], source_lock_sha256)
            self.assertEqual(list(payload["files"]), sorted(payload["files"]))
            self.assertNotIn(manifest_path.name, payload["files"])
            for name, digest in payload["files"].items():
                self.assertEqual(
                    digest,
                    hashlib.sha256((wheelhouse / name).read_bytes()).hexdigest(),
                )

    def test_manifest_rejects_symlink_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            wheelhouse = Path(directory)
            target = wheelhouse / "outside.whl"
            target.write_bytes(b"outside")
            (wheelhouse / "linked.whl").symlink_to(target)

            with self.assertRaisesRegex(ValueError, "regular artifact"):
                build_manifest(
                    wheelhouse,
                    target_sha="f" * 40,
                    source_lock_sha256="e" * 64,
                )

    def test_manifest_rejects_preexisting_manifest_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            wheelhouse = Path(directory)
            target = wheelhouse / "outside-manifest"
            target.write_text("do not overwrite", encoding="utf-8")
            (wheelhouse / "manifest.sha256").symlink_to(target)

            with self.assertRaisesRegex(ValueError, "manifest"):
                build_manifest(
                    wheelhouse,
                    target_sha="f" * 40,
                    source_lock_sha256="e" * 64,
                )
            self.assertEqual(target.read_text(encoding="utf-8"), "do not overwrite")

    def test_build_orchestrator_rebuilds_cffi_and_runs_offline_verification(self):
        target_sha = "f" * 40
        source_hash = CFFI_SDIST_SHA256
        lock_text = (
            "cffi==2.1.1 \\\n"
            f"    --hash=sha256:{source_hash}\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lock_path = root / "repo" / "twocomms" / "requirements.lock"
            lock_path.parent.mkdir(parents=True)
            lock_path.write_text(lock_text, encoding="utf-8")
            wheelhouse = root / "wheelhouse" / target_sha
            sdist = root / "cffi-2.1.1.tar.gz"
            sdist.write_bytes(b"verified source")
            cffi_wheel = root / "cffi-2.1.1-cp314-cp314-manylinux_2_28_x86_64.whl"
            cffi_wheel.write_bytes(b"verified wheel")
            calls: list[tuple[str, ...]] = []

            def fake_run(command, **kwargs):
                rendered = tuple(str(part) for part in command)
                calls.append(rendered)
                if rendered[-2:] == ("-m", "venv"):
                    Path(rendered[-1]).mkdir(parents=True, exist_ok=True)
                if "download" in rendered:
                    destination = Path(rendered[rendered.index("--dest") + 1])
                    (destination / "dependency-1.0-py3-none-any.whl").write_bytes(b"dependency")

            with (
                patch.object(builder, "_assert_builder_environment", return_value={}),
                patch.object(builder, "_tool_version", return_value="tool 1"),
                patch.object(builder, "_download_verified", return_value=sdist),
                patch.object(builder, "_validate_cffi_source"),
                patch.object(builder, "_build_cffi_once", return_value=cffi_wheel) as build_cffi,
                patch.object(builder, "_validate_cffi_wheel"),
                patch.object(builder, "build_http_ece_main", return_value=0) as build_http_ece,
                patch.object(builder, "_run", side_effect=fake_run),
            ):
                result = builder.build_wheelhouse(
                    target_sha=target_sha,
                    lock_path=lock_path,
                    wheelhouse=wheelhouse,
                    python=root / "python",
                    auditwheel="auditwheel",
                    image_digest=builder.EXPECTED_IMAGE_DIGEST,
                )

            self.assertEqual(result, wheelhouse)
            self.assertEqual(build_cffi.call_count, 2)
            self.assertTrue(build_http_ece.called)
            install = next(call for call in calls if "install" in call and "pip" in call)
            self.assertIn("--no-index", install)
            self.assertIn("--only-binary", install)
            self.assertIn("--require-hashes", install)
            self.assertTrue((wheelhouse / "manifest.sha256").is_file())


if __name__ == "__main__":
    unittest.main()
