"""Contract tests for the non-mutating staged-release preparation phase."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from scripts import deploy_release


class FakeRunner:
    def __init__(self, *, outputs=None, failures=None):
        self.calls: list[tuple[str, ...]] = []
        self.outputs = outputs or {}
        self.failures = failures or set()

    def __call__(self, argv, *, cwd=None, env=None):
        command = tuple(str(part) for part in argv)
        self.calls.append(command)
        rendered = " ".join(command)
        if command in self.failures or any(
            marker in rendered for marker in self.failures if isinstance(marker, str)
        ):
            raise deploy_release.CommandFailure(command, 42, "injected failure")
        output = self.outputs.get(command, self.outputs.get(command[0], ""))
        if callable(output):
            output = output(command, cwd, env)
        if command[:3] == ("git", "worktree", "add") and len(command) >= 4:
            worktree = Path(command[-2])
            (worktree / "twocomms").mkdir(parents=True, exist_ok=True)
            (worktree / "scripts").mkdir(parents=True, exist_ok=True)
            (worktree / "twocomms" / "requirements.lock").write_text(
                "example==1.0.0 --hash=sha256:" + "0" * 64 + "\n", encoding="utf-8"
            )
            (worktree / "twocomms" / "manage.py").write_text("", encoding="utf-8")
            (worktree / "scripts" / "verify_locked_requirements.py").write_text("", encoding="utf-8")
        if "-m" in command and "venv" in command:
            Path(command[-1]).mkdir(parents=True, exist_ok=True)
        if "collectstatic" in command and env and env.get("STATIC_ROOT"):
            static_root = Path(env["STATIC_ROOT"])
            static_root.mkdir(parents=True, exist_ok=True)
            (static_root / "staticfiles.json").write_text('{"paths": ["app.css"]}', encoding="utf-8")
        if "compress" in command and env and env.get("STATIC_ROOT"):
            static_root = Path(env["STATIC_ROOT"])
            (static_root / "compressed-page.html").write_text("<html>compressed</html>", encoding="utf-8")
        return deploy_release.CommandResult(0, str(output), "")


class StagedReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.live = root / "live"
        self.live.mkdir()
        (self.live / ".git").mkdir()
        self.release_root = root / "releases"
        self.active_venv = root / "active-venv"
        self.active_static = root / "active-static"
        self.lock_path = root / "deploy.lock"
        self.evidence_root = root / "evidence"
        self.system_python = Path("/opt/alt/python314/bin/python3.14")
        self.target_sha = "a" * 40
        self.live_sha = "b" * 40
        self.config = deploy_release.ReleaseConfig(
            live_checkout=self.live,
            release_root=self.release_root,
            active_venv=self.active_venv,
            active_static=self.active_static,
            system_python=self.system_python,
            deploy_lock=self.lock_path,
            evidence_root=self.evidence_root,
            wheelhouse_root=self.release_root / "wheelhouse",
            reviewed_lock_sha256=None,
        )
        self.runner = FakeRunner(
            outputs={
                ("git", "status", "--porcelain", "--untracked-files=no"): "",
                ("git", "symbolic-ref", "--short", "HEAD"): "main\n",
                ("git", "rev-parse", "HEAD"): f"{self.live_sha}\n",
                ("git", "rev-parse", "origin/main"): f"{self.target_sha}\n",
                ("git", "merge-base", "--is-ancestor", self.live_sha, self.target_sha): "",
            }
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def _manifest(self, *, digest=None):
        wheelhouse = self.config.wheelhouse_root / self.target_sha
        wheelhouse.mkdir(parents=True, exist_ok=True)
        wheel = wheelhouse / "example-1.0.0-py3-none-any.whl"
        wheel.write_bytes(b"wheel")
        digest = digest or hashlib.sha256(wheel.read_bytes()).hexdigest()
        (wheelhouse / "manifest.sha256").write_text(
            json.dumps({"target_sha": self.target_sha, "files": {wheel.name: digest}}, sort_keys=True),
            encoding="utf-8",
        )

    def test_dirty_live_checkout_is_rejected_before_fetch_or_stage(self):
        self.runner.outputs[("git", "status", "--porcelain", "--untracked-files=no")] = " M app.py\n"

        with self.assertRaises(deploy_release.ReleaseError):
            deploy_release.prepare(self.config, self.target_sha, run=self.runner)

        self.assertEqual(self.runner.calls[0][:3], ("git", "status", "--porcelain"))
        self.assertFalse(any(call[:2] == ("git", "fetch") for call in self.runner.calls))
        self.assertFalse(self.release_root.exists())

    def test_target_must_be_origin_main_and_fast_forward_of_live_sha(self):
        self._manifest()
        self.runner.outputs[("git", "rev-parse", "origin/main")] = f"{'c' * 40}\n"

        with self.assertRaises(deploy_release.ReleaseError):
            deploy_release.prepare(self.config, self.target_sha, run=self.runner)

        self.assertFalse(any(call[:2] == ("git", "worktree") for call in self.runner.calls))

    def test_fresh_versioned_venv_is_created_at_final_immutable_path(self):
        self._manifest()
        prepared = deploy_release.prepare(self.config, self.target_sha, run=self.runner)

        expected = self.release_root / "venvs" / self.target_sha
        self.assertEqual(prepared.venv, expected)
        self.assertIn((str(self.system_python), "-m", "venv", str(expected)), self.runner.calls)
        self.assertFalse(any("mv" in call for call in self.runner.calls))

    def test_install_failure_leaves_live_checkout_venv_static_and_processes_untouched(self):
        self._manifest()
        self.active_venv.mkdir()
        self.active_static.mkdir()
        before = (self.active_venv.stat().st_ino, self.active_static.stat().st_ino)
        self.runner.failures.add("pip")

        with self.assertRaises(deploy_release.ReleaseError):
            deploy_release.prepare(self.config, self.target_sha, run=self.runner)

        self.assertEqual(before, (self.active_venv.stat().st_ino, self.active_static.stat().st_ino))
        self.assertFalse(any("maintenance-on" in call for call in self.runner.calls))
        self.assertFalse(any(call[:2] == ("cloudlinux-selector", "stop") for call in self.runner.calls))

        self.assertIn(
            ("git", "worktree", "remove", "--force", str(self.release_root / "worktrees" / self.target_sha)),
            self.runner.calls,
        )

    def test_missing_or_mismatched_immutable_wheelhouse_fails_before_maintenance(self):
        with self.assertRaises(deploy_release.ReleaseError):
            deploy_release.prepare(self.config, self.target_sha, run=self.runner)

        self.assertFalse(any("maintenance-on" in call for call in self.runner.calls))
        self.assertFalse(any(call[:2] == ("git", "worktree") for call in self.runner.calls))

        self._manifest(digest="0" * 64)
        with self.assertRaises(deploy_release.ReleaseError):
            deploy_release.prepare(self.config, self.target_sha, run=self.runner)
        self.assertFalse(any("maintenance-on" in call for call in self.runner.calls))

    def test_strict_lock_or_import_failure_leaves_live_state_untouched(self):
        self._manifest()
        self.runner.failures.add("verify_locked_requirements.py")

        with self.assertRaises(deploy_release.ReleaseError):
            deploy_release.prepare(self.config, self.target_sha, run=self.runner)

        self.assertFalse(any("maintenance-on" in call for call in self.runner.calls))
        self.assertFalse(self.active_venv.exists())
        self.assertFalse(self.active_static.exists())

    def test_reviewed_lock_digest_mismatch_is_rejected_before_install(self):
        self._manifest()
        self.config = replace(self.config, reviewed_lock_sha256="f" * 64)

        with self.assertRaises(deploy_release.ReleaseError):
            deploy_release.prepare(self.config, self.target_sha, run=self.runner)

        self.assertFalse(any("pip" in call for call in self.runner.calls))

    def test_unapplied_migration_is_rejected_before_maintenance(self):
        self._manifest()
        self.runner.failures.add("migrate")

        with self.assertRaises(deploy_release.ReleaseError):
            deploy_release.prepare(self.config, self.target_sha, run=self.runner)

        self.assertFalse(any("maintenance-on" in call for call in self.runner.calls))

    def test_collectstatic_or_compress_failure_leaves_live_state_untouched(self):
        self._manifest()
        self.runner.failures.add("collectstatic")

        with self.assertRaises(deploy_release.ReleaseError):
            deploy_release.prepare(self.config, self.target_sha, run=self.runner)

        self.assertFalse(any("maintenance-on" in call for call in self.runner.calls))
        self.assertFalse(any(call[:2] == ("cloudlinux-selector", "stop") for call in self.runner.calls))


if __name__ == "__main__":
    unittest.main()
