import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALL_SCRIPT = REPO_ROOT / "scripts" / "install_product_catalog_image_jobs_cron.sh"
BEGIN_MARKER = "# BEGIN TWOCOMMS PRODUCT CATALOG IMAGE JOBS"


class InstallProductCatalogImageJobsCronTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.fake_bin = self.root / "bin"
        self.fake_bin.mkdir()
        self.crontab_file = self.root / "crontab"
        self.django_root = self.root / "TwoComms_Site" / "twocomms"
        self.django_root.mkdir(parents=True)
        (self.django_root / "manage.py").write_text("#!/bin/sh\n", encoding="utf-8")
        self.cloudlinux_wrapper = self.root / "lve-manager" / "utils" / "python_wrapper"
        self.cloudlinux_wrapper.parent.mkdir(parents=True)
        self.cloudlinux_wrapper.write_text(
            """#!/usr/bin/env bash
set -eu
if [ "${TWC_FAKE_PYTHON_FAIL:-0}" = 1 ]; then
  echo 'private DB_PASSWORD=must-not-leak' >&2
  exit 19
fi
if [ "${1:-}" = "-c" ]; then
  case "${2:-}" in *"SELECT VERSION()"*) ;; *) exit 23 ;; esac
  if [ "${TWC_FAKE_PYTHON_ENGINE:-mysql}" = "sqlite" ]; then
    printf '%s\\n' '{"conn_max_age":0,"engine":"django.db.backends.sqlite3","image_job_schema_ready":false,"mariadb":false}'
  else
    printf '%s\\n' '{"conn_max_age":0,"engine":"django.db.backends.mysql","image_job_schema_ready":'"${TWC_FAKE_IMAGE_SCHEMA_READY:-true}"',"mariadb":true}'
  fi
fi
""",
            encoding="utf-8",
        )
        self.cloudlinux_wrapper.chmod(0o700)
        self.python = self.root / "venv" / "bin" / "python"
        self.python.parent.mkdir(parents=True)
        self.python.symlink_to(self.cloudlinux_wrapper)
        self.flock = self.root / "flock"
        self.timeout = self.root / "timeout"
        self.nice = self.root / "nice"
        for path in (self.flock, self.timeout, self.nice):
            path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            path.chmod(path.stat().st_mode | stat.S_IXUSR)
        self._write_executable(
            "crontab",
            """#!/usr/bin/env bash
set -eu
if [ "${1:-}" = "-l" ]; then
  if [ -f "$FAKE_CRONTAB_FILE" ]; then cat "$FAKE_CRONTAB_FILE"; exit 0; fi
  echo 'no crontab for test' >&2
  exit 1
fi
cp "$1" "$FAKE_CRONTAB_FILE"
""",
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def _write_executable(self, name, content):
        path = self.fake_bin / name
        path.write_text(content, encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR)

    def _env(self):
        env = os.environ.copy()
        env.update({
            "PATH": f"{self.fake_bin}:/usr/bin:/bin",
            "FAKE_CRONTAB_FILE": str(self.crontab_file),
            "TWC_DJANGO_ROOT": str(self.django_root),
            "TWC_PYTHON": str(self.python),
            "TWC_CLOUDLINUX_PYTHON_WRAPPER": str(self.cloudlinux_wrapper),
            "TWC_FLOCK_BIN": str(self.flock),
            "TWC_TIMEOUT_BIN": str(self.timeout),
            "TWC_NICE_BIN": str(self.nice),
            "TWC_CRONTAB_BIN": "crontab",
        })
        return env

    def _run(self, mode, *, env=None):
        return subprocess.run(
            ["bash", str(INSTALL_SCRIPT), mode],
            env=env or self._env(),
            text=True,
            capture_output=True,
            timeout=10,
        )

    def test_install_is_idempotent_and_preserves_unrelated_cron(self):
        self.crontab_file.write_text("17 4 * * * /opt/other-job\n", encoding="utf-8")

        first = self._run("--install")
        first_content = self.crontab_file.read_text(encoding="utf-8")
        second = self._run("--install")

        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(self.crontab_file.read_text(encoding="utf-8"), first_content)
        self.assertIn("17 4 * * * /opt/other-job", first_content)
        self.assertEqual(first_content.count(BEGIN_MARKER), 1)
        self.assertIn("reconcile_image_optimization_jobs --max-jobs 4", first_content)
        self.assertIn("--allow-production", first_content)
        self.assertIn("DJANGO_ENV=production", first_content)
        self.assertIn("DJANGO_SETTINGS_MODULE=twocomms.production_settings", first_content)
        self.assertIn("--kill-after=30s 1500s", first_content)
        self.assertIn(str(self.flock), first_content)
        self.assertIn(str(self.timeout), first_content)
        self.assertIn(str(self.nice), first_content)

    def test_check_detects_missing_or_drifted_block(self):
        self.assertNotEqual(self._run("--check").returncode, 0)
        self.assertEqual(self._run("--install").returncode, 0)
        self.assertEqual(self._run("--check").returncode, 0)
        self.crontab_file.write_text("# drift\n", encoding="utf-8")
        self.assertNotEqual(self._run("--check").returncode, 0)

    def test_preflight_rejects_sqlite_or_missing_schema_without_crontab_write(self):
        original = "17 4 * * * /opt/other-job\n"
        self.crontab_file.write_text(original, encoding="utf-8")
        for key, value in (
            ("TWC_FAKE_PYTHON_ENGINE", "sqlite"),
            ("TWC_FAKE_IMAGE_SCHEMA_READY", "false"),
        ):
            with self.subTest(key=key):
                env = self._env()
                env[key] = value
                result = self._run("--install", env=env)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(
                    self.crontab_file.read_text(encoding="utf-8"), original
                )

    def test_preflight_failure_is_sanitized(self):
        env = self._env()
        env["TWC_FAKE_PYTHON_FAIL"] = "1"

        result = self._run("--check", env=env)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("preflight", result.stderr.lower())
        self.assertNotIn("DB_PASSWORD", result.stderr)

    def test_rejects_plain_python_and_duplicate_owner(self):
        self.python.unlink()
        self.python.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        self.python.chmod(0o700)
        plain_python = self._run("--install")
        self.assertNotEqual(plain_python.returncode, 0)
        self.assertIn("CloudLinux", plain_python.stderr)

        self.python.unlink()
        self.python.symlink_to(self.cloudlinux_wrapper)
        original = "* * * * * /srv/manage.py reconcile_image_optimization_jobs\n"
        self.crontab_file.write_text(original, encoding="utf-8")
        duplicate = self._run("--install")
        self.assertNotEqual(duplicate.returncode, 0)
        self.assertIn("outside", duplicate.stderr)
        self.assertEqual(self.crontab_file.read_text(encoding="utf-8"), original)

    def test_missing_explicit_runtime_fails_closed(self):
        env = self._env()
        env.pop("TWC_PYTHON")

        result = self._run("--install", env=env)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("TWC_PYTHON is required", result.stderr)
