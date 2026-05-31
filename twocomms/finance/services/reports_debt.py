"""Звіти дебіторки/кредиторки, балансу, план/факт та фінпоказників (ТЗ 06)."""
from __future__ import annotations

from decimal import Decimal

from django.db.models import Sum

from ..models import Invoice, Transaction
from . import balances as balance_service
from . import reports as core_reports
from .timeutil import day_end, day_start


def _planned(company, ttype):
    return (Transaction.objects.filter(company=company, status=Transaction.STATUS_PLANNED, type=ttype)
            .exclude(excluded_from_reports=True)
            .select_related('counterparty', 'project', 'account', 'category', 'reseller'))


def receivables(company, params=None):
    """Дебіторка: планові доходи + неоплачені/частково оплачені інвойси."""
    from django.utils import timezone
    today = timezone.localdate()
    rows = []
    total = Decimal('0')
    for t in _planned(company, Transaction.TYPE_INCOME):
        amount = t.amount_base or t.amount
        total += amount
        due = t.date_actual.date() if t.date_actual else None
        rows.append({
            'source': 'planned', 'id': t.id,
            'counterparty': t.counterparty.name if t.counterparty else '—',
            'reseller': t.reseller.name if t.reseller_id else '',
            'reseller_id': t.reseller_id,
            'amount': amount, 'date': due.isoformat() if due else '',
            'project': t.project.name if t.project else '',
            'comment': t.comment, 'status': 'Планується',
            'overdue': bool(due and due < today),
        })
    for inv in company.invoices.exclude(status__in=[Invoice.STATUS_PAID, Invoice.STATUS_CANCELLED, Invoice.STATUS_DRAFT]):
        balance_due = inv.balance_due
        if balance_due <= 0:
            continue
        total += balance_due
        rows.append({
            'source': 'invoice', 'id': inv.id,
            'counterparty': inv.payer_name or (inv.counterparty.name if inv.counterparty else '—'),
            'amount': balance_due, 'date': inv.due_date.isoformat() if inv.due_date else '',
            'project': inv.project.name if inv.project else '',
            'comment': f'Рахунок №{inv.number}', 'status': inv.get_status_display(),
            'overdue': bool(inv.due_date and inv.due_date < today),
        })
    rows.sort(key=lambda r: (not r['overdue'], r['date']))
    return {'rows': rows, 'total': total}


def payables(company, params=None):
    """Кредиторка: планові витрати + зобов'язання перед постачальниками."""
    from django.utils import timezone
    today = timezone.localdate()
    rows = []
    total = Decimal('0')
    for t in _planned(company, Transaction.TYPE_EXPENSE):
        amount = t.amount_base or t.amount
        total += amount
        due = t.date_actual.date() if t.date_actual else None
        rows.append({
            'source': 'planned', 'id': t.id,
            'counterparty': t.counterparty.name if t.counterparty else '—',
            'reseller': t.reseller.name if t.reseller_id else '',
            'reseller_id': t.reseller_id,
            'amount': amount, 'date': due.isoformat() if due else '',
            'project': t.project.name if t.project else '',
            'comment': t.comment, 'status': 'Планується',
            'overdue': bool(due and due < today),
        })
    rows.sort(key=lambda r: (not r['overdue'], r['date']))
    return {'rows': rows, 'total': total}


