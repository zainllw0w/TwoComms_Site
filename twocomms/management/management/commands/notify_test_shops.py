import os
from datetime import datetime, time, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

import requests

from management.models import ReminderSent, Shop


def _send_message(token: str, chat_id: int, text: str) -> None:
    if not token or not chat_id:
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        requests.post(url, data={"chat_id": chat_id, "text": text}, timeout=8)
    except Exception:
        return


class Command(BaseCommand):
    help = "Надсилає Telegram-сповіщення, коли у тестового магазину залишилась 1 доба."

    def handle(self, *args, **options):
        now = timezone.localtime(timezone.now())
        tz = timezone.get_current_timezone()

        manager_token = os.environ.get("MANAGER_TG_BOT_TOKEN") or os.environ.get("MANAGEMENT_TG_BOT_TOKEN")
        admin_token = os.environ.get("MANAGEMENT_TG_BOT_TOKEN") or manager_token

        admin_chat_raw = os.environ.get("MANAGEMENT_TG_ADMIN_CHAT_ID")
        try:
            admin_chat_id = int(admin_chat_raw) if admin_chat_raw else None
        except Exception:
            admin_chat_id = None

        qs = Shop.objects.filter(shop_type=Shop.ShopType.TEST, test_connected_at__isnull=False).select_related("managed_by")
        sent_count = 0

        for shop in qs:
            days = int(shop.test_period_days or 14)
            end_date = shop.test_connected_at + timedelta(days=days)
            end_dt = timezone.make_aware(datetime.combine(end_date, time.min), tz)
            remaining = end_dt - now
            if remaining <= timedelta(seconds=0):
                continue
            if remaining > timedelta(days=1):
                continue

            hours_left = max(1, int(remaining.total_seconds() // 3600))
            key = f"testshop-1day-{shop.id}"

            # Manager
            chat_id = None
            try:
                profile = shop.managed_by.userprofile if shop.managed_by else None
                chat_id = int(getattr(profile, "tg_manager_chat_id", None) or 0) or None
            except Exception:
                chat_id = None

            text = (
                "⏳ Тестовий магазин: залишилась 1 доба\n"
                f"Магазин: {shop.name}\n"
                f"Залишилось: {hours_left} год\n"
                "Дія: звʼяжіться та уточніть — продовжують чи повертають товар."
            )

            if chat_id and manager_token and not ReminderSent.objects.filter(key=key, chat_id=chat_id).exists():
                _send_message(manager_token, chat_id, text)
                ReminderSent.objects.create(key=key, chat_id=chat_id)
                sent_count += 1

            # Admin
            if admin_chat_id and admin_token and not ReminderSent.objects.filter(key=key, chat_id=admin_chat_id).exists():
                _send_message(admin_token, admin_chat_id, text)
                ReminderSent.objects.create(key=key, chat_id=admin_chat_id)
                sent_count += 1

        self.stdout.write(self.style.SUCCESS(f"Done. Sent: {sent_count}"))

