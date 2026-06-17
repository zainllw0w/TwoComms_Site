"""
Тести єдиного вхідного вебхука Binotel (apiCallSettings / apiCallCompleted).
"""
import json

from django.contrib.auth import get_user_model
from django.test import TestCase, Client as TestClient, override_settings
from django.urls import reverse

from management.models import BinotelWebhookEvent, CallRecord, Client
from management.services.binotel import (
    client_ip_from_request,
    is_binotel_ip,
    parse_webhook_call_details,
)

HOST = "management.twocomms.shop"
BINOTEL_IP = "194.88.218.116"


class BinotelWebhookHelpersTests(TestCase):
    def test_parse_call_details_direction(self):
        out = parse_webhook_call_details({"generalCallID": 123, "callType": 0, "externalNumber": "(067) 111-22-33", "billsec": 42})
        self.assertEqual(out["general_call_id"], "123")
        self.assertEqual(out["direction"], "inbound")
        self.assertEqual(out["external_number"], "0671112233")
        self.assertEqual(out["bill_seconds"], 42)
        out2 = parse_webhook_call_details({"generalCallID": 9, "callType": 1})
        self.assertEqual(out2["direction"], "outbound")

    def test_is_binotel_ip(self):
        self.assertTrue(is_binotel_ip("194.88.218.116"))
        self.assertFalse(is_binotel_ip("8.8.8.8"))
        self.assertFalse(is_binotel_ip(""))


@override_settings(ROOT_URLCONF="twocomms.urls_management")
class BinotelWebhookEndpointTests(TestCase):
    def setUp(self):
        self.http = TestClient()
        self.url = reverse("management_binotel_webhook")

    def _post(self, payload, **extra):
        return self.http.post(
            self.url,
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_HOST=HOST,
            secure=True,
            **extra,
        )

    def test_get_healthcheck(self):
        resp = self.http.get(self.url, HTTP_HOST=HOST, secure=True)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json().get("status"), "ok")

    def test_call_completed_creates_callrecord(self):
        payload = {
            "requestType": "apiCallCompleted",
            "callDetails": {
                "generalCallID": 555001,
                "companyID": 94066,
                "callType": 1,
                "internalNumber": "901",
                "externalNumber": "0671112233",
                "billsec": 73,
                "waitsec": 5,
                "disposition": "ANSWER",
                "startTime": 1700000000,
            },
        }
        resp = self._post(payload)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json().get("status"), "success")
        rec = CallRecord.objects.get(provider="binotel", external_call_id="555001")
        self.assertEqual(rec.direction, "outbound")
        self.assertEqual(rec.duration_seconds, 73)
        ev = BinotelWebhookEvent.objects.latest("id")
        self.assertEqual(ev.request_type, "apiCallCompleted")
        self.assertTrue(ev.handled_ok)

    def test_call_completed_idempotent(self):
        payload = {
            "requestType": "apiCallCompleted",
            "callDetails": {"generalCallID": 777, "callType": 1, "externalNumber": "0670000000", "billsec": 10},
        }
        self._post(payload)
        self._post(payload)
        self.assertEqual(CallRecord.objects.filter(external_call_id="777").count(), 1)

    def test_call_settings_known_client(self):
        owner = get_user_model().objects.create_user(username="own1", password="x", email="m@e.com")
        Client.objects.create(shop_name="Тестовий магазин", phone="0671112233", owner=owner)
        payload = {"requestType": "apiCallSettings", "callType": 0, "externalNumber": "0671112233", "companyID": 94066}
        resp = self._post(payload)
        self.assertEqual(resp.status_code, 200)
        cd = resp.json().get("customerData")
        self.assertIsNotNone(cd)
        self.assertEqual(cd["name"], "Тестовий магазин")
        self.assertEqual(cd.get("assignedToEmployeeEmail"), "m@e.com")
        self.assertIn("linkToCrmUrl", cd)

    def test_call_settings_unknown_client(self):
        payload = {"requestType": "apiCallSettings", "callType": 0, "externalNumber": "0000000000"}
        resp = self._post(payload)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {})

    def test_unknown_request_type_acked(self):
        resp = self._post({"requestType": "somethingElse"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json().get("status"), "success")

    def test_invalid_json_does_not_500(self):
        resp = self.http.post(
            self.url, data="<<<not json>>>", content_type="application/json",
            HTTP_HOST=HOST, secure=True,
        )
        self.assertEqual(resp.status_code, 200)

    @override_settings(BINOTEL_WEBHOOK_ENFORCE_IP=True)
    def test_ip_enforcement_blocks_non_binotel(self):
        resp = self._post({"requestType": "apiCallCompleted", "callDetails": {"generalCallID": 1}}, REMOTE_ADDR="8.8.8.8")
        self.assertEqual(resp.status_code, 403)

    @override_settings(BINOTEL_WEBHOOK_ENFORCE_IP=True)
    def test_ip_enforcement_allows_binotel(self):
        resp = self._post(
            {"requestType": "apiCallCompleted", "callDetails": {"generalCallID": 222, "callType": 1, "billsec": 1}},
            REMOTE_ADDR=BINOTEL_IP,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json().get("status"), "success")

    @override_settings(BINOTEL_WEBHOOK_TOKEN="s3cr3t")
    def test_token_required_when_set(self):
        # Без токена в шляху → 404.
        resp = self._post({"requestType": "apiCallCompleted", "callDetails": {"generalCallID": 1}})
        self.assertEqual(resp.status_code, 404)
        # З правильним токеном → 200.
        url = reverse("management_binotel_webhook_token", kwargs={"token": "s3cr3t"})
        resp2 = self.http.post(
            url, data=json.dumps({"requestType": "apiCallCompleted", "callDetails": {"generalCallID": 2, "callType": 1, "billsec": 1}}),
            content_type="application/json", HTTP_HOST=HOST, secure=True,
        )
        self.assertEqual(resp2.status_code, 200)


@override_settings(ROOT_URLCONF="twocomms.urls_management")
class BinotelWebhookEventsViewTests(TestCase):
    def test_events_view_access(self):
        staff = get_user_model().objects.create_user(username="st", password="x", is_staff=True)
        regular = get_user_model().objects.create_user(username="rg", password="x")
        url = reverse("management_binotel_webhook_events")

        anon = TestClient().get(url, HTTP_HOST=HOST, secure=True)
        self.assertIn(anon.status_code, (302, 403))

        http = TestClient(); http.force_login(regular)
        self.assertEqual(http.get(url, HTTP_HOST=HOST, secure=True).status_code, 403)

        http2 = TestClient(); http2.force_login(staff)
        resp = http2.get(url, HTTP_HOST=HOST, secure=True)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["success"])
