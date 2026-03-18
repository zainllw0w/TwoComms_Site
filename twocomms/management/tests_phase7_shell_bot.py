import json
from io import BytesIO
from pathlib import Path
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import UserProfile
from management.models import Client, ClientFollowUp, ManagerCommissionAccrual, ManagerPayoutRequest
from management.views import build_report_excel


@override_settings(
    ROOT_URLCONF="twocomms.urls_management",
    ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1", "management.twocomms.shop"],
)
class HomeShellRenderTests(TestCase):
    CSS_PATH = Path(__file__).resolve().parents[1] / "twocomms_django_theme/static/css/management.css"
    MANAGEMENT_HOST = "management.twocomms.shop"

    def get_home(self):
        return self.client.get("/", secure=True, HTTP_HOST=self.MANAGEMENT_HOST)

    def test_home_marks_staff_user_as_admin_and_renders_callback_row(self):
        user = get_user_model().objects.create_user(username="shell_admin", password="x", is_staff=True)
        profile = UserProfile.objects.get(user=user)
        profile.is_manager = False
        profile.save(update_fields=["is_manager"])
        self.client.force_login(user)
        next_call_at = timezone.make_aware(datetime(2026, 3, 16, 14, 30))
        Client.objects.create(
            shop_name="Callback Shop",
            phone="+380671112233",
            full_name="Owner",
            owner=user,
            call_result=Client.CallResult.THINKING,
            next_call_at=next_call_at,
        )

        response = self.get_home()

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Адміністратор")
        self.assertContains(response, "callback-ghost-row")
        self.assertContains(response, "Наступна фаза")

    def test_home_marks_non_staff_manager_as_manager(self):
        user = get_user_model().objects.create_user(username="shell_manager", password="x")
        profile = UserProfile.objects.get(user=user)
        profile.is_manager = True
        profile.save(update_fields=["is_manager"])
        self.client.force_login(user)

        response = self.get_home()

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Менеджер")

    def test_home_moves_due_today_callbacks_into_today_group_and_marks_missed_callbacks(self):
        user = get_user_model().objects.create_user(username="callback_manager", password="x")
        profile = UserProfile.objects.get(user=user)
        profile.is_manager = True
        profile.save(update_fields=["is_manager"])
        self.client.force_login(user)

        now = timezone.now()
        due_today = now.replace(hour=18, minute=0, second=0, microsecond=0)
        missed_at = now - timedelta(days=1, hours=2)

        due_client = Client.objects.create(
            shop_name="Due Today Shop",
            phone="+380671000001",
            full_name="Due Today",
            owner=user,
            call_result=Client.CallResult.THINKING,
            next_call_at=due_today,
        )
        missed_client = Client.objects.create(
            shop_name="Missed Shop",
            phone="+380671000002",
            full_name="Missed",
            owner=user,
            call_result=Client.CallResult.THINKING,
            next_call_at=missed_at,
        )
        yesterday_created = now - timedelta(days=1)
        Client.objects.filter(id__in=[due_client.id, missed_client.id]).update(created_at=yesterday_created)

        response = self.get_home()

        self.assertEqual(response.status_code, 200)
        grouped = response.context["grouped_clients"]
        flat = {
            item["shop"]: (label, item)
            for label, items in grouped
            for item in items
        }
        self.assertEqual(flat["Due Today Shop"][0], "Сьогодні")
        self.assertEqual(flat["Due Today Shop"][1]["callback_state"], "today")
        self.assertTrue(flat["Due Today Shop"][1]["callback_pending"])
        self.assertEqual(flat["Missed Shop"][1]["callback_state"], "missed")
        self.assertFalse(flat["Missed Shop"][1]["callback_pending"])

    def test_home_renders_updated_daily_zones_and_secondary_shell_chips(self):
        user = get_user_model().objects.create_user(username="shell_metrics", password="x", is_staff=True)
        self.client.force_login(user)
        now = timezone.localtime(timezone.now()).replace(second=0, microsecond=0)
        due_today = now.replace(hour=17, minute=15)
        due_now_at = now - timedelta(minutes=20)
        missed_at = now - timedelta(hours=3)
        Client.objects.create(
            shop_name="Due Today Shop",
            phone="+380671000111",
            full_name="Due",
            owner=user,
            call_result=Client.CallResult.THINKING,
            next_call_at=due_today,
        )
        due_now_client = Client.objects.create(
            shop_name="Due Now Shop",
            phone="+380671000113",
            full_name="Due Now",
            owner=user,
            call_result=Client.CallResult.THINKING,
            next_call_at=due_now_at,
        )
        missed_client = Client.objects.create(
            shop_name="Missed Shop",
            phone="+380671000112",
            full_name="Missed",
            owner=user,
            call_result=Client.CallResult.THINKING,
            next_call_at=missed_at,
        )
        ClientFollowUp.objects.create(
            client=due_now_client,
            owner=user,
            due_at=due_now_at,
            due_date=due_now_at.date(),
            grace_until=now + timedelta(minutes=15),
        )
        ClientFollowUp.objects.create(
            client=missed_client,
            owner=user,
            due_at=missed_at,
            due_date=missed_at.date(),
            grace_until=now - timedelta(minutes=5),
        )

        response = self.get_home()

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "0–19")
        self.assertContains(response, "20–49")
        self.assertContains(response, "50+")
        self.assertContains(response, "daily-followups")
        self.assertContains(response, "Сьогодні")
        self.assertContains(response, "Термінові")
        self.assertContains(response, 'data-help-target="daily-stats-help"')
        self.assertContains(response, 'id="daily-stats-help"')
        self.assertContains(response, "help-popover--daily")
        self.assertContains(response, "daily-disclosure")
        self.assertEqual(response.context["management_shell_today_callbacks"], 2)
        self.assertEqual(response.context["management_shell_urgent_callbacks"], 1)
        self.assertEqual(response.context["management_shell_missed_callbacks"], 1)

    def test_home_renders_scroll_region_and_compact_action_stack_contract(self):
        user = get_user_model().objects.create_user(username="shell_layout", password="x", is_staff=True)
        self.client.force_login(user)
        Client.objects.create(
            shop_name="Action Shop",
            phone="+380671110113",
            full_name="Owner",
            owner=user,
            call_result=Client.CallResult.THINKING,
            next_call_at=timezone.now() + timedelta(hours=1),
        )

        response = self.get_home()

        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        self.assertContains(response, 'id="sidebar-rail-scroll"')
        self.assertContains(response, "sidebar-rail__scroll-cue")
        self.assertContains(response, "sidebar-rail__mouse")
        self.assertContains(response, "user-profile__identity")
        self.assertContains(response, "user-profile__meta")
        self.assertContains(response, "user-role__text")
        self.assertContains(response, "user-identity-line")
        self.assertContains(response, "user-actions-strip")
        self.assertContains(response, "user-action user-action--money")
        self.assertContains(response, "user-action user-action--stats user-action--icon-only")
        self.assertContains(response, "user-action user-action--edit user-action--icon-only")
        self.assertContains(response, "user-action user-action--logout user-action--icon-only")
        self.assertContains(response, "user-action__money-currency-icon")
        self.assertContains(response, "sidebar-nav-slot")
        self.assertContains(response, "sidebar-nav-panel")
        self.assertContains(response, "sidebar-collapse-toggle")
        self.assertContains(response, "sidebar-collapse-toggle--cue")
        self.assertContains(response, "sidebar-collapse-toggle--full-bleed")
        self.assertContains(response, "sidebar-collapsed-launcher")
        self.assertContains(response, "sidebar-collapsed-launcher__surface")
        self.assertContains(response, "sidebar-collapsed-launcher__arrow")
        self.assertContains(response, "sidebar-collapse-toggle__arrow--left")
        self.assertContains(response, "sidebar-collapse-toggle__arrow--right")
        self.assertContains(response, "action-rail--overlay")
        self.assertContains(response, "action-rail__stack--vertical")
        self.assertContains(response, "action-rail__stack")
        self.assertContains(response, "action-rail__callback")
        self.assertContains(response, "action-rail__callback-text")
        self.assertContains(response, "action-rail__utility")
        self.assertNotContains(response, "sidebar-collapsed-launcher__deck")
        self.assertNotContains(response, "sidebar-collapsed-launcher__card--back")
        self.assertRegex(
            html,
            r'(?s)<nav class="nav-menu nav-menu--primary" id="sidebar-primary-nav">.*?</nav>\s*<button type="button" class="sidebar-collapse-toggle[^"]*" id="sidebar-collapse-toggle"',
        )
        self.assertEqual(response.content.decode("utf-8").count(">Парсинг<"), 1)

    def test_home_renders_full_bleed_collapse_cue_modifier(self):
        user = get_user_model().objects.create_user(username="shell_cue_modifier", password="x", is_staff=True)
        self.client.force_login(user)

        response = self.get_home()

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "sidebar-collapse-toggle--cue")
        self.assertContains(response, "sidebar-collapse-toggle--full-bleed")

    def test_management_css_uses_tighter_collapse_cue_gap_contract(self):
        css = self.CSS_PATH.read_text(encoding="utf-8")

        self.assertIn("padding-bottom: 26px;", css)
        self.assertIn("padding: 12px 12px 6px;", css)
        self.assertIn("min-height: 52px;", css)

    def test_management_css_uses_interactive_collapse_cue_hover_contract(self):
        css = self.CSS_PATH.read_text(encoding="utf-8")

        self.assertIn("cursor: pointer;", css)
        self.assertIn("@keyframes sidebar-collapse-arrow-drift", css)
        self.assertIn(".sidebar-collapse-toggle--cue:hover .sidebar-collapse-toggle__label", css)
        self.assertIn("text-shadow: 0 0 14px rgba(255, 91, 87, 0.18);", css)
        self.assertIn("animation: sidebar-collapse-arrow-drift 1.35s ease-in-out infinite alternate;", css)

    def test_home_renders_collapse_cue_outside_nav_flow(self):
        user = get_user_model().objects.create_user(username="shell_cue_structure", password="x", is_staff=True)
        self.client.force_login(user)

        response = self.get_home()

        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        self.assertRegex(
            html,
            r'(?s)<nav class="nav-menu nav-menu--primary" id="sidebar-primary-nav">.*?</nav>\s*<button type="button" class="sidebar-collapse-toggle[^"]*" id="sidebar-collapse-toggle"',
        )
        self.assertNotRegex(
            html,
            r'(?s)<nav class="nav-menu nav-menu--primary" id="sidebar-primary-nav">.*?id="sidebar-collapse-toggle".*?</nav>',
        )

    def test_home_uses_effective_callback_state_for_due_now_and_missed(self):
        user = get_user_model().objects.create_user(username="callback_effective_mgr", password="x")
        profile = UserProfile.objects.get(user=user)
        profile.is_manager = True
        profile.save(update_fields=["is_manager"])
        self.client.force_login(user)

        now = timezone.localtime(timezone.now()).replace(second=0, microsecond=0)
        due_now_at = now - timedelta(minutes=25)
        missed_at = now - timedelta(hours=3)

        due_client = Client.objects.create(
            shop_name="Grace Window Shop",
            phone="+380671009001",
            full_name="Grace Owner",
            owner=user,
            call_result=Client.CallResult.THINKING,
            next_call_at=due_now_at,
        )
        missed_client = Client.objects.create(
            shop_name="Expired Grace Shop",
            phone="+380671009002",
            full_name="Expired Owner",
            owner=user,
            call_result=Client.CallResult.THINKING,
            next_call_at=missed_at,
        )
        ClientFollowUp.objects.create(
            client=due_client,
            owner=user,
            due_at=due_now_at,
            due_date=due_now_at.date(),
            grace_until=now + timedelta(minutes=20),
        )
        ClientFollowUp.objects.create(
            client=missed_client,
            owner=user,
            due_at=missed_at,
            due_date=missed_at.date(),
            grace_until=now - timedelta(minutes=5),
        )

        response = self.get_home()

        self.assertEqual(response.status_code, 200)
        grouped = response.context["grouped_clients"]
        flat = {
            item["shop"]: item
            for _, items in grouped
            for item in items
        }
        self.assertEqual(flat["Grace Window Shop"]["callback_state"], "due_now")
        self.assertFalse(flat["Grace Window Shop"]["callback_pending"])
        self.assertEqual(flat["Expired Grace Shop"]["callback_state"], "missed")
        self.assertEqual(response.context["management_shell_today_callbacks"], 1)
        self.assertEqual(response.context["management_shell_urgent_callbacks"], 1)
        self.assertEqual(response.context["management_shell_missed_callbacks"], 1)

    def test_home_renders_money_action_from_same_summary_as_payout_page(self):
        user = get_user_model().objects.create_user(username="shell_money_mgr", password="x", is_staff=True)
        profile = UserProfile.objects.get(user=user)
        profile.manager_position = "Старший менеджер з дуже довгою посадою"
        profile.save(update_fields=["manager_position"])
        self.client.force_login(user)

        now = timezone.now()
        ManagerCommissionAccrual.objects.create(
            owner=user,
            amount=Decimal("1500.00"),
            frozen_until=now - timedelta(days=1),
        )
        ManagerCommissionAccrual.objects.create(
            owner=user,
            amount=Decimal("400.00"),
            frozen_until=now + timedelta(days=10),
        )
        ManagerPayoutRequest.objects.create(
            owner=user,
            amount=Decimal("250.00"),
            status=ManagerPayoutRequest.Status.APPROVED,
        )
        ManagerPayoutRequest.objects.create(
            owner=user,
            amount=Decimal("300.00"),
            status=ManagerPayoutRequest.Status.PAID,
            paid_at=now - timedelta(days=2),
        )

        home_response = self.get_home()
        payouts_response = self.client.get("/payouts/", secure=True)

        self.assertEqual(home_response.status_code, 200)
        self.assertEqual(payouts_response.status_code, 200)
        self.assertEqual(home_response.context["management_shell_payout_available"], Decimal("950.00"))
        self.assertTrue(home_response.context["management_shell_has_active_payout_request"])
        self.assertEqual(home_response.context["management_shell_payout_available"], payouts_response.context["available"])
        self.assertContains(home_response, 'href="/payouts/"')
        self.assertContains(home_response, 'data-money-available="950.00"')
        self.assertContains(home_response, "950.00")
        self.assertContains(home_response, "user-action__money-currency-icon")
        self.assertContains(home_response, "₴")


