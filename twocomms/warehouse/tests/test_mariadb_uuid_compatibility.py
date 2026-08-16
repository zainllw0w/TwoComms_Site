from __future__ import annotations

import importlib
import uuid

from django.db import connection
from django.test import TransactionTestCase


MIGRATION_MODULE = importlib.import_module(
    "warehouse.migrations.0012_mariadb_native_uuid_compatibility"
)


class MariaDBUuidCompatibilityTests(TransactionTestCase):
    reset_sequences = False

    def test_legacy_char32_uuid_values_upgrade_and_new_uuid_writes_succeed(self):
        if connection.vendor != "mysql" or not connection.mysql_is_mariadb:
            self.skipTest("MariaDB-only physical schema regression")
        database_name = str(connection.settings_dict.get("NAME") or "")
        if not database_name.startswith("test_twocomms_"):
            self.fail("UUID compatibility test requires a disposable test_twocomms_* database")

        table = "test_legacy_uuid_upgrade"
        legacy = uuid.UUID("12345678-1234-5678-9abc-def012345678")
        fresh = uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
        quote = connection.ops.quote_name

        try:
            with connection.cursor() as cursor:
                cursor.execute(f"DROP TABLE IF EXISTS {quote(table)}")
                cursor.execute(
                    f"CREATE TABLE {quote(table)} ("
                    "id BIGINT PRIMARY KEY AUTO_INCREMENT, "
                    "token CHAR(32) NOT NULL UNIQUE) ENGINE=InnoDB"
                )
                cursor.execute(
                    f"INSERT INTO {quote(table)} (token) VALUES (%s)",
                    [legacy.hex],
                )

            with connection.schema_editor() as schema_editor:
                MIGRATION_MODULE.convert_legacy_mariadb_uuid_column(
                    schema_editor,
                    table,
                    "token",
                )

            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT DATA_TYPE FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s AND COLUMN_NAME=%s",
                    [table, "token"],
                )
                self.assertEqual(cursor.fetchone()[0].lower(), "uuid")
                cursor.execute(f"SELECT token FROM {quote(table)} WHERE id=1")
                self.assertEqual(str(cursor.fetchone()[0]), str(legacy))
                cursor.execute(
                    f"INSERT INTO {quote(table)} (token) VALUES (%s)",
                    [fresh],
                )
                cursor.execute(f"SELECT token FROM {quote(table)} WHERE id=2")
                self.assertEqual(str(cursor.fetchone()[0]), str(fresh))
        finally:
            with connection.cursor() as cursor:
                cursor.execute(f"DROP TABLE IF EXISTS {quote(table)}")

    def test_myisam_table_is_upgraded_to_innodb(self):
        if connection.vendor != "mysql" or not connection.mysql_is_mariadb:
            self.skipTest("MariaDB-only physical schema regression")
        database_name = str(connection.settings_dict.get("NAME") or "")
        if not database_name.startswith("test_twocomms_"):
            self.fail("engine compatibility test requires a disposable test_twocomms_* database")

        table = "test_legacy_warehouse_engine"
        quote = connection.ops.quote_name
        try:
            with connection.cursor() as cursor:
                cursor.execute(f"DROP TABLE IF EXISTS {quote(table)}")
                cursor.execute(
                    f"CREATE TABLE {quote(table)} (id BIGINT PRIMARY KEY) ENGINE=MyISAM"
                )

            with connection.schema_editor() as schema_editor:
                MIGRATION_MODULE.ensure_table_innodb(schema_editor, table)

            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT ENGINE FROM information_schema.TABLES "
                    "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s",
                    [table],
                )
                self.assertEqual(cursor.fetchone()[0].lower(), "innodb")
        finally:
            with connection.cursor() as cursor:
                cursor.execute(f"DROP TABLE IF EXISTS {quote(table)}")
