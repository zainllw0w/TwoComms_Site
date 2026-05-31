"""Розділ «Магазини під реалізацію» (consignment): список, деталь, CRUD, виплати."""
from __future__ import annotations

import datetime as dt
import json
from decimal import Decimal, InvalidOperation

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET, require_POST

from ..models import (
    Attachment, Reseller, ConsignmentShipment, ConsignmentItem,
    Transaction, get_default_company,
)
from ..permissions import finance_access_required
from ..services import consignment as svc
from ..services import serializers as ser


def _body(request):
    if request.content_type and 'application/json' in request.content_type:
        try:
            return json.loads(request.body or '{}')
        except (ValueError, TypeError):
            return {}
    return request.POST


def _dec(value, default='0') -> Decimal:
    try:
        return Decimal(str(value if value not in (None, '') else default))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal(default)


def _parse_date(value):
    if not value:
        from django.utils import timezone
        return timezone.localdate()
    try:
        return dt.date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        from django.utils import timezone
        return timezone.localdate()


# ----------------------------- Сторінки -----------------------------

@finance_access_required
def consignment_list(request):
    company = get_default_company()

    status_filter = (request.GET.get('status') or '').strip()
    q = (request.GET.get('q') or '').strip()

    resellers_qs = Reseller.objects.filter(company=company).select_related('counterparty')
    if status_filter:
        resellers_qs = resellers_qs.filter(status=status_filter)
    if q:
        resellers_qs = resellers_qs.filter(name__icontains=q)

    rows = []
    total_debt = Decimal('0')
    total_frozen = Decimal('0')
    soonest = None
    for r in resellers_qs:
        debt = svc.reseller_debt(r)
        frozen = svc.reseller_frozen(r)
        overdue = svc.reseller_overdue_days(r)
        schedule = svc.payment_schedule(r, horizon_days=90)
        next_pay = schedule[0] if schedule else None
        if next_pay and (soonest is None or next_pay['date'] < soonest):
            soonest = next_pay['date']
        total_debt += debt
        total_frozen += frozen
        rows.append({
            'id': r.id, 'name': r.name,
            'counterparty': r.counterparty.name if r.counterparty else '',
            'status': r.status, 'status_display': r.get_status_display(),
            'terms_display': r.get_terms_kind_display(),
            'debt': ser.money(debt, company.base_currency),
            'debt_raw': debt,
            'frozen': ser.money(frozen, company.base_currency),
            'frozen_raw': frozen,
            'overdue_days': overdue,
            'next_payment': next_pay['date'] if next_pay else '',
        })

    rows.sort(key=lambda x: (x['debt_raw'] + x['frozen_raw']), reverse=True)

    return render(request, 'finance/consignment/list.html', {
        'active_tab': 'consignment',
        'rows': rows,
        'total_count': len(rows),
        'total_debt': ser.money(total_debt, company.base_currency),
        'total_frozen': ser.money(total_frozen, company.base_currency),
        'soonest_payment': soonest or '',
        'status_filter': status_filter,
        'q': q,
        'statuses': Reseller.STATUS_CHOICES,
        'dropdowns': ser.serialize_dropdowns(company),
        'terms_kinds': Reseller.TERMS_CHOICES,
    })


@finance_access_required
def consignment_detail(request, reseller_id):
    company = get_default_company()
    reseller = get_object_or_404(Reseller, id=reseller_id, company=company)
    stats = svc.reseller_stats(reseller)

    # Товари під реалізацію (з залишком або проданим)
    items = []
    for item in reseller.consignment_items.select_related('shipment').all():
        items.append({
            'id': item.id, 'title': item.title, 'print_name': item.print_name,
            'color': item.color, 'size': item.size,
            'qty': item.qty, 'sold_qty': item.sold_qty, 'remaining': item.remaining_qty,
            'unit_cost': ser.money(item.unit_cost, company.base_currency),
            'unit_price': ser.money(item.unit_price, company.base_currency),
            'frozen': ser.money(item.frozen_value, company.base_currency),
            'is_consignment': item.is_consignment,
        })

    # Поставки
    shipments = []
    for s in reseller.shipments.prefetch_related('items', 'attachments').all():
        shipments.append({
            'id': s.id, 'number': s.number, 'ttn': s.ttn, 'date': s.date.isoformat(),
            'total_debt': ser.money(s.total_debt, company.base_currency),
            'comment': s.comment,
            'attachments': [{'name': a.original_name or a.file.name,
                             'url': a.file.url} for a in s.attachments.all()],
            'items_count': s.items.count(),
        })

    chart_data = {
        'payments_by_month': [{'month': m, 'amount': float(a)} for m, a in stats['payments_by_month']],
        'schedule': stats['schedule'],
        'timeline': stats['timeline'],
    }

    return render(request, 'finance/consignment/detail.html', {
        'active_tab': 'consignment',
        'reseller': reseller,
        'stats': stats,
        'debt': ser.money(stats['debt'], company.base_currency),
        'frozen': ser.money(stats['frozen'], company.base_currency),
        'frozen_qty': stats['frozen_qty'],
        'overdue_days': stats['overdue_days'],
        'revenue_period': ser.money(stats['revenue_period'], company.base_currency),
        'sold_qty_period': stats['sold_qty_period'],
        'payments_total': ser.money(stats['payments_total'], company.base_currency),
        'next_payment': stats['next_payment'],
        'items': items,
        'shipments': shipments,
        'timeline': stats['timeline'],
        'top_items': stats['top_items'],
        'chart_data': json.dumps(chart_data),
        'dropdowns': ser.serialize_dropdowns(company),
        'terms_kinds': Reseller.TERMS_CHOICES,
        'statuses': Reseller.STATUS_CHOICES,
    })


