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
import hashlib
import io
import json
import os
from pathlib import Path
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
COMMAND_TIMEOUT_SECONDS = 30 * 60
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
    validate_restore_drill_evidence(evidence.get("restore_drill") or {})


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
    if rehearsal != "1":
        raise GateFailure("migration_rehearsal_marker_missing")
    database_path = Path(os.environ.get("DJANGO61_MIGRATION_DB_PATH", ""))
    temp_root = Path(os.environ.get("DJANGO61_MIGRATION_TEMP_ROOT", ""))
    database_path = validate_disposable_database_path(database_path, temp_root)
    if database_path.exists() and database_path.is_symlink():
        raise GateFailure("disposable_database_symlink_forbidden")

    os.environ["DJANGO_SETTINGS_MODULE"] = SETTINGS
    import django
    from django.conf import settings

    # The profile starts with one in-memory SQLite alias. Replace it before
    # setup/connection construction, and fail closed if a DTF alias appears.
    configured_databases = settings.DATABASES
    if set(configured_databases) != {"default"}:
        raise GateFailure("database_alias_violation")
    configured_databases["default"] = {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": str(database_path),
        "OPTIONS": {},
        "TEST": {"NAME": str(database_path)},
    }
    if "dtf" in configured_databases:
        raise GateFailure("dtf_database_alias_forbidden")
    django.setup()

    from django.apps import apps
    from django.db import connection
    from django.db.migrations.executor import MigrationExecutor
    from django.db.migrations.loader import MigrationLoader
    from django.db.migrations.recorder import MigrationRecorder

    if connection.vendor != "sqlite":
        raise GateFailure("sqlite_rehearsal_required")
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

    return {
        "status": "ok",
        "database_vendor": connection.vendor,
        "settings": SETTINGS,
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
        print(json.dumps({"status": "failed", "error": type(exc).__name__}))
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

    authoritative_fingerprint = _require_sha256(
        authoritative_evidence.get("graph_fingerprint"),
        "authoritative_graph_fingerprint",
    )
    if authoritative_fingerprint != fingerprint:
        raise GateFailure("authoritative_graph_fingerprint_mismatch")
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
    authoritative_history_hash = _require_sha256(
        authoritative_evidence.get("applied_history_hash"),
        "authoritative_applied_history_hash",
    )
    if clean_hash != replay_hash:
        raise GateFailure("mariadb_replay_history_hash_mismatch")
    if clean_hash != authoritative_history_hash:
        raise GateFailure("authoritative_applied_history_hash_mismatch")
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
    parser.add_argument("--worker", choices=("probe", "migrate", "migrate-check", "drift"))
    args = parser.parse_args(argv)
    if args.worker:
        return _worker_main(args.worker)
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
