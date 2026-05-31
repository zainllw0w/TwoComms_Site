"""Бізнес-логіка модуля «Магазини під реалізацію» (consignment).

Усі грошові рухи проходять через ``services/transactions.py`` (єдина точка
перерахунку балансів + аудит). Борг магазину = планові income-транзакції
(``source='consignment'``, ``reseller=...``), що автоматично потрапляють у
дебіторку, прогноз і календар. Заморожені під реалізацію товари рахуються
агрегатом ``(qty - sold_qty) * unit_cost`` (патерн warehouse_link).
"""
from __future__ import annotations

import datetime as dt
from collections import OrderedDict
from decimal import Decimal

from django.db import transaction as db_transaction
from django.db.models import F, Sum
from django.utils import timezone

from ..models import (
    Attachment, Reseller, ConsignmentShipment, ConsignmentItem,
    ResellerPayment, ConsignmentSale, Transaction, get_default_company,
)
from . import audit as audit_service
from . import transactions as txn_service


# ----------------------------- Умови оплати -----------------------------

def validate_terms(kind: str, data: dict | None) -> dict:
    """Нормалізує та валідує JSON-параметри графіку оплати.

    Повертає очищений dict або кидає ValueError.
    """
    data = dict(data or {})
    out: dict = {}
    if kind == Reseller.TERMS_ONETIME:
        raw_due = data.get('due_days', 14)
        try:
            due = int(raw_due)
        except (TypeError, ValueError):
            raise ValueError('due_days має бути цілим числом')
        if due <= 0:
            raise ValueError('due_days має бути додатнім')
        out['due_days'] = due
    elif kind == Reseller.TERMS_INSTALLMENT:
        period = data.get('period', 'month')
        if period not in ('month', 'week'):
            raise ValueError('period має бути month або week')
        out['period'] = period
        out['every'] = max(1, int(data.get('every', 1) or 1))
        amount = data.get('amount')
        out['amount'] = str(Decimal(str(amount))) if amount not in (None, '', 0) else None
        periods = data.get('periods')
        out['periods'] = int(periods) if periods not in (None, '', 0) else None
        out['anchor_day'] = min(28, max(1, int(data.get('anchor_day', 1) or 1)))
    elif kind == Reseller.TERMS_PERIODIC:
        period = data.get('period', 'month')
        if period not in ('month', 'week'):
            raise ValueError('period має бути month або week')
        out['period'] = period
        out['every'] = max(1, int(data.get('every', 1) or 1))
        out['anchor_day'] = min(28, max(1, int(data.get('anchor_day', 1) or 1)))
    else:
        raise ValueError(f'Невідомий terms_kind: {kind}')
    return out


def _add_period(date: dt.date, period: str, every: int) -> dt.date:
    if period == 'week':
        return date + dt.timedelta(weeks=every)
    # month
    month = date.month - 1 + every
    year = date.year + month // 12
    month = month % 12 + 1
    day = min(date.day, 28)
    return dt.date(year, month, day)


def expected_due_date(reseller: Reseller, from_date: dt.date) -> dt.date:
    """Очікувана дата першого платежу за умовами магазину."""
    terms = reseller.terms or {}
    if reseller.terms_kind == Reseller.TERMS_ONETIME:
        return from_date + dt.timedelta(days=int(terms.get('due_days', 14) or 14))
    # installment / periodic — перший платіж через один період
    period = terms.get('period', 'month')
    every = int(terms.get('every', 1) or 1)
    return _add_period(from_date, period, every)