@override_settings(
    ROOT_URLCONF="twocomms.urls_management",
    ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1", "management.twocomms.shop"],
)
class ProfileBotBindTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="bind_mgr", password="x", is_staff=True)
        self.client.force_login(self.user)

    def test_profile_bind_returns_deep_link_and_fallback_code(self):
        with patch.dict(
            "os.environ",
            {
                "MANAGER_TG_BOT_USERNAME": "twocomms_manager_bot",
            },
            clear=False,
        ):
            response = self.client.post(
                "/profile/bind-code/",
                secure=True,
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertIn("deep_link_url", payload)
        self.assertIn("fallback_code", payload)
        self.assertIn("start_payload", payload)
        self.assertTrue(payload["deep_link_url"].startswith("https://t.me/twocomms_manager_bot?start="))

    def test_management_bot_webhook_accepts_signed_start_payload(self):
        with patch.dict(
            "os.environ",
            {
                "MANAGER_TG_BOT_TOKEN": "manager-token",
                "MANAGER_TG_BOT_USERNAME": "twocomms_manager_bot",
            },
            clear=False,
        ):
            bind_response = self.client.post(
                "/profile/bind-code/",
                secure=True,
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )
            payload = bind_response.json()
            start_payload = payload["start_payload"]
            webhook_response = self.client.post(
                "/tg-manager/webhook/manager-token/",
                data=json.dumps(
                    {
                        "message": {
                            "text": f"/start {start_payload}",
                            "chat": {"id": 555123},
                            "from": {"username": "manager_bind_user"},
                        }
                    }
                ),
                content_type="application/json",
            )

        self.assertEqual(webhook_response.status_code, 200)
        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual(profile.tg_manager_chat_id, 555123)
        self.assertEqual(profile.tg_manager_username, "manager_bind_user")


@override_settings(
    ROOT_URLCONF="twocomms.urls_management",
    ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1", "management.twocomms.shop"],
)
class ReportWorkbookTests(TestCase):
    def test_build_report_excel_contains_new_analytics_sheets(self):
        import openpyxl

        user = get_user_model().objects.create_user(username="report_admin", password="x", is_staff=True)
        next_call_at = timezone.make_aware(datetime(2026, 3, 16, 16, 45))
        Client.objects.create(
            shop_name="Report Shop",
            phone="+380671110000",
            full_name="Report Owner",
            owner=user,
            source="Instagram",
            call_result=Client.CallResult.THINKING,
            next_call_at=next_call_at,
        )

        workbook_bytes = build_report_excel(
            user,
            stats={"points_today": 12, "processed_today": 1},
            clients=list(Client.objects.filter(owner=user)),
        )

        workbook = openpyxl.load_workbook(BytesIO(workbook_bytes))
        self.assertEqual(
            workbook.sheetnames,
            [
                "Overview",
                "Clients",
                "Callbacks",
                "Duplicate Queue",
                "Shadow Score Context",
                "Advice & Risk Notes",
            ],
        )
        overview = workbook["Overview"]
        self.assertEqual(overview["A1"].value, "Звіт менеджера")
        self.assertEqual(overview["A2"].value, "Менеджер")
