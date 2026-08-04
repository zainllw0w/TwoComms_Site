"""Contract tests for the fail-closed disposable MariaDB settings profile."""

import os
import subprocess
import sys
from pathlib import Path

from django.test import SimpleTestCase


PROJECT_ROOT = Path(__file__).resolve().parents[1]
_IMPORT_PROFILE = "import test_settings_mariadb"


class MariaDbTestSettingsContractTests(SimpleTestCase):
    def _environment(self, **overrides):
        environment = os.environ.copy()
        environment.update({
            "TEST_MARIADB_NAME": "test_twocomms_ig_contract",
            "TEST_MARIADB_USER": "test_user",
            "TEST_MARIADB_PASSWORD": "test_password",
            "TEST_MARIADB_HOST": "127.0.0.1",
            "TEST_MARIADB_PORT": "3306",
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
                    "assert settings.MIGRATION_MODULES == {}; "
                    "assert settings.DATABASE_ROUTERS == []; "
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
