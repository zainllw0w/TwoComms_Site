from importlib import import_module
from unittest.mock import Mock, patch

from django.db import migrations
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

        with patch.object(migration, "ensure_additive_schema") as ensure:
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

        with patch.object(migration, "ensure_additive_schema") as ensure:
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

        with patch.object(migration, "ensure_additive_schema"):
            migration.ensure_materiality_schema(registry, editor)

        editor.execute.assert_called_once_with(
            f"ALTER TABLE `{migration.EVENT_TABLE}` ENGINE=InnoDB"
        )
