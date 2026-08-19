from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "run_django61_migration_squash_gate.py"


def _valid_restore_drill():
    return {
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
            "source_database": "test_twocomms_mig_clean_0123456789ab",
            "destination_database": "test_twocomms_mig_restore_0123456789ab",
        },
        "rollback": {"status": "passed", "verified": True},
    }


def _valid_authoritative_history():
    return {
        "status": "passed",
        "authoritative": True,
        "read_only": True,
        "database_vendor": "mariadb",
        "database_alias": "default",
        "non_dtf_only": True,
        "source": "approved-read-only-export",
        "captured_at": "2026-08-19T12:00:00Z",
        "pending": 0,
        "applied_history_count": 461,
        "applied_history_hash": "a" * 64,
        "graph_fingerprint": "b" * 64,
    }


def _valid_mariadb_metadata_scope():
    return {
        "includes": [
            "tables",
            "columns",
            "indexes",
            "constraints",
            "checks",
            "foreign_keys",
            "triggers",
            "routines",
            "events",
        ],
        "dump_options": ["--routines", "--triggers", "--events"],
    }


def _valid_mariadb_rehearsal():
    return {
        "status": "passed",
        "database_vendor": "mariadb",
        "production_compatible": True,
        "server_version": "11.4.12-MariaDB",
        "disposable": True,
        "cleanup": {
            "status": "verified",
            "generated_databases_absent": True,
            "generated_user_absent": True,
            "temporary_dump_removed": True,
            "mariadb_process_closed": True,
        },
        "graph_fingerprint": "b" * 64,
        "schema_metadata_scope": _valid_mariadb_metadata_scope(),
        "clean_install": {
            "status": "passed",
            "pending": 0,
            "database": "test_twocomms_mig_clean_0123456789ab",
            "schema_hash": "c" * 64,
            "applied_history_hash": "a" * 64,
            "applied_history_count": 450,
            "schema_metadata_scope": _valid_mariadb_metadata_scope(),
            "trigger_count": 1,
            "routine_count": 0,
            "event_count": 0,
        },
        "replay": {
            "status": "passed",
            "pending": 0,
            "database": "test_twocomms_mig_restore_0123456789ab",
            "schema_hash": "c" * 64,
            "applied_history_hash": "a" * 64,
            "applied_history_count": 450,
            "schema_metadata_scope": _valid_mariadb_metadata_scope(),
            "trigger_count": 1,
            "routine_count": 0,
            "event_count": 0,
        },
        "restore_drill": _valid_restore_drill(),
        "authoritative_history_compatibility": {
            "status": "verified",
            "method": "migration_identity_set_review",
            "decision": "go",
            "graph_fingerprint": "b" * 64,
            "authoritative_graph_fingerprint": "b" * 64,
            "authoritative_pending": 0,
            "authoritative_applied_history_count": 461,
            "authoritative_applied_history_hash": "a" * 64,
            "current_applied_history_count": 450,
            "current_applied_history_hash": "a" * 64,
            "reviewer": "db-owner",
            "reviewed_at": "2026-08-19T12:00:00Z",
        },
    }


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
            "cleanup": {
                "status": "verified",
                "generated_databases_absent": True,
                "generated_user_absent": True,
                "temporary_dump_removed": True,
                "mariadb_process_closed": True,
            },
            "schema_metadata_scope": _valid_mariadb_metadata_scope(),
            "clean_install": {
                "status": "passed",
                "pending": 0,
                "database": "test_twocomms_mig_clean_0123456789ab",
                "schema_hash": "c" * 64,
                "applied_history_hash": "a" * 64,
                "applied_history_count": 450,
                "schema_metadata_scope": _valid_mariadb_metadata_scope(),
                "trigger_count": 1,
                "routine_count": 0,
                "event_count": 0,
            },
            "replay": {
                "status": "passed",
                "pending": 0,
                "database": "test_twocomms_mig_restore_0123456789ab",
                "schema_hash": "c" * 64,
                "applied_history_hash": "a" * 64,
                "applied_history_count": 450,
                "schema_metadata_scope": _valid_mariadb_metadata_scope(),
                "trigger_count": 1,
                "routine_count": 0,
                "event_count": 0,
            },
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
                    "source_database": "test_twocomms_mig_clean_0123456789ab",
                    "destination_database": "test_twocomms_mig_restore_0123456789ab",
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

    def test_mariadb_rehearsal_requires_two_database_schema_and_history_parity(self):
        from scripts import run_django61_migration_squash_gate as gate

        rehearsal = _valid_mariadb_rehearsal()
        rehearsal["clean_install"].update(
            {
                "database": "test_twocomms_mig_clean_0123456789ab",
                "schema_hash": "a" * 64,
                "applied_history_hash": "b" * 64,
                "applied_history_count": 450,
            }
        )
        rehearsal["replay"].update(
            {
                "database": "test_twocomms_mig_restore_0123456789ab",
                "schema_hash": "a" * 64,
                "applied_history_hash": "b" * 64,
                "applied_history_count": 450,
            }
        )
        rehearsal["restore_drill"]["restore"].update(
            {
                "destination_database": "test_twocomms_mig_restore_0123456789ab",
                "schema_hash_matches": True,
                "applied_history_matches": True,
            }
        )

        gate.validate_mariadb_rehearsal_evidence(rehearsal)

        del rehearsal["replay"]["schema_hash"]
        with self.assertRaisesRegex(gate.GateFailure, "mariadb_replay_schema_hash"):
            gate.validate_mariadb_rehearsal_evidence(rehearsal)

    def test_mariadb_schema_parity_ignores_dump_renamed_check_constraint(self):
        from scripts import run_django61_migration_squash_gate as gate

        # MariaDB's JSON alias creates an automatic CHECK whose name follows
        # the column. A logical dump can restore the same expression under the
        # final column-derived name, so the expression is the parity identity.
        source = gate._canonical_mariadb_check_clause(
            "CHECK (JSON_VALID(`data`))"
        )
        restored = gate._canonical_mariadb_check_clause(
            "check ( json_valid(data) )"
        )
        self.assertEqual(source, restored)
        self.assertEqual(
            gate._canonical_mariadb_check_clause(
                "CHECK (JSON_VALID(`extra_data`))"
            ),
            gate._canonical_mariadb_check_clause(
                " check ( json_valid(extra_data) ) "
            ),
        )

    def test_schema_hash_ignores_only_auto_json_check_name_drift_and_tracks_rest(self):
        from scripts import run_django61_migration_squash_gate as gate

        class FakeCursor:
            def __init__(self, responses):
                self.responses = responses
                self.current = ()

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def execute(self, statement):
                statement = " ".join(statement.split()).casefold()
                if "from information_schema.tables " in statement:
                    self.current = self.responses["tables"]
                elif "from information_schema.columns " in statement:
                    self.current = self.responses["columns"]
                elif "from information_schema.statistics " in statement:
                    self.current = self.responses["indexes"]
                elif "from information_schema.table_constraints " in statement:
                    self.current = self.responses["constraints"]
                elif "from information_schema.check_constraints " in statement:
                    self.current = self.responses["checks"]
                elif "from information_schema.key_column_usage " in statement:
                    self.current = self.responses["foreign_keys"]
                elif "from information_schema.triggers " in statement:
                    self.current = self.responses["triggers"]
                elif "from information_schema.routines " in statement:
                    self.current = self.responses["routines"]
                elif "from information_schema.events " in statement:
                    self.current = self.responses["events"]
                else:  # pragma: no cover - catches an incomplete metadata contract
                    raise AssertionError(statement)

            def fetchall(self):
                return list(self.current)

        class FakeConnection:
            def __init__(self, responses):
                self.responses = responses

            def cursor(self):
                return FakeCursor(self.responses)

        def metadata(check_name, trigger_statement="SET NEW.value = OLD.value"):
            return {
                "tables": [("example", "InnoDB", "BASE TABLE", "utf8mb4_unicode_ci")],
                "columns": [("example", "value", 1, None, "YES", "varchar", 20, None, None, "varchar(20)", "", "", "utf8mb4_unicode_ci")],
                "indexes": [],
                "constraints": [],
                "checks": [("example", check_name, "json_valid(`value`)")],
                "foreign_keys": [],
                "triggers": [("example_trigger", "example", "UPDATE", "BEFORE", 1, trigger_statement, "ROW", None, "OLD", "NEW")],
                "routines": [],
                "events": [],
            }

        source = gate._mariadb_schema_hash(FakeConnection(metadata("value_new")))
        restored = gate._mariadb_schema_hash(FakeConnection(metadata("value")))
        self.assertEqual(source[0], restored[0])

        renamed_user_check = gate._mariadb_schema_hash(
            FakeConnection(metadata("renamed_user_check"))
        )
        self.assertNotEqual(source[0], renamed_user_check[0])

        changed_trigger = gate._mariadb_schema_hash(
            FakeConnection(metadata("value_new", "SET NEW.value = 'changed'"))
        )
        self.assertNotEqual(source[0], changed_trigger[0])

        self.assertEqual(source[3:], (1, 0, 0))

    def test_database_cleanup_ownership_is_marked_before_ambiguous_create(self):
        from scripts import run_django61_migration_squash_gate as gate

        attempted = {}

        class AmbiguousAdmin:
            def create_database(self, database):
                raise RuntimeError("connection lost after CREATE DATABASE")

        with self.assertRaisesRegex(RuntimeError, "connection lost"):
            gate._create_owned_mariadb_database(
                AmbiguousAdmin(), "test_twocomms_mig_clean_0123456789ab", attempted
            )
        self.assertTrue(attempted["test_twocomms_mig_clean_0123456789ab"])

        class Cursor:
            def __init__(self, check_name):
                self.check_name = check_name
                self.rows = []

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def execute(self, statement):
                normalized = statement.casefold()
                if "information_schema.tables" in normalized:
                    self.rows = [
                        (
                            "social_auth_partial",
                            "InnoDB",
                            "BASE TABLE",
                            "utf8mb4_unicode_ci",
                        )
                    ]
                elif "information_schema.columns" in normalized:
                    self.rows = [
                        (
                            "social_auth_partial",
                            "data",
                            1,
                            None,
                            "NO",
                            "longtext",
                            None,
                            None,
                            None,
                            "longtext",
                            "",
                            "",
                            "utf8mb4_bin",
                        )
                    ]
                elif "information_schema.statistics" in normalized:
                    self.rows = []
                elif "information_schema.table_constraints" in normalized:
                    self.rows = (
                        []
                        if "constraint_type <> 'check'" in normalized
                        else [("social_auth_partial", self.check_name, "CHECK")]
                    )
                elif "information_schema.check_constraints" in normalized:
                    self.rows = [
                        ("social_auth_partial", "json_valid(`data`)")
                    ]
                elif "information_schema.key_column_usage" in normalized:
                    self.rows = []
                elif "information_schema.triggers" in normalized:
                    self.rows = []
                elif "information_schema.routines" in normalized:
                    self.rows = []
                elif "information_schema.events" in normalized:
                    self.rows = []
                else:
                    raise AssertionError(statement)

            def fetchall(self):
                return self.rows

        class Connection:
            def __init__(self, check_name):
                self.check_name = check_name

            def cursor(self):
                return Cursor(self.check_name)

        source_hash, *_ = gate._mariadb_schema_hash(Connection("data_new"))
        restored_hash, *_ = gate._mariadb_schema_hash(Connection("data"))
        self.assertEqual(source_hash, restored_hash)

    def test_mariadb_lifecycle_evidence_declares_cleanup_only_after_all_resources_are_verified(self):
        from scripts import run_django61_migration_squash_gate as gate

        metadata_scope = _valid_mariadb_metadata_scope()
        worker_result = {
            "graph_fingerprint": "a" * 64,
            "graph_node_count": 7,
            "graph_leaf_count": 2,
            "schema_object_count": 12,
            "schema_hash": "b" * 64,
            "applied_history_hash": "c" * 64,
            "applied": 7,
            "pending": 0,
            "schema_metadata_scope": metadata_scope,
            "trigger_count": 0,
            "routine_count": 0,
            "event_count": 0,
        }

        class Admin:
            host = "127.0.0.1"
            port = 3307

            def __init__(self):
                self.closed = False

            def server_identity(self):
                return {"version": "11.4.12-MariaDB", "version_comment": "MariaDB"}

            def ensure_namespace_absent(self, *_args):
                pass

            def create_database(self, *_args):
                pass

            def create_user(self, *_args):
                pass

            def grant_schema(self, *_args):
                pass

            def drop_user(self, *_args):
                pass

            def drop_database(self, *_args):
                pass

            def verify_cleanup(self, *_args):
                return False, False

            def close(self):
                self.closed = True

        admin = Admin()
        components = mock.Mock()
        components._native_admin.return_value = admin
        components._validate_server_identity.return_value = ("11.4.12-MariaDB", "MariaDB")
        components._process_environment.side_effect = lambda source: source
        observed = {}

        def capture_evidence(_path, payload):
            observed["payload"] = payload
            self.assertTrue(admin.closed)

        with tempfile.TemporaryDirectory(prefix="twc-migration-test-") as directory, \
            mock.patch.object(gate, "_mariadb_components", return_value=components), \
            mock.patch.object(gate, "_resolve_mariadb_client", return_value="mariadb"), \
            mock.patch.object(gate, "_run_mariadb_subprocess_worker", return_value=worker_result), \
            mock.patch.object(gate, "validate_mariadb_probe"), \
            mock.patch.object(gate, "_mariadb_dump", return_value="d" * 64), \
            mock.patch.object(gate, "_mariadb_restore"), \
            mock.patch.object(gate, "assess_authoritative_history_snapshot", return_value={"status": "stale"}), \
            mock.patch.object(gate, "_repo_sha", return_value="e" * 40), \
            mock.patch.object(gate, "write_evidence", side_effect=capture_evidence):
            gate.run_mariadb_lifecycle_gate(
                python=sys.executable,
                evidence_path=Path(directory) / "evidence.json",
                source_environment={"PATH": os.environ.get("PATH", "")},
            )

        cleanup = observed["payload"]["cleanup"]
        self.assertEqual(
            cleanup,
            {
                "status": "verified",
                "generated_databases_absent": True,
                "generated_user_absent": True,
                "temporary_dump_removed": True,
                "mariadb_process_closed": True,
            },
        )
        rendered = json.dumps(cleanup, sort_keys=True)
        self.assertNotIn("127.0.0.1", rendered)
        self.assertNotIn("3307", rendered)

    def test_mariadb_lifecycle_does_not_write_evidence_when_cleanup_fails(self):
        from scripts import run_django61_migration_squash_gate as gate

        metadata_scope = _valid_mariadb_metadata_scope()
        worker_result = {
            "graph_fingerprint": "a" * 64,
            "graph_node_count": 7,
            "graph_leaf_count": 2,
            "schema_object_count": 12,
            "schema_hash": "b" * 64,
            "applied_history_hash": "c" * 64,
            "applied": 7,
            "pending": 0,
            "schema_metadata_scope": metadata_scope,
            "trigger_count": 0,
            "routine_count": 0,
            "event_count": 0,
        }

        class Admin:
            host = "127.0.0.1"
            port = 3307

            def server_identity(self):
                return {"version": "11.4.12-MariaDB", "version_comment": "MariaDB"}

            def ensure_namespace_absent(self, *_args):
                pass

            def create_database(self, *_args):
                pass

            def create_user(self, *_args):
                pass

            def grant_schema(self, *_args):
                pass

            def drop_user(self, *_args):
                raise RuntimeError("drop failed")

            def drop_database(self, *_args):
                pass

            def verify_cleanup(self, *_args):
                return False, False

            def close(self):
                pass

        components = mock.Mock()
        components._native_admin.return_value = Admin()
        components._validate_server_identity.return_value = ("11.4.12-MariaDB", "MariaDB")
        components._process_environment.side_effect = lambda source: source
        write = mock.Mock()

        with tempfile.TemporaryDirectory(prefix="twc-migration-test-") as directory, \
            mock.patch.object(gate, "_mariadb_components", return_value=components), \
            mock.patch.object(gate, "_resolve_mariadb_client", return_value="mariadb"), \
            mock.patch.object(gate, "_run_mariadb_subprocess_worker", return_value=worker_result), \
            mock.patch.object(gate, "validate_mariadb_probe"), \
            mock.patch.object(gate, "_mariadb_dump", return_value="d" * 64), \
            mock.patch.object(gate, "_mariadb_restore"), \
            mock.patch.object(gate, "assess_authoritative_history_snapshot", return_value={"status": "stale"}), \
            mock.patch.object(gate, "_repo_sha", return_value="e" * 40), \
            mock.patch.object(gate, "write_evidence", write):
            with self.assertRaisesRegex(gate.GateFailure, "mariadb_lifecycle_cleanup_failed"):
                gate.run_mariadb_lifecycle_gate(
                    python=sys.executable,
                    evidence_path=Path(directory) / "evidence.json",
                    source_environment={"PATH": os.environ.get("PATH", "")},
                )

        write.assert_not_called()

    def test_mariadb_rehearsal_requires_verified_cleanup_evidence(self):
        from scripts import run_django61_migration_squash_gate as gate

        rehearsal = _valid_mariadb_rehearsal()
        del rehearsal["cleanup"]["temporary_dump_removed"]
        with self.assertRaisesRegex(gate.GateFailure, "mariadb_cleanup_temporary_dump_removed_missing"):
            gate.validate_mariadb_rehearsal_evidence(rehearsal)

    def test_stale_authoritative_snapshot_is_evidence_but_never_an_approval(self):
        from scripts import run_django61_migration_squash_gate as gate

        current = {
            "graph_fingerprint": "c" * 64,
            "applied": 470,
            "applied_history_hash": "d" * 64,
        }
        with tempfile.TemporaryDirectory(prefix="twc-migration-test-") as directory:
            evidence = Path(directory) / "history.json"
            evidence.write_text(
                json.dumps(_valid_authoritative_history()), encoding="utf-8"
            )
            compatibility = gate.assess_authoritative_history_snapshot(
                current, evidence_path=evidence
            )

        self.assertEqual(
            compatibility["status"], "snapshot_graph_diverged"
        )
        self.assertEqual(
            compatibility["decision"],
            "no-go_until_fresh_read_only_identity_set_review",
        )
        rehearsal = _valid_mariadb_rehearsal()
        rehearsal["graph_fingerprint"] = "c" * 64
        rehearsal["clean_install"].update(
            {"applied_history_count": 470, "applied_history_hash": "d" * 64}
        )
        rehearsal["replay"].update(
            {"applied_history_count": 470, "applied_history_hash": "d" * 64}
        )
        rehearsal["authoritative_history_compatibility"] = compatibility
        decision = gate.build_decision(
            sqlite_clean_install=True,
            sqlite_restore=True,
            authoritative_applied_history=True,
            mariadb_clean_install=True,
            approved_ranges=True,
            authoritative_evidence=_valid_authoritative_history(),
            mariadb_evidence=rehearsal,
            restore_evidence=_valid_restore_drill(),
        )
        self.assertEqual(decision["decision"], "no-go")
        self.assertIn(
            "authoritative_history_compatibility_invalid",
            decision["blocking_conditions"],
        )

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

    def test_squash_readiness_never_authorizes_historical_file_deletion(self):
        from scripts import run_django61_migration_squash_gate as gate

        decision = gate.build_decision(
            sqlite_clean_install=True,
            sqlite_restore=True,
            authoritative_applied_history=True,
            mariadb_clean_install=True,
            approved_ranges=True,
            authoritative_evidence=_valid_authoritative_history(),
            mariadb_evidence=_valid_mariadb_rehearsal(),
            restore_evidence=_valid_restore_drill(),
        )

        self.assertEqual(decision["decision"], "go")
        self.assertTrue(decision["squash_may_run"])
        self.assertFalse(decision["historical_migrations_may_be_deleted"])
        self.assertIn(
            "follow_up_release_required",
            decision["post_squash_requirements"],
        )

    def test_metadata_manifest_requires_matching_graph_and_preserves_history(self):
        from scripts import run_django61_migration_squash_gate as gate

        manifest = gate.build_squash_artifact_manifest(
            graph_fingerprint="b" * 64,
            authoritative_evidence=_valid_authoritative_history(),
            mariadb_evidence=_valid_mariadb_rehearsal(),
            restore_evidence=_valid_restore_drill(),
            approved_ranges={
                "status": "approved",
                "scope": "non_dtf",
                "graph_fingerprint": "b" * 64,
                "reviewer": "db-owner",
                "approved_at": "2026-08-19T12:00:00Z",
                "ranges": [
                    {
                        "app": "accounts",
                        "start": "0001_initial",
                        "end": "0030_latest",
                        "replacement": "0001_squashed_0030_latest",
                    }
                ],
            },
        )

        self.assertEqual(manifest["status"], "ready")
        self.assertEqual(manifest["artifact_type"], "metadata_only")
        self.assertEqual(manifest["graph_fingerprint"], "b" * 64)
        self.assertFalse(manifest["historical_migrations_deleted"])
        self.assertFalse(manifest["squash_executed"])
        self.assertEqual(len(manifest["approved_ranges_evidence_sha256"]), 64)

        with self.assertRaisesRegex(gate.GateFailure, "graph_fingerprint_mismatch"):
            gate.build_squash_artifact_manifest(
                graph_fingerprint="c" * 64,
                authoritative_evidence=_valid_authoritative_history(),
                mariadb_evidence=_valid_mariadb_rehearsal(),
                restore_evidence=_valid_restore_drill(),
                approved_ranges={
                    "status": "approved",
                    "scope": "non_dtf",
                    "graph_fingerprint": "b" * 64,
                    "reviewer": "db-owner",
                    "approved_at": "2026-08-19T12:00:00Z",
                    "ranges": [
                        {
                            "app": "accounts",
                            "start": "0001_initial",
                            "end": "0030_latest",
                            "replacement": "0001_squashed_0030_latest",
                        }
                    ],
                },
            )

        stale_snapshot = _valid_mariadb_rehearsal()
        stale_snapshot["clean_install"]["applied_history_hash"] = "d" * 64
        stale_snapshot["replay"]["applied_history_hash"] = "d" * 64
        stale_snapshot["authoritative_history_compatibility"]["current_applied_history_hash"] = "d" * 64
        stale_snapshot["authoritative_history_compatibility"]["status"] = (
            "snapshot_graph_diverged"
        )
        stale_snapshot["authoritative_history_compatibility"]["decision"] = (
            "no-go_until_fresh_read_only_identity_set_review"
        )
        with self.assertRaisesRegex(
            gate.GateFailure, "authoritative_history_compatibility_not_verified"
        ):
            gate.build_squash_artifact_manifest(
                graph_fingerprint="b" * 64,
                authoritative_evidence=_valid_authoritative_history(),
                mariadb_evidence=stale_snapshot,
                restore_evidence=_valid_restore_drill(),
                approved_ranges={
                    "status": "approved",
                    "scope": "non_dtf",
                    "graph_fingerprint": "b" * 64,
                    "reviewer": "db-owner",
                    "approved_at": "2026-08-19T12:00:00Z",
                    "ranges": [
                        {
                            "app": "accounts",
                            "start": "0001_initial",
                            "end": "0030_latest",
                            "replacement": "0001_squashed_0030_latest",
                        }
                    ],
                },
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
