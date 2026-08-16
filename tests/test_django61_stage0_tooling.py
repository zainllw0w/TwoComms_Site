"""Focused contracts for Stage 0 warnings, static files, and inventory."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = ROOT / "twocomms"


class WarningGateContractTests(unittest.TestCase):
    def test_only_owned_vendor_warning_is_allowlisted(self):
        from scripts.run_django_warning_gate import classify_warning_lines

        project = (
            "/repo/storefront/models.py:10: RemovedInDjango70Warning: project warning"
        )
        vendor = (
            "/venv/site-packages/social_django/admin.py:8: "
            "RemovedInDjango70Warning: Setting ModelAdmin.list_select_related "
            "to True is deprecated. Use False or a list or tuple of fields to fetch instead."
        )
        result = classify_warning_lines([project, vendor])

        self.assertEqual(result["blocked"], [project])
        self.assertEqual(result["allowed"], [vendor])

    def test_expired_vendor_allowlist_entry_is_blocked(self):
        from scripts.run_django_warning_gate import classify_warning_lines

        vendor = (
            "/venv/site-packages/social_django/admin.py:8: "
            "RemovedInDjango70Warning: Setting ModelAdmin.list_select_related "
            "to True is deprecated. Use False or a list or tuple of fields to fetch instead."
        )
        result = classify_warning_lines([vendor], today=date(2026, 10, 2))

        self.assertEqual(result["allowed"], [])
        self.assertEqual(result["blocked"], [vendor])

    def test_unrecognized_vendor_warning_is_blocked(self):
        from scripts.run_django_warning_gate import classify_warning_lines

        warning = (
            "/venv/site-packages/example/admin.py:8: "
            "RemovedInDjango70Warning: unexpected"
        )
        self.assertEqual(classify_warning_lines([warning])["blocked"], [warning])

    def test_project_owned_generic_deprecation_warnings_are_blocked(self):
        from scripts.run_django_warning_gate import classify_warning_lines

        warnings = [
            "/repo/storefront/models.py:10: DeprecationWarning: old behavior",
            (
                "/repo/management/views.py:20: PendingDeprecationWarning: "
                "future removal"
            ),
        ]

        self.assertEqual(classify_warning_lines(warnings)["allowed"], [])
        self.assertEqual(classify_warning_lines(warnings)["blocked"], warnings)


class StaticProfileContractTests(unittest.TestCase):
    def test_static_gate_requires_rendered_manifest_backed_assets(self):
        from scripts.run_static_gate import _validate_render_probe_payload

        self.assertEqual(
            _validate_render_probe_payload(
                {
                    "rendered_static_urls": 2,
                    "rendered_compressor_urls": 1,
                    "missing_assets": [],
                }
            ),
            {"rendered_static_urls": 2, "rendered_compressor_urls": 1},
        )
        with self.assertRaises(RuntimeError):
            _validate_render_probe_payload(
                {
                    "rendered_static_urls": 2,
                    "rendered_compressor_urls": 0,
                    "missing_assets": [],
                }
            )

    def test_static_profile_uses_temporary_manifest_storage_without_dtf(self):
        with tempfile.TemporaryDirectory() as directory:
            environment = {
                name: value
                for name, value in os.environ.items()
                if not name.startswith("DB_") and name != "DATABASE_URL"
            }
            environment.update(
                {
                    "DJANGO_SETTINGS_MODULE": "test_settings_static_non_dtf",
                    "TWC_TEST_STATIC_ROOT": directory,
                    "SECRET_KEY": "stage0-static-contract",
                    "PYTHONPATH": str(APP_ROOT),
                }
            )
            statement = (
                "import json,django; django.setup(); from django.apps import apps; "
                "from django.conf import settings; print(json.dumps({"
                "'apps':[c.name for c in apps.get_app_configs()],"
                "'root':str(settings.STATIC_ROOT),"
                "'backend':settings.STORAGES['staticfiles']['BACKEND'],"
                "'offline':settings.COMPRESS_OFFLINE"
                "},sort_keys=True))"
            )
            result = subprocess.run(
                [sys.executable, "-c", statement],
                cwd=APP_ROOT,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout.strip().splitlines()[-1])
        self.assertNotIn("dtf", payload["apps"])
        self.assertEqual(payload["root"], str(Path(directory).resolve()))
        self.assertEqual(
            payload["backend"],
            "whitenoise.storage.CompressedManifestStaticFilesStorage",
        )
        self.assertTrue(payload["offline"])


class InventoryContractTests(unittest.TestCase):
    def test_inventory_path_filter_keeps_non_dtf_profiles(self):
        from scripts.build_non_dtf_inventory import _is_non_dtf

        self.assertTrue(_is_non_dtf(APP_ROOT / "test_settings_no_network_non_dtf.py"))
        self.assertFalse(_is_non_dtf(APP_ROOT / "dtf" / "models.py"))
        self.assertFalse(_is_non_dtf(APP_ROOT / "twocomms" / "urls_dtf.py"))

    def test_inventory_is_sanitized_and_dtf_is_excluded(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "inventory.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "build_non_dtf_inventory.py"),
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["dtf_scope"], "excluded")
        self.assertFalse(payload["dtf_app_loaded"])
        for key in (
            "models",
            "url_patterns",
            "templates",
            "python_files",
            "javascript_files",
            "management_commands",
        ):
            self.assertGreater(payload["counts"][key], 0)
        self.assertNotIn("paths", payload)


if __name__ == "__main__":
    unittest.main()
