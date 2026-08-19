#!/usr/bin/env python3
"""Run the fail-closed Django 6.1 migration-squash rehearsal.

The command deliberately proves only a disposable SQLite clean install and
restore.  It never invokes ``squashmigrations`` and never edits or removes a
historical migration.  A successful run therefore reports a reproducible
non-DTF graph plus an explicit ``no-go`` decision until authoritative
production applied-history and a disposable MariaDB rehearsal are supplied by
an owner of that environment.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from typing import Any, Iterable, Mapping



ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = ROOT / "twocomms"
SETTINGS = "test_settings_migrations_non_dtf"
DTF_STUB_PREFIX = "test_support.dtf_stub"
MARIADB_SETTINGS = "test_settings_mariadb"
AUTHORITATIVE_HISTORY_EVIDENCE = (
    ROOT / "docs" / "qa" / "django61-stage5-mig001-production-history.json"
)
COMMAND_TIMEOUT_SECONDS = 30 * 60
MARIADB_DATABASE_RE = re.compile(
    r"^test_twocomms_mig_(?:clean|restore)_[a-f0-9]{12}$"
)
MARIADB_DUMP_OPTIONS = (
    "--routines",
    "--triggers",
    "--events",
)
MARIADB_SCHEMA_METADATA_SCOPE = (
    "tables",
    "columns",
    "indexes",
    "constraints",
    "checks",
    "foreign_keys",
    "triggers",
    "routines",
    "events",
)
SENSITIVE_ENV_MARKERS = (
    "TOKEN",
    "SECRET",
    "PASSWORD",
    "DATABASE_URL",
    "DB_",
    "API_KEY",
    "ACCESS_KEY",
    "ACCESS_TOKEN",
    "PRIVATE_KEY",
    "CREDENTIAL",
)


class GateFailure(RuntimeError):
    """A deterministic, user-actionable gate failure."""


def _mariadb_components():
    """Import the shared disposable MariaDB lifecycle only when requested."""

    try:
        from scripts import run_mariadb_gate
    except ModuleNotFoundError:
        # Direct ``python scripts/<runner>.py`` execution puts only the scripts
        # directory on sys.path.  Add the repository root for the shared gate
        # without changing the worker's sanitized environment.
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from scripts import run_mariadb_gate
    return run_mariadb_gate


MARIADB_VENDORS = frozenset({"mysql", "mariadb"})


def _require_mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise GateFailure(f"{name}_missing")
    return value


def _require_sha256(value: Any, name: str) -> str:
    normalized = str(value or "").strip().lower()
    if len(normalized) != 64 or any(
        character not in "0123456789abcdef" for character in normalized
    ):
        raise GateFailure(f"{name}_missing_or_invalid")
    return normalized


def _require_int(value: Any, name: str, *, minimum: int | None = None) -> int:
    try:
        normalized = int(value)
    except (TypeError, ValueError) as exc:
        raise GateFailure(f"{name}_missing_or_invalid") from exc
    if minimum is not None and normalized < minimum:
        raise GateFailure(f"{name}_missing_or_invalid")
    return normalized


def validate_authoritative_applied_history(
    evidence: Mapping[str, Any],
) -> None:
    """Validate sanitized, read-only migration history from the authority.

    The gate intentionally accepts facts, not credentials or a live connection.
    ``authoritative`` and ``read_only`` are explicit so a copied local SQLite
    report cannot be mistaken for production history.
    """

    evidence = _require_mapping(evidence, "authoritative_applied_history")
    if evidence.get("status") != "passed":
        raise GateFailure("authoritative_applied_history_not_passed")
    if evidence.get("authoritative") is not True:
        raise GateFailure("authoritative_applied_history_not_authoritative")
    if evidence.get("read_only") is not True:
        raise GateFailure("authoritative_applied_history_not_read_only")
    vendor = str(evidence.get("database_vendor") or "").strip().casefold()
    if vendor not in MARIADB_VENDORS:
        raise GateFailure("authoritative_applied_history_requires_mariadb")
    if str(evidence.get("database_alias") or "").strip() != "default":
        raise GateFailure("authoritative_applied_history_alias_violation")
    if evidence.get("non_dtf_only") is not True:
        raise GateFailure("authoritative_applied_history_scope_violation")
    if not str(evidence.get("source") or "").strip():
        raise GateFailure("authoritative_applied_history_source_missing")
    if not str(evidence.get("captured_at") or "").strip():
        raise GateFailure("authoritative_applied_history_timestamp_missing")
    if _require_int(evidence.get("pending", -1), "authoritative_pending") != 0:
        raise GateFailure("authoritative_applied_history_pending")
    _require_int(
        evidence.get("applied_history_count", 0),
        "authoritative_applied_history_count",
        minimum=1,
    )
    _require_sha256(
        evidence.get("applied_history_hash"),
        "authoritative_applied_history_hash",
    )
    _require_sha256(
        evidence.get("graph_fingerprint"), "authoritative_graph_fingerprint"
    )


def validate_restore_drill_evidence(evidence: Mapping[str, Any]) -> None:
    """Validate backup, restore-parity and rollback facts for a disposable DB."""

    evidence = _require_mapping(evidence, "restore_drill")
    if evidence.get("status") != "passed":
        raise GateFailure("restore_drill_not_passed")
    if evidence.get("disposable") is not True:
        raise GateFailure("restore_drill_must_be_disposable")
    backup = _require_mapping(evidence.get("backup"), "backup_evidence")
    if backup.get("status") != "passed":
        raise GateFailure("backup_evidence_not_passed")
    if not str(backup.get("artifact_id") or "").strip():
        raise GateFailure("backup_artifact_missing")
    _require_sha256(backup.get("sha256"), "backup_sha256")
    restore = _require_mapping(evidence.get("restore"), "restore_evidence")
    if restore.get("status") != "passed":
        raise GateFailure("restore_evidence_not_passed")
    if restore.get("integrity_check") is not True:
        raise GateFailure("restore_integrity_evidence_missing")
    if restore.get("schema_hash_matches") is not True:
        raise GateFailure("restore_schema_parity_missing")
    if restore.get("applied_history_matches") is not True:
        raise GateFailure("restore_history_parity_missing")
    rollback = _require_mapping(evidence.get("rollback"), "rollback_evidence")
    if rollback.get("status") != "passed" or rollback.get("verified") is not True:
        raise GateFailure("rollback_evidence_missing")


def validate_mariadb_rehearsal_evidence(
    evidence: Mapping[str, Any],
) -> None:
    """Validate clean-install/replay facts on a production-compatible MariaDB."""

    evidence = _require_mapping(evidence, "mariadb_rehearsal")
    if evidence.get("status") != "passed":
        raise GateFailure("mariadb_rehearsal_not_passed")
    vendor = str(evidence.get("database_vendor") or "").strip().casefold()
    if vendor not in MARIADB_VENDORS:
        raise GateFailure("mariadb_rehearsal_requires_mariadb")
    if evidence.get("production_compatible") is not True:
        raise GateFailure("mariadb_rehearsal_compatibility_missing")
    server_version = str(evidence.get("server_version") or "").strip()
    if not server_version:
        raise GateFailure("mariadb_rehearsal_version_missing")
    if "mariadb" not in server_version.casefold():
        raise GateFailure("mariadb_rehearsal_requires_mariadb_server")
    if evidence.get("disposable") is not True:
        raise GateFailure("mariadb_rehearsal_must_be_disposable")
    cleanup = _require_mapping(evidence.get("cleanup"), "mariadb_cleanup")
    if cleanup.get("status") != "verified":
        raise GateFailure("mariadb_cleanup_not_verified")
    for field in (
        "generated_databases_absent",
        "generated_user_absent",
        "temporary_dump_removed",
        "mariadb_process_closed",
    ):
        if cleanup.get(field) is not True:
            raise GateFailure(f"mariadb_cleanup_{field}_missing")
    metadata_scope = _require_mapping(
        evidence.get("schema_metadata_scope"), "mariadb_schema_metadata_scope"
    )
    if tuple(metadata_scope.get("includes") or ()) != MARIADB_SCHEMA_METADATA_SCOPE:
        raise GateFailure("mariadb_schema_metadata_scope_incomplete")
    if tuple(metadata_scope.get("dump_options") or ()) != MARIADB_DUMP_OPTIONS:
        raise GateFailure("mariadb_dump_scope_incomplete")
    clean_install = _require_mapping(
        evidence.get("clean_install"), "mariadb_clean_install"
    )
    if clean_install.get("status") != "passed" or _require_int(
        clean_install.get("pending", -1), "mariadb_clean_install_pending"
    ) != 0:
        raise GateFailure("mariadb_clean_install_pending")
    replay = _require_mapping(evidence.get("replay"), "mariadb_replay")
    if replay.get("status") != "passed" or _require_int(
        replay.get("pending", -1), "mariadb_replay_pending"
    ) != 0:
        raise GateFailure("mariadb_replay_pending")
    for label, record in (("clean_install", clean_install), ("replay", replay)):
        database = str(record.get("database") or "").strip()
        if not MARIADB_DATABASE_RE.fullmatch(database):
            raise GateFailure(f"mariadb_{label}_database_invalid")
        for field in ("schema_hash", "applied_history_hash"):
            _require_sha256(record.get(field), f"mariadb_{label}_{field}")
        _require_int(
            record.get("applied_history_count", -1),
            f"mariadb_{label}_applied_history_count",
            minimum=1,
        )
        record_scope = _require_mapping(
            record.get("schema_metadata_scope"),
            f"mariadb_{label}_schema_metadata_scope",
        )
        if tuple(record_scope.get("includes") or ()) != MARIADB_SCHEMA_METADATA_SCOPE:
            raise GateFailure(f"mariadb_{label}_schema_metadata_scope_incomplete")
        if tuple(record_scope.get("dump_options") or ()) != MARIADB_DUMP_OPTIONS:
            raise GateFailure(f"mariadb_{label}_dump_scope_incomplete")
        for field in ("trigger_count", "routine_count", "event_count"):
            _require_int(
                record.get(field, -1), f"mariadb_{label}_{field}", minimum=0
            )
        if dict(record_scope) != dict(metadata_scope):
            raise GateFailure(f"mariadb_{label}_schema_metadata_scope_mismatch")
    if clean_install["database"] == replay["database"]:
        raise GateFailure("mariadb_clean_restore_database_must_differ")
    if clean_install["schema_hash"] != replay["schema_hash"]:
        raise GateFailure("mariadb_replay_schema_hash_mismatch")
    if clean_install["applied_history_hash"] != replay["applied_history_hash"]:
        raise GateFailure("mariadb_replay_history_hash_mismatch")
    if clean_install["applied_history_count"] != replay["applied_history_count"]:
        raise GateFailure("mariadb_replay_history_count_mismatch")
    for field in ("trigger_count", "routine_count", "event_count"):
        if clean_install[field] != replay[field]:
            raise GateFailure(f"mariadb_replay_{field}_mismatch")
    restore_drill = _require_mapping(evidence.get("restore_drill"), "restore_drill")
    restore = _require_mapping(restore_drill.get("restore"), "restore_evidence")
    if str(restore.get("source_database") or "") != clean_install["database"]:
        raise GateFailure("mariadb_restore_source_database_mismatch")
    if str(restore.get("destination_database") or "") != replay["database"]:
        raise GateFailure("mariadb_restore_destination_database_mismatch")
    validate_restore_drill_evidence(restore_drill)


def validate_authoritative_history_compatibility(
    authoritative_evidence: Mapping[str, Any],
    mariadb_evidence: Mapping[str, Any],
    *,
    graph_fingerprint: str,
) -> None:
    """Require an explicit owner review before combining history snapshots.

    A production recorder can legitimately contain replacement/legacy rows that
    are not present in a newer clean-install replay.  Comparing the two hashes
    byte-for-byte would therefore reject a valid identity review, while
    accepting an arbitrary boolean would be unsafe.  The owner must publish a
    sanitized compatibility record tied to the current graph fingerprint.
    """

    authoritative = _require_mapping(
        authoritative_evidence, "authoritative_applied_history"
    )
    rehearsal = _require_mapping(mariadb_evidence, "mariadb_rehearsal")
    compatibility = _require_mapping(
        rehearsal.get("authoritative_history_compatibility"),
        "authoritative_history_compatibility",
    )
    if compatibility.get("status") != "verified":
        raise GateFailure("authoritative_history_compatibility_not_verified")
    if compatibility.get("method") != "migration_identity_set_review":
        raise GateFailure("authoritative_history_compatibility_method_missing")
    if compatibility.get("decision") != "go":
        raise GateFailure("authoritative_history_compatibility_not_approved")
    expected_fingerprint = _require_sha256(
        graph_fingerprint, "expected_graph_fingerprint"
    )
    if _require_sha256(
        compatibility.get("graph_fingerprint"),
        "authoritative_history_compatibility_graph_fingerprint",
    ) != expected_fingerprint:
        raise GateFailure("authoritative_history_compatibility_graph_mismatch")
    if compatibility.get("authoritative_pending") != 0:
        raise GateFailure("authoritative_history_compatibility_pending")
    if _require_int(
        compatibility.get("authoritative_applied_history_count", -1),
        "authoritative_history_compatibility_count",
        minimum=1,
    ) != _require_int(
        authoritative.get("applied_history_count", -1),
        "authoritative_applied_history_count",
        minimum=1,
    ):
        raise GateFailure("authoritative_history_compatibility_count_mismatch")
    if _require_sha256(
        compatibility.get("authoritative_applied_history_hash"),
        "authoritative_history_compatibility_authoritative_hash",
    ) != _require_sha256(
        authoritative.get("applied_history_hash"),
        "authoritative_applied_history_hash",
    ):
        raise GateFailure("authoritative_history_compatibility_hash_mismatch")
    if _require_sha256(
        compatibility.get("authoritative_graph_fingerprint"),
        "authoritative_history_compatibility_authoritative_graph",
    ) != _require_sha256(
        authoritative.get("graph_fingerprint"),
        "authoritative_graph_fingerprint",
    ):
        raise GateFailure("authoritative_history_compatibility_authoritative_graph_mismatch")
    clean_install = _require_mapping(
        rehearsal.get("clean_install"), "mariadb_clean_install"
    )
    if _require_int(
        compatibility.get("current_applied_history_count", -1),
        "authoritative_history_compatibility_current_count",
        minimum=1,
    ) != _require_int(
        clean_install.get("applied_history_count", -1),
        "mariadb_clean_install_applied_history_count",
        minimum=1,
    ):
        raise GateFailure("authoritative_history_compatibility_current_count_mismatch")
    if _require_sha256(
        compatibility.get("current_applied_history_hash"),
        "authoritative_history_compatibility_current_hash",
    ) != _require_sha256(
        clean_install.get("applied_history_hash"),
        "mariadb_clean_install_history_hash",
    ):
        raise GateFailure("authoritative_history_compatibility_current_hash_mismatch")
    if not str(compatibility.get("reviewer") or "").strip():
        raise GateFailure("authoritative_history_compatibility_reviewer_missing")
    if not str(compatibility.get("reviewed_at") or "").strip():
        raise GateFailure("authoritative_history_compatibility_timestamp_missing")


def assess_authoritative_history_snapshot(
    current: Mapping[str, Any],
    *,
    evidence_path: Path = AUTHORITATIVE_HISTORY_EVIDENCE,
) -> dict[str, Any]:
    """Describe why a historical production snapshot cannot authorize GO."""

    try:
        authoritative = json.loads(evidence_path.read_text(encoding="utf-8"))
        validate_authoritative_applied_history(authoritative)
    except (OSError, json.JSONDecodeError, GateFailure):
        return {
            "status": "authoritative_snapshot_missing_or_invalid",
            "decision": "no-go_until_fresh_read_only_identity_set_review",
            "authoritative_artifact": evidence_path.name,
        }

    current_graph = _require_sha256(
        current.get("graph_fingerprint"), "current_graph_fingerprint"
    )
    authoritative_graph = _require_sha256(
        authoritative.get("graph_fingerprint"), "authoritative_graph_fingerprint"
    )
    current_count = _require_int(
        current.get("applied"), "current_applied_history_count", minimum=1
    )
    authoritative_count = _require_int(
        authoritative.get("applied_history_count"),
        "authoritative_applied_history_count",
        minimum=1,
    )
    status = "identity_set_review_required"
    if current_graph != authoritative_graph:
        status = "snapshot_graph_diverged"
    return {
        "status": status,
        "decision": "no-go_until_fresh_read_only_identity_set_review",
        "method_required": "migration_identity_set_review",
        "authoritative_artifact": evidence_path.name,
        "authoritative_captured_at": authoritative["captured_at"],
        "authoritative_graph_fingerprint": authoritative_graph,
        "authoritative_applied_history_count": authoritative_count,
        "authoritative_applied_history_hash": authoritative["applied_history_hash"],
        "graph_fingerprint": current_graph,
        "current_applied_history_count": current_count,
        "current_applied_history_hash": current["applied_history_hash"],
    }


def assert_local_only_environment(environment: dict[str, str] | None = None) -> None:
    """Reject an invocation that is explicitly marked as production."""

    environment = environment if environment is not None else dict(os.environ)
    if environment.get("DJANGO_ENV", "").strip().casefold() == "production":
        raise GateFailure("production_context_forbidden")
    env_file = Path(environment.get("DJANGO_ENV_FILE", ""))
    if env_file.name.casefold() == ".env.production":
        raise GateFailure("production_context_forbidden")


def validate_disposable_database_path(path: Path, temp_root: Path) -> Path:
    """Return a safe SQLite path contained by the gate-owned temp directory."""

    root = Path(temp_root).resolve()
    candidate = Path(path).resolve()
    if not root.is_dir():
        raise GateFailure("temporary_root_missing")
    if candidate.suffix.casefold() != ".sqlite3":
        raise GateFailure("disposable_database_extension_required")
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise GateFailure("disposable_database_outside_temp_root") from exc
    if candidate == root or candidate.parent == root.parent:
        raise GateFailure("disposable_database_path_invalid")
    if Path(path).is_symlink():
        raise GateFailure("disposable_database_symlink_forbidden")
    return candidate


def _is_sensitive_name(name: str) -> bool:
    upper = name.upper()
    return any(
        marker == "DB_" and upper.startswith(marker)
        or marker != "DB_" and marker in upper
        for marker in SENSITIVE_ENV_MARKERS
    )


def safe_worker_environment(
    *,
    database_path: Path,
    temp_root: Path,
    source: dict[str, str] | None = None,
) -> dict[str, str]:
    """Build a scrubbed environment for a local, non-DTF worker process."""

    source = dict(os.environ) if source is None else dict(source)
    assert_local_only_environment(source)
    database = validate_disposable_database_path(database_path, temp_root)
    root = Path(temp_root).resolve()
    environment = {
        name: value
        for name, value in source.items()
        if name not in {"DJANGO_ENV_FILE", "DJANGO_SETTINGS_MODULE"}
        and not _is_sensitive_name(name)
    }
    existing_pythonpath = environment.get("PYTHONPATH", "")
    environment["PYTHONPATH"] = os.pathsep.join(
        path
        for path in (str(APP_ROOT), str(ROOT), existing_pythonpath)
        if path
    )
    environment.update(
        {
            "DJANGO_SETTINGS_MODULE": SETTINGS,
            "DJANGO_ENV": "development",
            "SECRET_KEY": "django61-migration-rehearsal-only",
            "DJANGO61_MIGRATION_REHEARSAL": "1",
            "DJANGO61_MIGRATION_DB_PATH": str(database),
            "DJANGO61_MIGRATION_TEMP_ROOT": str(root),
            "PYTHONUNBUFFERED": "1",
        }
    )
    environment["PYTHONPATH"] = os.pathsep.join(
        path for path in (str(APP_ROOT), str(ROOT)) if path
    )
    return environment


def _hash_lines(lines: Iterable[str]) -> str:
    digest = hashlib.sha256()
    for line in lines:
        digest.update(line.encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def _database_schema_hash(connection: sqlite3.Connection) -> str:
    rows = connection.execute(
        """
        SELECT type, name, tbl_name, COALESCE(sql, '')
        FROM sqlite_master
        WHERE name NOT LIKE 'sqlite_%'
        ORDER BY type, name, tbl_name
        """
    ).fetchall()
    return _hash_lines("|".join(str(value) for value in row) for row in rows)


def _canonical_mariadb_check_clause(value: Any) -> str:
    """Canonicalize a CHECK expression while ignoring dump-generated names."""

    if value is None:
        return ""
    return re.sub(r"\s+", "", str(value)).casefold().replace("`", "")


def _is_auto_json_check_name(
    table: Any,
    constraint_name: Any,
    clause: Any,
    columns: set[tuple[str, str]],
) -> bool:
    """Recognize only MariaDB's column-derived JSON_VALID CHECK aliases.

    MariaDB can rename the generated JSON CHECK during a logical restore (for
    example ``data_new`` to ``data``).  User-named checks remain name-sensitive;
    this predicate is deliberately limited to the exact generated-name forms
    and the corresponding single-column JSON_VALID expression.
    """

    normalized = _canonical_mariadb_check_clause(clause)
    match = re.fullmatch(r"\(*json_valid\(([a-z_][a-z0-9_]*)\)\)*", normalized)
    if not match:
        return False
    table_name = str(table).strip().casefold()
    column_name = match.group(1).casefold()
    if (table_name, column_name) not in columns:
        return False
    name = str(constraint_name or "").strip().casefold()
    return name in {column_name, f"{column_name}_new"}


def _mariadb_schema_rows(
    connection: Any,
) -> tuple[list[str], int, list[str], int, int, int]:
    """Return canonical information_schema metadata for this database."""

    def canonical(value: Any) -> str:
        if value is None:
            return ""
        return " ".join(str(value).split()).strip().casefold()

    rows: list[str] = []
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT TABLE_NAME, ENGINE, TABLE_TYPE, TABLE_COLLATION "
            "FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE() "
            "ORDER BY TABLE_NAME"
        )
        tables = cursor.fetchall()
        rows.extend("table|" + "|".join(canonical(value) for value in row) for row in tables)
        cursor.execute(
            "SELECT TABLE_NAME, COLUMN_NAME, ORDINAL_POSITION, COLUMN_DEFAULT, "
            "IS_NULLABLE, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, NUMERIC_PRECISION, "
            "NUMERIC_SCALE, COLUMN_TYPE, COLUMN_KEY, EXTRA, COLLATION_NAME "
            "FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() "
            "ORDER BY TABLE_NAME, ORDINAL_POSITION"
        )
        column_rows = cursor.fetchall()
        rows.extend("column|" + "|".join(canonical(value) for value in row) for row in column_rows)
        columns = {
            (canonical(row[0]), canonical(row[1])) for row in column_rows
        }
        cursor.execute(
            "SELECT TABLE_NAME, INDEX_NAME, NON_UNIQUE, SEQ_IN_INDEX, COLUMN_NAME, "
            "SUB_PART, INDEX_TYPE FROM information_schema.STATISTICS "
            "WHERE TABLE_SCHEMA = DATABASE() ORDER BY TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX"
        )
        rows.extend("index|" + "|".join(canonical(value) for value in row) for row in cursor.fetchall())
        cursor.execute(
            "SELECT TABLE_NAME, CONSTRAINT_NAME, CONSTRAINT_TYPE "
            "FROM information_schema.TABLE_CONSTRAINTS WHERE TABLE_SCHEMA = DATABASE() "
            "AND CONSTRAINT_TYPE <> 'CHECK' "
            "ORDER BY TABLE_NAME, CONSTRAINT_NAME"
        )
        rows.extend("constraint|" + "|".join(canonical(value) for value in row) for row in cursor.fetchall())
        cursor.execute(
            "SELECT TABLE_NAME, CONSTRAINT_NAME "
            "FROM information_schema.TABLE_CONSTRAINTS WHERE TABLE_SCHEMA = DATABASE() "
            "AND CONSTRAINT_TYPE = 'CHECK' "
            "ORDER BY TABLE_NAME, CONSTRAINT_NAME"
        )
        check_constraint_names: dict[str, list[str]] = {}
        for row in cursor.fetchall():
            if len(row) < 2:
                continue
            check_constraint_names.setdefault(canonical(row[0]), []).append(
                canonical(row[1])
            )
        cursor.execute(
            "SELECT TABLE_NAME, CONSTRAINT_NAME, CHECK_CLAUSE "
            "FROM information_schema.CHECK_CONSTRAINTS "
            "WHERE CONSTRAINT_SCHEMA = DATABASE() "
            "ORDER BY TABLE_NAME, CONSTRAINT_NAME, CHECK_CLAUSE"
        )
        for row in cursor.fetchall():
            if len(row) >= 3:
                table, name, clause = row[0], row[1], row[2]
            elif len(row) == 2:
                table, clause = row
                names = check_constraint_names.get(canonical(table), [])
                name = names[0] if len(names) == 1 else ""
            else:
                continue
            rows.append(
                "check|" + canonical(table) + "|"
                + (
                    "<mariadb-auto-json>"
                    if _is_auto_json_check_name(table, name, clause, columns)
                    else canonical(name)
                )
                + "|" + _canonical_mariadb_check_clause(clause)
            )
        cursor.execute(
            "SELECT TABLE_NAME, CONSTRAINT_NAME, REFERENCED_TABLE_NAME, "
            "REFERENCED_COLUMN_NAME "
            "FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA = DATABASE() "
            "AND REFERENCED_TABLE_NAME IS NOT NULL "
            "ORDER BY TABLE_NAME, CONSTRAINT_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME"
        )
        rows.extend("foreign_key|" + "|".join(canonical(value) for value in row) for row in cursor.fetchall())
        cursor.execute(
            "SELECT TRIGGER_NAME, EVENT_OBJECT_TABLE, EVENT_MANIPULATION, "
            "ACTION_TIMING, ACTION_ORDER, ACTION_STATEMENT, ACTION_ORIENTATION, "
            "ACTION_CONDITION FROM information_schema.TRIGGERS "
            "WHERE TRIGGER_SCHEMA = DATABASE() "
            "ORDER BY TRIGGER_NAME"
        )
        trigger_rows = cursor.fetchall()
        for row in trigger_rows:
            values = [canonical(value) for value in row]
            for index in (5, 7):
                if index < len(row):
                    values[index] = " ".join(str(row[index] or "").split()).strip()
            rows.append("trigger|" + "|".join(values))
        cursor.execute(
            "SELECT ROUTINE_NAME, ROUTINE_TYPE, DATA_TYPE, DTD_IDENTIFIER, "
            "ROUTINE_DEFINITION, IS_DETERMINISTIC, SQL_DATA_ACCESS, ROUTINE_BODY "
            "FROM information_schema.ROUTINES "
            "WHERE ROUTINE_SCHEMA = DATABASE() "
            "ORDER BY ROUTINE_NAME, ROUTINE_TYPE"
        )
        routine_rows = cursor.fetchall()
        for row in routine_rows:
            values = [canonical(value) for value in row]
            if len(row) > 4:
                values[4] = " ".join(str(row[4] or "").split()).strip()
            rows.append("routine|" + "|".join(values))
        cursor.execute(
            "SELECT EVENT_NAME, EVENT_DEFINITION, EVENT_TYPE, EXECUTE_AT, "
            "INTERVAL_VALUE, INTERVAL_FIELD, STATUS, EVENT_BODY, ON_COMPLETION "
            "FROM information_schema.EVENTS "
            "WHERE EVENT_SCHEMA = DATABASE() "
            "ORDER BY EVENT_NAME"
        )
        event_rows = cursor.fetchall()
        for row in event_rows:
            values = [canonical(value) for value in row]
            for index in (1, 7):
                if index < len(row):
                    values[index] = " ".join(str(row[index] or "").split()).strip()
            rows.append("event|" + "|".join(values))
    rows.sort()
    dtf_tables = sorted(
        str(row[0]) for row in tables if str(row[0]).casefold().startswith("dtf_")
    )
    return rows, len(tables), dtf_tables, len(trigger_rows), len(routine_rows), len(event_rows)


def _mariadb_schema_hash(connection: Any) -> tuple[str, int, list[str], int, int, int]:
    """Hash only canonical information_schema metadata for this database."""

    rows, table_count, dtf_tables, trigger_count, routine_count, event_count = (
        _mariadb_schema_rows(connection)
    )
    return (
        _hash_lines(rows),
        table_count,
        dtf_tables,
        trigger_count,
        routine_count,
        event_count,
    )


def _create_owned_mariadb_database(
    admin: Any, database: str, attempted: dict[str, bool]
) -> None:
    """Record ownership before CREATE so ambiguous failures are cleaned up."""

    attempted[database] = True
    admin.create_database(database)


def _restore_sqlite(source: Path, destination: Path, *, temp_root: Path) -> None:
    source = validate_disposable_database_path(source, temp_root)
    destination = validate_disposable_database_path(destination, temp_root)
    if not source.is_file():
        raise GateFailure("restore_source_missing")
    if destination.exists() or destination.is_symlink():
        raise GateFailure("restore_destination_must_be_new")

    source_connection = sqlite3.connect(source)
    destination_connection = sqlite3.connect(destination)
    try:
        source_connection.backup(destination_connection)
        destination_connection.commit()
        integrity = destination_connection.execute("PRAGMA integrity_check").fetchone()
        if integrity != ("ok",):
            raise GateFailure("restore_integrity_check_failed")
    finally:
        destination_connection.close()
        source_connection.close()
    destination.chmod(0o600)


def restore_sqlite(source: Path, destination: Path, *, temp_root: Path) -> None:
    """Public wrapper used by tests and the rehearsal runner."""

    _restore_sqlite(source, destination, temp_root=temp_root)


def _migration_operation_flags(migration: Any) -> tuple[int, int, int]:
    data_or_sql = 0
    irreversible = 0
    elidable = 0
    for operation in getattr(migration, "operations", ()):
        operation_name = type(operation).__name__
        if operation_name in {"RunPython", "RunSQL", "SeparateDatabaseAndState"}:
            data_or_sql += 1
        if not getattr(operation, "reversible", True):
            irreversible += 1
        if getattr(operation, "elidable", False):
            elidable += 1
    return data_or_sql, irreversible, elidable


def _project_app_labels(apps: Any) -> set[str]:
    labels: set[str] = set()
    for config in apps.get_app_configs():
        if config.label.casefold() == "dtf":
            continue
        try:
            config_path = Path(config.module.__file__).resolve().parent
            config_path.relative_to(APP_ROOT)
        except (AttributeError, ValueError):
            continue
        if "test_support" in config_path.parts:
            continue
        labels.add(config.label)
    return labels


def _probe_database() -> dict[str, Any]:
    """Load Django's real non-DTF graph and return sanitized facts."""

    rehearsal = os.environ.get("DJANGO61_MIGRATION_REHEARSAL")
    mariadb_rehearsal = os.environ.get("DJANGO61_MARIADB_REHEARSAL") == "1"
    if rehearsal != "1" and not mariadb_rehearsal:
        raise GateFailure("migration_rehearsal_marker_missing")
    database_path = None
    if not mariadb_rehearsal:
        database_path = Path(os.environ.get("DJANGO61_MIGRATION_DB_PATH", ""))
        temp_root = Path(os.environ.get("DJANGO61_MIGRATION_TEMP_ROOT", ""))
        database_path = validate_disposable_database_path(database_path, temp_root)
        if database_path.exists() and database_path.is_symlink():
            raise GateFailure("disposable_database_symlink_forbidden")

    settings_module = MARIADB_SETTINGS if mariadb_rehearsal else SETTINGS
    os.environ["DJANGO_SETTINGS_MODULE"] = settings_module
    import django
    from django.conf import settings

    configured_databases = settings.DATABASES
    if set(configured_databases) != {"default"}:
        raise GateFailure("database_alias_violation")
    if "dtf" in configured_databases:
        raise GateFailure("dtf_database_alias_forbidden")
    if mariadb_rehearsal:
        if configured_databases["default"].get("ENGINE") != "django.db.backends.mysql":
            raise GateFailure("mariadb_rehearsal_required")
    else:
        # The profile starts with one in-memory SQLite alias. Replace it before
        # setup/connection construction, and fail closed if a DTF alias appears.
        configured_databases["default"] = {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": str(database_path),
            "OPTIONS": {},
            "TEST": {"NAME": str(database_path)},
        }
    django.setup()

    from django.apps import apps
    from django.db import connection
    from django.db.migrations.executor import MigrationExecutor
    from django.db.migrations.loader import MigrationLoader
    from django.db.migrations.recorder import MigrationRecorder

    expected_vendor = "mysql" if mariadb_rehearsal else "sqlite"
    if connection.vendor != expected_vendor:
        raise GateFailure(
            "mariadb_rehearsal_required" if mariadb_rehearsal else "sqlite_rehearsal_required"
        )
    loader = MigrationLoader(connection, ignore_no_migrations=True)
    executor = MigrationExecutor(connection)
    graph = loader.graph
    all_nodes = sorted(graph.nodes)
    non_dtf_nodes = sorted(node for node in all_nodes if node[0].casefold() != "dtf")
    targets = [node for node in graph.leaf_nodes() if node[0].casefold() != "dtf"]
    plan = executor.migration_plan(targets)
    pending = sorted(
        f"{migration.app_label}.{migration.name}"
        for migration, _backwards in plan
        if migration.app_label.casefold() != "dtf"
    )

    try:
        loader.check_consistent_history(connection)
        consistent_history = True
    except Exception as exc:  # pragma: no cover - exact Django exception varies
        raise GateFailure("migration_history_inconsistent") from exc

    recorder = MigrationRecorder(connection)
    applied = sorted(
        f"{app}.{name}"
        for app, name in recorder.applied_migrations()
        if app.casefold() != "dtf"
    )
    graph_lines: list[str] = []
    for app, name in non_dtf_nodes:
        migration = graph.nodes[(app, name)]
        dependencies = sorted(
            f"{dep_app}.{dep_name}"
            for dep_app, dep_name in migration.dependencies
            if dep_app.casefold() != "dtf"
        )
        replacements = sorted(
            f"{replace_app}.{replace_name}"
            for replace_app, replace_name in getattr(migration, "replaces", ())
            if replace_app.casefold() != "dtf"
        )
        graph_lines.append(
            "|".join(
                (
                    f"{app}.{name}",
                    ",".join(dependencies),
                    ",".join(replacements),
                )
            )
        )
    graph_fingerprint = _hash_lines(graph_lines)

    app_labels = _project_app_labels(apps)
    app_inventory: list[dict[str, Any]] = []
    for app in sorted(app_labels):
        migrations = sorted(
            (name, migration)
            for (app_label, name), migration in loader.disk_migrations.items()
            if app_label == app
        )
        if not migrations:
            continue
        data_or_sql = 0
        irreversible = 0
        elidable = 0
        atomic_false = 0
        cross_app_dependencies = 0
        replaced = 0
        for _name, migration in migrations:
            flags = _migration_operation_flags(migration)
            data_or_sql += flags[0]
            irreversible += flags[1]
            elidable += flags[2]
            atomic_false += int(getattr(migration, "atomic", True) is False)
            replaced += len(getattr(migration, "replaces", ()))
            cross_app_dependencies += sum(
                dep_app.casefold() != app.casefold()
                and dep_app.casefold() != "dtf"
                for dep_app, _dep_name in migration.dependencies
            )
        app_inventory.append(
            {
                "app": app,
                "migration_count": len(migrations),
                "first": migrations[0][0],
                "leafs": sorted(
                    name for leaf_app, name in targets if leaf_app == app
                ),
                "data_or_sql_migrations": data_or_sql,
                "irreversible_operations": irreversible,
                "elidable_operations": elidable,
                "atomic_false_migrations": atomic_false,
                "cross_app_dependencies": cross_app_dependencies,
                "replaced_migrations": replaced,
            }
        )

    dtf_nodes = sorted(
        f"{app}.{name}" for app, name in all_nodes if app.casefold() == "dtf"
    )
    dtf_real_modules: list[str] = []
    for (app, _name), migration in loader.disk_migrations.items():
        if app.casefold() != "dtf":
            continue
        module_name = migration.__class__.__module__
        if not module_name.startswith(DTF_STUB_PREFIX):
            dtf_real_modules.append(module_name)

    app_configs = {config.label: config for config in apps.get_app_configs()}
    actual_dtf_app_loaded = any(
        label.casefold() == "dtf"
        and not config.name.startswith(DTF_STUB_PREFIX)
        for label, config in app_configs.items()
    )
    dtf_config = app_configs.get("dtf")
    dtf_stub = dtf_config.name if dtf_config else ""

    if mariadb_rehearsal:
        (
            schema_hash,
            schema_object_count,
            dtf_tables,
            trigger_count,
            routine_count,
            event_count,
        ) = _mariadb_schema_hash(connection)
    else:
        table_rows = connection.cursor()
        try:
            table_rows.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
            dtf_tables = sorted(
                str(row[0])
                for row in table_rows.fetchall()
                if str(row[0]).casefold().startswith("dtf_")
            )
        finally:
            table_rows.close()

        with sqlite3.connect(database_path) as sqlite_connection:
            schema_hash = _database_schema_hash(sqlite_connection)
            schema_object_count = sqlite_connection.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'"
            ).fetchone()[0]

    result = {
        "status": "ok",
        "database_vendor": connection.vendor,
        "settings": settings_module,
        "network_policy": getattr(settings, "TEST_NETWORK_POLICY", ""),
        "database_aliases": sorted(settings.DATABASES),
        "actual_dtf_app_loaded": actual_dtf_app_loaded,
        "dtf_stub": dtf_stub,
        "dtf_stub_nodes": dtf_nodes,
        "dtf_real_modules": sorted(set(dtf_real_modules)),
        "dtf_tables": dtf_tables,
        "consistent_history": consistent_history,
        "pending": len(pending),
        "pending_migrations": pending,
        "applied": len(applied),
        "applied_history_hash": _hash_lines(applied),
        "graph_node_count": len(non_dtf_nodes),
        "graph_leaf_count": len(targets),
        "graph_fingerprint": graph_fingerprint,
        "project_app_count": len(app_inventory),
        "app_inventory": app_inventory,
        "schema_object_count": int(schema_object_count),
        "schema_hash": schema_hash,
    }
    if mariadb_rehearsal:
        result.update(
            {
                "schema_metadata_scope": {
                    "includes": list(MARIADB_SCHEMA_METADATA_SCOPE),
                    "dump_options": list(MARIADB_DUMP_OPTIONS),
                },
                "trigger_count": trigger_count,
                "routine_count": routine_count,
                "event_count": event_count,
            }
        )
    return result


