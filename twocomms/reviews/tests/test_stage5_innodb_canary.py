from __future__ import annotations

import importlib
import os
import tempfile
import uuid
from pathlib import Path
from unittest import mock

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import Client, RequestFactory, SimpleTestCase, TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from reviews.admin import ReviewAdmin, ReviewVoteAdmin
from reviews.models import Review, ReviewStatus, ReviewVote
from storefront.models import Category, Product


MIGRATION_MODULE = "reviews.migrations.0003_reviewvote_innodb_canary"
EXPECTED_INDEXES = (
    ("PRIMARY", 0, "BTREE", "id"),
    ("reviews_reviewvote_anon_key_9578b8b8", 1, "BTREE", "anon_key"),
    ("reviews_reviewvote_review_id_0cdb7cab", 1, "BTREE", "review_id"),
    ("reviews_reviewvote_user_id_595149a6", 1, "BTREE", "user_id"),
    ("rev_vote_unique_anon", 0, "BTREE", "review_id,anon_identity"),
    ("rev_vote_unique_user", 0, "BTREE", "review_id,user_id"),
)


class _Cursor:
    def __init__(self, state):
        self.state = state
        self.statement = ""

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, statement, params=None):
        self.statement = " ".join(str(statement).split()).lower()
        self.state["queries"].append((self.statement, tuple(params or ())))

    def fetchone(self):
        if "information_schema.tables" in self.statement:
            return (self.state["engine"],)
        if "information_schema.triggers" in self.statement:
            return (self.state["triggers"],)
        if "information_schema.columns" in self.statement:
            return self.state["generated_identity"]
        if "index_type = 'fulltext'" in self.statement:
            return (self.state["fulltext"],)
        if "count(*) from" in self.statement:
            if "having count(*) > 1" in self.statement:
                return (self.state["duplicates"],)
            return (self.state["rows"],)
        raise AssertionError(f"unexpected fetchone query: {self.statement}")

    def fetchall(self):
        if "information_schema.statistics" in self.statement:
            return list(self.state["indexes"])
        if "information_schema.key_column_usage" in self.statement:
            return list(self.state["foreign_keys"])
        raise AssertionError(f"unexpected fetchall query: {self.statement}")


class _Connection:
    vendor = "mysql"
    alias = "default"

    def __init__(self, state):
        self.state = state

    def cursor(self):
        return _Cursor(self.state)


class _SchemaEditor:
    def __init__(self, state, *, vendor="mysql"):
        self.state = state
        self.connection = _Connection(state)
        self.connection.vendor = vendor
        self.executed = []

    def quote_name(self, name):
        return f"`{name}`"

    def execute(self, statement):
        self.executed.append(statement)
        normalized = str(statement).upper()
        if "ENGINE=INNODB" in normalized:
            self.state["engine"] = "InnoDB"
        elif "ENGINE=MYISAM" in normalized:
            self.state["engine"] = "MyISAM"


def _state(**overrides):
    state = {
        "engine": "MyISAM",
        "rows": 0,
        "duplicates": 0,
        "triggers": 0,
        "fulltext": 0,
        "indexes": list(EXPECTED_INDEXES),
        "foreign_keys": [],
        "generated_identity": (
            "STORED GENERATED",
            "case when user_id is null then anon_key else null end",
        ),
        "queries": [],
    }
    state.update(overrides)
    return state


