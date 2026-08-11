"""Guarded data merge for a split catalog schema.

The canonical application owns the current tables.  A legacy table prefix is
accepted only as runtime input so the retired identity never becomes part of
the tracked application contract.  The merge is deliberately conservative:
missing rows are copied, expected source-of-truth fields are reconciled, and
unexpected shared-column conflicts stop the run before a destructive phase.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping, Sequence

from django.apps import apps
from django.db import connections, transaction


class SchemaMergeError(RuntimeError):
    """Raised when the two physical schemas cannot be merged safely."""


VOLATILE_COLUMNS = frozenset({"created_at", "updated_at"})
SCHEMA_MERGE_LOCK_NAME = "twocomms:product-catalog-schema-merge"


@dataclass(frozen=True)
class TablePair:
    model_label: str
    current_table: str
    legacy_table: str


def schema_merge_locked(connection_alias: str = "default") -> bool:
    """Return whether another connection owns the catalog merge lock."""

    connection = connections[connection_alias]
    if connection.vendor != "mysql":
        return False
    with connection.cursor() as cursor:
        cursor.execute("SELECT IS_USED_LOCK(%s)", [SCHEMA_MERGE_LOCK_NAME])
        row = cursor.fetchone()
    return bool(row and row[0] is not None)


def compare_rows(
    legacy_rows: Sequence[Mapping[str, Any]],
    current_rows: Sequence[Mapping[str, Any]],
    columns: Iterable[str],
    *,
    primary_key: str = "id",
    ignored_columns: Iterable[str] = (),
    authoritative_columns: Iterable[str] = (),
    strict_conflicts: bool = False,
) -> dict[str, Any]:
    """Compare rows by primary key and return a deterministic merge plan.

    ``authoritative_columns`` are reported as updates rather than conflicts;
    all other shared-column differences are returned in ``conflicts``.  The
    caller decides whether to apply those updates after validating the full
    manifest.
    """

    shared = tuple(columns)
    ignored = set(ignored_columns)
    authoritative = set(authoritative_columns)
    old_by_id = {row.get(primary_key): row for row in legacy_rows}
    current_by_id = {row.get(primary_key): row for row in current_rows}
    if None in old_by_id or None in current_by_id:
        raise SchemaMergeError(f"{primary_key} is required for every merge row")

    missing_ids = sorted(set(old_by_id) - set(current_by_id))
    current_only_ids = sorted(set(current_by_id) - set(old_by_id))
    update_columns: dict[str, list[str]] = {}
    conflicts: list[dict[str, Any]] = []

    for row_id in sorted(set(old_by_id) & set(current_by_id)):
        old = old_by_id[row_id]
        current = current_by_id[row_id]
        updates: list[str] = []
        for column in shared:
            if column == primary_key or column in ignored:
                continue
            if old.get(column) == current.get(column):
                continue
            updates.append(column)
            if strict_conflicts and column not in authoritative:
                conflicts.append(
                    {
                        "id": row_id,
                        "column": column,
                        "legacy": old.get(column),
                        "current": current.get(column),
                    }
                )
        if updates:
            update_columns[str(row_id)] = sorted(updates)

    return {
        "missing_ids": missing_ids,
        "current_only_ids": current_only_ids,
        "update_ids": sorted(int(row_id) for row_id in update_columns),
        "update_columns": update_columns,
        "conflicts": conflicts,
    }


def dependency_order(connection, pairs: Sequence[Mapping[str, Any] | TablePair]) -> list[str]:
    """Return current tables in parent-before-child foreign-key order."""

    tables = {
        pair.current_table if isinstance(pair, TablePair) else str(pair["current_table"])
        for pair in pairs
    }
    parents: dict[str, set[str]] = {table: set() for table in tables}
    cursor_context = connection.cursor()
    if hasattr(type(cursor_context), "__enter__"):
        with cursor_context as cursor:
            for table in tables:
                constraints = connection.introspection.get_constraints(cursor, table)
                for detail in constraints.values():
                    foreign_key = detail.get("foreign_key")
                    if not foreign_key:
                        continue
                    parent = str(foreign_key[0])
                    if parent in tables and parent != table:
                        parents[table].add(parent)
    else:  # tiny fake connections used by the planner unit tests
        cursor = cursor_context
        for table in tables:
            constraints = connection.introspection.get_constraints(cursor, table)
            for detail in constraints.values():
                foreign_key = detail.get("foreign_key")
                if not foreign_key:
                    continue
                parent = str(foreign_key[0])
                if parent in tables and parent != table:
                    parents[table].add(parent)

    ordered: list[str] = []
    temporary: set[str] = set()
    visited: set[str] = set()

    def visit(table: str) -> None:
        if table in visited:
            return
        if table in temporary:
            raise SchemaMergeError(f"catalog foreign-key cycle includes {table}")
        temporary.add(table)
        for parent in sorted(parents[table]):
            visit(parent)
        temporary.remove(table)
        visited.add(table)
        ordered.append(table)

    for table in sorted(tables):
        visit(table)
    return ordered


def _primary_key_columns(connection, table: str) -> tuple[str, ...]:
    with connection.cursor() as cursor:
        constraints = connection.introspection.get_constraints(cursor, table)
    primary = [
        tuple(detail.get("columns") or ())
        for detail in constraints.values()
        if detail.get("primary_key")
    ]
    if len(primary) != 1 or len(primary[0]) != 1:
        raise SchemaMergeError(f"{table} must have exactly one scalar primary key")
    return primary[0]


def _constraint_signature(
    connection,
    table: str,
    *,
    referenced_table_map: Mapping[str, str] | None = None,
) -> set[tuple[Any, ...]]:
    with connection.cursor() as cursor:
        constraints = connection.introspection.get_constraints(cursor, table)
    signature = set()
    referenced_table_map = referenced_table_map or {}
    for name, detail in constraints.items():
        if detail.get("primary_key"):
            continue
        fk = detail.get("foreign_key")
        if fk:
            fk = (referenced_table_map.get(str(fk[0]), str(fk[0])), str(fk[1]))
        signature.add(
            (
                bool(detail.get("unique")),
                bool(detail.get("index")),
                tuple(detail.get("columns") or ()),
                tuple(fk or ()),
            )
        )
    return signature


def _column_signatures(connection, table: str) -> dict[str, tuple[Any, ...]]:
    with connection.cursor() as cursor:
        description = connection.introspection.get_table_description(cursor, table)
    result = {}
    for column in description:
        result[str(column.name)] = (
            connection.introspection.get_field_type(column.type_code, column),
            getattr(column, "internal_size", None),
            getattr(column, "precision", None),
            getattr(column, "scale", None),
            bool(getattr(column, "null_ok", False)),
            getattr(column, "collation", None),
        )
    return result


def build_table_pairs(
    connection,
    *,
    current_app_label: str,
    legacy_table_prefix: str,
) -> tuple[TablePair, ...]:
    """Build pairs from current Django model state and physical tables."""

    if not legacy_table_prefix or legacy_table_prefix == current_app_label:
        raise SchemaMergeError("legacy table prefix must be explicit and distinct")
    actual = set(connection.introspection.table_names())
    config = apps.get_app_config(current_app_label)
    pairs: list[TablePair] = []
    prefix = f"{current_app_label}_"
    for model in config.get_models():
        current = model._meta.db_table
        if not current.startswith(prefix):
            raise SchemaMergeError(f"unexpected current catalog table: {current}")
        legacy = f"{legacy_table_prefix}_{current[len(prefix):]}"
        if current in actual and legacy in actual:
            pairs.append(TablePair(model._meta.label, current, legacy))
        elif legacy in actual:
            raise SchemaMergeError(f"current table is missing for {legacy}: {current}")
    expected_legacy = {pair.legacy_table for pair in pairs}
    unexpected_legacy = sorted(
        table
        for table in actual
        if table.startswith(f"{legacy_table_prefix}_") and table not in expected_legacy
    )
    if unexpected_legacy:
        raise SchemaMergeError(
            "unexpected legacy-prefixed tables: " + ", ".join(unexpected_legacy)
        )
    if not pairs:
        raise SchemaMergeError("no paired catalog tables found")
    return tuple(sorted(pairs, key=lambda pair: pair.current_table))


class SchemaMerge:
    """Plan and apply a paired-table merge, with a final legacy cleanup."""

    def __init__(
        self,
        *,
        legacy_table_prefix: str,
        legacy_app_label: str | None = None,
        current_app_label: str = "product_catalog",
        connection_alias: str = "default",
        saved_pairs: Sequence[Mapping[str, Any]] | None = None,
    ) -> None:
        if not legacy_table_prefix or legacy_table_prefix == current_app_label:
            raise SchemaMergeError("legacy table prefix must be explicit and distinct")
        self.connection = connections[connection_alias]
        self.connection_alias = connection_alias
        self.legacy_table_prefix = legacy_table_prefix
        self.legacy_app_label = legacy_app_label or legacy_table_prefix
        self.current_app_label = current_app_label
        if self.connection.vendor != "mysql":
            raise SchemaMergeError("catalog schema merge requires MySQL")
        if saved_pairs is None:
            self.pairs = build_table_pairs(
                self.connection,
                current_app_label=current_app_label,
                legacy_table_prefix=legacy_table_prefix,
            )
        else:
            self.pairs = tuple(
                TablePair(
                    str(item["model_label"]),
                    str(item["current_table"]),
                    str(item["legacy_table"]),
                )
                for item in saved_pairs
            )
            actual = set(self.connection.introspection.table_names())
            missing_current = sorted(
                pair.current_table for pair in self.pairs if pair.current_table not in actual
            )
            if missing_current:
                raise SchemaMergeError(
                    "canonical tables disappeared during resume: "
                    + ", ".join(missing_current)
                )
        self.pair_by_current = {pair.current_table: pair for pair in self.pairs}

    def _quote(self, table: str) -> str:
        return self.connection.ops.quote_name(table)

    def _rows(self, table: str) -> tuple[list[str], list[dict[str, Any]]]:
        with self.connection.cursor() as cursor:
            cursor.execute(f"SELECT * FROM {self._quote(table)}")
            columns = [item[0] for item in cursor.description]
            rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
        return columns, rows

    def _engine(self, table: str) -> str:
        with self.connection.cursor() as cursor:
            cursor.execute(
                "SELECT ENGINE FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s",
                [table],
            )
            row = cursor.fetchone()
        return str(row[0] if row else "").upper()

    def _external_legacy_references(self) -> list[dict[str, str]]:
        refs: list[dict[str, str]] = []
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT TABLE_NAME, CONSTRAINT_NAME, REFERENCED_TABLE_NAME
                FROM information_schema.KEY_COLUMN_USAGE
                WHERE CONSTRAINT_SCHEMA = DATABASE()
                  AND REFERENCED_TABLE_NAME IS NOT NULL
                """
            )
            for table, constraint, referenced in cursor.fetchall():
                if str(referenced).startswith(f"{self.legacy_table_prefix}_") and str(table) not in {
                    pair.legacy_table for pair in self.pairs
                }:
                    refs.append(
                        {
                            "table": str(table),
                            "constraint": str(constraint),
                            "referenced_table": str(referenced),
                        }
                    )
        return refs

    def preflight(self) -> dict[str, Any]:
        order = dependency_order(self.connection, self.pairs)
        if external := self._external_legacy_references():
            raise SchemaMergeError(
                "external foreign keys reference legacy catalog tables: "
                + ", ".join(item["table"] + "." + item["constraint"] for item in external)
            )

        manifest: list[dict[str, Any]] = []
        table_map = {pair.legacy_table: pair.current_table for pair in self.pairs}
        for pair in self.pairs:
            for table in (pair.legacy_table, pair.current_table):
                if self._engine(table) != "INNODB":
                    raise SchemaMergeError(f"catalog table must use InnoDB: {table}")
            legacy_columns, legacy_rows = self._rows(pair.legacy_table)
            current_columns, current_rows = self._rows(pair.current_table)
            legacy_pk = _primary_key_columns(self.connection, pair.legacy_table)
            current_pk = _primary_key_columns(self.connection, pair.current_table)
            if legacy_pk != current_pk:
                raise SchemaMergeError(
                    f"primary key mismatch for {pair.current_table}: {legacy_pk} != {current_pk}"
                )
            if set(legacy_columns) - set(current_columns):
                raise SchemaMergeError(
                    f"current table {pair.current_table} is missing columns "
                    f"{sorted(set(legacy_columns) - set(current_columns))}"
                )
            legacy_signatures = _column_signatures(self.connection, pair.legacy_table)
            current_signatures = _column_signatures(self.connection, pair.current_table)
            incompatible_columns = sorted(
                column
                for column in legacy_columns
                if legacy_signatures[column] != current_signatures.get(column)
            )
            if incompatible_columns:
                raise SchemaMergeError(
                    f"column shape mismatch for {pair.current_table}: "
                    + ", ".join(incompatible_columns)
                )
            if _constraint_signature(
                self.connection,
                pair.legacy_table,
                referenced_table_map=table_map,
            ) != _constraint_signature(
                self.connection,
                pair.current_table,
            ):
                raise SchemaMergeError(f"constraint shape mismatch for {pair.current_table}")
            model_name = pair.model_label.rsplit(".", 1)[-1]
            authoritative = ("source",) if model_name == "ProductInventoryPolicy" else ()
            comparison = compare_rows(
                legacy_rows,
                current_rows,
                legacy_columns,
                primary_key=legacy_pk[0],
                ignored_columns=VOLATILE_COLUMNS,
                authoritative_columns=authoritative,
                strict_conflicts=True,
            )
            if comparison["conflicts"]:
                raise SchemaMergeError(
                    f"unexpected shared-row conflicts for {pair.current_table}: "
                    + repr(comparison["conflicts"][:8])
                )
            manifest.append(
                {
                    **asdict(pair),
                    "legacy_columns": legacy_columns,
                    "current_columns": current_columns,
                    "legacy_count": len(legacy_rows),
                    "current_count": len(current_rows),
                    "comparison": comparison,
                }
            )
        return {
            "current_app_label": self.current_app_label,
            "legacy_table_prefix": self.legacy_table_prefix,
            "order": order,
            "pairs": manifest,
            "external_legacy_references": [],
        }

    def _insert_rows(self, pair: TablePair, row_ids: Sequence[Any]) -> int:
        if not row_ids:
            return 0
        legacy_columns, legacy_rows = self._rows(pair.legacy_table)
        current_columns, _ = self._rows(pair.current_table)
        primary_key = _primary_key_columns(self.connection, pair.current_table)[0]
        by_id = {row[primary_key]: row for row in legacy_rows}
        columns = [column for column in legacy_columns if column in current_columns]
        rendered_columns = ", ".join(self._quote(column) for column in columns)
        placeholders = ", ".join(["%s"] * len(columns))
        sql = (
            f"INSERT INTO {self._quote(pair.current_table)} ({rendered_columns}) "
            f"VALUES ({placeholders})"
        )
        inserted = 0
        with self.connection.cursor() as cursor:
            for row_id in row_ids:
                row = by_id[row_id]
                cursor.execute(sql, [row.get(column) for column in columns])
                inserted += 1
        return inserted

    def _update_authoritative_rows(self, pair: TablePair, comparison: Mapping[str, Any]) -> int:
        update_columns = comparison.get("update_columns") or {}
        if not update_columns:
            return 0
        primary_key = _primary_key_columns(self.connection, pair.current_table)[0]
        _, legacy_rows = self._rows(pair.legacy_table)
        old_by_id = {row[primary_key]: row for row in legacy_rows}
        count = 0
        with self.connection.cursor() as cursor:
            for raw_id, columns in update_columns.items():
                row_id = int(raw_id)
                assignments = ", ".join(f"{self._quote(column)} = %s" for column in columns)
                sql = (
                    f"UPDATE {self._quote(pair.current_table)} SET {assignments} "
                    f"WHERE {self._quote(primary_key)} = %s"
                )
                cursor.execute(
                    sql,
                    [old_by_id[row_id][column] for column in columns] + [row_id],
                )
                count += cursor.rowcount
        return count

    def _reset_auto_increment(self, table: str) -> None:
        pk = _primary_key_columns(self.connection, table)[0]
        with self.connection.cursor() as cursor:
            cursor.execute(
                f"SELECT COALESCE(MAX({self._quote(pk)}), 0) + 1 FROM {self._quote(table)}"
            )
            next_id = int(cursor.fetchone()[0])
            cursor.execute(f"ALTER TABLE {self._quote(table)} AUTO_INCREMENT = {next_id}")

    def merge_rows(self, preflight: Mapping[str, Any], checkpoint=None) -> dict[str, Any]:
        """Copy/reconcile rows in dependency order and return a report."""

        by_table = {item["current_table"]: item for item in preflight["pairs"]}
        inserted = 0
        updated = 0
        for table in preflight["order"]:
            item = by_table[table]
            pair = TablePair(item["model_label"], item["current_table"], item["legacy_table"])
            comparison = item["comparison"]
            inserted += self._insert_rows(pair, comparison["missing_ids"])
            updated += self._update_authoritative_rows(pair, comparison)
            self._reset_auto_increment(pair.current_table)
            if checkpoint:
                checkpoint({"phase": "rows-merged", "table": table, "inserted": inserted, "updated": updated})
        return {"inserted": inserted, "updated": updated}

    def remap_metadata(self) -> dict[str, int]:
        """Move auth references to canonical ContentTypes/permissions."""

        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import Group, Permission
        from django.contrib.contenttypes.models import ContentType

        legacy_label = self.legacy_app_label
        current_cts = {
            row["model"]: row["id"]
            for row in ContentType.objects.using(self.connection_alias)
            .filter(app_label=self.current_app_label)
            .values("id", "model")
        }
        legacy_cts = list(
            ContentType.objects.using(self.connection_alias)
            .filter(app_label=legacy_label)
            .values("id", "model")
        )
        if not legacy_cts:
            return {"permission_references": 0, "permissions_deleted": 0, "content_types_deleted": 0}
        if any(row["model"] not in current_cts for row in legacy_cts):
            raise SchemaMergeError("a legacy ContentType has no canonical model match")

        legacy_ct_ids = [row["id"] for row in legacy_cts]
        with self.connection.cursor() as cursor:
            cursor.execute(
                "SELECT TABLE_NAME FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() AND COLUMN_NAME = 'content_type_id'"
            )
            content_type_tables = [str(row[0]) for row in cursor.fetchall()]
            for table in content_type_tables:
                if table in {"auth_permission", "django_content_type"}:
                    continue
                placeholders = ", ".join(["%s"] * len(legacy_ct_ids))
                cursor.execute(
                    f"SELECT COUNT(*) FROM {self._quote(table)} "
                    f"WHERE {self._quote('content_type_id')} IN ({placeholders})",
                    legacy_ct_ids,
                )
                if int(cursor.fetchone()[0]):
                    raise SchemaMergeError(
                        f"legacy ContentTypes are still referenced by {table}"
                    )

        old_permissions = list(
            Permission.objects.using(self.connection_alias)
            .filter(content_type_id__in=[row["id"] for row in legacy_cts])
            .values("id", "content_type_id", "codename")
        )
        canonical_permissions = {
            (row["content_type_id"], row["codename"]): row["id"]
            for row in Permission.objects.using(self.connection_alias)
            .filter(content_type_id__in=list(current_cts.values()))
            .values("id", "content_type_id", "codename")
        }
        remapped = 0
        permission_through_models = (
            Group.permissions.through,
            get_user_model().user_permissions.through,
        )
        with transaction.atomic(using=self.connection_alias):
            with self.connection.cursor() as cursor:
                for old in old_permissions:
                    model = next(row["model"] for row in legacy_cts if row["id"] == old["content_type_id"])
                    new_ct = current_cts[model]
                    new_permission = canonical_permissions.get((new_ct, old["codename"]))
                    if new_permission is None:
                        raise SchemaMergeError(
                            f"missing canonical permission for {model}.{old['codename']}"
                        )
                    for through in permission_through_models:
                        table = through._meta.db_table
                        permission_field = next(
                            field
                            for field in through._meta.local_fields
                            if getattr(field.remote_field, "model", None) is Permission
                        )
                        principal_field = next(
                            field
                            for field in through._meta.local_fields
                            if field is not permission_field and field.primary_key is False
                        )
                        permission_column = permission_field.column
                        principal_column = principal_field.column
                        cursor.execute(
                            f"SELECT {self._quote(principal_column)} FROM {self._quote(table)} "
                            f"WHERE {self._quote(permission_column)} = %s",
                            [old["id"]],
                        )
                        principals = {row[0] for row in cursor.fetchall()}
                        if not principals:
                            continue
                        cursor.execute(
                            f"INSERT IGNORE INTO {self._quote(table)} "
                            f"({self._quote(principal_column)}, {self._quote(permission_column)}) "
                            f"SELECT {self._quote(principal_column)}, %s FROM {self._quote(table)} "
                            f"WHERE {self._quote(permission_column)} = %s",
                            [new_permission, old["id"]],
                        )
                        remapped += cursor.rowcount
                        cursor.execute(
                            f"SELECT {self._quote(principal_column)} FROM {self._quote(table)} "
                            f"WHERE {self._quote(permission_column)} = %s",
                            [new_permission],
                        )
                        mapped = {row[0] for row in cursor.fetchall()}
                        if not principals.issubset(mapped):
                            raise SchemaMergeError(
                                f"permission remap invariant failed for {table}"
                            )
                        cursor.execute(
                            f"DELETE FROM {self._quote(table)} "
                            f"WHERE {self._quote(permission_column)} = %s",
                            [old["id"]],
                        )
            Permission.objects.using(self.connection_alias).filter(
                id__in=[row["id"] for row in old_permissions]
            ).delete()
            ContentType.objects.using(self.connection_alias).filter(
                id__in=[row["id"] for row in legacy_cts]
            ).delete()
        return {
            "permission_references": remapped,
            "permissions_deleted": len(old_permissions),
            "content_types_deleted": len(legacy_cts),
        }

    def drop_legacy_tables(self, preflight: Mapping[str, Any], checkpoint=None) -> int:
        """Drop old tables only after all row/metadata invariants pass."""

        order = list(reversed(preflight["order"]))
        by_table = {item["current_table"]: item for item in preflight["pairs"]}
        dropped = 0
        with self.connection.cursor() as cursor:
            for current_table in order:
                legacy_table = by_table[current_table]["legacy_table"]
                actual = set(self.connection.introspection.table_names())
                if legacy_table in actual:
                    cursor.execute(f"DROP TABLE {self._quote(legacy_table)}")
                    dropped += 1
                if checkpoint:
                    checkpoint({"phase": "legacy-tables-dropped", "table": legacy_table, "dropped": dropped})
        return dropped

    def verify_cleanup(self, post_merge: Mapping[str, Any]) -> dict[str, Any]:
        """Verify the canonical row counts and absence of retired metadata."""

        actual = set(self.connection.introspection.table_names())
        remaining = sorted(
            table for table in actual if table.startswith(f"{self.legacy_table_prefix}_")
        )
        if remaining:
            raise SchemaMergeError(
                "legacy catalog tables remain after cleanup: " + ", ".join(remaining)
            )
        expected_counts = {
            item["current_table"]: int(item["current_count"])
            for item in post_merge["pairs"]
        }
        actual_counts = {}
        for table, expected in expected_counts.items():
            if self._engine(table) != "INNODB":
                raise SchemaMergeError(f"canonical catalog table is not InnoDB: {table}")
            with self.connection.cursor() as cursor:
                cursor.execute(f"SELECT COUNT(*) FROM {self._quote(table)}")
                actual_count = int(cursor.fetchone()[0])
            if actual_count != expected:
                raise SchemaMergeError(
                    f"canonical row count drift for {table}: {actual_count} != {expected}"
                )
            actual_counts[table] = actual_count

        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType
        from django.db.migrations.recorder import MigrationRecorder

        recorder = MigrationRecorder(self.connection)
        if recorder.Migration.objects.using(self.connection_alias).filter(
            app=self.legacy_app_label
        ).exists():
            raise SchemaMergeError("legacy migration rows remain after cleanup")
        if ContentType.objects.using(self.connection_alias).filter(
            app_label=self.legacy_app_label
        ).exists():
            raise SchemaMergeError("legacy ContentTypes remain after cleanup")
        if Permission.objects.using(self.connection_alias).filter(
            content_type__app_label=self.legacy_app_label
        ).exists():
            raise SchemaMergeError("legacy permissions remain after cleanup")
        return {"table_counts": actual_counts, "legacy_metadata": 0}
