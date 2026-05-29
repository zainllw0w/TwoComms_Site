"""Розділ «Аналітика»: вітрина звітів + детальні звіти + експорт XLSX."""
from __future__ import annotations

import datetime as dt
import json

from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from ..models import AuditLog, FinancialMetric, Transaction, get_default_company
from ..permissions import finance_access_required
from ..services import reports as rep
from ..services import reports_debt as repd
from ..services import serializers as ser


REPORT_CARDS = [
    {'kind': 'cashflow', 'title': 'Гроші / Cash flow', 'desc': 'Рух грошових коштів'},
    {'kind': 'pnl', 'title': 'P&L', 'desc': 'Прибутки та збитки'},
    {'kind': 'receivables', 'title': 'Дебіторка', 'desc': 'Хто винен компанії'},
    {'kind': 'payables', 'title': 'Кредиторка', 'desc': 'Кому винна компанія'},
    {'kind': 'statement', 'title': 'Виписка за рахунком', 'desc': 'Рух по рахунку'},
    {'kind': 'projects', 'title': 'Проекти', 'desc': 'Прибутковість проектів'},
    {'kind': 'audit', 'title': 'Історія дій', 'desc': 'Журнал змін'},
    {'kind': 'balance', 'title': 'Баланс', 'desc': 'Активи та пасиви'},
    {'kind': 'plan_fact', 'title': 'План/Факт', 'desc': 'Порівняння плану і факту'},
    {'kind': 'metrics', 'title': 'Фінансові показники', 'desc': 'EBITDA, маржа, KPI'},
]


def _m(company, v, signed=False):
    return ser.money(v, company.base_currency, signed=signed)


@finance_access_required
def analytics(request):
    company = get_default_company()
    return render(request, 'finance/analytics.html', {
        'active_tab': 'analytics',
        'cards': REPORT_CARDS,
    })


@finance_access_required
def report(request, kind):
    company = get_default_company()
    ctx = {'active_tab': 'analytics', 'kind': kind,
           'dropdowns': ser.serialize_dropdowns(company),
           'period': request.GET.get('period', 'month')}

    if kind == 'cashflow':
        data = rep.cash_flow(company, request.GET)
        ctx.update({
            'title': 'Cash flow', 'data': data,
            'cash_in': _m(company, data['cash_in']),
            'cash_out': _m(company, data['cash_out']),
            'net': _m(company, data['net'], signed=True),
            'chart_data': json.dumps({
                'series': data['series'],
                'income_by_category': data['income_by_category'],
                'expense_by_category': data['expense_by_category'],
            }),
        })
        return render(request, 'finance/reports/cashflow.html', ctx)

    if kind == 'pnl':
        data = rep.pnl(company, request.GET)
        ctx.update({
            'title': 'P&L', 'data': data,
            'income': _m(company, data['income']),
            'expenses': _m(company, data['expenses']),
            'profit': _m(company, data['profit'], signed=True),
            'margin': round(data['margin'], 1),
            'chart_data': json.dumps({
                'series': data['series'],
                'income_by_category': data['income_by_category'],
                'expense_by_category': data['expense_by_category'],
            }),
        })
        return render(request, 'finance/reports/pnl.html', ctx)

    if kind == 'receivables':
        data = repd.receivables(company)
        ctx.update({'title': 'Дебіторка', 'rows': _fmt_debt(company, data['rows']),
                    'total': _m(company, data['total'])})
        return render(request, 'finance/reports/debt.html', ctx)

    if kind == 'payables':
        data = repd.payables(company)
        ctx.update({'title': 'Кредиторка', 'rows': _fmt_debt(company, data['rows']),
                    'total': _m(company, data['total']), 'is_payable': True})
        return render(request, 'finance/reports/debt.html', ctx)

    if kind == 'statement':
        acc_id = request.GET.get('account')
        account = company.accounts.filter(id=acc_id).first() or company.accounts.first()
        if not account:
            ctx.update({'title': 'Виписка за рахунком', 'no_account': True})
            return render(request, 'finance/reports/statement.html', ctx)
        data = rep.account_statement(company, account, request.GET)
        ctx.update({
            'title': f'Виписка: {account.name}', 'account': account,
            'opening': _m(company, data['opening']), 'closing': _m(company, data['closing']),
            'income': _m(company, data['income']), 'expense': _m(company, data['expense']),
            'rows': [ser.serialize_transaction(t) for t in data['transactions']],
        })
        return render(request, 'finance/reports/statement.html', ctx)

    if kind == 'projects':
        data = rep.projects_report(company, request.GET)
        for r in data['rows']:
            r['income_d'] = _m(company, r['income'])
            r['expense_d'] = _m(company, r['expense'])
            r['profit_d'] = _m(company, r['profit'], signed=True)
        ctx.update({'title': 'Проекти', 'rows': data['rows']})
        return render(request, 'finance/reports/projects.html', ctx)

    if kind == 'audit':
        logs = AuditLog.objects.filter(company=company).select_related('user')[:300]
        ctx.update({'title': 'Історія дій', 'logs': logs})
        return render(request, 'finance/reports/audit.html', ctx)

    if kind == 'balance':
        data = repd.balance_sheet(company)
        for side in ('assets', 'liabilities'):
            for r in data[side]:
                r['amount_d'] = _m(company, r['amount'])
        ctx.update({
            'title': 'Баланс', 'data': data,
            'total_assets': _m(company, data['total_assets']),
            'total_liabilities': _m(company, data['total_liabilities']),
            'difference': _m(company, data['difference'], signed=True),
        })
        return render(request, 'finance/reports/balance.html', ctx)

    if kind == 'plan_fact':
        data = repd.plan_fact(company, request.GET)
        for r in data['rows']:
            r['plan_d'] = _m(company, r['plan'])
            r['fact_d'] = _m(company, r['fact'])
            r['deviation_d'] = _m(company, r['deviation'], signed=True)
            r['completion'] = round(r['completion'], 1)
        ctx.update({'title': 'План/Факт', 'rows': data['rows']})
        return render(request, 'finance/reports/plan_fact.html', ctx)

    if kind == 'metrics':
        data = repd.metrics(company, request.GET)
        for r in data['base']:
            r['value_d'] = (f"{r['value']}%" if r.get('is_percent') else _m(company, r['value']))
        for r in data['custom']:
            r['value_d'] = _m(company, r['value'])
        ctx.update({'title': 'Фінансові показники', 'data': data,
                    'income_categories': company.categories.exclude(type='expense'),
                    'expense_categories': company.categories.exclude(type='income')})
        return render(request, 'finance/reports/metrics.html', ctx)

    ctx.update({'title': 'Звіт', 'section_subtitle': 'Невідомий звіт'})
    return render(request, 'finance/coming_soon.html',
                  {'section_title': 'Звіт', 'active_tab': 'analytics'})


