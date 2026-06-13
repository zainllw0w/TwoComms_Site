"""Точне погашення зобов'язань (кредиторка/дебіторка) з прив'язкою до реального платежу.

Дзеркало ``consignment.register_payment`` для загальних зобов'язань (повторювані +
разові планові). Два режими:
  - ``new_payment`` — створити новий фактичний платіж (expense/income) з рахунку;
  - ``pick_txn``    — прив'язати вже наявний фактичний платіж (НЕ дублюючи його,
                      тож баланс не змінюється — гроші вже пішли).

ІНВАРІАНТИ:
  • Погашення фактом НІКОЛИ не змінює ``template_amount`` (оцінку зобов'язання).
    Тому наступний місяць показує ту саму орієнтовну суму, а не фактично сплачену.
  • Повне погашення періоду повторюваного зобов'язання просуває його на наступний
    період (нагадування «перестрибує» на наступний місяць). Часткове — лишає
    залишок плановим на тому ж періоді.
  • Кожне погашення фіксується ``ObligationSettlement`` (молекулярна точність:
    яка сума, яким платежем, з якого рахунку, за який період).
"""
from __future__ import annotations

from decimal import Decimal

from django.db import transaction as db_transaction
from django.utils import timezone

from ..models import ObligationSettlement, Transaction
from . import cards as cards_service
from . import recurring as recurring_service
from . import transactions as txn_service


def _period_for(planned_txn) -> tuple[str, str]:
    """('YYYY-MM', 'MM.YYYY') періоду планового екземпляра."""
    d = planned_txn.date_actual.date() if planned_txn.date_actual else timezone.localdate()
    return f'{d.year}-{d.month:02d}', d.strftime('%m.%Y')


def _advance_rule(rule, *, user, from_date) -> None:
    """Просуває повторюване правило на наступний період (як settle_occurrence).

    next_occurrence лишається попереду (його виставив initial materialize), тож
    скасований поточний екземпляр НЕ регенерується (генерація йде лише вперед від
    next_occurrence). Викликаємо materialize, щоб тримати горизонт заповненим.
    """
    if rule is None or not rule.is_active:
        return
    if rule.next_occurrence is None or rule.next_occurrence <= from_date:
        nxt = recurring_service.calculate_next_occurrence(rule, from_date)
        if nxt is not None:
            rule.next_occurrence = nxt
            rule.save(update_fields=['next_occurrence'])
    recurring_service.materialize(rule, user=user)


@db_transaction.atomic
def settle_obligation(*, user, planned_txn, mode, amount=None, payment_txn=None,
                      account=None, date=None, counterparty=None,
                      full_period=None, remember_card=False, card_hint=None) -> dict:
    """Гасить зобов'язання, представлене найближчим плановим екземпляром.

    Повертає {'payment', 'settlement', 'full_period'}.
    """
    if planned_txn.status != Transaction.STATUS_PLANNED:
        raise ValueError("Гасити можна лише планове зобов'язання")

    company = planned_txn.company
    rule = planned_txn.recurrence_rule
    ttype = planned_txn.type
    plan_amount = planned_txn.amount or Decimal('0')
    counterparty = counterparty or planned_txn.counterparty
    when = date or timezone.now()
    period_key, period_label = _period_for(planned_txn)
    planned_date = planned_txn.date_actual.date() if planned_txn.date_actual else timezone.localdate()

    # --- Валідація режиму та суми ---
    if mode == 'new_payment':
        if amount in (None, ''):
            amount = plan_amount
        amount = Decimal(str(amount))
        if amount <= 0:
            raise ValueError('Сума має бути більшою за 0')
        if account is None:
            raise ValueError('Оберіть рахунок списання/зарахування')
    elif mode == 'pick_txn':
        if payment_txn is None:
            raise ValueError('Не обрано платіж')
        if payment_txn.status != Transaction.STATUS_ACTUAL:
            raise ValueError('Платіж має бути фактичним')
        if payment_txn.type != ttype:
            raise ValueError('Тип платежу не збігається із зобов\'язанням')
        if amount in (None, ''):
            amount = payment_txn.amount
        amount = Decimal(str(amount))
        if amount <= 0 or amount > payment_txn.amount:
            raise ValueError('Сума погашення невірна')
    else:
        raise ValueError(f'Невідомий режим: {mode}')

    if full_period is None:
        full_period = amount >= plan_amount

    # --- 1) Отримати/створити фактичний платіж ---
    if mode == 'new_payment':
        if full_period:
            # Провести саме цей плановий екземпляр як фактичний (advance + count
            # для count-режиму). template_amount settle_occurrence НЕ чіпає.
            payment = recurring_service.settle_occurrence(
                planned_txn, user=user, account=account, counterparty=counterparty,
                date_actual=when, amount=amount)
        else:
            payment = txn_service.create_transaction(
                user=user, type=ttype, status=Transaction.STATUS_ACTUAL,
                amount=amount, account=account,
                currency=account.currency if account else company.base_currency,
                counterparty=counterparty, date_actual=when,
                comment=(planned_txn.comment or (rule.title if rule else '')),
                source='manual', is_business=planned_txn.is_business)
    else:  # pick_txn — використовуємо наявний платіж, нічого не дублюємо.
        payment = payment_txn
        upd = {}
        if counterparty and not payment.counterparty_id:
            upd['counterparty'] = counterparty
        if rule and full_period and not payment.recurrence_rule_id:
            # Прив'язка до правила, щоб «скільки лишилось» (count) рахувало платіж.
            upd['recurrence_rule'] = rule
        if upd:
            txn_service.update_transaction(payment, user=user, **upd)

    # --- 2) Застосувати до планового екземпляра ---
    if full_period:
        if mode == 'pick_txn':
            # Плановий виконано наявним фактичним → скасувати, просунути правило.
            txn_service.update_transaction(planned_txn, user=user,
                                           status=Transaction.STATUS_CANCELLED)
            _advance_rule(rule, user=user, from_date=planned_date)
        # для new_payment full — settle_occurrence уже скасував/просунув.
    else:
        # Частково: зменшити плановий на сплачене (залишок лишається плановим).
        remainder = plan_amount - amount
        if remainder <= 0:
            txn_service.update_transaction(planned_txn, user=user,
                                           status=Transaction.STATUS_CANCELLED)
            _advance_rule(rule, user=user, from_date=planned_date)
            full_period = True
        else:
            txn_service.update_transaction(planned_txn, user=user, amount=remainder)

    # --- 3) Зв'язок-погашення (молекулярна точність) ---
    # planned_txn-посилання лишаємо лише коли плановий ще існує як окремий обʼєкт
    # (частково або pick_txn). Для new_payment full плановий СТАВ платежем.
    keep_planned_ref = not (full_period and mode == 'new_payment')
    settlement = ObligationSettlement.objects.create(
        company=company, payment=payment, rule=rule,
        planned_txn=(planned_txn if keep_planned_ref else None),
        period_key=period_key, period_label=period_label,
        amount=amount, currency=payment.currency,
        created_by=user if getattr(user, 'is_authenticated', False) else None,
    )

    # --- 4) Запам'ятати картку контрагента (за згодою) ---
    if remember_card and counterparty and card_hint:
        cards_service.upsert_card(
            counterparty, when=when,
            pan_mask=card_hint.get('pan_mask', ''), last4=card_hint.get('last4', ''),
            bank=card_hint.get('bank', ''), iban=card_hint.get('iban', ''))

    return {'payment': payment, 'settlement': settlement, 'full_period': full_period}


