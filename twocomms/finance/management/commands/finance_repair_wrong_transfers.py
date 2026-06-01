"""Відкат хибно-конвертованих внутрішніх переказів назад у витрати.

Попередній reconcile зводив витрату+дохід у переказ за часом+сумою (нестрого),
через що переказ на ЧУЖУ картку/ФОП (іншій людині) міг помилково стати
«внутрішнім переказом на власний ФОП». Внутрішнім переказом вважаємо ЛИШЕ той,
де ``counter_iban`` витрати збігається з IBAN власного рахунку-отримувача.

Ця команда повертає у ВИТРАТИ всі integration-перекази, де власність призначення
не підтверджена (counter_iban порожній або не дорівнює IBAN to_account). Видалений
колись зустрічний дохід відновиться при наступній синхронізації виписки.

Запуск:  python manage.py finance_repair_wrong_transfers [--dry-run]
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction as db_transaction

from finance.models import Transaction, get_default_company
from finance.services import transactions as txn_service


class Command(BaseCommand):
    help = 'Повертає хибні внутрішні перекази (на чужі рахунки) назад у витрати'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **opts):
        dry = opts.get('dry_run')
        company = get_default_company()
        reverted = 0
        qs = (Transaction.objects.filter(
                company=company, source='integration', type=Transaction.TYPE_TRANSFER)
              .select_related('account', 'to_account'))
        for t in qs:
            ed = t.external_data or {}
            ci = ed.get('counter_iban', '')
            to_iban = t.to_account.iban if t.to_account else ''
            confirmed_own = bool(ci and to_iban and ci == to_iban)
            if confirmed_own:
                continue  # справжній власний переказ — лишаємо

            acc = t.account
            self.stdout.write(
                f'#{t.id} {t.date_actual:%Y-%m-%d} {t.amount} '
                f'{acc.name if acc else "?"} → {t.to_account.name if t.to_account else "?"} '
                f'(counter_iban={ci or "-"}) → ВИТРАТА | {t.comment[:30]}')
            if dry:
                reverted += 1
                continue

            # Чистимо службові маркери reconcile.
            clean = dict(ed)
            for k in ('consumed_external_ids', 'matched_income_external_id',
                      'matched_income_amount', 'matched_income_account_id',
                      'matched_income_date'):
                clean.pop(k, None)
            with db_transaction.atomic():
                txn_service.update_transaction(
                    t, user=None,
                    type=Transaction.TYPE_EXPENSE,
                    to_account=None, to_amount=None,
                    category=None,
                    is_business=bool(acc.is_business) if acc else False,
                    external_data=clean,
                )
            reverted += 1

        prefix = '[dry-run] ' if dry else ''
        self.stdout.write(self.style.SUCCESS(
            f'{prefix}Повернуто у витрати: {reverted}'))
