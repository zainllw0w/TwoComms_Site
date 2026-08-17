"""Safety contracts for release-artifact pruning."""

from __future__ import annotations

import fcntl
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from scripts import prune_release_artifacts as pruning


class ReleaseArtifactPruningTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.release_root = self.root / "releases"
        self.venv_root = self.release_root / "venvs"
        self.retained_root = self.release_root / "retained"
        self.runtime_venv_root = self.root / "runtime" / "venvs"
        self.runtime_static_root = self.root / "runtime" / "static"
        for path in (
            self.venv_root,
            self.retained_root,
            self.runtime_venv_root,
            self.runtime_static_root,
        ):
            path.mkdir(parents=True)

        self.active_target = self.runtime_venv_root / "current"
        self.active_target.mkdir()
        self.active_venv = self.root / "selector" / "3.14"
        self.active_venv.parent.mkdir()
        self.active_venv.symlink_to(self.active_target, target_is_directory=True)
        self.active_static_target = self.runtime_static_root / "current"
        self.active_static_target.mkdir()
        self.active_static = self.root / "staticfiles"
        self.active_static.symlink_to(self.active_static_target, target_is_directory=True)
        self.deploy_lock = self.release_root / "deploy.lock"
        self.config = pruning.PruneConfig(
            active_venv=self.active_venv,
            active_static=self.active_static,
            deploy_lock=self.deploy_lock,
            allowed_roots=(
                self.venv_root,
                self.retained_root,
                self.runtime_venv_root,
            ),
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    @staticmethod
    def _artifact(root: Path, name: str) -> Path:
        artifact = root / name
        artifact.mkdir()
        (artifact / "marker.txt").write_text("owned\n", encoding="utf-8")
        return artifact

    def _replace_active_target(self, target: Path) -> None:
        self.active_venv.unlink()
        self.active_venv.symlink_to(target, target_is_directory=True)

    def _replace_active_static_target(self, target: Path) -> None:
        self.active_static.unlink()
        self.active_static.symlink_to(target, target_is_directory=True)

    def test_dry_run_is_default_and_keeps_validated_child(self):
        candidate = self._artifact(self.venv_root, "old-release")

        result = pruning.prune(self.config, [candidate])

        self.assertFalse(result.applied)
        self.assertEqual(result.active_target, self.active_target.resolve())
        self.assertEqual(result.candidates, (candidate.resolve(),))
        self.assertTrue(candidate.is_dir())

    def test_apply_removes_only_the_validated_direct_child(self):
        candidate = self._artifact(self.venv_root, "old-release")
        sibling = self._artifact(self.venv_root, "keep-release")

        result = pruning.prune(self.config, [candidate], apply=True)

        self.assertTrue(result.applied)
        self.assertFalse(candidate.exists())
        self.assertTrue(sibling.is_dir())
        self.assertTrue(self.active_target.is_dir())

    def test_entire_batch_is_validated_before_the_first_deletion(self):
        candidate = self._artifact(self.venv_root, "old-release")
        outside = self._artifact(self.root, "outside")

        with self.assertRaisesRegex(pruning.PruneError, "allowed release root"):
            pruning.prune(self.config, [candidate, outside], apply=True)

        self.assertTrue(candidate.is_dir())
        self.assertTrue(outside.is_dir())

    def test_external_active_target_is_never_deleted(self):
        with self.assertRaisesRegex(pruning.PruneError, "active venv"):
            pruning.prune(self.config, [self.active_target], apply=True)

        self.assertTrue(self.active_target.is_dir())

    def test_active_static_target_is_never_deleted(self):
        active_static_target = self._artifact(self.retained_root, "active-static-release")
        self._replace_active_static_target(active_static_target)

        with self.assertRaisesRegex(pruning.PruneError, "active static"):
            pruning.prune(self.config, [active_static_target], apply=True)

        self.assertTrue(active_static_target.is_dir())

    def test_parent_of_nested_active_target_is_never_deleted(self):
        retained_release = self._artifact(self.retained_root, "rollback-release")
        nested_active_target = retained_release / "venv"
        nested_active_target.mkdir()
        self._replace_active_target(nested_active_target)

        with self.assertRaisesRegex(pruning.PruneError, "active venv"):
            pruning.prune(self.config, [retained_release], apply=True)

        self.assertTrue(nested_active_target.is_dir())

    def test_descendant_of_active_target_is_never_deleted(self):
        candidate = self._artifact(self.active_target, "package-cache")
        config = pruning.PruneConfig(
            active_venv=self.active_venv,
            active_static=self.active_static,
            deploy_lock=self.deploy_lock,
            allowed_roots=(self.active_target,),
        )

        with self.assertRaisesRegex(pruning.PruneError, "active venv"):
            pruning.prune(config, [candidate], apply=True)

        self.assertTrue(candidate.is_dir())

    def test_symlink_candidate_is_rejected_without_touching_its_target(self):
        external = self._artifact(self.root, "external")
        candidate = self.venv_root / "linked-release"
        candidate.symlink_to(external, target_is_directory=True)

        with self.assertRaisesRegex(pruning.PruneError, "symlink"):
            pruning.prune(self.config, [candidate], apply=True)

        self.assertTrue(candidate.is_symlink())
        self.assertTrue((external / "marker.txt").is_file())

    def test_candidate_must_be_a_direct_child_of_an_allowed_root(self):
        release = self._artifact(self.venv_root, "old-release")
        nested = self._artifact(release, "nested")

        for candidate in (self.venv_root, nested):
            with self.subTest(candidate=candidate):
                with self.assertRaisesRegex(pruning.PruneError, "direct child"):
                    pruning.prune(self.config, [candidate], apply=True)

        self.assertTrue(release.is_dir())
        self.assertTrue(nested.is_dir())

    def test_active_venv_must_be_a_resolvable_symlink(self):
        self.active_venv.unlink()
        self.active_venv.mkdir()
        candidate = self._artifact(self.venv_root, "old-release")

        with self.assertRaisesRegex(pruning.PruneError, "active venv.*symlink"):
            pruning.prune(self.config, [candidate], apply=True)

        self.assertTrue(candidate.is_dir())

    def test_allowed_roots_must_be_real_directories(self):
        actual_root = self.root / "actual-root"
        actual_root.mkdir()
        linked_root = self.release_root / "linked-root"
        linked_root.symlink_to(actual_root, target_is_directory=True)
        candidate = self._artifact(actual_root, "old-release")
        config = pruning.PruneConfig(
            active_venv=self.active_venv,
            active_static=self.active_static,
            deploy_lock=self.deploy_lock,
            allowed_roots=(linked_root,),
        )

        with self.assertRaisesRegex(pruning.PruneError, "allowed release root.*symlink"):
            pruning.prune(config, [candidate], apply=True)

        self.assertTrue(candidate.is_dir())

    def test_allowed_release_roots_must_not_overlap(self):
        candidate = self._artifact(self.venv_root, "old-release")
        config = pruning.PruneConfig(
            active_venv=self.active_venv,
            active_static=self.active_static,
            deploy_lock=self.deploy_lock,
            allowed_roots=(self.release_root, self.venv_root),
        )

        with self.assertRaisesRegex(pruning.PruneError, "allowed release roots.*overlap"):
            pruning.prune(config, [candidate])

        self.assertTrue(candidate.is_dir())

    def test_contended_deploy_lock_rejects_even_dry_run(self):
        candidate = self._artifact(self.venv_root, "old-release")
        self.deploy_lock.touch()

        with self.deploy_lock.open("a+", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(pruning.PruneError, "deployment.*running"):
                pruning.prune(self.config, [candidate])

        self.assertTrue(candidate.is_dir())

    def test_candidate_must_not_contain_the_deploy_lock(self):
        candidate = self._artifact(self.venv_root, "old-release")
        config = pruning.PruneConfig(
            active_venv=self.active_venv,
            active_static=self.active_static,
            deploy_lock=candidate / "deploy.lock",
            allowed_roots=self.config.allowed_roots,
        )

        with self.assertRaisesRegex(pruning.PruneError, "deploy lock"):
            pruning.prune(config, [candidate], apply=True)

        self.assertTrue(candidate.is_dir())
        self.assertFalse((candidate / "deploy.lock").exists())

    def test_cli_requires_explicit_apply_for_mutation(self):
        candidate = self._artifact(self.venv_root, "old-release")
        common = [
            "--active-venv",
            str(self.active_venv),
            "--active-static",
            str(self.active_static),
            "--deploy-lock",
            str(self.deploy_lock),
            "--allowed-root",
            str(self.venv_root),
            str(candidate),
        ]

        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(pruning.main(common), 0)
        self.assertTrue(candidate.is_dir())
        self.assertIn('"mode": "dry-run"', output.getvalue())

        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(pruning.main(["--apply", *common]), 0)
        self.assertFalse(candidate.exists())
        self.assertIn('"mode": "apply"', output.getvalue())


if __name__ == "__main__":
    unittest.main()