def _fmt_debt(company, rows):
    for r in rows:
        r['amount_d'] = _m(company, r['amount'])
    return rows


# ----------------------------- Експорт XLSX -----------------------------

@finance_access_required
def report_export(request, kind):
    company = get_default_company()
    try:
        from openpyxl import Workbook
    except ImportError:
        return JsonResponse({'ok': False, 'error': 'openpyxl недоступний'}, status=500)

    wb = Workbook()
    ws = wb.active
    ws.title = kind[:31]

    if kind == 'projects':
        data = rep.projects_report(company, request.GET)
        ws.append(['Проект', 'Дохід', 'Витрата', 'Прибуток', 'Маржа %', 'Частка %'])
        for r in data['rows']:
            ws.append([r['name'], float(r['income']), float(r['expense']),
                       float(r['profit']), round(r['margin'], 1), round(r['share'], 1)])
    elif kind == 'plan_fact':
        data = repd.plan_fact(company, request.GET)
        ws.append(['Категорія', 'План', 'Факт', 'Відхилення', 'Виконання %'])
        for r in data['rows']:
            ws.append([r['category'], float(r['plan']), float(r['fact']),
                       float(r['deviation']), round(r['completion'], 1)])
    elif kind in ('receivables', 'payables'):
        data = repd.receivables(company) if kind == 'receivables' else repd.payables(company)
        ws.append(['Контрагент', 'Сума', 'Дата', 'Проект', 'Статус', 'Коментар'])
        for r in data['rows']:
            ws.append([r['counterparty'], float(r['amount']), r['date'],
                       r['project'], r['status'], r['comment']])
    else:
        # Загальний експорт операцій періоду.
        from .. services import filters as fs
        qs = fs.filter_transactions(company, request.GET)
        ws.append(['Дата', 'Тип', 'Сума', 'Валюта', 'Рахунок', 'Категорія', 'Контрагент', 'Проект', 'Коментар'])
        for t in qs[:5000]:
            ws.append([
                t.date_actual.strftime('%Y-%m-%d %H:%M') if t.date_actual else '',
                t.get_type_display(), float(t.amount), t.currency,
                t.account.name if t.account else '', t.category.name if t.category else '',
                t.counterparty.name if t.counterparty else '', t.project.name if t.project else '',
                t.comment,
            ])

    resp = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    resp['Content-Disposition'] = f'attachment; filename="finance_{kind}.xlsx"'
    wb.save(resp)
    return resp


# ----------------------------- KPI + дії боргів -----------------------------

@finance_access_required(api=True)
@require_POST
def metric_create_api(request):
    company = get_default_company()
    data = json.loads(request.body or '{}')
    name = (data.get('name') or '').strip()
    if not name:
        return JsonResponse({'ok': False, 'error': 'Вкажіть назву показника'}, status=400)
    metric = FinancialMetric.objects.create(company=company, name=name,
                                             formula='revenue_minus_variable')
    inc = [i for i in (data.get('income_categories') or []) if str(i).isdigit()]
    exp = [i for i in (data.get('expense_categories') or []) if str(i).isdigit()]
    if inc:
        metric.income_categories.set(company.categories.filter(id__in=inc))
    if exp:
        metric.expense_categories.set(company.categories.filter(id__in=exp))
    return JsonResponse({'ok': True, 'id': metric.id})


@finance_access_required(api=True)
@require_POST
def debt_settle_api(request, txn_id):
    """Погасити планову операцію (дебіторка/кредиторка) → стає фактичною."""
    from ..services import transactions as txn_service
    company = get_default_company()
    txn = get_object_or_404(Transaction, id=txn_id, company=company)
    txn_service.mark_planned_actual(txn, user=request.user)
    return JsonResponse({'ok': True})
