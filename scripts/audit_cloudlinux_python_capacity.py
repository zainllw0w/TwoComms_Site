#!/usr/bin/env python3
"""Read-only CloudLinux Python capacity and runtime ownership audit.

The script is intentionally pure stdlib and safe for execution by the
application user. It never prints selector JSON, command lines, or environment
variables outside the small LSAPI allowlist.
"""

from __future__ import annotations

import argparse
import errno
import json
import os
import pwd
import re
import selectors
import shutil
import signal
import stat as stat_module
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path


SCHEMA_VERSION = 1
MAX_SELECTOR_BYTES = 8 * 1024 * 1024
MAX_SELECTOR_STDERR_BYTES = 256 * 1024
MAX_PROC_FILE_BYTES = 2 * 1024 * 1024
MAX_SUPERVISOR_STATE_BYTES = 256 * 1024
MAX_DAEMON_PID_BYTES = 128
DEFAULT_SNAPSHOT_ATTEMPTS = 4
DEFAULT_SNAPSHOT_DELAY = 0.2
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
VERSION_RE = re.compile(r"^[0-9.]{1,20}$")
COMM_RE = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")
USER_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
LSAPI_KEYS = (
    "LSAPI_CHILDREN",
    "LSAPI_EXTRA_CHILDREN",
    "LSAPI_AVOID_FORK",
)
MEMORY_KEYS = (
    "Rss",
    "Pss",
    "Private_Clean",
    "Private_Dirty",
    "Private_Hugetlb",
)


class AuditInputError(ValueError):
    """The audit cannot safely establish a required source of truth."""


def _safe_sha(value) -> str:
    candidate = str(value or "").lower()
    return candidate if SHA_RE.fullmatch(candidate) else "<invalid>"


def _safe_lsapi_value(key: str, value) -> str:
    candidate = str(value or "")
    if key in {"LSAPI_CHILDREN", "LSAPI_EXTRA_CHILDREN"}:
        return candidate if candidate.isdigit() and len(candidate) <= 6 else "<invalid>"
    if key == "LSAPI_AVOID_FORK":
        return candidate if candidate in {"0", "1"} else "<invalid>"
    return "<invalid>"


def _safe_comm(value: str) -> str:
    candidate = str(value or "")[:80]
    return candidate if COMM_RE.fullmatch(candidate) else "<other>"


def _safe_int(value, *, label: str, minimum: int = 0) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise AuditInputError(f"{label}_invalid") from exc
    if parsed < minimum:
        raise AuditInputError(f"{label}_invalid")
    return parsed


def _validate_absolute_file(path: Path, *, label: str, executable: bool = False) -> Path:
    if not path.is_absolute():
        raise AuditInputError(f"{label}_must_be_absolute")
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise AuditInputError(f"{label}_unreadable") from exc
    if not resolved.is_file() or (executable and not os.access(resolved, os.X_OK)):
        raise AuditInputError(f"{label}_unreadable")
    return resolved


def _lstat_not_symlink(path: Path, *, label: str) -> os.stat_result:
    try:
        observed = path.lstat()
    except OSError as exc:
        raise AuditInputError(f"{label}_unreadable") from exc
    if stat_module.S_ISLNK(observed.st_mode):
        raise AuditInputError(f"{label}_symlink_rejected")
    return observed


def _validate_app_root(path: Path, *, uid: int, fixture_mode: bool) -> Path:
    if not path.is_absolute():
        raise AuditInputError("app_root_must_be_absolute")
    _lstat_not_symlink(path, label="app_root")
    try:
        root = path.resolve(strict=True)
    except OSError as exc:
        raise AuditInputError("app_root_unreadable") from exc
    if root == Path("/") or not root.is_dir() or not (root / "manage.py").is_file():
        raise AuditInputError("app_root_missing_manage_py")
    if not fixture_mode and root.stat().st_uid != uid:
        raise AuditInputError("app_root_uid_mismatch")
    return root


def _kill_and_wait_process_group(process: subprocess.Popen, *, timeout: float = 8.0) -> bool:
    """Kill the selector's isolated session and wait until the group vanishes."""
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    except OSError:
        return False
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            process.kill()
            process.wait(timeout=1)
        except (OSError, subprocess.TimeoutExpired):
            return False
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            os.killpg(process.pid, 0)
        except ProcessLookupError:
            return True
        except PermissionError:
            return False
        time.sleep(0.02)
    return False


