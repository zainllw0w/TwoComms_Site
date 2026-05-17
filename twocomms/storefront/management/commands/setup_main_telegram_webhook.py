"""
Management-команда для (пере)встановлення webhook головного Telegram-бота.

Викликає `setWebhook` із параметром `secret_token` (якщо задано
TELEGRAM_BOT_WEBHOOK_SECRET у середовищі), а також `allowed_updates=["message"]`
щоб бот точно отримував контактні апдейти.

Використання:
    python manage.py setup_main_telegram_webhook
    python manage.py setup_main_telegram_webhook --url https://twocomms.shop/accounts/telegram/webhook/
    python manage.py setup_main_telegram_webhook --check
"""

from __future__ import annotations

import json
import os

import requests
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Налаштувати webhook головного Telegram-бота (з secret_token, якщо задано)."

    DEFAULT_WEBHOOK_URL = "https://twocomms.shop/accounts/telegram/webhook/"

    def add_arguments(self, parser):
        parser.add_argument(
            "--url",
            default=self.DEFAULT_WEBHOOK_URL,
            help="URL webhook'а (за замовчуванням twocomms.shop/accounts/telegram/webhook/).",
        )
        parser.add_argument(
            "--check",
            action="store_true",
            help="Тільки показати поточну конфігурацію (`getWebhookInfo`), не змінювати.",
        )

    def handle(self, *args, **opts):
        token = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
        if not token:
            self.stderr.write(self.style.ERROR("❌ TELEGRAM_BOT_TOKEN не задано."))
            return

        # Перевіряємо що бот валідний і збираємо username
        try:
            me_resp = requests.get(
                f"https://api.telegram.org/bot{token}/getMe", timeout=10
            ).json()
        except Exception as exc:
            self.stderr.write(self.style.ERROR(f"❌ getMe failed: {exc}"))
            return
        if not me_resp.get("ok"):
            self.stderr.write(self.style.ERROR(f"❌ getMe error: {me_resp}"))
            return
        bot = me_resp.get("result", {})
        bot_username = bot.get("username", "")
        self.stdout.write(self.style.NOTICE(
            f"✅ Бот: @{bot_username} (id={bot.get('id')}, name={bot.get('first_name')})"
        ))

        # getWebhookInfo
        try:
            info = requests.get(
                f"https://api.telegram.org/bot{token}/getWebhookInfo", timeout=10
            ).json()
        except Exception as exc:
            self.stderr.write(self.style.ERROR(f"❌ getWebhookInfo failed: {exc}"))
            return
        info_result = info.get("result", {})
        self.stdout.write(self.style.NOTICE("📋 Поточна конфігурація webhook:"))
        self.stdout.write(json.dumps(info_result, ensure_ascii=False, indent=2))

        if opts["check"]:
            return

        webhook_url = opts["url"]
        secret_token = (os.environ.get("TELEGRAM_BOT_WEBHOOK_SECRET") or "").strip()

        # setWebhook
        payload = {
            "url": webhook_url,
            "allowed_updates": ["message", "callback_query"],
            "drop_pending_updates": False,
        }
        if secret_token:
            payload["secret_token"] = secret_token

        try:
            resp = requests.post(
                f"https://api.telegram.org/bot{token}/setWebhook",
                json=payload,
                timeout=15,
            ).json()
        except Exception as exc:
            self.stderr.write(self.style.ERROR(f"❌ setWebhook failed: {exc}"))
            return

        if resp.get("ok"):
            self.stdout.write(self.style.SUCCESS(
                f"✅ Webhook встановлено: {webhook_url}"
                + (" (з secret_token)" if secret_token else " (без secret_token)")
            ))
        else:
            self.stderr.write(self.style.ERROR(f"❌ setWebhook error: {resp}"))

        # Optional: підказка про bot_username
        if bot_username:
            self.stdout.write(self.style.NOTICE(
                f"💡 Для deep-link верифікації Telegram у формі кастомного принта "
                f"задайте TELEGRAM_BOT_USERNAME={bot_username} (або залиште пустим — "
                f"воно буде підтягуватись через getMe з кешем 10хв)."
            ))
