"""Команда: ініціалізація компанії та системних категорій + (опційно) демо-дані.

Використання:
    python manage.py finance_seed_demo            # компанія + системні категорії
    python manage.py finance_seed_demo --demo     # + демонстраційні дані
    python manage.py finance_seed_demo --clear     # видалити демо-дані
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from finance.models import get_default_company
from finance.services import demo as demo_service


class Command(BaseCommand):
    help = 'Ініціалізує компанію, системні категорії та (опційно) демо-дані фінансового кабінету.'

    def add_arguments(self, parser):
        parser.add_argument('--demo', action='store_true', help='Створити демонстраційні дані.')
        parser.add_argument('--clear', action='store_true', help='Видалити демонстраційні дані.')

    def handle(self, *args, **options):
        company = get_default_company()
        self.stdout.write(self.style.SUCCESS(f'Компанія: {company.name} (id={company.id})'))

        if options['clear']:
            counts = demo_service.clear_demo(company)
            self.stdout.write(self.style.WARNING(f'Демо-дані видалено: {counts}'))
            return

        demo_service.ensure_system_categories(company)
        self.stdout.write(self.style.SUCCESS('Системні категорії готові.'))

        if options['demo']:
            result = demo_service.seed_demo_company()
            self.stdout.write(self.style.SUCCESS(f'Демо-дані створено: {result}'))
        else:
            self.stdout.write('Демо-дані пропущено (додайте --demo для генерації).')
