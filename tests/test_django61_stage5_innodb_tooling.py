import importlib.util
import json
from pathlib import Path
import unittest


SCRIPT = Path(__file__).parents[1] / "scripts" / "build_innodb_stage5_inventory.py"
SPEC = importlib.util.spec_from_file_location("stage5_inventory", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class Stage5InventoryTests(unittest.TestCase):
    def test_selects_only_domain_reviewed_non_dtf_myisam_table_with_no_writers(self):
        report = MODULE.build_report(
            {
                "database": "default",
                "tables": [
                    {
                        "name": "app_disposable_legacy",
                        "model": "app.DisposableLegacy",
                        "engine": "MyISAM",
                        "rows": 7,
                        "data_length": 512,
                        "criticality": "low",
                        "writers": 0,
                        "orphan_scan_complete": True,
                        "writer_audit_complete": True,
                        "domain_review_complete": True,
                    },
                    {
                        "name": "storefront_product",
                        "model": "storefront.Product",
                        "engine": "MyISAM",
                        "rows": 10,
                        "criticality": "high",
                        "writers": 1,
                    },
                ],
                "foreign_keys": [],
                "rollback": {"method": "maintenance_window", "backup_verified": True, "write_freeze": True},
            }
        )
        self.assertEqual(report["selected_canary"]["name"], "app_disposable_legacy")
        migration_order = {
            row["name"]: row["migration_order"] for row in report["tables"]
        }
        self.assertEqual(migration_order["app_disposable_legacy"], 1)

    def test_active_or_managed_engine_table_cannot_be_selected_as_canary(self):
        base = {
            "database": "default",
            "foreign_keys": [],
            "rollback": {
                "method": "maintenance_window",
                "backup_verified": True,
                "write_freeze": True,
            },
        }
        for override in (
            {"domain_review_complete": False},
            {"managed_engine_contract": True},
            {"writers": 1},
        ):
            with self.subTest(override=override):
                report = MODULE.build_report(
                    {
                        **base,
                        "tables": [
                            {
                                "name": "storefront_promocodegroup",
                                "model": "storefront.PromoCodeGroup",
                                "engine": "MyISAM",
                                "rows": 7,
                                "data_length": 512,
                                "criticality": "low",
                                "writers": 0,
                                "orphan_scan_complete": True,
                                "writer_audit_complete": True,
                                "domain_review_complete": True,
                                "managed_engine_contract": False,
                                **override,
                            }
                        ],
                    }
                )
                self.assertIsNone(report["selected_canary"])
                self.assertEqual(report["canary_status"], "blocked_no_proven_candidate")

    def test_dependency_order_comes_from_foreign_keys_not_declared_order(self):
        report = MODULE.build_report(
            {
                "database": "default",
                "tables": [
                    {"name": "child", "engine": "MyISAM", "rows": 2, "criticality": "low", "writers": 0},
                    {"name": "parent", "engine": "MyISAM", "rows": 3, "criticality": "low", "writers": 0},
                ],
                "foreign_keys": [{"parent": "parent", "child": "child"}],
                "rollback": {"method": "dual_write", "backup_verified": True, "reverse_sync": True},
            }
        )
        self.assertEqual(report["dependency_order"], ["parent", "child"])

    def test_backup_alone_is_not_a_safe_rollback(self):
        with self.assertRaises(ValueError):
            MODULE.build_report(
                {
                    "database": "default",
                    "tables": [{"name": "safe", "model": "app.Safe", "engine": "InnoDB"}],
                    "foreign_keys": [],
                    "rollback": {"method": "backup_restore", "backup_verified": True},
                }
            )

    def test_json_output_is_sanitized(self):
        report = MODULE.build_report(
            {
                "database": "default",
                "tables": [{"name": "small", "model": "app.Small", "engine": "InnoDB", "rows": 1, "criticality": "low", "writers": 0}],
                "foreign_keys": [],
                "rollback": {"method": "replica_switchover", "backup_verified": True, "reverse_sync": True},
            }
        )
        encoded = json.dumps(report)
        self.assertNotIn("password", encoded.lower())
        self.assertNotIn("secret", encoded.lower())

    def test_dtf_scope_and_negative_metrics_fail_closed(self):
        base = {
            "database": "default",
            "tables": [{"name": "safe", "model": "app.Safe", "engine": "MyISAM"}],
            "foreign_keys": [],
            "rollback": {"method": "maintenance_window", "backup_verified": True, "write_freeze": True},
        }
        for unsafe in (
            {**base, "database": "dtf"},
            {**base, "tables": [{"name": "dtf_order", "model": "dtf.Order", "engine": "MyISAM"}]},
            {**base, "tables": [{"name": "safe", "model": "app.Safe", "engine": "MyISAM", "rows": -1}]},
        ):
            with self.subTest(unsafe=unsafe):
                with self.assertRaises(ValueError):
                    MODULE.build_report(unsafe)

    def test_unmeasured_writer_and_orphan_risk_cannot_select_a_canary(self):
        report = MODULE.build_report(
            {
                "database": "default",
                "tables": [
                    {
                        "name": "small_legacy_table",
                        "model": "app.SmallLegacy",
                        "engine": "MyISAM",
                        "rows": 1,
                        "criticality": "low",
                        "writers": 0,
                        "orphan_scan_complete": False,
                    }
                ],
                "foreign_keys": [],
                "rollback": {
                    "method": "maintenance_window",
                    "backup_verified": True,
                    "write_freeze": True,
                },
            }
        )

        self.assertIsNone(report["selected_canary"])
        self.assertEqual(report["canary_status"], "blocked_no_proven_candidate")
        self.assertEqual(
            report["tables"][0]["risk"], "unmeasured_writer_and_orphan_risk"
        )

    def test_unmeasured_writer_risk_cannot_select_a_canary(self):
        report = MODULE.build_report(
            {
                "database": "default",
                "tables": [
                    {
                        "name": "small_legacy_table",
                        "model": "app.SmallLegacy",
                        "engine": "MyISAM",
                        "rows": 1,
                        "criticality": "low",
                        "writers": 0,
                        "orphan_scan_complete": True,
                        "writer_audit_complete": False,
                    }
                ],
                "foreign_keys": [],
                "rollback": {
                    "method": "maintenance_window",
                    "backup_verified": True,
                    "write_freeze": True,
                },
            }
        )

        self.assertIsNone(report["selected_canary"])
        self.assertEqual(report["canary_status"], "blocked_no_proven_candidate")
        self.assertEqual(report["tables"][0]["risk"], "unmeasured_writer_risk")


if __name__ == "__main__":
    unittest.main()