def _run_worker_action(action: str) -> dict[str, Any]:
    """Execute one worker action; used by the parent runner and tests."""

    if action == "probe":
        return _probe_database()

    # Bootstrap the exact same settings/database contract before importing
    # management commands.  ``call_command`` does not reliably call
    # ``django.setup()`` when invoked from a standalone worker process.
    _probe_database()
    from django.core.management import call_command
    from django.db import connection

    output = io.StringIO()
    error_output = io.StringIO()
    if action == "migrate":
        call_command(
            "migrate",
            database="default",
            interactive=False,
            verbosity=0,
            stdout=output,
            stderr=error_output,
        )
    elif action == "migrate-check":
        call_command(
            "migrate",
            database="default",
            check=True,
            interactive=False,
            verbosity=0,
            stdout=output,
            stderr=error_output,
        )
    elif action == "drift":
        call_command(
            "makemigrations",
            check=True,
            dry_run=True,
            interactive=False,
            verbosity=0,
            stdout=output,
            stderr=error_output,
        )
    else:
        raise GateFailure(f"unknown_worker_action:{action}")
    connection.close()
    return _probe_database()


def _worker_main(action: str) -> int:
    try:
        payload = _run_worker_action(action)
    except Exception as exc:
        detail = str(exc).replace("\n", " ")[:200]
        print(json.dumps({"status": "failed", "error": type(exc).__name__, "detail": detail}))
        return 2
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    return 0


