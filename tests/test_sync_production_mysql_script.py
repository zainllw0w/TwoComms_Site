"""Safety contracts for the one-way production MariaDB snapshot pull."""

from __future__ import annotations

import gzip
import os
import stat
import subprocess
import tempfile
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SYNC_SCRIPT = ROOT / "scripts" / "sync_production_mysql.sh"


class SyncProductionMySQLTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.fake_bin = self.root / "bin"
        self.fake_bin.mkdir()
        self.sync_root = self.root / "sync"
        self.defaults_file = self.home / ".my.cnf"
        self.defaults_file.write_text(
            "[client]\nuser=local\npassword=local\n", encoding="utf-8"
        )
        self.defaults_file.chmod(0o600)
        self.invocations = self.root / "invocations.log"
        self._write_executable(
            "sshpass",
            """#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" = "-e" ]]; then shift; fi
exec "$@"
""",
        )
        self._write_executable(
            "ssh",
            """#!/usr/bin/env bash
set -euo pipefail
printf 'ssh %s\n' "$*" >> "$FAKE_INVOCATIONS"
if [[ "${FAKE_REMOTE_FAIL:-0}" = "1" ]]; then exit 42; fi
printf '%s\n' 'CREATE TABLE sample (id integer);'
printf '%s\n' 'INSERT INTO sample VALUES (1);'
""",
        )
        self._write_executable(
            "mariadb-dump",
            """#!/usr/bin/env bash
set -euo pipefail
printf 'dump %s\n' "$*" >> "$FAKE_INVOCATIONS"
printf '%s\n' 'CREATE TABLE sample (id integer);'
printf '%s\n' 'INSERT INTO sample VALUES (1);'
""",
        )
        self._write_executable(
            "mariadb",
            """#!/usr/bin/env bash
set -euo pipefail
printf 'client %s\n' "$*" >> "$FAKE_INVOCATIONS"
query=''
for ((i=1; i <= $#; i++)); do
  arg="${!i}"
  if [[ "$arg" = "-e" || "$arg" = "--execute" ]]; then
    j=$((i + 1)); query="${!j}"
  elif [[ "$arg" = --execute=* ]]; then
    query="${arg#--execute=}"
  fi
done
if [[ "$query" == *"COUNT(*)"* || "$query" == *"schema_name"* ]]; then
  printf '1\n'
fi
if [[ "${FAKE_TARGET_CREATE_FAIL_ONCE:-0}" = "1" \
      && "$query" == *'CREATE DATABASE `twc_snapshot_main_db` '* \
      && ! -e "$FAKE_CREATE_FAILURE_MARKER" ]]; then
  : > "$FAKE_CREATE_FAILURE_MARKER"
  exit 77
fi
cat >/dev/null
""",
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def _write_executable(self, name: str, content: str) -> Path:
        path = self.fake_bin / name
        path.write_text(content, encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
        return path

    def _env(self, **overrides: str) -> dict[str, str]:
        environment = os.environ.copy()
        environment.update(
            {
                "HOME": str(self.home),
                "PATH": f"{self.fake_bin}:/usr/bin:/bin",
                "TWOCOMMS_SYNC_ROOT": str(self.sync_root),
                "TWOCOMMS_LOCAL_MYSQL_DEFAULTS_FILE": str(self.defaults_file),
                "TWOCOMMS_REMOTE_DB_NAMES": "main_db",
                "TWOCOMMS_DEPLOY_PASSWORD": "secret-must-not-leak",
                "TWOCOMMS_MIN_DUMP_BYTES": "20",
                "TWOCOMMS_LOCAL_DB_PREFIX": "twc_snapshot_",
                "TWOCOMMS_SNAPSHOT_RETENTION_DAYS": "7",
                "TWOCOMMS_SSH_HOST": "127.0.0.1",
                "TWOCOMMS_SSH_USER": "fixture-user",
                "TWOCOMMS_REMOTE_PROJECT": "/srv/twocomms",
                "TWOCOMMS_REMOTE_VENV": "/srv/venv/bin/activate",
                "FAKE_INVOCATIONS": str(self.invocations),
                "FAKE_CREATE_FAILURE_MARKER": str(self.root / "create-failed"),
            }
        )
        environment.update(overrides)
        return environment

    def _run(self, *args: str, **overrides: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(SYNC_SCRIPT), *args],
            env=self._env(**overrides),
            text=True,
            capture_output=True,
            timeout=20,
            check=False,
        )

    def test_repository_entry_point_is_executable(self):
        self.assertTrue(os.access(SYNC_SCRIPT, os.X_OK))

    def test_apply_requires_confirmation_and_password(self):
        result = self._run("--apply")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("confirm-production-snapshot", result.stderr)
        self.assertFalse(self.invocations.exists())

        result = self._run(
            "--apply",
            "--confirm-production-snapshot",
            TWOCOMMS_DEPLOY_PASSWORD="",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("TWOCOMMS_DEPLOY_PASSWORD", result.stderr)

    def test_apply_and_dry_run_flags_cannot_be_combined_in_either_order(self):
        for arguments in (
            ("--dry-run", "--apply", "--confirm-production-snapshot"),
            ("--apply", "--dry-run", "--confirm-production-snapshot"),
        ):
            with self.subTest(arguments=arguments):
                result = self._run(*arguments)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("cannot be combined", result.stderr)
                self.assertFalse(self.invocations.exists())

    def test_script_has_no_embedded_production_connection_identifiers(self):
        source = SYNC_SCRIPT.read_text(encoding="utf-8")
        for marker in (
            "195.191.25.63",
            "qlknpodo@",
            "/home/qlknpodo/",
        ):
            self.assertNotIn(marker, source)

    def test_database_name_is_required_and_remote_auto_list_is_forbidden(self):
        result = self._run(
            "--apply",
            "--confirm-production-snapshot",
            TWOCOMMS_REMOTE_DB_NAMES="",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("explicit", result.stderr.lower())
        self.assertFalse(self.invocations.exists())

    def test_dtf_database_is_rejected_before_any_client_call(self):
        for name in ("dtf", "dtf_db", "QLKNPODO_DTF_DB", "archive-dtf"):
            with self.subTest(name=name):
                result = self._run(
                    "--apply",
                    "--confirm-production-snapshot",
                    TWOCOMMS_REMOTE_DB_NAMES=name,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("dtf", result.stderr.lower())
                self.assertFalse(self.invocations.exists())

    def test_only_one_non_dtf_database_can_be_synchronized(self):
        result = self._run(
            "--apply",
            "--confirm-production-snapshot",
            TWOCOMMS_REMOTE_DB_NAMES="main_db,second_db",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("exactly one", result.stderr.lower())
        self.assertFalse(self.invocations.exists())

    def test_rejects_non_loopback_or_missing_disposable_prefix(self):
        result = self._run(
            "--apply",
            "--confirm-production-snapshot",
            TWOCOMMS_LOCAL_HOST="db.example.invalid",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("loopback", result.stderr.lower())

        result = self._run(
            "--apply",
            "--confirm-production-snapshot",
            TWOCOMMS_LOCAL_DB_PREFIX="",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("prefix", result.stderr.lower())

    def test_dry_run_is_side_effect_free_and_prints_resolved_target(self):
        result = self._run("--dry-run")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("twc_snapshot_main_db", result.stdout)
        self.assertFalse(self.invocations.exists())
        self.assertFalse(self.sync_root.exists())

    def test_remote_dump_failure_publishes_no_archive_or_secret(self):
        result = self._run(
            "--apply",
            "--confirm-production-snapshot",
            FAKE_REMOTE_FAIL="1",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(list(self.sync_root.rglob("*.sql.gz")), [])
        self.assertNotIn("secret-must-not-leak", result.stdout + result.stderr)

    def test_partial_target_ddl_failure_restores_rollback_and_keeps_it_private(self):
        result = self._run(
            "--apply",
            "--confirm-production-snapshot",
            FAKE_TARGET_CREATE_FAIL_ONCE="1",
        )

        self.assertNotEqual(result.returncode, 0)
        rollback = list((self.sync_root / "rollback").glob("*.sql.gz"))
        self.assertEqual(len(rollback), 1)
        self.assertEqual(stat.S_IMODE(rollback[0].stat().st_mode), 0o600)
        self.assertEqual(list((self.sync_root / "incoming").glob("*.sql.gz")), [])
        self.assertEqual(list((self.sync_root / "snapshots").glob("*.sql.gz")), [])
        invocations = self.invocations.read_text(encoding="utf-8")
        self.assertGreaterEqual(
            invocations.count("CREATE DATABASE `twc_snapshot_main_db`"),
            2,
        )

    def test_success_prunes_only_owned_expired_archives(self):
        snapshots = self.sync_root / "snapshots"
        rollback = self.sync_root / "rollback"
        snapshots.mkdir(parents=True)
        rollback.mkdir(parents=True)
        expired_snapshot = snapshots / "default-20000101000000-1.sql.gz"
        expired_rollback = rollback / "local-default-20000101000000-1.sql.gz"
        sentinel = snapshots / "do-not-delete.sql.gz"
        recent = snapshots / "default-recent.sql.gz"
        for path in (expired_snapshot, expired_rollback, sentinel, recent):
            path.write_bytes(b"private")
        old = time.time() - 10 * 24 * 60 * 60
        os.utime(expired_snapshot, (old, old))
        os.utime(expired_rollback, (old, old))

        result = self._run(
            "--apply",
            "--confirm-production-snapshot",
            TWOCOMMS_SNAPSHOT_RETENTION_DAYS="7",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(expired_snapshot.exists())
        self.assertFalse(expired_rollback.exists())
        self.assertTrue(sentinel.exists())
        self.assertTrue(recent.exists())

    def test_success_keeps_private_snapshot_and_uses_nonlocking_dump_flags(self):
        result = self._run("--apply", "--confirm-production-snapshot")

        self.assertEqual(result.returncode, 0, result.stderr)
        snapshots = list((self.sync_root / "snapshots").glob("*.sql.gz"))
        self.assertEqual(len(snapshots), 1)
        self.assertEqual(stat.S_IMODE(snapshots[0].stat().st_mode), 0o600)
        with gzip.open(snapshots[0], "rt", encoding="utf-8") as dump:
            self.assertIn("CREATE TABLE sample", dump.read())
        invocations = self.invocations.read_text(encoding="utf-8")
        self.assertIn("--single-transaction", invocations)
        self.assertIn("--skip-lock-tables", invocations)
        self.assertNotIn("dtf_db", invocations.casefold())
        self.assertNotIn(".twocomms_backup_dbs", invocations)
        self.assertIn("production_settings", invocations)
        self.assertIn("DATABASES", invocations)
        self.assertIn("bash -lc", invocations)
        self.assertNotIn("manage.py shell", invocations)
        self.assertEqual(list(self.sync_root.rglob("*.tmp.*")), [])
        self.assertNotIn("secret-must-not-leak", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
