"""
Команда для тестирования Telegram уведомлений
"""
from django.core.management.base import BaseCommand
from orders.telegram_notifications import telegram_notifier


class Command(BaseCommand):
    help = 'Тестирует отправку уведомлений в Telegram'

    def add_arguments(self, parser):
        parser.add_argument(
            '--message',
            type=str,
            help='Сообщение для отправки',
            default='Тестовое сообщение от TwoComms бота'
        )

    def handle(self, *args, **options):
        message = options['message']
        
        if not telegram_notifier.is_configured():
            self.stdout.write(
                self.style.ERROR(
                    'Telegram бот не настроен. Проверьте переменные окружения:\n'
                    '- TELEGRAM_BOT_TOKEN\n'
                    '- TELEGRAM_CHAT_ID'
                )
            )
            return
        
        self.stdout.write('Отправка тестового сообщения...')
        
        success = telegram_notifier.send_message(message)
        
        if success:
            self.stdout.write(
                self.style.SUCCESS('Сообщение успешно отправлено!')
            )
        else:
            self.stdout.write(
                self.style.ERROR('Ошибка при отправке сообщения')
            )
