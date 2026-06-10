import uuid

from django.contrib.auth import get_user_model
from django.core import signing
from django.test import TestCase, Client as TestClient, override_settings
from django.urls import reverse
from django.utils import timezone

from management.models import (
    Client,
    ClientCPLink,
    ClientFollowUp,
    ClientInteractionAttempt,
    CommercialOfferEmailLog,
)

HOST = "management.twocomms.shop"
MGMT = override_settings(ROOT_URLCONF="twocomms.urls_management")


def _make_manager(username="cp_mgr"):
    return get_user_model().objects.create_user(username=username, password="x", is_staff=True)


def _make_log(owner, **kw):
    defaults = dict(
        owner=owner,
        recipient_email="client@example.com",
        recipient_name="ТестМаг",
        subject="S",
        status=CommercialOfferEmailLog.Status.SENT,
    )
    defaults.update(kw)
    return CommercialOfferEmailLog.objects.create(**defaults)


class TrackingModelTests(TestCase):
    def test_log_has_track_token(self):
        user = _make_manager("cp1")
        log = _make_log(user)
        self.assertIsInstance(log.track_token, uuid.UUID)
        log2 = _make_log(user, recipient_email="b@example.com")
        self.assertNotEqual(log.track_token, log2.track_token)


@MGMT
class TrackingEndpointTests(TestCase):
    def setUp(self):
        self.user = _make_manager("cp2")
        self.log = _make_log(self.user)
        self.http = TestClient()

    def test_open_pixel_sets_opened_at(self):
        url = reverse("management_cp_track_open", args=[str(self.log.track_token)])
        resp = self.http.get(url, HTTP_HOST=HOST, secure=True)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "image/png")
        self.log.refresh_from_db()
        self.assertIsNotNone(self.log.opened_at)

    def test_open_pixel_invalid_token_no_500(self):
        url = reverse("management_cp_track_open", args=[str(uuid.uuid4())])
        resp = self.http.get(url, HTTP_HOST=HOST, secure=True)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "image/png")

    def test_click_redirect_only_signed(self):
        signed = signing.dumps("https://twocomms.shop/wholesale/", salt="cp.click")
        url = reverse("management_cp_track_click", args=[str(self.log.track_token)])
        resp = self.http.get(url + f"?u={signed}", HTTP_HOST=HOST, secure=True)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp["Location"], "https://twocomms.shop/wholesale/")
        self.log.refresh_from_db()
        self.assertEqual(self.log.click_count, 1)
        self.assertIsNotNone(self.log.first_click_at)

    def test_click_redirect_rejects_unsigned(self):
        url = reverse("management_cp_track_click", args=[str(self.log.track_token)])
        resp = self.http.get(url + "?u=https://evil.example.com", HTTP_HOST=HOST, secure=True)
        self.assertEqual(resp.status_code, 302)
        self.assertNotIn("evil.example.com", resp["Location"])


@MGMT
class LinkClientTests(TestCase):
    def setUp(self):
        self.user = _make_manager("cp3")
        self.log = _make_log(self.user)
        self.http = TestClient()
        self.http.force_login(self.user)

    def _link(self, **payload):
        url = reverse("management_commercial_offer_link_client")
        return self.http.post(url, data=payload, HTTP_HOST=HOST, secure=True)

    def test_link_creates_new_client_idempotent(self):
        resp = self._link(log_id=self.log.id, new_shop_name="Новий Маг", new_phone="0501112233")
        self.assertEqual(resp.status_code, 200, resp.content)
        client = Client.objects.get(shop_name="Новий Маг")
        self.assertEqual(client.call_result, Client.CallResult.SENT_EMAIL)
        self.assertEqual(ClientCPLink.objects.filter(cp_log=self.log).count(), 1)
        self.assertTrue(ClientInteractionAttempt.objects.filter(cp_log=self.log).exists())
        resp2 = self._link(log_id=self.log.id, client_id=client.id)
        self.assertEqual(resp2.status_code, 200, resp2.content)
        self.assertEqual(ClientCPLink.objects.filter(cp_log=self.log).count(), 1)


@MGMT
class ProcessOutcomeTests(TestCase):
    def setUp(self):
        self.user = _make_manager("cp4")
        self.log = _make_log(self.user)
        self.client_obj = Client.objects.create(
            shop_name="М", phone="0501112233", full_name="І", owner=self.user
        )
        ClientCPLink.objects.create(client=self.client_obj, cp_log=self.log, linked_by=self.user)
        self.http = TestClient()
        self.http.force_login(self.user)

    def test_process_sets_outcome(self):
        url = reverse("management_commercial_offer_process")
        resp = self.http.post(url, data={"log_id": self.log.id, "response_outcome": "thinking"}, HTTP_HOST=HOST, secure=True)
        self.assertEqual(resp.status_code, 200, resp.content)
        self.log.refresh_from_db()
        self.assertEqual(self.log.response_outcome, "thinking")

    def test_process_creates_followup_when_linked(self):
        url = reverse("management_commercial_offer_process")
        due = (timezone.now() + timezone.timedelta(days=1)).strftime("%Y-%m-%dT%H:%M")
        resp = self.http.post(
            url,
            data={"log_id": self.log.id, "response_outcome": "thinking", "next_call_at": due},
            HTTP_HOST=HOST,
            secure=True,
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(ClientFollowUp.objects.filter(client=self.client_obj).exists())
