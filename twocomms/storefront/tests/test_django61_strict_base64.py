from __future__ import annotations

import base64
import importlib.machinery
import importlib.util
from pathlib import Path
from unittest.mock import Mock, patch

from django.core.cache import cache
from django.test import RequestFactory, SimpleTestCase

from storefront.views.monobank import (
    _verify_monobank_signature,
    _verify_signature_with_key,
)
from storefront.views.utils import _verify_monobank_signature as _verify_utils_signature


def _base64_variants(raw: bytes):
    for alphabet, encoder in (
        ("standard", base64.b64encode),
        ("urlsafe", base64.urlsafe_b64encode),
    ):
        padded = encoder(raw).decode("ascii")
        yield alphabet, "padded", padded
        yield alphabet, "unpadded", padded.rstrip("=")


def _make_ec_keypair():
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    private_key = ec.generate_private_key(ec.SECP256R1())
    pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_key, pem


def _sign_ec(private_key, body: bytes) -> bytes:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec

    return private_key.sign(body, ec.ECDSA(hashes.SHA256()))


class ModularMonobankBase64ContractTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _request(self, signature: str, body=b'{"status":"success"}'):
        return self.factory.post(
            "/payments/monobank/webhook/",
            data=body,
            content_type="application/json",
            HTTP_X_SIGN=signature,
        )

    def test_signature_accepts_standard_and_urlsafe_padded_and_unpadded_values(self):
        signature_bytes = b"\xfb\xff"

        for alphabet, padding, encoded in _base64_variants(signature_bytes):
            with self.subTest(alphabet=alphabet, padding=padding):
                request = self._request(encoded)
                with patch(
                    "storefront.views.monobank._get_monobank_public_key",
                    return_value="provider-public-key",
                ), patch(
                    "storefront.views.monobank._verify_signature_with_key",
                    return_value=True,
                ) as verify:
                    self.assertTrue(_verify_monobank_signature(request))

                verify.assert_called_once_with(
                    "provider-public-key",
                    signature_bytes,
                    request.body,
                )

    def test_signature_rejects_whitespace_and_trailing_garbage_before_verify(self):
        encoded = base64.b64encode(b"\xfb\xff").decode("ascii")
        invalid_values = {
            "embedded whitespace": f"{encoded[:2]} {encoded[2:]}",
            "non alphabet": f"{encoded}!!",
            "alphabet after padding": f"{encoded}QUJD",
        }

        for label, malformed in invalid_values.items():
            with self.subTest(label=label):
                request = self._request(malformed)
                with patch(
                    "storefront.views.monobank._get_monobank_public_key",
                    return_value="provider-public-key",
                ), patch(
                    "storefront.views.monobank._verify_signature_with_key",
                    return_value=True,
                ) as verify:
                    with self.assertLogs("storefront.monobank", level="WARNING") as caught:
                        self.assertFalse(_verify_monobank_signature(request))

                verify.assert_not_called()
                self.assertNotIn(malformed, "\n".join(caught.output))

    def test_public_key_accepts_standard_and_urlsafe_padded_and_unpadded_values(self):
        private_key, pem = _make_ec_keypair()
        body = b"provider-body"
        signature = _sign_ec(private_key, body)

        for alphabet, padding, encoded in _base64_variants(pem):
            with self.subTest(alphabet=alphabet, padding=padding):
                self.assertTrue(_verify_signature_with_key(encoded, signature, body))

    def test_public_key_rejects_trailing_garbage_without_logging_material(self):
        private_key, pem = _make_ec_keypair()
        body = b"provider-body"
        signature = _sign_ec(private_key, body)
        encoded_key = base64.b64encode(pem).decode("ascii")
        malformed = f"{encoded_key}!!"

        with self.assertLogs("storefront.monobank", level="WARNING") as caught:
            self.assertFalse(_verify_signature_with_key(malformed, signature, body))

        log_output = "\n".join(caught.output)
        self.assertNotIn(encoded_key, log_output)
        self.assertNotIn(malformed, log_output)


