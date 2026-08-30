from importlib import import_module
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.db import connection, migrations
from django.test import SimpleTestCase, TestCase

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
        editor = Mock()
        editor.connection.vendor = "mysql"
        expected_clause = migration._EXPECTED_CHECK_CLAUSES["mysql"][0]
        with patch.object(
            migration,
            "_physical_check_clause",
            return_value=expected_clause,
        ), patch.object(migration, "_validate_check_truth_table"):
            migration._validate_check(editor, {
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
            with patch.object(
                migration,
                "_physical_check_clause",
                return_value=expected_clause,
            ), patch.object(migration, "_validate_check_truth_table"):
                migration._validate_check(editor, {
                    "columns": ["checkout_series_key"],
                    "check": True,
                })

    def test_wrong_same_name_check_predicate_is_rejected(self):
        migration = self.migration
        editor = Mock()
        editor.connection.vendor = "mysql"

        with patch.object(
            migration,
            "_physical_check_clause",
            return_value="checkout_series_key is null or 1 = 1",
        ), self.assertRaisesRegex(RuntimeError, "normalized predicate"):
            migration._validate_check(editor, {
                "columns": list(migration.CHECK_COLUMNS),
                "check": True,
            })

    def test_field_validator_checks_physical_type_nullability_and_size(self):
        migration = self.migration
        editor = Mock()
        editor.connection.introspection.get_field_type.return_value = "CharField"
        column = SimpleNamespace(
            type_code=1,
            null_ok=True,
            internal_size=64,
            default=None,
        )

        migration._validate_field(editor, "checkout_series_key", column)

        editor.connection.introspection.get_field_type.return_value = "TextField"
        with self.assertRaisesRegex(RuntimeError, "has type"):
            migration._validate_field(editor, "checkout_series_key", column)
        editor.connection.introspection.get_field_type.return_value = "CharField"
        with self.assertRaisesRegex(RuntimeError, "nullability"):
            migration._validate_field(
                editor,
                "checkout_series_key",
                SimpleNamespace(
                    type_code=1,
                    null_ok=False,
                    internal_size=64,
                    default=None,
                ),
            )
        with self.assertRaisesRegex(RuntimeError, "length"):
            migration._validate_field(
                editor,
                "checkout_series_key",
                SimpleNamespace(
                    type_code=1,
                    null_ok=True,
                    internal_size=32,
                    default=None,
                ),
            )

    def test_field_validator_normalizes_and_rejects_physical_defaults(self):
        migration = self.migration
        editor = Mock()
        editor.connection.introspection.get_field_type.return_value = "IntegerField"

        migration._validate_field(
            editor,
            "checkout_winner_claimed",
            SimpleNamespace(
                type_code=1,
                null_ok=False,
                internal_size=1,
                default="((0))",
            ),
        )
        with self.assertRaisesRegex(RuntimeError, "has default"):
            migration._validate_field(
                editor,
                "checkout_winner_claimed",
                SimpleNamespace(
                    type_code=1,
                    null_ok=False,
                    internal_size=1,
                    default="1",
                ),
            )

    def test_irreversible_validator_is_last_before_any_reverse_ddl(self):
        operations = self.migration.Migration.operations

        self.assertIsInstance(operations[-1], migrations.RunPython)
        self.assertFalse(operations[-1].reversible)
        self.assertTrue(all(
            isinstance(
                operation,
                (IdempotentAddField, IdempotentAddIndex, IdempotentAddConstraint),
            )
            for operation in operations[1:-1]
        ))


class CheckoutSeriesPhysicalPredicateTests(TestCase):
    def test_sqlite_named_check_matches_exact_predicate_and_truth_table(self):
        migration = import_module(
            "orders.migrations.0058_paymentattempt_checkout_series"
        )
        editor = SimpleNamespace(
            connection=connection,
            quote_name=connection.ops.quote_name,
        )
        with connection.cursor() as cursor:
            constraints = connection.introspection.get_constraints(
                cursor,
                migration.TABLE,
            )

        migration._validate_check(
            editor,
            constraints[migration.CHECK_NAME],
        )
