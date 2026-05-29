"""Розділ «Календар»: місячна сітка прогнозу + деталізація дня."""
from __future__ import annotations

import datetime as dt

from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET

from ..models import get_default_company
from ..permissions import finance_access_required
from ..services import calendar as cal_service
from ..services import serializers as ser


def _money(company, amount):
    return ser.money(amount, company.base_currency, signed=False)


@finance_access_required
def calendar(request):
    company = get_default_company()
    today = timezone.localdate()
    try:
        year = int(request.GET.get('year', today.year))
        month = int(request.GET.get('month', today.month))
        if not 1 <= month <= 12:
            month = today.month
    except (ValueError, TypeError):
        year, month = today.year, today.month

    grid = cal_service.month_grid(company, year, month, request.GET)
    # Форматуємо суми для відображення.
    for d in grid['days']:
        d['income_display'] = ser.money(d['income'], company.base_currency, signed=True) if d['income'] else ''
        d['expense_display'] = ser.money(-d['expense'], company.base_currency, signed=True) if d['expense'] else ''
        d['end_display'] = ser.money(d['end_balance'], company.base_currency)

    context = {
        'active_tab': 'calendar',
        'grid': grid,
        'dropdowns': ser.serialize_dropdowns(company),
        'prev_year': (dt.date(year, month, 1) - dt.timedelta(days=1)).year,
        'prev_month': (dt.date(year, month, 1) - dt.timedelta(days=1)).month,
        'next_date': dt.date(year, month, 28) + dt.timedelta(days=7),
    }
    nd = context['next_date']
    context['next_year'] = nd.year
    context['next_month'] = nd.month
    return render(request, 'finance/calendar.html', context)


@finance_access_required(api=True)
@require_GET
def calendar_day_api(request, date_str):
    company = get_default_company()
    try:
        day = dt.date.fromisoformat(date_str)
    except ValueError:
        return JsonResponse({'ok': False, 'error': 'Невірна дата'}, status=400)

    detail = cal_service.day_detail(company, day, request.GET)
    txns = [ser.serialize_transaction(t) for t in detail['transactions']]
    return JsonResponse({
        'ok': True,
        'date': detail['date'],
        'start_balance': _money(company, detail['start_balance']),
        'income': ser.money(detail['income'], company.base_currency, signed=True),
        'expense': ser.money(-detail['expense'], company.base_currency, signed=True),
        'end_balance': _money(company, detail['end_balance']),
        'transactions': txns,
    })
