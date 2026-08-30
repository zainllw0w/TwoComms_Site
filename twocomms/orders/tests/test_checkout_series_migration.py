from importlib import import_module
from types import SimpleNamespace
from unittest.mock import Mock

from django.db import migrations
from django.test import SimpleTestCase

from management.migration_operations import (
    IdempotentAddConstraint,
    IdempotentAddField,
    IdempotentAddIndex,
)


class CheckoutSeriesMigrationTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.migration = import_module(
            "orders.migrations.0058_paymentattempt_checkout_series"
        )

    def test_leaf_is_retry_safe_non_atomic_and_irreversible(self):
        migration = self.migration
        self.assertEqual(
            migration.Migration.dependencies,
            [("orders", "0057_paymentattempt_provider_recheck")],
        )
        self.assertFalse(migration.Migration.atomic)
        self.assertEqual(
            sum(isinstance(op, IdempotentAddField) for op in migration.Migration.operations),
            3,
        )
        self.assertEqual(
            sum(isinstance(op, IdempotentAddIndex) for op in migration.Migration.operations),
            2,
        )
        self.assertEqual(
            sum(isinstance(op, IdempotentAddConstraint) for op in migration.Migration.operations),
            2,
        )
        self.assertIsInstance(migration.Migration.operations[-1], migrations.RunPython)
        self.assertFalse(migration.Migration.operations[-1].reversible)

    def test_index_unique_and_check_shape_validation_rejects_conflicts(self):
        migration = self.migration
        migration._validate_index(
            "pay_attempt_series_idx",
            {
                "columns": list(migration.INDEX_EXPECTATIONS["pay_attempt_series_idx"]),
                "index": True,
                "unique": False,
            },
        )
        migration._validate_unique({
            "columns": list(migration.UNIQUE_COLUMNS),
            "unique": True,
        })
        migration._validate_check({
            "columns": list(migration.CHECK_COLUMNS),
            "check": True,
        })

        with self.assertRaisesRegex(RuntimeError, "index shape"):
            migration._validate_index(
                "pay_attempt_series_idx",
                {"columns": ["wrong"], "index": True, "unique": False},
            )
        with self.assertRaisesRegex(RuntimeError, "unique shape"):
            migration._validate_unique({
                "columns": list(reversed(migration.UNIQUE_COLUMNS)),
                "unique": True,
            })
        with self.assertRaisesRegex(RuntimeError, "check shape"):
            migration._validate_check({
                "columns": ["checkout_series_key"],
                "check": True,
            })

    def test_field_validator_checks_physical_type_nullability_and_size(self):
        migration = self.migration
        editor = Mock()
        editor.connection.introspection.get_field_type.return_value = "CharField"
        column = SimpleNamespace(type_code=1, null_ok=True, internal_size=64)

        migration._validate_field(editor, "checkout_series_key", column)

        editor.connection.introspection.get_field_type.return_value = "TextField"
        with self.assertRaisesRegex(RuntimeError, "has type"):
            migration._validate_field(editor, "checkout_series_key", column)
        editor.connection.introspection.get_field_type.return_value = "CharField"
        with self.assertRaisesRegex(RuntimeError, "nullability"):
            migration._validate_field(
                editor,
                "checkout_series_key",
                SimpleNamespace(type_code=1, null_ok=False, internal_size=64),
            )
        with self.assertRaisesRegex(RuntimeError, "length"):
            migration._validate_field(
                editor,
                "checkout_series_key",
                SimpleNamespace(type_code=1, null_ok=True, internal_size=32),
            )
