"""Regression contracts for warnings that must be green before Stage 0 exits."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
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
                "SECRET_KEY": "signature-contract-secret",
                "PYTHONPATH": str(APP_ROOT),
            }
        )
        statement = (
            "import django; django.setup(); "
            "from management.ig_bot_models import provider_evidence_signature; "
            "print(provider_evidence_signature(deal_id=1,client_id=2,provider='monobank',"
            "source='provider_pull',invoice_id='inv-1',provider_status='success',"
            "payload_digest='a'*64))"
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
        signature = result.stdout.strip().splitlines()[-1]
        self.assertEqual(len(signature), hashlib.sha1().digest_size * 2)
        self.assertNotIn("salted_hmac()", result.stderr)


class ImportCompatibilityContractTests(unittest.TestCase):
    def test_storefront_tasks_import_has_no_load_module_warning(self):
        environment = os.environ.copy()
        environment.update(
            {
                "DJANGO_SETTINGS_MODULE": "test_settings_no_network_non_dtf",
                "SECRET_KEY": "import-contract",
                "PYTHONPATH": str(APP_ROOT),
            }
        )
        result = subprocess.run(
            [
                sys.executable,
                "-Wa",
                "-c",
                "import django; django.setup(); import storefront.tasks",
            ],
            cwd=APP_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("load_module()", result.stderr)


if __name__ == "__main__":
    unittest.main()
