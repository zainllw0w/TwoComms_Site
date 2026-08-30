from importlib import import_module
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.db import migrations, models
from django.test import SimpleTestCase


class AnalysisMaterialityMigrationTests(SimpleTestCase):
    def test_schema_follows_0181_and_is_retry_safe_irreversible(self):
        migration = import_module(
            "management.migrations.0182_analysis_materiality_ledger"
        )

        self.assertEqual(
            migration.Migration.dependencies,
            [("management", "0181_gemini_accounting_v2_innodb")],
        )
        self.assertFalse(migration.Migration.atomic)
        self.assertIsInstance(
            migration.Migration.operations[0],
            migrations.SeparateDatabaseAndState,
        )
        self.assertIsInstance(migration.Migration.operations[1], migrations.RunPython)
        self.assertFalse(migration.Migration.operations[1].reversible)
        self.assertFalse(migration.Migration.operations[-1].reversible)
        self.assertTrue({
            "claimed_materiality_event_highwater",
            "claimed_materiality_digest",
            "claimed_authority_digest",
            "claimed_artifact_digest",
        }.issubset({name for _app, _model, name in migration.JOB_FIELD_SPECS}))

    def test_mysql_trigger_and_engine_contract_is_idempotent(self):
        migration = import_module(
            "management.migrations.0182_analysis_materiality_ledger"
        )
        editor = Mock()
        editor.connection.vendor = "mysql"

        migration.create_append_only_triggers(Mock(), editor)

        sql = "\n".join(call.args[0] for call in editor.execute.call_args_list)
        self.assertIn("DROP TRIGGER IF EXISTS ig_mat_no_update", sql)
        self.assertIn("DROP TRIGGER IF EXISTS ig_mat_no_delete", sql)
        self.assertIn("SIGNAL SQLSTATE '45000'", sql)

    def test_engine_inventory_registers_materiality_table(self):
        from management.services.ig_engine_health import IG_RUNTIME_TABLES

        self.assertIn(
            "management_iganalysismaterialityevent",
            IG_RUNTIME_TABLES,
        )

    def test_partial_table_resume_delegates_to_introspection_reconciler(self):
        migration = import_module(
            "management.migrations.0182_analysis_materiality_ledger"
        )
        event_model = Mock()
        registry = Mock()
        registry.get_model.return_value = event_model
        editor = Mock()
        editor.connection.vendor = "sqlite"
        editor.connection.introspection.table_names.return_value = [
            migration.EVENT_TABLE
        ]

        with patch.object(migration, "ensure_additive_schema") as ensure, patch.object(
            migration, "ensure_event_key_unique"
        ):
            migration.ensure_materiality_schema(registry, editor)

        editor.create_model.assert_not_called()
        ensure.assert_called_once()

    def test_fresh_create_does_not_readd_deferred_event_indexes(self):
        migration = import_module(
            "management.migrations.0182_analysis_materiality_ledger"
        )
        event_model = Mock()
        registry = Mock()
        registry.get_model.return_value = event_model
        editor = Mock()
        editor.connection.vendor = "sqlite"
        editor.connection.introspection.table_names.return_value = []

        with patch.object(migration, "ensure_additive_schema") as ensure, patch.object(
            migration, "ensure_event_key_unique"
        ):
            migration.ensure_materiality_schema(registry, editor)

        editor.create_model.assert_called_once_with(event_model)
        self.assertEqual(
            ensure.call_args.kwargs["field_specs"],
            migration.JOB_FIELD_SPECS,
        )
        self.assertEqual(
            ensure.call_args.kwargs["index_specs"],
            migration.JOB_INDEX_SPECS,
        )

    def test_existing_mysql_table_converges_to_innodb_before_reconcile(self):
        migration = import_module(
            "management.migrations.0182_analysis_materiality_ledger"
        )
        registry = Mock()
        registry.get_model.return_value = Mock()
        editor = Mock()
        editor.quote_name.side_effect = lambda value: f"`{value}`"
        editor.connection.vendor = "mysql"
        editor.connection.introspection.table_names.return_value = [
            migration.EVENT_TABLE
        ]
        cursor = Mock()
        cursor.fetchone.return_value = ("MyISAM",)
        editor.connection.cursor.return_value.__enter__ = Mock(return_value=cursor)
        editor.connection.cursor.return_value.__exit__ = Mock(return_value=False)

        with patch.object(migration, "ensure_additive_schema"), patch.object(
            migration, "ensure_event_key_unique"
        ):
            migration.ensure_materiality_schema(registry, editor)

        editor.execute.assert_called_once_with(
            f"ALTER TABLE `{migration.EVENT_TABLE}` ENGINE=InnoDB"
        )

    def test_partial_foreign_key_column_validates_physical_target_type(self):
        from management.migrations._resumable_schema import _validate_field

        editor = Mock()
        editor.connection.introspection.get_field_type.return_value = (
            "BigIntegerField"
        )
        field = SimpleNamespace(
            column="client_id",
            null=False,
            max_length=None,
            is_relation=True,
            many_to_one=True,
            target_field=SimpleNamespace(
                get_internal_type=lambda: "BigAutoField"
            ),
        )
        column = SimpleNamespace(
            type_code=8,
            null_ok=False,
            internal_size=None,
        )

        _validate_field(editor, "management_event", field, column)
        editor.connection.introspection.get_field_type.return_value = "CharField"
        with self.assertRaisesRegex(RuntimeError, "expected BigAutoField"):
            _validate_field(editor, "management_event", field, column)

    def test_existing_event_key_unique_index_is_structurally_validated(self):
        migration = import_module(
            "management.migrations.0182_analysis_materiality_ledger"
        )
        constraint = models.UniqueConstraint(
            fields=["event_key"],
            name="ig_mat_event_key_unique",
        )
        model = SimpleNamespace(
            _meta=SimpleNamespace(
                db_table=migration.EVENT_TABLE,
                get_field=lambda _name: SimpleNamespace(column="event_key"),
                constraints=[constraint],
            )
        )
        registry = Mock()
        registry.get_model.return_value = model
        editor = Mock()
        cursor = Mock()
        editor.connection.cursor.return_value.__enter__ = Mock(return_value=cursor)
        editor.connection.cursor.return_value.__exit__ = Mock(return_value=False)
        editor.connection.introspection.get_constraints.return_value = {
            "ig_mat_event_key_unique": {
                "unique": True,
                "columns": ["event_key"],
            }
        }

        migration.ensure_event_key_unique(registry, editor)
        editor.add_constraint.assert_not_called()

        editor.connection.introspection.get_constraints.return_value = {
            "ig_mat_event_key_unique": {
                "unique": False,
                "columns": ["wrong"],
            }
        }
        with self.assertRaisesRegex(RuntimeError, "incompatible shape"):
            migration.ensure_event_key_unique(registry, editor)

        editor.connection.introspection.get_constraints.return_value = {}
        migration.ensure_event_key_unique(registry, editor)
        editor.add_constraint.assert_called_once_with(model, constraint)
