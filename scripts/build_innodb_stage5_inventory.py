#!/usr/bin/env python3
"""Build a sanitized, read-only Stage 5 engine inventory and ranking report.

The command consumes an allowlisted JSON export from a MariaDB read-only
preflight. It never opens a database connection and never emits row contents.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


MAX_CANARY_ROWS = 1_000
MAX_CANARY_BYTES = 16 * 1024 * 1024
SAFE_ROLLBACK_METHODS = {"maintenance_window", "dual_write", "replica_switchover", "reverse_sync"}


def _is_dtf(name: str) -> bool:
    value = name.casefold()
    return value == "dtf" or value.startswith("dtf_") or value.startswith("dtf.")


def _clean_table(raw: dict[str, Any]) -> dict[str, Any]:
    name = str(raw.get("name", "")).strip()
    engine = str(raw.get("engine", "unknown")).strip()
    if not name or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_." for char in name):
        raise ValueError(f"invalid table name: {name!r}")
    return {
        "name": name,
        "engine": engine,
        "rows": int(raw.get("rows", 0)),
        "data_length": int(raw.get("data_length", 0)),
        "index_length": int(raw.get("index_length", 0)),
        "criticality": str(raw.get("criticality", "unknown")),
        "writers": int(raw.get("writers", 0)),
        "triggers": int(raw.get("triggers", 0)),
    }


def _dependency_order(names: list[str], foreign_keys: list[dict[str, str]]) -> list[str]:
    known = set(names)
    edges = {name: set() for name in names}
    indegree = {name: 0 for name in names}
    for relation in foreign_keys:
        parent = relation.get("parent", "")
        child = relation.get("child", "")
        if parent not in known or child not in known:
            raise ValueError(f"foreign key references unknown table: {parent!r}->{child!r}")
        if child not in edges[parent]:
            edges[parent].add(child)
            indegree[child] += 1
    ready = sorted(name for name, degree in indegree.items() if degree == 0)
    order: list[str] = []
    while ready:
        current = ready.pop(0)
        order.append(current)
        for child in sorted(edges[current]):
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.append(child)
                ready.sort()
    if len(order) != len(names):
        raise ValueError("foreign-key graph contains a cycle")
    return order


def _validate_rollback(raw: dict[str, Any]) -> dict[str, Any]:
    method = str(raw.get("method", "")).strip()
    if method not in SAFE_ROLLBACK_METHODS:
        raise ValueError("backup-only rollback is unsafe; require maintenance_window, dual_write, replica_switchover, or reverse_sync")
    if not bool(raw.get("backup_verified")):
        raise ValueError("rollback requires a verified backup")
    if method == "maintenance_window" and not bool(raw.get("write_freeze")):
        raise ValueError("maintenance-window rollback requires an explicit write freeze")
    if method in {"dual_write", "replica_switchover", "reverse_sync"} and not bool(raw.get("reverse_sync")):
        raise ValueError("online rollback requires explicit reverse-sync/reconciliation")
    return {"method": method, "backup_verified": True, "write_loss_safe": True}


def build_report(payload: dict[str, Any]) -> dict[str, Any]:
    tables = [_clean_table(row) for row in payload.get("tables", [])]
    tables = [row for row in tables if not _is_dtf(row["name"])]
    names = [row["name"] for row in tables]
    if len(names) != len(set(names)):
        raise ValueError("duplicate table name")
    foreign_keys = [
        {"parent": str(item.get("parent", "")), "child": str(item.get("child", ""))}
        for item in payload.get("foreign_keys", [])
    ]
    order = _dependency_order(names, foreign_keys)
    linked = {name for relation in foreign_keys for name in (relation["parent"], relation["child"])}
    candidates = [
        row for row in tables
        if row["engine"].casefold() == "myisam"
        and row["rows"] <= MAX_CANARY_ROWS
        and row["data_length"] + row["index_length"] <= MAX_CANARY_BYTES
        and row["criticality"].casefold() == "low"
        and row["writers"] == 0
        and row["triggers"] == 0
        and row["name"] not in linked
    ]
    candidates.sort(key=lambda row: (row["rows"], row["data_length"] + row["index_length"], row["name"]))
    rollback = _validate_rollback(dict(payload.get("rollback", {})))
    return {
        "schema": 1,
        "database": str(payload.get("database", "unknown")),
        "dtf_scope": "excluded",
        "tables": tables,
        "dependency_order": order,
        "selected_canary": candidates[0] if candidates else None,
        "canary_status": "eligible" if candidates else "blocked_no_proven_candidate",
        "rollback": rollback,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="sanitized JSON inventory")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = build_report(json.loads(args.input.read_text(encoding="utf-8")))
    rendered = json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
