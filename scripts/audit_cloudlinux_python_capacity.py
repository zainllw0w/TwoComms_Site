#!/usr/bin/env python3
"""Read-only CloudLinux Python capacity and runtime ownership audit.

The script is intentionally pure stdlib and safe for execution by the
application user. It never prints selector JSON, command lines, or environment
variables outside the small LSAPI allowlist.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path


SCHEMA_VERSION = 1
MAX_SELECTOR_BYTES = 8 * 1024 * 1024
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
VERSION_RE = re.compile(r"^[0-9.]{1,20}$")
COMM_RE = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")
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


def _validate_app_root(path: Path) -> Path:
    if not path.is_absolute():
        raise AuditInputError("app_root_must_be_absolute")
    try:
        root = path.resolve(strict=True)
    except OSError as exc:
        raise AuditInputError("app_root_unreadable") from exc
    if root == Path("/") or not root.is_dir() or not (root / "manage.py").is_file():
        raise AuditInputError("app_root_missing_manage_py")
    return root


def _run_json_command(command: list[str], *, cwd: Path, timeout: float) -> dict:
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise AuditInputError("selector_command_unavailable") from exc
    if result.returncode != 0:
        # Never forward selector stderr: it may include environment details.
        raise AuditInputError(f"selector_command_failed_rc_{result.returncode}")
    if len(result.stdout) > MAX_SELECTOR_BYTES:
        raise AuditInputError("selector_output_too_large")
    try:
        payload = json.loads(result.stdout.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise AuditInputError("selector_output_invalid_json") from exc
    if not isinstance(payload, dict):
        raise AuditInputError("selector_output_invalid_shape")
    return payload


def _find_selector_application(payload: dict, expected_app_root: str) -> dict:
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
        for user_payload in users.values():
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
        "version": safe_version,
        "app_status": app_status,
        "lsapi": lsapi,
    }


def _read_status(proc_dir: Path) -> dict[str, str]:
    try:
        lines = (proc_dir / "status").read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise AuditInputError("process_status_unreadable") from exc
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


def _read_comm(proc_dir: Path) -> str:
    try:
        return _safe_comm((proc_dir / "comm").read_text(encoding="utf-8").strip())
    except OSError as exc:
        raise AuditInputError("process_comm_unreadable") from exc


def _read_memory(proc_dir: Path) -> dict[str, int]:
    try:
        lines = (proc_dir / "smaps_rollup").read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise AuditInputError("process_memory_unreadable") from exc
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


def _read_lsapi_environ(proc_dir: Path) -> dict[str, str]:
    try:
        payload = (proc_dir / "environ").read_bytes()
    except OSError as exc:
        raise AuditInputError("lswsgi_environ_unreadable") from exc
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


def _fd_references(proc_dir: Path, target: os.stat_result) -> bool:
    fd_dir = proc_dir / "fd"
    try:
        descriptors = list(fd_dir.iterdir())
    except OSError:
        return False
    for descriptor in descriptors:
        try:
            observed = descriptor.stat()
        except OSError:
            continue
        if observed.st_dev == target.st_dev and observed.st_ino == target.st_ino:
            return True
    return False


def _scan_processes(proc_root: Path, *, uid: int, lock_paths: dict[str, Path]) -> dict:
    if not proc_root.is_absolute() or not proc_root.is_dir():
        raise AuditInputError("proc_root_unreadable")
    lock_stats = {}
    for name, path in lock_paths.items():
        try:
            lock_stats[name] = path.stat()
        except OSError as exc:
            raise AuditInputError(f"{name}_lock_unreadable") from exc

    processes = []
    vanished = 0
    unreadable_same_uid = []
    for entry in sorted(proc_root.iterdir(), key=lambda item: item.name):
        if not entry.name.isdigit() or not entry.is_dir():
            continue
        pid = int(entry.name)
        try:
            status = _read_status(entry)
        except AuditInputError:
            vanished += 1
            continue
        if _real_uid(status) != uid:
            # Do not inspect comm, memory, environ, fd or command data for
            # another account.
            continue
        try:
            comm = _read_comm(entry)
            memory = _read_memory(entry)
        except AuditInputError:
            unreadable_same_uid.append(pid)
            continue
        locks = [
            name
            for name, lock_stat in lock_stats.items()
            if _fd_references(entry, lock_stat)
        ]
        process = {
            "pid": pid,
            "ppid": _ppid(status),
            "comm": comm,
            "memory": memory,
            "locks": locks,
        }
        if comm == "lswsgi":
            process["lsapi"] = _read_lsapi_environ(entry)
        processes.append(process)

    if not processes:
        raise AuditInputError("same_uid_processes_missing")
    return {
        "processes": processes,
        "vanished_during_scan": vanished,
        "unreadable_same_uid_pids": unreadable_same_uid,
    }


def _sum_memory(processes: list[dict]) -> dict[str, int]:
    return {
        key: sum(process["memory"][key] for process in processes)
        for key in ("rss_kib", "pss_kib", "private_kib")
    }


def _load_supervisor_state(app_root: Path) -> dict:
    path = app_root / "tmp" / "ig_bot_supervisor_state.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AuditInputError("supervisor_state_unreadable") from exc
    if not isinstance(payload, dict):
        raise AuditInputError("supervisor_state_invalid")
    return payload


def _read_daemon_pid(app_root: Path) -> int:
    try:
        return _safe_int(
            (app_root / "tmp" / "ig_bot.pid").read_text(encoding="ascii").strip(),
            label="daemon_pid",
            minimum=1,
        )
    except OSError as exc:
        raise AuditInputError("daemon_pid_unreadable") from exc


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
        app_root = _validate_app_root(Path(args.app_root))
        proc_root = Path(args.proc_root)
        uid = _safe_int(args.uid, label="uid")
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
        selector = _find_selector_application(
            selector_payload,
            str(args.selector_app_root),
        )
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
        scan = _scan_processes(proc_root, uid=uid, lock_paths=lock_paths)
        processes = scan["processes"]
        _check(
            checks,
            "same_uid_processes_readable",
            not scan["unreadable_same_uid_pids"],
            scan["unreadable_same_uid_pids"],
            [],
        )
        lswsgi = [process for process in processes if process["comm"] == "lswsgi"]
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
            name: [process["pid"] for process in processes if name in process["locks"]]
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
        _check(
            checks,
            "supervisor_state_pid",
            holders["supervisor"] == [state_supervisor_pid],
            holders["supervisor"],
            [state_supervisor_pid],
        )
        _check(
            checks,
            "daemon_state_pid",
            holders["daemon"] == [state_child_pid] and daemon_pid == state_child_pid,
            {"lock_holders": holders["daemon"], "pid_file": daemon_pid},
            {"lock_holders": [state_child_pid], "pid_file": state_child_pid},
        )

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
                "vanished_during_scan": scan["vanished_during_scan"],
                "unreadable_same_uid_pids": scan["unreadable_same_uid_pids"],
                "lswsgi": {
                    "master_count": len(masters),
                    "child_count": len(children),
                    "master_pids": sorted(process["pid"] for process in masters),
                    "child_pids": sorted(process["pid"] for process in children),
                    "lsapi": runtime_env_sets,
                    "memory": _sum_memory(lswsgi),
                },
                "locks": holders,
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
    parser.add_argument("--uid", type=int, default=os.getuid())
    parser.add_argument("--timeout", type=float, default=10.0)
    return parser


def main(argv=None) -> int:
    args = _build_parser().parse_args(argv)
    payload, exit_code = audit_capacity(args)
    print(json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
