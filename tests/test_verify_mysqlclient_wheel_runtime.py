from __future__ import annotations

import os
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts import verify_mysqlclient_wheel_runtime as verifier


class FakeCursor:
    def __init__(self):
        self.description = (
            ("VERSION()", 253),
            ("@@sql_mode", 253),
            ("@@default_storage_engine", 253),
            ("decimal_probe", 246),
            ("string_probe", 253),
        )
        self.executed = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, sql):
        self.executed.append(sql)
        if "SIGNED" in sql:
            self.description = (("signed_probe", 3),)
        else:
            self.description = (
                ("VERSION()", 253),
                ("@@sql_mode", 253),
                ("@@default_storage_engine", 253),
                ("decimal_probe", 246),
                ("string_probe", 253),
            )

    def fetchone(self):
        if self.executed and "SIGNED" in self.executed[-1]:
            return (-42,)
        return (
            "11.4.12-MariaDB",
            "STRICT_TRANS_TABLES,NO_ENGINE_SUBSTITUTION",
            "InnoDB",
            Decimal("1234567890.123456"),
            verifier.EXPECTED_UNICODE_VALUE,
        )


class FakeConnection:
    def __init__(self):
        self.cursor_instance = FakeCursor()

    def cursor(self):
        return self.cursor_instance


class MysqlclientWheelRuntimeTests(unittest.TestCase):
    def test_accepts_exact_typed_values_and_repeats_query(self):
        connection = FakeConnection()

        result = verifier.verify_typed_connection(
            connection,
            expected_server_version="11.4.12",
            iterations=3,
        )

        self.assertEqual(result["field_types"], [253, 253, 253, 246, 253])
        self.assertEqual(result["signed_field_type"], 3)
        self.assertEqual(result["iterations"], 3)
        self.assertEqual(len(connection.cursor_instance.executed), 6)

    def test_rejects_corrupted_type_codes(self):
        connection = FakeConnection()
        original_execute = connection.cursor_instance.execute

        def corrupted_execute(sql):
            original_execute(sql)
            connection.cursor_instance.description = tuple(
                (field[0], 0) for field in connection.cursor_instance.description
            )

        connection.cursor_instance.execute = corrupted_execute

        with self.assertRaisesRegex(verifier.WheelRuntimeError, "metadata"):
            verifier.verify_typed_connection(
                connection,
                expected_server_version="11.4.12",
                iterations=1,
            )

    def test_requires_preload_to_be_unset(self):
        with self.assertRaisesRegex(verifier.WheelRuntimeError, "LD_PRELOAD"):
            verifier.require_clean_loader_environment({"LD_PRELOAD": "/tmp/lib.so"})

    def test_loaded_library_must_match_bundled_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            library = Path(directory) / "mysqlclient.libs" / "libmariadb-deadbeef.so.3"
            library.parent.mkdir()
            library.write_bytes(b"bundled connector")
            evidence = {
                "mysqlclient_bundled_library_name": (
                    "mysqlclient.libs/libmariadb-deadbeef.so.3"
                ),
                "mysqlclient_bundled_library_sha256": verifier.sha256(library),
                "mysqlclient_bundled_library_soname": "libmariadb-deadbeef.so.3",
            }

            result = verifier.verify_loaded_library(
                evidence,
                loaded_libraries={library.resolve()},
                soname_reader=lambda path: path.name,
            )

            self.assertEqual(result["library_sha256"], verifier.sha256(library))
            self.assertEqual(result["library_soname"], library.name)

    def test_cli_forces_a_query_before_inspecting_process_maps(self):
        order = []

        class Connection:
            def close(self):
                return None

        mysql_module = SimpleNamespace(connect=lambda **kwargs: Connection())
        with (
            patch.dict(sys.modules, {"MySQLdb": mysql_module}),
            patch.object(verifier, "require_clean_loader_environment"),
            patch.object(verifier, "_load_evidence", return_value={}),
            patch.object(
                verifier,
                "verify_typed_connection",
                side_effect=lambda *args, **kwargs: order.append("query") or {},
            ),
            patch.object(
                verifier,
                "verify_loaded_library",
                side_effect=lambda *args, **kwargs: order.append("loader") or {},
            ),
            redirect_stdout(io.StringIO()),
        ):
            result = verifier.main(
                [
                    "--evidence",
                    "/tmp/not-read.json",
                    "--expected-server-version",
                    "11.4.12",
                    "--iterations",
                    "1",
                ]
            )

        self.assertEqual(result, 0)
        self.assertEqual(order, ["query", "loader"])


if __name__ == "__main__":
    unittest.main()
