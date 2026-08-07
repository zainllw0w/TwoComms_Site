"""Contract tests for the non-mutating staged-release preparation phase."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from scripts import deploy_release


class FakeRunner:
    def __init__(self, *, outputs=None, failures=None):
        self.calls: list[tuple[str, ...]] = []
        self.timeouts: dict[tuple[str, ...], float | None] = {}
        self.outputs = outputs or {}
        self.failures = failures or set()

    def __call__(self, argv, *, cwd=None, env=None, timeout=None):
        command = tuple(str(part) for part in argv)
        self.calls.append(command)
        self.timeouts[command] = timeout
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
        (self.live / "manage.py").write_text("", encoding="utf-8")
        (self.live / "requirements.lock").write_bytes(b"locked\n")
        (self.live / "scripts").mkdir()
        (self.live / "scripts" / "verify_locked_requirements.py").write_text("", encoding="utf-8")
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

    def test_every_prepare_subprocess_has_a_bounded_timeout(self):
        self._manifest()

        deploy_release.prepare(self.config, self.target_sha, run=self.runner)

        unbounded = [
            " ".join(command)
            for command, timeout in self.runner.timeouts.items()
            if timeout is None
        ]
        self.assertEqual(unbounded, [])

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
        self.assertEqual(
            self.runner.timeouts[
                (
                    "git",
                    "worktree",
                    "remove",
                    "--force",
                    str(self.release_root / "worktrees" / self.target_sha),
                )
            ],
            self.config.command_timeout_seconds,
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



class SwitchRunner(FakeRunner):
    def __init__(
        self,
        config,
        *,
        failures=None,
        maintenance_output="maintenance active lease_id=lease-owned expires_at=9999999999",
        current_sha="b" * 40,
        branch="main",
        tracked_status="",
    ):
        super().__init__(failures=failures)
        self.config = config
        self.maintenance_output = maintenance_output
        self.current_sha = current_sha
        self.branch = branch
        self.tracked_status = tracked_status

    @staticmethod
    def _requested_lease_id(command):
        try:
            return command[command.index("--maintenance-lease-id") + 1]
        except ValueError:
            return "lease-owned"

    def __call__(self, argv, *, cwd=None, env=None, timeout=None):
        command = tuple(str(part) for part in argv)
        if command == ("git", "rev-parse", "HEAD"):
            self.calls.append(command)
            return deploy_release.CommandResult(0, self.current_sha + "\n", "")
        if command == ("git", "symbolic-ref", "--short", "HEAD"):
            self.calls.append(command)
            return deploy_release.CommandResult(0, self.branch + "\n", "")
        if command == ("git", "status", "--porcelain", "--untracked-files=no"):
            self.calls.append(command)
            return deploy_release.CommandResult(0, self.tracked_status, "")
        result = super().__call__(argv, cwd=cwd, env=env, timeout=timeout)
        rendered = " ".join(str(part) for part in argv)
        if command[:3] == ("git", "merge", "--ff-only"):
            self.current_sha = command[-1]
        if command[:3] == ("git", "update-ref", "refs/heads/main"):
            self.current_sha = command[3]
        if "run_instagram_bot" in rendered and "--maintenance-on" in rendered:
            lease_id = self._requested_lease_id(command)
            lease_path = deploy_release.maintenance_path(self.config)
            lease_path.parent.mkdir(parents=True, exist_ok=True)
            lease_path.write_text(
                json.dumps({"lease_id": lease_id, "started_at": 1, "expires_at": 9999999999}),
                encoding="utf-8",
            )
            return deploy_release.CommandResult(
                0,
                self.maintenance_output.replace("lease-owned", lease_id),
                "",
            )
        if "management.twocomms.shop" in rendered:
            return deploy_release.CommandResult(
                0,
                json.dumps(
                    {
                        "status": "ok",
                        "queues": {
                            "available": True,
                            "dangerous_backlog": 0,
                            "analysis_failed": 18,
                        },
                    }
                ),
            )
        if "run_instagram_bot" in rendered and "--maintenance-off" in rendered:
            deploy_release.maintenance_path(self.config).unlink(missing_ok=True)
        return result


class ReceiptMismatchRunner(SwitchRunner):
    def __call__(self, argv, *, cwd=None, env=None, timeout=None):
        command = tuple(str(part) for part in argv)
        rendered = " ".join(command)
        if "run_instagram_bot" in rendered and "--maintenance-on" in rendered:
            self.calls.append(command)
            lease_path = deploy_release.maintenance_path(self.config)
            lease_path.parent.mkdir(parents=True, exist_ok=True)
            lease_path.write_text(
                json.dumps({"lease_id": "other", "started_at": 1, "expires_at": 9999999999}),
                encoding="utf-8",
            )
            lease_id = self._requested_lease_id(command)
            return deploy_release.CommandResult(
                0,
                f"maintenance active lease_id={lease_id} expires_at=9999999999",
                "",
            )
        if "run_instagram_bot" in rendered and "--maintenance-off" in rendered:
            self.calls.append(command)
            if any(marker in rendered for marker in self.failures if isinstance(marker, str)):
                raise deploy_release.CommandFailure(command, 23, "injected cleanup failure")
            return deploy_release.CommandResult(0, "maintenance owner mismatch", "")
        return super().__call__(argv, cwd=cwd, env=env, timeout=timeout)


class ForeignRaceActivationRunner(SwitchRunner):
    def __call__(self, argv, *, cwd=None, env=None, timeout=None):
        command = tuple(str(part) for part in argv)
        rendered = " ".join(command)
        if "run_instagram_bot" in rendered and "--maintenance-on" in rendered:
            self.calls.append(command)
            lease_path = deploy_release.maintenance_path(self.config)
            lease_path.parent.mkdir(parents=True, exist_ok=True)
            lease_path.write_text(
                json.dumps(
                    {
                        "lease_id": "foreign-race",
                        "started_at": 1,
                        "expires_at": 9999999999,
                    }
                ),
                encoding="utf-8",
            )
            raise deploy_release.CommandFailure(command, 17, "maintenance already active")
        return super().__call__(argv, cwd=cwd, env=env, timeout=timeout)


class OwnedActivationFailureRunner(SwitchRunner):
    def __call__(self, argv, *, cwd=None, env=None, timeout=None):
        command = tuple(str(part) for part in argv)
        rendered = " ".join(command)
        if "run_instagram_bot" in rendered and "--maintenance-on" in rendered:
            self.calls.append(command)
            lease_id = self._requested_lease_id(command)
            lease_path = deploy_release.maintenance_path(self.config)
            lease_path.parent.mkdir(parents=True, exist_ok=True)
            lease_path.write_text(
                json.dumps({"lease_id": lease_id, "started_at": 1, "expires_at": 9999999999}),
                encoding="utf-8",
            )
            raise deploy_release.CommandFailure(command, 17, "daemon did not stop")
        return super().__call__(argv, cwd=cwd, env=env, timeout=timeout)


class MergeMutatesThenFailsRunner(SwitchRunner):
    def __call__(self, argv, *, cwd=None, env=None, timeout=None):
        command = tuple(str(part) for part in argv)
        if command[:3] == ("git", "merge", "--ff-only"):
            self.calls.append(command)
            self.current_sha = command[-1]
            raise deploy_release.CommandFailure(command, 42, "injected post-update failure")
        return super().__call__(argv, cwd=cwd, env=env, timeout=timeout)


class RollbackTrackedDriftRunner(SwitchRunner):
    """Introduce a tracked edit between switch preflight and rollback."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.status_calls = 0

    def __call__(self, argv, *, cwd=None, env=None, timeout=None):
        command = tuple(str(part) for part in argv)
        if command == ("git", "status", "--porcelain", "--untracked-files=no"):
            self.status_calls += 1
            self.tracked_status = " M externally-edited.py\n" if self.status_calls >= 2 else ""
        return super().__call__(argv, cwd=cwd, env=env, timeout=timeout)


