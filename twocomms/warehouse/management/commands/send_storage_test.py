"""Send a test broadcast through the Storage bot to verify configuration.

Usage:
    python manage.py send_storage_test                       # to all admins
    python manage.py send_storage_test --evening             # send the actual evening reminder format
    python manage.py send_storage_test --chat-id 123456789   # to a specific chat_id only
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.utils import timezone

from warehouse.services.telegram_storage import (
    build_evening_reminder_keyboard,
    build_evening_reminder_text,
    get_admin_chat_ids,
    get_bot_token,
    send_message,
)


class Command(BaseCommand):
    help = "Send a test message through the Storage bot to verify config + admin list."

    def add_arguments(self, parser):
        parser.add_argument(
            "--chat-id",
            dest="chat_id",
            default=None,
            help="Send only to a single chat_id (skip admin auto-discovery).",
        )
        parser.add_argument(
            "--evening",
            action="store_true",
            help="Use the actual evening reminder layout (with inline keyboard).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Resolve recipients but do not actually send anything.",
        )

    def handle(self, *args, **options):
        token = get_bot_token()
        if not token:
            self.stderr.write(self.style.ERROR(
                "❌ Storage bot token not found. Set one of:\n"
                "   TELEGRAM_STORAGE_BOT_TOKEN, telegram_storage_API"
            ))
            return

        masked = token[:6] + "…" + token[-4:]
        self.stdout.write(self.style.SUCCESS(f"✅ Token loaded: {masked}"))

        if options["chat_id"]:
            chat_ids = [str(options["chat_id"]).strip()]
            self.stdout.write(f"Single recipient: {chat_ids[0]}")
        else:
            chat_ids = get_admin_chat_ids()
            self.stdout.write(f"Auto-discovered {len(chat_ids)} admin chat_id(s):")
            for cid in chat_ids:
                self.stdout.write(f"  • {cid}")

        if not chat_ids:
            self.stderr.write(self.style.WARNING(
                "⚠️  No recipients found. Either:\n"
                "    a) ensure warehouse admins have UserProfile.telegram_id filled,\n"
                "    b) add chat_ids to WarehouseSettings.evening_reminder_chat_ids,\n"
                "    c) set TELEGRAM_STORAGE_CHAT_IDS env (comma-separated)."
            ))
            return

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("--dry-run: not sending."))
            return

        if options["evening"]:
            today = timezone.localdate()
            text = build_evening_reminder_text(
                movements_count=0,
                unverified_count=0,
                today_str=today.strftime("%d.%m.%Y") + " (тест)",
            )
            keyboard = build_evening_reminder_keyboard(
                "https://storage.twocomms.shop/today/"
            )
        else:
            text = (
                "🧪 <b>Тестове повідомлення Storage-бота</b>\n\n"
                f"Час: {timezone.localtime().strftime('%d.%m.%Y %H:%M')}\n"
                "Якщо ви бачите це — бот налаштований коректно і ви у списку адмінів.\n\n"
                "Щоденні вечірні нагадування приходитимуть о 22:00 (Київ)."
            )
            keyboard = None

        sent = 0
        for cid in chat_ids:
            result = send_message(cid, text, reply_markup=keyboard)
            if result and result.get("ok"):
                sent += 1
                self.stdout.write(self.style.SUCCESS(f"  ✅ delivered to {cid}"))
            else:
                self.stderr.write(self.style.ERROR(f"  ❌ failed for {cid}: {result}"))

        self.stdout.write(self.style.SUCCESS(
            f"\n📨 Done: {sent}/{len(chat_ids)} delivered."
        ))
