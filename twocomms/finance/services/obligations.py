"""Групування планових платежів у ЗОБОВ'ЯЗАННЯ (obligations).

Проблема, яку вирішує модуль: повторюваний платіж (комуналка, оренда) та борг
магазину з розстрочкою матеріалізуються як кілька планових ``Transaction`` — по
одній на кожен період. У журналі це виглядало як дублі «платіж 1/6, 2/6…».

Тут ми **згортаємо** ці копії в один логічний рядок-зобов'язання, що показує:
періодичність, суму за період, скільки лишилось (кількість і сума), дату
найближчого платежу та чи прострочено. Жодної нової логіки балансу — самі
планові транзакції лишаються джерелом правди для прогнозу й календаря.

Ключ групування:
  • recurrence_rule_id            → повторюване зобов'язання («recurring»);
  • external_data.consignment_shipment_id → розстрочка магазину («installment»);
  • інакше окрема транзакція       → разове зобов'язання («onetime»).
"""
from __future__ import annotations

from collections import OrderedDict
from decimal import Decimal

from django.utils import timezone

from ..models import Transaction
from . import recurring as recurring_service


def _new_group(kind, ttype):
    return {
        'kind': kind,
        'type': ttype,
        'title': '',
        'counterparty': '', 'counterparty_id': None,
        'reseller': '', 'reseller_id': None,
        'account': '', 'account_id': None,
        'category': '',
        'currency': 'UAH',
        'per_amount': Decimal('0'),
        'frequency_label': '',
        'remaining_label': '',
        'remaining_count': None,
        'remaining_amount': None,
        'planned_sum': Decimal('0'),
        'planned_count': 0,
        'rule_id': None,
        'shipment_id': None,
        'next_due': None,
        'next_txn_id': None,
        '_txns': [],
    }


def _group_key(txn):
    if txn.recurrence_rule_id:
        return ('rule', txn.recurrence_rule_id)
    sid = (txn.external_data or {}).get('consignment_shipment_id')
    if sid:
        return ('shipment', sid)
    return ('txn', txn.id)


def planned_obligations(company) -> dict:
    """Згорнуті планові зобов'язання компанії, розділені на доходи й витрати.

    Повертає dict із 'income'/'expense' (списки зобов'язань, відсортовані за
    датою найближчого платежу — прострочені першими) та агрегатами для KPI.
    """
    today = timezone.localdate()
    qs = (Transaction.objects
          .filter(company=company, status=Transaction.STATUS_PLANNED)
          .exclude(excluded_from_reports=True)
          .select_related('recurrence_rule', 'counterparty', 'account',
                          'category', 'reseller', 'project')
          .order_by('date_actual'))

    groups: "OrderedDict[tuple, dict]" = OrderedDict()
    for t in qs:
        key = _group_key(t)
        g = groups.get(key)
        if g is None:
            kind = {'rule': 'recurring', 'shipment': 'installment', 'txn': 'onetime'}[key[0]]
            g = _new_group(kind, t.type)
            groups[key] = g
        g['_txns'].append(t)
        g['planned_sum'] += (t.amount_base or t.amount or Decimal('0'))
        g['planned_count'] += 1
        # Найближчий (найраніший) платіж — він перший за сортуванням.
        if g['next_due'] is None and t.date_actual:
            g['next_due'] = t.date_actual.date()
            g['next_txn_id'] = t.id
        # Реквізити беремо з найранішої транзакції групи.
        if not g['currency']:
            g['currency'] = t.currency
        g['currency'] = g['currency'] or t.currency
        if not g['counterparty'] and t.counterparty_id:
            g['counterparty'] = t.counterparty.name
            g['counterparty_id'] = t.counterparty_id
        if not g['reseller'] and t.reseller_id:
            g['reseller'] = t.reseller.name
            g['reseller_id'] = t.reseller_id
        if not g['account'] and t.account_id:
            g['account'] = t.account.name
            g['account_id'] = t.account_id
        if not g['category'] and t.category_id:
            g['category'] = t.category.name

    income, expense = [], []
    for (kind_key, ident), g in groups.items():
        first = g['_txns'][0]
        g['currency'] = first.currency or 'UAH'

        if g['kind'] == 'recurring' and first.recurrence_rule_id:
            rule = first.recurrence_rule
            g['rule_id'] = rule.id
            g['title'] = rule.title or first.comment or 'Повторюваний платіж'
            g['frequency_label'] = rule.frequency_label
            g['per_amount'] = rule.template_amount or first.amount
            rem = recurring_service.remaining(rule)
            g['remaining_label'] = rem['label']
            g['remaining_count'] = rem['left']
            g['remaining_amount'] = rem['left_amount']
        elif g['kind'] == 'installment':
            g['shipment_id'] = ident
            g['title'] = g['reseller'] and f'Борг магазину {g["reseller"]}' or (first.comment or 'Розстрочка')
            g['per_amount'] = first.amount
            g['frequency_label'] = 'розстрочка'
            g['remaining_count'] = g['planned_count']
            g['remaining_amount'] = g['planned_sum']
            g['remaining_label'] = f'лишилось {g["planned_count"]} платеж(і/ів)'
        else:  # onetime
            g['title'] = first.comment or (g['counterparty'] or g['category'] or 'Разовий платіж')
            g['per_amount'] = first.amount
            g['frequency_label'] = ''
            g['remaining_label'] = ''

        g['overdue'] = bool(g['next_due'] and g['next_due'] < today)
        g['overdue_days'] = (today - g['next_due']).days if g['overdue'] else 0
        g['next_due_iso'] = g['next_due'].isoformat() if g['next_due'] else ''
        g.pop('_txns', None)

        (income if g['type'] == Transaction.TYPE_INCOME else expense).append(g)

    def _sort(items):
        # Прострочені першими, далі за датою найближчого платежу.
        items.sort(key=lambda x: (not x['overdue'], x['next_due_iso'] or '9999'))
        return items

    _sort(income)
    _sort(expense)

    income_sum = sum((g['planned_sum'] for g in income), Decimal('0'))
    expense_sum = sum((g['planned_sum'] for g in expense), Decimal('0'))
    overdue_income = sum((g['planned_sum'] for g in income if g['overdue']), Decimal('0'))
    overdue_expense = sum((g['planned_sum'] for g in expense if g['overdue']), Decimal('0'))
    overdue_count = sum(1 for g in income + expense if g['overdue'])

    return {
        'income': income,
        'expense': expense,
        'income_sum': income_sum,
        'expense_sum': expense_sum,
        'net': income_sum - expense_sum,
        'overdue_income': overdue_income,
        'overdue_expense': overdue_expense,
        'overdue_count': overdue_count,
        'income_count': len(income),
        'expense_count': len(expense),
    }
