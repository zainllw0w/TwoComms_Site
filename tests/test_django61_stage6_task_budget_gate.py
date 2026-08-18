import importlib.util
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_django61_stage6_task_budget_gate.py"


def load_gate_module():
    spec = importlib.util.spec_from_file_location("task_budget_gate", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Stage6TaskBudgetGateTests(unittest.TestCase):
    def setUp(self):
        self.gate = load_gate_module()
        self.policy = {
            "schema_version": 1,
            "scope": "non-dtf",
            "worker": {"processes": 3, "connections": 1, "fds": 32},
            "reserve": {"connections": 1, "fds": 64, "processes": 1},
            "canary": {
                "task": "task_runtime.tasks.no_send_canary",
                "payload_keys": ["marker"],
                "external_io": False,
            },
        }
        self.snapshot = {
            "schema_version": 1,
            "scope": "non-dtf",
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "provenance": {"source": "cloudlinux-bound-python", "kind": "read-only"},
            "runtime": {"cloudlinux_bound": True, "python": "3.14.6", "django": "6.1"},
            "database": {"engine": "django.db.backends.mysql", "conn_max_age": 0},
            "mysql": {"max_user_connections": 20, "account_current_connections": 12},
            "fd": {"soft_limit": 1024, "account_open_fds": 200},
            "process": {"soft_limit": 128, "account_current_processes": 15},
        }

    def test_valid_snapshot_and_no_send_canary_pass(self):
        result = self.gate.verify(self.policy, self.snapshot, repo_root=ROOT)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["budget"]["db_headroom_after"], 7)
        self.assertEqual(result["budget"]["fd_headroom_after"], 792)
        self.assertEqual(result["budget"]["process_headroom_after"], 110)

    def test_launcher_process_budget_cannot_be_understated(self):
        self.policy["worker"]["processes"] = 1
        with self.assertRaisesRegex(self.gate.GateError, "three process"):
            self.gate.verify(self.policy, self.snapshot, repo_root=ROOT)

    def test_runtime_database_and_provenance_are_required(self):
        for key in ("captured_at", "provenance", "runtime", "database"):
            snapshot = json.loads(json.dumps(self.snapshot))
            snapshot.pop(key)
            with self.subTest(key=key), self.assertRaisesRegex(self.gate.GateError, key):
                self.gate.verify(self.policy, snapshot, repo_root=ROOT)

    def test_sqlite_or_persistent_connections_fail_closed(self):
        self.snapshot["database"]["engine"] = "django.db.backends.sqlite3"
        with self.assertRaisesRegex(self.gate.GateError, "MySQL"):
            self.gate.verify(self.policy, self.snapshot, repo_root=ROOT)
        self.snapshot["database"]["engine"] = "django.db.backends.mysql"
        self.snapshot["database"]["conn_max_age"] = 60
        with self.assertRaisesRegex(self.gate.GateError, "CONN_MAX_AGE"):
            self.gate.verify(self.policy, self.snapshot, repo_root=ROOT)
        self.snapshot["database"]["conn_max_age"] = False
        with self.assertRaisesRegex(self.gate.GateError, "CONN_MAX_AGE"):
            self.gate.verify(self.policy, self.snapshot, repo_root=ROOT)

    def test_stale_snapshot_fails_closed(self):
        self.snapshot["captured_at"] = "2020-01-01T00:00:00+00:00"
        with self.assertRaisesRegex(self.gate.GateError, "freshness"):
            self.gate.verify(self.policy, self.snapshot, repo_root=ROOT)

    def test_missing_per_account_measurement_fails_closed(self):
        self.snapshot["mysql"].pop("account_current_connections")
        with self.assertRaisesRegex(self.gate.GateError, "account_current_connections"):
            self.gate.verify(self.policy, self.snapshot, repo_root=ROOT)

    def test_insufficient_connection_headroom_fails_closed(self):
        self.snapshot["mysql"]["account_current_connections"] = 19
        with self.assertRaisesRegex(self.gate.GateError, "MariaDB"):
            self.gate.verify(self.policy, self.snapshot, repo_root=ROOT)

    def test_dtf_scope_is_forbidden(self):
        self.snapshot["scope"] = "DTF"
        with self.assertRaisesRegex(self.gate.GateError, "DTF"):
            self.gate.verify(self.policy, self.snapshot, repo_root=ROOT)

    def test_canary_source_cannot_import_network_or_enqueue(self):
        original_read_text = Path.read_text

        def fake_read_text(path, *args, **kwargs):
            if str(path).endswith("task_runtime/tasks.py"):
                return "import requests\n"
            return original_read_text(path, *args, **kwargs)

        try:
            Path.read_text = fake_read_text
            with self.assertRaisesRegex(self.gate.GateError, "network"):
                self.gate.verify(self.policy, self.snapshot, repo_root=ROOT)
        finally:
            Path.read_text = original_read_text

    def test_canary_body_must_be_strict_marker_only_return(self):
        original_read_text = Path.read_text

        def fake_read_text(path, *args, **kwargs):
            if str(path).endswith("task_runtime/tasks.py"):
                return (
                    "def no_send_canary(*, marker):\n"
                    "    value = marker\n"
                    "    return {'external_io': False, 'marker': value}\n"
                )
            return original_read_text(path, *args, **kwargs)

        try:
            Path.read_text = fake_read_text
            with self.assertRaisesRegex(self.gate.GateError, "pure"):
                self.gate.verify(self.policy, self.snapshot, repo_root=ROOT)
        finally:
            Path.read_text = original_read_text

    def test_cli_emits_json_only_after_passing_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            policy_path = Path(directory) / "policy.json"
            snapshot_path = Path(directory) / "snapshot.json"
            policy_path.write_text(json.dumps(self.policy), encoding="utf-8")
            snapshot_path.write_text(json.dumps(self.snapshot), encoding="utf-8")
            output = self.gate.main(
                ["--policy", str(policy_path), "--snapshot", str(snapshot_path), "--repo-root", str(ROOT)]
            )
        self.assertEqual(output, 0)


if __name__ == "__main__":
    unittest.main()
