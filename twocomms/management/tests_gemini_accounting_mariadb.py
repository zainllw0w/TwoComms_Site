"""Disposable MariaDB proof for the Gemini accounting S3a schema.

Run only with the repository's guarded disposable profile (never DB_*):

    DJANGO_SETTINGS_MODULE=test_settings_mariadb \
      TEST_MARIADB_NAME=test_twocomms_<unique_suffix> \
      TEST_MARIADB_USER=<disposable_user> \
      TEST_MARIADB_PASSWORD=<disposable_password> \
      "$TWC_PYTHON" manage.py test \
      management.tests_gemini_accounting_mariadb --verbosity 2

``test_settings_mariadb`` refuses production names/users/hosts and requires an
explicit opt-in for a non-loopback disposable host.
"""
from unittest import skipUnless

from django.db import connection
from django.test import TestCase

from management.models import (
    GeminiModelQuotaUsage,
    GeminiQuotaProfile,
    GeminiQuotaState,
    GeminiRequest,
    GeminiRequestAttempt,
)


ACCOUNTING_TABLES = (
    "management_geminiquotaprofile",
    "management_geminiquotastate",
    "management_geminirequest",
    "management_geminirequestattempt",
    "management_geminimodelquotausage",
)


@skipUnless(connection.vendor == "mysql", "Disposable MariaDB-only S3a proof")
class GeminiAccountingMariaDbSchemaTests(TestCase):

    def test_database_is_explicitly_disposable(self):
        database = str(connection.settings_dict.get("NAME") or "")
        self.assertRegex(database, r"^test_twocomms_[A-Za-z0-9_]+$")

    def test_every_accounting_table_is_innodb(self):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT TABLE_NAME, ENGINE FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME IN (%s)"
                % ", ".join(["%s"] * len(ACCOUNTING_TABLES)),
                list(ACCOUNTING_TABLES),
            )
            engines = {str(table): str(engine).upper() for table, engine in cursor.fetchall()}

        self.assertEqual(set(engines), set(ACCOUNTING_TABLES))
        self.assertEqual(set(engines.values()), {"INNODB"})

    def test_seed_is_profiles_only(self):
        self.assertEqual(GeminiQuotaProfile.objects.count(), 4)
        self.assertEqual(GeminiQuotaState.objects.count(), 0)
        self.assertEqual(GeminiRequest.objects.count(), 0)
        self.assertEqual(GeminiRequestAttempt.objects.count(), 0)
        self.assertEqual(GeminiModelQuotaUsage.objects.count(), 0)
