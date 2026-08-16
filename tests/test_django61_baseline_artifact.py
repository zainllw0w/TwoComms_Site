"""Contracts for the sanitized Django 5.2/6.1 baseline comparison."""

from __future__ import annotations

import unittest


class Django61BaselineArtifactTests(unittest.TestCase):
    @staticmethod
    def _artifact_metadata():
        return {
            "command": "python scripts/run_non_dtf_test_suite.py",
            "scope": "non-DTF full suite",
            "source_base_sha": "a" * 40,
            "evidence_scope": "local pre-integration compatibility evidence",
            "source_tree_state": "uncommitted-stage0-changes",
            "stable_shards": (
                "storefront.tests.test_product_video",
                "management.tests_ig_profile",
            ),
        }

    def test_full_suite_uses_explicit_non_dtf_labels(self):
        from scripts.run_non_dtf_test_suite import NON_DTF_TEST_LABELS, build_command

        self.assertIn("management.tests_ig_profile", NON_DTF_TEST_LABELS)
        self.assertIn("storefront.tests.test_product_video", NON_DTF_TEST_LABELS)
        self.assertNotIn("management", NON_DTF_TEST_LABELS)
        self.assertNotIn(
            "management.tests_ig_mariadb_lifecycle", NON_DTF_TEST_LABELS
        )
        self.assertNotIn(
            "management.tests_ig_mariadb_follow_ugc", NON_DTF_TEST_LABELS
        )
        self.assertFalse(any("dtf" in label.casefold() for label in NON_DTF_TEST_LABELS))
        self.assertFalse(any("test_settings" in label for label in NON_DTF_TEST_LABELS))
        command = build_command(python="/project/python", settings="safe_settings")
        self.assertEqual(command[0], "/project/python")
        self.assertIn("--settings=safe_settings", command)
        self.assertEqual(command[3 : 3 + len(NON_DTF_TEST_LABELS)], list(NON_DTF_TEST_LABELS))

    def test_matching_results_keep_exact_failure_and_error_ids(self):
        from scripts.build_django61_baseline_artifact import build_comparison

        log = "\n".join(
            (
                "ERROR: test_database (management.tests_db.DatabaseTests.test_database)",
                "FAIL: test_template (storefront.tests_ui.TemplateTests.test_template)",
                "Ran 2 tests in 0.100s",
                "FAILED (failures=1, errors=1)",
            )
        )
        try:
            comparison = build_comparison(
                baseline_text=log,
                candidate_text=log,
                baseline_runtime="Django 5.2.11",
                candidate_runtime="Django 6.1",
                **self._artifact_metadata(),
            )
        except TypeError as exc:
            self.fail(f"Comparison metadata is part of the artifact contract: {exc}")

        self.assertEqual(comparison["status"], "matched")
        self.assertEqual(comparison["delta"], {"candidate_only": [], "baseline_only": []})
        self.assertEqual(comparison["baseline"]["error_ids"], [
            "test_database (management.tests_db.DatabaseTests.test_database)"
        ])
        self.assertEqual(comparison["candidate"]["failure_ids"], [
            "test_template (storefront.tests_ui.TemplateTests.test_template)"
        ])

    def test_comparison_rejects_dtf_test_identifier(self):
        from scripts.build_django61_baseline_artifact import build_comparison

        log = "\n".join(
            (
                "ERROR: test_route (dtf.tests.RouteTests.test_route)",
                "Ran 1 test in 0.100s",
                "FAILED (failures=0, errors=1)",
            )
        )

        with self.assertRaisesRegex(ValueError, "DTF"):
            build_comparison(
                baseline_text=log,
                candidate_text=log,
                baseline_runtime="Django 5.2.11",
                candidate_runtime="Django 6.1",
                **self._artifact_metadata(),
            )

    def test_comparison_rejects_dtf_identifier_from_passing_verbose_test(self):
        from scripts.build_django61_baseline_artifact import build_comparison

        log = "\n".join(
            (
                "test_route (dtf.tests.RouteTests.test_route) ... ok",
                "Ran 1 test in 0.100s",
                "OK",
            )
        )

        with self.assertRaisesRegex(ValueError, "DTF"):
            build_comparison(
                baseline_text=log,
                candidate_text=log,
                baseline_runtime="Django 5.2.11",
                candidate_runtime="Django 6.1",
                **self._artifact_metadata(),
            )

    def test_parser_distinguishes_dtf_migration_setup_from_dtf_test_identifiers(self):
        from scripts.build_django61_baseline_artifact import parse_test_log

        historical_mariadb_log = "\n".join(
            (
                "Applying dtf.0004_dtfsamplelead_alter_dtforder_length_source_and_more... OK",
                "test_database (management.tests_db.DatabaseTests.test_database) ... ok",
                "Ran 1 test in 0.100s",
                "OK",
            )
        )

        parsed = parse_test_log(historical_mariadb_log)

        self.assertEqual(parsed["summary"]["tests"], 1)
        self.assertEqual(parsed["failure_ids"], [])
        self.assertEqual(parsed["error_ids"], [])

    def test_parser_ignores_indented_ok_lines_from_migration_output(self):
        from scripts.build_django61_baseline_artifact import parse_test_log

        log = "\n".join(
            (
                "Applying storefront.0001_initial...",
                " OK",
                "Applying management.0001_initial...",
                " OK",
                "test_database (management.tests_db.DatabaseTests.test_database) ... ok",
                "Ran 1 test in 0.100s",
                "OK",
                "Preserving test database...",
                " OK",
            )
        )

        self.assertEqual(parse_test_log(log)["summary"]["tests"], 1)

    def test_parser_requires_exactly_one_complete_unittest_footer(self):
        from scripts.build_django61_baseline_artifact import parse_test_log

        valid_log = "\n".join(("Ran 1 test in 0.100s", "OK"))
        cases = {
            "missing": "test_example ... ok",
            "duplicated": f"{valid_log}\n{valid_log}",
        }

        for name, log in cases.items():
            with self.subTest(name=name):
                with self.assertRaisesRegex(ValueError, "exactly one"):
                    parse_test_log(log)

    def test_parser_rejects_unrecognized_summary_content(self):
        from scripts.build_django61_baseline_artifact import parse_test_log

        log = "\n".join(
            (
                "Ran 1 test in 0.100s",
                "OK (skippped=1)",
            )
        )

        with self.assertRaisesRegex(ValueError, "Unrecognized unittest summary"):
            parse_test_log(log)

    def test_parser_rejects_summary_count_that_disagrees_with_outcome_ids(self):
        from scripts.build_django61_baseline_artifact import parse_test_log

        log = "\n".join(
            (
                "ERROR: test_database (management.tests_db.DatabaseTests.test_database)",
                "Ran 2 tests in 0.100s",
                "FAILED (errors=2)",
            )
        )

        with self.assertRaisesRegex(ValueError, "summary errors=2.*ERROR ids=1"):
            parse_test_log(log)

    def test_parser_preserves_repeated_outcome_records_in_sorted_order(self):
        from scripts.build_django61_baseline_artifact import parse_test_log

        repeated = "test_zeta (management.tests_db.DatabaseTests.test_zeta)"
        first = "test_alpha (management.tests_db.DatabaseTests.test_alpha)"
        log = "\n".join(
            (
                f"ERROR: {repeated}",
                f"ERROR: {first}",
                f"ERROR: {repeated}",
                "Ran 3 tests in 0.100s",
                "FAILED (errors=3)",
            )
        )

        try:
            parsed = parse_test_log(log)
        except ValueError as exc:
            self.fail(f"Repeated unittest outcome records must remain valid: {exc}")

        self.assertEqual(parsed["error_ids"], [first, repeated, repeated])
        self.assertEqual(parsed["summary"]["errors"], 3)

    def test_summary_count_delta_cannot_be_reported_as_matched(self):
        from scripts.build_django61_baseline_artifact import build_comparison

        baseline_log = "\n".join(
            (
                "Ran 2 tests in 0.100s",
                "OK (skipped=1)",
            )
        )
        candidate_log = "\n".join(
            (
                "Ran 2 tests in 0.100s",
                "OK",
            )
        )

        comparison = build_comparison(
            baseline_text=baseline_log,
            candidate_text=candidate_log,
            baseline_runtime="Django 5.2.11",
            candidate_runtime="Django 6.1",
            **self._artifact_metadata(),
        )

        self.assertEqual(comparison["status"], "different")
        self.assertFalse(comparison["summary_matches"])

    def test_repeated_outcome_id_delta_uses_multiset_semantics(self):
        from scripts.build_django61_baseline_artifact import build_comparison

        first = "test_alpha (management.tests_db.DatabaseTests.test_alpha)"
        second = "test_beta (management.tests_db.DatabaseTests.test_beta)"

        def log_for(*identifiers):
            lines = [f"ERROR: {identifier}" for identifier in identifiers]
            lines.extend(("Ran 3 tests in 0.100s", "FAILED (errors=3)"))
            return "\n".join(lines)

        try:
            comparison = build_comparison(
                baseline_text=log_for(first, first, second),
                candidate_text=log_for(first, second, second),
                baseline_runtime="Django 5.2.11",
                candidate_runtime="Django 6.1",
                **self._artifact_metadata(),
            )
        except ValueError as exc:
            self.fail(f"Repeated unittest outcome records must remain valid: {exc}")

        self.assertEqual(comparison["status"], "different")
        self.assertEqual(comparison["delta"]["baseline_only"], [f"ERROR: {first}"])
        self.assertEqual(comparison["delta"]["candidate_only"], [f"ERROR: {second}"])

    def test_artifact_records_scope_provenance_and_deterministic_triage_clusters(self):
        from scripts.build_django61_baseline_artifact import build_comparison

        log = "\n".join(
            (
                "ERROR: test_database (management.tests_db.DatabaseTests.test_database)",
                "FAIL: test_template (storefront.tests_ui.TemplateTests.test_template)",
                "Ran 2 tests in 0.100s",
                "FAILED (failures=1, errors=1)",
            )
        )
        comparison = build_comparison(
            baseline_text=log,
            candidate_text=log,
            baseline_runtime="Django 5.2.11",
            candidate_runtime="Django 6.1",
            **self._artifact_metadata(),
        )

        self.assertEqual(comparison["schema_version"], 2)
        self.assertEqual(
            comparison["metadata"],
            {
                "command": "python scripts/run_non_dtf_test_suite.py",
                "dtf_scope": "excluded",
                "dtf_migration_setup": "not-loaded",
                "provenance": {
                    "base_sha": "a" * 40,
                    "clean_tree_assertion": "not-made",
                    "evidence_scope": "local pre-integration compatibility evidence",
                    "source_tree_state": "uncommitted-stage0-changes",
                },
                "scope": "non-DTF full suite",
                "stable_shards": [
                    "management.tests_ig_profile",
                    "storefront.tests.test_product_video",
                ],
            },
        )
        self.assertEqual(
            comparison["root_cause_clusters"],
            [
                {
                    "baseline_outcomes": [
                        "ERROR: test_database (management.tests_db.DatabaseTests.test_database)"
                    ],
                    "basis": "test_module_prefix",
                    "candidate_outcomes": [
                        "ERROR: test_database (management.tests_db.DatabaseTests.test_database)"
                    ],
                    "cluster_id": "module:management.tests_db",
                    "diagnosis": None,
                },
                {
                    "baseline_outcomes": [
                        "FAIL: test_template (storefront.tests_ui.TemplateTests.test_template)"
                    ],
                    "basis": "test_module_prefix",
                    "candidate_outcomes": [
                        "FAIL: test_template (storefront.tests_ui.TemplateTests.test_template)"
                    ],
                    "cluster_id": "module:storefront.tests_ui",
                    "diagnosis": None,
                },
            ],
        )

    def test_tracked_artifact_validation_requires_hashes_and_consistent_provenance(self):
        from scripts.build_django61_baseline_artifact import (
            build_comparison,
            validate_comparison_artifact,
        )

        log = "\n".join(
            (
                "test_database (management.tests_db.DatabaseTests.test_database) ... ok",
                "Ran 1 test in 0.100s",
                "OK",
            )
        )
        artifact = build_comparison(
            baseline_text=log,
            candidate_text=log,
            baseline_runtime="Django 5.2.11",
            candidate_runtime="Django 6.1",
            **self._artifact_metadata(),
        )

        with self.assertRaisesRegex(ValueError, "log_sha256"):
            validate_comparison_artifact(artifact)

        artifact["baseline"]["log_sha256"] = "b" * 64
        artifact["candidate"]["log_sha256"] = "c" * 64
        self.assertIsNone(validate_comparison_artifact(artifact))

    def test_fresh_candidate_log_must_match_the_tracked_django61_side(self):
        from scripts.build_django61_baseline_artifact import (
            build_comparison,
            compare_candidate_log,
        )

        tracked_log = "\n".join(
            (
                "FAIL: test_template (storefront.tests_ui.TemplateTests.test_template)",
                "Ran 1 test in 0.100s",
                "FAILED (failures=1)",
            )
        )
        artifact = build_comparison(
            baseline_text=tracked_log,
            candidate_text=tracked_log,
            baseline_runtime="Django 5.2.11",
            candidate_runtime="Django 6.1",
            **self._artifact_metadata(),
        )
        artifact["baseline"]["log_sha256"] = "b" * 64
        artifact["candidate"]["log_sha256"] = "c" * 64

        matched = compare_candidate_log(artifact=artifact, candidate_text=tracked_log)
        self.assertEqual(matched["status"], "matched")

        changed = compare_candidate_log(
            artifact=artifact,
            candidate_text="\n".join(
                (
                    "ERROR: test_template (storefront.tests_ui.TemplateTests.test_template)",
                    "Ran 1 test in 0.100s",
                    "FAILED (errors=1)",
                )
            ),
        )
        self.assertEqual(changed["status"], "different")
        self.assertTrue(changed["delta"]["fresh_only"])


if __name__ == "__main__":
    unittest.main()
