"""Contracts for the immutable production wheelhouse builder."""

from __future__ import annotations

import base64
import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from scripts import build_release_wheelhouse as builder
from scripts.build_release_wheelhouse import (
    CFFI_SDIST_SHA256,
    MYSQLCLIENT_SDIST_SHA256,
    build_manifest,
    replace_package_hashes,
)


class ReleaseWheelhouseTests(unittest.TestCase):
    def test_connector_c_source_and_library_are_pinned_to_fixed_3319_artifact(self):
        self.assertEqual(builder.MARIADB_CONNECTOR_C_VERSION, "3.3.19")
        self.assertEqual(
            builder.MARIADB_CONNECTOR_C_SOURCE_SHA256,
            "672bec76cfbb2fdb46ad4f681cd1e63c80721d7a07316e5849dc63e69d6ecdf7",
        )
        self.assertEqual(
            builder.MARIADB_CONNECTOR_C_LIBRARY_SHA256,
            "5395b9398e16b3313ed3d799771ec33a4661beb91833648b457a0bfdb0fb36ee",
        )
        self.assertEqual(
            builder.MARIADB_CONNECTOR_C_ROOT,
            Path("/opt/mariadb-connector-c-3.3.19"),
        )

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
            "mysqlclient==2.2.8 \\\n"
            f"    --hash=sha256:{MYSQLCLIENT_SDIST_SHA256}\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lock_path = root / "repo" / "twocomms" / "requirements.lock"
            lock_path.parent.mkdir(parents=True)
            lock_path.write_text(lock_text, encoding="utf-8")
            wheelhouse = root / "wheelhouse" / target_sha
            sdist = root / "cffi-2.1.1.tar.gz"
            sdist.write_bytes(b"verified source")
            mysqlclient_sdist = root / "mysqlclient-2.2.8.tar.gz"
            mysqlclient_sdist.write_bytes(b"verified mysqlclient source")
            setuptools_wheel = root / "setuptools-80.9.0-py3-none-any.whl"
            setuptools_wheel.write_bytes(b"verified build backend")
            cffi_wheel = root / "cffi-2.1.1-cp314-cp314-manylinux_2_28_x86_64.whl"
            cffi_wheel.write_bytes(b"verified wheel")
            mysqlclient_wheel = root / (
                "mysqlclient-2.2.8-cp314-cp314-manylinux_2_28_x86_64.whl"
            )
            mysqlclient_wheel.write_bytes(b"verified mysqlclient wheel")
            calls: list[tuple[str, ...]] = []

            def fake_run(command, **kwargs):
                rendered = tuple(str(part) for part in command)
                calls.append(rendered)
                if rendered[-2:] == ("-m", "venv"):
                    Path(rendered[-1]).mkdir(parents=True, exist_ok=True)
                if "download" in rendered:
                    destination = Path(rendered[rendered.index("--dest") + 1])
                    (destination / "dependency-1.0-py3-none-any.whl").write_bytes(b"dependency")

            def fake_download(url, destination, expected_hash):
                if "setuptools" in url:
                    return setuptools_wheel
                if "mysqlclient" in url:
                    return mysqlclient_sdist
                return sdist

            def fake_tool_version(command):
                if command[:3] == ["rpm", "-q", "libffi-devel"]:
                    return builder.EXPECTED_LIBFFI_DEVEL
                return "tool 1"

            connector_evidence = {
                "mariadb_connector_c_library_sha256": builder.MARIADB_CONNECTOR_C_LIBRARY_SHA256,
                "mariadb_connector_c_soname": "libmariadb.so.3",
                "mariadb_connector_c_source_sha256": builder.MARIADB_CONNECTOR_C_SOURCE_SHA256,
                "mariadb_connector_c_source_url": builder.MARIADB_CONNECTOR_C_SOURCE_URL,
                "mariadb_connector_c_version": "3.3.19",
            }
            bundled_evidence = {
                "mysqlclient_bundled_library_name": "mysqlclient.libs/libmariadb-deadbeef.so.3",
                "mysqlclient_bundled_library_sha256": "b" * 64,
                "mysqlclient_bundled_library_soname": "libmariadb-deadbeef.so.3",
            }

            with (
                patch.object(builder, "_assert_builder_environment", return_value={}),
                patch.object(builder, "_tool_version", side_effect=fake_tool_version),
                patch.object(
                    builder,
                    "_validate_mariadb_connector_c",
                    return_value=connector_evidence,
                ) as validate_connector,
                patch.object(builder, "_download_verified", side_effect=fake_download),
                patch.object(builder, "_validate_cffi_source"),
                patch.object(builder, "_build_cffi_once", return_value=cffi_wheel) as build_cffi,
                patch.object(builder, "_validate_cffi_wheel"),
                patch.object(builder, "_validate_mysqlclient_source"),
                patch.object(builder, "_build_mysqlclient_once", return_value=mysqlclient_wheel) as build_mysqlclient,
                patch.object(
                    builder,
                    "_validate_mysqlclient_wheel",
                    return_value=bundled_evidence,
                ),
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
            validate_connector.assert_called_once_with(builder.MARIADB_CONNECTOR_C_ROOT)
            self.assertEqual(build_cffi.call_count, 2)
            self.assertEqual(build_mysqlclient.call_count, 2)
            for call in build_cffi.call_args_list:
                self.assertIn("build-venv/bin/python", str(call.args[0]))
            self.assertTrue(build_http_ece.called)
            backend_install = next(
                call for call in calls if "install" in call and "setuptools-build.lock" in " ".join(call)
            )
            self.assertIn("--no-index", backend_install)
            self.assertIn("--only-binary", backend_install)
            self.assertIn("--require-hashes", backend_install)
            install = next(call for call in calls if "install" in call and "pip" in call)
            self.assertIn("--no-index", install)
            self.assertIn("--only-binary", install)
            self.assertIn("--require-hashes", install)
            mysqlclient_smokes = [
                call for call in calls if any("import MySQLdb" in part for part in call)
            ]
            self.assertTrue(mysqlclient_smokes)
            mysqlclient_smoke = mysqlclient_smokes[0]
            self.assertIn("verify-venv/bin/python", mysqlclient_smoke[0])
            self.assertIn("MySQLdb.version_info", mysqlclient_smoke[-1])
            self.assertTrue((wheelhouse / "manifest.sha256").is_file())
            evidence = json.loads(
                (wheelhouse / "builder-evidence.json").read_text(encoding="utf-8")
            )
            self.assertEqual(evidence["mariadb_connector_c_version"], "3.3.19")
            self.assertEqual(
                evidence["mariadb_connector_c_source_url"],
                builder.MARIADB_CONNECTOR_C_SOURCE_URL,
            )
            self.assertEqual(
                evidence["mysqlclient_bundled_library_sha256"],
                "b" * 64,
            )

    def test_mysqlclient_build_uses_the_pinned_connector_tree(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sdist = root / "mysqlclient-2.2.8.tar.gz"
            sdist.write_bytes(b"source")
            (root / "build").mkdir()
            environments: list[dict[str, str]] = []

            def fake_run(command, *, cwd=None, env=None):
                environments.append(dict(env or {}))
                rendered = tuple(str(part) for part in command)
                output = Path(rendered[rendered.index("--wheel-dir") + 1])
                name = (
                    "mysqlclient-2.2.8-cp314-cp314-manylinux_2_28_x86_64.whl"
                    if "repair" in rendered
                    else "mysqlclient-2.2.8-cp314-cp314-linux_x86_64.whl"
                )
                (output / name).write_bytes(b"wheel")

            with (
                patch.object(builder, "_run", side_effect=fake_run),
                patch.object(builder, "_normalize_wheel"),
            ):
                builder._build_mysqlclient_once(
                    root / "python",
                    "auditwheel",
                    sdist,
                    root / "build",
                    label="one",
                )

            build_env = environments[0]
            self.assertEqual(
                build_env["MYSQLCLIENT_CFLAGS"],
                "-I/opt/mariadb-connector-c-3.3.19/include/mariadb",
            )
            self.assertEqual(
                build_env["MYSQLCLIENT_LDFLAGS"],
                "-L/opt/mariadb-connector-c-3.3.19/lib/mariadb -lmariadb",
            )
            for environment in environments:
                self.assertEqual(
                    environment["LD_LIBRARY_PATH"],
                    "/opt/mariadb-connector-c-3.3.19/lib/mariadb",
                )

    def test_connector_tree_validation_records_version_hash_and_soname(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            include = root / "include" / "mariadb"
            library_dir = root / "lib" / "mariadb"
            include.mkdir(parents=True)
            library_dir.mkdir(parents=True)
            (include / "mariadb_version.h").write_text(
                '#define MARIADB_PACKAGE_VERSION "3.3.19"\n',
                encoding="utf-8",
            )
            library = library_dir / "libmariadb.so.3"
            library.write_bytes(b"pinned connector")
            archive = root / "connector.tar.gz"
            archive.write_bytes(b"pinned source")

            with (
                patch.object(
                    builder,
                    "sha256",
                    side_effect=lambda path: (
                        builder.MARIADB_CONNECTOR_C_SOURCE_SHA256
                        if Path(path) == archive
                        else builder.MARIADB_CONNECTOR_C_LIBRARY_SHA256
                    ),
                ),
                patch.object(builder, "_read_elf_soname", return_value="libmariadb.so.3"),
            ):
                evidence = builder._validate_mariadb_connector_c(
                    root,
                    source_archive=archive,
                )

            self.assertEqual(evidence["mariadb_connector_c_version"], "3.3.19")
            self.assertEqual(
                evidence["mariadb_connector_c_library_sha256"],
                builder.MARIADB_CONNECTOR_C_LIBRARY_SHA256,
            )
            self.assertEqual(evidence["mariadb_connector_c_soname"], "libmariadb.so.3")

    def test_mysqlclient_wheel_records_one_bundled_mariadb_library(self):
        with tempfile.TemporaryDirectory() as directory:
            wheel = Path(directory) / (
                "mysqlclient-2.2.8-cp314-cp314-manylinux_2_28_x86_64.whl"
            )
            bundled_name = "mysqlclient.libs/libmariadb-deadbeef.so.3"
            with zipfile.ZipFile(wheel, "w") as archive:
                archive.writestr(
                    "mysqlclient-2.2.8.dist-info/METADATA",
                    "Name: mysqlclient\nVersion: 2.2.8\n",
                )
                archive.writestr(
                    "mysqlclient-2.2.8.dist-info/WHEEL",
                    "Tag: cp314-cp314-manylinux_2_28_x86_64\n",
                )
                archive.writestr(
                    "MySQLdb/_mysql.cpython-314-x86_64-linux-gnu.so",
                    b"binary",
                )
                archive.writestr(bundled_name, b"bundled connector")

            with patch.object(
                builder,
                "_read_wheel_elf_soname",
                return_value="libmariadb-deadbeef.so.3",
            ), patch.object(
                builder,
                "_read_wheel_elf_dynamic",
                return_value=(None, ("libmariadb-deadbeef.so.3",)),
            ):
                evidence = builder._validate_mysqlclient_wheel(wheel)

            self.assertEqual(evidence["mysqlclient_bundled_library_name"], bundled_name)
            self.assertEqual(
                evidence["mysqlclient_bundled_library_sha256"],
                hashlib.sha256(b"bundled connector").hexdigest(),
            )
            self.assertEqual(
                evidence["mysqlclient_bundled_library_soname"],
                "libmariadb-deadbeef.so.3",
            )

    def test_cffi_validator_accepts_auditwheel_dual_platform_tag(self):
        with tempfile.TemporaryDirectory() as directory:
            wheel = Path(directory) / (
                "cffi-2.1.1-cp314-cp314-"
                "manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl"
            )
            with zipfile.ZipFile(wheel, "w") as archive:
                archive.writestr(
                    "cffi-2.1.1.dist-info/METADATA",
                    "Name: cffi\nVersion: 2.1.1\n",
                )
                archive.writestr(
                    "cffi-2.1.1.dist-info/WHEEL",
                    "Tag: cp314-cp314-manylinux_2_27_x86_64\n"
                    "Tag: cp314-cp314-manylinux_2_28_x86_64\n",
                )
                archive.writestr("_cffi_backend.cpython-314-x86_64-linux-gnu.so", b"binary")

            builder._validate_cffi_wheel(wheel)

    def test_mysqlclient_validator_accepts_package_scoped_extension(self):
        with tempfile.TemporaryDirectory() as directory:
            wheel = Path(directory) / (
                "mysqlclient-2.2.8-cp314-cp314-manylinux_2_28_x86_64.whl"
            )
            with zipfile.ZipFile(wheel, "w") as archive:
                archive.writestr(
                    "mysqlclient-2.2.8.dist-info/METADATA",
                    "Name: mysqlclient\nVersion: 2.2.8\n",
                )
                archive.writestr(
                    "mysqlclient-2.2.8.dist-info/WHEEL",
                    "Tag: cp314-cp314-manylinux_2_28_x86_64\n",
                )
                archive.writestr(
                    "MySQLdb/_mysql.cpython-314-x86_64-linux-gnu.so",
                    b"binary",
                )
                archive.writestr(
                    "mysqlclient.libs/libmariadb-deadbeef.so.3",
                    b"bundled connector",
                )

            with (
                patch.object(
                    builder,
                    "_read_wheel_elf_soname",
                    return_value="libmariadb-deadbeef.so.3",
                ),
                patch.object(
                    builder,
                    "_read_wheel_elf_dynamic",
                    return_value=(None, ("libmariadb-deadbeef.so.3",)),
                ),
            ):
                evidence = builder._validate_mysqlclient_wheel(wheel)
            self.assertEqual(
                evidence["mysqlclient_bundled_library_name"],
                "mysqlclient.libs/libmariadb-deadbeef.so.3",
            )

    def test_auditwheel_output_normalization_removes_archive_nondeterminism(self):
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.whl"
            second = Path(directory) / "second.whl"
            members = {
                "z-last.txt": b"last",
                "a-first.txt": b"first",
            }
            for wheel, timestamp in ((first, (2024, 1, 1, 0, 0, 0)), (second, (2025, 2, 2, 0, 0, 0))):
                with zipfile.ZipFile(wheel, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                    for name, payload in reversed(tuple(members.items())):
                        info = zipfile.ZipInfo(name, date_time=timestamp)
                        info.compress_type = zipfile.ZIP_DEFLATED
                        info.external_attr = 0o644 << 16
                        archive.writestr(info, payload)

            builder._normalize_wheel(first)
            builder._normalize_wheel(second)

            self.assertEqual(first.read_bytes(), second.read_bytes())
            with zipfile.ZipFile(first) as archive:
                self.assertEqual(archive.namelist(), sorted(members))
                self.assertTrue(
                    all(info.date_time == (1980, 1, 1, 0, 0, 0) for info in archive.infolist())
                )

    def test_auditwheel_output_normalizes_nonsemantic_permission_bits(self):
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.whl"
            second = Path(directory) / "second.whl"
            members = {
                "pkg/data.txt": b"data",
                "pkg/tool": b"tool",
                "pkg/": b"",
            }
            modes = (
                {"pkg/data.txt": 0o100644, "pkg/tool": 0o100755, "pkg/": 0o40755},
                {"pkg/data.txt": 0o100664, "pkg/tool": 0o100775, "pkg/": 0o40775},
            )
            for wheel, wheel_modes in zip((first, second), modes):
                with zipfile.ZipFile(wheel, "w") as archive:
                    for name, payload in members.items():
                        info = zipfile.ZipInfo(name)
                        info.create_system = 3
                        info.external_attr = wheel_modes[name] << 16
                        archive.writestr(info, payload)

            builder._normalize_wheel(first)
            builder._normalize_wheel(second)

            self.assertEqual(first.read_bytes(), second.read_bytes())
            with zipfile.ZipFile(first) as archive:
                normalized_modes = {
                    info.filename: info.external_attr >> 16 for info in archive.infolist()
                }
            self.assertEqual(normalized_modes["pkg/data.txt"], 0o100644)
            self.assertEqual(normalized_modes["pkg/tool"], 0o100755)
            self.assertEqual(normalized_modes["pkg/"], 0o40755)

    def test_auditwheel_sbom_and_record_are_byte_for_byte_normalized(self):
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.whl"
            second = Path(directory) / "second.whl"
            sbom_documents = (
                {
                    "bomFormat": "CycloneDX",
                    "components": [
                        {"bom-ref": "pkg:pypi/z", "name": "z"},
                        {"bom-ref": "pkg:pypi/a", "name": "a"},
                    ],
                    "dependencies": [
                        {"ref": "pkg:pypi/z", "dependsOn": ["pkg:pypi/b", "pkg:pypi/a"]},
                        {"ref": "pkg:pypi/a", "dependsOn": []},
                    ],
                },
                {
                    "dependencies": [
                        {"dependsOn": [], "ref": "pkg:pypi/a"},
                        {"dependsOn": ["pkg:pypi/a", "pkg:pypi/b"], "ref": "pkg:pypi/z"},
                    ],
                    "components": [
                        {"name": "a", "bom-ref": "pkg:pypi/a"},
                        {"name": "z", "bom-ref": "pkg:pypi/z"},
                    ],
                    "bomFormat": "CycloneDX",
                },
            )
            for wheel, document in zip((first, second), sbom_documents):
                sbom = json.dumps(document).encode("utf-8")
                payloads = {
                    "pkg/data.bin": b"binary",
                    "pkg.dist-info/sboms/auditwheel.cdx.json": sbom,
                }
                record = "".join(
                    f"{name},sha256={'0' * 43},{len(payload)}\n"
                    for name, payload in payloads.items()
                ).encode("utf-8")
                payloads["pkg.dist-info/RECORD"] = record
                with zipfile.ZipFile(wheel, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                    for name, payload in reversed(tuple(payloads.items())):
                        archive.writestr(name, payload)

            builder._normalize_wheel(first)
            builder._normalize_wheel(second)

            self.assertEqual(first.read_bytes(), second.read_bytes())
            with zipfile.ZipFile(first) as archive:
                sbom_name = "pkg.dist-info/sboms/auditwheel.cdx.json"
                sbom = json.loads(archive.read(sbom_name))
                self.assertEqual(
                    [component["name"] for component in sbom["components"]], ["a", "z"]
                )
                dependency = next(
                    item for item in sbom["dependencies"] if item["ref"] == "pkg:pypi/z"
                )
                self.assertEqual(dependency["dependsOn"], ["pkg:pypi/a", "pkg:pypi/b"])
                record = archive.read("pkg.dist-info/RECORD").decode("utf-8")
                expected = base64.urlsafe_b64encode(
                    hashlib.sha256(archive.read(sbom_name)).digest()
                ).rstrip(b"=").decode("ascii")
                self.assertIn(f"{sbom_name},sha256={expected},", record)

    def test_cffi_build_disables_nondeterministic_debug_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sdist = root / "cffi-2.1.1.tar.gz"
            sdist.write_bytes(b"source")
            (root / "build").mkdir()
            environments: list[dict[str, str]] = []

            def fake_run(command, *, cwd=None, env=None):
                environments.append(dict(env or {}))
                rendered = tuple(str(part) for part in command)
                output = Path(rendered[rendered.index("--wheel-dir") + 1])
                if "repair" in rendered:
                    name = (
                        "cffi-2.1.1-cp314-cp314-"
                        "manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl"
                    )
                else:
                    name = "cffi-2.1.1-cp314-cp314-linux_x86_64.whl"
                (output / name).write_bytes(b"wheel")

            with (
                patch.object(builder, "_run", side_effect=fake_run),
                patch.object(builder, "_normalize_wheel"),
            ):
                builder._build_cffi_once(
                    root / "python",
                    "auditwheel",
                    sdist,
                    root / "build",
                    label="one",
                )

            build_env = environments[0]
            self.assertIn("-g0", build_env["CFLAGS"])
            self.assertIn("-ffile-prefix-map=/tmp=.", build_env["CFLAGS"])
            self.assertEqual(build_env["LDFLAGS"], "-Wl,--build-id=sha1")


if __name__ == "__main__":
    unittest.main()
