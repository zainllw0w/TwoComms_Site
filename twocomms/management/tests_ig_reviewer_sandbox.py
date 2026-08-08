"""W1 / IMP-007 — Meta-reviewer в read-only sandbox (F-SEC-004).

Внешний аккаунт из группы «Meta Bot Reviewer» нужен, чтобы Meta могла
посмотреть, как работает приложение. Смотреть — да; управлять живым
продакшеном — нет.

Сейчас reviewer может: глобально запустить и остановить бота, поменять
`ai_enabled` / `receive_via_poll` / `gemini_model` (эти три поля стоят
ВНЕ блока `if not reviewer_mode`), поставить на паузу, скрыть и пометить
«втрачено» реальную карточку клиента.

Инвариант, который закрепляют тесты: reviewer читает, но не мутирует.
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase, override_settings

from management.bot_access import META_REVIEWER_GROUP_NAME
from management.models import IgClient, InstagramBotLog, InstagramBotSettings


@override_settings(ALLOWED_HOSTS=["management.twocomms.shop", "testserver"])
class ReviewerSandboxTests(TestCase):
    def setUp(self):
        group, _ = Group.objects.get_or_create(name=META_REVIEWER_GROUP_NAME)
        self.reviewer = get_user_model().objects.create_user(
            username="meta_reviewer", password="review-pass"
        )
        self.reviewer.groups.add(group)
        self.admin = get_user_model().objects.create_user(
            username="bot_admin", password="admin-pass", is_staff=True
        )
        self.client_card = IgClient.objects.create(
            igsid="5000000001", username="live_client"
        )

    def _login_reviewer(self):
        self.client.force_login(self.reviewer)

    def _post(self, path, data=None):
        return self.client.post(
            path,
            data or {},
            HTTP_HOST="management.twocomms.shop",
            secure=True,
        )

    # ------------------------------------- демо-контроль: можно, но с следом
    def test_reviewer_stop_is_allowed_but_attributed(self):
        """DR-006: демо-контроль сохранён, но перестаёт быть незаметным."""
        settings_row = InstagramBotSettings.load()
        settings_row.is_enabled = True
        settings_row.save(update_fields=["is_enabled"])
        self._login_reviewer()

        with patch("management.bot_views.bot.stop_bot"), patch(
            "management.bot_views.bot.notify_manager"
        ):
            response = self._post("/bot/api/stop/")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            InstagramBotLog.objects.filter(
                event="reviewer_action", detail__contains="meta_reviewer"
            ).exists(),
            "остановка внешним reviewer'ом должна оставлять след с его именем",
        )

    def test_reviewer_start_is_attributed(self):
        self._login_reviewer()

        with patch("management.bot_views.bot.start_bot"), patch(
            "management.bot_views.bot.notify_manager"
        ):
            response = self._post("/bot/api/start/")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            InstagramBotLog.objects.filter(
                event="reviewer_action", detail__contains="bot_start"
            ).exists()
        )

    def test_reviewer_alert_omits_username_but_keeps_local_actor_id(self):
        marker = "private.reviewer@example.com"
        self.reviewer.username = marker
        self.reviewer.save(update_fields=["username"])
        self._login_reviewer()

        with patch("management.bot_views.bot.stop_bot"), patch(
            "management.bot_views.bot.notify_manager"
        ) as notify_manager:
            response = self._post("/bot/api/stop/")

        self.assertEqual(response.status_code, 200)
        alert = notify_manager.call_args.args[0]
        self.assertNotIn(marker, alert)
        self.assertIn(f"Актор ID: {self.reviewer.pk}", alert)
        self.assertIn("Тип збою: bot_stop", alert)

    def test_admin_action_is_not_logged_as_reviewer(self):
        """След reviewer'а не должен появляться от действий администратора."""
        self.client.force_login(self.admin)

        with patch("management.bot_views.bot.start_bot"):
            self._post("/bot/api/start/")

        self.assertFalse(
            InstagramBotLog.objects.filter(event="reviewer_action").exists()
        )

    # ------------------------------- рабочая конфигурация: reviewer не меняет
    def test_reviewer_cannot_change_gemini_model_or_transport(self):
        settings_row = InstagramBotSettings.load()
        settings_row.gemini_model = "gemini-3-flash-preview"
        settings_row.receive_via_poll = False
        settings_row.save(update_fields=["gemini_model", "receive_via_poll"])
        self._login_reviewer()

        with patch("management.bot_views.bot.notify_manager"):
            response = self._post(
                "/bot/api/settings/",
                {
                    "ai_enabled": "on",
                    "gemini_model": "gemini-2.5-flash",
                    "receive_via_poll": "on",
                },
            )

        self.assertEqual(response.status_code, 200)
        settings_row.refresh_from_db()
        self.assertEqual(
            settings_row.gemini_model,
            "gemini-3-flash-preview",
            "рабочая модель Gemini — не демо-переключатель",
        )
        self.assertFalse(
            settings_row.receive_via_poll,
            "транспорт приёма событий — не демо-переключатель",
        )

    def test_admin_can_still_change_gemini_model(self):
        settings_row = InstagramBotSettings.load()
        settings_row.gemini_model = "gemini-3-flash-preview"
        settings_row.save(update_fields=["gemini_model"])
        self.client.force_login(self.admin)

        response = self._post(
            "/bot/api/settings/",
            {"ai_enabled": "on", "gemini_model": "gemini-3.5-flash"},
        )

        self.assertEqual(response.status_code, 200)
        settings_row.refresh_from_db()
        self.assertEqual(settings_row.gemini_model, "gemini-3.5-flash")

    # -------------------------------------------------- реальные карточки
    def test_reviewer_cannot_pause_real_client(self):
        self._login_reviewer()

        response = self._post(
            f"/bot/api/clients/{self.client_card.pk}/pause/"
        )

        self.assertEqual(response.status_code, 403)
        self.client_card.refresh_from_db()
        self.assertFalse(self.client_card.bot_paused)

    def test_reviewer_cannot_hide_real_client(self):
        self._login_reviewer()

        response = self._post(f"/bot/api/clients/{self.client_card.pk}/hide/")

        self.assertEqual(response.status_code, 403)
        self.client_card.refresh_from_db()
        self.assertIsNone(self.client_card.hidden_at)

    def test_reviewer_cannot_mark_client_lost(self):
        self._login_reviewer()

        response = self._post(f"/bot/api/clients/{self.client_card.pk}/lost/")

        self.assertEqual(response.status_code, 403)

    def test_reviewer_cannot_resume_or_unhide(self):
        self._login_reviewer()

        for action in ("resume", "unhide"):
            with self.subTest(action=action):
                response = self._post(
                    f"/bot/api/clients/{self.client_card.pk}/{action}/"
                )
                self.assertEqual(response.status_code, 403)

    # ------------------------------------------------------- чтение живо
    def test_reviewer_can_still_read_status(self):
        self._login_reviewer()

        response = self.client.get(
            "/bot/api/status/",
            HTTP_HOST="management.twocomms.shop",
            secure=True,
        )

        self.assertEqual(response.status_code, 200)

    def test_reviewer_status_redacts_live_diagnostics_and_logs(self):
        settings_row = InstagramBotSettings.load()
        settings_row.page_id = "real-page-id"
        settings_row.last_error = "customer@example.com leaked diagnostic"
        settings_row.save(update_fields=["page_id", "last_error", "updated_at"])
        InstagramBotLog.objects.create(
            level="error",
            event="provider_failure",
            detail="IGSID 5000000001 customer@example.com",
        )
        self._login_reviewer()

        response = self.client.get(
            "/bot/api/status/",
            HTTP_HOST="management.twocomms.shop",
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["log"], [])
        self.assertNotIn("provider_account_id", payload["status"])
        self.assertNotIn("last_error", payload["status"])
        self.assertNotIn("customer@example.com", response.content.decode())

    def test_reviewer_status_is_allowlisted_and_drops_unknown_nested_fields(self):
        marker = "future-private-customer-note-marker"
        self._login_reviewer()

        with patch(
            "management.bot_views.bot.status_snapshot",
            return_value={
                "state": "running",
                "running": True,
                "daemon_online": True,
                "pending": 0,
                "customer_note": {"text": marker},
                "future_sensitive_field": marker,
            },
        ):
            response = self.client.get(
                "/bot/api/status/",
                HTTP_HOST="management.twocomms.shop",
                secure=True,
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["status"],
            {
                "state": "running",
                "running": True,
                "daemon_online": True,
                "pending": 0,
            },
        )
        self.assertNotIn(marker, response.content.decode())

    def test_reviewer_stats_api_is_blocked_before_business_queries(self):
        self._login_reviewer()

        with patch(
            "management.models.InstagramBotMessage.objects.filter"
        ) as message_query:
            response = self.client.get(
                "/bot/api/stats/",
                HTTP_HOST="management.twocomms.shop",
                secure=True,
            )

        self.assertEqual(response.status_code, 403)
        message_query.assert_not_called()
        self.assertNotIn("live_client", response.content.decode())

    def test_reviewer_dashboard_does_not_render_live_stats_panel(self):
        self._login_reviewer()

        response = self.client.get(
            "/bot/",
            HTTP_HOST="management.twocomms.shop",
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertNotIn('data-tab="stats"', body)
        self.assertNotIn('data-panel="stats"', body)

    def test_reviewer_client_list_is_empty_sandbox(self):
        self._login_reviewer()

        response = self.client.get(
            "/bot/api/clients/",
            HTTP_HOST="management.twocomms.shop",
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["clients"], [])
        self.assertTrue(payload["reviewer_sandbox"])
        self.assertNotIn("live_client", response.content.decode())

    # ------------------------------------------- админ не пострадал
    def test_admin_can_still_pause_client(self):
        self.client.force_login(self.admin)

        response = self._post(f"/bot/api/clients/{self.client_card.pk}/pause/")

        self.assertEqual(response.status_code, 200)
        self.client_card.refresh_from_db()
        self.assertTrue(self.client_card.bot_paused)
