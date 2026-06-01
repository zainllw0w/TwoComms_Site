"""Backfill авто-категорій за MCC для вже імпортованих транзакцій monobank.

Призначає finance.Category витратам без категорії на основі MCC-групи. Правила
користувача мають пріоритет — транзакції з уже встановленою категорією не
чіпаємо. Запуск:  python manage.py finance_categorize_mcc [--dry-run]
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from finance.models import Transaction, get_default_company
from finance.services import mcc as mcc_mod


class Command(BaseCommand):
    help = 'Призначає категорії за MCC витратам без категорії (monobank)'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **opts):
        dry = opts.get('dry_run')
        company = get_default_company()
        qs = (Transaction.objects.filter(
                company=company, type=Transaction.TYPE_EXPENSE,
                category__isnull=True)
              .exclude(mcc__isnull=True))
        by_group: dict = {}
        updated = 0
        for txn in qs.iterator():
            cat = mcc_mod.get_or_create_category_for_mcc(company, txn.mcc)
            if cat is None:
                continue
            by_group[cat.name] = by_group.get(cat.name, 0) + 1
            if not dry:
                Transaction.objects.filter(pk=txn.pk).update(category=cat)
            updated += 1

        for name, cnt in sorted(by_group.items(), key=lambda x: -x[1]):
            self.stdout.write(f'  {name}: {cnt}')
        prefix = '[dry-run] ' if dry else ''
        self.stdout.write(self.style.SUCCESS(f'{prefix}Категоризовано: {updated}'))