def _run_bounded_command(command: list[str], *, cwd: Path, timeout: float) -> bytearray:
    try:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
    except OSError as exc:
        raise AuditInputError("selector_command_unavailable") from exc
    assert process.stdout is not None and process.stderr is not None
    os.set_blocking(process.stdout.fileno(), False)
    os.set_blocking(process.stderr.fileno(), False)
    stdout = bytearray()
    stderr_size = 0
    stream_kind = {
        process.stdout.fileno(): "stdout",
        process.stderr.fileno(): "stderr",
    }
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    selector.register(process.stderr, selectors.EVENT_READ)
    deadline = time.monotonic() + timeout
    failure = ""
    try:
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                failure = "selector_command_timeout"
                break
            events = selector.select(min(0.25, remaining))
            if not events and process.poll() is not None:
                events = [(key, selectors.EVENT_READ) for key in selector.get_map().values()]
            for key, _mask in events:
                try:
                    chunk = os.read(key.fd, 65536)
                except BlockingIOError:
                    continue
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                if stream_kind[key.fd] == "stdout":
                    if len(stdout) + len(chunk) > MAX_SELECTOR_BYTES:
                        failure = "selector_output_too_large"
                        break
                    stdout.extend(chunk)
                else:
                    stderr_size += len(chunk)
                    if stderr_size > MAX_SELECTOR_STDERR_BYTES:
                        failure = "selector_stderr_too_large"
                        break
            if failure:
                break
        if failure:
            group_stopped = _kill_and_wait_process_group(process)
            returncode = process.returncode
        else:
            try:
                returncode = process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                failure = "selector_command_timeout"
                group_stopped = _kill_and_wait_process_group(process)
                returncode = process.returncode
    finally:
        selector.close()
        process.stdout.close()
        process.stderr.close()
    if failure:
        for index in range(len(stdout)):
            stdout[index] = 0
        if not group_stopped:
            raise AuditInputError("selector_process_group_not_stopped")
        raise AuditInputError(failure)
    if returncode != 0:
        for index in range(len(stdout)):
            stdout[index] = 0
        raise AuditInputError(f"selector_command_failed_rc_{returncode}")
    return stdout


def _run_json_command(command: list[str], *, cwd: Path, timeout: float) -> dict:
    raw = _run_bounded_command(command, cwd=cwd, timeout=timeout)
    try:
        decoded = raw.decode("utf-8")
        payload = json.loads(decoded)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise AuditInputError("selector_output_invalid_json") from exc
    finally:
        for index in range(len(raw)):
            raw[index] = 0
        decoded = "" if "decoded" in locals() else ""
    if not isinstance(payload, dict):
        raise AuditInputError("selector_output_invalid_shape")
    return payload


def _find_selector_application(
    payload: dict,
    *,
    expected_user: str,
    expected_app_root: str,
) -> dict:
    matches = []
    versions = payload.get("available_versions")
    if not isinstance(versions, dict):
        raise AuditInputError("selector_versions_missing")
    for version, version_payload in versions.items():
        if not isinstance(version_payload, dict):
            continue
        users = version_payload.get("users")
        if not isinstance(users, dict):
            continue
        user_payload = users.get(expected_user)
        if not isinstance(user_payload, dict):
            continue
        applications = user_payload.get("applications")
        if not isinstance(applications, dict):
            continue
        app = applications.get(expected_app_root)
        if isinstance(app, dict):
            matches.append((str(version), app))
    if not matches:
        raise AuditInputError("selector_app_missing")
    if len(matches) != 1:
        raise AuditInputError("selector_app_ambiguous")
    version, app = matches[0]
    env = app.get("env_vars")
    if not isinstance(env, dict):
        raise AuditInputError("selector_env_missing")
    # Discard every non-allowlisted environment value immediately.
    lsapi = {
        key: _safe_lsapi_value(key, env[key])
        for key in LSAPI_KEYS
        if key in env
    }
    raw_status = str(app.get("app_status") or "")
    app_status = raw_status if raw_status in {"started", "stopped"} else "<invalid>"
    safe_version = version if VERSION_RE.fullmatch(version) else "<invalid>"
    return {
        "selector_app_root": expected_app_root,
        "selector_user": expected_user,
        "version": safe_version,
        "app_status": app_status,
        "lsapi": lsapi,
    }


def _read_at(dir_fd: int, name: str, *, max_bytes: int = MAX_PROC_FILE_BYTES) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(name, flags, dir_fd=dir_fd)
    except OSError as exc:
        raise AuditInputError("process_file_unreadable") from exc
    payload = bytearray()
    try:
        while True:
            chunk = os.read(descriptor, min(65536, max_bytes + 1 - len(payload)))
            if not chunk:
                break
            payload.extend(chunk)
            if len(payload) > max_bytes:
                raise AuditInputError("process_file_too_large")
    finally:
        os.close(descriptor)
    return bytes(payload)


