from importlib import import_module
from types import SimpleNamespace
from unittest.mock import Mock, call

from django.db import migrations
from django.test import SimpleTestCase


class CatalogMigrationRecoveryTests(SimpleTestCase):
    def test_inventory_policy_migration_repairs_an_existing_partial_table(self):
        migration = import_module("product_catalog.migrations.0008_product_inventory_policy")
        fields = [
            SimpleNamespace(name="id", column="id"),
            SimpleNamespace(name="source", column="source"),
            SimpleNamespace(name="updated_at", column="updated_at"),
            SimpleNamespace(name="product", column="product_id"),
        ]
        model = SimpleNamespace(
            _meta=SimpleNamespace(
                db_table="product_catalog_productinventorypolicy",
                local_fields=fields,
            )
        )
        app_registry = Mock()
        app_registry.get_model.return_value = model
        schema_editor = Mock()
        schema_editor.connection.vendor = "sqlite"
        schema_editor.connection.introspection.table_names.return_value = [
            "product_catalog_productinventorypolicy"
        ]
        schema_editor.connection.cursor.return_value.__enter__ = Mock(return_value=Mock())
        schema_editor.connection.cursor.return_value.__exit__ = Mock(return_value=False)
        schema_editor.connection.introspection.get_table_description.return_value = [
            SimpleNamespace(name="id"),
        ]

        migration.ensure_inventory_policy_table(app_registry, schema_editor)

        schema_editor.create_model.assert_not_called()
        self.assertEqual(
            [call.args[1].name for call in schema_editor.add_field.call_args_list],
            ["source", "updated_at", "product"],
        )

    def test_inventory_policy_backfill_is_idempotent(self):
        migration = import_module("product_catalog.migrations.0008_product_inventory_policy")
        product_manager = Mock()
        product_manager.values_list.return_value.iterator.return_value = iter([1, 2])
        link_manager = Mock()
        link_manager.values_list.return_value.distinct.return_value = [2]
        policy_manager = Mock()
        app_registry = Mock()
        class Policy:
            objects = policy_manager

            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)

        app_registry.get_model.side_effect = [
            SimpleNamespace(objects=product_manager),
            Policy,
            SimpleNamespace(objects=link_manager),
        ]

        migration.backfill_product_inventory_policies(app_registry, SimpleNamespace())

        policy_manager.bulk_create.assert_called_once()
        self.assertTrue(policy_manager.bulk_create.call_args.kwargs["ignore_conflicts"])

    def test_taxonomy_field_migration_adds_only_missing_columns(self):
        migration = import_module("product_catalog.migrations.0012_taxonomy_assets_and_seo")
        field_names = [
            "icon",
            "seo_h1_uk",
            "seo_h1_ru",
            "seo_h1_en",
            "seo_keywords_uk",
            "seo_keywords_ru",
            "seo_keywords_en",
        ]
        fields = {name: SimpleNamespace(name=name, column=name) for name in field_names}
        model = SimpleNamespace(
            _meta=SimpleNamespace(
                db_table="product_catalog_merchcollection",
                get_field=lambda name: fields[name],
            )
        )
        app_registry = Mock()
        app_registry.get_model.return_value = model
        schema_editor = Mock()
        cursor = Mock()
        schema_editor.connection.cursor.return_value.__enter__ = Mock(return_value=cursor)
        schema_editor.connection.cursor.return_value.__exit__ = Mock(return_value=False)
        schema_editor.connection.introspection.get_table_description.return_value = [
            SimpleNamespace(name="id"),
            SimpleNamespace(name="icon"),
            SimpleNamespace(name="seo_h1_uk"),
        ]

        migration.ensure_taxonomy_fields(app_registry, schema_editor)

        self.assertEqual(
            [call.args[1].name for call in schema_editor.add_field.call_args_list],
            field_names[2:],
        )

    def test_taxonomy_field_migration_keeps_state_separate_from_resumable_ddl(self):
        migration = import_module("product_catalog.migrations.0012_taxonomy_assets_and_seo")

        self.assertFalse(migration.Migration.atomic)
        self.assertIsInstance(
            migration.Migration.operations[0],
            migrations.SeparateDatabaseAndState,
        )
        self.assertIsInstance(migration.Migration.operations[1], migrations.RunPython)

    def test_taxonomy_field_migration_rejects_an_incompatible_existing_column(self):
        migration = import_module("product_catalog.migrations.0012_taxonomy_assets_and_seo")
        field = SimpleNamespace(
            name="seo_h1_uk",
            column="seo_h1_uk",
            null=False,
            max_length=180,
            get_internal_type=lambda: "CharField",
        )
        model = SimpleNamespace(
            _meta=SimpleNamespace(
                db_table="product_catalog_merchcollection",
                get_field=lambda _name: field,
            )
        )
        app_registry = Mock()
        app_registry.get_model.return_value = model
        schema_editor = Mock()
        schema_editor.connection.vendor = "sqlite"
        cursor = Mock()
        schema_editor.connection.cursor.return_value.__enter__ = Mock(return_value=cursor)
        schema_editor.connection.cursor.return_value.__exit__ = Mock(return_value=False)
        schema_editor.connection.introspection.get_table_description.return_value = [
            SimpleNamespace(
                name="seo_h1_uk",
                type_code="wrong",
                null_ok=True,
                internal_size=10,
            )
        ]
        schema_editor.connection.introspection.get_field_type.return_value = "TextField"

        with self.assertRaisesRegex(RuntimeError, "seo_h1_uk"):
            migration.ensure_taxonomy_fields(app_registry, schema_editor)

    def test_image_job_migration_repairs_an_existing_partial_table(self):
        migration = import_module("product_catalog.migrations.0014_image_optimization_job_indexes")
        fields = [
            SimpleNamespace(name="id", column="id", db_index=False),
            SimpleNamespace(name="status", column="status", db_index=False),
        ]
        index = SimpleNamespace(
            name="product_cat_model_l_5e4b9f_idx",
            fields=("model_label", "object_id", "field_name", "-created_at"),
        )
        model = SimpleNamespace(
            _meta=SimpleNamespace(
                db_table="product_catalog_imageoptimizationjob",
                local_fields=fields,
                indexes=[index],
                get_field=lambda name: SimpleNamespace(column=name),
            )
        )
        app_registry = Mock()
        app_registry.get_model.return_value = model
        schema_editor = Mock()
        cursor = Mock()
        schema_editor.connection.cursor.return_value.__enter__ = Mock(return_value=cursor)
        schema_editor.connection.cursor.return_value.__exit__ = Mock(return_value=False)
        schema_editor.connection.introspection.table_names.return_value = [
            "product_catalog_imageoptimizationjob"
        ]
        schema_editor.connection.introspection.get_table_description.return_value = [
            SimpleNamespace(name="id")
        ]
        schema_editor.connection.introspection.get_constraints.return_value = {}

        migration.ensure_image_job_indexes(app_registry, schema_editor)

        schema_editor.create_model.assert_not_called()
        schema_editor.add_field.assert_called_once_with(model, fields[1])
        schema_editor.add_index.assert_called_once_with(model, index)

    def test_image_job_migration_creates_missing_table_after_state_registration(self):
        migration = import_module("product_catalog.migrations.0014_image_optimization_job_indexes")
        model = SimpleNamespace(
            _meta=SimpleNamespace(
                db_table="product_catalog_imageoptimizationjob",
                local_fields=[],
                indexes=[],
            )
        )
        app_registry = Mock()
        app_registry.get_model.return_value = model
        schema_editor = Mock()
        schema_editor.connection.introspection.table_names.return_value = []

        migration.ensure_image_job_indexes(app_registry, schema_editor)

        schema_editor.create_model.assert_called_once_with(model)
        self.assertIsInstance(
            migration.Migration.operations[0],
            migrations.SeparateDatabaseAndState,
        )
        self.assertFalse(migration.Migration.atomic)
        self.assertTrue(migration.Migration.operations[0].database_operations)

    def test_image_job_migration_rejects_a_wrong_named_index_definition(self):
        migration = import_module("product_catalog.migrations.0014_image_optimization_job_indexes")
        index = SimpleNamespace(
            name="product_cat_model_l_5e4b9f_idx",
            fields=("model_label", "object_id", "field_name", "-created_at"),
        )
        model = SimpleNamespace(
            _meta=SimpleNamespace(
                db_table="product_catalog_imageoptimizationjob",
                local_fields=[],
                indexes=[index],
                get_field=lambda name: SimpleNamespace(column=name),
            )
        )
        app_registry = Mock()
        app_registry.get_model.return_value = model
        schema_editor = Mock()
        schema_editor.connection.vendor = "sqlite"
        schema_editor.connection.introspection.table_names.return_value = [
            "product_catalog_imageoptimizationjob"
        ]
        cursor = Mock()
        schema_editor.connection.cursor.return_value.__enter__ = Mock(return_value=cursor)
        schema_editor.connection.cursor.return_value.__exit__ = Mock(return_value=False)
        schema_editor.connection.introspection.get_table_description.return_value = []
        schema_editor.connection.introspection.get_constraints.return_value = {
            index.name: {
                "columns": ["wrong_column"],
                "index": True,
                "unique": False,
                "primary_key": False,
            }
        }

        with self.assertRaisesRegex(RuntimeError, index.name):
            migration.ensure_image_job_indexes(app_registry, schema_editor)

    def test_image_job_migration_rejects_myisam_recovery_table(self):
        migration = import_module("product_catalog.migrations.0014_image_optimization_job_indexes")
        model = SimpleNamespace(
            _meta=SimpleNamespace(
                db_table="product_catalog_imageoptimizationjob",
                local_fields=[],
                indexes=[],
            )
        )
        app_registry = Mock()
        app_registry.get_model.return_value = model
        schema_editor = Mock()
        schema_editor.connection.vendor = "mysql"
        schema_editor.connection.introspection.table_names.return_value = [
            "product_catalog_imageoptimizationjob"
        ]
        cursor = Mock()
        cursor.fetchone.return_value = ("MyISAM",)
        schema_editor.connection.cursor.return_value.__enter__ = Mock(return_value=cursor)
        schema_editor.connection.cursor.return_value.__exit__ = Mock(return_value=False)
        schema_editor.connection.introspection.get_table_description.return_value = []
        schema_editor.connection.introspection.get_constraints.return_value = {}
        schema_editor.connection.cursor.return_value.__enter__ = Mock(return_value=cursor)
        schema_editor.connection.cursor.return_value.__exit__ = Mock(return_value=False)

        with self.assertRaisesRegex(RuntimeError, "InnoDB"):
            migration.ensure_image_job_indexes(app_registry, schema_editor)

    def test_additive_image_job_migration_repairs_lease_and_indexes(self):
        migration = import_module("product_catalog.migrations.0014_image_optimization_job_indexes")
        fields = [
            SimpleNamespace(name="lease_token", column="lease_token", db_index=False),
        ]
        index = SimpleNamespace(
            name="pc_job_status_upd_9f3d_idx",
            fields=("status", "-updated_at"),
        )
        model = SimpleNamespace(
            _meta=SimpleNamespace(
                db_table="product_catalog_imageoptimizationjob",
                local_fields=fields,
                indexes=[index],
                get_field=lambda name: SimpleNamespace(column=name),
            )
        )
        app_registry = Mock()
        app_registry.get_model.return_value = model
        schema_editor = Mock()
        schema_editor.connection.vendor = "sqlite"
        schema_editor.connection.introspection.table_names.return_value = [
            "product_catalog_imageoptimizationjob"
        ]
        schema_editor.connection.introspection.get_table_description.return_value = []
        schema_editor.connection.introspection.get_constraints.return_value = {}
        schema_editor.connection.cursor.return_value.__enter__ = Mock(return_value=Mock())
        schema_editor.connection.cursor.return_value.__exit__ = Mock(return_value=False)

        migration.ensure_image_job_indexes(app_registry, schema_editor)

        schema_editor.add_field.assert_called_once_with(model, fields[0])
        schema_editor.add_index.assert_called_once_with(model, index)
