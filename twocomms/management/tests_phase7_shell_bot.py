import json
from io import BytesIO
from datetime import datetime, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import UserProfile
from management.models import Client
from management.views import build_report_excel


@override_settings(
    ROOT_URLCONF="twocomms.urls_management",
    ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1", "management.twocomms.shop"],
)
class HomeShellRenderTests(TestCase):
    def test_home_marks_staff_user_as_admin_and_renders_callback_row(self):
        user = get_user_model().objects.create_user(username="shell_admin", password="x", is_staff=True)
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

        response = self.client.get("/", secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Адміністратор")
        self.assertContains(response, "callback-ghost-row")
        self.assertContains(response, "Передзвонити")

    def test_home_marks_non_staff_manager_as_manager(self):
        user = get_user_model().objects.create_user(username="shell_manager", password="x")
        profile = UserProfile.objects.get(user=user)
        profile.is_manager = True
        profile.save(update_fields=["is_manager"])
        self.client.force_login(user)

        response = self.client.get("/", secure=True)

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

        response = self.client.get("/", secure=True)

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
        due_today = timezone.now().replace(hour=17, minute=15, second=0, microsecond=0)
        missed_at = timezone.now() - timedelta(days=1, hours=1)
        Client.objects.create(
            shop_name="Due Today Shop",
            phone="+380671000111",
            full_name="Due",
            owner=user,
            call_result=Client.CallResult.THINKING,
            next_call_at=due_today,
        )
        Client.objects.create(
            shop_name="Missed Shop",
            phone="+380671000112",
            full_name="Missed",
            owner=user,
            call_result=Client.CallResult.THINKING,
            next_call_at=missed_at,
        )

        response = self.client.get("/", secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "0–19")
        self.assertContains(response, "20–49")
        self.assertContains(response, "50+")
        self.assertContains(response, "Передзвони сьогодні")
        self.assertContains(response, "Пропущено")
        self.assertContains(response, 'data-help-target="daily-stats-help"')
        self.assertContains(response, 'id="daily-stats-help"')
        self.assertContains(response, "help-popover--daily")
        self.assertContains(response, "daily-disclosure")

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

        response = self.client.get("/", secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="sidebar-rail-scroll"')
        self.assertContains(response, "sidebar-rail__scroll-cue")
        self.assertContains(response, "sidebar-rail__mouse")
        self.assertContains(response, "user-profile__identity")
        self.assertContains(response, "user-role__text")
        self.assertContains(response, "action-rail__stack--vertical")
        self.assertContains(response, "action-rail__stack")
        self.assertContains(response, "action-rail__callback")
        self.assertContains(response, "action-rail__utility")


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
