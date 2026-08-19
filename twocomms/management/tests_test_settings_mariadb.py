"""Contract tests for the fail-closed disposable MariaDB settings profile."""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
_IMPORT_PROFILE = "import test_settings_mariadb"


class MariaDbTestSettingsContractTests(unittest.TestCase):
    def setUp(self):
        self._marker_directory = tempfile.TemporaryDirectory()
        self.marker = Path(self._marker_directory.name) / "review_writes.frozen"
        self.marker.write_bytes(b"review-write-freeze-v1\n")
        self.marker.chmod(0o600)

    def tearDown(self):
        self._marker_directory.cleanup()

    def _environment(self, **overrides):
        environment = os.environ.copy()
        environment.update({
            "TEST_MARIADB_NAME": "test_twocomms_ig_contract",
            "TEST_MARIADB_USER": "test_user",
            "TEST_MARIADB_PASSWORD": "test_password",
            "TEST_MARIADB_HOST": "127.0.0.1",
            "TEST_MARIADB_PORT": "3306",
            "TEST_REVIEW_WRITE_FREEZE_MARKER": str(self.marker),
        })
        environment.pop("DB_NAME", None)
        environment.pop("DB_NAME_DTF", None)
        environment.pop("DB_HOST", None)
        environment.pop("DB_HOST_DTF", None)
        environment.update(overrides)
        return environment

    def _import_profile(self, **overrides):
        return subprocess.run(
            [sys.executable, "-c", _IMPORT_PROFILE],
            cwd=PROJECT_ROOT,
            env=self._environment(**overrides),
            capture_output=True,
            text=True,
            check=False,
        )

    def test_rejects_missing_required_credentials(self):
        result = self._import_profile(TEST_MARIADB_USER="")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "TEST_MARIADB_USER must be set for the disposable MariaDB test profile.",
            result.stderr,
        )

    def test_rejects_missing_review_write_freeze_marker(self):
        result = self._import_profile(TEST_REVIEW_WRITE_FREEZE_MARKER="")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "TEST_REVIEW_WRITE_FREEZE_MARKER must be set for the disposable "
            "MariaDB test profile.",
            result.stderr,
        )

    def test_rejects_invalid_review_write_freeze_marker_content(self):
        self.marker.write_bytes(b"invalid\n")

        result = self._import_profile()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("review write-freeze marker is invalid", result.stderr)

    def test_rejects_insecure_review_write_freeze_marker_permissions(self):
        self.marker.chmod(0o644)

        result = self._import_profile()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("review write-freeze marker is invalid", result.stderr)

    def test_rejects_a_name_outside_the_disposable_namespace(self):
        result = self._import_profile(TEST_MARIADB_NAME="qlknpodo_MySQL_DB")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("TEST_MARIADB_NAME must match test_twocomms_", result.stderr)

    def test_rejects_configured_production_database_name(self):
        result = self._import_profile(
            DB_NAME="test_twocomms_ig_contract",
            DB_HOST="production.database.example",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("matches a configured production database", result.stderr)

    def test_rejects_configured_production_host_including_loopback_alias(self):
        result = self._import_profile(
            DB_NAME="qlknpodo_MySQL_DB",
            DB_HOST="localhost",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("matches a configured production database host", result.stderr)

    def test_rejects_production_localhost_default_when_db_host_is_unset(self):
        result = self._import_profile(DB_NAME="qlknpodo_MySQL_DB")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("matches a configured production database host", result.stderr)

    def test_rejects_an_equivalent_ipv6_loopback_host(self):
        result = self._import_profile(
            TEST_MARIADB_HOST="0:0:0:0:0:0:0:1",
            DB_NAME="qlknpodo_MySQL_DB",
            DB_HOST="::1",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("matches a configured production database host", result.stderr)

    def test_rejects_non_loopback_host_without_explicit_remote_opt_in(self):
        result = self._import_profile(TEST_MARIADB_HOST="mariadb.example.test")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "TEST_MARIADB_REMOTE_ALLOWED=1",
            result.stderr,
        )

    def test_rejects_a_test_user_matching_configured_production_users(self):
        result = self._import_profile(
            DB_USER="test_user",
            DB_NAME="qlknpodo_MySQL_DB",
            DB_HOST="production.database.example",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "matches a configured production database user",
            result.stderr,
        )

    def test_profile_uses_only_the_disposable_migrated_database(self):
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import test_settings_mariadb as settings; "
                    "database = settings.DATABASES['default']; "
                    "assert database['ENGINE'] == 'django.db.backends.mysql'; "
                    "assert database['NAME'] == 'test_twocomms_ig_contract'; "
                    "assert database['TEST']['NAME'] == 'test_twocomms_ig_contract'; "
                    "assert database['TEST']['MIGRATE'] is True; "
                    "assert settings.MIGRATION_MODULES == {"
                    "'dtf': 'test_support.dtf_stub.migrations', "
                    "'warehouse': 'test_support.warehouse_migrations_non_dtf'}; "
                    "assert settings.DATABASE_ROUTERS == []; "
                    "assert 'dtf.apps.DtfConfig' not in settings.INSTALLED_APPS; "
                    "assert 'test_support.dtf_stub.apps.DtfStubConfig' in settings.INSTALLED_APPS; "
                    "assert settings.TEST_NETWORK_POLICY == 'deny-external-allow-loopback'; "
                    f"assert settings.REVIEW_WRITE_FREEZE_MARKER == {str(self.marker)!r}; "
                    "import os; "
                    "assert os.environ['MANAGER_TG_BOT_TOKEN'] == ''; "
                    "assert os.environ['MANAGEMENT_TG_BOT_TOKEN'] == ''"
                ),
            ],
            cwd=PROJECT_ROOT,
            env=self._environment(
                DB_NAME="qlknpodo_MySQL_DB",
                DB_HOST="production.database.example",
            ),
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
