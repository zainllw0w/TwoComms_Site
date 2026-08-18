from __future__ import annotations

import os
import stat
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from django.db import models
from scripts import run_generated_price_experiment as experiment


class GeneratedPriceFormulaTests(unittest.TestCase):
    def test_contract_matrix_matches_decimal_and_current_integer_formula(self):
        for price in experiment.CONTRACT_PRICES:
            for discount in experiment.CONTRACT_DISCOUNTS:
                with self.subTest(price=price, discount=discount):
                    expected = (
                        int(Decimal(price) * Decimal(100 - discount) / Decimal(100))
                        if discount
                        else price
                    )
                    self.assertEqual(
                        experiment.current_product_final_price(price, discount),
                        expected,
                    )

    def test_generated_expression_is_typed_and_uses_mariadb_integer_division(self):
        expression = experiment.generated_price_expression()

        self.assertIsInstance(expression.output_field, models.PositiveIntegerField)
        self.assertIsInstance(expression, experiment.MariaDBIntegerDivision)


class GeneratedPriceHarnessSafetyTests(unittest.TestCase):
    def test_native_binary_resolution_is_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(experiment.ExperimentError):
                experiment.resolve_native_binaries(Path(temp_dir))

    def test_native_binary_resolution_accepts_only_both_executables(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            binary_dir = Path(temp_dir)
            for name in ("mariadbd", "mariadb-install-db"):
                path = binary_dir / name
                path.write_text("#!/bin/sh\nexit 0\n", encoding="ascii")
                path.chmod(path.stat().st_mode | stat.S_IXUSR)

            self.assertEqual(
                experiment.resolve_native_binaries(binary_dir),
                {
                    "mariadbd": str(binary_dir / "mariadbd"),
                    "mariadb-install-db": str(binary_dir / "mariadb-install-db"),
                },
            )

    def test_runtime_environment_never_forwards_database_or_provider_secrets(self):
        source = {
            "PATH": os.environ.get("PATH", ""),
            "LANG": "uk_UA.UTF-8",
            "DB_NAME": "production",
            "DB_PASSWORD": "secret",
            "DB_NAME_DTF": "dtf",
            "TELEGRAM_BOT_TOKEN": "token",
            "META_ACCESS_TOKEN": "token",
            "UNRELATED_SECRET": "secret",
        }

        sanitized = experiment.sanitized_native_environment(source)

        self.assertEqual(sanitized["LANG"], "uk_UA.UTF-8")
        self.assertEqual(sanitized["PYTHONNOUSERSITE"], "1")
        for forbidden in (
            "DB_NAME",
            "DB_PASSWORD",
            "DB_NAME_DTF",
            "TELEGRAM_BOT_TOKEN",
            "META_ACCESS_TOKEN",
            "UNRELATED_SECRET",
        ):
            self.assertNotIn(forbidden, sanitized)


class GeneratedPriceIndexPlanTests(unittest.TestCase):
    def test_index_plan_requires_generated_price_index_and_range_access(self):
        evidence = experiment.validate_index_plan(
            {
                "key": experiment.INDEX_NAME,
                "type": "range",
                "possible_keys": experiment.INDEX_NAME,
                "rows": 12,
                "Extra": "Using index condition",
            }
        )

        self.assertEqual(evidence["key"], experiment.INDEX_NAME)
        self.assertEqual(evidence["access_type"], "range")

    def test_index_plan_rejects_full_scan(self):
        with self.assertRaises(experiment.ExperimentError):
            experiment.validate_index_plan(
                {
                    "key": None,
                    "type": "ALL",
                    "possible_keys": experiment.INDEX_NAME,
                    "rows": 4096,
                    "Extra": "Using filesort",
                }
            )


if __name__ == "__main__":
    unittest.main()
