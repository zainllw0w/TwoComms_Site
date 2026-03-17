from types import SimpleNamespace
from unittest.mock import patch

from django.template import loader
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.urls import resolve

from management import context_processors as management_context_processors


class _DummyUser:
    def __init__(self):
        self.is_authenticated = True
        self.is_staff = True
        self.username = "template_admin"
        self.email = "template-admin@example.com"
        self.userprofile = SimpleNamespace(
            avatar=None,
            birth_date=None,
            city="Kyiv",
            email="template-admin@example.com",
            full_name="Template Admin",
            instagram="",
            manager_base_salary_uah=0,
            manager_commission_percent=0,
            manager_position="Адміністратор",
            payment_details="",
            phone="",
            tg_manager_alert_15m=True,
            tg_manager_alert_5m=True,
            tg_manager_alert_due_now=True,
            tg_manager_alert_missed_callback=True,
            tg_manager_alert_report_late=True,
            tg_manager_chat_id=None,
            tg_manager_critical_advice_enabled=True,
            tg_manager_daily_advice_enabled=True,
            tg_manager_username="",
            viber="",
            whatsapp="",
        )

    def get_full_name(self):
        return "Template Admin"


@override_settings(
    ROOT_URLCONF="twocomms.urls_management",
    ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1", "management.twocomms.shop"],
)
class ManagementTemplateRegressionTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _build_request(self, path: str):
        request = self.factory.get(path, HTTP_HOST="management.twocomms.shop")
        request.user = _DummyUser()
        request.resolver_match = resolve(path)
        return request

    def test_base_shell_renders_without_processed_today_fallback_context(self):
        template = loader.get_template("management/base.html")
        request = self._build_request("/shops/")

        with patch.object(management_context_processors, "management_shell_context", return_value={}):
            html = template.render(
                {
                    "manager_bot_username": "",
                    "management_shell_daily_zone": "warning",
                    "management_shell_duplicate_reviews": 0,
                    "management_shell_has_active_payout_request": False,
                    "management_shell_mosaic_label": "Накопичуємо дані",
                    "management_shell_mosaic_meta": "Потрібно щонайменше 20 обробок для стабільного показу.",
                    "management_shell_mosaic_ready": False,
                    "management_shell_payout_available": 0,
                    "management_shell_payout_url": "/payouts/",
                    "management_shell_processed_total": 0,
                    "management_shell_role_label": "Адміністратор",
                    "management_shell_stats_url": "/stats/admin/",
                    "management_shell_today_callbacks": 0,
                    "management_shell_urgent_callbacks": 0,
                    "progress_clients_pct": 0,
                    "progress_points_pct": 0,
                    "reminders": [],
                    "user_points_today": 0,
                },
                request=request,
            )

        self.assertIn('id="clients-legend">0<', html)
        self.assertIn("daily-stats", html)

    def test_contracts_template_compiles(self):
        template = loader.get_template("management/contracts.html")
        self.assertIsNotNone(template)
