"""Contracts for the pinned immutable-release wheelhouse workflow."""

from __future__ import annotations

import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "immutable-release-wheelhouse.yml"
IMAGE_DIGEST = "sha256:fdb9a9c223b215604dc7b6f7e8fff4b39bfea5fbaa7777a2e5544a60dfa437f8"


class ImmutableReleaseWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = WORKFLOW.read_text(encoding="utf-8")

    def test_workflow_is_targeted_to_main_and_manual_dispatch(self):
        self.assertRegex(self.source, r"(?m)^\s*push:\s*$")
        self.assertRegex(self.source, r"(?m)^\s*branches:\s*\[main\]\s*$")
        self.assertRegex(self.source, r"(?m)^\s*workflow_dispatch:\s*$")

    def test_builder_uses_the_pinned_manylinux_image_and_runtime(self):
        self.assertIn(f"manylinux_2_28_x86_64@{IMAGE_DIGEST}", self.source)
        self.assertIn("/opt/python/cp314-cp314/bin/python", self.source)
        self.assertIn("--image-digest", self.source)
        self.assertIn("--target-sha \"${{ github.sha }}\"", self.source)

    def test_native_build_headers_are_installed_from_a_hash_pinned_rpm(self):
        self.assertIn("libffi-devel-3.1-24.el8.x86_64.rpm", self.source)
        self.assertIn(
            "8f5458bc961d226a0383575823f04d89989d801d11b1eeece2fe5498df49f186",
            self.source,
        )
        self.assertIn("sha256sum --check", self.source)
        self.assertIn("rpm -Uvh --replacepkgs", self.source)
        self.assertIn("libffi-devel-3.1-24.el8.x86_64", self.source)

    def test_mysqlclient_build_uses_hash_pinned_connector_c_3319_tarball(self):
        self.assertIn(
            "mariadb-connector-c-3.3.19-rhel8-amd64.tar.gz",
            self.source,
        )
        self.assertIn(
            "672bec76cfbb2fdb46ad4f681cd1e63c80721d7a07316e5849dc63e69d6ecdf7",
            self.source,
        )
        self.assertIn("/opt/mariadb-connector-c-3.3.19", self.source)
        self.assertIn("include/mariadb/mariadb_version.h", self.source)
        self.assertIn('MARIADB_PACKAGE_VERSION "3.3.19"', self.source)
        self.assertIn("lib/mariadb/libmariadb.so.3", self.source)
        self.assertIn(
            "5395b9398e16b3313ed3d799771ec33a4661beb91833648b457a0bfdb0fb36ee",
            self.source,
        )
        self.assertIn("readelf -d", self.source)
        self.assertIn("libmariadb.so.3", self.source)
        self.assertIn("sha256sum --check --strict", self.source)
        self.assertIn('grep -F "not found" <<<"$ldd_output"', self.source)
        self.assertIn("libssl", self.source)
        self.assertIn("libcrypto", self.source)
        self.assertIn("TLS/OpenSSL", self.source)
        self.assertNotIn("mariadb-connector-c-3.1.11", self.source)
        self.assertNotIn("rpm -q mariadb-connector-c", self.source)
        self.assertNotIn('rpm -Uvh --replacepkgs --nodeps "$runtime_path"', self.source)

    def test_workflow_runs_typed_query_gate_against_mariadb_11412(self):
        self.assertRegex(self.source, r"(?m)^\s*services:\s*$")
        self.assertIn(
            "image: mariadb:11.4.12@sha256:67873d30a17f6a9c331f06363b2fa15f38abca415529966d67c84f87f82439fe",
            self.source,
        )
        self.assertIn("scripts/verify_mysqlclient_wheel_runtime.py", self.source)
        self.assertIn("--expected-server-version 11.4.12", self.source)
        self.assertIn("--iterations 100", self.source)
        self.assertIn("env -u LD_PRELOAD", self.source)
        self.assertIn("builder-evidence.json", self.source)
        gate_source = (REPO_ROOT / "scripts" / "verify_mysqlclient_wheel_runtime.py").read_text(encoding="utf-8")
        self.assertIn("@@default_storage_engine", gate_source)
        self.assertIn("EXPECTED_FIELD_TYPES = [253, 253, 253, 246, 253]", gate_source)
        self.assertIn('grep -F "not found" <<<"$ldd_output"', self.source)
        self.assertNotIn('rpm -Uvh --replacepkgs --nodeps "$runtime_path"', self.source)

    def test_workflow_builds_and_verifies_target_bound_artifact(self):
        self.assertIn("scripts/build_release_wheelhouse.py", self.source)
        self.assertIn("twocomms/requirements.lock", self.source)
        self.assertIn("wheelhouse/${{ github.sha }}", self.source)
        self.assertIn("manifest.sha256", self.source)
        self.assertIn("builder-evidence.json", self.source)
        self.assertIn('evidence["libffi_devel"]', self.source)
        self.assertIn('evidence["mariadb_connector_c_version"]', self.source)
        self.assertIn('evidence["mariadb_connector_c_source_sha256"]', self.source)
        self.assertIn('evidence["mysqlclient_bundled_library_sha256"]', self.source)
        self.assertIn("actions/upload-artifact", self.source)
        self.assertIn("if-no-files-found: error", self.source)

    def test_workflow_has_no_production_install_or_unpinned_target(self):
        self.assertNotIn("pip install --index-url", self.source)
        self.assertNotIn("pip install --extra-index-url", self.source)
        self.assertNotRegex(self.source, r"target-sha\s+\$\{\{\s*github\.ref\s*\}\}")
        self.assertNotRegex(self.source, r"target-sha\s+\$\{\{\s*inputs\.")

    def test_actions_are_pinned_to_commit_shas(self):
        action_refs = re.findall(r"uses:\s+[^\s@]+@([^\s]+)", self.source)
        self.assertTrue(action_refs)
        self.assertTrue(all(re.fullmatch(r"[0-9a-f]{40}", ref) for ref in action_refs))


if __name__ == "__main__":
    unittest.main()
