from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client as DjangoClient
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Client, ClientFollowUp, LeadParsingJob, LeadParsingResult, ManagementLead, Report
from .parser_service import _places_search_text, create_parsing_job, parse_cities, parser_run_step
from .stats_service import compute_kpd, parse_stats_range
from .views import _close_followups_for_report, _sync_client_followup


class StatsRangeTests(TestCase):
    def test_parse_today_range(self):
        r = parse_stats_range({"period": "today"}, now=timezone.now())
        self.assertEqual(r.period, "today")
        self.assertEqual(r.start_date, timezone.localdate())
        self.assertEqual(r.end_date, timezone.localdate())
        self.assertLess(r.start, r.end)


class KpdTests(TestCase):
    def test_kpd_non_negative(self):
        cfg = {"kpd": {}, "advice": {}}
        metrics = {
            "active_seconds": 0,
            "points": 0,
            "processed": 0,
            "success_weighted": 0,
            "followups_total": 0,
            "followups_missed": 0,
            "cp_email_sent": 0,
            "shops_created": 0,
            "invoices_created": 0,
            "report_days_required": 0,
            "report_days_late": 0,
        }
        out = compute_kpd(metrics, cfg)
        self.assertGreaterEqual(out["value"], 0.0)

    def test_kpd_penalty_reduces_value(self):
        cfg = {"kpd": {}, "advice": {}}
        base = {
            "active_seconds": 3 * 3600,
            "points": 120,
            "processed": 30,
            "success_weighted": 10,
            "cp_email_sent": 2,
            "shops_created": 1,
            "invoices_created": 1,
            "report_days_required": 5,
            "report_days_late": 0,
        }
        ok = compute_kpd({**base, "followups_total": 10, "followups_missed": 0}, cfg)["value"]
        bad = compute_kpd({**base, "followups_total": 10, "followups_missed": 5}, cfg)["value"]
        self.assertGreater(ok, bad)


class FollowUpTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="mgr", password="x")

    def test_followup_created_and_closed(self):
        now = timezone.now()
        due = now + timedelta(hours=2)
        client = Client.objects.create(
            shop_name="S",
            phone="+380000000000",
            full_name="N",
            owner=self.user,
            next_call_at=due,
        )
        _sync_client_followup(client, None, client.next_call_at, now)

        fu = ClientFollowUp.objects.get(client=client, owner=self.user)
        self.assertEqual(fu.status, ClientFollowUp.Status.OPEN)

        # Clear next_call_at -> cancelled
        prev = client.next_call_at
        client.next_call_at = None
        client.save(update_fields=["next_call_at"])
        _sync_client_followup(client, prev, client.next_call_at, now + timedelta(minutes=5))

        fu.refresh_from_db()
        self.assertEqual(fu.status, ClientFollowUp.Status.CANCELLED)

    def test_followup_reschedule_vs_done(self):
        now = timezone.now()
        due = now + timedelta(hours=5)
        client = Client.objects.create(
            shop_name="S",
            phone="+380000000000",
            full_name="N",
            owner=self.user,
            next_call_at=due,
        )
        _sync_client_followup(client, None, client.next_call_at, now)
        fu = ClientFollowUp.objects.get(client=client, owner=self.user)

        # Reschedule before due -> rescheduled
        new_due = now + timedelta(hours=6)
        prev = client.next_call_at
        client.next_call_at = new_due
        client.save(update_fields=["next_call_at"])
        _sync_client_followup(client, prev, client.next_call_at, now + timedelta(minutes=10))
        fu.refresh_from_db()
        self.assertEqual(fu.status, ClientFollowUp.Status.RESCHEDULED)

        # New open followup exists
        self.assertTrue(
            ClientFollowUp.objects.filter(client=client, owner=self.user, status=ClientFollowUp.Status.OPEN).exists()
        )

        # Move after original due -> done
        open_fu = ClientFollowUp.objects.filter(client=client, owner=self.user, status=ClientFollowUp.Status.OPEN).first()
        later = timezone.now() + timedelta(hours=10)
        prev2 = client.next_call_at
        client.next_call_at = later
        client.save(update_fields=["next_call_at"])
        _sync_client_followup(client, prev2, client.next_call_at, now + timedelta(hours=7))
        open_fu.refresh_from_db()
        self.assertIn(open_fu.status, {ClientFollowUp.Status.DONE, ClientFollowUp.Status.RESCHEDULED})

    def test_followups_marked_missed_on_report(self):
        now = timezone.now()
        due = now + timedelta(hours=1)
        client = Client.objects.create(
            shop_name="S",
            phone="+380000000000",
            full_name="N",
            owner=self.user,
            next_call_at=due,
        )
        _sync_client_followup(client, None, client.next_call_at, now)

        report = Report.objects.create(owner=self.user, points=0, processed=0)
        _close_followups_for_report(report)

        fu = ClientFollowUp.objects.get(client=client, owner=self.user)
        self.assertEqual(fu.status, ClientFollowUp.Status.MISSED)
        self.assertEqual(fu.closed_by_report_id, report.id)


class ParserServiceTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="admin_mgr", password="x", is_staff=True)

    def test_parse_cities_keeps_single_city_phrase(self):
        self.assertEqual(parse_cities("Харків"), ["Харків"])
        self.assertEqual(parse_cities("Нью Йорк"), ["Нью Йорк"])
        self.assertEqual(parse_cities("Харків, Київ"), ["Харків", "Київ"])

    def test_parser_records_no_phone_results(self):
        job = create_parsing_job(user=self.user, keywords_raw="військторг", cities_raw="Харків", request_limit=3)
        fake_places = [
            {
                "id": "test-place-1",
                "displayName": {"text": "Магазин без номера"},
                "formattedAddress": "Харків",
            }
        ]
        with patch("management.parser_service.get_maps_api_key", return_value="x"), patch(
            "management.parser_service._places_search_text",
            return_value=(fake_places, ""),
        ):
            parser_run_step(job)

        job.refresh_from_db()
        self.assertEqual(job.no_phone_skipped, 1)
        self.assertEqual(job.added_to_moderation, 0)
        self.assertFalse(ManagementLead.objects.filter(parser_job=job).exists())
        result = LeadParsingResult.objects.filter(job=job).first()
        self.assertIsNotNone(result)
        self.assertEqual(result.status, LeadParsingResult.ResultStatus.NO_PHONE)

    def test_places_search_uses_configured_referer_headers(self):
        class DummyResponse:
            status_code = 200

            @staticmethod
            def json():
                return {"places": [], "nextPageToken": ""}

        with patch("management.parser_service.geocode_city_center", return_value=None), patch(
            "management.parser_service.get_maps_request_referer",
            return_value="https://management.twocomms.shop/",
        ), patch("management.parser_service.requests.post", return_value=DummyResponse()) as post_mock:
            places, next_page_token = _places_search_text(
                api_key="test-key",
                text_query="військторг Харків",
                city="Харків",
            )

        self.assertEqual(places, [])
        self.assertEqual(next_page_token, "")
        headers = post_mock.call_args.kwargs["headers"]
        self.assertEqual(headers.get("Referer"), "https://management.twocomms.shop/")
        self.assertEqual(headers.get("Origin"), "https://management.twocomms.shop")


@override_settings(
    ROOT_URLCONF="twocomms.urls_management",
    ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1", "management.twocomms.shop"],
)
class ParserApiTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="staff_user", password="x", is_staff=True)
        self.client_http = DjangoClient(enforce_csrf_checks=True)
        self.client_http.force_login(self.user)
        # Subdomain redirects in test environment can hide csrf cookie issuance.
        # Set a deterministic csrf cookie and use the same value in form/header.
        self.csrf = "a" * 32
        self.client_http.cookies["csrftoken"] = self.csrf

    def _post(self, url_name, data):
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

    def test_pause_endpoint_accepts_valid_csrf(self):
        job = LeadParsingJob.objects.create(
            created_by=self.user,
            status=LeadParsingJob.Status.RUNNING,
            keywords_raw="військторг",
            cities_raw="Харків",
            keywords=["військторг"],
            cities=["Харків"],
            request_limit=10,
        )
        response = self._post("management_parser_pause_api", {"job_id": str(job.id)})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload.get("success"))
        job.refresh_from_db()
        self.assertEqual(job.status, LeadParsingJob.Status.PAUSED)

    def test_start_step_resume_stop_flow_returns_json(self):
        start = self._post(
            "management_parser_start_api",
            {
                "keywords": "військторг",
                "cities": "Харків",
                "request_limit": "2",
            },
        )
        self.assertEqual(start.status_code, 200)
        start_payload = start.json()
        self.assertTrue(start_payload.get("success"))
        job_id = str(start_payload["job"]["id"])
        self.assertEqual(start_payload["job"]["status"], LeadParsingJob.Status.RUNNING)

        with patch("management.parsing_views.parser_run_step", side_effect=lambda j: j):
            step = self._post("management_parser_step_api", {"job_id": job_id})
        self.assertEqual(step.status_code, 200)
        self.assertTrue(step.json().get("success"))

        pause = self._post("management_parser_pause_api", {"job_id": job_id})
        self.assertEqual(pause.status_code, 200)
        self.assertEqual(pause.json()["job"]["status"], LeadParsingJob.Status.PAUSED)

        resume = self._post("management_parser_resume_api", {"job_id": job_id})
        self.assertEqual(resume.status_code, 200)
        self.assertEqual(resume.json()["job"]["status"], LeadParsingJob.Status.RUNNING)

        stop = self._post("management_parser_stop_api", {"job_id": job_id})
        self.assertEqual(stop.status_code, 200)
        self.assertEqual(stop.json()["job"]["status"], LeadParsingJob.Status.STOPPED)
