import importlib.util
import json
import os
import signal
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


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
                with patch.object(supervisor.subprocess, "Popen") as popen:
                    result = supervisor.ensure_supervisor(root=root, python=python)
            self.assertEqual(result, 0)
            popen.assert_not_called()

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
            self.assertIn("child_uptime_seconds", state)


if __name__ == "__main__":
    unittest.main()
