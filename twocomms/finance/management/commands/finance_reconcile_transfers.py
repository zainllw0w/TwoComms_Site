"""Management команда для reconcile внутрішніх переказів."""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from finance.models import get_default_company
from finance.services import mono


class Command(BaseCommand):
    help = 'Зливає дублюючі перекази між власними рахунками'

    def add_arguments(self, parser):
        parser.add_argument(
            '--window',
            type=int,
            default=168,
            help='Вікно пошуку в годинах (за замовчуванням 168 = 7 днів)',
        )
        parser.add_argument(
            '--tolerance',
            type=float,
            default=2.0,
            help='Толерантність по сумі в відсотках (за замовчуванням 2.0)',
        )
        parser.add_argument(
            '--user',
            type=str,
            default='system',
            help='Username користувача для аудиту',
        )

    def handle(self, *args, **options):
        window_hours = options['window']
        tolerance = options['tolerance']
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

        company = get_default_company()

        self.stdout.write(
            f'Пошук дублюючих переказів (вікно: {window_hours}год, толерантність: {tolerance}%)...'
        )

        # Запускаємо reconcile
        matched = mono.reconcile_internal_transfers(
            company,
            user=user,
            window_hours=window_hours,
            tolerance_percent=tolerance
        )

        if matched > 0:
            self.stdout.write(
                self.style.SUCCESS(f'✅ Злито {matched} пар переказів')
            )
        else:
            self.stdout.write(
                self.style.WARNING('⚠️ Дублюючих переказів не знайдено')
            )
