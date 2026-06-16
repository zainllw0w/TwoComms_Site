"""
Тести інтеграції Binotel: клієнт REST API (з мок-HTTP) + контроль доступу
до тестової вкладки.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, Client as TestClient, override_settings
from django.urls import reverse

from management.services.binotel import (
    BinotelClient,
    BinotelError,
    BinotelNotConfigured,
)

HOST = "management.twocomms.shop"


class _FakeResponse:
    def __init__(self, payload, status_code=200, text=""):
        self._payload = payload
        self.status_code = status_code
        self.text = text or ""

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


class BinotelClientTests(TestCase):
    def _client(self):
        return BinotelClient("k", "s")

    def test_build_url(self):
        c = self._client()
        self.assertEqual(
            c._build_url("calls/internal-number-to-external-number"),
            "https://api.binotel.com/api/4.0/calls/internal-number-to-external-number.json",
        )

    def test_send_request_injects_credentials(self):
        c = self._client()
        captured = {}

        def fake_post(url, data=None, headers=None, timeout=None):
            captured["url"] = url
            import json as _json
            captured["body"] = _json.loads(data)
            return _FakeResponse({"status": "success", "generalCallID": 42})

        with mock.patch.object(c._session, "post", side_effect=fake_post):
            data = c.internal_to_external("901", "0671112233")

        self.assertEqual(data["generalCallID"], 42)
        self.assertEqual(captured["body"]["key"], "k")
        self.assertEqual(captured["body"]["secret"], "s")
        self.assertEqual(captured["body"]["internalNumber"], "901")
        self.assertEqual(captured["body"]["externalNumber"], "0671112233")
        self.assertTrue(captured["url"].endswith("internal-number-to-external-number.json"))

    def test_error_status_raises(self):
        c = self._client()
        resp = _FakeResponse({"status": "error", "code": 121, "message": "Your key or secret is wrong"})
        with mock.patch.object(c._session, "post", return_value=resp):
            with self.assertRaises(BinotelError) as ctx:
                c.list_of_employees()
        self.assertEqual(ctx.exception.code, 121)

    def test_non_200_raises(self):
        c = self._client()
        resp = _FakeResponse(None, status_code=500, text="boom")
        with mock.patch.object(c._session, "post", return_value=resp):
            with self.assertRaises(BinotelError):
                c.online_calls()

    def test_invalid_json_raises(self):
        c = self._client()
        resp = _FakeResponse(None, status_code=200, text="<html>")
        with mock.patch.object(c._session, "post", return_value=resp):
            with self.assertRaises(BinotelError):
                c.online_calls()

    def test_call_details_wraps_single_id_into_list(self):
        c = self._client()
        captured = {}

        def fake_post(url, data=None, headers=None, timeout=None):
            import json as _json
            captured["body"] = _json.loads(data)
            return _FakeResponse({"status": "success", "callDetails": {}})

        with mock.patch.object(c._session, "post", side_effect=fake_post):
            c.call_details("123")
        self.assertEqual(captured["body"]["generalCallID"], ["123"])

    @override_settings(BINOTEL_API_KEY="", BINOTEL_API_SECRET="")
    def test_from_settings_not_configured(self):
        with self.assertRaises(BinotelNotConfigured):
            BinotelClient.from_settings()

    @override_settings(BINOTEL_API_KEY="abc", BINOTEL_API_SECRET="def")
    def test_from_settings_ok(self):
        c = BinotelClient.from_settings()
        self.assertEqual(c.key, "abc")
        self.assertEqual(c.secret, "def")
        self.assertTrue(BinotelClient.is_configured())


@override_settings(ROOT_URLCONF="twocomms.urls_management")
class BinotelViewAccessTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            username="bn_staff", password="x", is_staff=True
        )
        self.regular = get_user_model().objects.create_user(
            username="bn_user", password="x", is_staff=False
        )

    def test_page_redirects_for_non_staff(self):
        http = TestClient()
        http.force_login(self.regular)
        resp = http.get(reverse("management_binotel_test"), HTTP_HOST=HOST, secure=True)
        self.assertEqual(resp.status_code, 302)

    def test_page_ok_for_staff(self):
        http = TestClient()
        http.force_login(self.staff)
        resp = http.get(reverse("management_binotel_test"), HTTP_HOST=HOST, secure=True)
        self.assertEqual(resp.status_code, 200)

    def test_api_forbidden_for_non_staff(self):
        http = TestClient()
        http.force_login(self.regular)
        resp = http.get(reverse("management_binotel_status"), HTTP_HOST=HOST, secure=True)
        self.assertEqual(resp.status_code, 403)

    @override_settings(BINOTEL_API_KEY="", BINOTEL_API_SECRET="")
    def test_status_reports_not_configured(self):
        http = TestClient()
        http.force_login(self.staff)
        resp = http.get(reverse("management_binotel_status"), HTTP_HOST=HOST, secure=True)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertFalse(data["configured"])

    @override_settings(BINOTEL_API_KEY="", BINOTEL_API_SECRET="")
    def test_employees_requires_config(self):
        http = TestClient()
        http.force_login(self.staff)
        resp = http.get(reverse("management_binotel_employees"), HTTP_HOST=HOST, secure=True)
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.json()["configured"])

    @override_settings(BINOTEL_API_KEY="k", BINOTEL_API_SECRET="s")
    def test_call_initiates_with_mock(self):
        http = TestClient()
        http.force_login(self.staff)
        with mock.patch(
            "management.services.binotel.BinotelClient.internal_to_external",
            return_value={"status": "success", "generalCallID": 777},
        ):
            resp = http.post(
                reverse("management_binotel_call"),
                data={"internalNumber": "901", "externalNumber": "0671112233"},
                content_type="application/json",
                HTTP_HOST=HOST,
                secure=True,
            )
        self.assertEqual(resp.status_code, 200, resp.content)
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["generalCallID"], 777)

    @override_settings(BINOTEL_API_KEY="k", BINOTEL_API_SECRET="s")
    def test_raw_endpoint_whitelist(self):
        http = TestClient()
        http.force_login(self.staff)
        resp = http.post(
            reverse("management_binotel_raw"),
            data={"endpoint": "customers/delete", "params": {}},
            content_type="application/json",
            HTTP_HOST=HOST,
            secure=True,
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("не дозволений", resp.json()["error"])

    @override_settings(BINOTEL_API_KEY="k", BINOTEL_API_SECRET="s")
    def test_call_record_extracts_url(self):
        http = TestClient()
        http.force_login(self.staff)
        with mock.patch(
            "management.services.binotel.BinotelClient.call_record",
            return_value={"status": "success", "url": "https://rec.example/x.mp3"},
        ):
            resp = http.post(
                reverse("management_binotel_call_record"),
                data={"generalCallID": "123"},
                content_type="application/json",
                HTTP_HOST=HOST,
                secure=True,
            )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["url"], "https://rec.example/x.mp3")
