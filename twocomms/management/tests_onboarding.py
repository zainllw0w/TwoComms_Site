"""Тести Фази 6: онбординг-гейт + PII."""
from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from management.models import ManagerOnboardingConsent, ManagerPersonalData, AdminAuditLog
from management.services import pii

User = get_user_model()
TEST_KEY = Fernet.generate_key().decode()


class GateLogicTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = User.objects.create_user(username="g_mgr", password="x")
        cls.manager.userprofile.is_manager = True
        cls.manager.userprofile.save()
        cls.staff = User.objects.create_user(username="g_boss", password="x", is_staff=True)

    def test_manager_without_consent_is_gated(self):
        from management.middleware import manager_is_gated
        self.assertTrue(manager_is_gated(self.manager))

    def test_consent_unblocks(self):
        from management.middleware import manager_is_gated
        ManagerOnboardingConsent.objects.create(
            owner=self.manager, rules_version="1",
            accepted_18plus=True, accepted_rules=True, accepted_pdn=True,
        )
        self.assertFalse(manager_is_gated(self.manager))

    def test_non_manager_not_gated(self):
        from management.middleware import manager_is_gated
        self.assertFalse(manager_is_gated(self.staff))


@override_settings(
    ROOT_URLCONF="twocomms.urls_management",
    ALLOWED_HOSTS=["testserver", "management.twocomms.shop"],
    MANAGEMENT_ONBOARDING_ENABLED=True,
    MANAGEMENT_RULES_VERSION="1",
)
class GateMiddlewareTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = User.objects.create_user(username="gm_mgr", password="x")
        cls.manager.userprofile.is_manager = True
        cls.manager.userprofile.save()
        cls.staff = User.objects.create_user(username="gm_boss", password="x", is_staff=True)

    def test_gated_manager_redirected_to_onboarding(self):
        self.client.force_login(self.manager)
        resp = self.client.get("/", HTTP_HOST="management.twocomms.shop", secure=True)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/onboarding/", resp.url)

    def test_onboarding_path_not_blocked(self):
        self.client.force_login(self.manager)
        resp = self.client.get("/onboarding/", HTTP_HOST="management.twocomms.shop", secure=True)
        self.assertEqual(resp.status_code, 200)

    def test_staff_never_blocked(self):
        self.client.force_login(self.staff)
        resp = self.client.get("/admin-panel/", HTTP_HOST="management.twocomms.shop", secure=True)
        self.assertEqual(resp.status_code, 200)

    def test_consent_endpoint_unblocks(self):
        self.client.force_login(self.manager)
        resp = self.client.post(
            "/onboarding/consent/",
            data='{"accepted_18plus": true, "accepted_rules": true, "accepted_pdn": true}',
            content_type="application/json", HTTP_HOST="management.twocomms.shop", secure=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["ok"])
        self.assertTrue(ManagerOnboardingConsent.objects.filter(owner=self.manager, rules_version="1").exists())

    def test_consent_requires_all(self):
        self.client.force_login(self.manager)
        resp = self.client.post(
            "/onboarding/consent/",
            data='{"accepted_18plus": true, "accepted_rules": false, "accepted_pdn": true}',
            content_type="application/json", HTTP_HOST="management.twocomms.shop", secure=True,
        )
        self.assertEqual(resp.status_code, 400)


@override_settings(MANAGEMENT_ONBOARDING_ENABLED=False)
class GateDisabledTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = User.objects.create_user(username="gd_mgr", password="x")
        cls.manager.userprofile.is_manager = True
        cls.manager.userprofile.save()

    @override_settings(ROOT_URLCONF="twocomms.urls_management",
                       ALLOWED_HOSTS=["testserver", "management.twocomms.shop"])
    def test_disabled_gate_does_not_block(self):
        self.client.force_login(self.manager)
        # Без consent, але гейт вимкнено → не редіректить на онбординг.
        resp = self.client.get("/", HTTP_HOST="management.twocomms.shop", secure=True)
        self.assertNotIn(getattr(resp, "url", ""), ["/onboarding/"])


@override_settings(FIELD_ENCRYPTION_KEY=TEST_KEY)
class PIITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = User.objects.create_user(username="pii_mgr", password="x")
        cls.staff = User.objects.create_user(username="pii_boss", password="x", is_staff=True)

    def test_encrypt_decrypt_roundtrip(self):
        token = pii.encrypt("1234567890")
        self.assertIsNotNone(token)
        self.assertNotIn(b"1234567890", token)
        self.assertEqual(pii.decrypt(token), "1234567890")

    def test_mask_tail(self):
        self.assertEqual(pii.mask_tail("1234567890"), "****7890")
        self.assertEqual(pii.mask_tail(""), "—")

    def test_set_and_reveal_writes_audit(self):
        pii.set_personal_data(self.manager, tax_id="1234567890", passport="ABС123456", actor=self.staff)
        rec = ManagerPersonalData.objects.get(owner=self.manager)
        self.assertEqual(rec.tax_id_tail, "7890")
        self.assertTrue(AdminAuditLog.objects.filter(action="pii_update", entity_id=str(self.manager.id)).exists())

        data = pii.reveal_personal_data(self.manager, actor=self.staff, reason="перевірка договору")
        self.assertEqual(data["tax_id"], "1234567890")
        self.assertTrue(AdminAuditLog.objects.filter(action="pii_reveal", entity_id=str(self.manager.id)).exists())

    @override_settings(FIELD_ENCRYPTION_KEY="")
    def test_decrypt_without_key_returns_empty(self):
        self.assertEqual(pii.decrypt(b"whatever"), "")
