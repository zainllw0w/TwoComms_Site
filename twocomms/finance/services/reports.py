"""Аналітичні звіти: будуються з тих самих транзакцій (ТЗ 06).

Cash Flow — за датою руху грошей (date_actual), фактичні, перекази виключені.
P&L — за датою угоди (date_agreement, фолбек date_actual), фактичні, без переказів.
Дебіторка/кредиторка — планові операції + неоплачені інвойси.
"""
from __future__ import annotations

import datetime as dt
from collections import OrderedDict
from decimal import Decimal

from django.db.models import Sum
from django.db.models.functions import Coalesce

from ..models import Invoice, Transaction
from . import filters as filter_service
from .timeutil import day_end, day_start


def resolve_period(params):
    period = params.get('period', 'month')
    start, end = filter_service.period_range(period, params.get('date_from'), params.get('date_to'))
    if start is None:
        # 'all' → з найранішої операції до сьогодні.
        from django.utils import timezone
        start = dt.date(2000, 1, 1)
        end = timezone.localdate()
    return start, end


def _apply_dim_filters(qs, params):
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
    if params.get('counterparties'):
        ids = [i for i in str(params['counterparties']).split(',') if i.isdigit()]
        if ids:
            qs = qs.filter(counterparty_id__in=ids)
    return qs


def _actual(company):
    return (Transaction.objects.filter(company=company, status=Transaction.STATUS_ACTUAL)
            .exclude(excluded_from_reports=True))


# ----------------------------- Cash Flow -----------------------------

def cash_flow(company, params):
    start, end = resolve_period(params)
    qs = _apply_dim_filters(_actual(company), params).filter(
        date_actual__gte=day_start(start), date_actual__lte=day_end(end))

    cash_in = qs.filter(type=Transaction.TYPE_INCOME).aggregate(s=Sum('amount_base'))['s'] or Decimal('0')
    cash_out = qs.filter(type=Transaction.TYPE_EXPENSE).aggregate(s=Sum('amount_base'))['s'] or Decimal('0')

    # Серія по днях/місяцях.
    by_period = _series_by_period(qs, start, end)
    in_by_cat = _group_by_category(qs.filter(type=Transaction.TYPE_INCOME))
    out_by_cat = _group_by_category(qs.filter(type=Transaction.TYPE_EXPENSE))

    return {
        'cash_in': cash_in,
        'cash_out': cash_out,
        'net': cash_in - cash_out,
        'series': by_period,
        'income_by_category': in_by_cat,
        'expense_by_category': out_by_cat,
        'period': (start.isoformat(), end.isoformat()),
    }


def _series_by_period(qs, start, end):
    """Групування сум по днях (якщо період <= 62 днів) або місяцях."""
    span = (end - start).days
    buckets = OrderedDict()
    use_month = span > 62
    for t in qs.only('date_actual', 'type', 'amount_base'):
        d = t.date_actual.date()
        key = f'{d.year}-{d.month:02d}' if use_month else d.isoformat()
        if key not in buckets:
            buckets[key] = {'in': Decimal('0'), 'out': Decimal('0')}
        if t.type == Transaction.TYPE_INCOME:
            buckets[key]['in'] += t.amount_base
        elif t.type == Transaction.TYPE_EXPENSE:
            buckets[key]['out'] += t.amount_base
    return [{'label': k, 'in': float(v['in']), 'out': float(v['out'])}
            for k, v in sorted(buckets.items())]


def _group_by_category(qs):
    rows = (qs.values('category__name')
            .annotate(total=Coalesce(Sum('amount_base'), Decimal('0')))
            .order_by('-total'))
    return [{'name': r['category__name'] or 'Без категорії', 'total': float(r['total'])}
            for r in rows if r['total']]


# ----------------------------- P&L -----------------------------