class UtilsMonobankBase64ContractTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()

    def tearDown(self):
        cache.clear()

    def _rsa_fixture(self):
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding, rsa

        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pem = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        body = b"legacy-utils-provider-body"
        signature = private_key.sign(body, padding.PKCS1v15(), hashes.SHA256())
        return pem, body, signature

    def _request(self, signature: str, body: bytes):
        return self.factory.post(
            "/payments/monobank/webhook/",
            data=body,
            content_type="application/json",
            HTTP_X_SIGN=signature,
        )

    def test_utils_signature_accepts_all_provider_compatible_variants(self):
        pem, body, signature = self._rsa_fixture()
        cache.set("monobank_public_key", pem.decode("ascii"), 60)

        for alphabet, padding, encoded in _base64_variants(signature):
            with self.subTest(alphabet=alphabet, padding=padding):
                self.assertTrue(_verify_utils_signature(self._request(encoded, body)))

    def test_utils_signature_rejects_trailing_garbage_without_logging_material(self):
        pem, body, signature = self._rsa_fixture()
        cache.set("monobank_public_key", pem.decode("ascii"), 60)
        encoded_signature = base64.b64encode(signature).decode("ascii")
        malformed = f"{encoded_signature}!!"

        with self.assertLogs("storefront.monobank", level="WARNING") as caught:
            self.assertFalse(_verify_utils_signature(self._request(malformed, body)))

        log_output = "\n".join(caught.output)
        self.assertNotIn(encoded_signature, log_output)
        self.assertNotIn(malformed, log_output)


class LoadedLegacyMonobankBase64ContractTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        legacy_path = Path(__file__).resolve().parents[1] / "views.py.backup"
        loader = importlib.machinery.SourceFileLoader(
            "storefront.django61_strict_base64_legacy",
            str(legacy_path),
        )
        spec = importlib.util.spec_from_loader(loader.name, loader)
        cls.legacy = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.legacy)
        cls.factory = RequestFactory()

    def _request(self, signature: str, body=b"legacy-provider-body"):
        return self.factory.post(
            "/legacy-monobank-webhook/",
            data=body,
            content_type="application/json",
            HTTP_X_SIGN=signature,
        )

    def test_loaded_legacy_signature_accepts_all_provider_compatible_variants(self):
        signature_bytes = b"\xfb\xff"

        for alphabet, padding, encoded in _base64_variants(signature_bytes):
            with self.subTest(alphabet=alphabet, padding=padding):
                public_key = Mock()
                request = self._request(encoded)
                with patch.object(
                    self.legacy,
                    "_get_monobank_public_key",
                    return_value=public_key,
                ):
                    self.assertTrue(self.legacy._verify_monobank_signature(request))

                self.assertEqual(public_key.verify.call_args.args[0], signature_bytes)
                self.assertEqual(public_key.verify.call_args.args[1], request.body)

    def test_loaded_legacy_signature_rejects_trailing_garbage(self):
        signature = base64.b64encode(b"\xfb\xff").decode("ascii")
        malformed = f"{signature}!!"
        public_key = Mock()

        with patch.object(
            self.legacy,
            "_get_monobank_public_key",
            return_value=public_key,
        ):
            self.assertFalse(self.legacy._verify_monobank_signature(self._request(malformed)))

        public_key.verify.assert_not_called()

    def test_loaded_legacy_public_key_accepts_all_provider_compatible_variants(self):
        _, pem = _make_ec_keypair()

        for alphabet, padding, encoded in _base64_variants(pem):
            with self.subTest(alphabet=alphabet, padding=padding):
                self.legacy.MONOBANK_SIGNATURE_CACHE.update(key=None, fetched_at=0)
                with patch.object(
                    self.legacy,
                    "_monobank_api_request",
                    return_value={"result": {"key": encoded}},
                ):
                    public_key = self.legacy._get_monobank_public_key()

                self.assertIsNotNone(public_key)

    def test_loaded_legacy_public_key_rejects_trailing_garbage_safely(self):
        _, pem = _make_ec_keypair()
        secret_marker = "PUBLIC_KEY_MATERIAL_MUST_NOT_LEAK"
        malformed = f"{base64.b64encode(pem).decode('ascii')}!!{secret_marker}"
        self.legacy.MONOBANK_SIGNATURE_CACHE.update(key=None, fetched_at=0)

        with patch.object(
            self.legacy,
            "_monobank_api_request",
            return_value={"result": {"key": malformed}},
        ):
            with self.assertRaisesRegex(
                self.legacy.MonobankAPIError,
                r"^Помилка при обробці ключа підпису\.$",
            ) as caught:
                self.legacy._get_monobank_public_key()

        self.assertNotIn(secret_marker, str(caught.exception))