class ReviewVoteEngineMigrationUnitTests(SimpleTestCase):
    def _migration(self):
        path = Path(__file__).resolve().parents[1] / "migrations" / "0003_reviewvote_innodb_canary.py"
        self.assertTrue(path.is_file(), "the reversible ReviewVote engine migration is missing")
        return importlib.import_module(MIGRATION_MODULE)

    def test_forward_and_reverse_use_the_same_live_table_and_preserve_rows(self):
        migration = self._migration()
        state = _state()
        editor = _SchemaEditor(state)

        with mock.patch.object(migration, "review_write_freeze_verified", return_value=True):
            migration.convert_reviewvote_to_innodb(None, editor)
            state["rows"] = 1
            migration.restore_reviewvote_to_myisam(None, editor)

        self.assertEqual(
            editor.executed,
            [
                "ALTER TABLE `reviews_reviewvote` ENGINE=InnoDB",
                "ALTER TABLE `reviews_reviewvote` ENGINE=MyISAM",
            ],
        )
        self.assertEqual(state["rows"], 1)
        self.assertEqual(state["engine"], "MyISAM")

    def test_accepts_mariadb_foreign_key_index_layout(self):
        migration = self._migration()
        state = _state(
            indexes=[
                ("PRIMARY", 0, "BTREE", "id"),
                ("reviews_reviewvote_anon_key_9578b8b8", 1, "BTREE", "anon_key"),
                (
                    "reviews_reviewvote_user_id_595149a6_fk_auth_user_id",
                    1,
                    "BTREE",
                    "user_id",
                ),
                ("rev_vote_unique_anon", 0, "BTREE", "review_id,anon_identity"),
                ("rev_vote_unique_user", 0, "BTREE", "review_id,user_id"),
            ]
        )
        editor = _SchemaEditor(state)

        with mock.patch.object(migration, "review_write_freeze_verified", return_value=True):
            migration.convert_reviewvote_to_innodb(None, editor)
            state["rows"] = 1
            migration.restore_reviewvote_to_myisam(None, editor)

        self.assertEqual(
            editor.executed,
            [
                "ALTER TABLE `reviews_reviewvote` ENGINE=InnoDB",
                "ALTER TABLE `reviews_reviewvote` ENGINE=MyISAM",
            ],
        )

    def test_migration_requires_the_generated_identity_warning_fix(self):
        migration = self._migration()

        self.assertEqual(
            migration.Migration.dependencies,
            [("reviews", "0002_mariadb_vote_uniqueness")],
        )

    def test_mysql_preflight_rejects_unexpected_schema_or_data_before_ddl(self):
        migration = self._migration()
        cases = (
            ("engine", {"engine": "Aria"}),
            ("index", {"indexes": list(EXPECTED_INDEXES[:-1])}),
            ("trigger", {"triggers": 1}),
            ("FULLTEXT", {"fulltext": 1}),
            ("foreign key", {"foreign_keys": [("reviews_reviewvote", "review_id", "reviews_review", "id")]}),
            ("duplicate", {"duplicates": 1}),
            ("generated identity", {"generated_identity": ("", "")}),
            ("row count", {"rows": 1}),
        )
        for message, override in cases:
            state = _state(**override)
            editor = _SchemaEditor(state)
            with self.subTest(message=message), mock.patch.object(
                migration, "review_write_freeze_verified", return_value=True
            ), self.assertRaisesRegex(RuntimeError, message):
                migration.convert_reviewvote_to_innodb(None, editor)
            self.assertEqual(editor.executed, [])

    def test_fresh_innodb_install_and_sqlite_are_idempotent_noops(self):
        migration = self._migration()
        fresh_fks = [
            ("reviews_reviewvote", "review_id", "reviews_review", "id"),
            ("reviews_reviewvote", "user_id", "auth_user", "id"),
        ]
        editor = _SchemaEditor(_state(engine="InnoDB", foreign_keys=fresh_fks))

        with mock.patch.object(migration, "review_write_freeze_verified", return_value=False):
            migration.convert_reviewvote_to_innodb(None, editor)
            migration.restore_reviewvote_to_myisam(None, editor)
        self.assertEqual(editor.executed, [])

        sqlite_editor = _SchemaEditor(_state(), vendor="sqlite")
        migration.convert_reviewvote_to_innodb(None, sqlite_editor)
        migration.restore_reviewvote_to_myisam(None, sqlite_editor)
        self.assertEqual(sqlite_editor.executed, [])


