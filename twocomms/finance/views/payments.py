"""Розділ «Платежі»: журнал операцій + JSON-API для модалок і таблиці."""
from __future__ import annotations

import json
from decimal import Decimal

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET, require_POST

from ..models import (
    Account, Category, Counterparty, Project, Tag, Transaction, get_default_company,
)
from ..permissions import finance_access_required
from ..services import filters as filter_service
from ..services import payloads as payload_service
from ..services import serializers as ser
from ..services import transactions as txn_service


def _body(request):
    """POST-дані з form-urlencoded або JSON."""
    if request.content_type and 'application/json' in request.content_type:
        try:
            return json.loads(request.body or '{}')
        except (ValueError, TypeError):
            return {}
    return request.POST


# ----------------------------- Журнал -----------------------------

@finance_access_required
def payments(request):
    company = get_default_company()
    qs = filter_service.filter_transactions(company, request.GET)
    actual_qs, planned_qs = filter_service.split_actual_planned(qs)

    actual_rows = [ser.serialize_transaction(t) for t in actual_qs[:500]]
    planned_rows = [ser.serialize_transaction(t) for t in planned_qs[:500]]

    context = {
        'active_tab': 'payments',
        'rows': actual_rows,
        'planned_rows': planned_rows,
        'planned_count': planned_qs.count(),
        'total_count': actual_qs.count(),
        'dropdowns': ser.serialize_dropdowns(company),
        'current_filters': {
            'period': request.GET.get('period', 'all'),
            'search': request.GET.get('search', ''),
            'amount_min': request.GET.get('amount_min', ''),
            'amount_max': request.GET.get('amount_max', ''),
        },
    }
    return render(request, 'finance/payments.html', context)


@finance_access_required(api=True)
@require_GET
def dropdowns_api(request):
    company = get_default_company()
    return JsonResponse({'ok': True, **ser.serialize_dropdowns(company)})


# ----------------------------- CRUD операцій -----------------------------

@finance_access_required(api=True)
@require_POST
def transaction_create_api(request):
    data = _body(request)
    txn_type = data.get('type')
    if txn_type not in (Transaction.TYPE_INCOME, Transaction.TYPE_EXPENSE, Transaction.TYPE_TRANSFER):
        return JsonResponse({'ok': False, 'error': 'Невірний тип операції'}, status=400)
    try:
        kwargs = payload_service.parse_transaction_payload(data, txn_type=txn_type)
    except payload_service.PayloadError as e:
        return JsonResponse({'ok': False, 'error': str(e), 'field': e.field}, status=400)

    txn = txn_service.create_transaction(user=request.user, **kwargs)
    return JsonResponse({'ok': True, 'transaction': ser.serialize_transaction(txn)})


@finance_access_required(api=True)
@require_GET
def transaction_detail_api(request, txn_id):
    company = get_default_company()
    txn = get_object_or_404(Transaction, id=txn_id, company=company)
    return JsonResponse({'ok': True, 'transaction': ser.serialize_transaction(txn)})


@finance_access_required(api=True)
@require_POST
def transaction_update_api(request, txn_id):
    company = get_default_company()
    txn = get_object_or_404(Transaction, id=txn_id, company=company)
    data = _body(request)
    txn_type = data.get('type', txn.type)
    try:
        kwargs = payload_service.parse_transaction_payload(data, txn_type=txn_type)
    except payload_service.PayloadError as e:
        return JsonResponse({'ok': False, 'error': str(e), 'field': e.field}, status=400)

    tags = kwargs.pop('tags', None)
    txn_service.update_transaction(txn, user=request.user, tags=tags, **kwargs)
    return JsonResponse({'ok': True, 'transaction': ser.serialize_transaction(txn)})


@finance_access_required(api=True)
@require_POST
def transaction_delete_api(request, txn_id):
    company = get_default_company()
    txn = get_object_or_404(Transaction, id=txn_id, company=company)
    txn_service.delete_transaction(txn, user=request.user)
    return JsonResponse({'ok': True})


@finance_access_required(api=True)
@require_POST
def transaction_duplicate_api(request, txn_id):
    company = get_default_company()
    txn = get_object_or_404(Transaction, id=txn_id, company=company)
    new = txn_service.duplicate_transaction(txn, user=request.user)
    return JsonResponse({'ok': True, 'transaction': ser.serialize_transaction(new)})


