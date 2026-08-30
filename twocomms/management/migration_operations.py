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
