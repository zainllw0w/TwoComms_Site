import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "audit_cloudlinux_python_capacity.py"
EXPECTED_SHA = "a" * 40
SELECTOR_APP_ROOT = "TWC/TwoComms_Site/twocomms"


class CloudLinuxCapacityAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.app_root = self.root / "home" / "app" / SELECTOR_APP_ROOT
        self.app_root.mkdir(parents=True)
        (self.app_root / "manage.py").write_text("", encoding="utf-8")
        self.tmp = self.app_root / "tmp"
        self.tmp.mkdir()
        self.proc = self.root / "proc"
        self.proc.mkdir()
        self.selector_bin = self.root / "cloudlinux-selector"
        self.git_bin = self.root / "git"
        self.supervisor_lock = self.tmp / "ig_bot_supervisor.lock"
        self.daemon_lock = self.tmp / "ig_bot_daemon.lock"
        self.supervisor_lock.write_text("", encoding="utf-8")
        self.daemon_lock.write_text("", encoding="utf-8")
        self.selector_payload = self._selector_payload()
        self._write_selector(self.selector_payload)
        self._write_git(EXPECTED_SHA)
        self._write_runtime_state()
        self._write_process_tree()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _selector_payload(self, *, children="3", extra="0", status="started"):
        return {
            "result": "success",
            "available_versions": {
                "3.14.7": {
                    "users": {
                        "fixture-user": {
                            "applications": {
                                SELECTOR_APP_ROOT: {
                                    "app_status": status,
                                    "domain": "example.test",
                                    "app_uri": "",
                                    "env_vars": {
                                        "LSAPI_CHILDREN": children,
                                        "LSAPI_EXTRA_CHILDREN": extra,
                                        "DATABASE_PASSWORD": "selector-super-secret",
                                        "API_KEY": "selector-api-secret",
                                    },
                                }
                            }
                        }
                    }
                }
            },
        }

    def _write_executable(self, path: Path, content: str):
        path.write_text(content, encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR)

    def _write_selector(self, payload, *, returncode=0, stderr=""):
        encoded = json.dumps(payload)
        self._write_executable(
            self.selector_bin,
            "#!/usr/bin/env python3\n"
            "import sys\n"
            f"sys.stderr.write({stderr!r})\n"
            f"sys.stdout.write({encoded!r})\n"
            f"raise SystemExit({returncode})\n",
        )

    def _write_git(self, sha):
        self._write_executable(
            self.git_bin,
            "#!/usr/bin/env python3\n"
            f"print({sha!r})\n",
        )

    def _write_runtime_state(self, *, supervisor_pid=200, daemon_pid=201, sha=EXPECTED_SHA):
        (self.tmp / "ig_bot_supervisor_state.json").write_text(
            json.dumps(
                {
                    "event": "child_started",
                    "supervisor_pid": supervisor_pid,
                    "child_pid": daemon_pid,
                    "supervisor_release_sha": sha,
                    "child_release_sha": sha,
                }
            ),
            encoding="utf-8",
        )
        (self.tmp / "ig_bot.pid").write_text(str(daemon_pid), encoding="ascii")

    def _write_process(
        self,
        pid,
        *,
        uid=1001,
        ppid=1,
        comm="python3.14_bin",
        rss=100,
        pss=80,
        private_clean=10,
        private_dirty=60,
        environ=None,
        locks=(),
        cmdline_secret="",
    ):
        proc_dir = self.proc / str(pid)
        proc_dir.mkdir()
        (proc_dir / "status").write_text(
            f"Name:\t{comm}\nUid:\t{uid}\t{uid}\t{uid}\t{uid}\nPPid:\t{ppid}\n",
            encoding="utf-8",
        )
        (proc_dir / "comm").write_text(comm + "\n", encoding="utf-8")
        (proc_dir / "smaps_rollup").write_text(
            "00400000-00500000 ---p 00000000 00:00 0 [rollup]\n"
            f"Rss: {rss} kB\n"
            f"Pss: {pss} kB\n"
            f"Private_Clean: {private_clean} kB\n"
            f"Private_Dirty: {private_dirty} kB\n"
            "Private_Hugetlb: 0 kB\n",
            encoding="utf-8",
        )
        env = environ or {}
        (proc_dir / "environ").write_bytes(
            b"\0".join(f"{key}={value}".encode("ascii") for key, value in env.items())
            + b"\0"
        )
        (proc_dir / "cmdline").write_bytes(
            (cmdline_secret or "safe-command").encode("utf-8") + b"\0"
        )
        fd_dir = proc_dir / "fd"
        fd_dir.mkdir()
        for index, lock_path in enumerate(locks, start=3):
            (fd_dir / str(index)).symlink_to(lock_path)

    def _write_process_tree(self):
        lsapi_env = {
            "LSAPI_CHILDREN": "3",
            "LSAPI_EXTRA_CHILDREN": "0",
            "DATABASE_PASSWORD": "runtime-super-secret",
        }
        self._write_process(100, ppid=1, comm="lswsgi", rss=120, pss=90, environ=lsapi_env)
        for pid in (101, 102, 103):
            self._write_process(pid, ppid=100, comm="lswsgi", environ=lsapi_env)
        self._write_process(200, locks=(self.supervisor_lock,), rss=20, pss=15)
        self._write_process(201, locks=(self.daemon_lock,), rss=150, pss=130)
        self._write_process(202, comm="bash", rss=5, pss=4, cmdline_secret="--token cmdline-secret")
        # Foreign UID must be rejected before comm, memory, environ, fd or
        # cmdline inspection; only status is intentionally present.
        foreign = self.proc / "999"
        foreign.mkdir()
        (foreign / "status").write_text(
            "Name:\tforeign\nUid:\t2002\t2002\t2002\t2002\nPPid:\t1\n",
            encoding="utf-8",
        )
        (foreign / "cmdline").write_text("foreign-secret", encoding="utf-8")

    def _invoke(self, *extra):
        command = [
            sys.executable,
            str(SCRIPT),
            "--app-root",
            str(self.app_root),
            "--selector-app-root",
            SELECTOR_APP_ROOT,
            "--selector-bin",
            str(self.selector_bin),
            "--git-bin",
            str(self.git_bin),
            "--proc-root",
            str(self.proc),
            "--uid",
            "1001",
            "--expected-children",
            "3",
            "--expected-extra-children",
            "0",
            "--expected-sha",
            EXPECTED_SHA,
            *extra,
        ]
        result = subprocess.run(
            command,
            text=True,
            capture_output=True,
            timeout=20,
            check=False,
        )
        payload = json.loads(result.stdout)
        return result, payload

    def test_happy_path_reports_only_sanitized_capacity_and_identity(self):
        result, payload = self._invoke()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["selector"]["selector_app_root"], SELECTOR_APP_ROOT)
        self.assertEqual(payload["selector"]["lsapi"], {
            "LSAPI_CHILDREN": "3",
            "LSAPI_EXTRA_CHILDREN": "0",
        })
        self.assertEqual(payload["runtime"]["lswsgi"]["master_count"], 1)
        self.assertEqual(payload["runtime"]["lswsgi"]["child_count"], 3)
        self.assertEqual(payload["runtime"]["locks"]["supervisor"], [200])
        self.assertEqual(payload["runtime"]["locks"]["daemon"], [201])
        self.assertEqual(payload["release"]["checkout_sha"], EXPECTED_SHA)
        serialized = result.stdout + result.stderr
        for secret in (
            "selector-super-secret",
            "selector-api-secret",
            "runtime-super-secret",
            "cmdline-secret",
            "foreign-secret",
        ):
            self.assertNotIn(secret, serialized)

    def test_selector_children_drift_fails_without_leaking_other_env(self):
        self._write_selector(self._selector_payload(children="10"))

        result, payload = self._invoke()

        self.assertEqual(result.returncode, 1)
        self.assertIn("selector_lsapi_children", payload["errors"])
        self.assertNotIn("selector-super-secret", result.stdout)

    def test_missing_explicit_extra_children_is_drift(self):
        payload = self._selector_payload()
        del payload["available_versions"]["3.14.7"]["users"]["fixture-user"]["applications"][SELECTOR_APP_ROOT]["env_vars"]["LSAPI_EXTRA_CHILDREN"]
        self._write_selector(payload)

        result, report = self._invoke()

        self.assertEqual(result.returncode, 1)
        self.assertIn("selector_lsapi_extra_children", report["errors"])

    def test_stopped_selector_application_fails(self):
        self._write_selector(self._selector_payload(status="stopped"))

        result, report = self._invoke()

        self.assertEqual(result.returncode, 1)
        self.assertIn("selector_app_status", report["errors"])

    def test_runtime_with_more_than_expected_children_fails(self):
        self._write_process(
            104,
            ppid=100,
            comm="lswsgi",
            environ={"LSAPI_CHILDREN": "3", "LSAPI_EXTRA_CHILDREN": "0"},
        )

        result, report = self._invoke()

        self.assertEqual(result.returncode, 1)
        self.assertIn("lswsgi_child_limit", report["errors"])
        self.assertEqual(report["runtime"]["lswsgi"]["child_count"], 4)

    def test_runtime_lsapi_drift_fails(self):
        (self.proc / "103" / "environ").write_bytes(
            b"LSAPI_CHILDREN=10\0LSAPI_EXTRA_CHILDREN=3\0SECRET=never-print\0"
        )

        result, report = self._invoke()

        self.assertEqual(result.returncode, 1)
        self.assertIn("runtime_lsapi_children", report["errors"])
        self.assertIn("runtime_lsapi_extra_children", report["errors"])
        self.assertNotIn("never-print", result.stdout)

    def test_duplicate_supervisors_fail(self):
        self._write_process(203, locks=(self.supervisor_lock,))

        result, report = self._invoke()

        self.assertEqual(result.returncode, 1)
        self.assertIn("supervisor_singleton", report["errors"])

    def test_duplicate_daemons_fail(self):
        self._write_process(204, locks=(self.daemon_lock,))

        result, report = self._invoke()

        self.assertEqual(result.returncode, 1)
        self.assertIn("daemon_singleton", report["errors"])

    def test_unreadable_same_uid_memory_fails_nonzero(self):
        (self.proc / "103" / "smaps_rollup").unlink()

        result, report = self._invoke()

        self.assertEqual(result.returncode, 1)
        self.assertIn("same_uid_processes_readable", report["errors"])
        self.assertEqual(report["runtime"]["unreadable_same_uid_pids"], [103])

    def test_missing_supervisor_state_is_critical_error(self):
        (self.tmp / "ig_bot_supervisor_state.json").unlink()

        result, report = self._invoke()

        self.assertEqual(result.returncode, 2)
        self.assertEqual(report["status"], "error")
        self.assertEqual(report["errors"], ["supervisor_state_unreadable"])

    def test_checkout_and_runtime_sha_mismatch_fail(self):
        self._write_git("b" * 40)
        self._write_runtime_state(sha="c" * 40)

        result, report = self._invoke()

        self.assertEqual(result.returncode, 1)
        self.assertIn("checkout_sha", report["errors"])
        self.assertIn("supervisor_sha", report["errors"])
        self.assertIn("daemon_sha", report["errors"])

    def test_invalid_selector_json_never_forwards_raw_output_or_stderr(self):
        self._write_executable(
            self.selector_bin,
            "#!/bin/sh\nprintf '%s' 'raw-selector-secret'\nprintf '%s' 'stderr-secret' >&2\n",
        )

        result, report = self._invoke()

        self.assertEqual(result.returncode, 2)
        self.assertEqual(report["errors"], ["selector_output_invalid_json"])
        self.assertNotIn("raw-selector-secret", result.stdout + result.stderr)
        self.assertNotIn("stderr-secret", result.stdout + result.stderr)

    def test_selector_command_failure_reports_only_return_code(self):
        self._write_selector({}, returncode=17, stderr="private selector traceback")

        result, report = self._invoke()

        self.assertEqual(result.returncode, 2)
        self.assertEqual(report["errors"], ["selector_command_failed_rc_17"])
        self.assertNotIn("private selector traceback", result.stdout + result.stderr)

    def test_ambiguous_selector_app_is_critical_error(self):
        payload = self._selector_payload()
        payload["available_versions"]["3.13"] = payload["available_versions"]["3.14.7"]
        self._write_selector(payload)

        result, report = self._invoke()

        self.assertEqual(result.returncode, 2)
        self.assertEqual(report["errors"], ["selector_app_ambiguous"])

    def test_missing_selector_app_is_critical_error(self):
        payload = self._selector_payload()
        applications = payload["available_versions"]["3.14.7"]["users"]["fixture-user"]["applications"]
        applications["different/app"] = applications.pop(SELECTOR_APP_ROOT)
        self._write_selector(payload)

        result, report = self._invoke()

        self.assertEqual(result.returncode, 2)
        self.assertEqual(report["errors"], ["selector_app_missing"])

    def test_missing_runtime_lock_is_critical_error(self):
        self.supervisor_lock.unlink()

        result, report = self._invoke()

        self.assertEqual(result.returncode, 2)
        self.assertEqual(report["errors"], ["supervisor_lock_unreadable"])

    def test_runtime_avoid_fork_one_is_rejected_for_shared_hosting_target(self):
        for pid in (100, 101, 102, 103):
            (self.proc / str(pid) / "environ").write_bytes(
                b"LSAPI_CHILDREN=3\0LSAPI_EXTRA_CHILDREN=0\0LSAPI_AVOID_FORK=1\0"
            )

        result, report = self._invoke()

        self.assertEqual(result.returncode, 1)
        self.assertIn("runtime_lsapi_avoid_fork", report["errors"])

    def test_malicious_lsapi_value_is_redacted(self):
        self._write_selector(self._selector_payload(children="secret-in-lsapi-field"))

        result, report = self._invoke()

        self.assertEqual(result.returncode, 1)
        self.assertEqual(
            report["selector"]["lsapi"]["LSAPI_CHILDREN"],
            "<invalid>",
        )
        self.assertNotIn("secret-in-lsapi-field", result.stdout)

    def test_ops_contract_uses_read_only_target_three_zero_without_cron(self):
        ops = (ROOT / "twocomms" / "docs" / "OPS.md").read_text(encoding="utf-8")
        start = ops.index("### S1b CloudLinux capacity audit")
        end = ops.index("### Pre-revert rollback runtime", start)
        section = ops[start:end]
        self.assertIn("audit_cloudlinux_python_capacity.py", section)
        self.assertIn("--expected-children 3", section)
        self.assertIn("--expected-extra-children 0", section)
        self.assertIn("не является cron/worker", section)
        self.assertIn("Setup Python App", section)


if __name__ == "__main__":
    unittest.main()
