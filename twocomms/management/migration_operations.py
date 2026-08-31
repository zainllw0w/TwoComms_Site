"""Retry-idempotent Django migration operations for non-transactional DDL.

MariaDB commits each DDL statement even when Django cannot record the enclosing
migration. These operations reconcile an already-created table/column/index or
constraint on retry while preserving Django's normal state transitions.
"""
from __future__ import annotations

from django.db import migrations


def _table_names(schema_editor) -> set[str]:
    with schema_editor.connection.cursor() as cursor:
        return set(schema_editor.connection.introspection.table_names(cursor))


def _column_names(schema_editor, table: str) -> set[str]:
    with schema_editor.connection.cursor() as cursor:
        description = schema_editor.connection.introspection.get_table_description(
            cursor, table
        )
    names = set()
    for column in description:
        name = getattr(column, "name", None)
        if name is None:
            name = column[0]
        names.add(str(name))
    return names


def _constraint_names(schema_editor, table: str) -> set[str]:
    with schema_editor.connection.cursor() as cursor:
        constraints = schema_editor.connection.introspection.get_constraints(
            cursor, table
        )
    return set(constraints)


class IdempotentCreateModel(migrations.CreateModel):
    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        model = to_state.apps.get_model(app_label, self.name)
        if model._meta.db_table in _table_names(schema_editor):
            return
        return super().database_forwards(
            app_label, schema_editor, from_state, to_state
        )

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        model = from_state.apps.get_model(app_label, self.name)
        if model._meta.db_table not in _table_names(schema_editor):
            return
        return super().database_backwards(
            app_label, schema_editor, from_state, to_state
        )


class IdempotentAddField(migrations.AddField):
    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        model = to_state.apps.get_model(app_label, self.model_name)
        field = model._meta.get_field(self.name)
        if field.column in _column_names(schema_editor, model._meta.db_table):
            return
        return super().database_forwards(
            app_label, schema_editor, from_state, to_state
        )

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        model = from_state.apps.get_model(app_label, self.model_name)
        field = model._meta.get_field(self.name)
        if field.column not in _column_names(schema_editor, model._meta.db_table):
            return
        return super().database_backwards(
            app_label, schema_editor, from_state, to_state
        )


class IdempotentAddIndex(migrations.AddIndex):
    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        model = to_state.apps.get_model(app_label, self.model_name)
        if self.index.name in _constraint_names(schema_editor, model._meta.db_table):
            return
        return super().database_forwards(
            app_label, schema_editor, from_state, to_state
        )

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        model = from_state.apps.get_model(app_label, self.model_name)
        if self.index.name not in _constraint_names(schema_editor, model._meta.db_table):
            return
        return super().database_backwards(
            app_label, schema_editor, from_state, to_state
        )


class IdempotentAddConstraint(migrations.AddConstraint):
    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        model = to_state.apps.get_model(app_label, self.model_name)
        if self.constraint.name in _constraint_names(
            schema_editor, model._meta.db_table
        ):
            return
        return super().database_forwards(
            app_label, schema_editor, from_state, to_state
        )

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        model = from_state.apps.get_model(app_label, self.model_name)
        if self.constraint.name not in _constraint_names(
            schema_editor, model._meta.db_table
        ):
            return
        return super().database_backwards(
            app_label, schema_editor, from_state, to_state
        )


class IdempotentAddExactUniqueConstraint(migrations.AddConstraint):
    """Replay-safe unique constraint that refuses a same-name wrong shape."""

    def _existing(self, schema_editor, model):
        with schema_editor.connection.cursor() as cursor:
            return schema_editor.connection.introspection.get_constraints(
                cursor,
                model._meta.db_table,
            ).get(self.constraint.name)

    def _validate(self, schema_editor, model, existing) -> None:
        expected_columns = [
            str(model._meta.get_field(field_name).column)
            for field_name in self.constraint.fields
        ]
        actual_columns = [str(value) for value in existing.get("columns") or ()]
        if (
            not bool(existing.get("unique"))
            or bool(existing.get("primary_key"))
            or bool(existing.get("check"))
            or existing.get("foreign_key") is not None
            or actual_columns != expected_columns
        ):
            raise RuntimeError(
                "existing unique constraint has unexpected shape: "
                f"{self.constraint.name}"
            )

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        model = to_state.apps.get_model(app_label, self.model_name)
        existing = self._existing(schema_editor, model)
        if existing is not None:
            self._validate(schema_editor, model, existing)
            return
        return super().database_forwards(
            app_label, schema_editor, from_state, to_state
        )

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        model = from_state.apps.get_model(app_label, self.model_name)
        existing = self._existing(schema_editor, model)
        if existing is None:
            return
        self._validate(schema_editor, model, existing)
        return super().database_backwards(
            app_label, schema_editor, from_state, to_state
        )
