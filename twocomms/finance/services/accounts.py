"""Сервіс рахунків: створення, редагування, архівування, сортування,
корекція стартового балансу та залишків (ТЗ 05)."""
from __future__ import annotations

from decimal import Decimal

from django.db import transaction as db_transaction
from django.utils import timezone

from ..models import Account, Transaction, get_default_company
from . import audit as audit_service
from . import balances as balance_service


def create_account(*, user, name, currency='UAH', type='bank',
                    initial_balance=Decimal('0'), initial_balance_date=None) -> Account:
    company = get_default_company()
    last = company.accounts.order_by('-sort_order').first()
    sort_order = (last.sort_order + 1) if last else 0
    acc = Account.objects.create(
        company=company, name=name.strip(), currency=currency, type=type,
        initial_balance=Decimal(initial_balance or 0),
        current_balance=Decimal(initial_balance or 0),
        initial_balance_date=initial_balance_date or timezone.now().date(),
        sort_order=sort_order,
    )
    audit_service.log_action(user, 'create', 'account', acc.id,
                             summary=f'Створено рахунок {acc.name}', company=company)
    return acc


def update_account(account: Account, *, user, **fields) -> Account:
    before = {'name': account.name, 'initial_balance': str(account.initial_balance),
              'currency': account.currency, 'type': account.type}
    initial_changed = 'initial_balance' in fields
    for key, value in fields.items():
        if key == 'initial_balance':
            value = Decimal(value or 0)
        setattr(account, key, value)
    account.save()
    if initial_changed:
        account.recalc_balance(save=True)
    audit_service.log_action(user, 'update', 'account', account.id,
                             summary=f'Оновлено рахунок {account.name}',
                             before=before, company=account.company)
    return account


def archive_account(account: Account, *, user, archived=True) -> Account:
    account.is_archived = archived
    account.is_active = not archived
    account.save(update_fields=['is_archived', 'is_active'])
    audit_service.log_action(user, 'archive' if archived else 'unarchive', 'account',
                             account.id, summary=account.name, company=account.company)
    return account


def delete_account(account: Account, *, user) -> bool:
    """Видалення дозволене лише якщо немає операцій (ТЗ 05 §3)."""
    has_txns = (Transaction.objects.filter(account=account).exists()
                or Transaction.objects.filter(to_account=account).exists())
    if has_txns:
        return False
    name = account.name
    aid = account.id
    company = account.company
    account.delete()
    audit_service.log_action(user, 'delete', 'account', aid,
                             summary=f'Видалено рахунок {name}', company=company)
    return True


@db_transaction.atomic
def reorder_accounts(ordered_ids, *, user) -> None:
    company = get_default_company()
    for index, acc_id in enumerate(ordered_ids):
        Account.objects.filter(company=company, id=acc_id).update(sort_order=index)


@db_transaction.atomic
def correct_balance(account: Account, *, user, target_balance) -> Transaction:
    """Корекційна операція, що доводить залишок до target_balance (ТЗ 05 §10)."""
    from . import transactions as txn_service
    target = Decimal(target_balance)
    diff = target - account.current_balance
    if diff == 0:
        return None
    txn_type = Transaction.TYPE_INCOME if diff > 0 else Transaction.TYPE_EXPENSE
    return txn_service.create_transaction(
        user=user, type=txn_type, amount=abs(diff), account=account,
        currency=account.currency, comment='Коригування залишку', source='manual',
    )


def accounts_overview(company):
    """Дані для екрана керування рахунками."""
    items = []
    for acc in company.accounts.all().order_by('sort_order', 'id'):
        has_txns = (Transaction.objects.filter(account=acc).exists()
                    or Transaction.objects.filter(to_account=acc).exists())
        items.append({
            'id': acc.id, 'name': acc.name, 'type': acc.type,
            'type_display': acc.get_type_display(), 'currency': acc.currency,
            'initial_balance': str(acc.initial_balance),
            'current_balance': str(acc.current_balance),
            'balance_display': balance_service._symbol(acc.currency),
            'is_archived': acc.is_archived, 'is_active': acc.is_active,
            'has_transactions': has_txns,
            'integration': acc.integration.get_provider_display() if acc.integration else None,
            'is_business': acc.is_business,
            'external_kind': acc.external_kind,
            'masked_pan': acc.masked_pan,
            'auto_sync': acc.auto_sync,
            'color': acc.color or '',
            'icon_type': acc.icon_type or '',
            'icon_value': acc.icon_value or '',
            'icon_data': acc.icon_image or '',
        })
    return items
