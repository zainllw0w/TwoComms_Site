"""Розділ «Планові» — керування плановими платежами (доходи й витрати).

Бізнес-дашборд зобов'язань: повторювані (комуналка, оренда), розстрочки боргів
магазинів і разові планові — усе згорнуто в один рядок на зобов'язання з
періодичністю, сумою за період, «скільки лишилось», датою найближчого платежу
та позначкою прострочення. Звідси ж погашають/проводять платіж із вибором
рахунку та контрагента, редагують план і дивляться історію по контрагенту.
"""
from __future__ import annotations

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from ..models import Counterparty, get_default_company
from ..permissions import finance_access_required
from ..services import counterparty as cp_service
from ..services import obligations as obligations_service
from ..services import serializers as ser


def _fmt_obligation(company, g):
    """Форматує суми зобов'язання у відображувані рядки (raw → money)."""
    cur = g.get('currency') or company.base_currency
    g['per_amount_display'] = ser.money(g['per_amount'], cur)
    g['planned_sum_display'] = ser.money(g['planned_sum'], cur)
    if g.get('remaining_amount') is not None:
        g['remaining_amount_display'] = ser.money(g['remaining_amount'], cur)
    else:
        g['remaining_amount_display'] = ''
    return g


@finance_access_required
def planned(request):
    company = get_default_company()
    data = obligations_service.planned_obligations(company)

    income = [_fmt_obligation(company, g) for g in data['income']]
    expense = [_fmt_obligation(company, g) for g in data['expense']]

    cur = company.base_currency
    context = {
        'active_tab': 'planned',
        'income': income,
        'expense': expense,
        'income_sum': ser.money(data['income_sum'], cur),
        'expense_sum': ser.money(data['expense_sum'], cur),
        'net': ser.money(data['net'], cur, signed=True),
        'net_positive': data['net'] >= 0,
        'overdue_count': data['overdue_count'],
        'overdue_income': ser.money(data['overdue_income'], cur),
        'overdue_expense': ser.money(data['overdue_expense'], cur),
        'income_count': data['income_count'],
        'expense_count': data['expense_count'],
        'dropdowns': ser.serialize_dropdowns(company),
    }
    return render(request, 'finance/planned.html', context)


@finance_access_required(api=True)
@require_GET
def planned_obligations_api(request):
    """JSON-версія зобов'язань (для динамічного оновлення без перезавантаження)."""
    company = get_default_company()
    data = obligations_service.planned_obligations(company)
    income = [_fmt_obligation(company, g) for g in data['income']]
    expense = [_fmt_obligation(company, g) for g in data['expense']]
    cur = company.base_currency

    def _clean(items):
        out = []
        for g in items:
            out.append({k: v for k, v in g.items()
                        if k not in ('per_amount', 'planned_sum', 'remaining_amount', 'next_due')})
        return out

    return JsonResponse({
        'ok': True,
        'income': _clean(income),
        'expense': _clean(expense),
        'income_sum': ser.money(data['income_sum'], cur),
        'expense_sum': ser.money(data['expense_sum'], cur),
        'net': ser.money(data['net'], cur, signed=True),
        'overdue_count': data['overdue_count'],
    })


@finance_access_required(api=True)
@require_GET
def counterparty_history_api(request, counterparty_id):
    """Історія по контрагенту: операції, рахунки, підсумки."""
    company = get_default_company()
    cp = get_object_or_404(Counterparty, id=counterparty_id, company=company)
    return JsonResponse({'ok': True, **cp_service.counterparty_history(company, cp)})
