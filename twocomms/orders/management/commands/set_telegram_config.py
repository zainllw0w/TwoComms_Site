"""
Команда для настройки Telegram конфигурации
"""
from django.core.management.base import BaseCommand
import os


class Command(BaseCommand):
    help = 'Настраивает Telegram конфигурацию'

    def add_arguments(self, parser):
        parser.add_argument(
            '--token',
            type=str,
            help='Telegram Bot Token'
        )
        parser.add_argument(
            '--chat-id',
            type=str,
            help='Telegram Chat ID'
        )

    def handle(self, *args, **options):
        token = options.get('token')
        chat_id = options.get('chat_id')
        
        if not token or not chat_id:
            self.stdout.write(
                self.style.ERROR(
                    'Необходимо указать --token и --chat-id\n'
                    'Пример: python manage.py set_telegram_config --token "123456:ABC" --chat-id "123456789"'
                )
            )
            return
        
        # Проверяем формат токена
        if ':' not in token:
            self.stdout.write(
                self.style.ERROR('Неверный формат токена. Токен должен содержать ":"')
            )
            return
        
        # Проверяем формат chat_id
        if not chat_id.isdigit() and not chat_id.startswith('-'):
            self.stdout.write(
                self.style.ERROR('Неверный формат Chat ID. Должен быть числом')
            )
            return
        
        # Устанавливаем переменные окружения
        os.environ['TELEGRAM_BOT_TOKEN'] = token
        os.environ['TELEGRAM_CHAT_ID'] = chat_id
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Telegram конфигурация установлена:\n'
                f'Токен: {token[:10]}...{token[-5:]}\n'
                f'Chat ID: {chat_id}'
            )
        )
        
        # Тестируем подключение
        from orders.telegram_notifications import telegram_notifier
        
        if telegram_notifier.is_configured():
            self.stdout.write(
                self.style.SUCCESS('Конфигурация корректна!')
            )
            
            # Отправляем тестовое сообщение
            success = telegram_notifier.send_message('✅ Telegram бот настроен и работает!')
            if success:
                self.stdout.write(
                    self.style.SUCCESS('Тестовое сообщение отправлено!')
                )
            else:
                self.stdout.write(
                    self.style.ERROR('Ошибка при отправке тестового сообщения')
                )
        else:
            self.stdout.write(
                self.style.ERROR('Конфигурация некорректна')
            )
