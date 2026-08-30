import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "audit_cloudlinux_python_capacity.py"
SPEC = importlib.util.spec_from_file_location("capacity_auditor", SCRIPT)
auditor = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(auditor)
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
        (self.proc / "locks").write_text("", encoding="ascii")
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
        self._write_proc_locks(
            owners={"supervisor": [200], "daemon": [201]},
        )

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

    def _start_ticks(self, pid):
        return pid * 10 + 1

    def _write_runtime_state(self, *, supervisor_pid=200, daemon_pid=201, sha=EXPECTED_SHA):
        (self.tmp / "ig_bot_supervisor_state.json").write_text(
            json.dumps(
                {
                    "event": "child_started",
                    "supervisor_pid": supervisor_pid,
                    "child_pid": daemon_pid,
                    "supervisor_start_ticks": self._start_ticks(supervisor_pid),
                    "child_start_ticks": self._start_ticks(daemon_pid),
                    "supervisor_release_sha": sha,
                    "child_release_sha": sha,
                }
            ),
            encoding="utf-8",
        )
        (self.tmp / "ig_bot.pid").write_text(str(daemon_pid), encoding="ascii")

    def _lock_token(self, path):
        observed = path.stat()
        return f"{os.major(observed.st_dev):02x}:{os.minor(observed.st_dev):02x}:{observed.st_ino}"

    def _write_proc_locks(self, *, owners=None, waiters=None):
        owners = owners or {}
        waiters = waiters or {}
        paths = {"supervisor": self.supervisor_lock, "daemon": self.daemon_lock}
        lines = []
        index = 1
        for name, pids in owners.items():
            for pid in pids:
                lines.append(
                    f"{index}: FLOCK ADVISORY WRITE {pid} {self._lock_token(paths[name])} 0 EOF"
                )
                index += 1
        for name, pids in waiters.items():
            for pid in pids:
                lines.append(
                    f"{index}: -> FLOCK ADVISORY WRITE {pid} {self._lock_token(paths[name])} 0 EOF"
                )
                index += 1
        (self.proc / "locks").write_text("\n".join(lines) + "\n", encoding="ascii")

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
        cwd=None,
        start_ticks=None,
    ):
        proc_dir = self.proc / str(pid)
        proc_dir.mkdir()
        (proc_dir / "status").write_text(
            f"Name:\t{comm}\nUid:\t{uid}\t{uid}\t{uid}\t{uid}\nPPid:\t{ppid}\n",
            encoding="utf-8",
        )
        (proc_dir / "comm").write_text(comm + "\n", encoding="utf-8")
        ticks = start_ticks if start_ticks is not None else self._start_ticks(pid)
        stat_fields = ["S"] + ["0"] * 18 + [str(ticks)]
        (proc_dir / "stat").write_text(
            f"{pid} ({comm}) " + " ".join(stat_fields) + "\n",
            encoding="ascii",
        )
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
        (proc_dir / "cwd").symlink_to(cwd or self.app_root)

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

    def _invoke(self, *extra, fixture=True):
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
            "1001" if fixture else str(os.geteuid()),
            "--expected-children",
            "3",
            "--expected-extra-children",
            "0",
            "--expected-sha",
            EXPECTED_SHA,
        ]
        if fixture:
            command.extend(
                [
                    "--selector-user",
                    "fixture-user",
                    "--selector-home",
                    str(self.root / "home" / "app"),
                    "--fixture-mode",
                    "--snapshot-attempts",
                    "2",
                    "--snapshot-delay",
                    "0",
                ]
            )
        command.extend(extra)
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
        self.assertEqual(payload["runtime"]["locks"]["supervisor"]["owners"], [200])
        self.assertEqual(payload["runtime"]["locks"]["daemon"]["owners"], [201])
        self.assertIn("rss_sum_kib double-counts", payload["runtime"]["memory_accounting_note"])
        self.assertIn("pss_sum_kib", payload["runtime"]["memory"])
        self.assertNotIn("rss_kib", payload["runtime"]["memory"])
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

    def test_same_uid_second_application_is_not_counted_as_target_lswsgi(self):
        other_app = self.root / "home" / "app" / "other-app"
        other_app.mkdir()
        self._write_process(
            104,
            ppid=1,
            comm="lswsgi",
            cwd=other_app,
            environ={
                "LSAPI_CHILDREN": "99",
                "LSAPI_EXTRA_CHILDREN": "33",
                "OTHER_APP_SECRET": "never-output-other-app",
            },
        )
        applications = self.selector_payload["available_versions"]["3.14.7"]["users"]["fixture-user"]["applications"]
        applications["other-app"] = {
            "app_status": "started",
            "env_vars": {"LSAPI_CHILDREN": "99", "OTHER_SECRET": "selector-other-secret"},
        }
        self._write_selector(self.selector_payload)

        result, report = self._invoke()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(report["runtime"]["lswsgi"]["child_count"], 3)
        self.assertEqual(report["runtime"]["lswsgi"]["other_same_uid_app_count"], 1)
        self.assertNotIn("never-output-other-app", result.stdout)
        self.assertNotIn("selector-other-secret", result.stdout)

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
        self._write_proc_locks(
            owners={"supervisor": [200, 203], "daemon": [201]},
        )

        result, report = self._invoke()

        self.assertEqual(result.returncode, 1)
        self.assertIn("supervisor_singleton", report["errors"])

    def test_duplicate_daemons_fail(self):
        self._write_process(204, locks=(self.daemon_lock,))
        self._write_proc_locks(
            owners={"supervisor": [200], "daemon": [201, 204]},
        )

        result, report = self._invoke()

        self.assertEqual(result.returncode, 1)
        self.assertIn("daemon_singleton", report["errors"])

    def test_flock_waiter_is_not_misclassified_as_duplicate_owner(self):
        self._write_process(203)
        self._write_proc_locks(
            owners={"supervisor": [200], "daemon": [201]},
            waiters={"supervisor": [203]},
        )

        result, report = self._invoke()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(report["runtime"]["locks"]["supervisor"]["owners"], [200])
        self.assertEqual(report["runtime"]["locks"]["supervisor"]["waiters"], [203])

    def test_open_but_unlocked_fd_is_not_an_owner(self):
        self._write_process(203, locks=(self.supervisor_lock,))
        # /proc/locks intentionally retains only PID 200 as the true owner.

        result, report = self._invoke()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(report["runtime"]["locks"]["supervisor"]["owners"], [200])

    def test_flock_owner_must_match_supervisor_state(self):
        self._write_process(203)
        self._write_proc_locks(
            owners={"supervisor": [203], "daemon": [201]},
        )

        result, report = self._invoke()

        self.assertEqual(result.returncode, 1)
        self.assertIn("supervisor_state_pid", report["errors"])

    def test_unreadable_same_uid_memory_fails_nonzero(self):
        (self.proc / "103" / "smaps_rollup").unlink()

        result, report = self._invoke()

        self.assertEqual(result.returncode, 2)
        self.assertEqual(report["errors"], ["process_identity_repeatedly_unstable"])

    def test_missing_supervisor_state_is_critical_error(self):
        (self.tmp / "ig_bot_supervisor_state.json").unlink()

        result, report = self._invoke()

        self.assertEqual(result.returncode, 2)
        self.assertEqual(report["status"], "error")
        self.assertEqual(report["errors"], ["supervisor_state_unreadable"])

    def test_state_and_pid_reads_use_single_open_inode_across_path_swap(self):
        state_path = self.tmp / "ig_bot_supervisor_state.json"
        replacement_state = self.tmp / "replacement-state.json"
        replacement_state.write_text(
            json.dumps({"supervisor_pid": 999, "private": "must-not-win"}),
            encoding="utf-8",
        )
        real_open = auditor.os.open
        swapped = {"state": False}

        def state_swap(path, flags, *args, **kwargs):
            descriptor = real_open(path, flags, *args, **kwargs)
            if Path(path) == state_path and not swapped["state"]:
                swapped["state"] = True
                os.replace(replacement_state, state_path)
            return descriptor

        with patch.object(auditor.os, "open", side_effect=state_swap):
            payload = auditor._load_supervisor_state(self.app_root)
        self.assertEqual(payload["supervisor_pid"], 200)
        self.assertNotIn("private", payload)

        self._write_runtime_state()
        pid_path = self.tmp / "ig_bot.pid"
        replacement_pid = self.tmp / "replacement.pid"
        replacement_pid.write_text("999", encoding="ascii")
        swapped["pid"] = False

        def pid_swap(path, flags, *args, **kwargs):
            descriptor = real_open(path, flags, *args, **kwargs)
            if Path(path) == pid_path and not swapped["pid"]:
                swapped["pid"] = True
                os.replace(replacement_pid, pid_path)
            return descriptor

        with patch.object(auditor.os, "open", side_effect=pid_swap):
            daemon_pid = auditor._read_daemon_pid(self.app_root)
        self.assertEqual(daemon_pid, 201)

    def test_state_and_pid_files_have_strict_byte_limits(self):
        state_path = self.tmp / "ig_bot_supervisor_state.json"
        state_path.write_bytes(b"x" * (auditor.MAX_SUPERVISOR_STATE_BYTES + 1))
        with self.assertRaisesRegex(
            auditor.AuditInputError,
            "supervisor_state_too_large",
        ):
            auditor._load_supervisor_state(self.app_root)

        pid_path = self.tmp / "ig_bot.pid"
        pid_path.write_bytes(b"1" * (auditor.MAX_DAEMON_PID_BYTES + 1))
        with self.assertRaisesRegex(
            auditor.AuditInputError,
            "daemon_pid_file_too_large",
        ):
            auditor._read_daemon_pid(self.app_root)

    def test_checkout_and_runtime_sha_mismatch_fail(self):
        self._write_git("b" * 40)
        self._write_runtime_state(sha="c" * 40)

        result, report = self._invoke()

        self.assertEqual(result.returncode, 1)
        self.assertIn("checkout_sha", report["errors"])
        self.assertIn("supervisor_sha", report["errors"])
        self.assertIn("daemon_sha", report["errors"])

    def test_supervisor_and_daemon_start_ticks_must_match_state(self):
        self._write_runtime_state()
        state_path = self.tmp / "ig_bot_supervisor_state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["supervisor_start_ticks"] += 1
        state["child_start_ticks"] += 1
        state_path.write_text(json.dumps(state), encoding="utf-8")

        result, report = self._invoke()

        self.assertEqual(result.returncode, 2)
        self.assertEqual(report["errors"], ["runtime_identity_changed_after_snapshot"])

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

    def test_selector_stdout_and_stderr_are_hard_bounded(self):
        self._write_executable(
            self.selector_bin,
            "#!/usr/bin/env python3\n"
            "import sys\n"
            "sys.stdout.write('x' * (8 * 1024 * 1024 + 65536))\n",
        )
        result, report = self._invoke()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(report["errors"], ["selector_output_too_large"])
        self.assertLess(len(result.stdout), 4096)

        self._write_executable(
            self.selector_bin,
            "#!/usr/bin/env python3\n"
            "import sys\n"
            "sys.stderr.write('private' * (256 * 1024))\n",
        )
        result, report = self._invoke()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(report["errors"], ["selector_stderr_too_large"])
        self.assertNotIn("private", result.stdout + result.stderr)

    def test_selector_timeout_kills_inherited_pipe_grandchild_group(self):
        marker = self.root / "selector-processes.txt"
        payload = json.dumps(self.selector_payload)
        self._write_executable(
            self.selector_bin,
            "#!/usr/bin/env python3\n"
            "import os, subprocess, sys\n"
            "child = subprocess.Popen(\n"
            "    [sys.executable, '-c', 'import time; time.sleep(60)'],\n"
            "    stdout=sys.stdout, stderr=sys.stderr,\n"
            ")\n"
            f"open({str(marker)!r}, 'w').write(f'{{os.getpid()}} {{child.pid}}')\n"
            f"print({payload!r}, flush=True)\n",
        )
        started = __import__("time").monotonic()

        result, report = self._invoke("--timeout", "0.5")

        self.assertLess(__import__("time").monotonic() - started, 5)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(report["errors"], ["selector_command_timeout"])
        parent_pid, child_pid = map(int, marker.read_text(encoding="ascii").split())
        for pid in (parent_pid, child_pid):
            with self.assertRaises(ProcessLookupError):
                os.kill(pid, 0)

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

    def test_selector_user_and_canonical_root_are_bound(self):
        result, report = self._invoke("--selector-user", "other-user")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(report["errors"], ["selector_app_missing"])

        result, report = self._invoke("--selector-app-root", "different/app")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(report["errors"], ["selector_app_root_not_canonical"])

    def test_missing_runtime_lock_is_critical_error(self):
        self.supervisor_lock.unlink()

        result, report = self._invoke()

        self.assertEqual(result.returncode, 2)
        self.assertEqual(report["errors"], ["supervisor_lock_unreadable"])

    def test_symlinked_proc_lock_and_state_are_rejected(self):
        real_proc = self.proc.with_name("real-proc")
        self.proc.rename(real_proc)
        self.proc.symlink_to(real_proc, target_is_directory=True)
        result, report = self._invoke()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(report["errors"], ["proc_root_symlink_rejected"])

        self.proc.unlink()
        real_proc.rename(self.proc)
        proc_locks = self.proc / "locks"
        real_proc_locks = self.proc / "real-locks"
        proc_locks.rename(real_proc_locks)
        proc_locks.symlink_to(real_proc_locks)
        result, report = self._invoke()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(report["errors"], ["process_file_unreadable"])

        proc_locks.unlink()
        real_proc_locks.rename(proc_locks)
        real_lock = self.supervisor_lock.with_name("real-supervisor.lock")
        self.supervisor_lock.rename(real_lock)
        self.supervisor_lock.symlink_to(real_lock)
        result, report = self._invoke()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(report["errors"], ["supervisor_lock_symlink_rejected"])

        self.supervisor_lock.unlink()
        real_lock.rename(self.supervisor_lock)
        state_path = self.tmp / "ig_bot_supervisor_state.json"
        real_state = state_path.with_name("real-state.json")
        state_path.rename(real_state)
        state_path.symlink_to(real_state)
        result, report = self._invoke()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(report["errors"], ["supervisor_state_symlink_rejected"])

    def test_symlinked_app_root_is_not_a_canonical_selector_identity(self):
        linked_root = self.app_root.parent / "linked-app"
        linked_root.symlink_to(self.app_root, target_is_directory=True)

        result, report = self._invoke("--app-root", str(linked_root))

        self.assertEqual(result.returncode, 2)
        self.assertEqual(report["errors"], ["app_root_symlink_rejected"])

    def test_production_mode_rejects_custom_uid_and_proc_fixture(self):
        result, report = self._invoke(fixture=False)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(report["errors"], ["production_proc_root_must_be_proc"])

    def test_snapshot_can_exclude_the_auditor_pid_from_capacity_totals(self):
        snapshot = auditor._scan_once(
            self.proc,
            uid=1001,
            app_stat=self.app_root.stat(),
            lock_stats={
                "supervisor": self.supervisor_lock.stat(),
                "daemon": self.daemon_lock.stat(),
            },
            exclude_pid=202,
        )
        self.assertNotIn(202, {process["pid"] for process in snapshot["processes"]})

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
        self.assertIn("от нуля до трёх child", section)
        self.assertIn("pss_sum_kib", section)
        self.assertIn("inode `/proc/locks`", section)


