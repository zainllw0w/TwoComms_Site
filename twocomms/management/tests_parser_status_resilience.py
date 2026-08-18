import json
from datetime import timedelta
from unittest.mock import patch

import MySQLdb
from django.db import OperationalError
from django.db.transaction import TransactionManagementError
from django.contrib.auth import get_user_model
from django.test import Client, RequestFactory, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils.functional import SimpleLazyObject
from django.utils import timezone

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

    def test_dashboard_job_poll_never_enters_mutating_normalization(self):
        job = parser_service.LeadParsingJob.objects.create(
            created_by=self.user,
            status=parser_service.LeadParsingJob.Status.STOPPED,
            keywords_raw="військторг",
            cities_raw="Харків",
            keywords=["військторг"],
            cities=["Харків"],
            request_limit=10,
        )
        with patch.object(parser_service, "_runtime_lock_for_update") as lock_loader:
            result = parser_service.parser_dashboard_job()

        self.assertEqual(result.pk, job.pk)
        lock_loader.assert_not_called()

    def test_dashboard_job_poll_does_not_write_runtime_lock(self):
        job = parser_service.LeadParsingJob.objects.create(
            created_by=self.user,
            status=parser_service.LeadParsingJob.Status.RUNNING,
            keywords_raw="військторг",
            cities_raw="Харків",
            keywords=["військторг"],
            cities=["Харків"],
            request_limit=10,
            heartbeat_at=timezone.now(),
        )
        lock = parser_service.LeadParsingRuntimeLock.objects.create(
            singleton_key=parser_service.RUNTIME_LOCK_KEY,
            active_job=job,
        )
        previous_updated_at = timezone.now() - timedelta(days=1)
        parser_service.LeadParsingRuntimeLock.objects.filter(pk=lock.pk).update(
            updated_at=previous_updated_at,
        )

        result = parser_service.parser_dashboard_job()

        lock.refresh_from_db()
        self.assertEqual(result.pk, job.pk)
        self.assertEqual(lock.updated_at, previous_updated_at)

    def test_dashboard_job_poll_reconciles_conflicting_active_jobs(self):
        older = parser_service.LeadParsingJob.objects.create(
            created_by=self.user,
            status=parser_service.LeadParsingJob.Status.RUNNING,
            keywords_raw="старий",
            cities_raw="Харків",
            keywords=["старий"],
            cities=["Харків"],
            request_limit=10,
            heartbeat_at=timezone.now(),
        )
        newer = parser_service.LeadParsingJob.objects.create(
            created_by=self.user,
            status=parser_service.LeadParsingJob.Status.RUNNING,
            keywords_raw="новий",
            cities_raw="Київ",
            keywords=["новий"],
            cities=["Київ"],
            request_limit=10,
            heartbeat_at=timezone.now(),
        )

        result = parser_service.parser_dashboard_job()

        older.refresh_from_db()
        newer.refresh_from_db()
        lock = parser_service.LeadParsingRuntimeLock.objects.get(
            singleton_key=parser_service.RUNTIME_LOCK_KEY
        )
        self.assertEqual(result.pk, newer.pk)
        self.assertEqual(older.status, parser_service.LeadParsingJob.Status.STOPPED)
        self.assertEqual(older.stop_reason_code, "session_superseded")
        self.assertEqual(lock.active_job_id, newer.pk)

    def test_dashboard_job_poll_reconciles_conflict_behind_active_lock(self):
        canonical = parser_service.LeadParsingJob.objects.create(
            created_by=self.user,
            status=parser_service.LeadParsingJob.Status.RUNNING,
            keywords_raw="основний",
            cities_raw="Харків",
            keywords=["основний"],
            cities=["Харків"],
            request_limit=10,
            heartbeat_at=timezone.now(),
        )
        conflicting = parser_service.LeadParsingJob.objects.create(
            created_by=self.user,
            status=parser_service.LeadParsingJob.Status.RUNNING,
            keywords_raw="конфліктний",
            cities_raw="Київ",
            keywords=["конфліктний"],
            cities=["Київ"],
            request_limit=10,
            heartbeat_at=timezone.now(),
        )
        lock = parser_service.LeadParsingRuntimeLock.objects.create(
            singleton_key=parser_service.RUNTIME_LOCK_KEY,
            active_job=canonical,
        )

        result = parser_service.parser_dashboard_job()

        canonical.refresh_from_db()
        conflicting.refresh_from_db()
        lock.refresh_from_db()
        self.assertEqual(result.pk, canonical.pk)
        self.assertEqual(canonical.status, parser_service.LeadParsingJob.Status.RUNNING)
        self.assertEqual(conflicting.status, parser_service.LeadParsingJob.Status.STOPPED)
        self.assertEqual(conflicting.stop_reason_code, "session_superseded")
        self.assertEqual(lock.active_job_id, canonical.pk)

    def test_dashboard_job_does_not_let_stale_lock_stop_fresh_active_job(self):
        stale_time = timezone.now() - parser_service.SESSION_STALE_AFTER - timedelta(minutes=1)
        stale = parser_service.LeadParsingJob.objects.create(
            created_by=self.user,
            status=parser_service.LeadParsingJob.Status.RUNNING,
            keywords_raw="застарілий",
            cities_raw="Харків",
            keywords=["застарілий"],
            cities=["Харків"],
            request_limit=10,
            heartbeat_at=stale_time,
        )
        fresh = parser_service.LeadParsingJob.objects.create(
            created_by=self.user,
            status=parser_service.LeadParsingJob.Status.RUNNING,
            keywords_raw="свіжий",
            cities_raw="Київ",
            keywords=["свіжий"],
            cities=["Київ"],
            request_limit=10,
            heartbeat_at=timezone.now(),
        )
        lock = parser_service.LeadParsingRuntimeLock.objects.create(
            singleton_key=parser_service.RUNTIME_LOCK_KEY,
            active_job=stale,
        )

        result = parser_service.parser_dashboard_job()

        stale.refresh_from_db()
        fresh.refresh_from_db()
        lock.refresh_from_db()
        self.assertEqual(result.pk, fresh.pk)
        self.assertEqual(stale.status, parser_service.LeadParsingJob.Status.STOPPED)
        self.assertEqual(stale.stop_reason_code, "session_superseded")
        self.assertEqual(fresh.status, parser_service.LeadParsingJob.Status.RUNNING)
        self.assertEqual(lock.active_job_id, fresh.pk)

    def test_dashboard_job_skips_reconciliation_after_competing_poll_repairs_state(self):
        job = parser_service.LeadParsingJob.objects.create(
            created_by=self.user,
            status=parser_service.LeadParsingJob.Status.RUNNING,
            keywords_raw="військторг",
            cities_raw="Харків",
            keywords=["військторг"],
            cities=["Харків"],
            request_limit=10,
            heartbeat_at=timezone.now(),
        )
        repaired_at = timezone.now() - timedelta(days=1)

        def competing_poll_repair():
            lock = parser_service.LeadParsingRuntimeLock.objects.create(
                singleton_key=parser_service.RUNTIME_LOCK_KEY,
                active_job=job,
            )
            parser_service.LeadParsingRuntimeLock.objects.filter(pk=lock.pk).update(
                updated_at=repaired_at,
            )
            lock.refresh_from_db()
            return lock

        with patch.object(
            parser_service,
            "_runtime_lock_for_update",
            side_effect=competing_poll_repair,
        ), patch.object(
            parser_service,
            "_normalize_active_jobs_locked",
            wraps=parser_service._normalize_active_jobs_locked,
        ) as normalize:
            result = parser_service.parser_dashboard_job()

        lock = parser_service.LeadParsingRuntimeLock.objects.get(
            singleton_key=parser_service.RUNTIME_LOCK_KEY
        )
        self.assertEqual(result.pk, job.pk)
        normalize.assert_not_called()
        self.assertEqual(lock.updated_at, repaired_at)

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

    def test_status_api_retries_disconnect_during_lazy_authentication(self):
        calls = 0

        def flaky_get_user(request):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise OperationalError(2006, "server has gone away")
            return self.user

        request = RequestFactory().get(
            reverse("management_parser_status_api"),
            HTTP_HOST=HOST,
        )
        request.user = SimpleLazyObject(lambda: flaky_get_user(request))

        with patch.object(
            parsing_views,
            "parser_dashboard_job",
            return_value=None,
        ), patch.object(
            parsing_views,
            "_lead_queue_payload",
            return_value=([], []),
        ), patch.object(
            parsing_views,
            "_counters_payload",
            return_value={
                "moderation": 0,
                "base": 0,
                "converted": 0,
                "rejected": 0,
                "unprocessed": 0,
            },
        ):
            response = parsing_views.parser_status_api(request)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(json.loads(response.content)["success"])
        self.assertEqual(calls, 2)

    def test_status_api_returns_retryable_json_after_lazy_auth_disconnect(self):
        request = RequestFactory().get(
            reverse("management_parser_status_api"),
            HTTP_HOST=HOST,
        )

        def broken_get_user(_request):
            raise OperationalError(2006, "server has gone away")

        request.user = SimpleLazyObject(lambda: broken_get_user(request))
        response = parsing_views.parser_status_api(request)

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response["Retry-After"], "1")
        self.assertTrue(json.loads(response.content)["retryable"])

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

    def test_status_api_returns_retryable_json_for_raw_driver_disconnect_context(self):
        raw_disconnect = MySQLdb.OperationalError(2006, "")
        transaction_error = TransactionManagementError("broken transaction")
        transaction_error.__cause__ = raw_disconnect

        with patch.object(
            parsing_views,
            "_lead_queue_payload",
            side_effect=transaction_error,
        ):
            response = self.client.get(
                reverse("management_parser_status_api"),
                HTTP_HOST=HOST,
                secure=True,
            )

        self.assertEqual(response.status_code, 503)
        self.assertTrue(response.json()["retryable"])

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
