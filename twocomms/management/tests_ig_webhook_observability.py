"""W2 / IMP-012 — отказ ingress перестаёт быть невидимым (F-CORE-002, F-SEC-007, F-OPS-004).

Контекст из W0: 24–31 июля Meta получила ≈2268 отказов по подписи, из них
908 за один день — то есть приём лежал полностью. В БД от этого осталось
115 строк, потому что `LOG_KEEP_ROWS=500` вычистил остальное, а логгер
`ig_bot` не объявлен в `LOGGING.loggers`, поэтому файлового дубля нет.
Отказ всего входящего контура на шесть дней был технически ненаблюдаем.

Здесь закрепляются три инварианта:
1. Битый payload не исчезает бесследно (F-CORE-002).
2. Логгер `ig_bot` подключён к файловому логу (F-SEC-007).
3. В лог не попадает содержимое сообщения клиента — только метаданные.
"""
import hashlib
import hmac
import json
import os
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from management.models import InstagramBotLog


@override_settings(ALLOWED_HOSTS=["management.twocomms.shop", "testserver"])
class BadPayloadVisibilityTests(TestCase):
    SECRET = "test-secret"

    def _post(self, body: bytes):
        digest = hmac.new(self.SECRET.encode(), body, hashlib.sha256).hexdigest()
        with patch.dict(os.environ, {"IG_APP_SECRET": self.SECRET}, clear=True):
            return self.client.post(
                "/bot/webhook/",
                data=body,
                content_type="application/json",
                HTTP_X_HUB_SIGNATURE_256=f"sha256={digest}",
                HTTP_HOST="management.twocomms.shop",
                secure=True,
            )

    def test_broken_json_still_returns_200(self):
        """Ретрай битого payload не поможет — 200 остаётся осознанным."""
        response = self._post(b"not-json-at-all")

        self.assertEqual(response.status_code, 200)

    def test_broken_json_leaves_exactly_one_error_record(self):
        self._post(b"not-json-at-all")

        errors = list(
            InstagramBotLog.objects.filter(
                level="error", event="webhook_bad_payload"
            )
        )
        self.assertEqual(
            len(errors), 1, "битый payload обязан оставить ровно одну error-запись"
        )

    def test_bad_payload_record_has_diagnostics_but_no_message_text(self):
        secret_text = "мій номер 0501234567"
        body = ('{"broken": "' + secret_text + '"').encode()

        self._post(body)

        record = InstagramBotLog.objects.get(event="webhook_bad_payload")
        self.assertIn(str(len(body)), record.detail, "длина тела нужна для диагностики")
        self.assertNotIn(
            secret_text,
            record.detail,
            "тело webhook содержит PII — в лог оно попадать не должно",
        )
        self.assertNotIn("0501234567", record.detail)

    def test_valid_payload_writes_no_bad_payload_error(self):
        body = json.dumps(
            {"object": "instagram", "entry": []}
        ).encode()

        with patch("management.bot_webhook.bot.record_raw_event"):
            self._post(body)

        self.assertFalse(
            InstagramBotLog.objects.filter(event="webhook_bad_payload").exists()
        )


