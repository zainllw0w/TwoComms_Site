"""No-network runtime contracts for the locked Python dependency set.

This module intentionally imports every integration that is required at
runtime. A missing package is a hard failure, rather than an optional skip.
The cryptographic checks use generated in-memory keys and never contact a
provider or persist business data.
"""

from __future__ import annotations

import base64
import os
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Never inherit deployment credentials when this contract is invoked from a
# shell or CI runner that happens to carry production environment variables.
os.environ["SECRET_KEY"] = "task3-runtime-contract-secret-key"
os.environ["DJANGO_SETTINGS_MODULE"] = "test_settings"

import cffi  # noqa: E402
import cryptography  # noqa: E402
import django  # noqa: E402
import jwt  # noqa: E402
import openai  # noqa: E402
from cryptography.hazmat.primitives import hashes, serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import ec, rsa  # noqa: E402
from cryptography.hazmat.primitives.kdf.hkdf import HKDF  # noqa: E402
from facebook_business.api import FacebookAdsApi  # noqa: E402
from facebook_business.adobjects.serverside.event import Event  # noqa: E402
from google.analytics.data_v1beta import BetaAnalyticsDataClient  # noqa: E402
from google.auth import default as google_default_credentials  # noqa: E402
from google.oauth2 import service_account  # noqa: E402

django.setup()

from finance.services.crypto import decrypt, encrypt, fingerprint  # noqa: E402
from storefront.views.monobank import _verify_signature_with_key  # noqa: E402


class DependencyRuntimeContracts(unittest.TestCase):
    def test_required_import_surfaces_are_real_modules(self):
        self.assertTrue(cffi.__file__)
        self.assertTrue(cryptography.__file__)
        self.assertTrue(BetaAnalyticsDataClient)
        self.assertTrue(google_default_credentials)
        self.assertTrue(service_account.Credentials)
        self.assertTrue(FacebookAdsApi)
        self.assertTrue(Event)

    def test_fernet_and_hkdf_round_trips_are_deterministic(self):
        plaintext = "monobank-token-test"
        ciphertext = encrypt(plaintext)
        self.assertNotEqual(ciphertext, plaintext)
        self.assertEqual(decrypt(ciphertext), plaintext)
        self.assertEqual(fingerprint(plaintext), fingerprint(plaintext))

        derived = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"task3-runtime-salt",
            info=b"task3-runtime-info",
        ).derive(b"task3-runtime-secret")
        self.assertEqual(len(derived), 32)

    def test_monobank_ecdsa_signature_verification_accepts_only_original_body(self):
        private_key = ec.generate_private_key(ec.SECP256R1())
        public_key = private_key.public_key()
        body = b"{\"invoiceId\":\"runtime-contract\"}"
        signature = private_key.sign(body, ec.ECDSA(hashes.SHA256()))
        public_pem = public_key.public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        encoded_key = base64.b64encode(public_pem)
        self.assertTrue(_verify_signature_with_key(encoded_key, signature, body))
        self.assertFalse(_verify_signature_with_key(encoded_key, signature, body + b"!"))

    def test_pyjwt_rs256_encode_decode_round_trip(self):
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        private_pem = private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        public_pem = private_key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        token = jwt.encode({"sub": "runtime-contract", "scope": "test"}, private_pem, algorithm="RS256")
        claims = jwt.decode(token, public_pem, algorithms=["RS256"])
        self.assertEqual(claims["sub"], "runtime-contract")

    def test_openai_client_construction_does_not_contact_network(self):
        client = openai.OpenAI(api_key="runtime-contract", base_url="http://127.0.0.1:9")
        self.assertEqual(str(client.base_url), "http://127.0.0.1:9")

    def test_project_settings_load_with_nonproduction_secret(self):
        from twocomms import settings as project_settings

        self.assertEqual(project_settings.SECRET_KEY, "task3-runtime-contract-secret-key")


if __name__ == "__main__":
    unittest.main()
