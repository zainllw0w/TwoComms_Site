from importlib import import_module
from unittest.mock import Mock, patch

from django.apps import apps
from django.db import migrations
from django.test import SimpleTestCase

from storefront.models import Category


class PerformanceMigrationStateTests(SimpleTestCase):
    def test_second_performance_index_batch_preserves_project_state(self):
        migration = import_module("storefront.migrations.0030_add_performance_indexes")
        operation = migration.Migration.operations[0]

        self.assertIsInstance(operation, migrations.SeparateDatabaseAndState)
        self.assertEqual(len(operation.state_operations), 10)
        self.assertEqual(len(operation.database_operations), 1)
        self.assertIsInstance(operation.database_operations[0], migrations.RunPython)

        state_indexes = {
            item.index.name: tuple(item.index.fields)
            for item in operation.state_operations
        }
        self.assertEqual(
            state_indexes["idx_category_order"],
            ("order", "name"),
        )
        self.assertEqual(
            migration._REUSED_INDEXES,
            {
                ("Category", "idx_category_active"),
                ("Category", "idx_category_order"),
                ("Product", "idx_product_featured"),
            },
        )
        model_indexes = {index.name: tuple(index.fields) for index in Category._meta.indexes}
        self.assertEqual(model_indexes["idx_category_order"], ("order", "name"))

    def test_second_batch_reuses_matching_existing_indexes(self):
        migration = import_module("storefront.migrations.0030_add_performance_indexes")
        schema_editor = Mock()

        with patch.object(
            migration,
            "_index_columns",
            side_effect=lambda _editor, model, name: migration._expected_index_columns(
                model,
                dict(
                    (index_name, fields)
                    for _model_name, index_name, fields in migration._INDEXES
                )[name],
            ),
        ):
            migration._ensure_indexes(apps, schema_editor)

        schema_editor.add_index.assert_not_called()

    def test_second_batch_repairs_a_missing_reused_composite_index(self):
        migration = import_module("storefront.migrations.0030_add_performance_indexes")
        schema_editor = Mock()

        def columns(_editor, model, name):
            if name == "idx_category_order":
                return None
            fields = dict(
                (index_name, item_fields)
                for _model_name, index_name, item_fields in migration._INDEXES
            )[name]
            return migration._expected_index_columns(model, fields)

        with patch.object(migration, "_index_columns", side_effect=columns):
            migration._ensure_indexes(apps, schema_editor)

        schema_editor.add_index.assert_called_once()
        repaired = schema_editor.add_index.call_args.args[1]
        self.assertEqual(repaired.name, "idx_category_order")
        self.assertEqual(tuple(repaired.fields), ("order", "name"))

    def test_second_batch_refuses_same_name_with_different_columns(self):
        migration = import_module("storefront.migrations.0030_add_performance_indexes")
        schema_editor = Mock()

        with patch.object(
            migration,
            "_index_columns",
            return_value=("wrong_column",),
        ), self.assertRaisesMessage(RuntimeError, "index definition mismatch"):
            migration._ensure_indexes(apps, schema_editor)

        schema_editor.add_index.assert_not_called()

    def test_second_batch_rollback_keeps_indexes_owned_by_0018(self):
        migration = import_module("storefront.migrations.0030_add_performance_indexes")
        schema_editor = Mock()

        with patch.object(
            migration,
            "_index_columns",
            side_effect=lambda _editor, model, name: migration._expected_index_columns(
                model,
                dict(
                    (index_name, fields)
                    for _model_name, index_name, fields in migration._INDEXES
                )[name],
            ),
        ):
            migration._remove_indexes(apps, schema_editor)

        removed_names = {
            call.args[1].name for call in schema_editor.remove_index.call_args_list
        }
        self.assertTrue(
            {name for _model, name in migration._REUSED_INDEXES}.isdisjoint(
                removed_names
            )
        )
