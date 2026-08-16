from __future__ import annotations

import importlib
import re
import unittest


MIGRATION_MODULE = "warehouse.migrations.0012_mariadb_native_uuid_compatibility"


class _FakeCursor:
    def __init__(self, *, invalid_rows=0, engines=None):
        self.invalid_rows = invalid_rows
        self.engines = dict(engines or {})
        self.executed = []
        self.last_sql = ""
        self.last_params = ()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=None):
        self.last_sql = str(sql)
        self.last_params = tuple(params or ())
        self.executed.append((self.last_sql, self.last_params))

    def fetchone(self):
        if "information_schema.COLUMNS" in self.last_sql:
            return ("char", 32, "NO")
        if "information_schema.TABLES" in self.last_sql:
            return (self.engines.get(self.last_params[0], "MyISAM"),)
        if "REGEXP" in self.last_sql:
            return (self.invalid_rows,)
        raise AssertionError(f"unexpected query: {self.last_sql}")


class _FakeConnection:
    def __init__(self, cursor, *, vendor="mysql", mysql_is_mariadb=True):
        self._cursor = cursor
        self.vendor = vendor
        self.mysql_is_mariadb = mysql_is_mariadb
        self.ops = self

    def cursor(self):
        return self._cursor

    @staticmethod
    def quote_name(value):
        return f"`{value}`"


class _FakeSchemaEditor:
    def __init__(self, cursor, *, vendor="mysql", mysql_is_mariadb=True):
        self.connection = _FakeConnection(
            cursor,
            vendor=vendor,
            mysql_is_mariadb=mysql_is_mariadb,
        )
        self.executed = []

    @staticmethod
    def quote_name(value):
        return f"`{value}`"

    def execute(self, sql):
        statement = str(sql)
        self.executed.append(statement)
        engine_match = re.search(r"ALTER TABLE `([^`]+)` ENGINE=InnoDB", statement)
        if engine_match:
            self.connection._cursor.engines[engine_match.group(1)] = "InnoDB"


class MariaDBUuidMigrationContractTests(unittest.TestCase):
    def setUp(self):
        self.migration = importlib.import_module(MIGRATION_MODULE)

    def test_migration_covers_every_legacy_uuid_column_found_in_production(self):
        self.assertEqual(
            self.migration.LEGACY_UUID_COLUMNS,
            (
                ("dtf_dtfbuildersession", "session_id"),
                ("storefront_pushnotificationdelivery", "event_token"),
                ("management_commercialofferemaillog", "track_token"),
                ("warehouse_writeoffrequest", "token"),
            ),
        )

    def test_migration_covers_every_warehouse_table_found_in_production(self):
        self.assertEqual(
            self.migration.WAREHOUSE_TABLES,
            (
                "warehouse_consumablecategory",
                "warehouse_consumableitem",
                "warehouse_print",
                "warehouse_print_default_products",
                "warehouse_print_garment_colors",
                "warehouse_printcategory",
                "warehouse_printcolorvariant",
                "warehouse_printcolorvariant_colors",
                "warehouse_stockitem",
                "warehouse_stockmovement",
                "warehouse_storagecategory",
                "warehouse_storagesubcategory",
                "warehouse_storagesubcategory_colors",
                "warehouse_warehousesettings",
                "warehouse_writeoffrequest",
            ),
        )

    def test_mariadb_char32_columns_are_converted_to_native_uuid(self):
        cursor = _FakeCursor()
        schema_editor = _FakeSchemaEditor(cursor)

        self.migration.convert_legacy_mariadb_uuid_columns(None, schema_editor)

        self.assertEqual(len(schema_editor.executed), 4)
        for statement in schema_editor.executed:
            self.assertIn("ALTER TABLE", statement)
            self.assertIn(" UUID NOT NULL", statement)

    def test_invalid_legacy_values_fail_before_any_schema_change(self):
        cursor = _FakeCursor(invalid_rows=1)
        schema_editor = _FakeSchemaEditor(cursor)

        with self.assertRaisesRegex(RuntimeError, "invalid legacy UUID"):
            self.migration.convert_legacy_mariadb_uuid_columns(None, schema_editor)

        self.assertEqual(schema_editor.executed, [])

    def test_warehouse_tables_are_converted_to_innodb_and_verified(self):
        cursor = _FakeCursor()
        schema_editor = _FakeSchemaEditor(cursor)

        self.migration.ensure_warehouse_tables_innodb(None, schema_editor)

        altered_tables = {
            re.search(r"ALTER TABLE `([^`]+)`", statement).group(1)
            for statement in schema_editor.executed
        }
        self.assertEqual(altered_tables, set(self.migration.WAREHOUSE_TABLES))
        self.assertTrue(
            all(cursor.engines[table] == "InnoDB" for table in self.migration.WAREHOUSE_TABLES)
        )

    def test_uuid_conversion_is_noop_on_non_mariadb_mysql(self):
        cursor = _FakeCursor()
        schema_editor = _FakeSchemaEditor(cursor, mysql_is_mariadb=False)

        self.migration.convert_legacy_mariadb_uuid_columns(None, schema_editor)

        self.assertEqual(cursor.executed, [])
        self.assertEqual(schema_editor.executed, [])

    def test_physical_schema_repairs_are_noop_on_sqlite(self):
        cursor = _FakeCursor()
        schema_editor = _FakeSchemaEditor(
            cursor,
            vendor="sqlite",
            mysql_is_mariadb=False,
        )

        self.migration.ensure_warehouse_tables_innodb(None, schema_editor)
        self.migration.convert_legacy_mariadb_uuid_columns(None, schema_editor)

        self.assertEqual(cursor.executed, [])
        self.assertEqual(schema_editor.executed, [])


if __name__ == "__main__":
    unittest.main()
