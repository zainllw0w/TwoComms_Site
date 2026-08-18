#!/usr/bin/env python3
"""Evidence runner for Django 6.1 database-level ``on_delete`` actions.

The command has two deliberately separate paths:

* ``inventory`` inspects the non-DTF Django relation graph and, when an
  explicitly configured MariaDB connection is supplied, adds read-only facts
  about engines, real foreign keys, orphans, and reversible DDL evidence.
* ``run_disposable_experiment`` is a programmatic, gate-owned helper for a
  generated local-only MariaDB schema.  It compares a Python-side retention
  delete with an equivalent ``ON DELETE CASCADE`` delete and rehearses
  transactional/DDL rollback.  It is intentionally not exposed as a CLI:
  arbitrary command-line credentials/endpoints must never be able to create
  or drop a database.

No project model or migration is changed by this tool.  A report can therefore
prove a candidate and still return ``NO-GO`` when the current model graph (for
example Django's mixed ``on_delete`` check) is not safe to roll out.
"""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import re
import secrets
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DTF_APP_LABEL = "dtf"
DTF_TABLE_PREFIX = "dtf_"
RETENTION_FIELD_LABEL = "storefront.PageView.session"
SAFE_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
SOFT_DELETE_FIELD_NAMES = frozenset(
    {
        "deleted",
        "deleted_at",
        "is_archived",
        "is_deleted",
        "archived_at",
        "deactivated_at",
    }
)
DATABASE_ON_DELETE_NAMES = frozenset(
    {"DB_CASCADE", "DB_SET_DEFAULT", "DB_SET_NULL"}
)


def _model_label(model: Any) -> str:
    return str(model._meta.label)


def _table_name(model: Any) -> str:
    return str(model._meta.db_table)


def _is_dtf_model(model: Any) -> bool:
    return (
        getattr(model._meta, "app_label", "") == DTF_APP_LABEL
        or _table_name(model).startswith(DTF_TABLE_PREFIX)
    )


def _is_safe_identifier(value: str) -> bool:
    return bool(SAFE_IDENTIFIER.fullmatch(str(value)))


def _quote_identifier(value: str) -> str:
    if not _is_safe_identifier(value):
        raise ValueError(f"unsafe SQL identifier: {value!r}")
    return f"`{value}`"


def _on_delete_name(field: Any) -> str:
    action = getattr(getattr(field, "remote_field", None), "on_delete", None)
    return str(getattr(action, "__name__", action or "UNKNOWN"))


def _receiver_name(receiver: Any) -> str:
    module = getattr(receiver, "__module__", "")
    qualname = getattr(receiver, "__qualname__", getattr(receiver, "__name__", ""))
    return f"{module}.{qualname}".strip(".")


def _flatten_receivers(value: Any) -> Iterable[Any]:
    if isinstance(value, (list, tuple, set, frozenset)):
        for item in value:
            yield from _flatten_receivers(item)
    elif value is not None:
        yield value


def _signal_receivers(signal: Any, model: Any) -> list[Any]:
    """Return live receivers while tolerating Django 6.1 sync/async pairs."""

    return list(_flatten_receivers(signal._live_receivers(model)))


def _receiver_is_known_noop(receiver: Any, model: Any) -> bool:
    """Classify the two project-wide delete receivers that guard by model.

    The allow-list is intentionally code-backed rather than a blanket
    wildcard exception.  If a new receiver is connected, the inventory turns
    it into a blocker until this function is reviewed.
    """

    name = _receiver_name(receiver)
    if name == "storefront.signals.cancel_deleted_image_optimization":
        from storefront import signals as storefront_signals

        targets = getattr(storefront_signals, "IMAGE_OPTIMIZATION_FIELDS", {})
        return model not in targets
    if name == "warehouse.signals.warehouse_delete_print_images":
        from warehouse import signals as warehouse_signals

        label = _model_label(model)
        targets = getattr(warehouse_signals, "_PRINT_IMAGE_LIMITS", {})
        return label not in targets
    return False


