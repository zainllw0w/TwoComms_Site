from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "run_django61_migration_squash_gate.py"


class MigrationSquashGateUnitTests(unittest.TestCase):
    def test_safe_environment_strips_credentials_and_forces_non_dtf_profile(self):
        from scripts import run_django61_migration_squash_gate as gate

        with tempfile.TemporaryDirectory(prefix="twc-migration-test-") as directory:
            root = Path(directory)
            database = root / "clean.sqlite3"
            environment = gate.safe_worker_environment(
                database_path=database,
                temp_root=root,
                source={
                    "PATH": os.environ.get("PATH", ""),
                    "SECRET_KEY": "production-secret",
                    "DATABASE_URL": "mysql://prod:secret@example.invalid/prod",
                    "DB_NAME": "production",
                    "DB_NAME_DTF": "dtf-production",
                    "TELEGRAM_BOT_TOKEN": "production-token",
                },
            )

        rendered = json.dumps(environment, sort_keys=True)
        self.assertNotIn("production-secret", rendered)
        self.assertNotIn("mysql://", rendered)
        self.assertNotIn("production-token", rendered)
        self.assertNotIn("DB_NAME", environment)
        self.assertNotIn("DB_NAME_DTF", environment)
        self.assertNotIn("DJANGO_ENV_FILE", environment)
        self.assertEqual(
            environment["DJANGO_SETTINGS_MODULE"],
            "test_settings_migrations_non_dtf",
        )
        self.assertEqual(environment["DJANGO_ENV"], "development")
        self.assertEqual(environment["DJANGO61_MIGRATION_REHEARSAL"], "1")

    def test_explicit_production_context_is_refused(self):
        from scripts import run_django61_migration_squash_gate as gate

        for environment in (
            {"DJANGO_ENV": "production"},
            {"DJANGO_ENV_FILE": "/srv/site/.env.production"},
        ):
            with self.subTest(environment=environment), self.assertRaisesRegex(
                gate.GateFailure, "production_context_forbidden"
            ):
                gate.assert_local_only_environment(environment)

    def test_disposable_database_must_stay_inside_owned_temp_root(self):
        from scripts import run_django61_migration_squash_gate as gate

        with tempfile.TemporaryDirectory(prefix="twc-migration-test-") as directory:
            root = Path(directory)
            accepted = gate.validate_disposable_database_path(
                root / "clean.sqlite3", root
            )
            self.assertEqual(accepted, (root / "clean.sqlite3").resolve())

            for invalid in (
                root.parent / "outside.sqlite3",
                root / "not-sqlite.db",
                Path("relative.sqlite3"),
            ):
                with self.subTest(invalid=invalid), self.assertRaises(
                    gate.GateFailure
                ):
                    gate.validate_disposable_database_path(invalid, root)

    def test_probe_validation_blocks_every_dtf_surface(self):
        from scripts import run_django61_migration_squash_gate as gate

        clean = {
            "status": "ok",
            "database_vendor": "sqlite",
            "settings": "test_settings_migrations_non_dtf",
            "network_policy": "deny-external",
            "database_aliases": ["default"],
            "actual_dtf_app_loaded": False,
            "dtf_stub": "test_support.dtf_stub",
            "dtf_stub_nodes": [
                "dtf.0004_dtfsamplelead_alter_dtforder_length_source_and_more"
            ],
            "dtf_tables": [],
            "dtf_real_modules": [],
            "pending": 0,
            "consistent_history": True,
            "graph_fingerprint": "graph",
            "schema_hash": "schema",
        }
        gate.validate_probe(clean)

        mutations = (
            ("actual_dtf_app_loaded", True),
            ("dtf_stub", "dtf"),
            ("dtf_tables", ["dtf_order"]),
            ("dtf_real_modules", ["dtf.migrations.0001_initial"]),
            ("pending", 1),
            ("consistent_history", False),
            ("database_vendor", "mysql"),
        )
        for key, value in mutations:
            with self.subTest(key=key):
                payload = {**clean, key: value}
                with self.assertRaises(gate.GateFailure):
                    gate.validate_probe(payload)

    def test_candidate_inventory_is_advisory_and_fail_closed(self):
        from scripts import run_django61_migration_squash_gate as gate

        candidate = gate.classify_candidate(
            {
                "app": "management",
                "migration_count": 170,
                "first": "0001_initial",
                "leafs": ["0168_call_auto_analysis_enabled"],
                "data_or_sql_migrations": 40,
                "irreversible_operations": 3,
                "atomic_false_migrations": 18,
                "cross_app_dependencies": 9,
                "replaced_migrations": 0,
            }
        )
        self.assertTrue(candidate["candidate"])
        self.assertEqual(candidate["eligibility"], "blocked")
        self.assertEqual(candidate["risk"], "high")
        self.assertIn("authoritative_applied_history_missing", candidate["blockers"])
        self.assertIn("mariadb_clean_install_missing", candidate["blockers"])
        self.assertNotIn("suggested_squash_range", candidate)

        small = gate.classify_candidate(
            {
                "app": "reviews",
                "migration_count": 1,
                "first": "0001_initial",
                "leafs": ["0001_initial"],
                "data_or_sql_migrations": 0,
                "irreversible_operations": 0,
                "atomic_false_migrations": 0,
                "cross_app_dependencies": 0,
                "replaced_migrations": 0,
            }
        )
        self.assertFalse(small["candidate"])
        self.assertEqual(small["eligibility"], "not_candidate")

    def test_decision_remains_no_go_after_sqlite_rehearsal(self):
        from scripts import run_django61_migration_squash_gate as gate

        decision = gate.build_decision(
            sqlite_clean_install=True,
            sqlite_restore=True,
            authoritative_applied_history=False,
            mariadb_clean_install=False,
            approved_ranges=False,
        )

        self.assertEqual(decision["decision"], "no-go")
        self.assertEqual(
            decision["blocking_conditions"],
            [
                "authoritative_applied_history_missing",
                "mariadb_clean_install_missing",
                "approved_squash_ranges_missing",
            ],
        )
        self.assertFalse(decision["historical_migrations_may_be_deleted"])
        self.assertFalse(decision["squash_may_run"])

    def test_authoritative_history_rejects_sqlite_and_requires_read_only_mariadb(
        self,
    ):
        from scripts import run_django61_migration_squash_gate as gate

        history = {
            "status": "passed",
            "authoritative": True,
            "read_only": True,
            "database_vendor": "sqlite",
            "database_alias": "default",
            "non_dtf_only": True,
            "source": "local-rehearsal",
            "captured_at": "2026-08-18T12:00:00Z",
            "pending": 0,
            "applied_history_count": 450,
            "applied_history_hash": "a" * 64,
            "graph_fingerprint": "b" * 64,
        }
        with self.assertRaisesRegex(
            gate.GateFailure, "requires_mariadb"
        ):
            gate.validate_authoritative_applied_history(history)

        history["database_vendor"] = "mariadb"
        gate.validate_authoritative_applied_history(history)

    def test_mariadb_rehearsal_requires_clean_replay_and_restore_drill(self):
        from scripts import run_django61_migration_squash_gate as gate

        rehearsal = {
            "status": "passed",
            "database_vendor": "mysql",
            "production_compatible": True,
            "server_version": "11.4.12-MariaDB",
            "disposable": True,
            "clean_install": {"status": "passed", "pending": 0},
            "replay": {"status": "passed", "pending": 0},
            "restore_drill": {
                "status": "passed",
                "disposable": True,
                "backup": {
                    "status": "passed",
                    "artifact_id": "mariadb-fixture-1",
                    "sha256": "c" * 64,
                },
                "restore": {
                    "status": "passed",
                    "integrity_check": True,
                    "schema_hash_matches": True,
                    "applied_history_matches": True,
                },
                "rollback": {"status": "passed", "verified": True},
            },
        }
        gate.validate_mariadb_rehearsal_evidence(rehearsal)

        rehearsal["server_version"] = "8.0.36"
        with self.assertRaisesRegex(
            gate.GateFailure, "requires_mariadb_server"
        ):
            gate.validate_mariadb_rehearsal_evidence(rehearsal)
        rehearsal["server_version"] = "11.4.12-MariaDB"
        rehearsal["replay"] = {"status": "passed", "pending": 1}
        with self.assertRaisesRegex(gate.GateFailure, "mariadb_replay_pending"):
            gate.validate_mariadb_rehearsal_evidence(rehearsal)

    def test_go_claim_fails_closed_without_external_evidence(self):
        from scripts import run_django61_migration_squash_gate as gate

        decision = gate.build_decision(
            sqlite_clean_install=True,
            sqlite_restore=True,
            authoritative_applied_history=True,
            mariadb_clean_install=True,
            approved_ranges=True,
        )
        self.assertEqual(decision["decision"], "no-go")
        self.assertIn(
            "authoritative_applied_history_evidence_missing",
            decision["blocking_conditions"],
        )
        self.assertIn(
            "mariadb_clean_install_evidence_missing",
            decision["blocking_conditions"],
        )
        self.assertIn(
            "backup_restore_evidence_missing", decision["blocking_conditions"]
        )

    def test_sqlite_restore_uses_backup_api_and_preserves_content(self):
        from scripts import run_django61_migration_squash_gate as gate

        with tempfile.TemporaryDirectory(prefix="twc-migration-test-") as directory:
            root = Path(directory)
            source = root / "source.sqlite3"
            restored = root / "restored.sqlite3"
            with sqlite3.connect(source) as connection:
                connection.execute("CREATE TABLE proof (value TEXT NOT NULL)")
                connection.execute("INSERT INTO proof VALUES ('restored')")

            gate.restore_sqlite(source, restored, temp_root=root)

            with sqlite3.connect(restored) as connection:
                value = connection.execute("SELECT value FROM proof").fetchone()[0]
            self.assertEqual(value, "restored")

    def test_evidence_write_is_atomic_private_and_sanitized(self):
        from scripts import run_django61_migration_squash_gate as gate

        with tempfile.TemporaryDirectory(prefix="twc-migration-test-") as directory:
            evidence = Path(directory) / "evidence.json"
            gate.write_evidence(
                evidence,
                {
                    "status": "passed",
                    "decision": "no-go",
                    "database": "disposable-sqlite",
                },
            )
            payload = json.loads(evidence.read_text(encoding="utf-8"))

            self.assertEqual(payload["decision"], "no-go")
            self.assertEqual(evidence.stat().st_mode & 0o777, 0o600)
            self.assertFalse((evidence.parent / f".{evidence.name}.tmp").exists())


class MigrationSquashGateCliTests(unittest.TestCase):
    def test_cli_requires_explicit_local_rehearsal_flag(self):
        with tempfile.TemporaryDirectory(prefix="twc-migration-test-") as directory:
            result = subprocess.run(
                [sys.executable, str(RUNNER), "--evidence", str(Path(directory) / "x.json")],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("allow-local-sqlite-rehearsal", result.stderr)


if __name__ == "__main__":
    unittest.main()
