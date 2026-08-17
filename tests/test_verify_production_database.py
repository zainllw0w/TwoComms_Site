from __future__ import annotations

import os
import base64
import hashlib
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from scripts import verify_production_database


class FakeCursor:
    def __init__(self, row, description):
        self.row = row
        self.description = description
        self.executed = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, sql):
        self.executed.append(sql)

    def fetchone(self):
        return self.row


class FakeConnection:
    def __init__(self, *, engine="django.db.backends.mysql", row=None, description=None):
        self.settings_dict = {"ENGINE": engine}
        self.cursor_instance = FakeCursor(
            row
            or (
                "11.4.12-MariaDB-cll-lve",
                "STRICT_TRANS_TABLES,NO_ENGINE_SUBSTITUTION",
                "InnoDB",
                Decimal("123.45"),
                "probe",
            ),
            description
            or (
                ("VERSION()", 253),
                ("@@sql_mode", 253),
                ("@@default_storage_engine", 253),
                ("decimal_probe", 246),
                ("string_probe", 253),
            ),
        )

    def cursor(self):
        return self.cursor_instance


class ProductionDatabaseProbeTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.provider = (
            Path(self.temp_dir.name)
            / "site-packages"
            / "mysqlclient.libs"
            / "libmariadb-deadbeef.so.3"
        )
        self.provider.parent.mkdir(parents=True)
        self.provider.write_bytes(b"validated bundled library")
        record_dir = self.provider.parent.parent / "mysqlclient-2.2.8.dist-info"
        record_dir.mkdir()
        digest = base64.urlsafe_b64encode(
            hashlib.sha256(self.provider.read_bytes()).digest()
        ).rstrip(b"=").decode("ascii")
        (record_dir / "RECORD").write_text(
            "mysqlclient.libs/{} ,sha256={},{}\n".format(
                self.provider.name,
                digest,
                self.provider.stat().st_size,
            ).replace(" ", ""),
            encoding="utf-8",
        )
        self.environment = {}

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_accepts_typed_mariadb_result_with_loaded_expected_preload(self):
        connection = FakeConnection()

        result = verify_production_database.verify_connection(
            connection,
            environment=self.environment,
            loaded_libraries={self.provider.resolve()},
        )

        self.assertEqual(result["engine"], "django.db.backends.mysql")
        self.assertEqual(result["version"], "11.4.12-MariaDB-cll-lve")
        self.assertEqual(result["field_types"], [253, 253, 253, 246, 253])
        self.assertEqual(len(connection.cursor_instance.executed), 1)
        self.assertIn("SELECT VERSION()", connection.cursor_instance.executed[0])

    def test_rejects_sqlite_even_when_the_query_shape_looks_valid(self):
        with self.assertRaisesRegex(
            verify_production_database.DatabaseProbeError,
            "MySQL",
        ):
            verify_production_database.verify_connection(
                FakeConnection(engine="django.db.backends.sqlite3"),
                environment=self.environment,
                loaded_libraries={self.provider.resolve()},
            )

    def test_rejects_corrupted_mysql_field_metadata(self):
        corrupted = (
            ("VERSION()", 0),
            ("@@sql_mode", 0),
            ("@@default_storage_engine", 0),
            ("decimal_probe", 0),
            ("string_probe", 0),
        )

        with self.assertRaisesRegex(
            verify_production_database.DatabaseProbeError,
            "field metadata",
        ):
            verify_production_database.verify_connection(
                FakeConnection(description=corrupted),
                environment=self.environment,
                loaded_libraries={self.provider.resolve()},
            )

    def test_rejects_system_preload_and_dual_provider(self):
        with self.assertRaisesRegex(
            verify_production_database.DatabaseProbeError,
            "LD_PRELOAD",
        ):
            verify_production_database.verify_connection(
                FakeConnection(),
                environment={"LD_PRELOAD": "/usr/lib64/libmariadb.so.3"},
                loaded_libraries={self.provider.resolve()},
            )

        system_provider = Path(self.temp_dir.name) / "libmariadb.so.3"
        system_provider.write_bytes(b"system provider")
        with self.assertRaisesRegex(
            verify_production_database.DatabaseProbeError,
            "multiple MariaDB",
        ):
            verify_production_database.verify_connection(
                FakeConnection(),
                environment=self.environment,
                loaded_libraries={self.provider.resolve(), system_provider.resolve()},
            )

    def test_repeats_the_typed_query_for_the_requested_iterations(self):
        connection = FakeConnection()

        result = verify_production_database.verify_connection(
            connection,
            environment=self.environment,
            loaded_libraries={self.provider.resolve()},
            iterations=3,
        )

        self.assertEqual(result["iterations"], 3)
        self.assertEqual(len(connection.cursor_instance.executed), 3)

    def test_rejects_a_bundled_provider_with_a_tampered_record(self):
        self.provider.write_bytes(b"tampered bundled library")

        with self.assertRaisesRegex(
            verify_production_database.DatabaseProbeError,
            "RECORD",
        ):
            verify_production_database.verify_connection(
                FakeConnection(),
                environment=self.environment,
                loaded_libraries={self.provider.resolve()},
            )