def payment_schedule(reseller: Reseller, *, from_date: dt.date | None = None,
                     horizon_days: int = 180) -> list[dict]:
    """Очікувані дати/суми платежів за умовами магазину (для графіку та KPI)."""
    from_date = from_date or timezone.localdate()
    horizon = from_date + dt.timedelta(days=horizon_days)
    terms = reseller.terms or {}
    out: list[dict] = []

    if reseller.terms_kind == Reseller.TERMS_ONETIME:
        due = from_date + dt.timedelta(days=int(terms.get('due_days', 14) or 14))
        if due <= horizon:
            out.append({'date': due.isoformat(), 'amount': None, 'kind': 'onetime'})
        return out

    period = terms.get('period', 'month')
    every = int(terms.get('every', 1) or 1)
    amount = terms.get('amount')
    amount_val = Decimal(str(amount)) if amount not in (None, '', 0) else None
    periods = terms.get('periods')
    max_periods = int(periods) if periods not in (None, '', 0) else None

    cursor = _add_period(from_date, period, every)
    count = 0
    # Якщо задано фіксовану кількість періодів — генеруємо рівно стільки
    # (не обмежуючись горизонтом). Інакше — до горизонту.
    while True:
        if max_periods is not None:
            if count >= max_periods:
                break
        elif cursor > horizon:
            break
        out.append({
            'date': cursor.isoformat(),
            'amount': str(amount_val) if amount_val is not None else None,
            'kind': reseller.terms_kind,
        })
        cursor = _add_period(cursor, period, every)
        count += 1
    return out


# ----------------------------- CRUD магазину -----------------------------

@db_transaction.atomic
def create_reseller(*, user, name, counterparty=None, terms_kind=Reseller.TERMS_INSTALLMENT,
                    terms=None, contacts=None, notes='', status=Reseller.STATUS_ACTIVE) -> Reseller:
    company = get_default_company()
    clean_terms = validate_terms(terms_kind, terms)
    reseller = Reseller.objects.create(
        company=company, name=name, counterparty=counterparty,
        terms_kind=terms_kind, terms=clean_terms, contacts=contacts or {},
        notes=notes or '', status=status,
    )
    audit_service.log_action(
        user, 'create', 'reseller', reseller.id,
        summary=f'Створено магазин {reseller.name}', company=company,
    )
    return reseller


@db_transaction.atomic
def update_reseller(reseller: Reseller, *, user, **fields) -> Reseller:
    if 'terms_kind' in fields or 'terms' in fields:
        kind = fields.get('terms_kind', reseller.terms_kind)
        fields['terms_kind'] = kind
        fields['terms'] = validate_terms(kind, fields.get('terms', reseller.terms))
    for key, value in fields.items():
        setattr(reseller, key, value)
    reseller.save()
    audit_service.log_action(
        user, 'update', 'reseller', reseller.id,
        summary=f'Оновлено магазин {reseller.name}', company=reseller.company,
    )
    return reseller


@db_transaction.atomic
def delete_reseller(reseller: Reseller, *, user, force: bool = False) -> bool:
    """Видалення магазину. Заборонено при борг>0 або frozen>0 (без force).

    Повертає True якщо видалено, False якщо заблоковано.
    """
    if not force and (reseller_debt(reseller) > 0 or reseller_frozen(reseller) > 0):
        return False
    company = reseller.company
    name = reseller.name
    rid = reseller.id
    # Планові борги видаляємо (planned не впливає на баланс); фактичні виплати
    # лишаються (reseller=SET_NULL).
    for txn in reseller.transactions.filter(status=Transaction.STATUS_PLANNED):
        txn_service.delete_transaction(txn, user=user)
    reseller.delete()
    audit_service.log_action(
        user, 'delete', 'reseller', rid,
        summary=f'Видалено магазин {name}', company=company,
    )
    return True


# ----------------------------- Поставка -----------------------------

@db_transaction.atomic
def create_shipment(*, user, reseller, date, number='', debt_amount=Decimal('0'),
                    currency=None, comment='', items=None, attachments=None,
                    external_source='', external_ref='') -> ConsignmentShipment:
    """Створює поставку + позиції + (за наявності боргу) планову income-транзакцію.

    items: список dict з ключами source_kind, stock_item(opt), title, print_name,
    color, size, qty, unit_cost, unit_price, is_consignment, comment, external_ref.
    """
    company = reseller.company
    currency = currency or company.base_currency
    debt_amount = Decimal(str(debt_amount or 0))

    shipment = ConsignmentShipment.objects.create(
        company=company, reseller=reseller, number=number or '', date=date,
        debt_amount=debt_amount, currency=currency, comment=comment or '',
        external_source=external_source or '', external_ref=external_ref or '',
    )
    if attachments:
        shipment.attachments.set(attachments)

    debt_from_items = Decimal('0')
    for raw in (items or []):
        item = _create_item(company, shipment, reseller, raw)
        if not item.is_consignment:
            debt_from_items += item.line_total

    debt_total = debt_amount + debt_from_items
    if debt_total > 0:
        due = expected_due_date(reseller, date)
        txn = txn_service.create_transaction(
            user=user, type=Transaction.TYPE_INCOME, status=Transaction.STATUS_PLANNED,
            amount=debt_total, currency=currency, account=None,
            counterparty=reseller.counterparty,
            date_actual=timezone.make_aware(dt.datetime.combine(due, dt.time(12, 0))),
            comment=f'Поставка №{number or shipment.id} → {reseller.name}',
            source='consignment', is_business=True,
        )
        txn.reseller = reseller
        txn.save(update_fields=['reseller'])
        shipment.debt_txn = txn
        shipment.save(update_fields=['debt_txn'])

    audit_service.log_action(
        user, 'create', 'consignment_shipment', shipment.id,
        summary=f'Поставка магазину {reseller.name} на {debt_total} {currency}',
        company=company,
    )
    return shipment


