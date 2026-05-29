"""Розбір та валідація payload модалок операцій (дохід/витрата/переказ)."""
from __future__ import annotations

import datetime as dt
from decimal import Decimal, InvalidOperation

from django.utils import timezone

from ..models import (
    Account, Category, Counterparty, Project, Tag, Transaction, get_default_company,
)


class PayloadError(ValueError):
    """Помилка валідації payload з повідомленням для користувача."""

    def __init__(self, message, field=None):
        super().__init__(message)
        self.field = field


def _decimal(value, field, *, required=True):
    if value in (None, ''):
        if required:
            raise PayloadError('Вкажіть суму', field)
        return None
    try:
        d = Decimal(str(value).replace(' ', '').replace(',', '.'))
    except (InvalidOperation, ValueError):
        raise PayloadError('Невірна сума', field)
    return d


def _parse_dt(value, *, default_now=False):
    if not value:
        return timezone.now() if default_now else None
    for fmt in ('%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M', '%Y-%m-%d'):
        try:
            naive = dt.datetime.strptime(value, fmt)
            return timezone.make_aware(naive, timezone.get_current_timezone())
        except (ValueError, TypeError):
            continue
    return timezone.now() if default_now else None


def _account(company, value, field, *, required=True):
    if not value:
        if required:
            raise PayloadError('Оберіть рахунок', field)
        return None
    acc = company.accounts.filter(id=value).first()
    if acc is None and required:
        raise PayloadError('Рахунок не знайдено', field)
    if acc and not acc.is_active:
        raise PayloadError('Рахунок неактивний', field)
    return acc


def _optional_fk(model, company, value):
    if not value:
        return None
    return model.objects.filter(company=company, id=value).first()


def _tags(company, raw):
    if not raw:
        return []
    if isinstance(raw, str):
        ids = [v for v in raw.split(',') if v.strip().isdigit()]
    else:
        ids = [v for v in raw if str(v).isdigit()]
    return list(Tag.objects.filter(company=company, id__in=ids))


def parse_transaction_payload(data, *, txn_type):
    """Перетворює POST-дані у kwargs для сервісу transactions.

    txn_type: income | expense | transfer.
    Повертає dict готовий для create_transaction/update_transaction.
    """
    company = get_default_company()
    status = data.get('status') or Transaction.STATUS_ACTUAL
    if status not in dict(Transaction.STATUS_CHOICES):
        status = Transaction.STATUS_ACTUAL

    amount = _decimal(data.get('amount'), 'amount')
    if amount is not None and amount <= 0:
        raise PayloadError('Сума має бути більшою за 0', 'amount')

    date_actual = _parse_dt(data.get('date_actual'), default_now=True)
    date_agreement = _parse_dt(data.get('date_agreement')) if data.get('date_agreement') else None

    kwargs = {
        'type': txn_type,
        'status': status,
        'amount': amount,
        'date_actual': date_actual,
        'date_agreement': date_agreement,
        'comment': (data.get('comment') or '').strip(),
        'project': _optional_fk(Project, company, data.get('project')),
        'tags': _tags(company, data.get('tags')),
    }

    if txn_type == Transaction.TYPE_TRANSFER:
        from_acc = _account(company, data.get('from_account') or data.get('account'), 'from_account')
        to_acc = _account(company, data.get('to_account'), 'to_account')
        if from_acc and to_acc and from_acc.id == to_acc.id:
            raise PayloadError('Рахунки джерела й отримувача мають відрізнятися', 'to_account')
        kwargs['account'] = from_acc
        kwargs['to_account'] = to_acc
        kwargs['currency'] = from_acc.currency if from_acc else company.base_currency
        to_amount = _decimal(data.get('to_amount'), 'to_amount', required=False)
        if from_acc and to_acc and from_acc.currency != to_acc.currency:
            kwargs['to_amount'] = to_amount if to_amount is not None else amount
            rate = _decimal(data.get('exchange_rate'), 'exchange_rate', required=False)
            kwargs['exchange_rate'] = rate
        else:
            kwargs['to_amount'] = amount
    else:
        acc = _account(company, data.get('account'), 'account')
        kwargs['account'] = acc
        kwargs['currency'] = (data.get('currency') or (acc.currency if acc else company.base_currency))
        kwargs['category'] = _optional_fk(Category, company, data.get('category'))
        kwargs['counterparty'] = _optional_fk(Counterparty, company, data.get('counterparty'))

    return kwargs
