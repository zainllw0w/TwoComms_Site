import importlib.util
from pathlib import Path

from django.test import SimpleTestCase


SCRIPT = (
    Path(__file__).resolve().parents[3]
    / "scripts"
    / "run_checkout_series_s2a_mariadb_retry.py"
)
SPEC = importlib.util.spec_from_file_location("checkout_s2a_retry_script", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class CheckoutSeriesRetryScriptTests(SimpleTestCase):
    def test_script_requires_explicit_disposable_confirmation(self):
        self.assertFalse(MODULE._arguments([]).confirm_disposable)
        self.assertTrue(
            MODULE._arguments(["--confirm-disposable"]).confirm_disposable
        )

    def test_database_name_guard_accepts_only_checkout_s2a_test_namespace(self):
        self.assertEqual(
            MODULE._validate_disposable_name("test_twocomms_checkout_s2a_abc123"),
            "test_twocomms_checkout_s2a_abc123",
        )
        for value in (
            "twocomms",
            "test_twocomms_prod",
            "test_twocomms_s2a_abc123",
            "test_twocomms_checkout_s2a_bad-name",
            "",
        ):
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                MODULE._validate_disposable_name(value)

    def test_harness_is_provider_free_and_checks_every_safety_boundary(self):
        source = SCRIPT.read_text(encoding="utf-8")
        for contract in (
            "--confirm-disposable",
            "TEST_REVIEW_WRITE_FREEZE_MARKER",
            "0057_paymentattempt_provider_recheck",
            "0058_paymentattempt_checkout_series",
            "KILL_EXIT_CODE = 97",
            "validate_complete_schema",
            "physical_defaults",
            "invalid_shapes_rejected",
            "malformed_default_rejected",
            "malformed_check_rejected",
            "reverse_columns_preserved",
            "INNODB",
        ):
            self.assertIn(contract, source)
        self.assertNotIn("requests.", source)
        self.assertNotIn("monobank", source.casefold())