def _create_item(company, shipment, reseller, raw: dict) -> ConsignmentItem:
    """Створює позицію; для source_kind='stock' робить snapshot полів зі StockItem."""
    source_kind = raw.get('source_kind', ConsignmentItem.SOURCE_MANUAL)
    title = raw.get('title', '')
    print_name = raw.get('print_name', '')
    color = raw.get('color', '')
    size = raw.get('size', '')
    unit_cost = Decimal(str(raw.get('unit_cost', 0) or 0))
    stock_item = None

    if source_kind == ConsignmentItem.SOURCE_STOCK and raw.get('stock_item_id'):
        try:
            from warehouse.models import StockItem
            stock_item = StockItem.objects.filter(pk=raw['stock_item_id']).first()
        except Exception:
            stock_item = None
        if stock_item is not None:
            # Snapshot — стабільніше за live-FK.
            title = title or str(stock_item.subcategory)
            color = color or stock_item.color_display
            size = size or stock_item.size
            if not unit_cost:
                unit_cost = Decimal(str(stock_item.cost_price))

    return ConsignmentItem.objects.create(
        company=company, shipment=shipment, reseller=reseller,
        source_kind=source_kind, stock_item=stock_item,
        external_ref=raw.get('external_ref', ''),
        title=title or 'Позиція', print_name=print_name, color=color, size=size,
        qty=int(raw.get('qty', 0) or 0),
        unit_cost=unit_cost,
        unit_price=Decimal(str(raw.get('unit_price', 0) or 0)),
        is_consignment=bool(raw.get('is_consignment', True)),
        comment=raw.get('comment', ''),
    )


@db_transaction.atomic
def delete_shipment(shipment: ConsignmentShipment, *, user) -> None:
    company = shipment.company
    sid = shipment.id
    if shipment.debt_txn_id:
        try:
            txn_service.delete_transaction(shipment.debt_txn, user=user)
        except Exception:
            pass
    shipment.delete()
    audit_service.log_action(
        user, 'delete', 'consignment_shipment', sid,
        summary='Видалено поставку', company=company,
    )


# ----------------------------- Борг та заморожено -----------------------------

def reseller_debt(reseller: Reseller) -> Decimal:
    """Поточний борг магазину = Σ amount_base планових income-транзакцій."""
    agg = (reseller.transactions
           .filter(status=Transaction.STATUS_PLANNED, type=Transaction.TYPE_INCOME)
           .exclude(excluded_from_reports=True)
           .aggregate(s=Sum('amount_base')))
    return agg['s'] or Decimal('0')


def reseller_frozen(reseller: Reseller) -> Decimal:
    """Заморожено під реалізацію = Σ (qty - sold_qty) * unit_cost консигнаційних."""
    total = Decimal('0')
    items = reseller.consignment_items.filter(is_consignment=True).only(
        'qty', 'sold_qty', 'unit_cost')
    for item in items:
        total += item.frozen_value
    return total


def reseller_frozen_qty(reseller: Reseller) -> int:
    agg = (reseller.consignment_items.filter(is_consignment=True)
           .aggregate(q=Sum(F('qty') - F('sold_qty'))))
    return int(agg['q'] or 0)


