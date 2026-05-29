"""Серіалізація операцій та довідників у JSON для журналу/модалок."""
from __future__ import annotations

from decimal import Decimal

from django.utils import timezone

from ..models import Transaction

_SYMBOLS = {'UAH': '₴', 'USD': '$', 'EUR': '€', 'PLN': 'zł', 'GBP': '£'}

_MONTHS_UK = ['', 'січ', 'лют', 'бер', 'кві', 'тра', 'чер', 'лип', 'сер', 'вер', 'жов', 'лис', 'гру']


def currency_symbol(code: str) -> str:
    return _SYMBOLS.get(code, code or '')


def money(amount, currency='UAH', signed=False) -> str:
    """Форматування суми: пробіл-роздільник тисяч, символ валюти."""
    if amount is None:
        amount = Decimal('0')
    amount = Decimal(amount)
    sign = ''
    if signed and amount > 0:
        sign = '+'
    elif amount < 0:
        sign = '−'
    whole = f'{abs(amount):,.2f}'.replace(',', ' ')
    # Прибираємо .00 для цілих.
    if whole.endswith('.00'):
        whole = whole[:-3]
    return f'{sign}{whole} {currency_symbol(currency)}'.strip()


def date_label(value):
    if not value:
        return ''
    local = timezone.localtime(value) if timezone.is_aware(value) else value
    return f'{local.day} {_MONTHS_UK[local.month]} {local.year}'


def time_label(value):
    if not value:
        return ''
    local = timezone.localtime(value) if timezone.is_aware(value) else value
    return local.strftime('%H:%M')


def serialize_transaction(txn: Transaction, *, running_balance=None) -> dict:
    """Рядок журналу/дані для drawer."""
    is_income = txn.type == Transaction.TYPE_INCOME
    is_transfer = txn.type == Transaction.TYPE_TRANSFER

    if is_transfer:
        amount_display = money(txn.amount, txn.currency)
        amount_class = 'transfer'
    elif is_income:
        amount_display = money(txn.amount, txn.currency, signed=True)
        amount_class = 'pos'
    else:
        amount_display = money(-txn.amount, txn.currency, signed=True)
        amount_class = 'neg'

    account_name = txn.account.name if txn.account else '—'
    if is_transfer and txn.to_account:
        account_name = f'{account_name} → {txn.to_account.name}'

    return {
        'id': txn.id,
        'type': txn.type,
        'type_display': txn.get_type_display(),
        'status': txn.status,
        'status_display': txn.get_status_display(),
        'is_planned': txn.is_planned,
        'amount': str(txn.amount),
        'currency': txn.currency,
        'amount_display': amount_display,
        'amount_class': amount_class,
        'date': date_label(txn.date_actual),
        'time': time_label(txn.date_actual),
        'date_actual': timezone.localtime(txn.date_actual).strftime('%Y-%m-%dT%H:%M') if txn.date_actual else '',
        'date_agreement': timezone.localtime(txn.date_agreement).strftime('%Y-%m-%dT%H:%M') if txn.date_agreement else '',
        'account_id': txn.account_id,
        'to_account_id': txn.to_account_id,
        'account_name': account_name,
        'running_balance': money(running_balance, txn.account.currency if txn.account else 'UAH') if running_balance is not None else '',
        'counterparty_id': txn.counterparty_id,
        'counterparty': txn.counterparty.name if txn.counterparty else '',
        'category_id': txn.category_id,
        'category': txn.category.name if txn.category else '',
        'project_id': txn.project_id,
        'project': txn.project.name if txn.project else '',
        'comment': txn.comment,
        'tags': [{'id': t.id, 'name': t.name} for t in txn.tags.all()],
        'source': txn.source,
        'to_amount': str(txn.to_amount) if txn.to_amount is not None else '',
    }


def serialize_dropdowns(company) -> dict:
    """Довідники для модалок (рахунки, категорії, проєкти, контрагенти, теги)."""
    accounts = [{'id': a.id, 'name': a.name, 'currency': a.currency,
                 'balance': str(a.current_balance)}
                for a in company.accounts.filter(is_active=True, is_archived=False).order_by('sort_order')]
    income_cats = [{'id': c.id, 'name': c.name, 'parent': c.parent_id}
                   for c in company.categories.filter(is_active=True).exclude(type='expense')]
    expense_cats = [{'id': c.id, 'name': c.name, 'parent': c.parent_id}
                    for c in company.categories.filter(is_active=True).exclude(type='income')]
    projects = [{'id': p.id, 'name': p.name} for p in company.projects.all().order_by('sort_order')]
    counterparties = [{'id': c.id, 'name': c.name, 'group': c.group or c.get_type_display()}
                      for c in company.counterparties.all().order_by('name')]
    tags = [{'id': t.id, 'name': t.name} for t in company.tags.all().order_by('name')]
    return {
        'accounts': accounts,
        'income_categories': income_cats,
        'expense_categories': expense_cats,
        'projects': projects,
        'counterparties': counterparties,
        'tags': tags,
    }
