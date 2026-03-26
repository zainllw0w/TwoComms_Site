import os
from unittest.mock import patch

from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.test import Client as DjangoClient
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from management.models import LeadParsingJob
from management.parser_usage import GoogleProjectUsageProvider, ParserUsageSnapshot


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "twocomms-tests-parser-usage",
        }
    }
)
class ParserUsageProviderTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def test_google_provider_reports_project_missing(self):
        provider = GoogleProjectUsageProvider()

        with patch.dict(os.environ, {}, clear=True):
            status, usage = provider.fetch_google_project_usage()

        self.assertEqual(status, "local only · GOOGLE_CLOUD_PROJECT missing")
        self.assertIsNone(usage)

    def test_google_provider_reports_credentials_missing(self):
        provider = GoogleProjectUsageProvider()

        with patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "demo-project"}, clear=True):
            status, usage = provider.fetch_google_project_usage()

        self.assertEqual(status, "local only · Google Cloud credentials missing")
        self.assertIsNone(usage)

    def test_google_provider_uses_cache_to_avoid_repeated_external_calls(self):
        provider = GoogleProjectUsageProvider()

        with patch.dict(
            os.environ,
            {
                "GOOGLE_CLOUD_PROJECT": "demo-project",
                "GOOGLE_MONITORING_ACCESS_TOKEN": "demo-token",
            },
            clear=True,
        ), patch.object(provider, "_fetch_google_project_usage", return_value=321) as fetch_mock:
            first = provider.fetch_google_project_usage()
            second = provider.fetch_google_project_usage()

        self.assertEqual(first, ("connected via Cloud Monitoring", 321))
        self.assertEqual(second, ("connected via Cloud Monitoring", 321))
        fetch_mock.assert_called_once()


@override_settings(
    ROOT_URLCONF="twocomms.urls_management",
    ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1", "management.twocomms.shop"],
)
class ParserUsageApiTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="parser_usage_staff", password="x", is_staff=True)
        self.client_http = DjangoClient(enforce_csrf_checks=True)
        self.client_http.force_login(self.user)
        self.csrf = "b" * 32
        self.client_http.cookies["csrftoken"] = self.csrf

    def _post(self, url_name: str, data: dict):
        payload = dict(data)
        payload.setdefault("csrfmiddlewaretoken", self.csrf)
        return self.client_http.post(
            reverse(url_name),
            payload,
            HTTP_X_CSRFTOKEN=self.csrf,
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            HTTP_HOST="management.twocomms.shop",
            HTTP_REFERER="https://management.twocomms.shop/parsing/",
            secure=True,
        )

    def test_status_api_skips_usage_payload_without_include_usage_flag(self):
        with patch("management.parsing_views.parser_usage_snapshot") as usage_mock:
            response = self.client_http.get(
                reverse("management_parser_status_api"),
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
                HTTP_HOST="management.twocomms.shop",
                HTTP_REFERER="https://management.twocomms.shop/parsing/",
                secure=True,
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertNotIn("usage", response.json())
        usage_mock.assert_not_called()

    def test_status_api_includes_usage_payload_when_requested(self):
        snapshot = ParserUsageSnapshot(
            provider_status="connected",
            sku="Text Search Enterprise",
            field_mask_version="v-test",
            free_monthly_calls=1000,
            local_30d_usage=11,
            current_billing_month_usage=7,
            google_project_usage=22,
        )
        with patch("management.parsing_views.parser_usage_snapshot", return_value=snapshot) as usage_mock:
            response = self.client_http.get(
                f"{reverse('management_parser_status_api')}?include_usage=1",
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
                HTTP_HOST="management.twocomms.shop",
                HTTP_REFERER="https://management.twocomms.shop/parsing/",
                secure=True,
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["usage"]["google_project_usage"], 22)
        usage_mock.assert_called_once()

    def test_step_api_skips_usage_payload_by_default(self):
        job = LeadParsingJob.objects.create(
            created_by=self.user,
            status=LeadParsingJob.Status.RUNNING,
            keywords_raw="військторг",
            cities_raw="Одеса",
            keywords=["військторг"],
            cities=["Одеса"],
            request_limit=10,
            is_step_in_progress=True,
        )
        with patch("management.parsing_views.parser_usage_snapshot") as usage_mock:
            response = self._post("management_parser_step_api", {"job_id": str(job.id)})

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("usage", response.json())
        usage_mock.assert_not_called()
