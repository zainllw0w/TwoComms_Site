import importlib.util
import io
import json
import os
import signal
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from contextlib import redirect_stdout


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "instagram_bot_supervisor.py"
SPEC = importlib.util.spec_from_file_location("instagram_bot_supervisor", SCRIPT)
supervisor = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(supervisor)


class InstagramBotSupervisorTests(unittest.TestCase):
    def test_exit_attribution_distinguishes_exit_code_and_signal(self):
        self.assertEqual(supervisor._exit_attribution(7), (7, None))
        self.assertEqual(
            supervisor._exit_attribution(-signal.SIGTERM),
            (None, signal.SIGTERM),
        )

    def test_proc_start_ticks_are_read_from_field_22(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            proc_root = Path(temp_dir)
            process_dir = proc_root / "42"
            process_dir.mkdir()
            fields = ["S"] + [str(index) for index in range(4, 23)]
            (process_dir / "stat").write_text(
                "42 (worker with spaces) " + " ".join(fields),
                encoding="ascii",
            )

            self.assertEqual(
                supervisor._pid_start_ticks(42, proc_root=proc_root),
                22,
            )

    def test_event_journal_is_bounded_and_contains_no_exception_message(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            events = root / "events.jsonl"
            for index in range(supervisor.MAX_EVENT_RECORDS + 50):
                supervisor._append_event(
                    events,
                    {"event": "child_exited", "index": index, "exception_type": "RuntimeError"},
                )

            lines = events.read_text(encoding="utf-8").splitlines()
            self.assertLessEqual(len(lines), supervisor.MAX_EVENT_RECORDS)
            self.assertLessEqual(events.stat().st_size, supervisor.MAX_EVENT_BYTES)
            self.assertEqual(json.loads(lines[-1])["index"], supervisor.MAX_EVENT_RECORDS + 49)

    def test_maintenance_marker_blocks_spawn_only_until_its_real_expiry(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            marker = Path(temp_dir) / "maintenance.json"
            marker.write_text(
                json.dumps({"started_at": 100, "expires_at": 160}),
                encoding="utf-8",
            )
            self.assertTrue(supervisor._maintenance_active(marker, now=120))
            self.assertFalse(supervisor._maintenance_active(marker, now=161))

    def test_ensure_does_not_spawn_when_supervisor_lock_is_held(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "manage.py").write_text("", encoding="utf-8")
            python = root / "python"
            python.write_text("", encoding="utf-8")
            python.chmod(0o700)
            paths = supervisor._runtime_paths(root)
            with supervisor._exclusive_lock(paths["supervisor_lock"], blocking=True):
                with (
                    patch.object(supervisor, "_release_sha", return_value="unknown"),
                    patch.object(supervisor.subprocess, "Popen") as popen,
                ):
                    result = supervisor.ensure_supervisor(root=root, python=python)
            self.assertEqual(result, 0)
            popen.assert_not_called()
            state = json.loads(paths["state"].read_text(encoding="utf-8"))
            self.assertIn("last_ensure_seen_at", state)
            events = [
                json.loads(line)
                for line in paths["events"].read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(events[-1]["event"], "ensure_seen")

    def test_python_symlink_path_is_preserved_for_cloudlinux_binding(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            wrapper = root / "python_wrapper"
            wrapper.write_text("#!/bin/sh\n", encoding="utf-8")
            wrapper.chmod(0o700)
            selected = root / "venv-python"
            selected.symlink_to(wrapper)

            self.assertEqual(supervisor._validate_python(str(selected)), selected)

    def test_real_child_exit_persists_sha_pid_code_and_uptime(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manage = root / "manage.py"
            manage.write_text("raise SystemExit(7)\n", encoding="utf-8")
            runtime = supervisor.Supervisor(
                root=root,
                python=Path(sys.executable),
            )

            returncode, uptime = runtime._spawn_and_wait()

            self.assertEqual(returncode, 7)
            self.assertGreaterEqual(uptime, 0)
            state = json.loads(
                runtime.paths["state"].read_text(encoding="utf-8")
            )
            self.assertEqual(state["event"], "child_exited")
            self.assertEqual(state["child_exit_code"], 7)
            self.assertIsNone(state["child_exit_signal"])
            self.assertGreater(state["child_pid"], 0)
            self.assertIn("child_start_ticks", state)
            self.assertEqual(state["child_release_sha"], "unknown")
            self.assertEqual(state["supervisor_release_sha"], "unknown")
            self.assertIn("child_uptime_seconds", state)

    def test_concurrent_event_writers_do_not_lose_records(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            events = Path(temp_dir) / "events.jsonl"
            child_code = """
import importlib.util
import sys
from pathlib import Path
spec = importlib.util.spec_from_file_location('child_supervisor', sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
for index in range(25):
    module._append_event(
        Path(sys.argv[2]),
        {'event': 'concurrent', 'writer': sys.argv[3], 'index': index},
    )
"""
            children = [
                subprocess.Popen(
                    [sys.executable, "-c", child_code, str(SCRIPT), str(events), str(writer)]
                )
                for writer in range(4)
            ]
            for child in children:
                self.assertEqual(child.wait(timeout=20), 0)

            records = [
                json.loads(line)
                for line in events.read_text(encoding="utf-8").splitlines()
            ]
            observed = {
                (record["writer"], record["index"])
                for record in records
                if record.get("event") == "concurrent"
            }
            self.assertEqual(len(observed), 100)

    def test_release_change_gracefully_reloads_supervisor_before_spawning_b(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "manage.py").write_text("", encoding="utf-8")
            python = root / "python"
            python.write_text("", encoding="utf-8")
            python.chmod(0o700)
            paths = supervisor._runtime_paths(root)
            supervisor._atomic_json(
                paths["state"],
                {
                    "supervisor_pid": 123,
                    "supervisor_start_ticks": 456,
                    "supervisor_release_sha": "a" * 40,
                    "supervisor_sentinel": 10.0,
                },
            )

            with (
                patch.object(supervisor, "_lock_held", return_value=True),
                patch.object(supervisor, "_release_sha", return_value="b" * 40),
                patch.object(supervisor, "_restart_sentinel_mtime", return_value=20.0),
                patch.object(supervisor, "_pid_identity_matches", return_value=True),
                patch.object(supervisor, "_wait_for_lock_release", return_value=True),
                patch.object(supervisor.os, "kill") as kill,
                patch.object(supervisor.subprocess, "Popen") as popen,
                patch.dict(os.environ, {"SUPERVISOR_ENV_VERSION": "B"}),
            ):
                popen.return_value.pid = 789
                result = supervisor.ensure_supervisor(root=root, python=python)

            self.assertEqual(result, 0)
            kill.assert_called_once_with(123, signal.SIGHUP)
            popen.assert_called_once()
            self.assertEqual(
                popen.call_args.kwargs["env"]["SUPERVISOR_ENV_VERSION"],
                "B",
            )
            self.assertIn("--supervise", popen.call_args.args[0])
            with (
                patch.object(supervisor, "_release_sha", return_value="b" * 40),
                patch.object(supervisor, "_restart_sentinel_mtime", return_value=20.0),
            ):
                replacement = supervisor.Supervisor(root=root, python=python)
                replacement._record("supervisor_started")
            state = json.loads(paths["state"].read_text(encoding="utf-8"))
            self.assertEqual(state["supervisor_release_sha"], "b" * 40)
            self.assertEqual(state["supervisor_sentinel"], 20.0)

    def test_status_fails_when_ensure_seen_is_missing_or_stale(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "manage.py").write_text("", encoding="utf-8")
            python = root / "python"
            python.write_text("", encoding="utf-8")
            python.chmod(0o700)
            paths = supervisor._runtime_paths(root)
            base_state = {
                "event": "child_started",
                "supervisor_pid": 123,
                "supervisor_start_ticks": 456,
                "supervisor_release_sha": "b" * 40,
                "supervisor_sentinel": 0.0,
            }

            for label, last_seen, expected_age in (
                ("missing", None, None),
                ("stale", 100.0, 300.0),
            ):
                with self.subTest(label=label):
                    state = dict(base_state)
                    if last_seen is not None:
                        state["last_ensure_seen_at"] = last_seen
                    supervisor._atomic_json(paths["state"], state)
                    output = io.StringIO()
                    with (
                        patch.object(supervisor, "_lock_held", return_value=True),
                        patch.object(supervisor, "_pid_start_ticks", return_value=456),
                        patch.object(supervisor, "_release_sha", return_value="b" * 40),
                        patch.object(supervisor, "_restart_sentinel_mtime", return_value=0.0),
                        patch.object(supervisor.time, "time", return_value=400.0),
                        redirect_stdout(output),
                    ):
                        result = supervisor.main(
                            [
                                "--status",
                                "--root",
                                str(root),
                                "--python",
                                str(python),
                            ]
                        )
                    payload = json.loads(output.getvalue())
                    self.assertEqual(result, 1)
                    self.assertFalse(payload["ensure_fresh"])
                    self.assertEqual(payload["ensure_age_seconds"], expected_age)

    def test_deleted_state_is_not_treated_as_a_current_supervisor(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "manage.py").write_text("", encoding="utf-8")
            python = root / "python"
            python.write_text("", encoding="utf-8")
            python.chmod(0o700)
            with (
                patch.object(supervisor, "_lock_held", return_value=True),
                patch.object(supervisor, "_release_sha", return_value="b" * 40),
                patch.object(supervisor, "_restart_sentinel_mtime", return_value=1.0),
                patch.object(supervisor.subprocess, "Popen") as popen,
            ):
                result = supervisor.ensure_supervisor(root=root, python=python)

            self.assertEqual(result, 1)
            popen.assert_not_called()
            events = (
                supervisor._runtime_paths(root)["events"]
                .read_text(encoding="utf-8")
                .splitlines()
            )
            self.assertIn("supervisor_reload_requested_refused", events[-1])

    def test_cron_ensure_does_not_respawn_supervisor_during_rollback_maintenance(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "manage.py").write_text("", encoding="utf-8")
            python = root / "python"
            python.write_text("", encoding="utf-8")
            python.chmod(0o700)
            paths = supervisor._runtime_paths(root)
            paths["maintenance"].parent.mkdir(parents=True, exist_ok=True)
            paths["maintenance"].write_text(
                json.dumps(
                    {
                        "started_at": 100.0,
                        "expires_at": 160.0,
                        "lease_id": "rollback",
                    }
                ),
                encoding="utf-8",
            )
            with (
                patch.object(supervisor.time, "time", return_value=120.0),
                patch.object(supervisor, "_release_sha", return_value="unknown"),
                patch.object(supervisor.subprocess, "Popen") as popen,
            ):
                result = supervisor.ensure_supervisor(root=root, python=python)

            self.assertEqual(result, 0)
            popen.assert_not_called()
            self.assertIn(
                "supervisor_spawn_deferred_for_maintenance",
                paths["events"].read_text(encoding="utf-8"),
            )

    def test_explicit_stop_requires_verified_identity_and_releases_lock(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "manage.py").write_text("", encoding="utf-8")
            paths = supervisor._runtime_paths(root)
            supervisor._atomic_json(
                paths["state"],
                {"supervisor_pid": 123, "supervisor_start_ticks": 456},
            )
            with (
                patch.object(supervisor, "_lock_held", return_value=True),
                patch.object(supervisor, "_pid_identity_matches", return_value=True),
                patch.object(supervisor, "_wait_for_lock_release", return_value=True),
                patch.object(supervisor.os, "kill") as kill,
            ):
                result = supervisor.stop_supervisor(root=root)
            self.assertEqual(result, 0)
            kill.assert_called_once_with(123, signal.SIGTERM)


if __name__ == "__main__":
    unittest.main()