def _parse_status(payload: bytes) -> dict[str, str]:
    try:
        lines = payload.decode("utf-8").splitlines()
    except UnicodeError as exc:
        raise AuditInputError("process_status_invalid") from exc
    values = {}
    for line in lines:
        key, separator, value = line.partition(":")
        if separator and key in {"Uid", "PPid"}:
            values[key] = value.strip()
    if "Uid" not in values or "PPid" not in values:
        raise AuditInputError("process_status_incomplete")
    return values


def _real_uid(status: dict[str, str]) -> int:
    return _safe_int(status["Uid"].split()[0], label="process_uid")


def _ppid(status: dict[str, str]) -> int:
    return _safe_int(status["PPid"].split()[0], label="process_ppid")


def _parse_start_ticks(payload: bytes) -> int:
    try:
        _prefix, fields = payload.decode("ascii").rsplit(") ", 1)
        return _safe_int(fields.split()[19], label="process_start_ticks", minimum=1)
    except (UnicodeError, ValueError, IndexError) as exc:
        raise AuditInputError("process_stat_invalid") from exc


def _read_comm(pid_fd: int) -> str:
    try:
        return _safe_comm(_read_at(pid_fd, "comm", max_bytes=4096).decode("utf-8").strip())
    except UnicodeError as exc:
        raise AuditInputError("process_comm_invalid") from exc


def _read_memory(pid_fd: int) -> dict[str, int]:
    try:
        lines = _read_at(pid_fd, "smaps_rollup").decode("utf-8").splitlines()
    except UnicodeError as exc:
        raise AuditInputError("process_memory_invalid") from exc
    observed = dict.fromkeys(MEMORY_KEYS, 0)
    seen = set()
    for line in lines:
        key, separator, rest = line.partition(":")
        if not separator or key not in observed:
            continue
        parts = rest.split()
        if not parts:
            continue
        observed[key] = _safe_int(parts[0], label="process_memory")
        seen.add(key)
    if not {"Rss", "Pss", "Private_Clean", "Private_Dirty"}.issubset(seen):
        raise AuditInputError("process_memory_incomplete")
    return {
        "rss_kib": observed["Rss"],
        "pss_kib": observed["Pss"],
        "private_kib": (
            observed["Private_Clean"]
            + observed["Private_Dirty"]
            + observed["Private_Hugetlb"]
        ),
    }


def _read_lsapi_environ(pid_fd: int) -> dict[str, str]:
    payload = _read_at(pid_fd, "environ")
    values = {}
    for item in payload.split(b"\0"):
        key, separator, value = item.partition(b"=")
        if not separator:
            continue
        try:
            decoded_key = key.decode("ascii")
        except UnicodeError:
            continue
        if decoded_key not in LSAPI_KEYS:
            continue
        try:
            values[decoded_key] = _safe_lsapi_value(
                decoded_key,
                value.decode("ascii")[:32],
            )
        except UnicodeError:
            values[decoded_key] = "<invalid>"
    return values


def _regular_nonsymlink_stat(path: Path, *, label: str) -> os.stat_result:
    observed = _lstat_not_symlink(path, label=label)
    if not stat_module.S_ISREG(observed.st_mode):
        raise AuditInputError(f"{label}_not_regular")
    return observed


def _read_regular_nofollow(path: Path, *, label: str, max_bytes: int) -> bytes:
    """Open, validate and read one immutable inode through a single FD."""
    flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            raise AuditInputError(f"{label}_symlink_rejected") from exc
        raise AuditInputError(f"{label}_unreadable") from exc
    payload = bytearray()
    try:
        observed = os.fstat(descriptor)
        if not stat_module.S_ISREG(observed.st_mode):
            raise AuditInputError(f"{label}_not_regular")
        while True:
            remaining = max_bytes + 1 - len(payload)
            chunk = os.read(descriptor, min(65536, remaining))
            if not chunk:
                break
            payload.extend(chunk)
            if len(payload) > max_bytes:
                raise AuditInputError(f"{label}_too_large")
    finally:
        os.close(descriptor)
    return bytes(payload)


def _lock_identity(observed: os.stat_result) -> tuple[int, int, int]:
    return os.major(observed.st_dev), os.minor(observed.st_dev), observed.st_ino


