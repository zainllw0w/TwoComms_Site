"""Разовий ремонт балансів рахунків (виправлення дрейфу).

Причина дрейфу: reconcile_internal_transfers мутував транзакції вже після
фіксації initial_balance, а cron не робив фінального back-calc. Команда
відновлює коректний initial_balance:

- integration-рахунки: беремо останній достовірний ``balance_after`` зі своєї
  виписки (де ``account == рахунок``; перекази, отримані з чужого рахунку, мають
  чужий balance_after — їх пропускаємо) і доводимо current_balance до нього;
- manual-рахунки без руху, де current != initial: вирівнюємо initial = current,
  щоб recalc не «обнуляв» вручну виставлений залишок.

Запуск:  python manage.py finance_repair_balances [--dry-run]
"""
from __future__ import annotations

from decimal import Decimal

from django.core.management.base import BaseCommand

from finance.models import Account, Transaction, get_default_company


class Command(BaseCommand):
    help = 'Виправляє дрейф балансів рахунків (initial back-calc до банк-балансу)'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Лише показати, не змінювати')

    def handle(self, *args, **opts):
        dry = opts.get('dry_run')
        company = get_default_company()
        fixed = 0
        for acc in company.accounts.all():
            # recalc_balance(save=False) мутує acc.current_balance у пам'яті —
            # тож зберігаємо оригінал ДО виклику.
            original_current = acc.current_balance
            recomputed = acc.recalc_balance(save=False)
            has_txns = (Transaction.objects.filter(account=acc).exists()
                        or Transaction.objects.filter(to_account=acc).exists())

            target = None
            if acc.external_account_id:
                # Останній достовірний bank balance_after зі своєї виписки.
                last = (Transaction.objects.filter(
                            status=Transaction.STATUS_ACTUAL, account=acc)
                        .exclude(external_data__balance_after__isnull=True)
                        .order_by('-date_actual', '-id').first())
                if last and (last.external_data or {}).get('balance_after') is not None:
                    target = (Decimal(int(last.external_data['balance_after']))
                              / Decimal('100')).quantize(Decimal('0.01'))
            elif not has_txns and original_current != recomputed:
                # Manual-рахунок без руху: зберігаємо те, що бачить користувач.
                target = original_current

            if target is None:
                continue

            # Доводимо initial так, щоб current == target.
            new_initial = (acc.initial_balance + (target - recomputed)).quantize(Decimal('0.01'))
            if new_initial == acc.initial_balance:
                continue

            self.stdout.write(
                f'{acc.name[:30]:30} current {acc.current_balance} → {target} '
                f'(initial {acc.initial_balance} → {new_initial})')
            if not dry:
                acc.initial_balance = new_initial
                acc.save(update_fields=['initial_balance'])
                acc.recalc_balance(save=True)
            fixed += 1

        prefix = '[dry-run] ' if dry else ''
        self.stdout.write(self.style.SUCCESS(f'{prefix}Виправлено рахунків: {fixed}'))
