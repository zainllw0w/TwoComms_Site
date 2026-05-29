"""Розділ «Платежі»: журнал операцій + JSON-API для модалок і таблиці."""
from __future__ import annotations

import json
from decimal import Decimal

from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
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


_MAX_ATTACHMENT = 10 * 1024 * 1024  # 10 МБ


def _attach_files(request, txn):
    """Створює Attachment з request.FILES і прив'язує до операції (макс. 10 МБ)."""
    from ..models import Attachment
    files = request.FILES.getlist('attachments') or request.FILES.getlist('file')
    company = get_default_company()
    for f in files:
        if f.size > _MAX_ATTACHMENT:
            continue
        att = Attachment.objects.create(
            company=company, file=f, original_name=f.name[:255],
            content_type=getattr(f, 'content_type', '') or '', size=f.size,
            uploaded_by=request.user if request.user.is_authenticated else None,
        )
        txn.attachments.add(att)


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


# ----------------------------- Експорт відфільтрованих платежів -----------------------------

def _export_rows(company, params):
    """Список рядків (dict) поточної відфільтрованої вибірки журналу."""
    qs = filter_service.filter_transactions(company, params)
    rows = []
    for t in qs.select_related('account', 'to_account', 'category', 'counterparty', 'project')[:10000]:
        rows.append({
            'date': timezone.localtime(t.date_actual).strftime('%Y-%m-%d %H:%M') if t.date_actual else '',
            'type': t.get_type_display(),
            'status': t.get_status_display(),
            'amount': str(t.amount),
            'currency': t.currency,
            'account': t.account.name if t.account else '',
            'to_account': t.to_account.name if t.to_account else '',
            'category': t.category.name if t.category else '',
            'counterparty': t.counterparty.name if t.counterparty else '',
            'project': t.project.name if t.project else '',
            'comment': t.comment or '',
        })
    return rows


_EXPORT_COLS = [
    ('date', 'Дата'), ('type', 'Тип'), ('status', 'Статус'), ('amount', 'Сума'),
    ('currency', 'Валюта'), ('account', 'Рахунок'), ('to_account', 'На рахунок'),
    ('category', 'Категорія'), ('counterparty', 'Контрагент'), ('project', 'Проект'),
    ('comment', 'Коментар'),
]


@finance_access_required
@require_GET
def payments_export(request):
    """Експорт поточного відфільтрованого журналу у XLSX або XML (?format=)."""
    company = get_default_company()
    fmt = (request.GET.get('format') or 'xlsx').lower()
    rows = _export_rows(company, request.GET)
    stamp = timezone.localtime(timezone.now()).strftime('%Y%m%d_%H%M')

    if fmt == 'xml':
        import xml.etree.ElementTree as ET
        from xml.dom import minidom
        root = ET.Element('payments', {'exported': stamp, 'count': str(len(rows))})
        for r in rows:
            el = ET.SubElement(root, 'payment')
            for key, _label in _EXPORT_COLS:
                child = ET.SubElement(el, key)
                child.text = str(r.get(key, ''))
        raw = ET.tostring(root, encoding='utf-8')
        pretty = minidom.parseString(raw).toprettyxml(indent='  ', encoding='utf-8')
        resp = HttpResponse(pretty, content_type='application/xml; charset=utf-8')
        resp['Content-Disposition'] = f'attachment; filename="payments_{stamp}.xml"'
        return resp

    # XLSX за замовчуванням.
    try:
        from openpyxl import Workbook
    except ImportError:
        return JsonResponse({'ok': False, 'error': 'openpyxl недоступний'}, status=500)
    wb = Workbook()
    ws = wb.active
    ws.title = 'Платежі'
    ws.append([label for _key, label in _EXPORT_COLS])
    for r in rows:
        ws.append([(float(r['amount']) if _key == 'amount' and r['amount'] else r.get(_key, ''))
                   for _key, _label in _EXPORT_COLS])
    resp = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    resp['Content-Disposition'] = f'attachment; filename="payments_{stamp}.xlsx"'
    wb.save(resp)
    return resp


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
    if request.FILES:
        _attach_files(request, txn)
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
    if request.FILES:
        _attach_files(request, txn)
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