def _read_proc_locks(proc_fd: int, lock_stats: dict[str, os.stat_result]) -> dict:
    try:
        lines = _read_at(proc_fd, "locks", max_bytes=4 * 1024 * 1024).decode("ascii").splitlines()
    except UnicodeError as exc:
        raise AuditInputError("proc_locks_invalid") from exc
    identities = {name: _lock_identity(value) for name, value in lock_stats.items()}
    result = {name: {"owners": [], "waiters": []} for name in lock_stats}
    for line in lines:
        fields = line.split()
        try:
            flock_index = fields.index("FLOCK")
        except ValueError:
            continue
        if len(fields) <= flock_index + 4:
            continue
        waiter = "->" in fields[:flock_index]
        try:
            pid = int(fields[flock_index + 3])
            device, inode_text = fields[flock_index + 4].rsplit(":", 1)
            major_text, minor_text = device.split(":", 1)
            identity = (int(major_text, 16), int(minor_text, 16), int(inode_text))
        except (ValueError, IndexError):
            continue
        for name, expected in identities.items():
            if identity == expected:
                key = "waiters" if waiter else "owners"
                result[name][key].append(pid)
    for states in result.values():
        states["owners"].sort()
        states["waiters"].sort()
    return result


def _cwd_matches_app(pid_fd: int, app_stat: os.stat_result) -> bool:
    try:
        observed = os.stat("cwd", dir_fd=pid_fd, follow_symlinks=True)
    except OSError as exc:
        raise AuditInputError("process_cwd_unreadable") from exc
    return observed.st_dev == app_stat.st_dev and observed.st_ino == app_stat.st_ino


def _open_proc_root(proc_root: Path) -> int:
    if not proc_root.is_absolute():
        raise AuditInputError("proc_root_must_be_absolute")
    observed = _lstat_not_symlink(proc_root, label="proc_root")
    if not stat_module.S_ISDIR(observed.st_mode):
        raise AuditInputError("proc_root_unreadable")
    flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        return os.open(proc_root, flags)
    except OSError as exc:
        raise AuditInputError("proc_root_unreadable") from exc


def _scan_once(
    proc_root: Path,
    *,
    uid: int,
    app_stat: os.stat_result,
    lock_stats: dict[str, os.stat_result],
    exclude_pid: int | None,
) -> dict:
    proc_fd = _open_proc_root(proc_root)
    processes = []
    unstable = []
    try:
        lock_states = _read_proc_locks(proc_fd, lock_stats)
        for name in sorted(os.listdir(proc_fd)):
            if not name.isdigit():
                continue
            pid = int(name)
            if exclude_pid is not None and pid == exclude_pid:
                continue
            flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
            try:
                pid_fd = os.open(name, flags, dir_fd=proc_fd)
            except OSError:
                continue
            try:
                try:
                    status_before = _parse_status(_read_at(pid_fd, "status"))
                    uid_before = _real_uid(status_before)
                except AuditInputError:
                    continue
                if uid_before != uid:
                    continue
                try:
                    start_before = _parse_start_ticks(_read_at(pid_fd, "stat"))
                except AuditInputError:
                    unstable.append({"pid": pid, "reason": "identity_unreadable"})
                    continue
                try:
                    comm = _read_comm(pid_fd)
                    memory = _read_memory(pid_fd)
                    target_app = comm == "lswsgi" and _cwd_matches_app(pid_fd, app_stat)
                    lsapi = _read_lsapi_environ(pid_fd) if target_app else None
                    status_after = _parse_status(_read_at(pid_fd, "status"))
                    start_after = _parse_start_ticks(_read_at(pid_fd, "stat"))
                except AuditInputError:
                    unstable.append({"pid": pid, "reason": "same_uid_read_unstable"})
                    continue
                if _real_uid(status_after) != uid_before or start_after != start_before:
                    unstable.append({"pid": pid, "reason": "identity_changed"})
                    continue
                process = {
                    "pid": pid,
                    "ppid": _ppid(status_before),
                    "start_ticks": start_before,
                    "comm": comm,
                    "target_app": target_app,
                    "memory": memory,
                }
                if lsapi is not None:
                    process["lsapi"] = lsapi
                processes.append(process)
            finally:
                os.close(pid_fd)
    finally:
        os.close(proc_fd)
    if not processes:
        raise AuditInputError("same_uid_processes_missing")
    return {
        "processes": processes,
        "locks": lock_states,
        "unstable": unstable,
    }


def _snapshot_signature(snapshot: dict) -> tuple:
    identities = tuple(
        sorted(
            (
                item["pid"],
                item["ppid"],
                item["start_ticks"],
                item["comm"],
                item["target_app"],
            )
            for item in snapshot["processes"]
        )
    )
    locks = tuple(
        (name, tuple(value["owners"]), tuple(value["waiters"]))
        for name, value in sorted(snapshot["locks"].items())
    )
    return identities, locks


