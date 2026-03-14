from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from management.models import (
    Client,
    ClientFollowUp,
    CommandRunLog,
    DuplicateReview,
    ManagementDailyActivity,
    ManagementStatsConfig,
    ManagerDayStatus,
    Shop,
)
from management.services.followups import build_reminder_digest
from management.services.snapshots import build_daily_stats_range, persist_nightly_snapshot
from management.stats_service import get_stats_payload


class ExtendedConfigSeedTests(TestCase):
    def test_seed_management_defaults_populates_extended_versioned_contract(self):
        call_command("seed_management_defaults")

        config = ManagementStatsConfig.objects.get(pk=1)

        self.assertEqual(config.legacy_kpd_formula_version, "kpd-v1")
        self.assertEqual(config.shadow_mosaic_formula_version, "mosaic-v1")
        self.assertIn("weights", config.mosaic_config)
        self.assertIn("commission_rates", config.payroll_config)
        self.assertIn("aging_multipliers", config.forecast_config)
        self.assertIn("health_thresholds", config.telephony_config)
        self.assertIn("quiet_hours", config.ui_config)
        self.assertEqual(config.validation_state.get("state"), "shadow_window_open")


class ReminderDigestTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(username="reminder_mgr", password="x", is_staff=True)
        call_command("seed_management_defaults")

    def test_reminder_digest_enters_digest_mode_on_capacity_overload(self):
        now = timezone.localtime(timezone.now()).replace(second=0, microsecond=0)
        due_at = now - timedelta(minutes=5)
        for idx in range(30):
            client = Client.objects.create(
                shop_name=f"Reminder Shop {idx}",
                phone=f"+38067111{idx:04d}",
                full_name="Owner",
                owner=self.user,
                next_call_at=due_at,
            )
            ClientFollowUp.objects.create(
                client=client,
                owner=self.user,
                due_at=due_at,
                due_date=due_at.date(),
                grace_until=due_at - timedelta(hours=1),
            )

        digest = build_reminder_digest(self.user, now=now, stats={"processed_today": 5}, report_sent=True)

        self.assertTrue(digest["digest_mode"])
        self.assertIn("REMINDER_STORM", digest["incident_keys"])
        self.assertGreaterEqual(digest["overload_count"], 5)
        self.assertEqual(len(digest["reminders"]), 25)

    def test_send_management_reminders_command_logs_and_updates_followups(self):
        now = timezone.localtime(timezone.now()).replace(second=0, microsecond=0)
        client = Client.objects.create(
            shop_name="Command Reminder Shop",
            phone="+380671230000",
            full_name="Owner",
            owner=self.user,
            next_call_at=now - timedelta(minutes=3),
        )
        followup = ClientFollowUp.objects.create(
            client=client,
            owner=self.user,
            due_at=now - timedelta(minutes=3),
            due_date=now.date(),
            grace_until=now - timedelta(hours=1),
        )

        call_command("send_management_reminders")

        followup.refresh_from_db()
        self.assertIsNotNone(followup.last_notified_at)
        run_log = CommandRunLog.objects.get(command_name="send_management_reminders")
        self.assertEqual(run_log.status, CommandRunLog.Status.SUCCESS)
        self.assertGreaterEqual(run_log.rows_processed, 1)


class RichShadowPayloadTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(username="shadow_rich_mgr", password="x", is_staff=True)
        call_command("seed_management_defaults")

    def test_snapshot_and_stats_payload_expose_gate_incidents_and_portfolio_contract(self):
        target_date = date(2026, 3, 12)
        created_at = timezone.make_aware(datetime.combine(target_date, time(hour=11, minute=30)))
        Client.objects.create(
            shop_name="Shadow Payload Shop",
            phone="+380671115000",
            full_name="Owner",
            owner=self.user,
            call_result=Client.CallResult.WAITING_PAYMENT,
            points_override=180,
            source="Instagram",
        )
        Client.objects.filter(owner=self.user).update(created_at=created_at)
        ManagementDailyActivity.objects.create(
            user=self.user,
            date=target_date,
            active_seconds=5_400,
            last_seen_at=created_at,
        )
        ManagerDayStatus.objects.create(
            owner=self.user,
            day=target_date,
            status=ManagerDayStatus.Status.WORKING,
            capacity_factor=Decimal("0.80"),
            source_reason="manual",
        )
        Shop.objects.create(
            name="Rescue Risk Shop",
            owner_full_name="Owner",
            created_by=self.user,
            managed_by=self.user,
            shop_type=Shop.ShopType.TEST,
            test_connected_at=target_date - timedelta(days=20),
            test_period_days=7,
        )
        DuplicateReview.objects.create(
            owner=self.user,
            zone="review",
            incoming_shop_name="Possible Duplicate",
            incoming_phone="+380671115999",
            incoming_payload={"source": "manual"},
            candidate_summary=[{"kind": "client", "id": 1}],
        )

        persist_nightly_snapshot(owner=self.user, snapshot_date=target_date)
        payload = get_stats_payload(user=self.user, range_current=build_daily_stats_range(target_date))

        shadow = payload["shadow_score"]
        self.assertIn("ewr", shadow)
        self.assertIn("incident_keys", shadow)
        self.assertIn("gate_level", shadow)
        self.assertIn("dampener_value", shadow)
        self.assertIn("portfolio_health_state", shadow)
        self.assertIn("must_do_today", shadow)
        self.assertIn("best_opportunities", shadow)
        self.assertIn("rescue_top5", shadow)
        self.assertIn("salary_simulator", shadow)
        self.assertIn("why_changed_today", shadow)
        self.assertTrue(shadow["rescue_top5"])


@override_settings(ROOT_URLCONF="twocomms.urls_management")
class AnalyticsUiRegressionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(username="analytics_mgr", password="x", is_staff=True)
        self.client.force_login(self.user)
        call_command("seed_management_defaults")

        target_date = date(2026, 3, 12)
        created_at = timezone.make_aware(datetime.combine(target_date, time(hour=12, minute=45)))
        Client.objects.create(
            shop_name="UI Analytics Shop",
            phone="+380671119998",
            full_name="Owner",
            owner=self.user,
            call_result=Client.CallResult.THINKING,
            points_override=180,
            source="Instagram",
        )
        Client.objects.filter(owner=self.user).update(created_at=created_at)
        ManagementDailyActivity.objects.create(user=self.user, date=target_date, active_seconds=3_600, last_seen_at=created_at)
        persist_nightly_snapshot(owner=self.user, snapshot_date=target_date)

    def test_stats_page_renders_new_explainability_and_action_surfaces(self):
        target_date = date(2026, 3, 12)
        response = self.client.get(
            f"/stats/?period=range&from={target_date.isoformat()}&to={target_date.isoformat()}",
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Що змінилося сьогодні")
        self.assertContains(response, "Критично на сьогодні")
        self.assertContains(response, "Найкращі можливості")
        self.assertContains(response, "Топ-5 на порятунок")
        self.assertContains(response, "Симулятор винагороди")
        self.assertContains(response, "Радарний огляд")
        self.assertContains(response, "Таймлайн комунікації з клієнтом")
        self.assertContains(response, "Відкрити розклад")
        self.assertContains(response, "Подати апеляцію")

    def test_admin_panel_renders_readiness_incidents_and_forecast_widgets(self):
        response = self.client.get("/admin-panel/?tab=managers", secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Готовність і інциденти")
        self.assertContains(response, "Прогнозні діапазони")
        self.assertContains(response, "Черга дублів")
        self.assertContains(response, "Пріоритетні черги")
        self.assertContains(response, "Довіра до прогнозу")
        self.assertContains(response, "Менеджери під ризиком")
