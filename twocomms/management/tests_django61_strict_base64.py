from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import signing
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from accounts.models import UserProfile
from management.bot_views import _parse_meta_signed_request
from management.models import ManagerPersonalData
from management.parser_usage import (
    GoogleProjectUsageProvider,
    _service_account_info_from_env_or_file,
)
from management.services import pii
from management.views import _resolve_profile_from_start_payload


def _service_account_payload() -> tuple[bytes, dict]:
    payload = {
        "project_id": "django61-base64",
        "marker": "¾",
    }
    return (
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
        payload,
    )


def _base64_variants(raw: bytes):
    for alphabet, encoder in (
        ("standard", base64.b64encode),
        ("urlsafe", base64.urlsafe_b64encode),
    ):
        padded = encoder(raw).decode("ascii")
        yield alphabet, "padded", padded
        yield alphabet, "unpadded", padded.rstrip("=")


class MetaSignedRequestBase64ContractTests(SimpleTestCase):
    secret = "django61-meta-secret"
    payload = {"user_id": "123"}

    def _parts(self, *, encoded_payload: str | None = None) -> tuple[str, str]:
        if encoded_payload is None:
            encoded_payload = base64.urlsafe_b64encode(
                json.dumps(self.payload, separators=(",", ":")).encode("utf-8")
            ).decode("ascii").rstrip("=")
        signature = hmac.new(
            self.secret.encode("utf-8"),
            encoded_payload.encode("ascii"),
            hashlib.sha256,
        ).digest()
        encoded_signature = (
            base64.urlsafe_b64encode(signature).decode("ascii").rstrip("=")
        )
        return encoded_signature, encoded_payload

    def test_accepts_valid_meta_signed_request(self):
        encoded_signature, encoded_payload = self._parts()

        with patch.dict(
            "os.environ",
            {"FACEBOOK_APP_SECRET": self.secret},
            clear=True,
        ):
            self.assertEqual(
                _parse_meta_signed_request(f"{encoded_signature}.{encoded_payload}"),
                self.payload,
            )

    def test_rejects_trailing_garbage_in_signature_or_payload(self):
        encoded_signature, encoded_payload = self._parts()
        garbage_payload = f"{encoded_payload}!!"
        garbage_payload_signature, _ = self._parts(encoded_payload=garbage_payload)

        malformed_requests = {
            "signature": f"{encoded_signature}!!.{encoded_payload}",
            "payload": f"{garbage_payload_signature}.{garbage_payload}",
        }
        with patch.dict(
            "os.environ",
            {"FACEBOOK_APP_SECRET": self.secret},
            clear=True,
        ):
            for label, malformed in malformed_requests.items():
                with self.subTest(label=label):
                    self.assertEqual(_parse_meta_signed_request(malformed), {})


class LegacyManagerStartPayloadBase64ContractTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(username="strict-base64-manager")
        self.profile, _ = UserProfile.objects.get_or_create(user=user)
        self.profile.tg_manager_bind_code = "strictcode123"
        self.profile.tg_manager_bind_expires_at = timezone.now() + timedelta(minutes=10)
        self.profile.save(
            update_fields=["tg_manager_bind_code", "tg_manager_bind_expires_at"]
        )
        signed = signing.Signer(salt="management.bot.bind").sign(
            f"{user.pk}-{self.profile.tg_manager_bind_code}"
        )
        self.wrapped = base64.urlsafe_b64encode(signed.encode("utf-8")).decode("ascii")

    def test_accepts_valid_padded_and_unpadded_legacy_wrappers(self):
        for padding, token in (
            ("padded", self.wrapped),
            ("unpadded", self.wrapped.rstrip("=")),
        ):
            with self.subTest(padding=padding):
                self.assertEqual(_resolve_profile_from_start_payload(token), self.profile)

    def test_rejects_legacy_wrapper_with_trailing_garbage(self):
        self.assertIsNone(
            _resolve_profile_from_start_payload(f"{self.wrapped.rstrip('=')}!!!")
        )

    def test_rejects_legacy_wrapper_surrounded_by_whitespace(self):
        self.assertIsNone(_resolve_profile_from_start_payload(f" {self.wrapped}\n"))