def reseller_overdue_days(reseller: Reseller) -> int:
    """Макс. прострочка (днів) серед планових боргів магазину."""
    today = timezone.localdate()
    overdue = (reseller.transactions
               .filter(status=Transaction.STATUS_PLANNED, type=Transaction.TYPE_INCOME,
                       date_actual__date__lt=today)
               .order_by('date_actual').first())
    if not overdue:
        return 0
    return (today - overdue.date_actual.date()).days


def consignment_frozen_total(company) -> Decimal:
    """Загальна заморожена під реалізацію сума (для сайдбару/дашборду).

    Graceful: повертає 0 при будь-якій помилці.
    """
    try:
        total = Decimal('0')
        items = (ConsignmentItem.objects
                 .filter(company=company, is_consignment=True)
                 .only('qty', 'sold_qty', 'unit_cost'))
        for item in items:
            total += item.frozen_value
        return total
    except Exception:
        return Decimal('0')


def consignment_frozen_breakdown(company) -> dict:
    """Деталізація замороженого під реалізацію по магазинах."""
    try:
        by_reseller = []
        total = Decimal('0')
        total_qty = 0
        for reseller in Reseller.objects.filter(company=company).exclude(status=Reseller.STATUS_CLOSED):
            frozen = reseller_frozen(reseller)
            qty = reseller_frozen_qty(reseller)
            if frozen > 0 or qty > 0:
                by_reseller.append({'name': reseller.name, 'value': frozen, 'qty': qty})
                total += frozen
                total_qty += qty
        by_reseller.sort(key=lambda x: x['value'], reverse=True)
        return {'by_reseller': by_reseller, 'total': total, 'qty': total_qty}
    except Exception:
        return {'by_reseller': [], 'total': Decimal('0'), 'qty': 0}


def resellers_debt_total(company) -> Decimal:
    """Сумарний борг усіх магазинів."""
    agg = (Transaction.objects
           .filter(company=company, status=Transaction.STATUS_PLANNED,
                   type=Transaction.TYPE_INCOME, reseller__isnull=False)
           .exclude(excluded_from_reports=True)
           .aggregate(s=Sum('amount_base')))
    return agg['s'] or Decimal('0')


# ----------------------------- Виплати -----------------------------

def _apply_to_debt(reseller: Reseller, amount: Decimal, *, user) -> Decimal:
    """Зменшує планові борги магазину на ``amount`` (FIFO за датою).

    Повертає суму, що залишилась незастосованою (переплата). Планову, повністю
    покриту, скасовуємо (status=cancelled), часткову — зменшуємо.
    """
    remaining = Decimal(str(amount))
    planned = (reseller.transactions
               .filter(status=Transaction.STATUS_PLANNED, type=Transaction.TYPE_INCOME)
               .exclude(excluded_from_reports=True)
               .order_by('date_actual'))
    for txn in planned:
        if remaining <= 0:
            break
        debt = txn.amount
        if remaining >= debt:
            # Повне покриття — борг закрито (факт проведено окремою виплатою).
            txn_service.update_transaction(txn, user=user, status=Transaction.STATUS_CANCELLED)
            remaining -= debt
        else:
            # Часткове — зменшуємо суму планової.
            txn_service.update_transaction(txn, user=user, amount=debt - remaining)
            remaining = Decimal('0')
    return remaining