class RollbackPassengerStartFailureRunner(SwitchRunner):
    """Allow activation start, then fail the rollback start command."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_calls = 0

    def __call__(self, argv, *, cwd=None, env=None, timeout=None):
        command = tuple(str(part) for part in argv)
        if command[:2] == ("cloudlinux-selector", "start"):
            self.start_calls += 1
            if self.start_calls == 2:
                self.calls.append(command)
                self.timeouts[command] = timeout
                raise deploy_release.CommandFailure(command, 42, "rollback start failed")
        return super().__call__(argv, cwd=cwd, env=env, timeout=timeout)


class RollbackDriftAfterRefUpdateRunner(SwitchRunner):
    """Expose a tracked edit after the branch CAS but before tree restore."""

    def __call__(self, argv, *, cwd=None, env=None, timeout=None):
        command = tuple(str(part) for part in argv)
        if command[:3] == ("git", "diff", "--quiet"):
            self.calls.append(command)
            self.timeouts[command] = timeout
            raise deploy_release.CommandFailure(command, 1, "tracked drift")
        return super().__call__(argv, cwd=cwd, env=env, timeout=timeout)


class AmbiguousPassengerStartRunner(SwitchRunner):
    """The first start launches Passenger but returns an ambiguous failure."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_calls = 0
        self.stop_calls = 0
        self.app_running = True

    def __call__(self, argv, *, cwd=None, env=None, timeout=None):
        command = tuple(str(part) for part in argv)
        if command[:2] == ("cloudlinux-selector", "stop"):
            self.stop_calls += 1
            self.app_running = False
        if command[:2] == ("cloudlinux-selector", "start"):
            self.start_calls += 1
            self.app_running = True
            if self.start_calls == 1:
                self.calls.append(command)
                self.timeouts[command] = timeout
                raise deploy_release.CommandFailure(command, 42, "ambiguous Passenger start")
        return super().__call__(argv, cwd=cwd, env=env, timeout=timeout)