def _stable_scan(
    proc_root: Path,
    *,
    uid: int,
    app_stat: os.stat_result,
    lock_stats: dict[str, os.stat_result],
    exclude_pid: int | None,
    attempts: int,
    delay: float,
) -> dict:
    previous_signature = None
    instability_count = 0
    last_snapshot = None
    for attempt in range(attempts):
        snapshot = _scan_once(
            proc_root,
            uid=uid,
            app_stat=app_stat,
            lock_stats=lock_stats,
            exclude_pid=exclude_pid,
        )
        last_snapshot = snapshot
        if snapshot["unstable"]:
            instability_count += 1
            previous_signature = None
        else:
            signature = _snapshot_signature(snapshot)
            if previous_signature is not None:
                if signature == previous_signature:
                    snapshot["snapshot_attempts"] = attempt + 1
                    snapshot["instability_count"] = instability_count
                    return snapshot
                instability_count += 1
            previous_signature = signature
        if instability_count >= 2:
            raise AuditInputError("process_identity_repeatedly_unstable")
        if attempt + 1 < attempts:
            time.sleep(delay)
    if last_snapshot and last_snapshot["unstable"]:
        raise AuditInputError("process_identity_unstable")
    raise AuditInputError("process_snapshots_inconsistent")


def _sum_memory(processes: list[dict]) -> dict[str, int]:
    return {
        "rss_sum_kib": sum(process["memory"]["rss_kib"] for process in processes),
        "pss_sum_kib": sum(process["memory"]["pss_kib"] for process in processes),
        "private_sum_kib": sum(process["memory"]["private_kib"] for process in processes),
    }


def _load_supervisor_state(app_root: Path) -> dict:
    path = app_root / "tmp" / "ig_bot_supervisor_state.json"
    try:
        raw = _read_regular_nofollow(
            path,
            label="supervisor_state",
            max_bytes=MAX_SUPERVISOR_STATE_BYTES,
        )
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise AuditInputError("supervisor_state_unreadable") from exc
    if not isinstance(payload, dict):
        raise AuditInputError("supervisor_state_invalid")
    return payload


def _read_daemon_pid(app_root: Path) -> int:
    path = app_root / "tmp" / "ig_bot.pid"
    try:
        return _safe_int(
            _read_regular_nofollow(
                path,
                label="daemon_pid_file",
                max_bytes=MAX_DAEMON_PID_BYTES,
            ).decode("ascii").strip(),
            label="daemon_pid",
            minimum=1,
        )
    except UnicodeError as exc:
        raise AuditInputError("daemon_pid_unreadable") from exc


def _revalidate_process_identity(
    proc_root: Path,
    *,
    pid: int,
    uid: int,
    start_ticks: int,
) -> bool:
    proc_fd = _open_proc_root(proc_root)
    flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        pid_fd = os.open(str(pid), flags, dir_fd=proc_fd)
        try:
            status = _parse_status(_read_at(pid_fd, "status"))
            observed_ticks = _parse_start_ticks(_read_at(pid_fd, "stat"))
        finally:
            os.close(pid_fd)
    except (OSError, AuditInputError):
        return False
    finally:
        os.close(proc_fd)
    return _real_uid(status) == uid and observed_ticks == start_ticks


