from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path

from django.template import loader
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.urls import resolve

from management import context_processors as management_context_processors
from management.forms import CommercialOfferEmailForm


class _DummyUser:
    def __init__(self):
        self.id = 1
        self.pk = 1
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

    def __int__(self):
        return int(self.id)


@override_settings(
    ROOT_URLCONF="twocomms.urls_management",
    ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1", "management.twocomms.shop"],
)
class ManagementTemplateRegressionTests(SimpleTestCase):
    databases = {"default"}

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
                    "management_shell_stats_url": "/stats/",
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

    def test_contracts_template_bootstraps_history_for_js_cache(self):
        template = loader.get_template("management/contracts.html")
        request = self._build_request("/contracts/")

        with patch.object(management_context_processors, "management_shell_context", return_value={}):
            html = template.render(
                {
                    "contract_date_display": "18 березня 2026",
                    "contracts_history": [
                        {
                            "id": 17,
                            "contract_number": "TC-17/2026",
                            "contract_date": "18.03.2026",
                            "created_at": "18.03.2026 14:20",
                            "realizer_name": "Test Manager",
                            "product_title": "Худі",
                            "total_sum": 1350,
                            "review_status": "draft",
                            "review_reject_reason": "",
                            "is_approved": False,
                            "download_url": "/contracts/17/download/",
                        }
                    ],
                    "drop_hoodie_price": 1350,
                    "drop_tee_price": 570,
                    "hoodie_products": [],
                    "next_contract_number": "TC-18/2026",
                    "prefill_payload": {},
                    "tshirt_products": [],
                },
                request=request,
            )

        self.assertIn('id="contracts-history-data"', html)
        self.assertIn('"contract_number": "TC-17/2026"', html)
        self.assertIn("hydrateInitialContracts();", html)

    def test_commercial_offer_template_uses_deferred_bootstrap_marker(self):
        template = loader.get_template("management/commercial_offer_email.html")
        request = self._build_request("/commercial-offer/email/")
        form = CommercialOfferEmailForm(user=request.user)

        with patch.object(management_context_processors, "management_shell_context", return_value={}):
            html = template.render(
                {
                    "cp_tab": "email",
                    "form": form,
                    "gallery_edgy_json": "[]",
                    "gallery_neutral_json": "[]",
                    "logs": [],
                    "messenger_context": {
                        "links": {
                            "catalog": "",
                            "dropship": "",
                            "general_tg": "",
                            "wholesale": "",
                        },
                        "manager": {
                            "name": "Template Admin",
                            "phone": "",
                            "telegram": "",
                        },
                        "pricing": {
                            "dropFixed": {"hoodie": 1350, "tee": 570},
                            "dropshipLoyaltyStep": 10,
                            "maxDropDiscount": 120,
                            "optTiers": {},
                            "retailExamples": {"hoodie": 1912, "tee": 880},
                        },
                    },
                    "preview_light_text": "Preview light",
                    "preview_mode": "VISUAL",
                    "preview_preheader": "Preview preheader",
                    "preview_subject": "Preview subject",
                    "preview_visual_html": "<p>Preview visual</p>",
                    "send_error": "",
                    "sent_success": False,
                },
                request=request,
            )

        self.assertIn("function scheduleCommercialBootstrapWarmups()", html)
        self.assertIn("scheduleCommercialBootstrapWarmups();", html)

    def test_management_shell_script_guards_against_stale_navigation(self):
        script = Path("twocomms/twocomms_django_theme/static/js/management-shell.js").read_text()

        self.assertIn("AbortController", script)
        self.assertIn("navigationRequestId", script)
        self.assertIn("requestId !== navigationRequestId", script)

    def test_parsing_dashboard_script_avoids_forced_form_resync_on_each_poll(self):
        script = Path("twocomms/management/templates/management/parsing.html").read_text()

        self.assertIn("hasAppliedInitialJobToForm", script)
        self.assertIn("applyPayload(payload, { syncForm: false });", script)
        self.assertIn("applyPayload(err.payload, { syncForm: true });", script)

    def test_parsing_dashboard_script_does_not_schedule_step_while_step_is_in_progress(self):
        script = Path("twocomms/management/templates/management/parsing.html").read_text()

        self.assertIn("const canScheduleStep = () => Boolean(activeJob && activeJob.status === 'running' && !activeJob.is_step_in_progress);", script)
        self.assertIn("if (canScheduleStep()) {", script)

    def test_parsing_dashboard_script_refreshes_usage_on_a_slower_cadence(self):
        script = Path("twocomms/management/templates/management/parsing.html").read_text()

        self.assertIn("const USAGE_REFRESH_INTERVAL_MS = 60000;", script)
        self.assertIn("if (shouldRefreshUsage()) params.set('include_usage', '1');", script)

    def test_parsing_dashboard_exposes_quick_moderation_action_buttons(self):
        html = Path("twocomms/management/templates/management/parsing.html").read_text(encoding="utf-8")

        self.assertIn("quick-approve-moderation", html)
        self.assertIn("quick-reject-moderation", html)
        self.assertIn("moderation-action-btn--icon", html)
        self.assertIn('aria-label="Підтвердити"', html)
        self.assertIn('aria-label="Не підходить"', html)
        self.assertIn('data-icon="approve"', html)
        self.assertIn('data-icon="reject"', html)
        self.assertIn("submitModerationAction(", html)

    def test_parsing_dashboard_exposes_compact_moderation_row_layout(self):
        html = Path("twocomms/management/templates/management/parsing.html").read_text(encoding="utf-8")

        self.assertIn("moderation-cell__primary", html)
        self.assertIn("moderation-cell__secondary", html)
        self.assertIn("moderation-actions__primary", html)
        self.assertIn("moderation-actions__quick", html)
        self.assertIn("moderation-shop__summary", html)
        self.assertIn("moderation-site__primary", html)
        self.assertIn("moderation-action-btn--icon", html)
        self.assertIn('aria-label="Підтвердити"', html)
        self.assertIn('aria-label="Не підходить"', html)
        self.assertIn('data-icon=\"approve\"', html)
        self.assertIn('data-icon=\"reject\"', html)

    def test_base_template_skips_reminder_poll_when_page_is_hidden(self):
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
                    "management_shell_stats_url": "/stats/",
                    "management_shell_today_callbacks": 0,
                    "management_shell_urgent_callbacks": 0,
                    "progress_clients_pct": 0,
                    "progress_points_pct": 0,
                    "reminders": [],
                    "user_points_today": 0,
                },
                request=request,
            )

        self.assertIn("if (document.hidden) return;", html)

    def test_base_template_uses_generic_help_popover_scope_instead_of_daily_stats_only(self):
        html = Path("twocomms/management/templates/management/base.html").read_text()

        self.assertIn("data-help-scope", html)
        self.assertIn("closest('[data-help-scope]')", html)
        self.assertNotIn("closest('.daily-stats-head')", html)

    def test_home_template_uses_text_date_inputs_and_one_minute_followup_floor(self):
        html = Path("twocomms/management/templates/management/home.html").read_text(encoding="utf-8")

        self.assertIn('<input type="text" id="next_call_date" name="next_call_date"', html)
        self.assertIn('<input type="text" id="process_next_call_date" name="next_call_date"', html)
        self.assertIn('inputmode="numeric"', html)
        self.assertIn("nextAllowed.setMinutes(nextAllowed.getMinutes() + 1);", html)
        self.assertNotIn("nextAllowed.setMinutes(nextAllowed.getMinutes() + 30);", html)
        self.assertNotIn("const minuteStep = 5;", html)

    def test_management_css_centers_next_call_stack(self):
        css = Path("twocomms/twocomms_django_theme/static/css/management.css").read_text(encoding="utf-8")

        self.assertIn(".cell-next-call {", css)
        self.assertIn("text-align: center;", css)
        self.assertIn("justify-items: center;", css)
        self.assertIn("justify-content: center;", css)

    def test_home_template_confirms_no_follow_selection_before_closing_followup(self):
        html = Path("twocomms/management/templates/management/home.html").read_text(encoding="utf-8")

        self.assertIn("confirmNoFollowSelection", html)
        self.assertIn("Неконверсійний клієнт закриє follow-up для цієї картки.", html)