class TransientHealthRunner(SwitchRunner):
    """Fail the first site probe, then expose the healthy endpoint."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.site_health_calls = 0

    def __call__(self, argv, *, cwd=None, env=None, timeout=None):
        command = tuple(str(part) for part in argv)
        if "https://twocomms.shop/healthz/" in command:
            self.site_health_calls += 1
            if self.site_health_calls == 1:
                self.calls.append(command)
                self.timeouts[command] = timeout
                raise deploy_release.CommandFailure(command, 503, "cold start")
        return super().__call__(argv, cwd=cwd, env=env, timeout=timeout)


class SwitchTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.live = root / "live"
        self.live.mkdir()
        (self.live / "manage.py").write_text("", encoding="utf-8")
        (self.live / "requirements.lock").write_bytes(b"locked\n")
        (self.live / "scripts").mkdir()
        (self.live / "scripts" / "verify_locked_requirements.py").write_text("", encoding="utf-8")
        self.release_root = root / "releases"
        self.active_venv = root / "active-venv"
        self.active_static = root / "active-static"
        self.active_venv.mkdir()
        self.active_static.mkdir()
        self.config = deploy_release.ReleaseConfig(
            live_checkout=self.live,
            release_root=self.release_root,
            active_venv=self.active_venv,
            active_static=self.active_static,
            system_python=Path("/opt/alt/python314/bin/python3.14"),
            deploy_lock=root / "deploy.lock",
            evidence_root=root / "evidence",
            wheelhouse_root=root / "wheelhouse",
            reviewed_lock_sha256=None,
            cloudlinux_user="test-user",
            cloudlinux_app_root="TWC/TwoComms_Site/twocomms",
        )
        self.previous_sha = "b" * 40
        self.target_sha = "a" * 40
        self.worktree = self.release_root / "worktrees" / self.target_sha
        self.venv = self.release_root / "venvs" / self.target_sha
        self.static_root = self.release_root / "static" / self.target_sha
        self.worktree.mkdir(parents=True)
        (self.venv / "bin").mkdir(parents=True)
        (self.venv / "bin" / "python").write_text("", encoding="utf-8")
        (self.static_root / "CACHE").mkdir(parents=True)
        (self.static_root / "CACHE" / "manifest.json").write_text("{}", encoding="utf-8")
        (self.static_root / "compressed-page.html").write_text("ok", encoding="utf-8")
        self.prepared = deploy_release.PreparedRelease(
            target_sha=self.target_sha,
            previous_sha=self.previous_sha,
            worktree=self.worktree,
            venv=self.venv,
            static_root=self.static_root,
            wheelhouse=root / "wheelhouse" / self.target_sha,
            lock_sha256=hashlib.sha256(b"locked\n").hexdigest(),
        )
        self.runner = SwitchRunner(self.config)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_default_bot_health_uses_the_management_host(self):
        self.assertEqual(
            deploy_release.ReleaseConfig().bot_health_url,
            "https://management.twocomms.shop/bot/health/",
        )

    def test_default_maintenance_marker_is_relative_to_manage_py(self):
        nested_root = Path(self.temp_dir.name) / "nested-root"
        (nested_root / "twocomms").mkdir(parents=True)
        (nested_root / "twocomms" / "manage.py").write_text("", encoding="utf-8")
        config = replace(self.config, live_checkout=nested_root)

        self.assertEqual(
            deploy_release.maintenance_path(config),
            nested_root / "twocomms" / "tmp" / "ig_bot_maintenance.json",
        )

    def test_switch_enters_bot_maintenance_before_stopping_passenger(self):
        deploy_release.switch(self.config, self.prepared, run=self.runner)
        maintenance_index = next(i for i, call in enumerate(self.runner.calls) if "--maintenance-on" in call)
        stop_index = next(i for i, call in enumerate(self.runner.calls) if call[:2] == ("cloudlinux-selector", "stop"))
        self.assertLess(maintenance_index, stop_index)

    def test_maintenance_activation_uses_bounded_subprocess_timeout(self):
        deploy_release.switch(self.config, self.prepared, run=self.runner)
        maintenance_call = next(call for call in self.runner.calls if "--maintenance-on" in call)

        self.assertEqual(
            self.runner.timeouts[maintenance_call],
            self.config.maintenance_timeout_seconds,
        )

    def test_subprocess_timeout_is_a_release_error(self):
        with patch.object(
            deploy_release.subprocess,
            "run",
            side_effect=subprocess.TimeoutExpired(("blocked",), timeout=3),
        ):
            with self.assertRaisesRegex(deploy_release.ReleaseError, "timed out"):
                deploy_release.subprocess_runner(("blocked",), timeout=3)

    def test_stale_prepared_release_is_rejected_before_maintenance(self):
        runner = SwitchRunner(self.config, current_sha="c" * 40)

        with self.assertRaises(deploy_release.ReleaseError):
            deploy_release.switch(self.config, self.prepared, run=runner)

        self.assertFalse(any("--maintenance-on" in call for call in runner.calls))

    def test_switch_rejects_branch_drift_before_maintenance(self):
        runner = SwitchRunner(self.config, branch="release")

        with self.assertRaisesRegex(deploy_release.ReleaseError, "branch"):
            deploy_release.switch(self.config, self.prepared, run=runner)

        self.assertFalse(any("--maintenance-on" in call for call in runner.calls))

    def test_switch_rejects_tracked_worktree_drift_before_maintenance(self):
        runner = SwitchRunner(self.config, tracked_status=" M app.py\n")

        with self.assertRaises(deploy_release.ReleaseError):
            deploy_release.switch(self.config, self.prepared, run=runner)

        self.assertFalse(any("--maintenance-on" in call for call in runner.calls))

    def test_failed_maintenance_activation_releases_only_owned_lease(self):
        runner = OwnedActivationFailureRunner(self.config)
        with self.assertRaises(deploy_release.ReleaseError):
            deploy_release.switch(self.config, self.prepared, run=runner)
        self.assertIn("--maintenance-off", " ".join(" ".join(call) for call in runner.calls))
        self.assertFalse(deploy_release.maintenance_path(self.config).exists())

    def test_activation_race_never_releases_foreign_lease(self):
        runner = ForeignRaceActivationRunner(self.config)

        with self.assertRaises(deploy_release.ReleaseError):
            deploy_release.switch(self.config, self.prepared, run=runner)

        rendered = " ".join(" ".join(call) for call in runner.calls)
        self.assertNotIn("--maintenance-off", rendered)
        self.assertIn(
            "foreign-race",
            deploy_release.maintenance_path(self.config).read_text(encoding="utf-8"),
        )

    def test_failed_maintenance_cleanup_is_not_hidden(self):
        runner = OwnedActivationFailureRunner(self.config, failures={"--maintenance-off"})

        with self.assertRaisesRegex(deploy_release.ReleaseError, "cleanup failed"):
            deploy_release.switch(self.config, self.prepared, run=runner)

    def test_switch_order_is_stop_fast_forward_swap_venv_swap_static_start(self):
        deploy_release.switch(self.config, self.prepared, run=self.runner)
        rendered = [" ".join(call) for call in self.runner.calls]
        positions = [
            next(i for i, call in enumerate(rendered) if "--maintenance-on" in call),
            next(i for i, call in enumerate(rendered) if "cloudlinux-selector stop" in call),
            next(i for i, call in enumerate(rendered) if "merge" in call),
            next(i for i, call in enumerate(rendered) if "cloudlinux-selector start" in call),
        ]
        self.assertEqual(positions, sorted(positions))
        self.assertTrue(self.active_venv.is_symlink())
        self.assertTrue(self.active_static.is_symlink())

    def test_venv_and_static_switches_retain_previous_release_for_rollback(self):
        deploy_release.switch(self.config, self.prepared, run=self.runner)
        retained = self.release_root / "retained" / self.previous_sha
        self.assertTrue((retained / "venv").is_dir())
        self.assertTrue((retained / "static").is_dir())

    def test_start_or_health_failure_restores_previous_sha_venv_and_static(self):
        runner = SwitchRunner(self.config, failures={"cloudlinux-selector start"})
        with self.assertRaises(deploy_release.ReleaseError):
            deploy_release.switch(self.config, self.prepared, run=runner)
        self.assertFalse(self.active_venv.is_symlink())
        self.assertFalse(self.active_static.is_symlink())

    def test_ambiguous_passenger_start_is_stopped_before_runtime_rollback(self):
        runner = AmbiguousPassengerStartRunner(self.config)

        with self.assertRaises(deploy_release.ReleaseError):
            deploy_release.switch(self.config, self.prepared, run=runner)

        rendered = [" ".join(call) for call in runner.calls]
        stop_indexes = [
            index for index, command in enumerate(rendered)
            if command.startswith("cloudlinux-selector stop")
        ]
        restore_index = next(
            index for index, command in enumerate(rendered)
            if command.startswith("git update-ref")
        )
        self.assertEqual(runner.stop_calls, 2)
        self.assertLess(stop_indexes[-1], restore_index)

    def test_failed_symlink_rollback_retains_owned_maintenance_lease(self):
        runner = SwitchRunner(self.config, failures={"healthz/"})

        with patch.object(
            deploy_release,
            "_restore_switched_path",
            side_effect=deploy_release.ReleaseError("symlink rollback failed"),
        ):
            with self.assertRaisesRegex(deploy_release.ReleaseError, "rollback errors"):
                deploy_release.switch(self.config, self.prepared, run=runner)

        rendered = " ".join(" ".join(call) for call in runner.calls)
        self.assertNotIn("--maintenance-off", rendered)
        self.assertEqual(
            deploy_release._read_lease_id(deploy_release.maintenance_path(self.config)),
            SwitchRunner._requested_lease_id(
                next(call for call in runner.calls if "--maintenance-on" in call)
            ),
        )

    def test_failed_passenger_rollback_start_retains_owned_maintenance_lease(self):
        runner = RollbackPassengerStartFailureRunner(self.config, failures={"healthz/"})

        with self.assertRaisesRegex(deploy_release.ReleaseError, "rollback errors"):
            deploy_release.switch(self.config, self.prepared, run=runner)

        rendered = " ".join(" ".join(call) for call in runner.calls)
        self.assertEqual(runner.start_calls, 2)
        self.assertNotIn("--maintenance-off", rendered)
        self.assertIsNotNone(deploy_release._read_lease_id(deploy_release.maintenance_path(self.config)))

    def test_rollback_rejects_new_tracked_edit_before_git_restore(self):
        runner = RollbackTrackedDriftRunner(self.config, failures={"healthz/"})

        with self.assertRaises(deploy_release.ReleaseError):
            deploy_release.switch(self.config, self.prepared, run=runner)

        rendered = " ".join(" ".join(call) for call in runner.calls)
        self.assertNotIn("git update-ref", rendered)
        self.assertNotIn("git restore", rendered)
        self.assertNotIn("--maintenance-off", rendered)
        self.assertEqual(
            deploy_release._read_lease_id(deploy_release.maintenance_path(self.config)),
            SwitchRunner._requested_lease_id(
                next(call for call in runner.calls if "--maintenance-on" in call)
            ),
        )

    def test_rollback_rechecks_target_snapshot_after_ref_update(self):
        runner = RollbackDriftAfterRefUpdateRunner(self.config, failures={"healthz/"})

        with self.assertRaises(deploy_release.ReleaseError):
            deploy_release.switch(self.config, self.prepared, run=runner)

        rendered = " ".join(" ".join(call) for call in runner.calls)
        self.assertIn("git update-ref", rendered)
        self.assertIn(f"git diff --quiet {self.target_sha}", rendered)
        self.assertNotIn("git restore", rendered)
        self.assertNotIn("--maintenance-off", rendered)

    def test_activation_failure_evidence_marks_rollback_not_needed(self):
        runner = OwnedActivationFailureRunner(self.config)

        with self.assertRaises(deploy_release.ReleaseError):
            deploy_release.switch(self.config, self.prepared, run=runner)

        evidence = sorted(self.config.evidence_root.glob("release-*.json"))[-1]
        payload = json.loads(evidence.read_text(encoding="utf-8"))
        self.assertEqual(payload["failure_phase"], "maintenance_activation")
        self.assertFalse(payload["rollback_needed"])
        self.assertEqual(payload["rollback_status"], "not_needed")
        self.assertFalse(payload["rolled_back"])

    def test_activation_cleanup_failure_evidence_marks_retained_owned_lease(self):
        runner = OwnedActivationFailureRunner(self.config, failures={"--maintenance-off"})

        with self.assertRaisesRegex(deploy_release.ReleaseError, "cleanup failed"):
            deploy_release.switch(self.config, self.prepared, run=runner)

        evidence = sorted(self.config.evidence_root.glob("release-*.json"))[-1]
        payload = json.loads(evidence.read_text(encoding="utf-8"))
        self.assertEqual(payload["failure_phase"], "maintenance_activation")
        self.assertFalse(payload["rollback_needed"])
        self.assertTrue(payload["maintenance_lease_retained"])
        self.assertEqual(
            deploy_release._read_lease_id(deploy_release.maintenance_path(self.config)),
            next(call[call.index("--maintenance-lease-id") + 1] for call in runner.calls if "--maintenance-on" in call),
        )

    def test_http_health_failure_restores_exact_previous_sha_and_runtime(self):
        runner = SwitchRunner(self.config, failures={"healthz/"})

        with self.assertRaises(deploy_release.ReleaseError):
            deploy_release.switch(self.config, self.prepared, run=runner)

        self.assertEqual(runner.current_sha, self.previous_sha)
        self.assertTrue(self.active_venv.is_dir())
        self.assertTrue(self.active_static.is_dir())
        self.assertFalse(self.active_venv.is_symlink())
        self.assertFalse(self.active_static.is_symlink())
        rendered = " ".join(" ".join(call) for call in runner.calls)
        self.assertIn("git update-ref refs/heads/main", rendered)

    def test_transient_site_health_retries_before_rolling_back(self):
        config = replace(
            self.config,
            health_retry_attempts=2,
            health_retry_delay_seconds=0,
            health_deadline_seconds=5,
        )
        runner = TransientHealthRunner(config)

        result = deploy_release.switch(config, self.prepared, run=runner)

        self.assertEqual(result.target_sha, self.target_sha)
        self.assertEqual(runner.site_health_calls, 2)

    def test_failed_rollback_evidence_records_incomplete_runtime_recovery(self):
        runner = SwitchRunner(self.config, failures={"healthz/", "--ensure"})

        with self.assertRaisesRegex(deploy_release.ReleaseError, "rollback errors"):
            deploy_release.switch(self.config, self.prepared, run=runner)

        evidence = sorted(self.config.evidence_root.glob("release-*.json"))[-1]
        payload = json.loads(evidence.read_text(encoding="utf-8"))
        self.assertFalse(payload["rolled_back"])
        self.assertEqual(payload["rollback_status"], "incomplete")
        self.assertIn("CommandFailure", payload["rollback_errors"])
        self.assertEqual(payload["original_error"], "CommandFailure")

    def test_success_releases_owned_maintenance_and_ensures_current_daemon(self):
        deploy_release.switch(self.config, self.prepared, run=self.runner)
        on_call = next(call for call in self.runner.calls if "--maintenance-on" in call)
        off_call = next(call for call in self.runner.calls if "--maintenance-off" in call)
        self.assertIn("--maintenance-lease-id", on_call)
        self.assertEqual(off_call[-1], SwitchRunner._requested_lease_id(on_call))
        rendered = " ".join(" ".join(call) for call in self.runner.calls)
        self.assertIn("run_instagram_bot --ensure", rendered)

    def test_failure_does_not_release_an_unowned_maintenance_lease(self):
        lease_path = deploy_release.maintenance_path(self.config)
        lease_path.parent.mkdir(parents=True, exist_ok=True)
        lease_path.write_text(json.dumps({"lease_id": "other", "started_at": 1, "expires_at": 9999999999}), encoding="utf-8")
        runner = SwitchRunner(self.config, failures={"--maintenance-on"})
        with self.assertRaises(deploy_release.ReleaseError):
            deploy_release.switch(self.config, self.prepared, run=runner)
        self.assertNotIn("--maintenance-off", " ".join(" ".join(call) for call in runner.calls))
        self.assertIn("other", lease_path.read_text(encoding="utf-8"))

    def test_receipt_marker_mismatch_cleans_exact_receipt_and_preserves_foreign_lease(self):
        runner = ReceiptMismatchRunner(self.config)

        with self.assertRaises(deploy_release.ReleaseError):
            deploy_release.switch(self.config, self.prepared, run=runner)

        rendered = " ".join(" ".join(call) for call in runner.calls)
        on_call = next(call for call in runner.calls if "--maintenance-on" in call)
        self.assertIn(
            f"--maintenance-off {SwitchRunner._requested_lease_id(on_call)}",
            rendered,
        )
        self.assertIn("other", deploy_release.maintenance_path(self.config).read_text(encoding="utf-8"))
        self.assertNotIn("cloudlinux-selector stop", rendered)

    def test_receipt_marker_mismatch_reports_cleanup_failure(self):
        runner = ReceiptMismatchRunner(self.config, failures={"--maintenance-off"})

        with self.assertRaisesRegex(deploy_release.ReleaseError, "cleanup failed"):
            deploy_release.switch(self.config, self.prepared, run=runner)

    def test_stop_failure_releases_owned_maintenance_and_restores_old_app(self):
        runner = SwitchRunner(self.config, failures={"cloudlinux-selector stop"})
        with self.assertRaises(deploy_release.ReleaseError):
            deploy_release.switch(self.config, self.prepared, run=runner)
        self.assertFalse(deploy_release.maintenance_path(self.config).exists())
        self.assertIn(
            "cloudlinux-selector start",
            " ".join(" ".join(call) for call in runner.calls),
        )

    def test_fast_forward_failure_releases_owned_maintenance_and_restores_old_app(self):
        runner = SwitchRunner(self.config, failures={"git merge"})
        with self.assertRaises(deploy_release.ReleaseError):
            deploy_release.switch(self.config, self.prepared, run=runner)
        self.assertFalse(deploy_release.maintenance_path(self.config).exists())

    def test_nonzero_fast_forward_after_ref_update_restores_previous_sha_before_start(self):
        runner = MergeMutatesThenFailsRunner(self.config)

        with self.assertRaises(deploy_release.ReleaseError):
            deploy_release.switch(self.config, self.prepared, run=runner)

        self.assertEqual(runner.current_sha, self.previous_sha)
        rendered = [" ".join(call) for call in runner.calls]
        restore_index = next(i for i, call in enumerate(rendered) if "git update-ref refs/heads/main" in call)
        start_index = max(i for i, call in enumerate(rendered) if "cloudlinux-selector start" in call)
        self.assertLess(restore_index, start_index)

    def test_first_switch_converts_real_venv_directory_to_retained_target_and_symlink(self):
        deploy_release.switch(self.config, self.prepared, run=self.runner)
        self.assertTrue(self.active_venv.is_symlink())
        self.assertTrue((self.release_root / "retained" / self.previous_sha / "venv").is_dir())

    def test_first_switch_converts_real_static_directory_to_retained_target_and_symlink(self):
        deploy_release.switch(self.config, self.prepared, run=self.runner)
        self.assertTrue(self.active_static.is_symlink())
        self.assertTrue((self.release_root / "retained" / self.previous_sha / "static").is_dir())

    def test_existing_symlink_is_replaced_before_it_is_retained(self):
        old_target = self.release_root / "old-target"
        old_target.mkdir(parents=True)
        new_target = self.release_root / "new-target"
        new_target.mkdir(parents=True)
        active = self.release_root / "active"
        retained = self.release_root / "retained-old"
        active.symlink_to(old_target, target_is_directory=True)
        calls = []
        original_replace = os.replace

        def record_replace(source, destination):
            calls.append((Path(source), Path(destination)))
            return original_replace(source, destination)

        with patch.object(deploy_release.os, "replace", side_effect=record_replace):
            state = deploy_release._atomic_switch_path(active, new_target, retained)

        self.assertEqual(calls[0][1], active)
        self.assertTrue(active.is_symlink())
        self.assertTrue(state.retained.is_symlink())
        self.assertEqual(state.retained.resolve(), old_target.resolve())

    def test_existing_relative_symlink_keeps_target_when_retained_moves(self):
        old_target = self.release_root / "live-target"
        old_target.mkdir(parents=True)
        active_parent = self.release_root / "active"
        active_parent.mkdir(parents=True)
        active = active_parent / "venv"
        active.symlink_to(Path("../live-target"), target_is_directory=True)
        new_target = self.release_root / "new-target"
        new_target.mkdir(parents=True)
        retained = self.release_root / "retained" / "previous" / "venv"

        state = deploy_release._atomic_switch_path(active, new_target, retained)

        self.assertEqual(state.retained.resolve(), old_target.resolve())

    def test_failed_first_switch_restores_original_real_directories(self):
        runner = SwitchRunner(self.config, failures={"cloudlinux-selector start"})
        with self.assertRaises(deploy_release.ReleaseError):
            deploy_release.switch(self.config, self.prepared, run=runner)
        self.assertTrue(self.active_venv.is_dir())
        self.assertTrue(self.active_static.is_dir())
        self.assertFalse(self.active_venv.is_symlink())
        self.assertFalse(self.active_static.is_symlink())

    def test_evidence_is_mode_0600_and_contains_no_environment_or_credentials(self):
        result = deploy_release.switch(self.config, self.prepared, run=self.runner)
        evidence = Path(result.evidence_path)
        self.assertEqual(evidence.stat().st_mode & 0o777, 0o600)
        content = evidence.read_text(encoding="utf-8")
        self.assertNotIn("SECRET_KEY", content)
        self.assertNotIn("TELEGRAM", content)

    def test_evidence_records_sanitized_bot_queue_summary(self):
        result = deploy_release.switch(self.config, self.prepared, run=self.runner)
        payload = json.loads(Path(result.evidence_path).read_text(encoding="utf-8"))

        self.assertEqual(payload["health"]["queues"]["dangerous_backlog"], 0)
        self.assertEqual(payload["health"]["queues"]["analysis_failed"], 18)

    def test_http_health_script_uses_explicit_failure_under_optimized_python(self):
        command = deploy_release._http_health_command(self.config, "http://127.0.0.1/")
        script = command[2]

        self.assertNotIn("assert ", script)
        self.assertIn("raise SystemExit", script)
        compile(script, "<health-check>", "exec", optimize=2)

    def test_bot_health_script_rejects_dangerous_queue_backlog(self):
        command = deploy_release._http_health_command(
            self.config,
            "http://127.0.0.1/",
            require_queues=True,
        )

        self.assertIn("dangerous_backlog", command[2])
        self.assertIn("analysis_failed", command[2])

    def test_concurrent_deploy_is_rejected_by_flock(self):
        handle = deploy_release.acquire_deploy_lock(self.config.deploy_lock)
        try:
            with self.assertRaises(deploy_release.ReleaseError):
                deploy_release.switch(self.config, self.prepared, run=self.runner)
        finally:
            handle.close()

    def test_cli_activates_the_prepared_release(self):
        switched = deploy_release.SwitchResult(
            target_sha=self.target_sha,
            previous_sha=self.previous_sha,
            evidence_path=self.config.evidence_root / "release.json",
        )
        with (
            patch.object(deploy_release, "_default_config", return_value=self.config),
            patch.object(deploy_release, "prepare", return_value=self.prepared) as prepare_release,
            patch.object(deploy_release, "switch", return_value=switched) as switch_release,
        ):
            result = deploy_release.main(["--target-sha", self.target_sha])

        self.assertEqual(result, 0)
        prepare_release.assert_called_once_with(self.config, self.target_sha)
        switch_release.assert_called_once_with(self.config, self.prepared)


class RestoreCheckoutIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp_dir.name) / "repo"
        self.repo.mkdir()
        self._git("init", "-b", "main")
        self._git("config", "user.email", "release-test@example.invalid")
        self._git("config", "user.name", "Release Test")
        (self.repo / "tracked.txt").write_text("previous\n", encoding="utf-8")
        self._git("add", "tracked.txt")
        self._git("commit", "-m", "previous")
        self.previous_sha = self._git("rev-parse", "HEAD").stdout.strip()
        (self.repo / "tracked.txt").write_text("target\n", encoding="utf-8")
        self._git("commit", "-am", "target")
        self.target_sha = self._git("rev-parse", "HEAD").stdout.strip()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _git(self, *args):
        return subprocess.run(
            ("git", *args),
            cwd=self.repo,
            check=True,
            capture_output=True,
            text=True,
        )

    def test_restore_checkout_returns_real_git_tree_to_previous_commit(self):
        prepared = deploy_release.PreparedRelease(
            target_sha=self.target_sha,
            previous_sha=self.previous_sha,
            worktree=self.repo,
            venv=self.repo,
            static_root=self.repo,
            wheelhouse=self.repo,
            lock_sha256="a" * 64,
        )
        config = deploy_release.ReleaseConfig(live_checkout=self.repo)

        deploy_release._restore_checkout(
            config,
            prepared,
            run=deploy_release.subprocess_runner,
        )

        self.assertEqual(self._git("rev-parse", "HEAD").stdout.strip(), self.previous_sha)
        self.assertEqual((self.repo / "tracked.txt").read_text(encoding="utf-8"), "previous\n")
        self.assertEqual(self._git("status", "--porcelain").stdout, "")

    def test_restore_checkout_preserves_index_only_drift_after_ref_update(self):
        prepared = deploy_release.PreparedRelease(
            target_sha=self.target_sha,
            previous_sha=self.previous_sha,
            worktree=self.repo,
            venv=self.repo,
            static_root=self.repo,
            wheelhouse=self.repo,
            lock_sha256="a" * 64,
        )
        config = deploy_release.ReleaseConfig(live_checkout=self.repo)

        def runner(argv, *, cwd=None, env=None, timeout=None):
            command = tuple(str(part) for part in argv)
            result = deploy_release.subprocess_runner(
                command,
                cwd=cwd,
                env=env,
                timeout=timeout,
            )
            if command[:3] == ("git", "update-ref", "refs/heads/main"):
                (self.repo / "tracked.txt").write_text("staged drift\n", encoding="utf-8")
                self._git("add", "tracked.txt")
                (self.repo / "tracked.txt").write_text("target\n", encoding="utf-8")
            return result

        with self.assertRaisesRegex(deploy_release.ReleaseError, "tracked"):
            deploy_release._restore_checkout(config, prepared, run=runner)

        self.assertEqual(self._git("show", ":tracked.txt").stdout, "staged drift\n")
        self.assertEqual((self.repo / "tracked.txt").read_text(encoding="utf-8"), "target\n")


if __name__ == "__main__":
    unittest.main()
