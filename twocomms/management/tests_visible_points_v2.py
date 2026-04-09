from datetime import date, datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from management.models import Client, CommercialOfferEmailLog, ManagementLead
from management.services.snapshots import build_daily_stats_range
from management.stats_service import _get_or_build_config, get_stats_payload
from management.views import get_user_stats

from .services.visible_points import (
    VISIBLE_POINTS_POLICY_VERSION,
    build_visible_points_breakdown,
    classify_points_source_bucket,
    sync_client_visible_points,
)


class VisiblePointsServiceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="points_v2_mgr", password="x", is_staff=True)

    def _set_created_at(self, client: Client, created_at):
        Client.objects.filter(pk=client.pk).update(created_at=created_at)
        client.refresh_from_db()
        return client

    def _manual_client(self, **overrides):
        payload = {
            "shop_name": overrides.pop("shop_name", "Manual Shop"),
            "phone": overrides.pop("phone", "+380671110001"),
            "full_name": overrides.pop("full_name", "Owner"),
            "owner": self.user,
            "call_result": overrides.pop("call_result", Client.CallResult.NOT_INTERESTED),
            "call_result_reason_code": overrides.pop("call_result_reason_code", "current_supplier"),
            "call_result_reason_note": overrides.pop("call_result_reason_note", "Працюють з іншим постачальником."),
            "manager_note": overrides.pop("manager_note", "Зафіксовано аргумент клієнта."),
            "call_result_context": overrides.pop("call_result_context", {}),
            "next_call_at": overrides.pop("next_call_at", None),
        }
        payload.update(overrides)
        return Client.objects.create(**payload)

    def test_parser_sourced_mid_funnel_touch_scores_much_lower_than_manual(self):
        due_at = timezone.now() + timedelta(hours=3)
        manual = self._manual_client(
            shop_name="Manual Email",
            phone="+380671110011",
            call_result=Client.CallResult.SENT_EMAIL,
            call_result_reason_code="",
            call_result_reason_note="",
            manager_note="Надіслано КП і зафіксовано наступний крок.",
            call_result_context={"cp_log_id": 11, "cp_recipient_email": "owner@example.com"},
            next_call_at=due_at,
        )
        parser_client = self._manual_client(
            shop_name="Parser Email",
            phone="+380671110012",
            call_result=Client.CallResult.SENT_EMAIL,
            call_result_reason_code="",
            call_result_reason_note="",
            manager_note="Надіслано КП і зафіксовано наступний крок.",
            call_result_context={"cp_log_id": 12, "cp_recipient_email": "owner@example.com"},
            next_call_at=due_at,
        )
        ManagementLead.objects.create(
            shop_name="Parser Email",
            phone=parser_client.phone,
            full_name="Owner",
            added_by=self.user,
            processed_by=self.user,
            lead_source=ManagementLead.LeadSource.PARSER,
            status=ManagementLead.Status.CONVERTED,
            converted_client=parser_client,
        )

        manual_breakdown = build_visible_points_breakdown(manual)
        parser_breakdown = build_visible_points_breakdown(parser_client)

        self.assertEqual(classify_points_source_bucket(manual), "manual_origin")
        self.assertEqual(classify_points_source_bucket(parser_client), "parser_assigned_base")
        self.assertGreater(manual_breakdown["final_points"], parser_breakdown["final_points"])
        self.assertLessEqual(parser_breakdown["final_points"], 4)

    def test_negative_outcome_without_reason_and_note_is_capped_to_one(self):
        client = self._manual_client(
            shop_name="Weak Negative",
            phone="+380671110021",
            call_result=Client.CallResult.NOT_INTERESTED,
            call_result_reason_code="",
            call_result_reason_note="",
            manager_note="",
        )

        breakdown = build_visible_points_breakdown(client)

        self.assertEqual(breakdown["final_points"], 1)
        self.assertIn("negative_missing_context_cap", breakdown["flags"])

    def test_repeat_multiplier_halves_second_touch_and_zeros_third_same_identity(self):
        base_time = timezone.make_aware(datetime.combine(date(2026, 3, 26), time(hour=10, minute=0)))
        clients = []
        for idx in range(3):
            client = self._manual_client(
                shop_name=f"Repeat Shop {idx}",
                phone="+380671110031",
                call_result=Client.CallResult.NOT_INTERESTED,
                call_result_reason_code="current_supplier",
                call_result_reason_note="Працюють з іншим постачальником.",
                manager_note="Коротко зафіксовано суть відповіді.",
            )
            self._set_created_at(client, base_time + timedelta(minutes=idx))
            sync_client_visible_points(client)
            client.refresh_from_db()
            clients.append(client)

        self.assertEqual([item.points_override for item in clients], [4, 2, 0])

    def test_daily_caps_keep_wrote_ig_progress_small_even_with_followups(self):
        base_time = timezone.make_aware(datetime.combine(date(2026, 3, 26), time(hour=11, minute=0)))
        awarded = []
        for idx in range(3):
            client = self._manual_client(
                shop_name=f"IG Shop {idx}",
                phone=f"+38067111004{idx}",
                call_result=Client.CallResult.WROTE_IG,
                call_result_reason_code="",
                call_result_reason_note="",
                manager_note="Написав в direct і зафіксував контекст.",
                next_call_at=base_time + timedelta(hours=2 + idx),
            )
            self._set_created_at(client, base_time + timedelta(minutes=idx))
            sync_client_visible_points(client)
            client.refresh_from_db()
            awarded.append(int(client.points_override or 0))

        self.assertEqual(sum(awarded), 12)
        self.assertEqual(awarded[-1], 0)

    def test_thinking_with_scheduled_promise_is_worth_meaningfully_more_than_without_followup(self):
        with_followup = self._manual_client(
            shop_name="Promise Shop",
            phone="+380671110051",
            call_result=Client.CallResult.THINKING,
            call_result_reason_code="",
            call_result_reason_note="",
            manager_note="Уточнили заперечення і домовилися про швидкий передзвін.",
            next_call_at=timezone.now() + timedelta(hours=24),
        )
        no_followup = self._manual_client(
            shop_name="Loose Shop",
            phone="+380671110052",
            call_result=Client.CallResult.THINKING,
            call_result_reason_code="",
            call_result_reason_note="",
            manager_note="Сказав, що подумає, без фіксації наступного кроку.",
        )

        followup_points = build_visible_points_breakdown(with_followup)["final_points"]
        loose_points = build_visible_points_breakdown(no_followup)["final_points"]

        self.assertGreaterEqual(followup_points - loose_points, 3)


class VisiblePointsStatsConsistencyTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(username="points_stats_mgr", password="x", is_staff=True)

    def test_manual_lead_addition_no_longer_grants_visible_bar_bonus(self):
        now_local = timezone.localtime(timezone.now())
        ManagementLead.objects.create(
            shop_name="Manual Lead",
            phone="+380671110061",
            full_name="Owner",
            lead_source=ManagementLead.LeadSource.MANUAL,
            status=ManagementLead.Status.BASE,
            added_by=self.user,
        )

        stats = get_user_stats(self.user)

        self.assertEqual(stats["points_today"], 0)
        self.assertEqual(stats["points_total"], 0)
        self.assertEqual(stats["lead_bonus_today"], 0)
        self.assertEqual(stats["lead_bonus_total"], 0)

    def test_get_user_stats_and_stats_payload_use_same_points_override_value(self):
        target_date = timezone.localdate()
        created_at = timezone.make_aware(datetime.combine(target_date, time(hour=10, minute=30)))
        client = Client.objects.create(
            shop_name="Weighted Client",
            phone="+380671110071",
            full_name="Owner",
            owner=self.user,
            call_result=Client.CallResult.ORDER,
            points_override=7,
            call_result_context={"points_policy_version": VISIBLE_POINTS_POLICY_VERSION},
        )
        Client.objects.filter(pk=client.pk).update(created_at=created_at)

        user_stats = get_user_stats(self.user)
        payload = get_stats_payload(user=self.user, range_current=build_daily_stats_range(target_date))

        self.assertEqual(user_stats["points_today"], 7)
        self.assertEqual(payload["summary"]["points"], 7)
        self.assertEqual(payload["summary"]["points_per_client"], 7.0)

    def test_kpd_defaults_use_lower_points_norm_for_visible_bar_effort(self):
        self.assertEqual(_get_or_build_config()["kpd"]["points_norm"], 85)


