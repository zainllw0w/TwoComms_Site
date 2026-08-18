import json
import tempfile
from io import StringIO
from pathlib import Path
from django.core.management import call_command
from django.test import SimpleTestCase, override_settings

from storefront.management.commands.measure_stage4_baseline import (
    _cache_key_observability,
    _mariadb_status,
)


FILE_CACHE = {
    "default": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": "unused",
        "TIMEOUT": 60,
        "OPTIONS": {"MAX_ENTRIES": 100},
    }
}


class Stage4ObservabilityCommandTests(SimpleTestCase):
    @override_settings(CACHES=FILE_CACHE)
    def test_json_report_covers_cache_db_fd_and_password_contracts(self):
        with tempfile.TemporaryDirectory() as cache_dir, override_settings(
            CACHES={
                "default": {**FILE_CACHE["default"], "LOCATION": cache_dir}
            }
        ):
            stdout = StringIO()
            call_command(
                "measure_stage4_baseline",
                "--samples",
                "3",
                stdout=stdout,
            )

        report = json.loads(stdout.getvalue())
        self.assertEqual(report["schema"], "twocomms.django61.stage4.v1")
        self.assertTrue(report["read_only_database"])
        self.assertEqual(report["scope"], "non-dtf")
        self.assertIn("p50_ms", report["cache"]["io"])
        self.assertIn("p95_ms", report["cache"]["io"])
        self.assertIn(report["cache"]["concurrent_add"]["winners"], (1, 2))
        self.assertFalse(
            report["cache"]["concurrent_add"]["distributed_lock_safe"]
        )
        self.assertIn("inventory", report["cache"])
        self.assertEqual(report["cache_keys"]["old_key_reads"], 0)
        self.assertNotEqual(
            report["cache_keys"]["cold_key"],
            report["cache_keys"]["warm_key"],
        )
        self.assertIn("temporary_tables", report["database"])
        self.assertIn("aborted_connections", report["database"])
        self.assertIn("open", report["file_descriptors"])
        self.assertEqual(report["password_hasher"]["iterations"], 1_500_000)
        self.assertTrue(report["password_hasher"]["verify_ok"])
        self.assertFalse(report["password_hasher"]["current_needs_rehash"])
        self.assertTrue(report["password_hasher"]["legacy_needs_rehash"])
        self.assertFalse(Path(cache_dir).exists())

    def test_mariadb_probe_only_executes_show_global_status(self):
        class Cursor:
            def __init__(self):
                self.sql = []

            def execute(self, sql, params=None):
                self.sql.append(sql)

            def fetchall(self):
                return [("Created_tmp_tables", "10"), ("Created_tmp_disk_tables", "2")]

        cursor = Cursor()
        result = _mariadb_status(cursor)
        self.assertEqual(cursor.sql, ["SHOW GLOBAL STATUS WHERE Variable_name IN (%s, %s, %s, %s)"])
        self.assertEqual(result["Created_tmp_disk_tables"], 2)

    @override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "stage4-key-test"}})
    def test_cache_key_probe_never_reads_legacy_key(self):
        result = _cache_key_observability("release-123")
        self.assertIn("release-123", result["cold_key"])
        self.assertIn("release-123", result["warm_key"])
        self.assertEqual(result["old_key_reads"], 0)