class StableSnapshotPolicyTests(unittest.TestCase):
    @staticmethod
    def _snapshot(pid=100, *, unstable=None):
        return {
            "processes": [
                {
                    "pid": pid,
                    "ppid": 1,
                    "start_ticks": pid * 10,
                    "comm": "lswsgi",
                    "target_app": True,
                    "memory": {"rss_kib": 1, "pss_kib": 1, "private_kib": 1},
                    "lsapi": {"LSAPI_CHILDREN": "3", "LSAPI_EXTRA_CHILDREN": "0"},
                }
            ],
            "locks": {
                "supervisor": {"owners": [200], "waiters": []},
                "daemon": {"owners": [201], "waiters": []},
            },
            "unstable": list(unstable or []),
        }

    def _run(self, side_effect, attempts):
        with patch.object(auditor, "_scan_once", side_effect=side_effect):
            return auditor._stable_scan(
                Path("/fixture"),
                uid=1001,
                app_stat=None,
                lock_stats={},
                exclude_pid=None,
                attempts=attempts,
                delay=0,
            )

    def test_two_consistent_snapshots_are_required(self):
        result = self._run([self._snapshot(), self._snapshot()], 2)
        self.assertEqual(result["snapshot_attempts"], 2)
        self.assertEqual(result["instability_count"], 0)

    def test_one_vanish_can_retry_then_requires_two_stable_snapshots(self):
        unstable = self._snapshot(unstable=[{"pid": 100, "reason": "identity_changed"}])
        result = self._run([unstable, self._snapshot(), self._snapshot()], 3)
        self.assertEqual(result["snapshot_attempts"], 3)
        self.assertEqual(result["instability_count"], 1)

    def test_repeated_vanish_or_identity_change_is_critical(self):
        unstable = self._snapshot(unstable=[{"pid": 100, "reason": "identity_changed"}])
        with self.assertRaisesRegex(
            auditor.AuditInputError,
            "process_identity_repeatedly_unstable",
        ):
            self._run([unstable, unstable], 3)

        with self.assertRaisesRegex(
            auditor.AuditInputError,
            "process_identity_repeatedly_unstable",
        ):
            self._run(
                [self._snapshot(100), self._snapshot(101), self._snapshot(102)],
                3,
            )


if __name__ == "__main__":
    unittest.main()
