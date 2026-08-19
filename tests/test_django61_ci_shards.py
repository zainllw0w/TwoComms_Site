from __future__ import annotations

import io
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import run_django61_ci_shards as shards


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "django61-gate.yml"


class Django61CIShardContractTests(unittest.TestCase):
    def test_reviewed_shards_are_disjoint_non_dtf_and_complete(self):
        expected = {
            "tests.test_django61_stage0_tooling",
            "tests.test_django61_warning_prerequisites",
            "tests.test_django61_compatibility",
            "tests.test_ig_baseline_runner",
            "tests.test_requirements_contract",
            "tests.test_verify_locked_requirements",
        }
        modules = [
            module
            for _, shard_modules in shards.STABLE_SHARDS
            for module in shard_modules
        ]

        self.assertEqual(set(modules), expected)
        self.assertEqual(len(modules), len(set(modules)))
        self.assertFalse(any("dtf" in module.casefold() for module in modules))

    def test_child_environment_is_no_network_and_drops_production_credentials(self):
        environment = shards.build_environment(
            {
                "PATH": "/usr/bin",
                "PYTHONPATH": "/existing",
                "DB_NAME": "production",
                "DB_NAME_DTF": "production-dtf",
                "REDIS_URL": "redis://production",
                "TELEGRAM_BOT_TOKEN": "secret",
            }
        )

        self.assertEqual(
            environment["DJANGO_SETTINGS_MODULE"],
            "test_settings_no_network_non_dtf",
        )
        self.assertEqual(environment["TEST_NETWORK_POLICY"], "deny-external")
        self.assertTrue(environment["PYTHONPATH"].startswith(str(shards.APP_ROOT)))
        self.assertNotIn("DB_NAME", environment)
        self.assertNotIn("DB_NAME_DTF", environment)
        self.assertNotIn("REDIS_URL", environment)
        self.assertNotIn("TELEGRAM_BOT_TOKEN", environment)

    def test_command_is_exact_unittest_and_rejects_dtf(self):
        self.assertEqual(
            shards.build_command(
                ("tests.test_example",),
                python="/project/python",
                verbosity=1,
            ),
            ["/project/python", "-m", "unittest", "tests.test_example", "-v"],
        )
        with self.assertRaisesRegex(ValueError, "DTF"):
            shards.build_command(("dtf.tests",), python="/project/python")

    def test_runner_waits_for_every_shard_and_propagates_failure(self):
        calls = []

        def fake_runner(command, **kwargs):
            calls.append((tuple(command), kwargs))
            return subprocess.CompletedProcess(
                command,
                1 if "tests.test_django61_compatibility" in command else 0,
                stdout="shard stdout\n",
                stderr="shard stderr\n",
            )

        output = io.StringIO()
        result = shards.run_shards(
            jobs=2,
            python="/project/python",
            command_runner=fake_runner,
            output=output,
        )

        self.assertEqual(result, 1)
        self.assertEqual(len(calls), len(shards.STABLE_SHARDS))
        self.assertIn("status=failed", output.getvalue())
        self.assertIn("failed=django-compatibility", output.getvalue())
        for _, kwargs in calls:
            self.assertEqual(kwargs["cwd"], shards.ROOT)
            self.assertEqual(kwargs["env"]["TEST_NETWORK_POLICY"], "deny-external")
            self.assertFalse(kwargs["check"])

    def test_workflow_uses_bounded_process_shards_and_serial_django_runner(self):
        source = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("python scripts/run_django61_ci_shards.py --jobs 2", source)
        self.assertIn(
            "python -m unittest tests.test_django61_stage0_contracts -v",
            source,
        )
        product_video_line = next(
            line
            for line in source.splitlines()
            if "storefront.tests.test_product_video" in line
        )
        self.assertIn("--parallel 1", product_video_line)
        self.assertNotIn("--parallel 2", product_video_line)

    def test_runtime_contract_is_exact(self):
        with patch("platform.python_version", return_value="3.14.6"), patch(
            "django.get_version", return_value="6.1"
        ):
            shards.validate_runtime()
        with patch("platform.python_version", return_value="3.14.7"):
            with self.assertRaisesRegex(RuntimeError, "runtime_mismatch"):
                shards.validate_runtime()


if __name__ == "__main__":
    unittest.main()
