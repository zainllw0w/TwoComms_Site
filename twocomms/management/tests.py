from datetime import datetime, time, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.test import RequestFactory
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import (
    Client,
    ClientFollowUp,
    ClientInteractionAttempt,
    LeadParsingJob,
    LeadParsingQueryState,
    LeadParsingResult,
    ManagementLead,
    Report,
)
from .parser_service import _places_search_text, create_parsing_job, parse_cities, parse_keywords, parser_run_step
from .services.analytics_v7 import materialize_manager_day_fact
from .services.client_entry import record_client_interaction
from .services.snapshots import build_daily_stats_range, persist_nightly_snapshot
from .stats_service import compute_kpd, get_stats_payload, parse_stats_range
from .views import _close_followups_for_report, _sync_client_followup, send_report
from .models import ClientStageEvent, FollowUpEvent, ManagerDayFact, ManagerDayStatus, ReasonSignal, VerifiedWorkEvent


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

    def test_followups_remain_open_when_report_helper_runs(self):
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
        self.assertEqual(fu.status, ClientFollowUp.Status.OPEN)
        self.assertIsNone(fu.closed_by_report_id)

    @override_settings(ROOT_URLCONF="twocomms.urls_management", SECURE_SSL_REDIRECT=False)
    @patch("management.views.send_telegram_report")
    @patch("management.views.build_report_excel", return_value=b"excel")
    @patch("management.views.get_user_stats", return_value={"points_today": 0, "processed_today": 0})
    def test_send_report_does_not_mutate_open_followups(self, _mock_stats, _mock_excel, _mock_telegram):
        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])
        request_factory = RequestFactory()

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

        request = request_factory.post(reverse("management_send_report"))
        request.user = self.user
        response = send_report(request)

        self.assertIn(response.status_code, {301, 302})
        fu = ClientFollowUp.objects.get(client=client, owner=self.user)
        self.assertEqual(fu.status, ClientFollowUp.Status.OPEN)
        self.assertIsNone(fu.closed_by_report_id)
        self.assertEqual(Report.objects.filter(owner=self.user).count(), 1)

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
        cache.clear()

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

    def test_parse_keywords_dedupes_case_insensitive_values(self):
        self.assertEqual(
            parse_keywords('військторг, ВІЙСЬКТОРГ, "Тактичний одяг", "тактичний одяг"'),
            ["військторг", "Тактичний одяг"],
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

    def test_parser_saves_no_phone_place_with_website_when_enabled(self):
        job = create_parsing_job(
            user=self.user,
            keywords_raw="військторг",
            cities_raw="Харків",
            request_limit=3,
            save_no_phone_leads=True,
        )
        fake_places = [
            {
                "id": "test-place-website-no-phone",
                "displayName": {"text": "Магазин із сайтом"},
                "formattedAddress": "Харків",
                "websiteUri": "https://alpha.example.com",
            }
        ]
        with patch("management.parser_service.get_maps_api_key", return_value="x"), patch(
            "management.parser_service._places_search_text",
            return_value=(fake_places, ""),
        ):
            parser_run_step(job)

        job.refresh_from_db()
        self.assertEqual(job.no_phone_skipped, 0)
        self.assertEqual(job.saved_no_phone_to_moderation, 1)
        lead = ManagementLead.objects.get(parser_job=job)
        self.assertEqual(lead.status, ManagementLead.Status.MODERATION)
        self.assertTrue(lead.requires_phone_completion)
        self.assertEqual(lead.website_url, "https://alpha.example.com")
        result = LeadParsingResult.objects.filter(job=job).first()
        self.assertEqual(result.status, LeadParsingResult.ResultStatus.ADDED_NO_PHONE)

    def test_parser_does_not_save_no_phone_place_without_website_even_when_enabled(self):
        job = create_parsing_job(
            user=self.user,
            keywords_raw="військторг",
            cities_raw="Харків",
            request_limit=3,
            save_no_phone_leads=True,
        )
        fake_places = [
            {
                "id": "test-place-no-phone-no-website",
                "displayName": {"text": "Магазин без контактів"},
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
        self.assertEqual(job.saved_no_phone_to_moderation, 0)
        self.assertFalse(ManagementLead.objects.filter(parser_job=job).exists())

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

    def test_places_search_includes_region_and_type_filters(self):
        class DummyResponse:
            status_code = 200

            @staticmethod
            def json():
                return {"places": [], "nextPageToken": ""}

        request_spec = {
            "text_query": "військторг Харків",
            "keyword": "військторг",
            "city": "Харків",
            "included_type": "clothing_store",
            "strict_type_filtering": True,
        }

        with patch("management.parser_service.geocode_city_center", return_value=None), patch(
            "management.parser_service.requests.post",
            return_value=DummyResponse(),
        ) as post_mock:
            _places_search_text(
                api_key="test-key",
                text_query="військторг Харків",
                city="Харків",
                request_spec=request_spec,
            )

        kwargs = post_mock.call_args.kwargs
        self.assertIn("places.types", kwargs["headers"]["X-Goog-FieldMask"])
        self.assertEqual(kwargs["json"]["regionCode"], "UA")
        self.assertEqual(kwargs["json"]["includedType"], "clothing_store")
        self.assertTrue(kwargs["json"]["strictTypeFiltering"])

    def test_parser_runs_selected_types_sequentially_for_same_query(self):
        job = create_parsing_job(
            user=self.user,
            keywords_raw="військторг",
            cities_raw="Харків",
            request_limit=3,
            included_types=["clothing_store", "shoe_store"],
            strict_type_filtering=True,
        )
        requested_types = []

        def fake_places_search(*args, **kwargs):
            request_spec = kwargs.get("request_spec") or {}
            requested_types.append(request_spec.get("included_type"))
            return [], ""

        with patch("management.parser_service.get_maps_api_key", return_value="x"), patch(
            "management.parser_service._places_search_text",
            side_effect=fake_places_search,
        ):
            parser_run_step(job)

        job.refresh_from_db()
        self.assertEqual(requested_types, ["clothing_store"])
        self.assertEqual(job.status, LeadParsingJob.Status.RUNNING)
        self.assertEqual(job.request_count, 1)
        self.assertEqual(job.current_type_index, 1)
        self.assertEqual(job.included_type, "shoe_store")
        self.assertEqual(job.current_query, "військторг Харків")

        job.next_step_not_before = timezone.now() - timedelta(seconds=1)
        job.save(update_fields=["next_step_not_before"])

        with patch("management.parser_service.get_maps_api_key", return_value="x"), patch(
            "management.parser_service._places_search_text",
            side_effect=fake_places_search,
        ):
            parser_run_step(job)

        job.refresh_from_db()
        self.assertEqual(requested_types, ["clothing_store", "shoe_store"])
        self.assertEqual(job.status, LeadParsingJob.Status.COMPLETED)
        self.assertEqual(job.request_count, 2)
        self.assertEqual(job.current_request_spec, {})

    def test_parser_marks_query_exhausted_and_moves_to_next_city(self):
        job = create_parsing_job(
            user=self.user,
            keywords_raw="військторг",
            cities_raw="Харків, Київ",
            request_limit=5,
        )
        fake_place = {
            "id": "kyiv-place-1",
            "displayName": {"text": "Київський магазин"},
            "internationalPhoneNumber": "+380671112233",
            "formattedAddress": "Київ",
        }

        with patch("management.parser_service.get_maps_api_key", return_value="x"), patch(
            "management.parser_service._places_search_text",
            side_effect=[([], ""), ([fake_place], "")],
        ):
            parser_run_step(job)
            job.refresh_from_db()
            self.assertEqual(job.status, LeadParsingJob.Status.RUNNING)
            self.assertEqual(job.queries_exhausted_normal, 1)
            self.assertEqual(job.current_city_index, 1)
            query_state = LeadParsingQueryState.objects.get(job=job, keyword="військторг", city="Харків", included_type="")
            self.assertEqual(query_state.status, LeadParsingQueryState.Status.EXHAUSTED)
            self.assertTrue(
                LeadParsingResult.objects.filter(
                    job=job,
                    status=LeadParsingResult.ResultStatus.NOTICE,
                    reason_code="query_exhausted_no_more_results",
                ).exists()
            )

            job.next_step_not_before = timezone.now() - timedelta(seconds=1)
            job.save(update_fields=["next_step_not_before"])
            parser_run_step(job)

        job.refresh_from_db()
        self.assertEqual(job.added_to_moderation, 1)
        self.assertEqual(job.status, LeadParsingJob.Status.COMPLETED)

    def test_parser_skips_previously_exhausted_query_without_new_api_call(self):
        job = create_parsing_job(
            user=self.user,
            keywords_raw="військторг",
            cities_raw="Харків, Київ",
            request_limit=5,
        )
        LeadParsingQueryState.objects.create(
            job=job,
            keyword="військторг",
            city="Харків",
            included_type="",
            text_query="військторг Харків",
            status=LeadParsingQueryState.Status.EXHAUSTED,
            exhausted_reason_code="query_exhausted_no_more_results",
            exhausted_message="Харків уже було вичерпано раніше.",
        )

        with patch("management.parser_service.get_maps_api_key", return_value="x"), patch(
            "management.parser_service._places_search_text",
        ) as places_mock:
            parser_run_step(job)

        job.refresh_from_db()
        places_mock.assert_not_called()
        self.assertEqual(job.request_count, 0)
        self.assertEqual(job.current_city_index, 1)
        self.assertTrue(
            LeadParsingResult.objects.filter(
                job=job,
                status=LeadParsingResult.ResultStatus.NOTICE,
                reason_code="query_exhausted_cached_skip",
            ).exists()
        )

    def test_parser_stops_on_repeated_google_page_for_same_query(self):
        job = create_parsing_job(user=self.user, keywords_raw="військторг", cities_raw="Харків", request_limit=10)
        fake_place = {
            "id": "loop-place-1",
            "displayName": {"text": "Loop Store"},
            "internationalPhoneNumber": "+380671112233",
            "formattedAddress": "Харків",
        }

        with patch("management.parser_service.get_maps_api_key", return_value="x"), patch(
            "management.parser_service._places_search_text",
            side_effect=[([fake_place], "loop-token"), ([fake_place], "loop-token")],
        ):
            parser_run_step(job)
            job.refresh_from_db()
            job.next_step_not_before = timezone.now() - timedelta(seconds=1)
            job.save(update_fields=["next_step_not_before"])
            parser_run_step(job)

        job.refresh_from_db()
        self.assertEqual(job.status, LeadParsingJob.Status.STOPPED)
        self.assertEqual(job.stop_reason_code, "query_exhausted_repeated_page")
        self.assertEqual(job.queries_exhausted_anomaly, 1)
        query_state = LeadParsingQueryState.objects.get(job=job, keyword="військторг", city="Харків", included_type="")
        self.assertEqual(query_state.status, LeadParsingQueryState.Status.ANOMALY)

    def test_parser_stops_on_repeated_google_page_even_if_token_changes(self):
        job = create_parsing_job(user=self.user, keywords_raw="військторг", cities_raw="Харків", request_limit=10)
        fake_place = {
            "id": "loop-place-1",
            "displayName": {"text": "Loop Store"},
            "internationalPhoneNumber": "+380671112233",
            "formattedAddress": "Харків",
        }

        with patch("management.parser_service.get_maps_api_key", return_value="x"), patch(
            "management.parser_service._places_search_text",
            side_effect=[([fake_place], "loop-token-1"), ([fake_place], "loop-token-2")],
        ):
            parser_run_step(job)
            job.refresh_from_db()
            job.next_step_not_before = timezone.now() - timedelta(seconds=1)
            job.save(update_fields=["next_step_not_before"])
            parser_run_step(job)

        job.refresh_from_db()
        self.assertEqual(job.status, LeadParsingJob.Status.STOPPED)
        self.assertEqual(job.stop_reason_code, "query_exhausted_repeated_page")
        self.assertEqual(job.queries_exhausted_anomaly, 1)

    def test_parser_completes_when_target_leads_limit_reached(self):
        job = create_parsing_job(
            user=self.user,
            keywords_raw="військторг",
            cities_raw="Харків",
            request_limit=10,
            target_leads_limit=1,
        )
        fake_place = {
            "id": "target-place-1",
            "displayName": {"text": "Target Store"},
            "internationalPhoneNumber": "+380671112233",
            "formattedAddress": "Харків",
        }

        with patch("management.parser_service.get_maps_api_key", return_value="x"), patch(
            "management.parser_service._places_search_text",
            return_value=([fake_place], "next-token"),
        ):
            parser_run_step(job)

        job.refresh_from_db()
        self.assertEqual(job.status, LeadParsingJob.Status.COMPLETED)
        self.assertEqual(job.stop_reason_code, "target_leads_reached")
        self.assertEqual(job.target_leads_limit, 1)
        self.assertEqual(job.added_to_moderation, 1)

    def test_geocode_city_center_uses_shared_django_cache(self):
        class DummyResponse:
            status_code = 200

            @staticmethod
            def json():
                return {
                    "status": "OK",
                    "results": [
                        {
                            "geometry": {
                                "location": {"lat": 49.99, "lng": 36.23},
                            }
                        }
                    ],
                }

        with patch("management.parser_service.requests.get", return_value=DummyResponse()) as get_mock:
            from management.parser_service import geocode_city_center

            first = geocode_city_center("Харків", "test-key")
            second = geocode_city_center("Харків", "test-key")

        self.assertEqual(first, second)
        self.assertEqual(get_mock.call_count, 1)

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

    def test_history_lookback_zero_skips_existing_client_check(self):
        Client.objects.create(
            shop_name="Існуючий клієнт",
            phone="+380671112233",
            full_name="Owner",
            owner=self.user,
        )
        job = create_parsing_job(
            user=self.user,
            keywords_raw="військторг",
            cities_raw="Харків",
            request_limit=3,
            history_lookback_days=0,
        )
        fake_place = {
            "id": "client-dup-place-allowed",
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
        self.assertEqual(job.duplicate_existing_client_skipped, 0)

    def test_parser_does_not_treat_global_place_id_match_as_business_duplicate(self):
        ManagementLead.objects.create(
            shop_name="Старий лід",
            phone="+380501112233",
            full_name="Owner",
            google_place_id="shared-place-id",
            status=ManagementLead.Status.BASE,
            added_by=self.user,
        )
        job = create_parsing_job(
            user=self.user,
            keywords_raw="військторг",
            cities_raw="Харків",
            request_limit=3,
            history_lookback_days=0,
        )
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

    def test_recent_history_place_is_suppressed_when_within_lookback(self):
        existing = ManagementLead.objects.create(
            shop_name="Старий лід",
            phone="+380501112233",
            full_name="Owner",
            google_place_id="shared-place-id",
            status=ManagementLead.Status.BASE,
            added_by=self.user,
        )
        ManagementLead.objects.filter(id=existing.id).update(created_at=timezone.now())
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
        self.assertEqual(job.recent_history_place_skipped, 1)
        self.assertEqual(job.added_to_moderation, 0)

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

    def test_places_search_uses_location_restriction_when_viewport_available(self):
        class DummyResponse:
            status_code = 200

            @staticmethod
            def json():
                return {"places": [], "nextPageToken": ""}

        viewport = {
            "latitude": 49.99,
            "longitude": 36.23,
            "viewport": {
                "low": {"latitude": 49.9, "longitude": 36.1},
                "high": {"latitude": 50.1, "longitude": 36.4},
            },
        }

        with patch("management.parser_service.geocode_city_center", return_value=viewport), patch(
            "management.parser_service.requests.post",
            return_value=DummyResponse(),
        ) as post_mock:
            _places_search_text(
                api_key="test-key",
                text_query="військторг Харків",
                city="Харків",
            )

        body = post_mock.call_args.kwargs["json"]
        self.assertIn("locationRestriction", body)
        self.assertNotIn("locationBias", body)

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

    def _post_path(self, path, data):
        payload = dict(data)
        payload.setdefault("csrfmiddlewaretoken", self.csrf)
        return self.client_http.post(
            path,
            payload,
            HTTP_X_CSRFTOKEN=self.csrf,
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            HTTP_HOST="management.twocomms.shop",
            HTTP_REFERER="https://management.twocomms.shop/parsing/",
            secure=True,
        )

    def _post(self, url_name, data, *args):
        return self._post_path(reverse(url_name, args=args), data)

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
                "target_leads_limit": "7",
                "requests_per_minute": "20",
                "history_lookback_days": "45",
                "save_no_phone_leads": "on",
                "included_types": ["clothing_store", "shoe_store"],
                "strict_type_filtering": "on",
            },
        )
        self.assertEqual(start.status_code, 200)
        start_payload = start.json()
        self.assertTrue(start_payload.get("success"))
        job_id = str(start_payload["job"]["id"])
        self.assertEqual(start_payload["job"]["status"], LeadParsingJob.Status.RUNNING)
        job = LeadParsingJob.objects.get(id=job_id)
        self.assertEqual(job.history_lookback_days, 45)
        self.assertTrue(job.save_no_phone_leads)
        self.assertEqual(job.included_types, ["clothing_store", "shoe_store"])
        self.assertEqual(job.included_type, "clothing_store")
        self.assertEqual(job.current_type_index, 0)
        self.assertTrue(job.strict_type_filtering)
        self.assertEqual(job.target_leads_limit, 7)

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

    def test_start_rejects_when_paused_job_exists_and_returns_that_job(self):
        paused_job = LeadParsingJob.objects.create(
            created_by=self.user,
            status=LeadParsingJob.Status.PAUSED,
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
                "requests_per_minute": "10",
                "history_lookback_days": "30",
            },
        )
        self.assertEqual(response.status_code, 409)
        payload = response.json()
        self.assertEqual(payload["job"]["id"], paused_job.id)
        self.assertEqual(payload["job"]["status"], LeadParsingJob.Status.PAUSED)

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

    def test_status_api_stops_stale_running_job(self):
        stale_time = timezone.now() - timedelta(minutes=10)
        job = LeadParsingJob.objects.create(
            created_by=self.user,
            status=LeadParsingJob.Status.RUNNING,
            keywords_raw="військторг",
            cities_raw="Харків",
            keywords=["військторг"],
            cities=["Харків"],
            request_limit=10,
            heartbeat_at=stale_time,
        )
        response = self.client_http.get(
            reverse("management_parser_status_api"),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            HTTP_HOST="management.twocomms.shop",
            HTTP_REFERER="https://management.twocomms.shop/parsing/",
            secure=True,
        )
        self.assertEqual(response.status_code, 200)
        job.refresh_from_db()
        self.assertEqual(job.status, LeadParsingJob.Status.STOPPED)
        self.assertEqual(job.stop_reason_code, "session_stale_stopped")

    def test_status_api_keeps_recent_running_job_alive_within_extended_timeout(self):
        fresh_time = timezone.now() - timedelta(minutes=4)
        job = LeadParsingJob.objects.create(
            created_by=self.user,
            status=LeadParsingJob.Status.RUNNING,
            keywords_raw="військторг",
            cities_raw="Харків",
            keywords=["військторг"],
            cities=["Харків"],
            request_limit=10,
            heartbeat_at=fresh_time,
        )
        response = self.client_http.get(
            reverse("management_parser_status_api"),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            HTTP_HOST="management.twocomms.shop",
            HTTP_REFERER="https://management.twocomms.shop/parsing/",
            secure=True,
        )
        self.assertEqual(response.status_code, 200)
        job.refresh_from_db()
        self.assertEqual(job.status, LeadParsingJob.Status.RUNNING)

    def test_status_api_does_not_refresh_running_heartbeat(self):
        fresh_time = timezone.now() - timedelta(minutes=4)
        job = LeadParsingJob.objects.create(
            created_by=self.user,
            status=LeadParsingJob.Status.RUNNING,
            keywords_raw="військторг",
            cities_raw="Харків",
            keywords=["військторг"],
            cities=["Харків"],
            request_limit=10,
            heartbeat_at=fresh_time,
        )
        response = self.client_http.get(
            reverse("management_parser_status_api"),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            HTTP_HOST="management.twocomms.shop",
            HTTP_REFERER="https://management.twocomms.shop/parsing/",
            secure=True,
        )
        self.assertEqual(response.status_code, 200)
        job.refresh_from_db()
        self.assertEqual(job.heartbeat_at, fresh_time)

    def test_stop_api_defaults_to_user_stop(self):
        job = LeadParsingJob.objects.create(
            created_by=self.user,
            status=LeadParsingJob.Status.RUNNING,
            keywords_raw="військторг",
            cities_raw="Харків",
            keywords=["військторг"],
            cities=["Харків"],
            request_limit=10,
        )
        response = self._post(
            "management_parser_stop_api",
            {"job_id": str(job.id)},
        )
        self.assertEqual(response.status_code, 200)
        job.refresh_from_db()
        self.assertEqual(job.status, LeadParsingJob.Status.STOPPED)
        self.assertEqual(job.stop_reason_code, "user_stop")

    def test_parsing_dashboard_script_no_longer_contains_unload_stop_hooks(self):
        response = self.client_http.get(
            reverse("management_parsing_dashboard"),
            HTTP_HOST="management.twocomms.shop",
            secure=True,
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertNotIn("sendUnloadStop", content)
        self.assertNotIn("browser_unload_stop", content)
        self.assertNotIn("pagehide", content)
        self.assertNotIn("visibilitychange", content)

    def test_parsing_dashboard_script_uses_safe_render_helpers(self):
        response = self.client_http.get(
            reverse("management_parsing_dashboard"),
            HTTP_HOST="management.twocomms.shop",
            secure=True,
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("sanitizeExternalUrl", content)
        self.assertIn("escapeHtml", content)
        self.assertNotIn('<a href="${lead.website_url}"', content)

    def test_parsing_dashboard_uses_multi_type_queue_controls(self):
        response = self.client_http.get(
            reverse("management_parsing_dashboard"),
            HTTP_HOST="management.twocomms.shop",
            secure=True,
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn('name="included_types"', content)
        self.assertIn('id="parser-types-queue"', content)
        self.assertIn('id="parser-selected-types-summary"', content)
        self.assertIn("typeCheckboxes", content)
        self.assertNotIn('id="parser_included_type"', content)

    def test_moderation_save_allows_blank_phone_when_phone_completion_required(self):
        lead = ManagementLead.objects.create(
            shop_name="No Phone Lead",
            phone="",
            full_name="Owner",
            website_url="https://alpha.example.com",
            status=ManagementLead.Status.MODERATION,
            lead_source=ManagementLead.LeadSource.PARSER,
            requires_phone_completion=True,
            added_by=self.user,
        )

        response = self._post(
            "management_lead_moderation_action_api",
            {
                "action": "save",
                "shop_name": "No Phone Lead",
                "phone": "",
                "website_url": "https://alpha.example.com",
                "full_name": "Owner",
            },
            lead.id,
        )

        self.assertEqual(response.status_code, 200)
        lead.refresh_from_db()
        self.assertTrue(lead.requires_phone_completion)
        self.assertEqual(lead.status, ManagementLead.Status.MODERATION)

    def test_moderation_save_clears_phone_completion_when_valid_phone_provided(self):
        lead = ManagementLead.objects.create(
            shop_name="No Phone Lead",
            phone="",
            full_name="Owner",
            website_url="https://alpha.example.com",
            status=ManagementLead.Status.MODERATION,
            lead_source=ManagementLead.LeadSource.PARSER,
            requires_phone_completion=True,
            added_by=self.user,
        )

        response = self._post(
            "management_lead_moderation_action_api",
            {
                "action": "save",
                "shop_name": "No Phone Lead",
                "phone": "0671112233",
                "website_url": "https://alpha.example.com",
                "full_name": "Owner",
            },
            lead.id,
        )

        self.assertEqual(response.status_code, 200)
        lead.refresh_from_db()
        self.assertEqual(lead.phone, "+380671112233")
        self.assertFalse(lead.requires_phone_completion)

    def test_moderation_approve_rejects_blank_phone_when_phone_completion_required(self):
        lead = ManagementLead.objects.create(
            shop_name="No Phone Lead",
            phone="",
            full_name="Owner",
            website_url="https://alpha.example.com",
            status=ManagementLead.Status.MODERATION,
            lead_source=ManagementLead.LeadSource.PARSER,
            requires_phone_completion=True,
            added_by=self.user,
        )

        response = self._post(
            "management_lead_moderation_action_api",
            {
                "action": "approve",
                "shop_name": "No Phone Lead",
                "phone": "",
                "website_url": "https://alpha.example.com",
                "full_name": "Owner",
            },
            lead.id,
        )

        self.assertEqual(response.status_code, 400)
        lead.refresh_from_db()
        self.assertEqual(lead.status, ManagementLead.Status.MODERATION)


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


class AnalyticsV7Tests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="analytics_mgr", password="x")

    def _stable_now(self):
        return timezone.make_aware(datetime.combine(timezone.localdate(), time(hour=11, minute=0)))

    def test_record_client_interaction_creates_v7_reason_stage_and_verified_events(self):
        client = Client.objects.create(
            shop_name="Signal Shop",
            phone="+380000000111",
            full_name="Owner",
            owner=self.user,
            call_result=Client.CallResult.THINKING,
        )

        interaction = record_client_interaction(
            client=client,
            manager=self.user,
            result_capture={
                "reason_code": "thinking_need_callback",
                "reason_note": "Чекає рішення власника",
                "context": {"channel": "phone"},
                "details": "Просив повернутися завтра",
            },
            call_result=Client.CallResult.THINKING,
            next_call_at=None,
            evidence={"verification_level": "linked_evidence"},
        )

        stage_event = ClientStageEvent.objects.get(interaction=interaction)
        reason_signal = ReasonSignal.objects.get(interaction=interaction)
        verified_event = VerifiedWorkEvent.objects.get(interaction=interaction)

        self.assertEqual(stage_event.stage_code, "phase_1")
        self.assertEqual(stage_event.result_code, Client.CallResult.THINKING)
        self.assertEqual(reason_signal.reason_code, "thinking_need_callback")
        self.assertEqual(reason_signal.quality_label, "rich")
        self.assertEqual(
            verified_event.verification_level,
            ClientInteractionAttempt.VerificationLevel.LINKED_EVIDENCE,
        )
        self.assertEqual(verified_event.evidence_kind, "linked_evidence")

    def test_followup_sync_records_v7_open_and_close_events(self):
        now = self._stable_now()
        due = now + timedelta(hours=2)
        client = Client.objects.create(
            shop_name="Promise Shop",
            phone="+380000000112",
            full_name="Owner",
            owner=self.user,
            next_call_at=due,
            call_result=Client.CallResult.THINKING,
        )
        interaction = record_client_interaction(
            client=client,
            manager=self.user,
            result_capture={
                "reason_code": "thinking_need_callback",
                "reason_note": "Просив подзвонити після обіду",
                "context": {},
                "details": "",
            },
            call_result=Client.CallResult.THINKING,
            next_call_at=due,
            evidence={"verification_level": "linked_evidence"},
        )

        _sync_client_followup(client, None, due, now, source_interaction=interaction)
        first_followup = ClientFollowUp.objects.get(client=client, owner=self.user, status=ClientFollowUp.Status.OPEN)
        self.assertEqual(first_followup.followup_kind, ClientFollowUp.Kind.PROMISE)
        self.assertEqual(
            FollowUpEvent.objects.filter(
                followup=first_followup,
                event_type=FollowUpEvent.EventType.OPENED,
            ).count(),
            1,
        )

        new_due = due + timedelta(days=1)
        prev_due = client.next_call_at
        client.next_call_at = new_due
        client.save(update_fields=["next_call_at"])
        _sync_client_followup(client, prev_due, new_due, now + timedelta(minutes=10), source_interaction=interaction)

        closed_event = FollowUpEvent.objects.get(followup=first_followup, event_type=FollowUpEvent.EventType.CLOSED)
        replacement = ClientFollowUp.objects.get(
            client=client,
            owner=self.user,
            status=ClientFollowUp.Status.OPEN,
            due_at=new_due,
        )

        self.assertEqual(closed_event.close_reason, "callback_rescheduled")
        self.assertEqual(replacement.reschedule_count, 1)
        self.assertEqual(FollowUpEvent.objects.filter(client=client).count(), 3)

    def test_materialize_manager_day_fact_and_snapshot_embed_v7_payload(self):
        now = self._stable_now()
        day = timezone.localdate(now)
        due = now + timedelta(hours=1)
        client = Client.objects.create(
            shop_name="Snapshot Shop",
            phone="+380000000113",
            full_name="Owner",
            owner=self.user,
            next_call_at=due,
            call_result=Client.CallResult.THINKING,
        )
        interaction = record_client_interaction(
            client=client,
            manager=self.user,
            result_capture={
                "reason_code": "thinking_need_callback",
                "reason_note": "Потрібен повторний контакт",
                "context": {},
                "details": "",
            },
            call_result=Client.CallResult.THINKING,
            next_call_at=due,
            evidence={"verification_level": "linked_evidence"},
        )
        _sync_client_followup(client, None, due, now, source_interaction=interaction)
        ManagerDayStatus.objects.create(
            owner=self.user,
            day=day,
            status=ManagerDayStatus.Status.TECH_FAILURE,
            capacity_factor=Decimal("0.75"),
            source_reason="Telephony degraded",
        )

        fact = materialize_manager_day_fact(owner=self.user, day=day)
        snapshot = persist_nightly_snapshot(owner=self.user, snapshot_date=day)
        stats_payload = get_stats_payload(user=self.user, range_current=build_daily_stats_range(day))

        self.assertEqual(fact.day_status, ManagerDayStatus.Status.TECH_FAILURE)
        self.assertEqual(fact.interactions_total, 1)
        self.assertEqual(fact.reason_signals_total, 1)
        self.assertEqual(fact.followups_opened, 1)
        self.assertIn("v7", snapshot.payload)
        self.assertEqual(snapshot.payload["v7"]["facts"]["interactions_total"], 1)
        self.assertEqual(snapshot.payload["v7"]["facts"]["day_status"], ManagerDayStatus.Status.TECH_FAILURE)
        self.assertEqual(stats_payload["shadow_score"]["v7"]["facts"]["interactions_total"], 1)

    def test_backfill_command_is_idempotent_for_v7_events(self):
        now = self._stable_now()
        day = timezone.localdate(now)
        due = now + timedelta(hours=1)
        client = Client.objects.create(
            shop_name="Backfill Shop",
            phone="+380000000114",
            full_name="Owner",
            owner=self.user,
            next_call_at=due,
            call_result=Client.CallResult.THINKING,
        )
        interaction = record_client_interaction(
            client=client,
            manager=self.user,
            result_capture={
                "reason_code": "thinking_need_callback",
                "reason_note": "Потрібен повторний контакт",
                "context": {},
                "details": "",
            },
            call_result=Client.CallResult.THINKING,
            next_call_at=due,
            evidence={"verification_level": "linked_evidence"},
        )
        _sync_client_followup(client, None, due, now, source_interaction=interaction)

        for _ in range(2):
            call_command(
                "backfill_management_v7_analytics",
                "--user-id",
                str(self.user.id),
                "--date-from",
                day.isoformat(),
                "--date-to",
                day.isoformat(),
            )

        self.assertEqual(ClientStageEvent.objects.filter(interaction=interaction).count(), 1)
        self.assertEqual(ReasonSignal.objects.filter(interaction=interaction).count(), 1)
        self.assertEqual(VerifiedWorkEvent.objects.filter(interaction=interaction).count(), 1)
        self.assertEqual(FollowUpEvent.objects.filter(client=client).count(), 1)
        self.assertEqual(ManagerDayFact.objects.filter(owner=self.user, day=day).count(), 1)
