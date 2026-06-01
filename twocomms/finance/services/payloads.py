"""Розбір та валідація payload модалок операцій (дохід/витрата/переказ)."""
from __future__ import annotations

import datetime as dt
from decimal import Decimal, InvalidOperation

from django.utils import timezone

from ..models import (
    Account, Category, Counterparty, Project, Tag, Transaction, get_default_company,
)
from ..models import RecurrenceRule


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

    # Авто-план: якщо фактична дата у майбутньому — операція стає плановою.
    # (Підтвердження/проведення планової виставляє дату «зараз», тож вона лишається фактичною.)
    if date_actual and date_actual > timezone.now():
        status = Transaction.STATUS_PLANNED

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
    if 'is_business' in data:
        kwargs['is_business'] = str(data.get('is_business')).lower() in ('1', 'true', 'on', 'yes')

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


_FREQ_VALID = {'daily', 'weekly', 'monthly', 'yearly'}


def parse_recurrence_payload(data) -> dict | None:
    """Розбирає налаштування повторення з модалки операції.

    Очікує:
      recurrence            — '' | daily | weekly | monthly | yearly
      recurrence_interval   — кратність (кожні N), за замовчуванням 1
      recurrence_end_mode   — never | until | count
      recurrence_until      — дата (YYYY-MM-DD) для режиму until
      recurrence_count      — ціле для режиму count
      recurrence_title      — людська назва зобов'язання (опційно)

    Повертає dict параметрів для recurring.create_rule_from_transaction або
    None, якщо повторення не задано. Кидає PayloadError при невалідних даних.
    """
    freq = (data.get('recurrence') or '').strip()
    if not freq:
        return None
    if freq not in _FREQ_VALID:
        raise PayloadError('Невідома періодичність повторення', 'recurrence')

    try:
        interval = max(1, int(data.get('recurrence_interval') or 1))
    except (TypeError, ValueError):
        interval = 1

    end_mode = (data.get('recurrence_end_mode') or RecurrenceRule.END_NEVER).strip()
    if end_mode not in dict(RecurrenceRule.END_CHOICES):
        end_mode = RecurrenceRule.END_NEVER

    end_date = None
    count = None
    if end_mode == RecurrenceRule.END_UNTIL:
        raw = data.get('recurrence_until')
        if not raw:
            raise PayloadError('Вкажіть дату завершення повторення', 'recurrence_until')
        try:
            end_date = dt.date.fromisoformat(str(raw)[:10])
        except (ValueError, TypeError):
            raise PayloadError('Невірна дата завершення', 'recurrence_until')
    elif end_mode == RecurrenceRule.END_COUNT:
        try:
            count = int(data.get('recurrence_count') or 0)
        except (TypeError, ValueError):
            count = 0
        if count <= 0:
            raise PayloadError('Вкажіть кількість повторень', 'recurrence_count')

    return {
        'frequency': freq,
        'interval': interval,
        'end_mode': end_mode,
        'end_date': end_date,
        'count': count,
        'title': (data.get('recurrence_title') or '').strip(),
    }