# ----------------------------- CRUD магазину -----------------------------

@finance_access_required(api=True)
@require_POST
def consignment_reseller_create_api(request):
    company = get_default_company()
    data = _body(request)
    name = (data.get('name') or '').strip()
    if not name:
        return JsonResponse({'ok': False, 'error': 'Вкажіть назву магазину'}, status=400)

    counterparty = None
    cp_id = data.get('counterparty_id')
    if cp_id:
        counterparty = company.counterparties.filter(id=cp_id).first()

    terms = data.get('terms') or {}
    if isinstance(terms, str):
        try:
            terms = json.loads(terms)
        except (ValueError, TypeError):
            terms = {}

    try:
        reseller = svc.create_reseller(
            user=request.user, name=name, counterparty=counterparty,
            terms_kind=data.get('terms_kind', Reseller.TERMS_INSTALLMENT),
            terms=terms, contacts=data.get('contacts') or {},
            notes=data.get('notes', ''), status=data.get('status', Reseller.STATUS_ACTIVE),
        )
    except ValueError as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)
    return JsonResponse({'ok': True, 'id': reseller.id})


@finance_access_required(api=True)
@require_POST
def consignment_reseller_update_api(request, reseller_id):
    company = get_default_company()
    reseller = get_object_or_404(Reseller, id=reseller_id, company=company)
    data = _body(request)
    fields = {}
    if 'name' in data:
        fields['name'] = (data.get('name') or '').strip()
    if 'status' in data:
        fields['status'] = data.get('status')
    if 'notes' in data:
        fields['notes'] = data.get('notes', '')
    if 'contacts' in data:
        fields['contacts'] = data.get('contacts') or {}
    if 'counterparty_id' in data:
        cp = company.counterparties.filter(id=data.get('counterparty_id')).first()
        fields['counterparty'] = cp
    if 'terms_kind' in data:
        fields['terms_kind'] = data.get('terms_kind')
    if 'terms' in data:
        terms = data.get('terms') or {}
        if isinstance(terms, str):
            try:
                terms = json.loads(terms)
            except (ValueError, TypeError):
                terms = {}
        fields['terms'] = terms
    try:
        svc.update_reseller(reseller, user=request.user, **fields)
    except ValueError as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)
    return JsonResponse({'ok': True})


@finance_access_required(api=True)
@require_POST
def consignment_reseller_delete_api(request, reseller_id):
    company = get_default_company()
    reseller = get_object_or_404(Reseller, id=reseller_id, company=company)
    data = _body(request)
    force = bool(data.get('force'))
    ok = svc.delete_reseller(reseller, user=request.user, force=force)
    if not ok:
        return JsonResponse({
            'ok': False,
            'error': 'Магазин має непогашений борг або заморожені товари. '
                     'Спершу погасіть борг або підтвердіть видалення.',
            'needs_force': True,
        }, status=400)
    return JsonResponse({'ok': True})


# ----------------------------- Поставки -----------------------------

@finance_access_required(api=True)
@require_POST
def consignment_shipment_create_api(request, reseller_id):
    company = get_default_company()
    reseller = get_object_or_404(Reseller, id=reseller_id, company=company)

    # Multipart (файли + items JSON) або JSON.
    if request.content_type and 'multipart' in request.content_type:
        data = request.POST
        items_raw = data.get('items', '[]')
    else:
        data = _body(request)
        items_raw = data.get('items', [])

    try:
        items = json.loads(items_raw) if isinstance(items_raw, str) else (items_raw or [])
    except (ValueError, TypeError):
        items = []

    # Файли-вкладення.
    attachments = []
    for f in request.FILES.getlist('files'):
        att = Attachment.objects.create(
            company=company, file=f, original_name=f.name,
            content_type=getattr(f, 'content_type', ''), size=f.size,
            uploaded_by=request.user if request.user.is_authenticated else None,
        )
        attachments.append(att)

    try:
        shipment = svc.create_shipment(
            user=request.user, reseller=reseller,
            date=_parse_date(data.get('date')),
            number=data.get('number', ''),
            ttn=data.get('ttn', ''),
            debt_amount=_dec(data.get('debt_amount', 0)),
            currency=data.get('currency') or company.base_currency,
            comment=data.get('comment', ''),
            items=items, attachments=attachments,
            external_source=data.get('external_source', ''),
            external_ref=data.get('external_ref', ''),
            payment_monthly=_dec(data.get('payment_monthly')) if data.get('payment_monthly') else None,
        )
    except ValueError as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)
    return JsonResponse({'ok': True, 'id': shipment.id})