class IgBotLoggerWiringTests(TestCase):
    """F-SEC-007: `logger.warning('ig_bot: bad signature')` уходил в никуда.

    Проверяем **продакшен-конфигурацию**, а не `test_settings`: последний
    подменяет `LOGGING` пустым словарём, поэтому assert против
    `django.conf.settings` не доказал бы ничего о проде.
    """

    @staticmethod
    def _production_logging():
        import importlib

        return importlib.import_module("twocomms.settings").LOGGING

    def test_ig_bot_logger_is_declared(self):
        loggers = self._production_logging().get("loggers", {})

        self.assertIn(
            "ig_bot",
            loggers,
            "логгер ig_bot должен быть объявлен, иначе отказ ingress не виден в файле",
        )

    def test_ig_bot_logger_has_a_declared_handler(self):
        logging_config = self._production_logging()
        handlers = logging_config["loggers"]["ig_bot"].get("handlers") or []

        self.assertTrue(handlers, "у логгера ig_bot должен быть хотя бы один handler")
        for name in handlers:
            self.assertIn(
                name, logging_config.get("handlers", {}), f"handler {name} не объявлен"
            )

    def test_ig_bot_logger_has_dedicated_rotating_incident_file(self):
        logging_config = self._production_logging()
        handler = logging_config["handlers"].get("ig_bot_file") or {}

        self.assertEqual(handler.get("class"), "logging.handlers.RotatingFileHandler")
        self.assertGreaterEqual(int(handler.get("backupCount") or 0), 12)
        self.assertIn("ig_bot_file", logging_config["loggers"]["ig_bot"]["handlers"])

    def test_ig_bot_logger_level_captures_warnings(self):
        import logging

        level = self._production_logging()["loggers"]["ig_bot"].get("level", "WARNING")
        numeric = logging.getLevelName(level)

        self.assertIsInstance(numeric, int, f"нераспознанный уровень {level!r}")
        self.assertLessEqual(
            numeric,
            logging.WARNING,
            "bad_signature пишется уровнем warning — он должен проходить",
        )


class WebhookErrorRateAlertTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    @patch("management.services.instagram_bot.notify_manager")
    def test_alerts_once_when_4xx_share_is_high(self, notify):
        from management.services import instagram_bot as bot

        for _ in range(4):
            result = bot.record_webhook_response(403, reason="invalid_signature")
            self.assertFalse(result["degraded"])
        result = bot.record_webhook_response(403, reason="invalid_signature")

        self.assertTrue(result["degraded"])
        self.assertEqual(result["errors"], 5)
        self.assertEqual(result["total"], 5)
        self.assertEqual(notify.call_count, 1)
        self.assertFalse(notify.call_args.kwargs["deliver_immediately"])
        self.assertEqual(notify.call_args.kwargs["event_type"], "ig_webhook_4xx_rate")

    @patch("management.services.instagram_bot.notify_manager")
    def test_small_4xx_share_does_not_alert_or_degrade(self, notify):
        from management.services import instagram_bot as bot

        for _ in range(30):
            bot.record_webhook_response(200)
        for _ in range(5):
            result = bot.record_webhook_response(403, reason="invalid_signature")

        self.assertFalse(result["degraded"])
        self.assertLess(result["rate"], 0.25)
        self.assertFalse(notify.called)
        self.assertIsNone(bot.webhook_rejection_status())

    @patch("management.services.instagram_bot.notify_manager")
    def test_alerts_when_rate_crosses_threshold_after_more_than_five_errors(self, notify):
        from management.services import instagram_bot as bot

        for _ in range(20):
            bot.record_webhook_response(200)
        for _ in range(6):
            result = bot.record_webhook_response(403, reason="invalid_signature")
            self.assertFalse(result["degraded"])
        result = bot.record_webhook_response(403, reason="invalid_signature")

        self.assertTrue(result["degraded"])
        self.assertEqual(result["errors"], 7)
        self.assertEqual(result["total"], 27)
        self.assertEqual(notify.call_count, 1)

    @patch("management.services.instagram_bot.notify_manager")
    def test_successful_post_clears_current_degradation_after_rate_recovers(self, _notify):
        from management.services import instagram_bot as bot

        for _ in range(5):
            bot.record_webhook_response(403, reason="invalid_signature")
        self.assertIsNotNone(bot.webhook_rejection_status())
        bot.record_webhook_response(200)
        self.assertIsNotNone(
            bot.webhook_rejection_status(),
            "один успешный webhook не должен скрывать всё ещё высокий 4xx rate",
        )
        for _ in range(16):
            bot.record_webhook_response(200)

        self.assertIsNone(bot.webhook_rejection_status())
