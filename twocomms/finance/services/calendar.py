"""Календар: прогноз залишку коштів по днях (ТЗ 07).

Розрахунок компанійного залишку на кінець дня:
  start_day = end_prev_day
  end_day = start_day + actual_in - actual_out + planned_in - planned_out
Перекази всередині компанії не змінюють загальний залишок (ігноруються тут).
Минуле — факт; сьогодні — факт + неоплачені плани; майбутнє — прогноз.
"""
from __future__ import annotations

import calendar as _calendar
import datetime as dt
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from ..models import Transaction
from . import currency as currency_service

WEEKDAYS_UK = ['пн', 'вт', 'ср', 'чт', 'пт', 'сб', 'нд']
MONTHS_UK = ['', 'січень', 'лютий', 'березень', 'квітень', 'травень', 'червень',
             'липень', 'серпень', 'вересень', 'жовтень', 'листопад', 'грудень']


def _base_filter(company, params=None):
    qs = Transaction.objects.filter(company=company).exclude(status=Transaction.STATUS_CANCELLED)
    qs = qs.exclude(excluded_from_reports=True)
    if not params:
        return qs
    if params.get('accounts'):
        ids = [i for i in str(params['accounts']).split(',') if i.isdigit()]
        if ids:
            qs = qs.filter(account_id__in=ids)
    if params.get('projects'):
        ids = [i for i in str(params['projects']).split(',') if i.isdigit()]
        if ids:
            qs = qs.filter(project_id__in=ids)
    if params.get('categories'):
        ids = [i for i in str(params['categories']).split(',') if i.isdigit()]
        if ids:
            qs = qs.filter(category_id__in=ids)
    return qs


def opening_total(company, before_date, params=None) -> Decimal:
    """Компанійний фактичний залишок на кінець дня (before_date - 1)."""
    total = Decimal('0')
    # Стартові баланси рахунків у базовій валюті.
    accounts = company.accounts.filter(is_archived=False)
    if params and params.get('accounts'):
        ids = [int(i) for i in str(params['accounts']).split(',') if i.isdigit()]
        if ids:
            accounts = accounts.filter(id__in=ids)
    for acc in accounts:
        total += currency_service.convert(company, acc.initial_balance, acc.currency)
    # Фактичні операції до before_date.
    qs = _base_filter(company, params).filter(status=Transaction.STATUS_ACTUAL,
                                              date_actual__date__lt=before_date)
    inc = qs.filter(type=Transaction.TYPE_INCOME).aggregate(s=Sum('amount_base'))['s'] or Decimal('0')
    exp = qs.filter(type=Transaction.TYPE_EXPENSE).aggregate(s=Sum('amount_base'))['s'] or Decimal('0')
    return total + inc - exp


def _day_sums(company, day, params=None):
    qs = _base_filter(company, params).filter(date_actual__date=day)
    def agg(status, ttype):
        return qs.filter(status=status, type=ttype).aggregate(s=Sum('amount_base'))['s'] or Decimal('0')
    return {
        'actual_in': agg(Transaction.STATUS_ACTUAL, Transaction.TYPE_INCOME),
        'actual_out': agg(Transaction.STATUS_ACTUAL, Transaction.TYPE_EXPENSE),
        'planned_in': agg(Transaction.STATUS_PLANNED, Transaction.TYPE_INCOME),
        'planned_out': agg(Transaction.STATUS_PLANNED, Transaction.TYPE_EXPENSE),
    }


def month_grid(company, year, month, params=None):
    """Повертає структуру місяця з остатками/сумами по днях."""
    first = dt.date(year, month, 1)
    days_in_month = _calendar.monthrange(year, month)[1]
    today = timezone.localdate()

    running = opening_total(company, first, params)
    days = []
    for d in range(1, days_in_month + 1):
        day = dt.date(year, month, d)
        sums = _day_sums(company, day, params)
        income = sums['actual_in'] + sums['planned_in']
        expense = sums['actual_out'] + sums['planned_out']
        end = running + income - expense
        days.append({
            'day': d,
            'date': day.isoformat(),
            'weekday': day.weekday(),
            'is_today': day == today,
            'is_past': day < today,
            'is_future': day > today,
            'income': income,
            'expense': expense,
            'has_movement': income != 0 or expense != 0,
            'end_balance': end,
            'negative': end < 0,
        })
        running = end

    # Зсув першого дня (пн=0).
    lead = first.weekday()
    return {
        'year': year, 'month': month,
        'month_name': MONTHS_UK[month],
        'weekdays': WEEKDAYS_UK,
        'lead_blanks': list(range(lead)),
        'days': days,
        'prev': (first - dt.timedelta(days=1)).replace(day=1).isoformat(),
        'next': (first + dt.timedelta(days=days_in_month)).isoformat(),
    }


def day_detail(company, day, params=None):
    """Деталізація вибраного дня: залишок початок/кінець + операції."""
    start = opening_total(company, day, params)
    sums = _day_sums(company, day, params)
    income = sums['actual_in'] + sums['planned_in']
    expense = sums['actual_out'] + sums['planned_out']
    end = start + income - expense

    txns = (_base_filter(company, params).filter(date_actual__date=day)
            .select_related('account', 'to_account', 'category', 'counterparty', 'project')
            .order_by('date_actual'))
    return {
        'date': day.isoformat(),
        'start_balance': start,
        'income': income,
        'expense': expense,
        'end_balance': end,
        'base_currency': company.base_currency,
        'transactions': txns,
    }