@finance_access_required(api=True)
@require_POST
def consignment_shipment_delete_api(request, shipment_id):
    company = get_default_company()
    shipment = get_object_or_404(ConsignmentShipment, id=shipment_id, company=company)
    svc.delete_shipment(shipment, user=request.user)
    return JsonResponse({'ok': True})


# ----------------------------- Продаж -----------------------------

@finance_access_required(api=True)
@require_POST
def consignment_sale_create_api(request, item_id):
    company = get_default_company()
    item = get_object_or_404(ConsignmentItem, id=item_id, company=company)
    data = _body(request)
    try:
        sale = svc.register_sale(
            user=request.user, item=item, qty=int(data.get('qty', 0) or 0),
            date=_parse_date(data.get('date')),
            unit_price=_dec(data.get('unit_price', item.unit_price)),
            creates_debt=bool(data.get('creates_debt')),
        )
    except (ValueError, TypeError) as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)
    return JsonResponse({'ok': True, 'id': sale.id})


# ----------------------------- Виплати -----------------------------

@finance_access_required(api=True)
@require_GET
def consignment_payable_txns_api(request, reseller_id):
    company = get_default_company()
    reseller = get_object_or_404(Reseller, id=reseller_id, company=company)
    return JsonResponse({'ok': True, 'candidates': svc.payable_txn_candidates(reseller)})


@finance_access_required(api=True)
@require_POST
def consignment_payment_api(request, reseller_id):
    company = get_default_company()
    reseller = get_object_or_404(Reseller, id=reseller_id, company=company)
    data = _body(request)
    mode = data.get('mode', 'manual_cash')

    txn = None
    account = None
    if mode == 'pick_txn':
        txn = Transaction.objects.filter(
            id=data.get('txn_id'), company=company).first()
        if txn is None:
            return JsonResponse({'ok': False, 'error': 'Транзакцію не знайдено'}, status=400)
    elif mode == 'manual_cash':
        account = company.accounts.filter(id=data.get('account_id')).first()
        if account is None:
            return JsonResponse({'ok': False, 'error': 'Оберіть рахунок'}, status=400)

    try:
        payment = svc.register_payment(
            user=request.user, reseller=reseller, mode=mode,
            amount=_dec(data.get('amount', 0)), txn=txn, account=account,
            date=_parse_date(data.get('date')),
            link_account_cp=bool(data.get('link_account_cp')),
            comment=data.get('comment', ''),
        )
    except ValueError as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)
    return JsonResponse({'ok': True, 'id': payment.id})


@finance_access_required(api=True)
@require_GET
def consignment_stats_api(request, reseller_id):
    company = get_default_company()
    reseller = get_object_or_404(Reseller, id=reseller_id, company=company)
    stats = svc.reseller_stats(reseller)
    return JsonResponse({
        'ok': True,
        'debt': float(stats['debt']),
        'frozen': float(stats['frozen']),
        'frozen_qty': stats['frozen_qty'],
        'overdue_days': stats['overdue_days'],
        'payments_by_month': [{'month': m, 'amount': float(a)} for m, a in stats['payments_by_month']],
        'schedule': stats['schedule'],
        'timeline': stats['timeline'],
    })


@finance_access_required(api=True)
@require_GET
def consignment_reseller_get_api(request, reseller_id):
    """Дані магазину для заповнення форми редагування."""
    company = get_default_company()
    r = get_object_or_404(Reseller, id=reseller_id, company=company)
    return JsonResponse({
        'ok': True,
        'reseller': {
            'id': r.id, 'name': r.name,
            'counterparty_id': r.counterparty_id,
            'status': r.status, 'terms_kind': r.terms_kind,
            'terms': r.terms or {}, 'contacts': r.contacts or {},
            'notes': r.notes,
        },
    })


@finance_access_required(api=True)
@require_GET
def consignment_management_orders_api(request):
    """Список оптових замовлень менеджменту для вибору при поставці."""
    return JsonResponse({'ok': True, 'orders': svc.list_management_orders()})


@finance_access_required(api=True)
@require_GET
def consignment_management_tests_api(request):
    """Список тестових партій менеджменту."""
    return JsonResponse({'ok': True, 'batches': svc.list_management_test_batches()})


@finance_access_required(api=True)
@require_GET
def consignment_management_order_items_api(request, invoice_id):
    """Позиції конкретного оптового замовлення (для підстановки в поставку)."""
    return JsonResponse({'ok': True, 'items': svc.parse_management_order_items(invoice_id)})


@finance_access_required(api=True)
@require_GET
def consignment_management_test_items_api(request, shop_id):
    """Позиції тестової партії (для підстановки в поставку)."""
    return JsonResponse({'ok': True, 'items': svc.parse_management_test_batch_items(shop_id)})
