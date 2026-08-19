from __future__ import annotations

import importlib
import inspect
from pathlib import Path

from django.db import migrations, models
from django.test import SimpleTestCase

from reviews.models import ReviewVote


class _DuplicateQuery:
    def filter(self, *args, **kwargs):
        return self

    def exclude(self, *args, **kwargs):
        return self

    def values(self, *args, **kwargs):
        return self

    def annotate(self, *args, **kwargs):
        return self

    def exists(self):
        return True


class _HistoricalReviewVote:
    objects = _DuplicateQuery()


class _HistoricalApps:
    @staticmethod
    def get_model(app_label, model_name):
        if (app_label, model_name) != ("reviews", "ReviewVote"):
            raise AssertionError("unexpected historical model")
        return _HistoricalReviewVote


class ReviewVoteMariaDbConstraintTests(SimpleTestCase):
    def test_model_uses_real_unique_keys_with_generated_anon_identity(self):
        self.assertIn(
            "anon_identity",
            {field.name for field in ReviewVote._meta.get_fields()},
        )
        generated = ReviewVote._meta.get_field("anon_identity")

        self.assertIsInstance(generated, models.GeneratedField)
        self.assertTrue(generated.db_persist)
        self.assertFalse(generated.has_null_arg)
        constraints = {item.name: item for item in ReviewVote._meta.constraints}
        self.assertEqual(
            constraints["rev_vote_unique_user"].fields,
            ("review", "user"),
        )
        self.assertIsNone(constraints["rev_vote_unique_user"].condition)
        self.assertEqual(
            constraints["rev_vote_unique_anon"].fields,
            ("review", "anon_identity"),
        )
        self.assertIsNone(constraints["rev_vote_unique_anon"].condition)
        self.assertNotIn("rev_vote_unique_per_user", constraints)
        self.assertNotIn("rev_vote_unique_per_anon", constraints)

    def test_migration_rejects_duplicates_before_any_ddl(self):
        migration_path = (
            Path(__file__).resolve().parents[1]
            / "migrations"
            / "0002_mariadb_vote_uniqueness.py"
        )
        self.assertTrue(migration_path.is_file())
        migration = importlib.import_module(
            "reviews.migrations.0002_mariadb_vote_uniqueness"
        )
        self.assertFalse(migration.Migration.atomic)
        operations = migration.Migration.operations
        self.assertIsInstance(operations[0], migrations.RunPython)
        self.assertIsInstance(operations[1], migrations.SeparateDatabaseAndState)
        with self.assertRaisesRegex(RuntimeError, "duplicate ReviewVote"):
            migration.assert_no_review_vote_duplicates(
                _HistoricalApps(),
                schema_editor=None,
            )

    def test_migration_can_resume_partial_myisam_ddl_and_reverse_repeatedly(self):
        migration_path = (
            Path(__file__).resolve().parents[1]
            / "migrations"
            / "0002_mariadb_vote_uniqueness.py"
        )
        migration = importlib.import_module(
            "reviews.migrations.0002_mariadb_vote_uniqueness"
        )
        separated = migration.Migration.operations[1]
        self.assertIsInstance(separated, migrations.SeparateDatabaseAndState)
        self.assertTrue(
            all(
                isinstance(operation, migrations.RunPython)
                for operation in separated.database_operations
            )
        )

        forward_source = inspect.getsource(migration.apply_review_vote_schema)
        reverse_source = inspect.getsource(migration.reverse_review_vote_schema)
        module_source = migration_path.read_text(encoding="utf-8")
        self.assertIn("ADD COLUMN IF NOT EXISTS", forward_source)
        self.assertEqual(forward_source.count("ADD UNIQUE INDEX IF NOT EXISTS"), 2)
        self.assertEqual(reverse_source.count("DROP INDEX IF EXISTS"), 2)
        self.assertIn("DROP COLUMN IF EXISTS", reverse_source)
        self.assertNotIn("IrreversibleError", module_source)
