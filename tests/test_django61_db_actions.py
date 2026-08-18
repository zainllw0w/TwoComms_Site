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

    def test_disposable_endpoint_accepts_only_local_socket(self):
        db_actions.validate_disposable_endpoint(host=None, unix_socket="/private/tmp/db.sock")
        db_actions.validate_disposable_endpoint(host="127.0.0.1", unix_socket=None)

        for host in ("195.191.25.63", "db.twocomms.shop", "10.0.0.5"):
            with self.subTest(host=host):
                with self.assertRaisesRegex(ValueError, "local MariaDB"):
                    db_actions.validate_disposable_endpoint(host=host, unix_socket=None)
        with self.assertRaisesRegex(ValueError, "socket or loopback"):
            db_actions.validate_disposable_endpoint(host=None, unix_socket=None)

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