def _delete_signal_contract(model: Any) -> dict[str, list[str]]:
    from django.db.models.signals import post_delete, pre_delete

    all_receivers = {
        _receiver_name(receiver)
        for signal in (pre_delete, post_delete)
        for receiver in _signal_receivers(signal, model)
    }
    non_mandatory = {
        _receiver_name(receiver)
        for signal in (pre_delete, post_delete)
        for receiver in _signal_receivers(signal, model)
        if _receiver_is_known_noop(receiver, model)
    }
    return {
        "delete_receivers": sorted(all_receivers),
        "mandatory_delete_receivers": sorted(all_receivers - non_mandatory),
        "non_mandatory_delete_receivers": sorted(non_mandatory),
    }


def _soft_delete_fields(model: Any) -> list[str]:
    return sorted(
        str(field.name)
        for field in model._meta.get_fields()
        if not getattr(field, "auto_created", False)
        and str(getattr(field, "name", "")) in SOFT_DELETE_FIELD_NAMES
    )


def _python_on_delete_siblings(model: Any, current_field: Any) -> list[str]:
    siblings: list[str] = []
    for field in model._meta.get_fields():
        if field is current_field or getattr(field, "auto_created", False):
            continue
        if not (
            getattr(field, "many_to_one", False)
            or getattr(field, "one_to_one", False)
        ):
            continue
        action_name = _on_delete_name(field)
        if action_name in DATABASE_ON_DELETE_NAMES or action_name == "DO_NOTHING":
            continue
        siblings.append(f"{_model_label(model)}.{field.name}:{action_name}")
    return sorted(siblings)


def collect_static_inventory() -> list[dict[str, Any]]:
    """Collect every non-DTF local FK/OneToOne relation from Django's graph."""

    from django.apps import apps
    from django.db import models

    rows: list[dict[str, Any]] = []
    for child_model in sorted(apps.get_models(), key=_model_label):
        if _is_dtf_model(child_model):
            continue
        for field in child_model._meta.get_fields():
            if getattr(field, "auto_created", False):
                continue
            if not (
                getattr(field, "many_to_one", False)
                or getattr(field, "one_to_one", False)
            ):
                continue
            parent_model = getattr(getattr(field, "remote_field", None), "model", None)
            if parent_model is None or _is_dtf_model(parent_model):
                continue
            if not isinstance(field, (models.ForeignKey, models.OneToOneField)):
                continue

            signal_contract = _delete_signal_contract(child_model)
            child_soft_delete = _soft_delete_fields(child_model)
            parent_soft_delete = _soft_delete_fields(parent_model)
            rows.append(
                {
                    "field_label": f"{_model_label(child_model)}.{field.name}",
                    "child_model": _model_label(child_model),
                    "child_app": str(child_model._meta.app_label),
                    "child_table": _table_name(child_model),
                    "child_column": str(field.column),
                    "parent_model": _model_label(parent_model),
                    "parent_app": str(parent_model._meta.app_label),
                    "parent_table": _table_name(parent_model),
                    "parent_column": str(field.target_field.column),
                    "relation_type": "one_to_one"
                    if getattr(field, "one_to_one", False)
                    else "foreign_key",
                    "on_delete": _on_delete_name(field),
                    "db_constraint": bool(getattr(field, "db_constraint", True)),
                    "model_delete_override": child_model.delete
                    is not models.Model.delete,
                    "child_soft_delete_fields": child_soft_delete,
                    "parent_soft_delete_fields": parent_soft_delete,
                    "soft_delete_fields": sorted(
                        set(child_soft_delete + parent_soft_delete)
                    ),
                    "python_on_delete_siblings": _python_on_delete_siblings(
                        child_model, field
                    ),
                    **signal_contract,
                }
            )
    return rows