def _git_head(app_root: Path, git_bin: Path) -> str:
    try:
        result = subprocess.run(
            [os.fspath(git_bin), "rev-parse", "HEAD"],
            cwd=app_root,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise AuditInputError("git_head_unreadable") from exc
    if result.returncode != 0:
        raise AuditInputError("git_head_unreadable")
    try:
        sha = result.stdout.decode("ascii").strip().lower()
    except UnicodeError as exc:
        raise AuditInputError("git_head_invalid") from exc
    if not SHA_RE.fullmatch(sha):
        raise AuditInputError("git_head_invalid")
    return sha


def _check(checks: list[dict], code: str, ok: bool, observed=None, expected=None) -> None:
    item = {"code": code, "ok": bool(ok)}
    if observed is not None:
        item["observed"] = observed
    if expected is not None:
        item["expected"] = expected
    checks.append(item)


def audit_capacity(args) -> tuple[dict, int]:
    checks = []
    errors = []
    try:
        fixture_mode = bool(args.fixture_mode)
        uid = _safe_int(args.uid, label="uid")
        if not fixture_mode and uid != os.geteuid():
            raise AuditInputError("production_uid_must_equal_euid")
        proc_root = Path(args.proc_root)
        if not fixture_mode and os.fspath(proc_root) != "/proc":
            raise AuditInputError("production_proc_root_must_be_proc")
        attempts = _safe_int(args.snapshot_attempts, label="snapshot_attempts", minimum=2)
        try:
            snapshot_delay = float(args.snapshot_delay)
        except (TypeError, ValueError) as exc:
            raise AuditInputError("snapshot_delay_invalid") from exc
        if attempts > 5 or not 0 <= snapshot_delay <= 2:
            raise AuditInputError("snapshot_policy_invalid")
        if not fixture_mode and (
            attempts != DEFAULT_SNAPSHOT_ATTEMPTS
            or snapshot_delay != DEFAULT_SNAPSHOT_DELAY
        ):
            raise AuditInputError("production_snapshot_policy_is_fixed")
        try:
            account = pwd.getpwuid(uid)
        except KeyError as exc:
            if not fixture_mode:
                raise AuditInputError("euid_account_unavailable") from exc
            account = None
        selector_user = str(args.selector_user or (account.pw_name if account else ""))
        if not USER_RE.fullmatch(selector_user):
            raise AuditInputError("selector_user_invalid")
        selector_home = Path(
            args.selector_home
            or (account.pw_dir if account else "")
        )
        if not selector_home.is_absolute():
            raise AuditInputError("selector_home_must_be_absolute")
        if not fixture_mode and (
            selector_user != account.pw_name
            or selector_home.resolve(strict=True) != Path(account.pw_dir).resolve(strict=True)
        ):
            raise AuditInputError("selector_account_mismatch")
        app_root = _validate_app_root(
            Path(args.app_root),
            uid=uid,
            fixture_mode=fixture_mode,
        )
        try:
            canonical_selector_root = app_root.relative_to(
                selector_home.resolve(strict=True)
            ).as_posix()
        except (OSError, ValueError) as exc:
            raise AuditInputError("app_root_outside_selector_home") from exc
        if canonical_selector_root != str(args.selector_app_root):
            raise AuditInputError("selector_app_root_not_canonical")
        expected_children = _safe_int(
            args.expected_children,
            label="expected_children",
            minimum=1,
        )
        expected_extra = _safe_int(
            args.expected_extra_children,
            label="expected_extra_children",
        )
        expected_status = str(args.expected_status or "started")
        if expected_status not in {"started", "stopped"}:
            raise AuditInputError("expected_status_invalid")
        try:
            command_timeout = float(args.timeout)
        except (TypeError, ValueError) as exc:
            raise AuditInputError("timeout_invalid") from exc
        if not 0.1 <= command_timeout <= 60:
            raise AuditInputError("timeout_invalid")
        expected_sha = str(args.expected_sha or "").lower()
        if expected_sha and not SHA_RE.fullmatch(expected_sha):
            raise AuditInputError("expected_sha_invalid")
        selector_bin = _validate_absolute_file(
            Path(args.selector_bin),
            label="selector_bin",
            executable=True,
        )
        selector_payload = _run_json_command(
            [os.fspath(selector_bin), "get", "--json", "--interpreter", "python"],
            cwd=app_root,
            timeout=command_timeout,
        )
        try:
            selector = _find_selector_application(
                selector_payload,
                expected_user=selector_user,
                expected_app_root=canonical_selector_root,
            )
        finally:
            selector_payload.clear()
            del selector_payload
        selector_children = selector["lsapi"].get("LSAPI_CHILDREN")
        selector_extra = selector["lsapi"].get("LSAPI_EXTRA_CHILDREN")
        _check(
            checks,
            "selector_app_status",
            selector["app_status"] == expected_status,
            selector["app_status"],
            expected_status,
        )
        _check(
            checks,
            "selector_lsapi_children",
            selector_children == str(expected_children),
            selector_children or "<missing>",
            str(expected_children),
        )
        _check(
            checks,
            "selector_lsapi_extra_children",
            selector_extra == str(expected_extra),
            selector_extra or "<missing>",
            str(expected_extra),
        )

        lock_paths = {
            "supervisor": app_root / "tmp" / "ig_bot_supervisor.lock",
            "daemon": app_root / "tmp" / "ig_bot_daemon.lock",
        }
        lock_stats = {
            name: _regular_nonsymlink_stat(path, label=f"{name}_lock")
            for name, path in lock_paths.items()
        }
        scan = _stable_scan(
            proc_root,
            uid=uid,
            app_stat=app_root.stat(),
            lock_stats=lock_stats,
            exclude_pid=None if fixture_mode else os.getpid(),
            attempts=attempts,
            delay=snapshot_delay,
        )
        processes = scan["processes"]
        lswsgi = [process for process in processes if process["target_app"]]
        other_lswsgi = [
            process
            for process in processes
            if process["comm"] == "lswsgi" and not process["target_app"]
        ]
        lswsgi_pids = {process["pid"] for process in lswsgi}
        masters = [process for process in lswsgi if process["ppid"] not in lswsgi_pids]
        children = [process for process in lswsgi if process["ppid"] in lswsgi_pids]
        _check(checks, "lswsgi_master_count", len(masters) == 1, len(masters), 1)
        _check(
            checks,
            "lswsgi_child_limit",
            len(children) <= expected_children + expected_extra,
            len(children),
            expected_children + expected_extra,
        )
        runtime_env_sets = {
            key: sorted({process.get("lsapi", {}).get(key, "<missing>") for process in lswsgi})
            for key in LSAPI_KEYS
        }
        _check(
            checks,
            "runtime_lsapi_children",
            bool(lswsgi)
            and runtime_env_sets["LSAPI_CHILDREN"] == [str(expected_children)],
            runtime_env_sets["LSAPI_CHILDREN"],
            [str(expected_children)],
        )
        _check(
            checks,
            "runtime_lsapi_extra_children",
            bool(lswsgi)
            and runtime_env_sets["LSAPI_EXTRA_CHILDREN"] == [str(expected_extra)],
            runtime_env_sets["LSAPI_EXTRA_CHILDREN"],
            [str(expected_extra)],
        )
        avoid_values = runtime_env_sets["LSAPI_AVOID_FORK"]
        _check(
            checks,
            "runtime_lsapi_avoid_fork",
            bool(lswsgi) and set(avoid_values).issubset({"0", "<missing>"}),
            avoid_values,
            ["0", "<missing>"],
        )

        holders = {
            name: list(scan["locks"][name]["owners"])
            for name in lock_paths
        }
        waiters = {
            name: list(scan["locks"][name]["waiters"])
            for name in lock_paths
        }
        _check(checks, "supervisor_singleton", len(holders["supervisor"]) == 1, holders["supervisor"], "one pid")
        _check(checks, "daemon_singleton", len(holders["daemon"]) == 1, holders["daemon"], "one pid")
        state = _load_supervisor_state(app_root)
        daemon_pid = _read_daemon_pid(app_root)
        state_supervisor_pid = _safe_int(
            state.get("supervisor_pid"),
            label="state_supervisor_pid",
            minimum=1,
        )
        state_child_pid = _safe_int(
            state.get("child_pid"),
            label="state_child_pid",
            minimum=1,
        )
        state_supervisor_ticks = _safe_int(
            state.get("supervisor_start_ticks"),
            label="state_supervisor_start_ticks",
            minimum=1,
        )
        state_child_ticks = _safe_int(
            state.get("child_start_ticks"),
            label="state_child_start_ticks",
            minimum=1,
        )
        process_by_pid = {process["pid"]: process for process in processes}
        _check(
            checks,
            "supervisor_state_pid",
            holders["supervisor"] == [state_supervisor_pid],
            holders["supervisor"],
            [state_supervisor_pid],
        )
        _check(
            checks,
            "supervisor_state_identity",
            bool(process_by_pid.get(state_supervisor_pid))
            and process_by_pid[state_supervisor_pid]["start_ticks"] == state_supervisor_ticks,
            process_by_pid.get(state_supervisor_pid, {}).get("start_ticks", "<missing>"),
            state_supervisor_ticks,
        )
        _check(
            checks,
            "daemon_state_pid",
            holders["daemon"] == [state_child_pid] and daemon_pid == state_child_pid,
            {"lock_holders": holders["daemon"], "pid_file": daemon_pid},
            {"lock_holders": [state_child_pid], "pid_file": state_child_pid},
        )
        _check(
            checks,
            "daemon_state_identity",
            bool(process_by_pid.get(state_child_pid))
            and process_by_pid[state_child_pid]["start_ticks"] == state_child_ticks,
            process_by_pid.get(state_child_pid, {}).get("start_ticks", "<missing>"),
            state_child_ticks,
        )
        if not _revalidate_process_identity(
            proc_root,
            pid=state_supervisor_pid,
            uid=uid,
            start_ticks=state_supervisor_ticks,
        ) or not _revalidate_process_identity(
            proc_root,
            pid=state_child_pid,
            uid=uid,
            start_ticks=state_child_ticks,
        ):
            raise AuditInputError("runtime_identity_changed_after_snapshot")

        state_supervisor_sha = _safe_sha(state.get("supervisor_release_sha"))
        state_daemon_sha = _safe_sha(state.get("child_release_sha"))
        sha = None
        if expected_sha:
            git_candidate = Path(args.git_bin)
            if not git_candidate.is_absolute():
                located = shutil.which(os.fspath(git_candidate))
                if not located:
                    raise AuditInputError("git_bin_unreadable")
                git_candidate = Path(located)
            git_bin = _validate_absolute_file(
                git_candidate,
                label="git_bin",
                executable=True,
            )
            sha = _git_head(app_root, git_bin)
            _check(checks, "checkout_sha", sha == expected_sha, sha, expected_sha)
            _check(
                checks,
                "supervisor_sha",
                state_supervisor_sha == expected_sha,
                state_supervisor_sha,
                expected_sha,
            )
            _check(
                checks,
                "daemon_sha",
                state_daemon_sha == expected_sha,
                state_daemon_sha,
                expected_sha,
            )

        grouped = defaultdict(list)
        for process in processes:
            grouped[process["comm"]].append(process)
        result = {
            "schema_version": SCHEMA_VERSION,
            "status": "ok",
            "selector": selector,
            "runtime": {
                "uid": uid,
                "same_uid_process_count": len(processes),
                "auditor_pid_excluded": None if fixture_mode else os.getpid(),
                "snapshot_attempts": scan["snapshot_attempts"],
                "instability_count": scan["instability_count"],
                "lswsgi": {
                    "master_count": len(masters),
                    "child_count": len(children),
                    "other_same_uid_app_count": len(other_lswsgi),
                    "master_pids": sorted(process["pid"] for process in masters),
                    "child_pids": sorted(process["pid"] for process in children),
                    "lsapi": runtime_env_sets,
                    "memory": _sum_memory(lswsgi),
                },
                "locks": {
                    name: {"owners": holders[name], "waiters": waiters[name]}
                    for name in sorted(lock_paths)
                },
                "memory_accounting_note": (
                    "rss_sum_kib double-counts shared pages; use pss_sum_kib and "
                    "private_sum_kib as primary capacity evidence"
                ),
                "memory": _sum_memory(processes),
                "memory_by_comm": {
                    comm: {"count": len(items), **_sum_memory(items)}
                    for comm, items in sorted(grouped.items())
                },
            },
            "release": {
                "expected_sha": expected_sha or None,
                "checkout_sha": sha,
                "supervisor_sha": state_supervisor_sha,
                "daemon_sha": state_daemon_sha,
            },
            "checks": checks,
            "errors": errors,
        }
        failed_codes = [item["code"] for item in checks if not item["ok"]]
        if failed_codes:
            result["status"] = "fail"
            result["errors"] = failed_codes
            return result, 1
        return result, 0
    except AuditInputError as exc:
        code = str(exc) or "audit_input_error"
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "error",
            "selector": None,
            "runtime": None,
            "release": None,
            "checks": checks,
            "errors": [code],
        }, 2
    except Exception as exc:
        # Fail closed without serializing exception text, selector payload,
        # process arguments, paths from foreign users, or environment values.
        safe_kind = re.sub(r"[^A-Za-z0-9_]", "", exc.__class__.__name__)[:64]
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "error",
            "selector": None,
            "runtime": None,
            "release": None,
            "checks": checks,
            "errors": [f"internal_{safe_kind or 'Error'}"],
        }, 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-root", required=True)
    parser.add_argument("--selector-app-root", required=True)
    parser.add_argument("--selector-user", default="")
    parser.add_argument("--selector-home", default="")
    parser.add_argument("--expected-children", type=int, default=3)
    parser.add_argument("--expected-extra-children", type=int, default=0)
    parser.add_argument("--expected-status", default="started")
    parser.add_argument("--expected-sha", default="")
    parser.add_argument(
        "--selector-bin",
        default=shutil.which("cloudlinux-selector") or "/usr/bin/cloudlinux-selector",
    )
    parser.add_argument("--git-bin", default=shutil.which("git") or "git")
    parser.add_argument("--proc-root", default="/proc")
    parser.add_argument("--uid", type=int, default=os.geteuid())
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--snapshot-attempts", type=int, default=DEFAULT_SNAPSHOT_ATTEMPTS)
    parser.add_argument("--snapshot-delay", type=float, default=DEFAULT_SNAPSHOT_DELAY)
    parser.add_argument(
        "--fixture-mode",
        action="store_true",
        help="Tests only: permit a custom proc root, UID, selector user/home and timing.",
    )
    return parser


def main(argv=None) -> int:
    args = _build_parser().parse_args(argv)
    payload, exit_code = audit_capacity(args)
    print(json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
