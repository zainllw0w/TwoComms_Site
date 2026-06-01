"""Переводить hold-операції monobank зі статусу draft у actual.

Раніше hold-операції (заблоковані кошти) імпортувались як draft і не
враховувались у звітах, хоча кошти банком уже зняті. Команда виправляє наявні
дані: integration-транзакції зі status=draft і external_data.hold=True → actual
(з перерахунком балансів задіяних рахунків).

Запуск:  python manage.py finance_fix_hold_drafts [--dry-run]
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from finance.models import Transaction, get_default_company
from finance.services import transactions as txn_service


class Command(BaseCommand):
    help = 'Переводить hold-draft операції monobank у actual (входять у звіти/баланс)'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **opts):
        dry = opts.get('dry_run')
        company = get_default_company()
        qs = Transaction.objects.filter(
            company=company, source='integration',
            status=Transaction.STATUS_DRAFT)
        fixed = 0
        for txn in qs:
            if not (txn.external_data or {}).get('hold'):
                continue
            self.stdout.write(
                f'  #{txn.id} {txn.type} {txn.amount} {txn.currency} '
                f'{txn.date_actual:%Y-%m-%d} → actual | {txn.comment[:30]}')
            if not dry:
                txn_service.update_transaction(
                    txn, user=None, status=Transaction.STATUS_ACTUAL)
            fixed += 1
        prefix = '[dry-run] ' if dry else ''
        self.stdout.write(self.style.SUCCESS(f'{prefix}Переведено у actual: {fixed}'))
