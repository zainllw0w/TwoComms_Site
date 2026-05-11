"""Встановлює Telegram webhook для Storage-бота."""
from __future__ import annotations

import os

from django.conf import settings
from django.core.management.base import BaseCommand

from warehouse.services.telegram_storage import (
    get_bot_token,
    get_webhook_info,
    set_webhook,
)


class Command(BaseCommand):
    help = "Встановлює (або перевіряє) Telegram webhook для Storage-бота"

    def add_arguments(self, parser):
        parser.add_argument(
            "--check-only",
            action="store_true",
            help="Тільки перевірити поточний стан webhook'а, не встановлювати",
        )
        parser.add_argument(
            "--url",
            type=str,
            default=None,
            help="URL для webhook (за замовчуванням: <WAREHOUSE_SUBDOMAIN_URL>/tg/webhook/<secret>/)",
        )

    def handle(self, *args, **options):
        token = get_bot_token()
        if not token:
            self.stderr.write(self.style.ERROR("TELEGRAM_STORAGE_BOT_TOKEN не задано"))
            return

        secret = (
            os.environ.get("TELEGRAM_STORAGE_WEBHOOK_SECRET")
            or getattr(settings, "TELEGRAM_STORAGE_WEBHOOK_SECRET", "")
            or ""
        )
        if not secret:
            self.stdout.write(
                self.style.WARNING(
                    "TELEGRAM_STORAGE_WEBHOOK_SECRET порожній — webhook буде створений без секрету. "
                    "Рекомендую задати випадковий рядок (>= 32 символи)."
                )
            )

        base = getattr(settings, "WAREHOUSE_SUBDOMAIN_URL", "https://storage.twocomms.shop").rstrip("/")
        webhook_url = options.get("url") or f"{base}/tg/webhook/{secret or 'no-secret'}/"

        info = get_webhook_info()
        if info and info.get("ok"):
            current = info.get("result", {})
            current_url = current.get("url") or "(none)"
            pending = current.get("pending_update_count", 0)
            last_err = current.get("last_error_message", "")
            self.stdout.write(f"Поточний URL:        {current_url}")
            self.stdout.write(f"Очікуючих апдейтів:  {pending}")
            if last_err:
                self.stdout.write(self.style.WARNING(f"Остання помилка:    {last_err}"))
        else:
            self.stdout.write(self.style.WARNING("Не вдалося отримати webhook info"))

        if options.get("check_only"):
            return

        self.stdout.write(f"\nВстановлюю webhook на: {webhook_url}")
        result = set_webhook(webhook_url, secret_token=secret or None)
        if result and result.get("ok"):
            self.stdout.write(self.style.SUCCESS("✅ Webhook встановлено"))
        else:
            self.stdout.write(
                self.style.ERROR(
                    f"❌ Не вдалося встановити webhook: {result}"
                )
            )
