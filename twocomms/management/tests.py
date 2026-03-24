from datetime import datetime, time, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client as DjangoClient
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Client, ClientFollowUp, LeadParsingJob, LeadParsingResult, ManagementLead, Report
from .parser_service import _places_search_text, create_parsing_job, parse_cities, parse_keywords, parser_run_step
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

    def _stable_now(self):
        return timezone.make_aware(datetime.combine(timezone.localdate(), time(hour=10, minute=0)))

    def test_followup_created_and_closed(self):
        now = self._stable_now()
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
        now = self._stable_now()
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
        later = self._stable_now() + timedelta(hours=10)
        prev2 = client.next_call_at
        client.next_call_at = later
        client.save(update_fields=["next_call_at"])
        _sync_client_followup(client, prev2, client.next_call_at, now + timedelta(hours=7))
        open_fu.refresh_from_db()
        self.assertIn(open_fu.status, {ClientFollowUp.Status.DONE, ClientFollowUp.Status.RESCHEDULED})

    def test_followups_marked_missed_on_report(self):
        now = self._stable_now()
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

    def test_followup_grace_window_and_effective_state(self):
        from management.services.followup_state import get_effective_callback_state

        now = self._stable_now()
        due = now - timedelta(minutes=30)
        client = Client.objects.create(
            shop_name="Grace Shop",
            phone="+380000000001",
            full_name="Owner",
            owner=self.user,
            next_call_at=due,
        )
        _sync_client_followup(client, None, client.next_call_at, now - timedelta(hours=1))

        followup = ClientFollowUp.objects.get(client=client, owner=self.user)
        self.assertEqual(followup.grace_until, due + timedelta(hours=2))

        state = get_effective_callback_state(client=client, now_dt=now)
        self.assertEqual(state.code, "due_now")

        followup.grace_until = now - timedelta(minutes=1)
        followup.save(update_fields=["grace_until"])
        state = get_effective_callback_state(client=client, now_dt=now)
        self.assertEqual(state.code, "missed")

        prev_due = client.next_call_at
        client.next_call_at = now + timedelta(days=1)
        client.save(update_fields=["next_call_at"])
        _sync_client_followup(client, prev_due, client.next_call_at, now + timedelta(minutes=5))

        state = get_effective_callback_state(client=client, now_dt=now + timedelta(minutes=5))
        self.assertEqual(state.code, "scheduled")


class ParserServiceTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="admin_mgr", password="x", is_staff=True)

    def test_parse_cities_keeps_single_city_phrase(self):
        self.assertEqual(parse_cities("Харків"), ["Харків"])
        self.assertEqual(parse_cities("Нью Йорк"), ["Нью Йорк"])
        self.assertEqual(parse_cities("Харків, Київ"), ["Харків", "Київ"])

    def test_parse_keywords_preserves_quoted_phrases_with_commas(self):
        self.assertEqual(
            parse_keywords('воєнторг, тактичний, "жіночий одяг, аксесуари"'),
            ["воєнторг", "тактичний", "жіночий одяг, аксесуари"],
        )

    def test_parse_keywords_keeps_space_separated_terms_and_drops_quotes(self):
        self.assertEqual(
            parse_keywords('Военторг "військове спорядження" Одяг'),
            ["Военторг", "військове спорядження", "Одяг"],
        )

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

    def test_parser_treats_same_job_page_repeat_as_technical_duplicate(self):
        job = create_parsing_job(user=self.user, keywords_raw="військторг", cities_raw="Харків", request_limit=3)
        fake_place = {
            "id": "repeat-place-1",
            "displayName": {"text": "Повторюваний магазин"},
            "internationalPhoneNumber": "+380671112233",
            "formattedAddress": "Харків",
        }
        with patch("management.parser_service.get_maps_api_key", return_value="x"), patch(
            "management.parser_service._places_search_text",
            side_effect=[([fake_place], "next-token"), ([fake_place], "")],
        ):
            parser_run_step(job)
            job.refresh_from_db()
            job.next_step_not_before = timezone.now() - timedelta(seconds=1)
            job.save(update_fields=["next_step_not_before"])
            parser_run_step(job)

        job.refresh_from_db()
        self.assertEqual(job.added_to_moderation, 1)
        self.assertEqual(job.duplicate_skipped, 1)
        self.assertEqual(job.duplicate_same_job_place_skipped, 1)
        self.assertEqual(job.request_count, 2)

    def test_parser_blocks_existing_client_by_exact_phone(self):
        Client.objects.create(
            shop_name="Існуючий клієнт",
            phone="+380671112233",
            full_name="Owner",
            owner=self.user,
        )
        job = create_parsing_job(user=self.user, keywords_raw="військторг", cities_raw="Харків", request_limit=3)
        fake_place = {
            "id": "client-dup-place",
            "displayName": {"text": "Новий магазин"},
            "internationalPhoneNumber": "+380671112233",
            "formattedAddress": "Харків",
        }
        with patch("management.parser_service.get_maps_api_key", return_value="x"), patch(
            "management.parser_service._places_search_text",
            return_value=([fake_place], ""),
        ):
            parser_run_step(job)

        job.refresh_from_db()
        self.assertEqual(job.duplicate_existing_client_skipped, 1)
        self.assertEqual(job.duplicate_skipped, 1)
        self.assertFalse(ManagementLead.objects.filter(parser_job=job).exists())

    def test_parser_does_not_treat_global_place_id_match_as_business_duplicate(self):
        ManagementLead.objects.create(
            shop_name="Старий лід",
            phone="+380501112233",
            full_name="Owner",
            google_place_id="shared-place-id",
            status=ManagementLead.Status.BASE,
            added_by=self.user,
        )
        job = create_parsing_job(user=self.user, keywords_raw="військторг", cities_raw="Харків", request_limit=3)
        fake_place = {
            "id": "shared-place-id",
            "displayName": {"text": "Новий магазин"},
            "internationalPhoneNumber": "+380671112233",
            "formattedAddress": "Харків",
        }
        with patch("management.parser_service.get_maps_api_key", return_value="x"), patch(
            "management.parser_service._places_search_text",
            return_value=([fake_place], ""),
        ):
            parser_run_step(job)

        job.refresh_from_db()
        self.assertEqual(job.added_to_moderation, 1)
        self.assertEqual(job.duplicate_skipped, 0)
        self.assertTrue(ManagementLead.objects.filter(parser_job=job, phone="+380671112233").exists())

    def test_parser_marks_rejected_history_by_exact_phone(self):
        ManagementLead.objects.create(
            shop_name="Відхилений лід",
            phone="+380671112233",
            full_name="Owner",
            status=ManagementLead.Status.REJECTED,
            added_by=self.user,
        )
        job = create_parsing_job(user=self.user, keywords_raw="військторг", cities_raw="Харків", request_limit=3)
        fake_place = {
            "id": "rejected-dup-place",
            "displayName": {"text": "Новий магазин"},
            "internationalPhoneNumber": "+380671112233",
            "formattedAddress": "Харків",
        }
        with patch("management.parser_service.get_maps_api_key", return_value="x"), patch(
            "management.parser_service._places_search_text",
            return_value=([fake_place], ""),
        ):
            parser_run_step(job)

        job.refresh_from_db()
        self.assertEqual(job.already_rejected_skipped, 1)
        self.assertEqual(job.duplicate_skipped, 0)

    def test_invalid_page_token_is_bounded_and_does_not_stick_forever(self):
        from management.parser_service import ParsingServiceError

        job = create_parsing_job(user=self.user, keywords_raw="військторг", cities_raw="Харків", request_limit=5)
        job.next_page_token = "bad-token"
        job.save(update_fields=["next_page_token"])

        with patch("management.parser_service.get_maps_api_key", return_value="x"), patch(
            "management.parser_service._places_search_text",
            side_effect=ParsingServiceError("Google Places API помилка (400): page token invalid"),
        ):
            parser_run_step(job)
            job.refresh_from_db()
            self.assertEqual(job.status, LeadParsingJob.Status.RUNNING)
            self.assertEqual(job.request_count, 1)
            self.assertTrue(job.next_page_token)

            job.next_step_not_before = timezone.now() - timedelta(seconds=1)
            job.save(update_fields=["next_step_not_before"])
            parser_run_step(job)
            job.refresh_from_db()
            self.assertEqual(job.status, LeadParsingJob.Status.RUNNING)
            self.assertEqual(job.request_count, 2)
            self.assertTrue(job.next_page_token)

            job.next_step_not_before = timezone.now() - timedelta(seconds=1)
            job.save(update_fields=["next_step_not_before"])
            parser_run_step(job)

        job.refresh_from_db()
        self.assertNotEqual(job.status, LeadParsingJob.Status.RUNNING)
        self.assertEqual(job.request_count, 3)
        self.assertEqual(job.next_page_token, "")
        self.assertFalse(job.is_step_in_progress)
        self.assertTrue(LeadParsingResult.objects.filter(job=job, status=LeadParsingResult.ResultStatus.ERROR).exists())

    def test_parser_counts_page_token_errors_as_requests(self):
        job = create_parsing_job(user=self.user, keywords_raw="військторг", cities_raw="Харків", request_limit=5)
        job.next_page_token = "bad-token"
        job.save(update_fields=["next_page_token"])

        from management.parser_service import ParsingServiceError

        with patch("management.parser_service.get_maps_api_key", return_value="x"), patch(
            "management.parser_service._places_search_text",
            side_effect=ParsingServiceError("Google Places API помилка (400): page token invalid"),
        ):
            parser_run_step(job)

        job.refresh_from_db()
        self.assertEqual(job.request_count, 1)
        self.assertGreaterEqual(job.request_error_count, 1)

    def test_unexpected_parser_exception_releases_lock_and_fails_job(self):
        job = create_parsing_job(user=self.user, keywords_raw="військторг", cities_raw="Харків", request_limit=5)

        with patch("management.parser_service.get_maps_api_key", return_value="x"), patch(
            "management.parser_service._places_search_text",
            side_effect=RuntimeError("boom"),
        ):
            parser_run_step(job)

        job.refresh_from_db()
        self.assertEqual(job.status, LeadParsingJob.Status.FAILED)
        self.assertFalse(job.is_step_in_progress)
        self.assertEqual(job.request_count, 1)
        self.assertIn("Непередбачена помилка парсингу", job.last_error)


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
                "requests_per_minute": "20",
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

    def test_start_rejects_second_active_job(self):
        LeadParsingJob.objects.create(
            created_by=self.user,
            status=LeadParsingJob.Status.RUNNING,
            keywords_raw="військторг",
            cities_raw="Харків",
            keywords=["військторг"],
            cities=["Харків"],
            request_limit=10,
        )
        response = self._post(
            "management_parser_start_api",
            {
                "keywords": "одяг",
                "cities": "Київ",
                "request_limit": "2",
                "requests_per_minute": "20",
            },
        )
        self.assertEqual(response.status_code, 409)
        payload = response.json()
        self.assertFalse(payload["success"])
        self.assertIn("вже є активна", payload["error"].lower())

    def test_step_api_does_not_run_second_step_while_first_is_in_progress(self):
        job = LeadParsingJob.objects.create(
            created_by=self.user,
            status=LeadParsingJob.Status.RUNNING,
            keywords_raw="військторг",
            cities_raw="Харків",
            keywords=["військторг"],
            cities=["Харків"],
            request_limit=10,
            is_step_in_progress=True,
            last_step_started_at=timezone.now(),
        )
        with patch("management.parsing_views.parser_run_step") as step_mock:
            response = self._post("management_parser_step_api", {"job_id": str(job.id)})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        step_mock.assert_not_called()

    def test_step_api_respects_next_step_not_before(self):
        job = LeadParsingJob.objects.create(
            created_by=self.user,
            status=LeadParsingJob.Status.RUNNING,
            keywords_raw="військторг",
            cities_raw="Харків",
            keywords=["військторг"],
            cities=["Харків"],
            request_limit=10,
            next_step_not_before=timezone.now() + timedelta(seconds=10),
        )
        with patch("management.parsing_views.parser_run_step") as step_mock:
            response = self._post("management_parser_step_api", {"job_id": str(job.id)})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        step_mock.assert_not_called()


class ParserRecoveryDryRunCommandTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="recovery_admin", password="x", is_staff=True)

    def test_command_reports_candidates_that_are_clear_by_exact_phone(self):
        job = LeadParsingJob.objects.create(
            created_by=self.user,
            status=LeadParsingJob.Status.COMPLETED,
            keywords_raw="військторг",
            cities_raw="Харків",
            keywords=["військторг"],
            cities=["Харків"],
            request_limit=10,
        )
        LeadParsingResult.objects.create(
            job=job,
            status=LeadParsingResult.ResultStatus.DUPLICATE,
            reason="Старий змішаний дубль",
            reason_code="legacy_duplicate",
            phone="+380671112233",
            place_name="Пропущений магазин",
            query="військторг Харків",
        )

        from io import StringIO

        out = StringIO()
        call_command("parser_recovery_dry_run", "--json", stdout=out)
        payload = out.getvalue()
        self.assertIn("Пропущений магазин", payload)
        self.assertIn("+380671112233", payload)

    def test_command_respects_scan_limit(self):
        job = LeadParsingJob.objects.create(
            created_by=self.user,
            status=LeadParsingJob.Status.COMPLETED,
            keywords_raw="військторг",
            cities_raw="Харків",
            keywords=["військторг"],
            cities=["Харків"],
            request_limit=10,
        )
        for idx in range(3):
            LeadParsingResult.objects.create(
                job=job,
                status=LeadParsingResult.ResultStatus.DUPLICATE,
                reason="Старий змішаний дубль",
                reason_code="legacy_duplicate",
                phone=f"+38067111223{idx}",
                place_name=f"Пропущений магазин {idx}",
                query="військторг Харків",
            )

        from io import StringIO

        out = StringIO()
        call_command("parser_recovery_dry_run", "--json", "--scan-limit", "1", stdout=out)
        payload = out.getvalue()
        self.assertIn('"scan_limit": 1', payload)
        self.assertIn('"scanned_count": 1', payload)
        self.assertIn('"truncated": true', payload)