class MariaDBInspector:
    """Read-only information_schema inspector for one explicitly supplied DB."""

    def __init__(self, connection: Any):
        self.connection = connection
        if getattr(connection, "vendor", "mysql") != "mysql":
            raise ValueError("database-level action inventory requires MariaDB/MySQL")

    def _fetchone(self, sql: str, params: Sequence[Any] = ()) -> Any:
        with self.connection.cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.fetchone()

    def inspect(self, relation: Mapping[str, Any]) -> dict[str, Any]:
        child_table = str(relation["child_table"])
        parent_table = str(relation["parent_table"])
        child_column = str(relation["child_column"])
        parent_column = str(relation["parent_column"])
        for table in (child_table, parent_table):
            if table.startswith(DTF_TABLE_PREFIX):
                raise ValueError("DTF table inventory is forbidden")
            _quote_identifier(table)
        _quote_identifier(child_column)
        _quote_identifier(parent_column)

        child_engine = self._fetchone(
            "SELECT ENGINE FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s",
            (child_table,),
        )
        parent_engine = self._fetchone(
            "SELECT ENGINE FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s",
            (parent_table,),
        )
        fk = self._fetchone(
            "SELECT kcu.CONSTRAINT_NAME, rc.DELETE_RULE "
            "FROM information_schema.KEY_COLUMN_USAGE kcu "
            "JOIN information_schema.REFERENTIAL_CONSTRAINTS rc "
            " ON rc.CONSTRAINT_SCHEMA=kcu.CONSTRAINT_SCHEMA "
            "AND rc.CONSTRAINT_NAME=kcu.CONSTRAINT_NAME "
            "AND rc.TABLE_NAME=kcu.TABLE_NAME "
            "WHERE kcu.CONSTRAINT_SCHEMA=DATABASE() AND kcu.TABLE_NAME=%s "
            "AND kcu.COLUMN_NAME=%s AND kcu.REFERENCED_TABLE_NAME=%s "
            "AND kcu.REFERENCED_COLUMN_NAME=%s ORDER BY kcu.CONSTRAINT_NAME LIMIT 1",
            (child_table, child_column, parent_table, parent_column),
        )
        orphan_sql = (
            f"SELECT COUNT(*) FROM {_quote_identifier(child_table)} child "
            f"LEFT JOIN {_quote_identifier(parent_table)} parent "
            f"ON child.{_quote_identifier(child_column)}="
            f"parent.{_quote_identifier(parent_column)} "
            f"WHERE child.{_quote_identifier(child_column)} IS NOT NULL "
            f"AND parent.{_quote_identifier(parent_column)} IS NULL"
        )
        orphan = self._fetchone(orphan_sql)
        show_create = self._fetchone(
            f"SHOW CREATE TABLE {_quote_identifier(child_table)}"
        )
        create_text = str(show_create[1]) if show_create and len(show_create) > 1 else ""
        return {
            "child_engine": str(child_engine[0]) if child_engine else None,
            "parent_engine": str(parent_engine[0]) if parent_engine else None,
            "constraint_name": str(fk[0]) if fk else None,
            "delete_rule": str(fk[1]) if fk else None,
            "orphan_count": int(orphan[0]) if orphan else None,
            "show_create_sha256": hashlib.sha256(create_text.encode()).hexdigest()
            if create_text
            else None,
        }


def enrich_inventory(
    relations: Iterable[Mapping[str, Any]], inspector: Any
) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for relation in relations:
        row = dict(relation)
        row["database"] = dict(inspector.inspect(row))
        enriched.append(row)
    return enriched


def assess_db_cascade(relation: Mapping[str, Any]) -> dict[str, Any]:
    database = dict(relation.get("database") or {})
    blockers: list[str] = []
    if relation.get("on_delete") != "CASCADE":
        blockers.append("source_on_delete_is_not_CASCADE")
    if not relation.get("db_constraint", False):
        blockers.append("django_db_constraint_false")
    if str(database.get("child_engine") or "").lower() != "innodb":
        blockers.append("child_engine_not_innodb")
    if str(database.get("parent_engine") or "").lower() != "innodb":
        blockers.append("parent_engine_not_innodb")
    if not database.get("constraint_name"):
        blockers.append("real_fk_missing")
    if database.get("orphan_count") is None:
        blockers.append("orphan_scan_missing")
    elif int(database["orphan_count"]) != 0:
        blockers.append("orphan_rows_present")
    if relation.get("mandatory_delete_receivers"):
        blockers.append("mandatory_delete_signals_present")
    if relation.get("soft_delete_fields"):
        blockers.append("soft_delete_contract_present")
    if relation.get("python_on_delete_siblings"):
        blockers.append("mixed_on_delete_models.E050")
    if relation.get("model_delete_override"):
        blockers.append("child_delete_override_present")

    rollback_ready = bool(
        database.get("constraint_name") and database.get("show_create_sha256")
    )
    if not rollback_ready:
        blockers.append("rollback_evidence_missing")
    rollback = {
        "ready": rollback_ready,
        "strategy": "reverse_AlterField_and_restore_captured_fk",
        "required_evidence": ["constraint_name", "show_create_sha256", "backup"],
    }
    decision = "GO" if not blockers else "NO-GO"
    return {
        "decision": decision,
        "decision_ru": (
            "Допустимо только после отдельного review и миграции"
            if decision == "GO"
            else "Не внедрять: сначала закрыть все блокеры"
        ),
        "blockers": sorted(set(blockers)),
        "database": database,
        "rollback": rollback,
    }