def balance_sheet(company, params=None):
    """Баланс: активи = пасиви (ТЗ 06 §11)."""
    money = balance_service.total_actual_balance(company)
    recv = receivables(company)['total']
    pay = payables(company)['total']

    # Капітал = початкові баланси (внесок власника).
    capital = Decimal('0')
    for acc in company.accounts.filter(is_archived=False):
        from . import currency as currency_service
        capital += currency_service.convert(company, acc.initial_balance, acc.currency)

    # Нерозподілений прибуток = фактичні доходи − витрати (за весь час).
    actual = (Transaction.objects.filter(company=company, status=Transaction.STATUS_ACTUAL)
              .exclude(type=Transaction.TYPE_TRANSFER).exclude(excluded_from_reports=True))
    inc = actual.filter(type=Transaction.TYPE_INCOME).aggregate(s=Sum('amount_base'))['s'] or Decimal('0')
    exp = actual.filter(type=Transaction.TYPE_EXPENSE).aggregate(s=Sum('amount_base'))['s'] or Decimal('0')
    retained = inc - exp

    assets = [
        {'name': 'Гроші на рахунках', 'amount': money},
        {'name': 'Дебіторська заборгованість', 'amount': recv},
    ]
    # Заморожений капітал як актив: товар на складі + товар у контрагентів.
    try:
        from . import warehouse_link
        frozen_wh = warehouse_link.frozen_in_warehouse()
        if frozen_wh:
            assets.append({'name': 'Товар на складі (собівартість)', 'amount': frozen_wh})
    except Exception:
        pass
    try:
        from . import consignment as consignment_service
        frozen_cons = consignment_service.consignment_frozen_total(company)
        if frozen_cons:
            assets.append({'name': 'Товар у контрагентів (реалізація)', 'amount': frozen_cons})
    except Exception:
        pass
    liabilities = [
        {'name': 'Кредиторська заборгованість', 'amount': pay},
        {'name': 'Капітал (стартові внески)', 'amount': capital},
        {'name': 'Нерозподілений прибуток', 'amount': retained},
    ]
    total_assets = sum((a['amount'] for a in assets), Decimal('0'))
    total_liabilities = sum((l['amount'] for l in liabilities), Decimal('0'))
    return {
        'assets': assets, 'liabilities': liabilities,
        'total_assets': total_assets, 'total_liabilities': total_liabilities,
        'difference': total_assets - total_liabilities,
        'balanced': abs(total_assets - total_liabilities) < Decimal('0.01'),
    }


def plan_fact(company, params):
    """План/Факт за категоріями (ТЗ 06 §12)."""
    start, end = core_reports.resolve_period(params)
    actual = (Transaction.objects.filter(company=company, status=Transaction.STATUS_ACTUAL)
              .exclude(type=Transaction.TYPE_TRANSFER).exclude(excluded_from_reports=True)
              .filter(date_actual__gte=day_start(start), date_actual__lte=day_end(end)))
    planned = (Transaction.objects.filter(company=company, status=Transaction.STATUS_PLANNED)
               .exclude(type=Transaction.TYPE_TRANSFER)
               .filter(date_actual__gte=day_start(start), date_actual__lte=day_end(end)))

    rows = []
    for cat in company.categories.filter(is_active=True):
        fact = actual.filter(category=cat).aggregate(s=Sum('amount_base'))['s'] or Decimal('0')
        plan = planned.filter(category=cat).aggregate(s=Sum('amount_base'))['s'] or Decimal('0')
        if fact == 0 and plan == 0:
            continue
        deviation = fact - plan
        rows.append({
            'category': cat.name, 'type': cat.type,
            'plan': plan, 'fact': fact, 'deviation': deviation,
            'completion': float(fact / plan * 100) if plan else (100.0 if fact else 0.0),
        })
    rows.sort(key=lambda r: abs(r['fact']), reverse=True)
    return {'rows': rows, 'period': (start.isoformat(), end.isoformat())}


def metrics(company, params):
    """Фінансові показники: налаштовувані KPI + базові (валовий прибуток, маржа, EBITDA)."""
    pnl_data = core_reports.pnl(company, params)
    income = pnl_data['income']
    expenses = pnl_data['expenses']
    profit = pnl_data['profit']

    base = [
        {'name': 'Дохід', 'value': income},
        {'name': 'Витрати', 'value': expenses},
        {'name': 'Валовий прибуток', 'value': profit},
        {'name': 'Маржа, %', 'value': Decimal(str(round(pnl_data['margin'], 1))), 'is_percent': True},
        {'name': 'EBITDA (спрощено)', 'value': profit},
    ]
    # Користувацькі KPI.
    custom = []
    start, end = core_reports.resolve_period(params)
    actual = (Transaction.objects.filter(company=company, status=Transaction.STATUS_ACTUAL)
              .filter(date_actual__gte=day_start(start), date_actual__lte=day_end(end)))
    for m in company.metrics.all():
        inc_ids = list(m.income_categories.values_list('id', flat=True))
        exp_ids = list(m.expense_categories.values_list('id', flat=True))
        rev = actual.filter(category_id__in=inc_ids).aggregate(s=Sum('amount_base'))['s'] or Decimal('0') if inc_ids else Decimal('0')
        var = actual.filter(category_id__in=exp_ids).aggregate(s=Sum('amount_base'))['s'] or Decimal('0') if exp_ids else Decimal('0')
        custom.append({'name': m.name, 'value': rev - var})
    return {'base': base, 'custom': custom, 'period': (start.isoformat(), end.isoformat())}