def pnl(company, params):
    start, end = resolve_period(params)
    # За датою угоди; фолбек на date_actual робимо через Coalesce у фільтрі.
    qs = _apply_dim_filters(_actual(company), params).exclude(type=Transaction.TYPE_TRANSFER)
    qs = qs.filter(
        Q_or_date(start, end)
    )
    income = qs.filter(type=Transaction.TYPE_INCOME).aggregate(s=Sum('amount_base'))['s'] or Decimal('0')
    expenses = qs.filter(type=Transaction.TYPE_EXPENSE).aggregate(s=Sum('amount_base'))['s'] or Decimal('0')
    return {
        'income': income,
        'expenses': expenses,
        'profit': income - expenses,
        'margin': (float((income - expenses) / income * 100) if income else 0.0),
        'income_by_category': _group_by_category(qs.filter(type=Transaction.TYPE_INCOME)),
        'expense_by_category': _group_by_category(qs.filter(type=Transaction.TYPE_EXPENSE)),
        'series': _series_by_period(qs, start, end),
        'period': (start.isoformat(), end.isoformat()),
    }


def Q_or_date(start, end):
    """P&L діапазон: date_agreement у межах, або (немає угоди) date_actual у межах."""
    from django.db.models import Q
    return (
        (Q(date_agreement__gte=day_start(start)) & Q(date_agreement__lte=day_end(end)))
        | (Q(date_agreement__isnull=True) & Q(date_actual__gte=day_start(start)) & Q(date_actual__lte=day_end(end)))
    )


# ----------------------------- Виписка за рахунком -----------------------------

def account_statement(company, account, params):
    from .calendar import opening_total  # повторне використання логіки залишку
    start, end = resolve_period(params)
    qs = (_actual(company).filter(date_actual__gte=day_start(start), date_actual__lte=day_end(end))
          .filter(account=account).select_related('category', 'counterparty', 'project')
          .order_by('date_actual'))
    # Початковий залишок рахунку: initial + рух до start (тільки цей рахунок).
    prior = _actual(company).filter(account=account, date_actual__lt=day_start(start))
    prior_in = prior.filter(type=Transaction.TYPE_INCOME).aggregate(s=Sum('amount'))['s'] or Decimal('0')
    prior_out = prior.filter(type=Transaction.TYPE_EXPENSE).aggregate(s=Sum('amount'))['s'] or Decimal('0')
    prior_tin = (_actual(company).filter(to_account=account, date_actual__lt=day_start(start))
                 .aggregate(s=Sum('to_amount'))['s'] or Decimal('0'))
    prior_tout = prior.filter(type=Transaction.TYPE_TRANSFER).aggregate(s=Sum('amount'))['s'] or Decimal('0')
    opening = account.initial_balance + prior_in - prior_out + prior_tin - prior_tout

    period_in = qs.filter(type=Transaction.TYPE_INCOME).aggregate(s=Sum('amount'))['s'] or Decimal('0')
    period_out = qs.filter(type=Transaction.TYPE_EXPENSE).aggregate(s=Sum('amount'))['s'] or Decimal('0')
    return {
        'account': account,
        'opening': opening,
        'income': period_in,
        'expense': period_out,
        'closing': opening + period_in - period_out,
        'transactions': qs,
        'period': (start.isoformat(), end.isoformat()),
    }


# ----------------------------- Проекти -----------------------------

def projects_report(company, params):
    start, end = resolve_period(params)
    qs = _actual(company).exclude(type=Transaction.TYPE_TRANSFER).filter(
        date_actual__gte=day_start(start), date_actual__lte=day_end(end))
    total_income = qs.filter(type=Transaction.TYPE_INCOME).aggregate(s=Sum('amount_base'))['s'] or Decimal('0')

    rows = []
    projects = list(company.projects.all()) + [None]
    for proj in projects:
        pqs = qs.filter(project=proj) if proj else qs.filter(project__isnull=True)
        income = pqs.filter(type=Transaction.TYPE_INCOME).aggregate(s=Sum('amount_base'))['s'] or Decimal('0')
        expense = pqs.filter(type=Transaction.TYPE_EXPENSE).aggregate(s=Sum('amount_base'))['s'] or Decimal('0')
        if income == 0 and expense == 0:
            continue
        profit = income - expense
        rows.append({
            'name': proj.name if proj else 'Без проекта',
            'income': income, 'expense': expense, 'profit': profit,
            'margin': float(profit / income * 100) if income else 0.0,
            'share': float(income / total_income * 100) if total_income else 0.0,
        })
    rows.sort(key=lambda r: r['income'], reverse=True)
    return {'rows': rows, 'total_income': total_income, 'period': (start.isoformat(), end.isoformat())}