class ReviewWriteFreezeStateTests(SimpleTestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.marker = Path(self.tempdir.name) / "review-writes.frozen"
        self.override = override_settings(REVIEW_WRITE_FREEZE_MARKER=self.marker)
        self.override.enable()
        self.addCleanup(self.override.disable)

    def test_missing_marker_allows_writes_and_valid_marker_blocks_them(self):
        from reviews.write_freeze import review_write_freeze_state

        self.assertEqual(review_write_freeze_state(), (False, False, "marker_missing"))
        self.marker.write_bytes(b"review-write-freeze-v1\n")
        self.marker.chmod(0o600)
        self.assertEqual(review_write_freeze_state(), (True, True, "frozen"))

    def test_invalid_or_insecure_marker_blocks_writes_but_is_not_verified(self):
        from reviews.write_freeze import review_write_freeze_state

        self.marker.write_bytes(b"wrong\n")
        self.marker.chmod(0o600)
        self.assertEqual(review_write_freeze_state(), (True, False, "marker_invalid"))
        self.marker.write_bytes(b"review-write-freeze-v1\n")
        self.marker.chmod(0o644)
        self.assertEqual(review_write_freeze_state(), (True, False, "marker_insecure_permissions"))


class ReviewWriteFreezeEndpointTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(name="Freeze", slug="freeze", is_active=True)
        cls.product = Product.objects.create(
            title="Freeze Tee", slug="freeze-tee", category=cls.category,
            price=300, status="published",
        )
        cls.review = Review.objects.create(
            product=cls.product,
            author_name="Reviewer",
            rating=5,
            body="A sufficiently long review body for the freeze test.",
            status=ReviewStatus.APPROVED,
        )

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.marker = Path(self.tempdir.name) / "review-writes.frozen"
        self.marker.write_bytes(b"review-write-freeze-v1\n")
        self.marker.chmod(0o600)
        self.override = override_settings(REVIEW_WRITE_FREEZE_MARKER=self.marker)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.client = Client()

    def test_public_submit_and_vote_fail_closed_without_writes(self):
        submit = self.client.post(
            reverse("reviews:submit", kwargs={"product_slug": self.product.slug}),
            {
                "rating": "5",
                "body": "Another sufficiently long review body for freeze.",
                "author_name": "Blocked",
                "website": "",
            },
        )
        vote = self.client.post(
            reverse("reviews:vote", kwargs={"review_id": self.review.pk}),
            {"value": ReviewVote.HELPFUL},
        )

        self.assertEqual(submit.status_code, 503)
        self.assertEqual(vote.status_code, 503)
        self.assertEqual(submit["Retry-After"], "60")
        self.assertEqual(vote["Retry-After"], "60")
        self.assertEqual(Review.objects.count(), 1)
        self.assertEqual(ReviewVote.objects.count(), 0)

    def test_review_admins_are_read_only_during_freeze(self):
        user = get_user_model().objects.create_superuser(
            username="freeze-admin", email="freeze@example.invalid", password="x"
        )
        request = RequestFactory().get("/admin/reviews/")
        request.user = user
        site = admin.AdminSite()
        for model_admin in (
            ReviewAdmin(Review, site),
            ReviewVoteAdmin(ReviewVote, site),
        ):
            with self.subTest(model=model_admin.model._meta.label):
                self.assertFalse(model_admin.has_add_permission(request))
                self.assertFalse(model_admin.has_change_permission(request))
                self.assertFalse(model_admin.has_delete_permission(request))
                self.assertEqual(model_admin.get_actions(request), {})


class ReviewVotePhysicalMariaDbRehearsalTests(TransactionTestCase):
    databases = {"default"}

    def test_physical_forward_write_and_reverse_preserve_rows_and_indexes(self):
        from django.db import connection

        if connection.vendor != "mysql" or not getattr(connection, "mysql_is_mariadb", False):
            self.skipTest("requires disposable MariaDB")
        migration = importlib.import_module(MIGRATION_MODULE)
        table = f"stage5_reviewvote_{uuid.uuid4().hex[:12]}"
        quote = connection.ops.quote_name
        with connection.cursor() as cursor:
            cursor.execute(
                f"CREATE TABLE {quote(table)} ("
                "`id` bigint NOT NULL AUTO_INCREMENT,"
                "`review_id` bigint NOT NULL,"
                "`user_id` bigint NULL,"
                "`anon_key` varchar(64) NOT NULL DEFAULT '',"
                "`anon_identity` varchar(64) GENERATED ALWAYS AS "
                "(CASE WHEN `user_id` IS NULL THEN `anon_key` ELSE NULL END) STORED,"
                "`value` varchar(10) NOT NULL,"
                "`created_at` datetime(6) NOT NULL,"
                "PRIMARY KEY (`id`),"
                "KEY `reviews_reviewvote_anon_key_9578b8b8` (`anon_key`),"
                "KEY `reviews_reviewvote_review_id_0cdb7cab` (`review_id`),"
                "KEY `reviews_reviewvote_user_id_595149a6` (`user_id`),"
                "UNIQUE KEY `rev_vote_unique_user` (`review_id`,`user_id`),"
                "UNIQUE KEY `rev_vote_unique_anon` (`review_id`,`anon_identity`)"
                ") ENGINE=MyISAM"
            )
        try:
            with connection.schema_editor() as editor, mock.patch.object(
                migration, "review_write_freeze_verified", return_value=True
            ):
                before = migration._index_signature(editor, table)
                migration._transition_engine(
                    editor, table, source="MyISAM", target="InnoDB", require_empty=True
                )
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"INSERT INTO {quote(table)} "
                        "(`review_id`,`user_id`,`anon_key`,`value`,`created_at`) "
                        "VALUES (1,NULL,'guest-1','helpful',CURRENT_TIMESTAMP(6))"
                    )
                migration._transition_engine(
                    editor, table, source="InnoDB", target="MyISAM", require_empty=False
                )
                after = migration._index_signature(editor, table)
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT ENGINE FROM information_schema.TABLES "
                    "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s",
                    [table],
                )
                self.assertEqual(cursor.fetchone()[0].lower(), "myisam")
                cursor.execute(f"SELECT `anon_key`,`value` FROM {quote(table)}")
                self.assertEqual(cursor.fetchall(), (("guest-1", "helpful"),))
            self.assertEqual(before, after)
        finally:
            with connection.cursor() as cursor:
                cursor.execute(f"DROP TABLE IF EXISTS {quote(table)}")
