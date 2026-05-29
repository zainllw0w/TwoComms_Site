"""Баланси та прогноз: єдине джерело правди для лівої панелі й розрахунків."""
from __future__ import annotations

from decimal import Decimal

from django.db import models
from django.utils import timezone

from ..models import Account, Transaction
from . import currency as currency_service


def recalc_account_balance(account: Account) -> Decimal:
    """Перерахунок фактичного балансу одного рахунку."""
    return account.recalc_balance(save=True)


def recalc_all_balances(company) -> None:
    """Перерахунок усіх рахунків компанії (напр. після імпорту)."""
    for account in company.accounts.all():
        account.recalc_balance(save=True)


def total_actual_balance(company, on_date=None) -> Decimal:
    """Сума фактичних залишків усіх активних рахунків у базовій валюті."""
    total = Decimal('0')
    accounts = company.accounts.filter(is_active=True, is_archived=False)
    for acc in accounts:
        total += currency_service.convert(company, acc.current_balance, acc.currency,
                                          company.base_currency, on_date)
    return total.quantize(Decimal('0.01'))


def planned_totals(company, date_from, date_to):
    """Планові доходи/витрати за період у базовій валюті.

    Витрати повертаються від'ємними (для відображення у панелі).
    """
    qs = Transaction.objects.filter(
        company=company, status=Transaction.STATUS_PLANNED,
        date_actual__date__gte=date_from, date_actual__date__lte=date_to,
    )
    income = Decimal('0')
    expense = Decimal('0')
    for t in qs:
        base = t.amount_base or currency_service.convert(company, t.amount, t.currency)
        if t.type == Transaction.TYPE_INCOME:
            income += base
        elif t.type == Transaction.TYPE_EXPENSE:
            expense += base
    return {'income': income.quantize(Decimal('0.01')),
            'expense': (-expense).quantize(Decimal('0.01'))}


def forecast_balance(company, date_from, date_to) -> Decimal:
    """Баланс з урахуванням майбутніх планових платежів за період (§2.4)."""
    base = total_actual_balance(company)
    planned = planned_totals(company, date_from, date_to)
    return (base + planned['income'] + planned['expense']).quantize(Decimal('0.01'))


def account_sidebar_data(company):
    """Дані рахунків для лівої панелі (назва + відображуваний баланс)."""
    items = []
    for acc in company.accounts.filter(is_active=True, is_archived=False):
        items.append({
            'id': acc.id,
            'name': acc.name,
            'currency': acc.currency,
            'balance': acc.current_balance,
            'balance_display': f'{acc.current_balance:,.0f} {_symbol(acc.currency)}'.replace(',', ' '),
        })
    return items


_SYMBOLS = {'UAH': '₴', 'USD': '$', 'EUR': '€', 'PLN': 'zł', 'GBP': '£'}


def _symbol(code: str) -> str:
    return _SYMBOLS.get(code, code)