@override_settings(ROOT_URLCONF="twocomms.urls_management")
class VisiblePointsWritePathTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="points_write_mgr", password="x", is_staff=True)
        self.client.force_login(self.user)
        self.sent_cp = CommercialOfferEmailLog.objects.create(
            owner=self.user,
            recipient_email="owner@example.com",
            recipient_name="Owner",
            subject="КП",
            status=CommercialOfferEmailLog.Status.SENT,
        )

    def test_home_client_create_persists_v2_points_metadata(self):
        response = self.client.post(
            "/",
            {
                "shop_name": "Manual Target",
                "phone": "+380671110081",
                "website_url": "https://manual.example.com",
                "full_name": "Owner",
                "role": Client.Role.MANAGER,
                "source": "instagram",
                "call_result": Client.CallResult.NOT_INTERESTED,
                "call_result_reason_code": "current_supplier",
                "call_result_reason_note": "Працюють з іншим постачальником.",
                "manager_note": "Виявив причину і зафіксував у картці.",
                "next_call_type": "no_follow",
            },
            secure=True,
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        created = Client.objects.get(shop_name="Manual Target", owner=self.user)
        self.assertEqual(created.points_override, 4)
        self.assertEqual(created.call_result_context["points_policy_version"], VISIBLE_POINTS_POLICY_VERSION)
        self.assertEqual(created.call_result_context["points_source_bucket"], "manual_origin")
        self.assertIn("points_breakdown", created.call_result_context)
        self.assertIn("points_flags", created.call_result_context)

    def test_lead_process_persists_parser_weighted_points(self):
        lead = ManagementLead.objects.create(
            shop_name="Parser Lead",
            phone="+380671110091",
            full_name="Owner",
            status=ManagementLead.Status.BASE,
            lead_source=ManagementLead.LeadSource.PARSER,
            added_by=self.user,
        )
        next_call_at = timezone.localtime(timezone.now()).replace(second=0, microsecond=0) + timedelta(hours=3)

        response = self.client.post(
            f"/leads/api/{lead.id}/process/",
            {
                "shop_name": "Parser Lead",
                "phone": "+380671110091",
                "website_url": "https://parser.example.com",
                "full_name": "Owner",
                "role": Client.Role.MANAGER,
                "source": "instagram",
                "call_result": Client.CallResult.SENT_EMAIL,
                "cp_log_id": str(self.sent_cp.id),
                "manager_note": "Надіслано КП і погоджено швидкий наступний крок.",
                "next_call_type": "scheduled",
                "next_call_date": next_call_at.strftime("%Y-%m-%d"),
                "next_call_time": next_call_at.strftime("%H:%M"),
            },
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        created = Client.objects.get(shop_name="Parser Lead", owner=self.user)
        self.assertEqual(created.call_result_context["points_policy_version"], VISIBLE_POINTS_POLICY_VERSION)
        self.assertEqual(created.call_result_context["points_source_bucket"], "parser_assigned_base")
        self.assertEqual(created.points_override, 3)


class RecalculateVisiblePointsCommandTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="points_recalc_mgr", password="x", is_staff=True)

    def test_command_recalculates_only_selected_date(self):
        target_date = date(2026, 3, 26)
        other_date = target_date - timedelta(days=1)
        target_client = Client.objects.create(
            shop_name="Target Legacy",
            phone="+380671110101",
            full_name="Owner",
            owner=self.user,
            call_result=Client.CallResult.NOT_INTERESTED,
            call_result_reason_code="current_supplier",
            call_result_reason_note="Працюють з іншим постачальником.",
            manager_note="Зафіксовано у коментарі.",
        )
        other_client = Client.objects.create(
            shop_name="Other Legacy",
            phone="+380671110102",
            full_name="Owner",
            owner=self.user,
            call_result=Client.CallResult.NOT_INTERESTED,
            call_result_reason_code="current_supplier",
            call_result_reason_note="Працюють з іншим постачальником.",
            manager_note="Зафіксовано у коментарі.",
        )
        Client.objects.filter(pk=target_client.pk).update(created_at=timezone.make_aware(datetime.combine(target_date, time(hour=9, minute=0))))
        Client.objects.filter(pk=other_client.pk).update(created_at=timezone.make_aware(datetime.combine(other_date, time(hour=9, minute=0))))

        call_command("recalculate_visible_points", date=target_date.isoformat())

        target_client.refresh_from_db()
        other_client.refresh_from_db()
        self.assertEqual(target_client.points_override, 4)
        self.assertEqual(target_client.call_result_context["points_policy_version"], VISIBLE_POINTS_POLICY_VERSION)
        self.assertIsNone(other_client.points_override)
