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
SAFE_ROLLBACK_METHODS = {
    "maintenance_window",
    "dual_write",
    "replica_switchover",
    "reverse_sync",
}


def _is_dtf(name: str) -> bool:
    value = name.casefold()
    return value == "dtf" or value.startswith("dtf_") or value.startswith("dtf.")


def _nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a non-negative integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a non-negative integer") from exc
    if parsed < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return parsed


def _clean_table(raw: dict[str, Any]) -> dict[str, Any]:
    name = str(raw.get("name", "")).strip()
    engine = str(raw.get("engine", "unknown")).strip()
    model = str(raw.get("model", "unknown")).strip()
    if not name or any(
        char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_."
        for char in name
    ):
        raise ValueError(f"invalid table name: {name!r}")
    if _is_dtf(name) or _is_dtf(model):
        raise ValueError("DTF scope is forbidden")
    if not engine:
        raise ValueError(f"missing engine for {name!r}")
    data_length = _nonnegative_int(raw.get("data_length", 0), "data_length")
    index_length = _nonnegative_int(raw.get("index_length", 0), "index_length")
    orphan_scan_complete = raw.get("orphan_scan_complete", False)
    if not isinstance(orphan_scan_complete, bool):
        raise ValueError("orphan_scan_complete must be a boolean")
    orphan_count = (
        _nonnegative_int(raw.get("orphan_count", 0), "orphan_count")
        if orphan_scan_complete
        else None
    )
    writer_audit_complete = raw.get("writer_audit_complete", False)
    if not isinstance(writer_audit_complete, bool):
        raise ValueError("writer_audit_complete must be a boolean")
    writers = (
        _nonnegative_int(raw.get("writers", 0), "writers")
        if writer_audit_complete
        else None
    )
    supplied_risk = str(raw.get("risk", "")).strip()
    if (
        engine.casefold() == "myisam"
        and not writer_audit_complete
        and not orphan_scan_complete
    ):
        risk = "unmeasured_writer_and_orphan_risk"
    elif engine.casefold() == "myisam" and not orphan_scan_complete:
        risk = "unmeasured_orphan_risk"
    elif engine.casefold() == "myisam" and not writer_audit_complete:
        risk = "unmeasured_writer_risk"
    elif supplied_risk:
        risk = supplied_risk
    elif engine.casefold() == "myisam":
        risk = "unclassified"
    else:
        risk = "not_target"
    return {
        "name": name,
        "model": model,
        "engine": engine,
        "rows": _nonnegative_int(raw.get("rows", 0), "rows"),
        "data_length": data_length,
        "index_length": index_length,
        "size_bytes": data_length + index_length,
        "criticality": str(raw.get("criticality", "unknown")),
        "writer_audit_complete": writer_audit_complete,
        "writers": writers,
        "triggers": _nonnegative_int(raw.get("triggers", 0), "triggers"),
        "orphan_scan_complete": orphan_scan_complete,
        "orphan_count": orphan_count,
        "risk": risk,
        "fulltext_indexes": _nonnegative_int(
            raw.get("fulltext_indexes", 0), "fulltext_indexes"
        ),
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
    database_alias = str(payload.get("database", "")).strip()
    if database_alias != "default" or _is_dtf(database_alias):
        raise ValueError("only the sanitized non-DTF default alias is allowed")
    tables = [_clean_table(row) for row in payload.get("tables", [])]
    if not tables:
        raise ValueError("table inventory is empty")
    names = [row["name"] for row in tables]
    if len(names) != len(set(names)):
        raise ValueError("duplicate table name")
    foreign_keys = [
        {"parent": str(item.get("parent", "")), "child": str(item.get("child", ""))}
        for item in payload.get("foreign_keys", [])
    ]
    declared_dependencies = [
        {
            "parent": str(item.get("before", "")),
            "child": str(item.get("after", "")),
        }
        for item in payload.get("dependencies", [])
    ]
    order = _dependency_order(names, foreign_keys + declared_dependencies)
    migration_positions = {name: index for index, name in enumerate(order, start=1)}
    for table in tables:
        table["migration_order"] = migration_positions[table["name"]]
    linked = {
        name
        for relation in foreign_keys + declared_dependencies
        for name in (relation["parent"], relation["child"])
    }
    candidates = [
        row for row in tables
        if row["engine"].casefold() == "myisam"
        and row["rows"] <= MAX_CANARY_ROWS
        and row["size_bytes"] <= MAX_CANARY_BYTES
        and row["criticality"].casefold() == "low"
        and row["model"].casefold() != "unknown"
        and row["writer_audit_complete"]
        and row["writers"] == 0
        and row["triggers"] == 0
        and row["orphan_scan_complete"]
        and row["orphan_count"] == 0
        and row["fulltext_indexes"] == 0
        and row["name"] not in linked
    ]
    candidates.sort(key=lambda row: (row["rows"], row["size_bytes"], row["name"]))
    rollback = _validate_rollback(dict(payload.get("rollback", {})))
    return {
        "schema": 1,
        "database_alias": database_alias,
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
