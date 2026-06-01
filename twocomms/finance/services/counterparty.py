"""Історія по контрагенту: усі операції, рахунки та підсумки.

Дозволяє бізнесу подивитися по конкретному контрагенту — що і коли з ним було,
через які рахунки проходили кошти, скільки ще заплановано (борг/зобов'язання).
Дані беруться з тих самих транзакцій (єдине джерело правди), плюс рахунки,
прив'язані до контрагента (``Account.counterparty``).
"""
from __future__ import annotations

from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from ..models import Account, Counterparty, Transaction
from . import serializers as ser


def counterparty_history(company, counterparty: Counterparty, *, limit: int = 200) -> dict:
    """Зведена історія по контрагенту.

    Повертає:
      transactions  — серіалізовані операції (фактичні + планові), новіші зверху;
      accounts      — рахунки, прив'язані до контрагента або задіяні в операціях;
      totals        — отримано/сплачено (фактичні) та заплановано (планові).
    """
    qs = (Transaction.objects
          .filter(company=company, counterparty=counterparty)
          .select_related('account', 'to_account', 'category', 'project',
                          'counterparty', 'recurrence_rule', 'reseller')
          .order_by('-date_actual', '-id'))

    received = Decimal('0')   # фактичні доходи від контрагента
    paid = Decimal('0')       # фактичні витрати на контрагента
    planned_in = Decimal('0')
    planned_out = Decimal('0')
    account_ids = set()

    rows = []
    for t in qs[:limit]:
        rows.append(ser.serialize_transaction(t))
        if t.account_id:
            account_ids.add(t.account_id)
        base = t.amount_base or t.amount or Decimal('0')
        if t.status == Transaction.STATUS_ACTUAL:
            if t.type == Transaction.TYPE_INCOME:
                received += base
            elif t.type == Transaction.TYPE_EXPENSE:
                paid += base
        elif t.status == Transaction.STATUS_PLANNED:
            if t.type == Transaction.TYPE_INCOME:
                planned_in += base
            elif t.type == Transaction.TYPE_EXPENSE:
                planned_out += base

    # Рахунки: прив'язані до контрагента + задіяні в операціях.
    linked = Account.objects.filter(company=company, counterparty=counterparty)
    for a in linked:
        account_ids.add(a.id)

    accounts = []
    for a in Account.objects.filter(company=company, id__in=account_ids):
        accounts.append({
            'id': a.id, 'name': a.name, 'currency': a.currency,
            'linked': a.counterparty_id == counterparty.id,
            'balance': ser.money(a.current_balance, a.currency),
        })

    cur = company.base_currency
    return {
        'counterparty': {
            'id': counterparty.id, 'name': counterparty.name,
            'type': counterparty.get_type_display(),
        },
        'transactions': rows,
        'accounts': accounts,
        'totals': {
            'received': ser.money(received, cur),
            'paid': ser.money(paid, cur),
            'net': ser.money(received - paid, cur, signed=True),
            'planned_in': ser.money(planned_in, cur),
            'planned_out': ser.money(planned_out, cur),
        },
    }