def validate_disposable_endpoint(
    *, host: str | None, unix_socket: str | None
) -> None:
    """Reject every endpoint except a local socket or loopback address."""

    normalized_host = (host or "").strip().lower()
    if unix_socket:
        if normalized_host and normalized_host not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("disposable experiment requires local MariaDB")
        return
    if not normalized_host:
        raise ValueError("disposable experiment requires a socket or loopback host")
    if normalized_host == "localhost":
        return
    try:
        address = ipaddress.ip_address(normalized_host)
    except ValueError as exc:
        raise ValueError("disposable experiment requires local MariaDB") from exc
    if not address.is_loopback:
        raise ValueError("disposable experiment requires local MariaDB")


def validate_live_database_alias(alias: str | None) -> str:
    """Return the only alias allowed for live, read-only inventory.

    The inventory must never be able to inspect DTF or another configured
    database by accepting a caller-selected Django connection alias.  Case
    and surrounding whitespace are harmless; every other value fails before
    Django's ``connections`` registry is touched.
    """

    normalized = str(alias or "").strip().casefold()
    if normalized != "default":
        raise ValueError("live inventory requires the literal default database alias")
    return normalized


def render_json_report(
    *,
    inventory: Sequence[Mapping[str, Any]],
    retention_decision: Mapping[str, Any],
    experiment: Mapping[str, Any] | None,
    output: Any,
) -> None:
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "non-DTF",
        "inventory_count": len(inventory),
        "inventory": list(inventory),
        "retention_graph": dict(retention_decision),
        "experiment": dict(experiment or {"status": "not_run"}),
    }
    json.dump(report, output, ensure_ascii=False, indent=2, sort_keys=True)
    output.write("\n")


def _execute(cursor: Any, sql: str, params: Sequence[Any] = ()) -> None:
    cursor.execute(sql, params)


def _count(cursor: Any, table: str) -> int:
    _execute(cursor, f"SELECT COUNT(*) FROM {_quote_identifier(table)}")
    row = cursor.fetchone()
    return int(row[0])


def _orphan_count(cursor: Any, child_table: str, parent_table: str) -> int:
    _execute(
        cursor,
        f"SELECT COUNT(*) FROM {_quote_identifier(child_table)} child "
        f"LEFT JOIN {_quote_identifier(parent_table)} parent "
        "ON child.parent_id=parent.id "
        "WHERE child.parent_id IS NOT NULL AND parent.id IS NULL",
    )
    row = cursor.fetchone()
    return int(row[0])


def _fk_rule(cursor: Any, database: str, table: str) -> str | None:
    _execute(
        cursor,
        "SELECT DELETE_RULE FROM information_schema.REFERENTIAL_CONSTRAINTS "
        "WHERE CONSTRAINT_SCHEMA=%s AND TABLE_NAME=%s "
        "ORDER BY CONSTRAINT_NAME LIMIT 1",
        (database, table),
    )
    row = cursor.fetchone()
    return str(row[0]) if row else None


def _benchmark_delete(
    connection: Any,
    *,
    parent_table: str,
    child_table: str,
    sessions: int,
    batch_size: int,
    python_side: bool,
) -> float:
    started = time.perf_counter()
    with connection.cursor() as cursor:
        for first in range(1, sessions + 1, batch_size):
            last = min(sessions, first + batch_size - 1)
            if python_side:
                _execute(
                    cursor,
                    f"DELETE FROM {_quote_identifier(child_table)} "
                    "WHERE parent_id BETWEEN %s AND %s",
                    (first, last),
                )
            _execute(
                cursor,
                f"DELETE FROM {_quote_identifier(parent_table)} "
                "WHERE id BETWEEN %s AND %s",
                (first, last),
            )
            connection.commit()
    return time.perf_counter() - started