@db_transaction.atomic
def register_payment(*, user, reseller, mode, amount=None, txn=None, account=None,
                     date=None, link_account_cp=False, comment='') -> ResellerPayment:
    """Реєструє виплату магазину та гасить борг.

    mode='manual_cash' → створює нову actual income-транзакцію (готівка) на
        ``amount`` через ``account`` (recalc балансу), прив'язує reseller.
    mode='pick_txn'    → використовує наявну actual income ``txn``; ``amount``
        обов'язковий. Опційно прив'язує account до контрагента магазину.
    Потім зменшує планові борги на ``amount``. Надлишок не йде в мінус.
    """
    company = reseller.company
    date = date or timezone.localdate()

    if mode == 'manual_cash':
        if amount is None or Decimal(str(amount)) <= 0:
            raise ValueError('Сума виплати обовʼязкова')
        amount = Decimal(str(amount))
        paid_txn = txn_service.create_transaction(
            user=user, type=Transaction.TYPE_INCOME, status=Transaction.STATUS_ACTUAL,
            amount=amount, account=account,
            currency=account.currency if account else company.base_currency,
            counterparty=reseller.counterparty,
            date_actual=timezone.make_aware(dt.datetime.combine(date, dt.time(12, 0))),
            comment=comment or f'Виплата від {reseller.name}',
            source='consignment', is_business=True,
        )
        paid_txn.reseller = reseller
        paid_txn.save(update_fields=['reseller'])
    elif mode == 'pick_txn':
        if txn is None:
            raise ValueError('Не обрано транзакцію')
        if amount is None or Decimal(str(amount)) <= 0:
            raise ValueError('Сума виплати обовʼязкова')
        amount = Decimal(str(amount))
        paid_txn = txn
        # Прив'язуємо транзакцію до магазину.
        if paid_txn.reseller_id != reseller.id:
            paid_txn.reseller = reseller
            paid_txn.save(update_fields=['reseller'])
        # Прив'язуємо рахунок до контрагента (за згодою), якщо ще не привʼязаний.
        if (link_account_cp and reseller.counterparty_id and paid_txn.account_id
                and not paid_txn.account.counterparty_id):
            paid_txn.account.counterparty = reseller.counterparty
            paid_txn.account.save(update_fields=['counterparty'])
    else:
        raise ValueError(f'Невідомий mode: {mode}')

    payment = ResellerPayment.objects.create(
        company=company, reseller=reseller, date=date, amount=amount,
        currency=paid_txn.currency, txn=paid_txn, comment=comment or '',
    )
    overpay = _apply_to_debt(reseller, amount, user=user)
    if overpay > 0:
        payment.comment = (payment.comment + f' (переплата {overpay})').strip()
        payment.save(update_fields=['comment'])

    audit_service.log_action(
        user, 'create', 'reseller_payment', payment.id,
        summary=f'Виплата {amount} від {reseller.name}', company=company,
    )
    return payment


def payable_txn_candidates(reseller: Reseller) -> list:
    """Кандидати-транзакції для погашення (actual income).

    Пріоритет: транзакції рахунків, привʼязаних до контрагента магазину,
    потім транзакції без привʼязки рахунку до контрагента. Уже привʼязані до
    іншого магазину — виключаємо.
    """
    from .serializers import serialize_transaction
    company = reseller.company
    qs = (Transaction.objects
          .filter(company=company, type=Transaction.TYPE_INCOME,
                  status=Transaction.STATUS_ACTUAL)
          .filter(reseller__isnull=True)
          .select_related('account', 'account__counterparty')
          .order_by('-date_actual')[:100])
    out = []
    for t in qs:
        acc_cp = t.account.counterparty_id if t.account_id else None
        priority = 0
        if reseller.counterparty_id and acc_cp == reseller.counterparty_id:
            priority = 2
        elif not acc_cp:
            priority = 1
        data = serialize_transaction(t)
        data['account_has_counterparty'] = bool(acc_cp)
        data['_priority'] = priority
        out.append(data)
    out.sort(key=lambda d: (d['_priority'], d['date_actual'] or ''), reverse=True)
    return out


# ----------------------------- Продаж позиції -----------------------------

@db_transaction.atomic
def register_sale(*, user, item: ConsignmentItem, qty, date=None, unit_price=None,
                  creates_debt=False) -> ConsignmentSale:
    """Фіксація продажу позиції під реалізацію.

    Збільшує ``sold_qty`` (валідація ≤ qty), зменшує frozen_value. Опційно
    створює планову income-транзакцію (борг магазину за проданий товар).
    """
    qty = int(qty)
    if qty <= 0:
        raise ValueError('Кількість має бути додатньою')
    if item.sold_qty + qty > item.qty:
        raise ValueError(
            f'Не можна продати {qty}: залишок {item.remaining_qty} з {item.qty}')

    date = date or timezone.localdate()
    unit_price = Decimal(str(unit_price)) if unit_price is not None else item.unit_price
    reseller = item.reseller
    company = reseller.company

    sale = ConsignmentSale.objects.create(
        company=company, reseller=reseller, item=item, qty=qty, date=date,
        unit_price=unit_price, creates_debt=bool(creates_debt),
    )
    item.sold_qty += qty
    item.save(update_fields=['sold_qty'])

    if creates_debt and unit_price > 0:
        due = expected_due_date(reseller, date)
        txn = txn_service.create_transaction(
            user=user, type=Transaction.TYPE_INCOME, status=Transaction.STATUS_PLANNED,
            amount=unit_price * qty, currency=company.base_currency, account=None,
            counterparty=reseller.counterparty,
            date_actual=timezone.make_aware(dt.datetime.combine(due, dt.time(12, 0))),
            comment=f'Продаж {qty} × {item.title} → {reseller.name}',
            source='consignment', is_business=True,
        )
        txn.reseller = reseller
        txn.save(update_fields=['reseller'])
        sale.debt_txn = txn
        sale.save(update_fields=['debt_txn'])

    audit_service.log_action(
        user, 'create', 'consignment_sale', sale.id,
        summary=f'Продаж {qty} × {item.title} ({reseller.name})', company=company,
    )
    return sale