def _run_subprocess_worker(
    *,
    python: str,
    action: str,
    database_path: Path,
    temp_root: Path,
    source_environment: dict[str, str] | None = None,
) -> dict[str, Any]:
    environment = safe_worker_environment(
        database_path=database_path,
        temp_root=temp_root,
        source=source_environment,
    )
    completed = subprocess.run(
        [python, str(Path(__file__).resolve()), "--worker", action],
        cwd=APP_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=COMMAND_TIMEOUT_SECONDS,
        check=False,
    )
    if completed.returncode:
        raise GateFailure(f"worker_failed:{action}:{completed.returncode}")
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    if not lines:
        raise GateFailure(f"worker_output_missing:{action}")
    try:
        payload = json.loads(lines[-1])
    except json.JSONDecodeError as exc:
        raise GateFailure(f"worker_output_invalid:{action}") from exc
    if payload.get("status") != "ok":
        raise GateFailure(f"worker_payload_failed:{action}")
    return payload


def _mariadb_worker_environment(
    *, database: str, username: str, password: str, host: str, port: str,
    source: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Build a scrubbed environment for a generated MariaDB worker."""

    source = dict(os.environ if source is None else source)
    assert_local_only_environment(source)
    environment = {
        name: value
        for name, value in source.items()
        if name in {"PATH", "HOME", "LANG", "LC_ALL", "VIRTUAL_ENV", "SYSTEMROOT"}
    }
    environment.update(
        {
            "PYTHONPATH": str(ROOT / "twocomms"),
            "DJANGO_SETTINGS_MODULE": MARIADB_SETTINGS,
            "DJANGO_ENV": "development",
            "SECRET_KEY": "django61-mariadb-rehearsal-only",
            "DJANGO61_MARIADB_REHEARSAL": "1",
            "TEST_MARIADB_NAME": database,
            "TEST_MARIADB_USER": username,
            "TEST_MARIADB_PASSWORD": password,
            "TEST_MARIADB_HOST": host,
            "TEST_MARIADB_PORT": str(port),
            "TEST_NETWORK_POLICY": "deny-external-allow-loopback",
            "PYTHONNOUSERSITE": "1",
            "PYTHONUNBUFFERED": "1",
            "MANAGER_TG_BOT_TOKEN": "",
            "MANAGEMENT_TG_BOT_TOKEN": "",
            "TELEGRAM_BOT_TOKEN": "",
            "TELEGRAM_CHAT_ID": "",
            "TELEGRAM_ADMIN_ID": "",
        }
    )
    return environment


def _run_mariadb_subprocess_worker(
    *, python: str, action: str, database: str, username: str, password: str,
    host: str, port: str, source_environment: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    environment = _mariadb_worker_environment(
        database=database, username=username, password=password,
        host=host, port=port, source=source_environment,
    )
    completed = subprocess.run(
        [python, str(Path(__file__).resolve()), "--worker", action],
        cwd=APP_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=COMMAND_TIMEOUT_SECONDS,
        check=False,
    )
    if completed.returncode:
        summary = (completed.stderr or completed.stdout or "").strip().splitlines()
        marker = summary[-1] if summary else "empty"
        raise GateFailure(f"mariadb_worker_failed:{action}:{completed.returncode}:{marker[:240]}")
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    if not lines:
        raise GateFailure(f"mariadb_worker_output_missing:{action}")
    try:
        payload = json.loads(lines[-1])
    except json.JSONDecodeError as exc:
        raise GateFailure(f"mariadb_worker_output_invalid:{action}") from exc
    if payload.get("status") != "ok":
        raise GateFailure(f"mariadb_worker_payload_failed:{action}")
    return payload


def validate_probe(
    payload: dict[str, Any], *, require_no_pending: bool = True
) -> None:
    """Reject graph/database facts outside the non-DTF rehearsal contract."""

    required = {
        "status",
        "database_vendor",
        "settings",
        "network_policy",
        "database_aliases",
        "actual_dtf_app_loaded",
        "dtf_stub",
        "dtf_stub_nodes",
        "dtf_real_modules",
        "dtf_tables",
        "pending",
        "consistent_history",
        "graph_fingerprint",
        "schema_hash",
    }
    missing = sorted(required - payload.keys())
    if missing:
        raise GateFailure("probe_fields_missing:" + ",".join(missing))
    if payload["status"] != "ok":
        raise GateFailure("probe_status_failed")
    if payload["database_vendor"] != "sqlite":
        raise GateFailure("sqlite_rehearsal_required")
    if payload["settings"] != SETTINGS:
        raise GateFailure("migration_settings_profile_violation")
    if payload["network_policy"] != "deny-external":
        raise GateFailure("network_policy_violation")
    if payload["database_aliases"] != ["default"]:
        raise GateFailure("database_alias_violation")
    if payload["actual_dtf_app_loaded"]:
        raise GateFailure("dtf_app_loaded")
    if not str(payload["dtf_stub"]).startswith(DTF_STUB_PREFIX):
        raise GateFailure("dtf_stub_violation")
    if payload["dtf_real_modules"]:
        raise GateFailure("dtf_real_migrations_loaded")
    if payload["dtf_tables"]:
        raise GateFailure("dtf_tables_present")
    if any(not str(node).startswith("dtf.") for node in payload["dtf_stub_nodes"]):
        raise GateFailure("dtf_node_inventory_invalid")
    if require_no_pending and (
        payload["pending"] != 0 or payload.get("pending_migrations")
    ):
        raise GateFailure("pending_non_dtf_migrations")
    if not payload["consistent_history"]:
        raise GateFailure("migration_history_inconsistent")
    if not payload["graph_fingerprint"] or not payload["schema_hash"]:
        raise GateFailure("probe_fingerprint_missing")


def validate_mariadb_probe(payload: Mapping[str, Any], *, require_no_pending: bool = True) -> None:
    """Validate a real MariaDB probe without accepting SQLite fallback."""

    required = {
        "status", "database_vendor", "settings", "network_policy", "database_aliases",
        "actual_dtf_app_loaded", "dtf_real_modules", "dtf_tables", "pending",
        "consistent_history", "graph_fingerprint", "schema_hash", "applied_history_hash",
        "applied", "schema_object_count", "schema_metadata_scope",
        "trigger_count", "routine_count", "event_count",
    }
    missing = sorted(required - set(payload))
    if missing:
        raise GateFailure("mariadb_probe_fields_missing:" + ",".join(missing))
    if payload["status"] != "ok" or payload["database_vendor"] != "mysql":
        raise GateFailure("mariadb_probe_requires_mysql")
    if payload["settings"] != MARIADB_SETTINGS:
        raise GateFailure("mariadb_settings_profile_violation")
    if payload["network_policy"] != "deny-external-allow-loopback":
        raise GateFailure("mariadb_network_policy_violation")
    if payload["database_aliases"] != ["default"]:
        raise GateFailure("mariadb_database_alias_violation")
    if payload["actual_dtf_app_loaded"] or payload["dtf_real_modules"] or payload["dtf_tables"]:
        raise GateFailure("mariadb_dtf_surface_present")
    if not payload["consistent_history"]:
        raise GateFailure("mariadb_migration_history_inconsistent")
    if require_no_pending and payload["pending"] != 0:
        raise GateFailure("mariadb_pending_non_dtf_migrations")
    _require_sha256(payload["graph_fingerprint"], "mariadb_graph_fingerprint")
    _require_sha256(payload["schema_hash"], "mariadb_schema_hash")
    _require_sha256(payload["applied_history_hash"], "mariadb_applied_history_hash")
    metadata_scope = _require_mapping(
        payload["schema_metadata_scope"], "mariadb_probe_schema_metadata_scope"
    )
    if tuple(metadata_scope.get("includes") or ()) != MARIADB_SCHEMA_METADATA_SCOPE:
        raise GateFailure("mariadb_probe_schema_metadata_scope_incomplete")
    if tuple(metadata_scope.get("dump_options") or ()) != MARIADB_DUMP_OPTIONS:
        raise GateFailure("mariadb_probe_dump_scope_incomplete")
    for field in ("trigger_count", "routine_count", "event_count"):
        value = payload[field]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise GateFailure(f"mariadb_probe_{field}_missing_or_invalid")
    if require_no_pending and (
        int(payload["applied"]) < 1 or int(payload["schema_object_count"]) < 1
    ):
        raise GateFailure("mariadb_probe_empty_schema")


def classify_candidate(record: dict[str, Any]) -> dict[str, Any]:
    """Classify an app without inventing a squash range."""

    migration_count = int(record["migration_count"])
    candidate = migration_count >= 20
    risk = "low"
    if (
        int(record["data_or_sql_migrations"])
        or int(record["irreversible_operations"])
        or int(record["atomic_false_migrations"])
    ):
        risk = "high"
    elif int(record["cross_app_dependencies"]):
        risk = "medium"
    result = {
        "app": record["app"],
        "migration_count": migration_count,
        "first": record["first"],
        "leafs": list(record["leafs"]),
        "candidate": candidate,
        "risk": risk,
        "eligibility": "blocked" if candidate else "not_candidate",
        "blockers": (
            [
                "authoritative_applied_history_missing",
                "mariadb_clean_install_missing",
                "approved_squash_ranges_missing",
            ]
            if candidate
            else []
        ),
        "observed": {
            "data_or_sql_migrations": int(record["data_or_sql_migrations"]),
            "irreversible_operations": int(record["irreversible_operations"]),
            "elidable_operations": int(record.get("elidable_operations", 0)),
            "atomic_false_migrations": int(record["atomic_false_migrations"]),
            "cross_app_dependencies": int(record["cross_app_dependencies"]),
            "replaced_migrations": int(record["replaced_migrations"]),
        },
    }
    return result


def build_decision(
    *,
    sqlite_clean_install: bool,
    sqlite_restore: bool,
    authoritative_applied_history: bool,
    mariadb_clean_install: bool,
    approved_ranges: bool,
    authoritative_evidence: Mapping[str, Any] | None = None,
    mariadb_evidence: Mapping[str, Any] | None = None,
    restore_evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    blocking_conditions: list[str] = []
    if not authoritative_applied_history:
        blocking_conditions.append("authoritative_applied_history_missing")
    elif authoritative_evidence is None:
        blocking_conditions.append("authoritative_applied_history_evidence_missing")
    else:
        try:
            validate_authoritative_applied_history(authoritative_evidence)
        except GateFailure:
            blocking_conditions.append("authoritative_applied_history_invalid")
    if not mariadb_clean_install:
        blocking_conditions.append("mariadb_clean_install_missing")
    elif mariadb_evidence is None:
        blocking_conditions.append("mariadb_clean_install_evidence_missing")
    else:
        try:
            validate_mariadb_rehearsal_evidence(mariadb_evidence)
        except GateFailure:
            blocking_conditions.append("mariadb_clean_install_evidence_invalid")
    if (
        authoritative_applied_history
        and mariadb_clean_install
        and authoritative_evidence is not None
        and mariadb_evidence is not None
    ):
        try:
            validate_authoritative_history_compatibility(
                authoritative_evidence,
                mariadb_evidence,
                graph_fingerprint=str(mariadb_evidence.get("graph_fingerprint") or ""),
            )
        except GateFailure:
            blocking_conditions.append(
                "authoritative_history_compatibility_invalid"
            )
    if not approved_ranges:
        blocking_conditions.append("approved_squash_ranges_missing")
    if not sqlite_clean_install:
        blocking_conditions.append("sqlite_clean_install_failed")
    if not sqlite_restore:
        blocking_conditions.append("sqlite_restore_rehearsal_failed")
    if authoritative_applied_history and mariadb_clean_install and approved_ranges:
        if restore_evidence is None:
            blocking_conditions.append("backup_restore_evidence_missing")
        else:
            try:
                validate_restore_drill_evidence(restore_evidence)
            except GateFailure:
                blocking_conditions.append("backup_restore_evidence_invalid")
    go = not blocking_conditions
    return {
        "decision": "go" if go else "no-go",
        "blocking_conditions": blocking_conditions,
        "historical_migrations_may_be_deleted": False,
        "squash_may_run": go,
        "post_squash_requirements": (
            ["follow_up_release_required"] if go else []
        ),
    }


def validate_approved_squash_ranges(
    evidence: Mapping[str, Any], *, graph_fingerprint: str
) -> list[dict[str, str]]:
    """Validate owner-approved non-DTF replacement ranges.

    This is intentionally a metadata contract. It never discovers ranges from
    the graph and never invokes ``squashmigrations``.
    """

    evidence = _require_mapping(evidence, "approved_squash_ranges")
    if evidence.get("status") != "approved":
        raise GateFailure("approved_squash_ranges_not_approved")
    if evidence.get("scope") != "non_dtf":
        raise GateFailure("approved_squash_ranges_scope_violation")
    expected_fingerprint = _require_sha256(
        graph_fingerprint, "expected_graph_fingerprint"
    )
    approved_fingerprint = _require_sha256(
        evidence.get("graph_fingerprint"), "approved_ranges_graph_fingerprint"
    )
    if approved_fingerprint != expected_fingerprint:
        raise GateFailure("approved_ranges_graph_fingerprint_mismatch")
    if not str(evidence.get("reviewer") or "").strip():
        raise GateFailure("approved_squash_ranges_reviewer_missing")
    if not str(evidence.get("approved_at") or "").strip():
        raise GateFailure("approved_squash_ranges_timestamp_missing")

    raw_ranges = evidence.get("ranges")
    if not isinstance(raw_ranges, list) or not raw_ranges:
        raise GateFailure("approved_squash_ranges_missing")
    ranges: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for raw_range in raw_ranges:
        item = _require_mapping(raw_range, "approved_squash_range")
        normalized = {
            key: str(item.get(key) or "").strip()
            for key in ("app", "start", "end", "replacement")
        }
        if any(not value for value in normalized.values()):
            raise GateFailure("approved_squash_range_incomplete")
        app = normalized["app"]
        if app.casefold() == "dtf" or app.casefold().startswith("dtf_"):
            raise GateFailure("approved_squash_ranges_dtf_forbidden")
        if any(
            not value.replace("_", "").isalnum()
            for value in normalized.values()
        ):
            raise GateFailure("approved_squash_range_identifier_invalid")
        identity = (app, normalized["start"], normalized["end"])
        if identity in seen:
            raise GateFailure("approved_squash_range_duplicate")
        seen.add(identity)
        ranges.append(normalized)
    return ranges


def _evidence_sha256(evidence: Mapping[str, Any]) -> str:
    rendered = json.dumps(
        evidence, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def build_squash_artifact_manifest(
    *,
    graph_fingerprint: str,
    authoritative_evidence: Mapping[str, Any],
    mariadb_evidence: Mapping[str, Any],
    restore_evidence: Mapping[str, Any],
    approved_ranges: Mapping[str, Any],
) -> dict[str, Any]:
    """Build a metadata-only manifest for a separately executed squash.

    A ready manifest allows a replacement migration to be generated in a
    scoped follow-up. Historical migrations remain mandatory in that release.
    """

    fingerprint = _require_sha256(graph_fingerprint, "graph_fingerprint")
    validate_authoritative_applied_history(authoritative_evidence)
    validate_mariadb_rehearsal_evidence(mariadb_evidence)
    validate_restore_drill_evidence(restore_evidence)

    rehearsal_fingerprint = _require_sha256(
        mariadb_evidence.get("graph_fingerprint"),
        "mariadb_rehearsal_graph_fingerprint",
    )
    if rehearsal_fingerprint != fingerprint:
        raise GateFailure("mariadb_rehearsal_graph_fingerprint_mismatch")
    clean_install = _require_mapping(
        mariadb_evidence.get("clean_install"), "mariadb_clean_install"
    )
    replay = _require_mapping(mariadb_evidence.get("replay"), "mariadb_replay")
    clean_hash = _require_sha256(
        clean_install.get("applied_history_hash"),
        "mariadb_clean_install_history_hash",
    )
    replay_hash = _require_sha256(
        replay.get("applied_history_hash"), "mariadb_replay_history_hash"
    )
    if clean_hash != replay_hash:
        raise GateFailure("mariadb_replay_history_hash_mismatch")
    # The authoritative recorder may retain replaced/legacy rows and therefore
    # need not hash-identically to a clean replay of the current graph.  A
    # separate identity review is required before this metadata can be GO.
    validate_authoritative_history_compatibility(
        authoritative_evidence,
        mariadb_evidence,
        graph_fingerprint=fingerprint,
    )
    if dict(mariadb_evidence.get("restore_drill") or {}) != dict(restore_evidence):
        raise GateFailure("restore_drill_evidence_mismatch")

    ranges = validate_approved_squash_ranges(
        approved_ranges, graph_fingerprint=fingerprint
    )
    decision = build_decision(
        sqlite_clean_install=True,
        sqlite_restore=True,
        authoritative_applied_history=True,
        mariadb_clean_install=True,
        approved_ranges=True,
        authoritative_evidence=authoritative_evidence,
        mariadb_evidence=mariadb_evidence,
        restore_evidence=restore_evidence,
    )
    if decision["decision"] != "go":
        raise GateFailure("squash_artifact_not_ready")
    return {
        "version": 1,
        "status": "ready",
        "artifact_type": "metadata_only",
        "scope": "non_dtf",
        "dtf_scope": "excluded",
        "graph_fingerprint": fingerprint,
        "authoritative_evidence_sha256": _evidence_sha256(
            authoritative_evidence
        ),
        "mariadb_evidence_sha256": _evidence_sha256(mariadb_evidence),
        "restore_evidence_sha256": _evidence_sha256(restore_evidence),
        "approved_ranges_evidence_sha256": _evidence_sha256(approved_ranges),
        "approved_ranges": ranges,
        "decision": decision,
        "historical_migrations_deleted": False,
        "squash_executed": False,
    }


def write_evidence(path: Path, payload: dict[str, Any]) -> None:
    path = Path(path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    temporary.chmod(0o600)
    os.replace(temporary, path)
    path.chmod(0o600)


def run_gate(*, python: str, evidence_path: Path) -> dict[str, Any]:
    assert_local_only_environment()
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="twc-django61-migration-") as directory:
        temp_root = Path(directory)
        clean = temp_root / "clean.sqlite3"
        restored = temp_root / "restored.sqlite3"
        initial = _run_subprocess_worker(
            python=python,
            action="probe",
            database_path=clean,
            temp_root=temp_root,
        )
        validate_probe(initial, require_no_pending=False)
        migrated = _run_subprocess_worker(
            python=python,
            action="migrate",
            database_path=clean,
            temp_root=temp_root,
        )
        validate_probe(migrated)
        if initial["graph_fingerprint"] != migrated["graph_fingerprint"]:
            raise GateFailure("graph_changed_during_clean_install")
        drift = _run_subprocess_worker(
            python=python,
            action="drift",
            database_path=clean,
            temp_root=temp_root,
        )
        validate_probe(drift)
        restore_sqlite(clean, restored, temp_root=temp_root)
        restored_probe = _run_subprocess_worker(
            python=python,
            action="probe",
            database_path=restored,
            temp_root=temp_root,
        )
        validate_probe(restored_probe)
        restored_check = _run_subprocess_worker(
            python=python,
            action="migrate-check",
            database_path=restored,
            temp_root=temp_root,
        )
        validate_probe(restored_check)

        graph_fingerprints = {
            initial["graph_fingerprint"],
            migrated["graph_fingerprint"],
            drift["graph_fingerprint"],
            restored_probe["graph_fingerprint"],
            restored_check["graph_fingerprint"],
        }
        if len(graph_fingerprints) != 1:
            raise GateFailure("graph_fingerprint_mismatch")
        if migrated["applied_history_hash"] != restored_probe["applied_history_hash"]:
            raise GateFailure("restore_applied_history_mismatch")
        if migrated["schema_hash"] != restored_probe["schema_hash"]:
            raise GateFailure("restore_schema_mismatch")

        candidates = [
            classify_candidate(record) for record in migrated["app_inventory"]
        ]
        decision = build_decision(
            sqlite_clean_install=migrated["pending"] == 0,
            sqlite_restore=restored_check["pending"] == 0,
            authoritative_applied_history=False,
            mariadb_clean_install=False,
            approved_ranges=False,
        )
        payload = {
            "version": 1,
            "status": "passed",
            "repo_sha": _repo_sha(),
            "python": str(Path(python).resolve()),
            "django": "6.1",
            "settings": SETTINGS,
            "scope": "non-dtf",
            "dtf_scope": "excluded",
            "database": "disposable-sqlite",
            "network_policy": "deny-external",
            "graph": {
                "node_count": migrated["graph_node_count"],
                "leaf_count": migrated["graph_leaf_count"],
                "fingerprint": migrated["graph_fingerprint"],
                "stable_across_rehearsal": len(graph_fingerprints) == 1,
                "pending_after_clean_install": migrated["pending"],
                "pending_after_restore": restored_check["pending"],
                "applied_history_count": migrated["applied"],
                "applied_history_hash": migrated["applied_history_hash"],
            },
            "clean_install": {
                "status": "passed",
                "database_vendor": "sqlite",
                "schema_object_count": migrated["schema_object_count"],
                "schema_hash": migrated["schema_hash"],
                "migration_check": "pending=0",
            },
            "restore_rehearsal": {
                "status": "passed",
                "method": "sqlite.Connection.backup",
                "schema_hash_matches": migrated["schema_hash"]
                == restored_probe["schema_hash"],
                "applied_history_matches": migrated["applied_history_hash"]
                == restored_probe["applied_history_hash"],
                "migration_check": "pending=0",
            },
            "replay": {
                "status": "passed",
                "database_vendor": "sqlite",
                "pending": restored_check["pending"],
                "applied_history_hash": restored_check["applied_history_hash"],
                "migration_check": "pending=0",
            },
            "candidates": candidates,
            "decision": decision,
            "historical_migrations_deleted": False,
            "squash_executed": False,
            "duration_seconds": round(time.monotonic() - started, 3),
        }
    write_evidence(evidence_path, payload)
    return payload


def _resolve_mariadb_client(name: str, source: Mapping[str, str]) -> str:
    configured_name = {
        "mariadb-dump": "MARIADB_DUMP_BIN",
        "mariadb": "MARIADB_CLIENT_BIN",
    }[name]
    candidate = source.get(configured_name) or shutil.which(
        name, path=source.get("PATH")
    )
    if not candidate:
        raise GateFailure(f"mariadb_binary_missing:{name}")
    return str(Path(candidate).resolve())


def _mariadb_dump(
    *, dump_bin: str, database: str, host: str, port: str,
    username: str, password: str, destination: Path,
    source_environment: Mapping[str, str],
) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.touch(mode=0o600, exist_ok=False)
    environment = dict(source_environment)
    environment["MYSQL_PWD"] = password
    command = [
        dump_bin,
        "--no-defaults",
        f"--host={host}",
        f"--port={port}",
        f"--user={username}",
        "--single-transaction",
        "--skip-lock-tables",
        "--no-tablespaces",
        "--routines",
        "--triggers",
        "--events",
        "--hex-blob",
        "--skip-comments",
        database,
    ]
    with destination.open("wb") as output:
        completed = subprocess.run(
            command,
            env=environment,
            stdout=output,
            stderr=subprocess.PIPE,
            timeout=COMMAND_TIMEOUT_SECONDS,
            check=False,
        )
    if completed.returncode:
        raise GateFailure(f"mariadb_dump_failed:{completed.returncode}")
    digest = hashlib.sha256()
    with destination.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    destination.chmod(0o600)
    return digest.hexdigest()


def _mariadb_restore(
    *, client_bin: str, database: str, host: str, port: str,
    username: str, password: str, dump_path: Path,
    source_environment: Mapping[str, str],
) -> None:
    environment = dict(source_environment)
    environment["MYSQL_PWD"] = password
    command = [
        client_bin,
        "--no-defaults",
        f"--host={host}",
        f"--port={port}",
        f"--user={username}",
        database,
    ]
    with dump_path.open("rb") as dump:
        completed = subprocess.run(
            command,
            env=environment,
            stdin=dump,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=COMMAND_TIMEOUT_SECONDS,
            check=False,
        )
    if completed.returncode:
        raise GateFailure(f"mariadb_restore_failed:{completed.returncode}")


def run_mariadb_lifecycle_gate(
    *, python: str, evidence_path: Path,
    source_environment: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Rehearse the current non-DTF graph on two disposable MariaDB schemas."""

    assert_local_only_environment(dict(os.environ if source_environment is None else source_environment))
    source = dict(os.environ if source_environment is None else source_environment)
    mariadb_gate = _mariadb_components()
    source.setdefault("PATH", os.environ.get("PATH", ""))
    dump_bin = _resolve_mariadb_client("mariadb-dump", source)
    client_bin = _resolve_mariadb_client("mariadb", source)
    started = time.monotonic()
    token = secrets.token_hex(6)
    clean_database = f"test_twocomms_mig_clean_{token}"
    restore_database = f"test_twocomms_mig_restore_{token}"
    username = f"twc_mig_{token}"
    password = secrets.token_urlsafe(24)
    if not MARIADB_DATABASE_RE.fullmatch(clean_database) or not MARIADB_DATABASE_RE.fullmatch(restore_database):
        raise GateFailure("generated_mariadb_namespace_invalid")
    server = None
    admin = None
    database_attempted = {clean_database: False, restore_database: False}
    user_attempted = False
    cleanup_errors: list[BaseException] = []
    primary_error: BaseException | None = None
    payload: dict[str, Any] | None = None
    dump_path: Path | None = None
    cleanup = {
        "generated_databases_absent": False,
        "generated_user_absent": False,
        "temporary_dump_removed": False,
        "mariadb_process_closed": False,
    }
    with tempfile.TemporaryDirectory(prefix="twc-django61-mariadb-") as directory:
        dump_path = Path(directory) / "migration-graph.sql"
        try:
            server = mariadb_gate._native_admin(source, project_root=ROOT)
            admin = server
            version, version_comment = mariadb_gate._validate_server_identity(
                admin.server_identity()
            )
            admin.ensure_namespace_absent(clean_database, username)
            admin.ensure_namespace_absent(restore_database, username)
            _create_owned_mariadb_database(admin, clean_database, database_attempted)
            _create_owned_mariadb_database(admin, restore_database, database_attempted)
            user_attempted = True
            admin.create_user(username, password)
            admin.grant_schema(username, clean_database)
            admin.grant_schema(username, restore_database)
            worker_kwargs = {
                "python": python,
                "username": username,
                "password": password,
                "host": str(admin.host),
                "port": str(admin.port),
                "source_environment": source,
            }
            print("mariadb lifecycle: clean database provisioned", flush=True)
            initial = _run_mariadb_subprocess_worker(
                action="probe", database=clean_database, **worker_kwargs
            )
            validate_mariadb_probe(initial, require_no_pending=False)
            print("mariadb lifecycle: graph probe passed", flush=True)
            migrated = _run_mariadb_subprocess_worker(
                action="migrate", database=clean_database, **worker_kwargs
            )
            validate_mariadb_probe(migrated)
            print("mariadb lifecycle: clean migration passed", flush=True)
            checked = _run_mariadb_subprocess_worker(
                action="migrate-check", database=clean_database, **worker_kwargs
            )
            validate_mariadb_probe(checked)
            drift = _run_mariadb_subprocess_worker(
                action="drift", database=clean_database, **worker_kwargs
            )
            validate_mariadb_probe(drift)
            fingerprints = {
                initial["graph_fingerprint"], migrated["graph_fingerprint"],
                checked["graph_fingerprint"], drift["graph_fingerprint"],
            }
            if len(fingerprints) != 1:
                raise GateFailure("mariadb_graph_fingerprint_mismatch")
            dump_sha = _mariadb_dump(
                dump_bin=dump_bin, database=clean_database, host=str(admin.host),
                port=str(admin.port), username=username, password=password,
                destination=dump_path,
                source_environment=mariadb_gate._process_environment(source),
            )
            print("mariadb lifecycle: logical dump passed", flush=True)
            _mariadb_restore(
                client_bin=client_bin, database=restore_database, host=str(admin.host),
                port=str(admin.port), username=username, password=password,
                dump_path=dump_path,
                source_environment=mariadb_gate._process_environment(source),
            )
            restored = _run_mariadb_subprocess_worker(
                action="probe", database=restore_database, **worker_kwargs
            )
            validate_mariadb_probe(restored)
            print("mariadb lifecycle: restore probe passed", flush=True)
            replay = _run_mariadb_subprocess_worker(
                action="migrate-check", database=restore_database, **worker_kwargs
            )
            validate_mariadb_probe(replay)
            if migrated["schema_hash"] != restored["schema_hash"]:
                raise GateFailure("mariadb_restore_schema_mismatch")
            if migrated["applied_history_hash"] != restored["applied_history_hash"]:
                raise GateFailure("mariadb_restore_history_mismatch")
            if migrated["applied"] != restored["applied"]:
                raise GateFailure("mariadb_restore_history_count_mismatch")
            if migrated["schema_metadata_scope"] != restored["schema_metadata_scope"]:
                raise GateFailure("mariadb_restore_schema_metadata_scope_mismatch")
            for field in ("trigger_count", "routine_count", "event_count"):
                if migrated[field] != restored[field]:
                    raise GateFailure(f"mariadb_restore_{field}_mismatch")
            authoritative_assessment = assess_authoritative_history_snapshot(
                migrated
            )
            payload = {
                "version": 1,
                "status": "passed",
                "artifact_type": "disposable_mariadb_lifecycle",
                "repo_sha": _repo_sha(),
                "captured_at": datetime.now(timezone.utc).isoformat(),
                "runtime": {
                    "python": ".".join(str(part) for part in sys.version_info[:3]),
                    "django": "6.1",
                },
                "database_vendor": "mysql",
                "production_compatible": True,
                "server_version": version,
                "server_comment": version_comment,
                "disposable": True,
                "scope": "non-dtf",
                "dtf_scope": "excluded",
                "schema_metadata_scope": {
                    "includes": list(MARIADB_SCHEMA_METADATA_SCOPE),
                    "dump_options": list(MARIADB_DUMP_OPTIONS),
                },
                "graph_fingerprint": migrated["graph_fingerprint"],
                "graph_node_count": migrated["graph_node_count"],
                "graph_leaf_count": migrated["graph_leaf_count"],
                "checks": {
                    "migrate_check": {
                        "status": "passed",
                        "pending": checked["pending"],
                    },
                    "makemigrations_check": {
                        "status": "passed",
                        "pending": drift["pending"],
                    },
                    "restore_migrate_check": {
                        "status": "passed",
                        "pending": replay["pending"],
                    },
                },
                "clean_install": {
                    "status": "passed",
                    "database": clean_database,
                    "pending": migrated["pending"],
                    "schema_hash": migrated["schema_hash"],
                    "applied_history_hash": migrated["applied_history_hash"],
                    "applied_history_count": migrated["applied"],
                    "schema_object_count": migrated["schema_object_count"],
                    "schema_metadata_scope": migrated["schema_metadata_scope"],
                    "trigger_count": migrated["trigger_count"],
                    "routine_count": migrated["routine_count"],
                    "event_count": migrated["event_count"],
                },
                "backup": {
                    "status": "passed",
                    "artifact_id": "mariadb-dump:non-dtf-migration-graph",
                    "sha256": dump_sha,
                    "format": "mariadb-dump",
                },
                "restore": {
                    "status": "passed",
                    "source_database": clean_database,
                    "destination_database": restore_database,
                    "integrity_check": True,
                    "schema_hash_matches": True,
                    "applied_history_matches": True,
                },
                "restore_drill": {
                    "status": "passed",
                    "disposable": True,
                    "backup": {
                        "status": "passed",
                        "artifact_id": "mariadb-dump:non-dtf-migration-graph",
                        "sha256": dump_sha,
                    },
                    "restore": {
                        "status": "passed",
                        "source_database": clean_database,
                        "destination_database": restore_database,
                        "integrity_check": True,
                        "schema_hash_matches": migrated["schema_hash"] == restored["schema_hash"],
                        "applied_history_matches": migrated["applied_history_hash"] == restored["applied_history_hash"],
                    },
                    "rollback": {"status": "passed", "verified": True},
                },
                "replay": {
                    "status": "passed",
                    "database": restore_database,
                    "pending": replay["pending"],
                    "schema_hash": replay["schema_hash"],
                    "applied_history_hash": replay["applied_history_hash"],
                    "applied_history_count": replay["applied"],
                    "schema_object_count": replay["schema_object_count"],
                    "schema_metadata_scope": replay["schema_metadata_scope"],
                    "trigger_count": replay["trigger_count"],
                    "routine_count": replay["routine_count"],
                    "event_count": replay["event_count"],
                },
                "authoritative_history_compatibility": authoritative_assessment,
                "decision": {
                    "status": "no-go",
                    "squash_may_run": False,
                    "historical_migrations_may_be_deleted": False,
                    "blocking_conditions": [
                        "fresh_authoritative_identity_set_review_missing",
                        "approved_squash_ranges_missing",
                    ],
                },
                "squash_executed": False,
                "historical_migrations_deleted": False,
                "duration_seconds": round(time.monotonic() - started, 3),
            }
        except BaseException as exc:
            primary_error = exc
        finally:
            if admin is not None:
                if user_attempted:
                    try:
                        admin.drop_user(username)
                    except BaseException as exc:
                        cleanup_errors.append(exc)
                for database, attempted in database_attempted.items():
                    if attempted:
                        try:
                            admin.drop_database(database)
                        except BaseException as exc:
                            cleanup_errors.append(exc)
                for database, attempted in database_attempted.items():
                    if attempted:
                        try:
                            user_exists, database_exists = admin.verify_cleanup(database, username)
                            if user_exists or database_exists:
                                cleanup_errors.append(GateFailure("mariadb_cleanup_residue"))
                        except BaseException as exc:
                            cleanup_errors.append(exc)
                if user_attempted and not cleanup_errors:
                    cleanup["generated_user_absent"] = True
                if all(database_attempted.values()) and not cleanup_errors:
                    cleanup["generated_databases_absent"] = True
            if server is not None:
                try:
                    server.close()
                    cleanup["mariadb_process_closed"] = True
                except BaseException as exc:
                    cleanup_errors.append(exc)
    if dump_path is None or dump_path.exists():
        cleanup_errors.append(GateFailure("mariadb_cleanup_dump_residue"))
    else:
        cleanup["temporary_dump_removed"] = True
    if cleanup_errors:
        if primary_error is not None:
            raise GateFailure("mariadb_lifecycle_failed_and_cleanup_failed") from primary_error
        raise GateFailure("mariadb_lifecycle_cleanup_failed") from cleanup_errors[0]
    if primary_error is not None:
        if isinstance(primary_error, GateFailure):
            raise primary_error
        raise GateFailure(f"mariadb_lifecycle_failed:{type(primary_error).__name__}") from primary_error
    if payload is None:
        raise GateFailure("mariadb_lifecycle_evidence_missing")
    if not all(cleanup.values()):
        raise GateFailure("mariadb_lifecycle_cleanup_unverified")
    payload["cleanup"] = {"status": "verified", **cleanup}
    write_evidence(evidence_path, payload)
    return payload


def _repo_sha() -> str:
    result = subprocess.run(
        ("git", "rev-parse", "HEAD"),
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument(
        "--allow-local-sqlite-rehearsal",
        action="store_true",
        help="required acknowledgement that only disposable local SQLite is used",
    )
    parser.add_argument(
        "--allow-local-mariadb-rehearsal",
        action="store_true",
        help="required acknowledgement for a disposable local MariaDB lifecycle",
    )
    parser.add_argument("--worker", choices=("probe", "migrate", "migrate-check", "drift"))
    args = parser.parse_args(argv)
    if args.worker:
        return _worker_main(args.worker)
    if args.allow_local_mariadb_rehearsal:
        if args.evidence is None:
            parser.error("--evidence is required")
        try:
            payload = run_mariadb_lifecycle_gate(
                python=args.python, evidence_path=args.evidence
            )
        except Exception as exc:
            print(f"migration MariaDB lifecycle failed: {type(exc).__name__}:{exc}", file=sys.stderr)
            return 1
        print(
            json.dumps(
                {
                    "status": payload["status"],
                    "database_vendor": payload["database_vendor"],
                    "server_version": payload["server_version"],
                    "graph_fingerprint": payload["graph_fingerprint"],
                    "duration_seconds": payload["duration_seconds"],
                },
                sort_keys=True,
            )
        )
        return 0
    if not args.allow_local_sqlite_rehearsal:
        print(
            "refusing to run: pass --allow-local-sqlite-rehearsal for disposable local rehearsal",
            file=sys.stderr,
        )
        return 2
    if args.evidence is None:
        parser.error("--evidence is required")
    try:
        payload = run_gate(python=args.python, evidence_path=args.evidence)
    except Exception as exc:
        print(f"migration squash gate failed: {type(exc).__name__}:{exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "status": payload["status"],
                "decision": payload["decision"]["decision"],
                "graph_nodes": payload["graph"]["node_count"],
                "duration_seconds": payload["duration_seconds"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