def run_disposable_experiment(
    connection_factory: Callable[[str | None], Any],
    *,
    sessions: int = 250,
    events_per_session: int = 8,
    batch_size: int = 50,
) -> dict[str, Any]:
    """Run the retention benchmark in a generated database and clean it up."""

    if sessions < 1 or events_per_session < 1 or batch_size < 1:
        raise ValueError("experiment sizes must be positive")
    admin = connection_factory(None)
    database = f"twc_dj61_db_actions_{secrets.token_hex(6)}"
    connection = None
    cleanup_error: Exception | None = None
    try:
        with admin.cursor() as cursor:
            _execute(cursor, "SELECT VERSION()")
            version_row = cursor.fetchone()
            version = str(version_row[0]) if version_row else ""
            if "mariadb" not in version.lower():
                raise RuntimeError(f"disposable experiment requires MariaDB, got {version}")
            _execute(
                cursor,
                f"CREATE DATABASE {_quote_identifier(database)} "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci",
            )
            admin.commit()
        connection = connection_factory(database)
        with connection.cursor() as cursor:
            _execute(cursor, f"USE {_quote_identifier(database)}")
            _execute(
                cursor,
                "CREATE TABLE retention_parent_py ("
                "id BIGINT PRIMARY KEY) ENGINE=InnoDB",
            )
            _execute(
                cursor,
                "CREATE TABLE retention_event_py ("
                "id BIGINT PRIMARY KEY, parent_id BIGINT NOT NULL, "
                "CONSTRAINT fk_retention_event_py FOREIGN KEY (parent_id) "
                "REFERENCES retention_parent_py(id) ON DELETE RESTRICT) ENGINE=InnoDB",
            )
            _execute(
                cursor,
                "CREATE TABLE retention_parent_db ("
                "id BIGINT PRIMARY KEY) ENGINE=InnoDB",
            )
            _execute(
                cursor,
                "CREATE TABLE retention_event_db ("
                "id BIGINT PRIMARY KEY, parent_id BIGINT NOT NULL, "
                "CONSTRAINT fk_retention_event_db FOREIGN KEY (parent_id) "
                "REFERENCES retention_parent_db(id) ON DELETE CASCADE) ENGINE=InnoDB",
            )
            parents = [(index,) for index in range(1, sessions + 1)]
            events = [
                (parent_id * events_per_session + offset, parent_id)
                for parent_id in range(1, sessions + 1)
                for offset in range(events_per_session)
            ]
            cursor.executemany("INSERT INTO retention_parent_py(id) VALUES (%s)", parents)
            cursor.executemany(
                "INSERT INTO retention_event_py(id,parent_id) VALUES (%s,%s)", events
            )
            cursor.executemany("INSERT INTO retention_parent_db(id) VALUES (%s)", parents)
            cursor.executemany(
                "INSERT INTO retention_event_db(id,parent_id) VALUES (%s,%s)", events
            )
            connection.commit()
            orphan_counts = {
                "python_graph": _orphan_count(
                    cursor, "retention_event_py", "retention_parent_py"
                ),
                "db_graph": _orphan_count(
                    cursor, "retention_event_db", "retention_parent_db"
                ),
            }
            if any(orphan_counts.values()):
                raise RuntimeError(f"generated retention graph has orphans: {orphan_counts}")

        python_seconds = _benchmark_delete(
            connection,
            parent_table="retention_parent_py",
            child_table="retention_event_py",
            sessions=sessions,
            batch_size=batch_size,
            python_side=True,
        )
        db_seconds = _benchmark_delete(
            connection,
            parent_table="retention_parent_db",
            child_table="retention_event_db",
            sessions=sessions,
            batch_size=batch_size,
            python_side=False,
        )
        with connection.cursor() as cursor:
            py_rule = _fk_rule(cursor, database, "retention_event_py")
            db_rule = _fk_rule(cursor, database, "retention_event_db")
            py_remaining = _count(cursor, "retention_parent_py") + _count(
                cursor, "retention_event_py"
            )
            db_remaining = _count(cursor, "retention_parent_db") + _count(
                cursor, "retention_event_db"
            )

            _execute(
                cursor,
                "CREATE TABLE retention_rollback_parent (id INT PRIMARY KEY) ENGINE=InnoDB",
            )
            _execute(
                cursor,
                "CREATE TABLE retention_rollback_child ("
                "id INT PRIMARY KEY, parent_id INT NOT NULL, "
                "CONSTRAINT fk_retention_rollback FOREIGN KEY(parent_id) "
                "REFERENCES retention_rollback_parent(id) ON DELETE CASCADE) ENGINE=InnoDB",
            )
            _execute(cursor, "INSERT INTO retention_rollback_parent VALUES (1)")
            _execute(cursor, "INSERT INTO retention_rollback_child VALUES (1,1)")
            connection.commit()
            _execute(cursor, "DELETE FROM retention_rollback_parent WHERE id=1")
            transactional_delete_counts = (
                _count(cursor, "retention_rollback_parent"),
                _count(cursor, "retention_rollback_child"),
            )
            connection.rollback()
            rollback_counts = (
                _count(cursor, "retention_rollback_parent"),
                _count(cursor, "retention_rollback_child"),
            )
            _execute(
                cursor,
                "ALTER TABLE retention_event_db DROP FOREIGN KEY fk_retention_event_db",
            )
            _execute(
                cursor,
                "ALTER TABLE retention_event_db ADD CONSTRAINT fk_retention_event_db "
                "FOREIGN KEY(parent_id) REFERENCES retention_parent_db(id) ON DELETE RESTRICT",
            )
            connection.commit()
            reverse_rule = _fk_rule(cursor, database, "retention_event_db")

        return {
            "status": "passed",
            "version": version,
            "database": database,
            "sessions": sessions,
            "events_per_session": events_per_session,
            "batch_size": batch_size,
            "python_seconds": round(python_seconds, 6),
            "db_cascade_seconds": round(db_seconds, 6),
            "speedup_ratio": round(python_seconds / db_seconds, 3)
            if db_seconds
            else None,
            "fk_rules": {"python": py_rule, "db_cascade": db_rule},
            "django_db_cascade_operation": "CASCADE",
            "orphan_counts_before_delete": orphan_counts,
            "remaining_rows": {"python_graph": py_remaining, "db_graph": db_remaining},
            "rollback": {
                "transactional_delete_before_rollback": transactional_delete_counts,
                "transactional_delete_after_rollback": rollback_counts,
                "ddl_reverse_rule": reverse_rule,
                "verified": transactional_delete_counts == (0, 0)
                and rollback_counts == (1, 1)
                and reverse_rule == "RESTRICT",
            },
            "delete_signals": {
                "project_retention_model": "none mandatory (static inventory)",
                "database_cascade_skips_child_signals": True,
            },
            # Returning this result is possible only after the ``finally``
            # cleanup below has completed successfully; cleanup failures are
            # raised and never produce a passing report.
            "cleanup_verified": True,
        }
    finally:
        if connection is not None:
            try:
                connection.close()
            except Exception as exc:  # pragma: no cover - defensive cleanup
                cleanup_error = exc
        try:
            with admin.cursor() as cursor:
                _execute(cursor, f"DROP DATABASE IF EXISTS {_quote_identifier(database)}")
                admin.commit()
                _execute(
                    cursor,
                    "SELECT SCHEMA_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME=%s",
                    (database,),
                )
                if cursor.fetchone() is not None:
                    raise RuntimeError("generated disposable database still exists")
        except Exception as exc:
            cleanup_error = cleanup_error or exc
        try:
            admin.close()
        except Exception as exc:  # pragma: no cover
            cleanup_error = cleanup_error or exc
        if cleanup_error is not None:
            raise RuntimeError("disposable MariaDB cleanup failed") from cleanup_error


def _load_django() -> None:
    sys.path.insert(0, str(PROJECT_ROOT / "twocomms"))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "twocomms.settings")
    import django

    django.setup()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    inventory = subparsers.add_parser("inventory")
    inventory.add_argument("--database-alias", default="default")
    inventory.add_argument(
        "--live",
        action="store_true",
        help="read-only MariaDB information_schema facts from the configured alias",
    )
    inventory.add_argument("--output", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "inventory":
        _load_django()
        relations = collect_static_inventory()
        if args.live:
            database_alias = validate_live_database_alias(args.database_alias)
            from django.db import connections

            relations = enrich_inventory(
                relations, MariaDBInspector(connections[database_alias])
            )
        target = next(
            row for row in relations if row["field_label"] == RETENTION_FIELD_LABEL
        )
        decision = assess_db_cascade(target)
        output = args.output.open("w", encoding="utf-8") if args.output else sys.stdout
        try:
            render_json_report(
                inventory=relations,
                retention_decision=decision,
                experiment=None,
                output=output,
            )
        finally:
            if args.output:
                output.close()
        return 0
    raise AssertionError(f"unsupported command: {args.command}")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
