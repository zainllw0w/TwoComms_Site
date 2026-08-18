#!/usr/bin/env python3
"""Fail-closed Stage 6 budget and no-send canary evidence gate.

The script reads an operator-provided, sanitized snapshot. It never opens a
database connection, runs a task, changes cron, or starts a worker.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


MIN_LAUNCHER_PROCESSES = 3
MAX_SNAPSHOT_AGE = timedelta(hours=24)


class GateError(ValueError):
    """Evidence does not establish a safe bounded worker budget."""


def _required_object(value: Any, key: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise GateError(f"{key} must be an object")
    return value


def _integer(value: Any, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise GateError(f"{path} must be a non-negative integer")
    return value


def _non_dtf(value: Any, path: str) -> None:
    if isinstance(value, str) and value.lower() != "non-dtf" and "dtf" in value.lower():
        raise GateError(f"DTF scope is forbidden ({path})")


def _load(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GateError(f"cannot load {label}: {exc}") from exc
    return _required_object(value, label)


def _assert_no_send_canary(policy: dict[str, Any], repo_root: Path) -> None:
    canary = _required_object(policy.get("canary"), "policy.canary")
    if canary.get("task") != "task_runtime.tasks.no_send_canary":
        raise GateError("canary task must be task_runtime.tasks.no_send_canary")
    if canary.get("payload_keys") != ["marker"] or canary.get("external_io") is not False:
        raise GateError("canary must have marker-only, external_io=false contract")
    source_path = repo_root / "twocomms/task_runtime/tasks.py"
    try:
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    except (OSError, SyntaxError) as exc:
        raise GateError(f"cannot inspect canary source: {exc}") from exc
    forbidden_modules = {"requests", "httpx", "urllib", "socket", "smtplib", "boto3"}
    forbidden_calls = {"enqueue", "aenqueue", "delay", "save", "create", "update", "delete"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(alias.name.split(".")[0] in forbidden_modules for alias in node.names):
                raise GateError("canary source imports a forbidden network module")
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".")[0] in forbidden_modules:
                raise GateError("canary source imports a forbidden network module")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in forbidden_calls:
                raise GateError("canary source calls forbidden network, enqueue, or persistence API")
    matching = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "no_send_canary"
    ]
    if len(matching) != 1 or isinstance(matching[0], ast.AsyncFunctionDef):
        raise GateError("canary source must define exactly one synchronous no_send_canary")
    function = matching[0]
    args = function.args
    if (
        args.posonlyargs
        or args.args
        or args.vararg
        or args.kwarg
        or len(args.kwonlyargs) != 1
        or args.kwonlyargs[0].arg != "marker"
        or args.kw_defaults != [None]
    ):
        raise GateError("canary source must use only a keyword-only marker argument")
    body = list(function.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
        body.pop(0)
    if len(body) != 1 or not isinstance(body[0], ast.Return) or not isinstance(body[0].value, ast.Dict):
        raise GateError("canary body must be a strict pure marker return")
    returned = body[0].value
    keys = [key.value if isinstance(key, ast.Constant) else None for key in returned.keys]
    if keys != ["external_io", "marker"] or len(returned.values) != 2:
        raise GateError("canary body must return only external_io and marker")
    external_io, marker = returned.values
    if not isinstance(external_io, ast.Constant) or external_io.value is not False:
        raise GateError("canary body must return external_io=false")
    if not isinstance(marker, ast.Name) or marker.id != "marker":
        raise GateError("canary body must return the marker without helpers")


def _assert_snapshot_metadata(snapshot: dict[str, Any]) -> None:
    captured_at = snapshot.get("captured_at")
    if not isinstance(captured_at, str) or not captured_at.strip():
        raise GateError("snapshot.captured_at is required")
    try:
        parsed = datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise GateError("snapshot.captured_at must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise GateError("snapshot.captured_at must include a timezone")
    age = datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)
    if age < timedelta(minutes=-5) or age > MAX_SNAPSHOT_AGE:
        raise GateError("snapshot.captured_at is outside the 24-hour freshness window")

    provenance = _required_object(snapshot.get("provenance"), "snapshot.provenance")
    if provenance.get("source") != "cloudlinux-bound-python" or provenance.get("kind") != "read-only":
        raise GateError("snapshot.provenance must identify a CloudLinux-bound read-only probe")
    runtime = _required_object(snapshot.get("runtime"), "snapshot.runtime")
    if runtime.get("cloudlinux_bound") is not True:
        raise GateError("snapshot.runtime must prove cloudlinux_bound=true")
    if runtime.get("python") != "3.14.6" or runtime.get("django") != "6.1":
        raise GateError("snapshot.runtime must prove Python 3.14.6 and Django 6.1")
    database = _required_object(snapshot.get("database"), "snapshot.database")
    if database.get("engine") != "django.db.backends.mysql":
        raise GateError("snapshot.database must use the Django MySQL backend")
    if isinstance(database.get("conn_max_age"), bool) or database.get("conn_max_age") != 0:
        raise GateError("snapshot.database must prove CONN_MAX_AGE=0")


def verify(policy: dict[str, Any], snapshot: dict[str, Any], *, repo_root: Path) -> dict[str, Any]:
    _non_dtf(policy.get("scope"), "policy.scope")
    _non_dtf(snapshot.get("scope"), "snapshot.scope")
    if policy.get("schema_version") != 1 or policy.get("scope") != "non-dtf":
        raise GateError("policy must declare schema_version=1 and scope=non-dtf")
    if snapshot.get("schema_version") != 1 or snapshot.get("scope") != "non-dtf":
        raise GateError("snapshot must declare schema_version=1 and scope=non-dtf")
    _assert_snapshot_metadata(snapshot)

    worker = _required_object(policy.get("worker"), "policy.worker")
    reserve = _required_object(policy.get("reserve"), "policy.reserve")
    worker_connections = _integer(worker.get("connections"), "policy.worker.connections")
    worker_fds = _integer(worker.get("fds"), "policy.worker.fds")
    worker_processes = _integer(worker.get("processes"), "policy.worker.processes")
    reserve_connections = _integer(reserve.get("connections"), "policy.reserve.connections")
    reserve_fds = _integer(reserve.get("fds"), "policy.reserve.fds")
    reserve_processes = _integer(reserve.get("processes"), "policy.reserve.processes")
    if min(worker_connections, worker_fds, worker_processes) < 1:
        raise GateError("worker budget must reserve at least one connection, FD, and process")
    if worker_processes < MIN_LAUNCHER_PROCESSES:
        raise GateError("worker budget must reserve three processes for flock, timeout, and Python")

    mysql = _required_object(snapshot.get("mysql"), "snapshot.mysql")
    fd = _required_object(snapshot.get("fd"), "snapshot.fd")
    process = _required_object(snapshot.get("process"), "snapshot.process")
    max_connections = _integer(mysql.get("max_user_connections"), "snapshot.mysql.max_user_connections")
    current_connections = _integer(mysql.get("account_current_connections"), "snapshot.mysql.account_current_connections")
    fd_limit = _integer(fd.get("soft_limit"), "snapshot.fd.soft_limit")
    current_fds = _integer(fd.get("account_open_fds"), "snapshot.fd.account_open_fds")
    process_limit = _integer(process.get("soft_limit"), "snapshot.process.soft_limit")
    current_processes = _integer(process.get("account_current_processes"), "snapshot.process.account_current_processes")

    db_headroom = max_connections - current_connections - worker_connections
    fd_headroom = fd_limit - current_fds - worker_fds
    process_headroom = process_limit - current_processes - worker_processes
    if db_headroom < reserve_connections:
        raise GateError("MariaDB account connection budget has insufficient worker headroom")
    if fd_headroom < reserve_fds:
        raise GateError("FD budget has insufficient worker headroom")
    if process_headroom < reserve_processes:
        raise GateError("process budget has insufficient worker headroom")
    _assert_no_send_canary(policy, repo_root)
    return {
        "status": "ok",
        "scope": "non-dtf",
        "budget": {
            "db_headroom_after": db_headroom,
            "fd_headroom_after": fd_headroom,
            "process_headroom_after": process_headroom,
            "worker": worker,
            "reserve": reserve,
        },
        "canary": {"task": policy["canary"]["task"], "execution": "not-run; static contract only"},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    try:
        result = verify(_load(args.policy, "policy"), _load(args.snapshot, "snapshot"), repo_root=args.repo_root)
    except GateError as exc:
        print(f"stage6-task-budget: FAIL: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
