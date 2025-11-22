"""
Management команда для установки Telegram webhook
"""
from django.core.management.base import BaseCommand
from django.conf import settings
from accounts.telegram_bot import telegram_bot
import requests


class Command(BaseCommand):
    help = 'Устанавливает или проверяет Telegram webhook'

    def add_arguments(self, parser):
        parser.add_argument(
            '--check-only',
            action='store_true',
            help='Только проверить статус webhook, не устанавливать',
        )
        parser.add_argument(
            '--url',
            type=str,
            help='URL для webhook (по умолчанию: https://twocomms.shop/accounts/telegram/webhook/)',
        )

    def handle(self, *args, **options):
        check_only = options.get('check_only', False)
        webhook_url = options.get('url') or 'https://twocomms.shop/accounts/telegram/webhook/'
        
        self.stdout.write("=" * 60)
        self.stdout.write(self.style.SUCCESS("ПРОВЕРКА И НАСТРОЙКА TELEGRAM WEBHOOK"))
        self.stdout.write("=" * 60)
        self.stdout.write("")
        
        # 1. Проверка токена
        token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
        if not token:
            self.stdout.write(self.style.ERROR("❌ Токен бота не найден!"))
            self.stdout.write("   Установите переменную окружения TELEGRAM_BOT_TOKEN")
            return
        self.stdout.write(self.style.SUCCESS(f"✅ Токен найден: {token[:10]}...{token[-5:]}"))
        self.stdout.write("")
        
        # 2. Проверка текущего статуса
        self.stdout.write("2. Проверка текущего статуса webhook...")
        webhook_info = telegram_bot.get_webhook_info()
        
        if webhook_info and webhook_info.get('ok'):
            result = webhook_info.get('result', {})
            current_url = result.get('url', '')
            pending = result.get('pending_update_count', 0)
            last_error = result.get('last_error_message', '')
            last_error_date = result.get('last_error_date', 0)
            
            if current_url:
                self.stdout.write(f"   Текущий URL: {current_url}")
                self.stdout.write(f"   Ожидающих обновлений: {pending}")
                if last_error:
                    self.stdout.write(self.style.ERROR(f"   ❌ Последняя ошибка: {last_error}"))
                    if last_error_date:
                        from datetime import datetime
                        error_time = datetime.fromtimestamp(last_error_date)
                        self.stdout.write(f"   Время ошибки: {error_time}")
            else:
                self.stdout.write(self.style.WARNING("   ⚠️  Webhook не установлен"))
        else:
            self.stdout.write(self.style.ERROR("   ❌ Не удалось получить информацию о webhook"))
        self.stdout.write("")
        
        if check_only:
            return
        
        # 3. Установка webhook
        self.stdout.write(f"3. Установка webhook на: {webhook_url}")
        
        if webhook_info and webhook_info.get('ok'):
            result = webhook_info.get('result', {})
            if result.get('url') == webhook_url:
                self.stdout.write(self.style.SUCCESS("   ✅ Webhook уже установлен на правильный URL"))
            else:
                if telegram_bot.set_webhook(webhook_url):
                    self.stdout.write(self.style.SUCCESS("   ✅ Webhook установлен успешно"))
                else:
                    self.stdout.write(self.style.ERROR("   ❌ Не удалось установить webhook"))
        else:
            if telegram_bot.set_webhook(webhook_url):
                self.stdout.write(self.style.SUCCESS("   ✅ Webhook установлен успешно"))
            else:
                self.stdout.write(self.style.ERROR("   ❌ Не удалось установить webhook"))
        self.stdout.write("")
        
        # 4. Финальная проверка
        self.stdout.write("4. Финальная проверка...")
        webhook_info = telegram_bot.get_webhook_info()
        if webhook_info and webhook_info.get('ok'):
            result = webhook_info.get('result', {})
            if result.get('url') == webhook_url:
                self.stdout.write(self.style.SUCCESS("   ✅ Webhook установлен и работает!"))
            else:
                self.stdout.write(self.style.ERROR("   ❌ Webhook не установлен правильно"))
        
        self.stdout.write("")
        self.stdout.write("=" * 60)



