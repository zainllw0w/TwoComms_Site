"""Regression contracts for Django 6.1 and upcoming Django/Python removals."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = ROOT / "twocomms"


class MailersContractTests(unittest.TestCase):
    def test_test_profile_uses_mailers_without_deprecated_email_settings(self):
        environment = os.environ.copy()
        environment.update(
            {
                "DJANGO_SETTINGS_MODULE": "test_settings_no_network_non_dtf",
                "SECRET_KEY": "mailers-contract",
                "PYTHONPATH": str(APP_ROOT),
            }
        )
        statement = (
            "import json,django; django.setup(); from django.conf import settings; "
            "from django.core.mail import mailers; connection=mailers['default']; "
            "print(json.dumps({"
            "'aliases':sorted(settings.MAILERS),"
            "'backend':connection.__class__.__module__+'.'+connection.__class__.__name__,"
            "'reply_to':settings.EMAIL_REPLY_TO_ADDRESS,"
            "'configured':settings.EMAIL_DELIVERY_CONFIGURED"
            "},sort_keys=True))"
        )
        result = subprocess.run(
            [sys.executable, "-Wa", "-c", statement],
            cwd=APP_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("The EMAIL_", result.stderr)
        payload = json.loads(result.stdout.strip().splitlines()[-1])
        self.assertEqual(payload["aliases"], ["default"])
        self.assertIn("locmem.EmailBackend", payload["backend"])
        self.assertFalse(payload["configured"])


class PaymentSignatureContractTests(unittest.TestCase):
    def test_explicit_sha1_preserves_legacy_signature_format(self):
        environment = os.environ.copy()
        environment.update(
            {
                "DJANGO_SETTINGS_MODULE": "test_settings_no_network_non_dtf",
                "PYTHONPATH": str(APP_ROOT),
            }
        )
        statement = """
import django
django.setup()
from django.test import override_settings
from management.ig_bot_models import provider_evidence_signature

with override_settings(SECRET_KEY="signature-contract-secret"):
    print(
        provider_evidence_signature(
            deal_id=1,
            client_id=2,
            provider="monobank",
            source="provider_pull",
            invoice_id="inv-1",
            provider_status="success",
            payload_digest="a" * 64,
        )
    )
"""
        result = subprocess.run(
            [sys.executable, "-Wa", "-c", statement],
            cwd=APP_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        signature = result.stdout.strip().splitlines()[-1]
        self.assertEqual(signature, "dbd20b4d534cef919aa46493f69b143ee815c3c4")
        self.assertEqual(len(signature), hashlib.sha1().digest_size * 2)
        self.assertNotIn("salted_hmac()", result.stderr)


class ImportCompatibilityContractTests(unittest.TestCase):
    def _run_storefront_tasks_script(
        self, script: str
    ) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment.update(
            {
                "DJANGO_SETTINGS_MODULE": "test_settings_no_network_non_dtf",
                "SECRET_KEY": "import-contract",
                "PYTHONPATH": str(APP_ROOT),
            }
        )
        return subprocess.run(
            [sys.executable, "-Wa", "-c", textwrap.dedent(script)],
            cwd=APP_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_storefront_tasks_import_has_no_load_module_warning(self):
        result = self._run_storefront_tasks_script(
            "import django; django.setup(); import storefront.tasks"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("load_module()", result.stderr)

    def test_storefront_tasks_forced_fallback_preserves_module_identity(self):
        result = self._run_storefront_tasks_script(
            """
            import builtins
            import django
            import importlib
            import sys

            django.setup()
            sys.modules.pop("storefront.tasks", None)
            sys.modules.pop("image_optimizer", None)
            real_import = builtins.__import__
            forced = {"count": 0}

            def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
                if name == "image_optimizer" and forced["count"] == 0:
                    forced["count"] += 1
                    raise ModuleNotFoundError(
                        "forced direct image_optimizer miss",
                        name="image_optimizer",
                    )
                return real_import(name, globals, locals, fromlist, level)

            builtins.__import__ = guarded_import
            try:
                tasks = importlib.import_module("storefront.tasks")
            finally:
                builtins.__import__ = real_import

            image_optimizer = importlib.import_module("image_optimizer")
            assert forced["count"] == 1
            assert sys.modules["image_optimizer"] is image_optimizer
            assert tasks.ImageOptimizer is image_optimizer.ImageOptimizer
            assert tasks.ImageOptimizer.__module__ == "image_optimizer"
            """
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("load_module()", result.stderr)

    def test_storefront_tasks_fallback_propagates_exec_error_and_cleans_module(self):
        result = self._run_storefront_tasks_script(
            """
            import builtins
            import django
            import importlib
            import importlib.machinery
            import importlib.util
            import sys

            django.setup()
            sys.modules.pop("storefront.tasks", None)
            sys.modules.pop("image_optimizer", None)
            real_import = builtins.__import__
            real_spec_from_file_location = importlib.util.spec_from_file_location

            class FailingLoader:
                def create_module(self, spec):
                    return None

                def exec_module(self, module):
                    raise RuntimeError("forced exec_module failure")

            def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
                if name == "image_optimizer":
                    raise ModuleNotFoundError(
                        "forced direct image_optimizer miss",
                        name="image_optimizer",
                    )
                return real_import(name, globals, locals, fromlist, level)

            def failing_spec(name, path):
                assert name == "image_optimizer"
                return importlib.machinery.ModuleSpec(name, FailingLoader())

            builtins.__import__ = guarded_import
            importlib.util.spec_from_file_location = failing_spec
            try:
                try:
                    importlib.import_module("storefront.tasks")
                except RuntimeError as exc:
                    assert str(exc) == "forced exec_module failure"
                else:
                    raise AssertionError("exec_module failure did not propagate")
            finally:
                builtins.__import__ = real_import
                importlib.util.spec_from_file_location = real_spec_from_file_location

            assert "image_optimizer" not in sys.modules
            assert "storefront.tasks" not in sys.modules
            """
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("load_module()", result.stderr)

    def test_storefront_tasks_does_not_fallback_for_transitive_import_error(self):
        result = self._run_storefront_tasks_script(
            """
            import builtins
            import django
            import importlib
            import sys

            django.setup()
            sys.modules.pop("storefront.tasks", None)
            sys.modules.pop("image_optimizer", None)
            real_import = builtins.__import__

            def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
                if name == "image_optimizer":
                    raise ModuleNotFoundError(
                        "forced transitive dependency miss",
                        name="forced_transitive_dependency",
                    )
                return real_import(name, globals, locals, fromlist, level)

            builtins.__import__ = guarded_import
            try:
                try:
                    importlib.import_module("storefront.tasks")
                except ModuleNotFoundError as exc:
                    assert exc.name == "forced_transitive_dependency"
                else:
                    raise AssertionError("transitive import error was hidden by fallback")
            finally:
                builtins.__import__ = real_import

            assert "image_optimizer" not in sys.modules
            assert "storefront.tasks" not in sys.modules
            """
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
