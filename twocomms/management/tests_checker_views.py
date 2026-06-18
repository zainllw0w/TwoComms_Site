from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client as DjangoClient
from django.test import TestCase, override_settings
from django.urls import reverse

from management import checker_views as cv
from management.models import LeadAICheck, LeadCheckerSettings, ManagementLead
from management.services import lead_checker

User = get_user_model()

HOST = "management.twocomms.shop"

MGMT = override_settings(
    ROOT_URLCONF="twocomms.urls_management",
    ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1", HOST],
    SECURE_SSL_REDIRECT=False,
)


class SerializeCheckTests(TestCase):
    def test_serialize_lead_with_check(self):
        lead = ManagementLead.objects.create(
            shop_name="Coyote", phone="0501112233", city="Харків",
            website_url="https://coyote.example", ai_score=82, ai_verdict="fit",
            lead_source=ManagementLead.LeadSource.PARSER,
        )
        LeadAICheck.objects.create(
            lead=lead, status=LeadAICheck.Status.DONE, overall_score=82,
            verdict_category="brand", partnership_fit=["wholesale", "collab"],
            confidence="high", brand_summary="UA streetwear",
            criteria=[{"key": "product_relevance", "title": "Товар", "score": 9, "comment": "ok"}],
            recommendation="колаб", sources=[{"title": "IG", "url": "https://instagram.com/x"}],
            instagram_url="https://instagram.com/x",
        )
        data = cv.serialize_lead_check(lead)
        self.assertEqual(data["lead_id"], lead.id)
        self.assertEqual(data["shop_name"], "Coyote")
        self.assertEqual(data["ai_score"], 82)
        self.assertEqual(data["ai_verdict"], "fit")
        self.assertEqual(data["verdict_category"], "brand")
        self.assertEqual(data["partnership_fit"], ["wholesale", "collab"])
        self.assertEqual(len(data["criteria"]), 1)
        self.assertEqual(data["instagram_url"], "https://instagram.com/x")

    def test_serialize_lead_without_check(self):
        lead = ManagementLead.objects.create(shop_name="NoCheck", phone="0501112299",
                                             lead_source=ManagementLead.LeadSource.PARSER)
        data = cv.serialize_lead_check(lead)
        self.assertEqual(data["lead_id"], lead.id)
        self.assertIsNone(data["ai_score"])
        self.assertEqual(data["criteria"], [])


@MGMT
class CheckerApiTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user("boss", password="x", is_staff=True)
        self.client = DjangoClient()
        self.client.force_login(self.staff)
        for i in range(2):
            ManagementLead.objects.create(shop_name=f"S{i}", phone=f"05055500{i}",
                                          lead_source=ManagementLead.LeadSource.PARSER)

    def _post(self, name, data=None, **kw):
        return self.client.post(reverse(name), data or {}, HTTP_HOST=HOST, secure=True, **kw)

    def _get(self, name, data=None, **kw):
        return self.client.get(reverse(name), data or {}, HTTP_HOST=HOST, secure=True, **kw)

    def test_start_status_stop_flow(self):
        r = self._post("management_checker_start_api",
                       {"scope": "unchecked", "requests_per_minute": "20"})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["success"])
        job_id = body["job"]["id"]

        r = self._get("management_checker_status_api", {"job_id": job_id})
        self.assertEqual(r.json()["job"]["total_selected"], 2)

        r = self._post("management_checker_stop_api", {"job_id": job_id})
        self.assertEqual(r.json()["job"]["status"], "stopped")

    def test_step_scores_one(self):
        start = self._post("management_checker_start_api",
                           {"scope": "unchecked", "requests_per_minute": "60"}).json()
        job_id = start["job"]["id"]
        fake = {"parsed": {"overall_score": 78, "criteria": []}, "usage": {}, "model": "m"}
        with patch.object(lead_checker, "gemini_generate_grounded", return_value=fake), \
             patch.object(lead_checker, "fetch_website_text", return_value=("", False)), \
             patch("management.services.lead_check_job.checker_can_run", return_value=True):
            r = self._post("management_checker_step_api", {"job_id": job_id})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["job"]["processed"], 1)

    def test_results_api_filters_band(self):
        from django.utils import timezone
        lead = ManagementLead.objects.first()
        lead.ai_score = 85
        lead.ai_verdict = "fit"
        lead.ai_checked_at = timezone.now()
        lead.save()
        LeadAICheck.objects.create(lead=lead, status=LeadAICheck.Status.DONE, overall_score=85)
        r = self._get("management_checker_results_api", {"band": "fit"})
        self.assertEqual(r.status_code, 200)
        rows = r.json()["results"]["rows"]
        self.assertTrue(any(row["lead_id"] == lead.id for row in rows))

    def test_settings_api_saves_key(self):
        r = self._post("management_checker_settings_api",
                       {"gemini_api_key": "new-key", "requests_per_minute": "10"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(LeadCheckerSettings.load().gemini_api_key, "new-key")

    def test_keys_status_api_returns_six(self):
        r = self._get("management_checker_keys_status_api")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["success"])
        self.assertEqual(len(body["keys"]), 6)
        self.assertIn("key_name", body["keys"][0])
        self.assertIn("available", body["keys"][0])

    def test_settings_api_saves_auto_recheck(self):
        r = self._post("management_checker_settings_api",
                       {"auto_recheck": "1", "auto_recheck_batch": "40"})
        self.assertEqual(r.status_code, 200)
        s = LeadCheckerSettings.load()
        self.assertTrue(s.auto_recheck)
        self.assertEqual(s.auto_recheck_batch, 40)

    def test_non_staff_denied(self):
        plain = User.objects.create_user("plain", password="x")
        c = DjangoClient()
        c.force_login(plain)
        r = c.post(reverse("management_checker_start_api"), {"scope": "unchecked"},
                   HTTP_HOST=HOST, secure=True)
        self.assertEqual(r.status_code, 403)


@MGMT
class CheckerPageTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user("boss2", password="x", is_staff=True)
        self.client = DjangoClient()
        self.client.force_login(self.staff)

    def test_leadops_page_renders_with_checker(self):
        # Чекер тепер вбудований у сторінку «Лідоген» (management_parsing).
        r = self.client.get(reverse("management_parsing"), HTTP_HOST=HOST, secure=True)
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"checker-endpoints", r.content)
        self.assertIn(b"leadops-nav", r.content)

    def test_checker_redirects_to_leadops(self):
        r = self.client.get(reverse("management_checker"), HTTP_HOST=HOST, secure=True)
        self.assertIn(r.status_code, (301, 302))

    def test_page_redirects_anon(self):
        c = DjangoClient()
        r = c.get(reverse("management_parsing"), HTTP_HOST=HOST, secure=True)
        self.assertIn(r.status_code, (302, 301))


@MGMT
class CheckerTabTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user("boss3", password="x", is_staff=True)
        self.client = DjangoClient()
        self.client.force_login(self.staff)

    def test_leadops_tab_present_for_staff(self):
        r = self.client.get(reverse("management_parsing"), HTTP_HOST=HOST, secure=True)
        self.assertEqual(r.status_code, 200)
        self.assertIn("Лідоген".encode(), r.content)
