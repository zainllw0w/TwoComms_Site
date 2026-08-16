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

    def test_mysqlclient_build_libraries_are_installed_from_hash_pinned_rpms(self):
        self.assertIn("mariadb-connector-c-config-3.1.11-2.el8_3.noarch.rpm", self.source)
        self.assertIn("mariadb-connector-c-3.1.11-2.el8_3.x86_64.rpm", self.source)
        self.assertIn("mariadb-connector-c-devel-3.1.11-2.el8_3.x86_64.rpm", self.source)
        self.assertIn(
            "eca6eb7026bfbb5ff51825587af1376bd6bd957dea4ec89cc7e9971a32983b0f",
            self.source,
        )
        self.assertIn(
            "85c37e356ca0e8114acfbe5fd5043ce1a95c35354851cc91b4066104e11dd658",
            self.source,
        )
        self.assertIn(
            "e7f9b90bb970c95179842fce9edf84ec943bc19b4bdd7029645e05d1e6a2e295",
            self.source,
        )
        self.assertIn("test -f /usr/include/mysql/mysql.h", self.source)
        self.assertIn("test -f /usr/lib64/libmariadb.so.3", self.source)
        self.assertIn("test -f /etc/my.cnf", self.source)
        self.assertIn("rpm -q mariadb-connector-c-config", self.source)
        self.assertIn('rpm -Uvh --replacepkgs --nodeps "$devel_path"', self.source)
        self.assertIn('rpm -Uvh --replacepkgs "$config_path" "$runtime_path"', self.source)
        self.assertIn('ldd_output="$(ldd /usr/lib64/libmariadb.so.3)"', self.source)
        self.assertIn('grep -F "not found" <<<"$ldd_output"', self.source)
        self.assertNotIn('rpm -Uvh --replacepkgs --nodeps "$runtime_path"', self.source)
        self.assertIn("mariadb_connector_c_devel", self.source)

    def test_workflow_builds_and_verifies_target_bound_artifact(self):
        self.assertIn("scripts/build_release_wheelhouse.py", self.source)
        self.assertIn("twocomms/requirements.lock", self.source)
        self.assertIn("wheelhouse/${{ github.sha }}", self.source)
        self.assertIn("manifest.sha256", self.source)
        self.assertIn("builder-evidence.json", self.source)
        self.assertIn('evidence["libffi_devel"]', self.source)
        self.assertIn("actions/upload-artifact", self.source)
        self.assertIn("if-no-files-found: error", self.source)

    def test_workflow_has_no_production_install_or_unpinned_target(self):
        self.assertNotIn("pip install", self.source)
        self.assertNotIn("pip install --", self.source)
        self.assertNotRegex(self.source, r"target-sha\s+\$\{\{\s*github\.ref\s*\}\}")
        self.assertNotRegex(self.source, r"target-sha\s+\$\{\{\s*inputs\.")

    def test_actions_are_pinned_to_commit_shas(self):
        action_refs = re.findall(r"uses:\s+[^\s@]+@([^\s]+)", self.source)
        self.assertTrue(action_refs)
        self.assertTrue(all(re.fullmatch(r"[0-9a-f]{40}", ref) for ref in action_refs))


if __name__ == "__main__":
    unittest.main()
