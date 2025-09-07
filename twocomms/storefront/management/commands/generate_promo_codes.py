"""
Команда для генерации промокодов для маркетинговых кампаний
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from storefront.models import PromoCode
import random
import string

class Command(BaseCommand):
    help = 'Генерирует промокоды для маркетинговых кампаний'

    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=10,
            help='Количество промокодов для генерации'
        )
        parser.add_argument(
            '--discount',
            type=int,
            default=10,
            help='Размер скидки в процентах'
        )
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Количество дней действия промокода'
        )
        parser.add_argument(
            '--prefix',
            type=str,
            default='PROMO',
            help='Префикс для промокода'
        )

    def handle(self, *args, **options):
        count = options['count']
        discount = options['discount']
        days = options['days']
        prefix = options['prefix']

        created_codes = []
        
        for i in range(count):
            # Генерируем уникальный код
            random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            code = f"{prefix}{random_part}"
            
            # Проверяем уникальность
            while PromoCode.objects.filter(code=code).exists():
                random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
                code = f"{prefix}{random_part}"
            
            # Создаем промокод
            promo_code = PromoCode.objects.create(
                code=code,
                discount_percent=discount,
                is_active=True,
                created_at=timezone.now(),
                expires_at=timezone.now() + timedelta(days=days)
            )
            
            created_codes.append(code)
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Успешно создано {count} промокодов:\n' + 
                '\n'.join(created_codes)
            )
        )