@override_settings(
    GOOGLE_SERVICE_ACCOUNT_JSON="",
    GOOGLE_APPLICATION_CREDENTIALS="",
    GOOGLE_MONITORING_ACCESS_TOKEN="",
)
class ServiceAccountBase64ContractTests(SimpleTestCase):
    def test_accepts_standard_and_urlsafe_padded_and_unpadded_payloads(self):
        raw, expected = _service_account_payload()

        for alphabet, padding, encoded in _base64_variants(raw):
            with self.subTest(alphabet=alphabet, padding=padding):
                with override_settings(GOOGLE_SERVICE_ACCOUNT_JSON_B64=encoded), patch.dict(
                    os.environ,
                    {},
                    clear=True,
                ):
                    self.assertEqual(_service_account_info_from_env_or_file(), expected)

    def test_rejects_whitespace_non_alphabet_and_trailing_garbage(self):
        raw, _ = _service_account_payload()
        encoded = base64.b64encode(raw).decode("ascii")
        double_padded = base64.b64encode(b"x").decode("ascii")
        self.assertTrue(double_padded.endswith("=="))
        invalid_values = {
            "leading whitespace": f" {encoded}",
            "embedded whitespace": f"{encoded[:8]} {encoded[8:]}",
            "non alphabet": f"{encoded}!!",
            "alphabet after padding": f"{encoded}QUJD",
            "partial padding": double_padded[:-1],
            "impossible length": "A",
            "non ascii": "£",
        }

        for label, malformed in invalid_values.items():
            with self.subTest(label=label):
                with override_settings(GOOGLE_SERVICE_ACCOUNT_JSON_B64=malformed), patch.dict(
                    os.environ,
                    {},
                    clear=True,
                ):
                    with self.assertRaisesRegex(ValueError, r"^Invalid Base64 payload$"):
                        _service_account_info_from_env_or_file()

    def test_provider_status_does_not_echo_invalid_credential_material(self):
        raw, _ = _service_account_payload()
        secret_marker = "PRIVATE_KEY_MATERIAL_MUST_NOT_LEAK"
        malformed = f"{base64.b64encode(raw).decode('ascii')}!!{secret_marker}"
        provider = GoogleProjectUsageProvider()

        with override_settings(GOOGLE_SERVICE_ACCOUNT_JSON_B64=malformed), patch.dict(
            os.environ,
            {"GOOGLE_CLOUD_PROJECT": "django61-base64"},
            clear=True,
        ):
            token, status = provider._monitoring_access_token()

        self.assertIsNone(token)
        self.assertEqual(
            status,
            "local only · invalid Google credentials (Invalid Base64 payload)",
        )
        self.assertNotIn(secret_marker, status)


class ManagerPersonalDataBinaryFieldContractTests(SimpleTestCase):
    def test_binary_field_base64_round_trip(self):
        raw = b"\x00encrypted-manager-pii\xff"
        field = ManagerPersonalData._meta.get_field("tax_id_enc")
        instance = ManagerPersonalData(tax_id_enc=raw)

        serialized = field.value_to_string(instance)
        restored = field.to_python(serialized)

        self.assertEqual(base64.b64decode(serialized, validate=True), raw)
        self.assertEqual(bytes(restored), raw)

    def test_binary_field_rejects_invalid_base64_without_logging_value(self):
        field = ManagerPersonalData._meta.get_field("passport_enc")

        for malformed in (
            "ZW5jcnlwdGVk IHBpaQ==",
            "ZW5jcnlwdGVkLXBpaQ==!!",
            "ZW5jcnlwdGVkLXBpaQ==QUJD",
        ):
            with self.subTest(malformed=malformed), self.assertNoLogs(
                "management.pii",
                level="WARNING",
            ):
                with self.assertRaises(ValidationError) as caught:
                    field.to_python(malformed)
                self.assertEqual(caught.exception.error_list[0].code, "invalid")

    def test_decrypt_failure_log_never_contains_pii_or_exception_detail(self):
        secret_marker = "PASSPORT_VALUE_MUST_NOT_LEAK"

        class RejectingFernet:
            def decrypt(self, token):
                raise ValueError(f"invalid encrypted value {secret_marker}")

        with patch("management.services.pii._fernet", return_value=RejectingFernet()):
            with self.assertLogs("management.pii", level="WARNING") as caught:
                self.assertEqual(pii.decrypt(b"opaque-token"), "")

        log_output = "\n".join(caught.output)
        self.assertNotIn(secret_marker, log_output)
        self.assertNotIn("invalid encrypted value", log_output)
