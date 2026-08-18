import io
import json
import os
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "twocomms"))
os.environ.setdefault("DEBUG", "1")
os.environ.setdefault("SECRET_KEY", "django61-db-actions-test")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "twocomms.settings")

import django

django.setup()

from scripts import audit_django61_db_actions as db_actions


class FakeInspector:
    def inspect(self, relation):
        self.relation = relation
        return {
            "child_engine": "InnoDB",
            "parent_engine": "InnoDB",
            "constraint_name": "fk_pageview_session",
            "delete_rule": "RESTRICT",
            "orphan_count": 0,
            "show_create_sha256": "a" * 64,
        }


class Django61DbActionsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.relations = db_actions.collect_static_inventory()
        cls.retention = next(
            row
            for row in cls.relations
            if row["field_label"] == "storefront.PageView.session"
        )

    def test_static_inventory_excludes_dtf_and_captures_retention_contract(self):
        self.assertTrue(self.relations)
        self.assertFalse(
            any(
                row["child_app"] == "dtf"
                or row["parent_app"] == "dtf"
                or row["child_table"].startswith("dtf_")
                or row["parent_table"].startswith("dtf_")
                for row in self.relations
            )
        )
        self.assertEqual(self.retention["on_delete"], "CASCADE")
        self.assertTrue(self.retention["db_constraint"])
        self.assertEqual(self.retention["soft_delete_fields"], [])
        self.assertEqual(self.retention["mandatory_delete_receivers"], [])
        self.assertEqual(
            self.retention["non_mandatory_delete_receivers"],
            [
                "storefront.signals.cancel_deleted_image_optimization",
                "warehouse.signals.warehouse_delete_print_images",
            ],
        )
        self.assertEqual(
            self.retention["python_on_delete_siblings"],
            ["storefront.PageView.user:SET_NULL"],
        )

    def test_database_facts_and_rollback_are_fail_closed(self):
        enriched = db_actions.enrich_inventory([self.retention], FakeInspector())[0]
        decision = db_actions.assess_db_cascade(enriched)

        self.assertEqual(decision["decision"], "NO-GO")
        self.assertIn("mixed_on_delete_models.E050", decision["blockers"])
        self.assertEqual(decision["database"]["delete_rule"], "RESTRICT")
        self.assertEqual(
            decision["rollback"]["strategy"],
            "reverse_AlterField_and_restore_captured_fk",
        )
        self.assertTrue(decision["rollback"]["ready"])

        ready = dict(enriched)
        ready["python_on_delete_siblings"] = []
        self.assertEqual(db_actions.assess_db_cascade(ready)["decision"], "GO")

        for key, value, expected in (
            ("child_engine", "MyISAM", "child_engine_not_innodb"),
            ("constraint_name", None, "real_fk_missing"),
            ("orphan_count", 1, "orphan_rows_present"),
        ):
            blocked = dict(ready)
            blocked["database"] = dict(ready["database"])
            blocked["database"][key] = value
            self.assertIn(expected, db_actions.assess_db_cascade(blocked)["blockers"])

    def test_companion_design_is_structured_and_e050_safe_only_after_siblings_map(self):
        relation = {
            "field_label": "sample.Event.session",
            "on_delete": "CASCADE",
            "python_on_delete_siblings": ["sample.Event.owner:SET_NULL"],
        }
        sibling = {
            "field_label": "sample.Event.owner",
            "on_delete": "SET_NULL",
            "null": True,
            "has_default": False,
        }

        design = db_actions.build_companion_action_design(
            relation,
            {sibling["field_label"]: sibling},
        )

        self.assertEqual(design["status"], "ready")
        self.assertTrue(design["e050_safe"])
        self.assertEqual(design["target_action"], "DB_CASCADE")
        self.assertEqual(
            design["companions"],
            [
                {
                    "field_label": "sample.Event.owner",
                    "current_action": "SET_NULL",
                    "proposed_action": "DB_SET_NULL",
                    "null": True,
                    "has_default": False,
                }
            ],
        )
        self.assertEqual(
            design["rollback"]["strategy"],
            "reverse_alter_fields_and_restore_captured_foreign_keys",
        )

    def test_companion_design_blocks_unsupported_or_non_nullable_siblings(self):
        relation = {
            "field_label": "sample.Event.session",
            "on_delete": "CASCADE",
            "python_on_delete_siblings": [
                "sample.Event.owner:SET_NULL",
                "sample.Event.guard:PROTECT",
            ],
        }
        siblings = {
            "sample.Event.owner": {
                "field_label": "sample.Event.owner",
                "on_delete": "SET_NULL",
                "null": False,
                "has_default": False,
            },
            "sample.Event.guard": {
                "field_label": "sample.Event.guard",
                "on_delete": "PROTECT",
                "null": False,
                "has_default": False,
            },
        }

        design = db_actions.build_companion_action_design(relation, siblings)

        self.assertEqual(design["status"], "blocked")
        self.assertFalse(design["e050_safe"])
        self.assertIn("companion_SET_NULL_requires_nullable_field", design["blockers"])
        self.assertIn("companion_PROTECT_has_no_database_action", design["blockers"])

    def test_static_inventory_exposes_companion_design_for_retention_candidate(self):
        design = self.retention["companion_action_design"]

        self.assertEqual(design["target_action"], "DB_CASCADE")
        self.assertTrue(design["required"])
        self.assertTrue(design["e050_safe"])
        self.assertEqual(
            design["companions"][0]["proposed_action"], "DB_SET_NULL"
        )

    def test_disposable_endpoint_accepts_only_local_socket(self):
        db_actions.validate_disposable_endpoint(
            host=None, unix_socket="/private/tmp/twc-dj61-disposable/db.sock"
        )
        db_actions.validate_disposable_endpoint(host="127.0.0.1", unix_socket=None)

        for host in ("195.191.25.63", "db.twocomms.shop", "10.0.0.5"):
            with self.subTest(host=host):
                with self.assertRaisesRegex(ValueError, "local MariaDB"):
                    db_actions.validate_disposable_endpoint(host=host, unix_socket=None)
        with self.assertRaisesRegex(ValueError, "socket or loopback"):
            db_actions.validate_disposable_endpoint(host=None, unix_socket=None)
        with self.assertRaisesRegex(ValueError, "temporary socket"):
            db_actions.validate_disposable_endpoint(
                host=None, unix_socket="/var/lib/mysql/mysql.sock"
            )

    def test_destructive_experiment_requires_explicit_disposable_interlock(self):
        calls = []

        def factory(_database):
            calls.append(_database)
            raise AssertionError("connection factory must not be reached")

        with self.assertRaisesRegex(RuntimeError, "interlock missing"):
            db_actions.run_disposable_experiment(
                factory,
                endpoint_host="127.0.0.1",
                connection_identity={
                    "environment": "disposable",
                    "database_role": "temporary",
                    "server_vendor": "mariadb",
                    "server_hostname": "localhost",
                    "server_port": 3306,
                    "db_user": "twc_dj61_disposable_test",
                },
            )
        self.assertEqual(calls, [])

    def test_destructive_experiment_rejects_remote_endpoint_before_factory(self):
        calls = []

        def factory(_database):
            calls.append(_database)
            raise AssertionError("connection factory must not be reached")

        identity = {
            "environment": "disposable",
            "database_role": "temporary",
            "server_vendor": "mariadb",
            "server_hostname": "prod-db",
            "server_port": 3306,
            "db_user": "twc_dj61_disposable_test",
        }
        with self.assertRaisesRegex(ValueError, "local MariaDB"):
            db_actions.run_disposable_experiment(
                factory,
                disposable_interlock=db_actions.DISPOSABLE_EXPERIMENT_INTERLOCK,
                endpoint_host="195.191.25.63",
                connection_identity=identity,
            )
        self.assertEqual(calls, [])

    def test_disposable_contract_accepts_only_complete_proof(self):
        identity = {
            "environment": "disposable",
            "database_role": "temporary",
            "server_vendor": "mariadb",
            "server_hostname": "localhost",
            "server_port": 3306,
            "db_user": "twc_dj61_disposable_test",
        }
        self.assertEqual(
            db_actions.validate_disposable_experiment_contract(
                interlock=db_actions.DISPOSABLE_EXPERIMENT_INTERLOCK,
                endpoint_host="127.0.0.1",
                endpoint_socket=None,
                connection_identity=identity,
            ),
            identity,
        )
        for key, value in (
            ("environment", "production"),
            ("database_role", "persistent"),
            ("server_vendor", "sqlite"),
            ("server_hostname", ""),
        ):
            invalid = dict(identity)
            invalid[key] = value
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                db_actions.validate_disposable_experiment_contract(
                    interlock=db_actions.DISPOSABLE_EXPERIMENT_INTERLOCK,
                    endpoint_host="127.0.0.1",
                    endpoint_socket=None,
                    connection_identity=invalid,
                )

    def test_disposable_connection_identity_is_verified_before_destructive_sql(self):
        class Cursor:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return None

            def execute(self, _sql, _params=()):
                return None

            def fetchone(self):
                return (
                    "11.4.12-MariaDB",
                    "localhost",
                    3306,
                    "twc_dj61_disposable_test@localhost",
                    None,
                )

        class Connection:
            def cursor(self):
                return Cursor()

        expected = {
            "server_hostname": "localhost",
            "server_port": 3306,
            "db_user": "twc_dj61_disposable_test",
        }
        db_actions.verify_disposable_connection_identity(Connection(), expected)
        with self.assertRaisesRegex(RuntimeError, "hostname mismatch"):
            db_actions.verify_disposable_connection_identity(
                Connection(), {**expected, "server_hostname": "other-host"}
            )

    def test_destructive_experiment_has_no_public_cli(self):
        with self.assertRaises(SystemExit) as raised:
            db_actions._build_parser().parse_args(
                ["experiment", "--host", "127.0.0.1", "--user", "local"]
            )
        self.assertEqual(raised.exception.code, 2)

    def test_live_inventory_accepts_only_normalized_default_alias(self):
        self.assertEqual(db_actions.validate_live_database_alias(" default "), "default")
        self.assertEqual(db_actions.validate_live_database_alias("DEFAULT"), "default")
        for alias in ("dtf", " DTF ", "replica", "default-readonly", ""):
            with self.subTest(alias=alias):
                with self.assertRaisesRegex(ValueError, "default"):
                    db_actions.validate_live_database_alias(alias)

    def test_report_is_russian_machine_readable_and_explicit_no_go(self):
        enriched = db_actions.enrich_inventory([self.retention], FakeInspector())[0]
        decision = db_actions.assess_db_cascade(enriched)
        output = io.StringIO()

        db_actions.render_json_report(
            inventory=[enriched],
            retention_decision=decision,
            experiment={"status": "passed", "db_cascade_seconds": 0.01},
            output=output,
        )

        report = json.loads(output.getvalue())
        self.assertEqual(report["scope"], "non-DTF")
        self.assertEqual(report["retention_graph"]["decision"], "NO-GO")
        self.assertIn("Не внедрять", report["retention_graph"]["decision_ru"])
        self.assertNotIn("password", output.getvalue().lower())


if __name__ == "__main__":
    unittest.main()