# ----------------------------- Статистика магазину -----------------------------

def reseller_timeline(reseller: Reseller) -> list[dict]:
    """Історія магазину: поставки + виплати + продажі, відсортовано за датою."""
    events = []
    for s in reseller.shipments.all():
        events.append({
            'date': s.date.isoformat(), 'kind': 'shipment',
            'label': f'Поставка №{s.number or s.id}',
            'amount': float(s.total_debt), 'sign': '+',
        })
    for p in reseller.payments.all():
        events.append({
            'date': p.date.isoformat(), 'kind': 'payment',
            'label': p.comment or 'Виплата',
            'amount': float(p.amount), 'sign': '-',
        })
    for sale in reseller.sales.select_related('item').all():
        events.append({
            'date': sale.date.isoformat(), 'kind': 'sale',
            'label': f'Продаж {sale.qty} × {sale.item.title}',
            'amount': float(sale.qty * sale.unit_price), 'sign': '',
        })
    events.sort(key=lambda e: e['date'], reverse=True)
    return events


def reseller_stats(reseller: Reseller, *, period_days: int = 180) -> dict:
    """Зведена статистика магазину для сторінки деталі та графіків."""
    today = timezone.localdate()
    period_start = today - dt.timedelta(days=period_days)

    debt = reseller_debt(reseller)
    frozen = reseller_frozen(reseller)
    frozen_qty = reseller_frozen_qty(reseller)
    overdue = reseller_overdue_days(reseller)

    # Виплати по місяцях
    payments_by_month = OrderedDict()
    payments_total = Decimal('0')
    for p in reseller.payments.all():
        key = p.date.strftime('%Y-%m')
        payments_by_month[key] = payments_by_month.get(key, Decimal('0')) + p.amount
        payments_total += p.amount

    # Продажі/виручка за період
    revenue_period = Decimal('0')
    sold_qty_period = 0
    for sale in reseller.sales.filter(date__gte=period_start).select_related('item'):
        revenue_period += sale.qty * sale.unit_price
        sold_qty_period += sale.qty

    # Топ товарів (продано / заморожено)
    top_items = []
    for item in reseller.consignment_items.all():
        if item.sold_qty > 0 or item.frozen_value > 0:
            top_items.append({
                'title': item.title, 'size': item.size, 'color': item.color,
                'sold': item.sold_qty, 'remaining': item.remaining_qty,
                'frozen': float(item.frozen_value),
            })
    top_items.sort(key=lambda x: (x['sold'], x['frozen']), reverse=True)

    schedule = payment_schedule(reseller)
    next_payment = schedule[0] if schedule else None

    return {
        'debt': debt, 'frozen': frozen, 'frozen_qty': frozen_qty,
        'overdue_days': overdue,
        'payments_total': payments_total,
        'payments_by_month': sorted(payments_by_month.items()),
        'revenue_period': revenue_period, 'sold_qty_period': sold_qty_period,
        'schedule': schedule, 'next_payment': next_payment,
        'top_items': top_items[:20],
        'timeline': reseller_timeline(reseller),
    }


# ----------------------------- Заглушка менеджмент-імпорту -----------------------------

def import_from_management(reseller, external_ref: str, *, user) -> list:
    """Хук-заглушка для майбутньої інтеграції з менеджментом (тестові партії).

    Поки no-op: повертає порожній список. Підключиться без зміни схеми.
    """
    return []
