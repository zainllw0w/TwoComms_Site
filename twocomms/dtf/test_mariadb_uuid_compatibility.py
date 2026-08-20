from __future__ import annotations

import importlib
import uuid

from django.db import connection
from django.test import TransactionTestCase


MIGRATION_MODULE = importlib.import_module(
    "dtf.migrations.0012_mariadb_native_uuid_compatibility"
)


class MariaDBDtfUuidCompatibilityTests(TransactionTestCase):
    reset_sequences = False

    def test_non_dtf_or_non_mariadb_connections_are_noops(self):
        self.assertFalse(MIGRATION_MODULE._is_dtf_mariadb(connection))

    def test_legacy_char32_values_upgrade_on_disposable_mariadb(self):
        if connection.vendor != "mysql" or not connection.mysql_is_mariadb:
            self.skipTest("MariaDB-only physical schema regression")
        database_name = str(connection.settings_dict.get("NAME") or "")
        if not database_name.startswith("test_twocomms_"):
            self.fail(
                "UUID compatibility test requires a disposable "
                "test_twocomms_* database"
            )

        table = "test_dtf_uuid_upgrade"
        legacy = uuid.UUID("12345678-1234-5678-9abc-def012345678")
        quote = connection.ops.quote_name
        original_table = MIGRATION_MODULE.TABLE_NAME
        original_column = MIGRATION_MODULE.COLUMN_NAME
        original_guard = MIGRATION_MODULE._is_dtf_mariadb
        try:
            with connection.cursor() as cursor:
                cursor.execute(f"DROP TABLE IF EXISTS {quote(table)}")
                cursor.execute(
                    f"CREATE TABLE {quote(table)} ("
                    "id BIGINT PRIMARY KEY AUTO_INCREMENT, "
                    "session_id CHAR(32) NOT NULL UNIQUE) ENGINE=InnoDB"
                )
                cursor.execute(
                    f"INSERT INTO {quote(table)} (session_id) VALUES (%s)",
                    [legacy.hex],
                )

            MIGRATION_MODULE.TABLE_NAME = table
            MIGRATION_MODULE.COLUMN_NAME = "session_id"
            with connection.schema_editor() as schema_editor:
                # The physical helper is deliberately tested through the
                # production migration entrypoint; the alias guard remains
                # covered by the no-op test above.
                MIGRATION_MODULE._is_dtf_mariadb = lambda conn: True
                MIGRATION_MODULE.convert_legacy_dtf_uuid_column(None, schema_editor)

            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT DATA_TYPE FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s "
                    "AND COLUMN_NAME=%s",
                    [table, "session_id"],
                )
                self.assertEqual(cursor.fetchone()[0].lower(), "uuid")
                cursor.execute(f"SELECT session_id FROM {quote(table)} WHERE id=1")
                self.assertEqual(str(cursor.fetchone()[0]), str(legacy))
        finally:
            MIGRATION_MODULE.TABLE_NAME = original_table
            MIGRATION_MODULE.COLUMN_NAME = original_column
            MIGRATION_MODULE._is_dtf_mariadb = original_guard
            with connection.cursor() as cursor:
                cursor.execute(f"DROP TABLE IF EXISTS {quote(table)}")
