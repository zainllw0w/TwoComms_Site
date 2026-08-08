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

    def test_workflow_builds_and_verifies_target_bound_artifact(self):
        self.assertIn("scripts/build_release_wheelhouse.py", self.source)
        self.assertIn("twocomms/requirements.lock", self.source)
        self.assertIn("wheelhouse/${{ github.sha }}", self.source)
        self.assertIn("manifest.sha256", self.source)
        self.assertIn("builder-evidence.json", self.source)
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
