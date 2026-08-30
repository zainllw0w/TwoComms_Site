from importlib import import_module
from types import SimpleNamespace
from unittest.mock import Mock

from django.db import migrations, models
from django.test import SimpleTestCase


class Gemini0177MigrationRecoveryTests(SimpleTestCase):
    def test_partial_ddl_resume_adds_only_missing_objects_and_is_idempotent(self):
        migration = import_module(
            "management.migrations.0177_gemini_adaptive_routing"
        )
        grouped = {}
        for app_label, model_name, field_name in migration.FIELD_SPECS:
            grouped.setdefault((app_label, model_name), []).append(field_name)

        model_map = {}
        columns = {}
        constraints = {}
        for key, names in grouped.items():
            table = f"{key[0]}_{key[1].lower()}"
            fields = {
                name: SimpleNamespace(name=name, column=name)
                for name in names
            }
            indexes = []
            model_constraints = []
            if key[1] == "InstagramBotMessage":
                indexes = [
                    models.Index(
                        fields=["private_media_delete_after"],
                        name="mgmt_igmsg_media_del",
                    ),
                    models.Index(
                        fields=["private_media_use_until"],
                        name="mgmt_igmsg_media_use",
                    ),
                ]
                model_constraints = [
                    models.CheckConstraint(
                        condition=models.Q(private_media_state__in=[
                            "", "active", "deleted",
                        ]),
                        name="mgmt_igmsg_media_state",
                    )
                ]
            model_map[key] = SimpleNamespace(
                _meta=SimpleNamespace(
                    db_table=table,
                    get_field=lambda name, fields=fields: fields[name],
                    indexes=indexes,
                    constraints=model_constraints,
                )
            )
            # Simulate MariaDB having committed only the first field before a
            # process crash, with no migration recorder row.
            columns[table] = {names[0]}
            constraints[table] = {}

        app_registry = Mock()
        app_registry.get_model.side_effect = lambda app, model: model_map[(app, model)]
        schema_editor = Mock()
        schema_editor.connection.vendor = "sqlite"
        schema_editor.connection.introspection.table_names.return_value = list(columns)
        cursor = Mock()
        schema_editor.connection.cursor.return_value.__enter__ = Mock(
            return_value=cursor
        )
        schema_editor.connection.cursor.return_value.__exit__ = Mock(
            return_value=False
        )
        schema_editor.connection.introspection.get_table_description.side_effect = (
            lambda _cursor, table: [
                SimpleNamespace(name=name) for name in sorted(columns[table])
            ]
        )
        schema_editor.connection.introspection.get_constraints.side_effect = (
            lambda _cursor, table: dict(constraints[table])
        )

        def add_field(model, field):
            columns[model._meta.db_table].add(field.column)

        def add_index(model, index):
            constraints[model._meta.db_table][index.name] = {"index": True}

        def add_constraint(model, constraint):
            constraints[model._meta.db_table][constraint.name] = {"check": True}

        schema_editor.add_field.side_effect = add_field
        schema_editor.add_index.side_effect = add_index
        schema_editor.add_constraint.side_effect = add_constraint

        migration.ensure_0177_schema(app_registry, schema_editor)
        first_field_calls = schema_editor.add_field.call_count
        self.assertGreater(first_field_calls, 0)
        self.assertEqual(schema_editor.add_index.call_count, 2)
        self.assertEqual(schema_editor.add_constraint.call_count, 1)

        migration.ensure_0177_schema(app_registry, schema_editor)

        self.assertEqual(schema_editor.add_field.call_count, first_field_calls)
        self.assertEqual(schema_editor.add_index.call_count, 2)
        self.assertEqual(schema_editor.add_constraint.call_count, 1)

    def test_migration_separates_state_from_resumable_non_atomic_ddl(self):
        migration = import_module(
            "management.migrations.0177_gemini_adaptive_routing"
        )

        self.assertFalse(migration.Migration.atomic)
        self.assertIsInstance(
            migration.Migration.operations[0],
            migrations.SeparateDatabaseAndState,
        )
        self.assertIsInstance(
            migration.Migration.operations[1],
            migrations.RunPython,
        )
        self.assertFalse(migration.Migration.operations[1].reversible)
        with self.assertRaises(NotImplementedError):
            migration.Migration.operations[1].database_backwards(
                "management",
                Mock(),
                Mock(),
                Mock(),
            )

    def test_same_name_incompatible_index_or_constraint_is_rejected(self):
        from management.migrations._resumable_schema import ensure_additive_schema

        fields = {
            "state": SimpleNamespace(
                name="state",
                column="state",
                get_internal_type=lambda: "CharField",
                null=False,
                max_length=20,
            ),
        }
        index = models.Index(fields=["state"], name="test_state_idx")
        constraint = models.CheckConstraint(
            condition=models.Q(state__in=["", "active"]),
            name="test_state_check",
        )
        model = SimpleNamespace(
            _meta=SimpleNamespace(
                db_table="management_test_state",
                get_field=lambda name: fields[name],
                indexes=[index],
                constraints=[constraint],
            )
        )
        registry = Mock()
        registry.get_model.return_value = model
        editor = Mock()
        editor.connection.vendor = "sqlite"
        editor.connection.introspection.table_names.return_value = [
            model._meta.db_table
        ]
        cursor = Mock()
        editor.connection.cursor.return_value.__enter__ = Mock(return_value=cursor)
        editor.connection.cursor.return_value.__exit__ = Mock(return_value=False)
        editor.connection.introspection.get_table_description.return_value = [
            SimpleNamespace(name="state")
        ]

        editor.connection.introspection.get_constraints.return_value = {
            "test_state_idx": {
                "index": True,
                "unique": False,
                "columns": ["wrong_column"],
            },
        }
        with self.assertRaisesRegex(RuntimeError, "test_state_idx has columns"):
            ensure_additive_schema(
                registry,
                editor,
                field_specs=(("management", "TestState", "state"),),
                index_specs=(("management", "TestState", "test_state_idx"),),
            )

        editor.connection.introspection.get_constraints.return_value = {
            "test_state_idx": {
                "index": True,
                "unique": False,
                "columns": ["state"],
            },
            "test_state_check": {
                "check": False,
                "columns": ["state"],
            },
        }
        with self.assertRaisesRegex(RuntimeError, "not a check constraint"):
            ensure_additive_schema(
                registry,
                editor,
                field_specs=(("management", "TestState", "state"),),
                index_specs=(("management", "TestState", "test_state_idx"),),
                constraint_specs=((
                    "management", "TestState", "test_state_check",
                ),),
            )