def payable_candidates(company, *, ttype, counterparty=None, limit=60) -> list:
    """Кандидати — фактичні платежі потрібного типу, ще не прив'язані до зобов'язань.

    Пріоритет: контрагент платежу збігається > рахунок прив'язаний до контрагента
    > решта. Підтягуємо суму/рахунок/дату для модалки погашення.
    """
    from .serializers import serialize_transaction
    qs = (Transaction.objects
          .filter(company=company, type=ttype, status=Transaction.STATUS_ACTUAL)
          .filter(settlements__isnull=True)
          .select_related('account', 'account__counterparty', 'counterparty')
          .order_by('-date_actual')[:200])
    out = []
    for t in qs:
        prio = 0
        if counterparty is not None:
            if t.counterparty_id == counterparty.id:
                prio = 3
            elif t.account_id and t.account.counterparty_id == counterparty.id:
                prio = 2
        data = serialize_transaction(t)
        data['_priority'] = prio
        out.append(data)
    out.sort(key=lambda d: (d['_priority'], d['date_actual'] or ''), reverse=True)
    return out[:limit]


def reverse_link_candidates(company, payment_txn) -> dict:
    """Для свіжого фактичного платежу — відкриті зобов'язання того ж контрагента.

    Повертає {'obligations': [...], 'counterparty_match': {...}}. Контрагента
    шукаємо за прямим counterparty платежу та за карткою (IBAN/маска/last4).
    """
    from . import obligations as obligations_service
    data = obligations_service.planned_obligations(company)
    side = (data['expense'] if payment_txn.type == Transaction.TYPE_EXPENSE
            else data['income'])

    match = cards_service.match_counterparty_by_payment(company, payment_txn)
    cp_ids = set()
    if payment_txn.counterparty_id:
        cp_ids.add(payment_txn.counterparty_id)
    if match['strong'] is not None:
        cp_ids.add(match['strong'].id)
    for c in match['candidates']:
        cp_ids.add(c.id)

    obligations = [g for g in side if g.get('counterparty_id') in cp_ids]
    return {'obligations': obligations, 'counterparty_match': match}


@db_transaction.atomic
def attach_payment_to_obligation(*, user, payment_txn, planned_txn,
                                 full_period=True, remember_card=False,
                                 card_hint=None) -> dict:
    """Обернений потік: прив'язати наявний платіж до зобов'язання (= pick_txn)."""
    return settle_obligation(
        user=user, planned_txn=planned_txn, mode='pick_txn',
        payment_txn=payment_txn, amount=payment_txn.amount,
        counterparty=planned_txn.counterparty, full_period=full_period,
        remember_card=remember_card, card_hint=card_hint)
