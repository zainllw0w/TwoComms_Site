from unittest.mock import patch

from django.db import OperationalError
from django.contrib.auth import get_user_model
from django.test import Client, TransactionTestCase, override_settings
from django.urls import reverse

from management import parser_service, parser_usage, parsing_views


HOST = "management.twocomms.shop"


@override_settings(
    ROOT_URLCONF="twocomms.urls_management",
    ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1", HOST],
    SECURE_SSL_REDIRECT=False,
)
class ParserStatusDatabaseResilienceTests(TransactionTestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="parser_status_resilience",
            password="x",
            is_staff=True,
        )
        self.client = Client()
        self.client.force_login(self.user)

    def test_dashboard_job_does_not_repeat_mutating_normalization_after_disconnect(self):
        job = parser_service.LeadParsingJob.objects.create(
            created_by=self.user,
            status=parser_service.LeadParsingJob.Status.STOPPED,
            keywords_raw="військторг",
            cities_raw="Харків",
            keywords=["військторг"],
            cities=["Харків"],
            request_limit=10,
        )
        calls = 0

        def flaky_lock_loader():
            nonlocal calls
            calls += 1
            raise OperationalError(2006, "server has gone away")

        with patch.object(parser_service, "_runtime_lock_for_update", side_effect=flaky_lock_loader):
            result = parser_service.parser_dashboard_job()

        self.assertEqual(result.pk, job.pk)
        self.assertEqual(calls, 1)

    def test_status_api_retries_payload_read_after_disconnect(self):
        calls = 0

        def flaky_queue_payload(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise OperationalError(2006, "server has gone away")
            return [], []

        with patch.object(parsing_views, "_lead_queue_payload", side_effect=flaky_queue_payload), \
             patch.object(parsing_views, "_counters_payload", return_value={
                 "moderation": 0,
                 "base": 0,
                 "converted": 0,
                 "rejected": 0,
                 "unprocessed": 0,
             }):
            response = self.client.get(
                reverse("management_parser_status_api"),
                HTTP_HOST=HOST,
                secure=True,
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertEqual(calls, 2)

    def test_usage_retry_does_not_repeat_external_provider_call(self):
        provider_calls = 0
        aggregate_calls = 0
        snapshot = parser_usage.ParserUsageSnapshot(
            provider_status="local only",
            sku="Text Search Enterprise",
            field_mask_version="test",
            free_monthly_calls=1000,
            local_30d_usage=0,
            current_billing_month_usage=0,
            google_project_usage=None,
        )

        def provider_result():
            nonlocal provider_calls
            provider_calls += 1
            return "local only", None

        def flaky_base_snapshot(*, provider_status, google_project_usage):
            nonlocal aggregate_calls
            aggregate_calls += 1
            if aggregate_calls == 1:
                raise OperationalError(2006, "server has gone away")
            return snapshot

        with patch.object(
            parser_usage.GoogleProjectUsageProvider,
            "fetch_google_project_usage",
            side_effect=provider_result,
        ), patch.object(parser_usage, "_base_snapshot", side_effect=flaky_base_snapshot):
            result = parser_usage.parser_usage_snapshot()

        self.assertEqual(result, snapshot)
        self.assertEqual(provider_calls, 1)
        self.assertEqual(aggregate_calls, 2)

    def test_status_api_returns_retryable_json_after_second_disconnect(self):
        calls = 0

        def always_broken_queue_payload():
            nonlocal calls
            calls += 1
            raise OperationalError(2006, "server has gone away")

        with patch.object(parsing_views, "_lead_queue_payload", side_effect=always_broken_queue_payload):
            response = self.client.get(
                reverse("management_parser_status_api"),
                HTTP_HOST=HOST,
                secure=True,
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {
            "success": False,
            "retryable": True,
            "error": "Временно не вдалося отримати стан парсера. Спробуйте ще раз.",
        })
        self.assertEqual(calls, 2)

    def test_status_api_catches_disconnect_from_optional_usage_read(self):
        with patch.object(
            parsing_views,
            "_usage_payload",
            side_effect=OperationalError(2006, "server has gone away"),
        ):
            response = self.client.get(
                reverse("management_parser_status_api"),
                {"include_usage": "1"},
                HTTP_HOST=HOST,
                secure=True,
            )

        self.assertEqual(response.status_code, 503)
        self.assertTrue(response.json()["retryable"])
