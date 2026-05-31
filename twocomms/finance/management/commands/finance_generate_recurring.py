"""Management команда для генерації recurring транзакцій — БЛОК 3."""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from finance.services import recurring


class Command(BaseCommand):
    help = 'Генерує планові транзакції на основі recurring правил'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=60,
            help='На скільки днів вперед генерувати транзакції (за замовчуванням 60)',
        )
        parser.add_argument(
            '--user',
            type=str,
            default='system',
            help='Username користувача для аудиту (за замовчуванням system)',
        )

    def handle(self, *args, **options):
        days_ahead = options['days']
        username = options['user']

        # Отримуємо або створюємо системного користувача
        User = get_user_model()
        user, created = User.objects.get_or_create(
            username=username,
            defaults={'is_active': False, 'is_staff': False}
        )

        if created:
            self.stdout.write(
                self.style.WARNING(f'Створено системного користувача: {username}')
            )

        self.stdout.write(f'Генерація recurring транзакцій на {days_ahead} днів вперед...')

        # Обробляємо всі правила
        stats = recurring.process_all_recurring_rules(user=user, days_ahead=days_ahead)

        self.stdout.write(
            self.style.SUCCESS(
                f'✅ Оброблено {stats["rules_processed"]} правил, '
                f'створено {stats["transactions_created"]} транзакцій'
            )
        )
