from __future__ import annotations

import importlib
import inspect
from pathlib import Path

from django.core.exceptions import ValidationError
from django.db import IntegrityError, migrations, models, transaction
from django.test import SimpleTestCase, TestCase

from storefront.models import ProductFitOption, WebPushDeviceSubscription


class _DuplicateQuery:
    def __init__(self, duplicate):
        self.duplicate = duplicate

    def filter(self, *args, **kwargs):
        return self

    def values(self, *args, **kwargs):
        return self

    def annotate(self, *args, **kwargs):
        return self

    def exists(self):
        return self.duplicate


class _HistoricalApps:
    def __init__(self, *, fit_duplicate=False):
        self.models = {
            ("storefront", "ProductFitOption"): type(
                "HistoricalProductFitOption",
                (),
                {"objects": _DuplicateQuery(fit_duplicate)},
            ),
        }

    def get_model(self, app_label, model_name):
        return self.models[(app_label, model_name)]


class StorefrontMariaDbConstraintTests(SimpleTestCase):
    def test_default_fit_uses_generated_product_identity_unique_key(self):
        self.assertIn(
            "default_product_identity",
            {field.name for field in ProductFitOption._meta.get_fields()},
        )
        generated = ProductFitOption._meta.get_field("default_product_identity")

        self.assertIsInstance(generated, models.GeneratedField)
        self.assertTrue(generated.db_persist)
        self.assertFalse(generated.has_null_arg)
        constraints = {
            item.name: item for item in ProductFitOption._meta.constraints
        }
        self.assertEqual(
            constraints["uniq_default_fit_product"].fields,
            ("default_product_identity",),
        )
        self.assertIsNone(constraints["uniq_default_fit_product"].condition)
        self.assertNotIn("uniq_default_fit_per_product", constraints)

    def test_webpush_state_preserves_existing_database_endpoint_uniqueness(self):
        self.assertNotIn(
            "endpoint_digest",
            {
                field.name
                for field in WebPushDeviceSubscription._meta.get_fields()
            },
        )
        endpoint = WebPushDeviceSubscription._meta.get_field("endpoint")

        self.assertEqual(endpoint.max_length, 768)
        self.assertFalse(endpoint.unique)
        self.assertNotIn(
            "uniq_webpush_endpoint_digest",
            {item.name for item in WebPushDeviceSubscription._meta.constraints},
        )
        endpoint_constraint = {
            item.name: item
            for item in WebPushDeviceSubscription._meta.constraints
        }["uniq_webpush_endpoint_state"]
        self.assertEqual(endpoint_constraint.fields, ("endpoint",))

    def test_migration_is_non_atomic_idempotent_and_state_only_for_endpoint(self):
        migration_path = (
            Path(__file__).resolve().parents[1]
            / "migrations"
            / "0097_mariadb_generated_uniqueness.py"
        )
        self.assertTrue(migration_path.is_file())
        migration = importlib.import_module(
            "storefront.migrations.0097_mariadb_generated_uniqueness"
        )
        self.assertFalse(migration.Migration.atomic)
        operations = migration.Migration.operations
        self.assertIsInstance(operations[0], migrations.RunPython)
        self.assertIsInstance(operations[1], migrations.SeparateDatabaseAndState)
        separated = operations[1]
        self.assertTrue(
            all(
                isinstance(operation, migrations.RunPython)
                for operation in separated.database_operations
            )
        )
        endpoint_state_operations = [
            operation
            for operation in separated.state_operations
            if isinstance(operation, migrations.AlterField)
            and operation.model_name == "webpushdevicesubscription"
            and operation.name == "endpoint"
        ]
        self.assertEqual(len(endpoint_state_operations), 1)
        self.assertFalse(endpoint_state_operations[0].field.unique)
        endpoint_state_constraints = [
            operation
            for operation in separated.state_operations
            if isinstance(operation, migrations.AddConstraint)
            and operation.model_name == "webpushdevicesubscription"
            and operation.constraint.name == "uniq_webpush_endpoint_state"
        ]
        self.assertEqual(len(endpoint_state_constraints), 1)
        self.assertEqual(endpoint_state_constraints[0].constraint.fields, ("endpoint",))

        forward_source = inspect.getsource(migration.apply_product_fit_schema)
        reverse_source = inspect.getsource(migration.reverse_product_fit_schema)
        module_source = migration_path.read_text(encoding="utf-8")
        self.assertIn("ADD COLUMN IF NOT EXISTS", forward_source)
        self.assertIn("ADD UNIQUE INDEX IF NOT EXISTS", forward_source)
        self.assertIn("DROP INDEX IF EXISTS", reverse_source)
        self.assertIn("DROP COLUMN IF EXISTS", reverse_source)
        self.assertNotIn("IrreversibleError", module_source)
        self.assertNotIn("endpoint_digest", module_source)
        self.assertNotIn("webpushdevicesubscription`", forward_source.casefold())

    def test_migration_rejects_default_fit_duplicates_before_physical_ddl(self):
        migration = importlib.import_module(
            "storefront.migrations.0097_mariadb_generated_uniqueness"
        )
        with self.assertRaisesRegex(
            RuntimeError,
            "duplicate default ProductFitOption",
        ):
            migration.assert_no_generated_unique_duplicates(
                _HistoricalApps(fit_duplicate=True),
                schema_editor=None,
            )


class WebPushEndpointUniquenessTests(TestCase):
    endpoint = "https://push.example.test/django61-constraint"

    @staticmethod
    def _subscription(endpoint):
        return WebPushDeviceSubscription(
            endpoint=endpoint,
            auth_key="auth",
            p256dh_key="p256dh",
        )

    def test_duplicate_endpoint_is_rejected_by_full_clean_and_database(self):
        self._subscription(self.endpoint).save()

        duplicate = self._subscription(self.endpoint)
        with self.assertRaises(ValidationError):
            duplicate.full_clean()

        with self.assertRaises(IntegrityError), transaction.atomic():
            duplicate.save(force_insert=True)