@finance_access_required(api=True)
@require_POST
def transaction_convert_transfer_api(request, txn_id):
    company = get_default_company()
    txn = get_object_or_404(Transaction, id=txn_id, company=company)
    data = _body(request)
    to_account = company.accounts.filter(id=data.get('to_account')).first()
    if not to_account:
        return JsonResponse({'ok': False, 'error': 'Оберіть рахунок отримувача'}, status=400)
    if to_account.id == txn.account_id:
        return JsonResponse({'ok': False, 'error': 'Рахунки мають відрізнятися'}, status=400)
    txn_service.convert_to_transfer(txn, user=request.user, to_account=to_account,
                                    to_amount=data.get('to_amount'))
    return JsonResponse({'ok': True, 'transaction': ser.serialize_transaction(txn)})


@finance_access_required(api=True)
@require_POST
def transaction_split_api(request, txn_id):
    company = get_default_company()
    txn = get_object_or_404(Transaction, id=txn_id, company=company)
    data = _body(request)
    raw_parts = data.get('parts') or []
    if isinstance(raw_parts, str):
        try:
            raw_parts = json.loads(raw_parts)
        except ValueError:
            raw_parts = []
    parts = []
    for p in raw_parts:
        parts.append({
            'amount': p.get('amount'),
            'category': company.categories.filter(id=p.get('category')).first() if p.get('category') else None,
            'project': company.projects.filter(id=p.get('project')).first() if p.get('project') else None,
            'comment': p.get('comment', ''),
        })
    try:
        children = txn_service.split_transaction(txn, user=request.user, parts=parts)
    except ValueError as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)
    return JsonResponse({'ok': True, 'children': [ser.serialize_transaction(c) for c in children]})


@finance_access_required(api=True)
@require_POST
def transaction_mark_actual_api(request, txn_id):
    company = get_default_company()
    txn = get_object_or_404(Transaction, id=txn_id, company=company)
    txn_service.mark_planned_actual(txn, user=request.user)
    return JsonResponse({'ok': True, 'transaction': ser.serialize_transaction(txn)})


# ----------------------------- Масові дії -----------------------------

@finance_access_required(api=True)
@require_POST
def transactions_bulk_api(request):
    company = get_default_company()
    data = _body(request)
    ids = data.get('ids') or []
    if isinstance(ids, str):
        ids = [i for i in ids.split(',') if i.strip().isdigit()]
    action = data.get('action')
    qs = Transaction.objects.filter(company=company, id__in=ids)
    if not qs.exists():
        return JsonResponse({'ok': False, 'error': 'Не обрано операцій'}, status=400)

    affected = 0
    if action == 'delete':
        for t in list(qs):
            txn_service.delete_transaction(t, user=request.user)
            affected += 1
    elif action == 'set_category':
        cat = company.categories.filter(id=data.get('value')).first()
        for t in qs:
            txn_service.update_transaction(t, user=request.user, category=cat)
            affected += 1
    elif action == 'set_project':
        proj = company.projects.filter(id=data.get('value')).first()
        for t in qs:
            txn_service.update_transaction(t, user=request.user, project=proj)
            affected += 1
    elif action == 'set_counterparty':
        cp = company.counterparties.filter(id=data.get('value')).first()
        for t in qs:
            txn_service.update_transaction(t, user=request.user, counterparty=cp)
            affected += 1
    elif action == 'add_tag':
        tag = company.tags.filter(id=data.get('value')).first()
        if tag:
            for t in qs:
                t.tags.add(tag)
                affected += 1
    elif action == 'mark_actual':
        for t in qs.filter(status=Transaction.STATUS_PLANNED):
            txn_service.mark_planned_actual(t, user=request.user)
            affected += 1
    else:
        return JsonResponse({'ok': False, 'error': 'Невідома дія'}, status=400)

    return JsonResponse({'ok': True, 'affected': affected})


# ----------------------------- Швидке створення сутностей -----------------------------

@finance_access_required(api=True)
@require_POST
def quick_create_entity_api(request):
    """Створення проєкту/контрагента/категорії/тегу з дропдауна (ТЗ 12 §11)."""
    company = get_default_company()
    data = _body(request)
    kind = data.get('kind')
    name = (data.get('name') or '').strip()
    if not name:
        return JsonResponse({'ok': False, 'error': 'Вкажіть назву'}, status=400)

    if kind == 'project':
        obj = Project.objects.create(company=company, name=name)
    elif kind == 'counterparty':
        obj = Counterparty.objects.create(company=company, name=name,
                                          type=data.get('type', 'client'))
    elif kind == 'category':
        ctype = data.get('type', 'expense')
        obj = Category.objects.create(company=company, name=name, type=ctype)
    elif kind == 'tag':
        obj = Tag.objects.create(company=company, name=name)
    else:
        return JsonResponse({'ok': False, 'error': 'Невідомий тип'}, status=400)

    return JsonResponse({'ok': True, 'id': obj.id, 'name': obj.name})
