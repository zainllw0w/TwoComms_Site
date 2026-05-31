"""Розділ «Рахунки»: керування рахунками, інтеграції (wizard+QR), імпорт виписки."""
from __future__ import annotations

import json

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET, require_POST

from ..models import Account, IntegrationConnection, get_default_company
from ..permissions import finance_access_required
from ..services import accounts as account_service
from ..services import imports as import_service
from ..services import integrations as integ_service


def _body(request):
    if request.content_type and 'application/json' in request.content_type:
        try:
            return json.loads(request.body or '{}')
        except (ValueError, TypeError):
            return {}
    return request.POST


@finance_access_required
def accounts(request):
    company = get_default_company()
    context = {
        'active_tab': 'payments',
        'accounts': account_service.accounts_overview(company),
        'providers': integ_service.PROVIDER_CATALOG,
        'currencies': ['UAH', 'USD', 'EUR', 'PLN', 'GBP'],
        'account_types': Account.TYPE_CHOICES,
    }
    return render(request, 'finance/accounts.html', context)


# ----------------------------- Рахунки CRUD -----------------------------

@finance_access_required(api=True)
@require_POST
def account_create_api(request):
    data = _body(request)
    name = (data.get('name') or '').strip()
    if not name:
        return JsonResponse({'ok': False, 'error': 'Вкажіть назву рахунку'}, status=400)
    acc = account_service.create_account(
        user=request.user, name=name, currency=data.get('currency', 'UAH'),
        type=data.get('type', 'bank'), initial_balance=data.get('initial_balance', 0),
    )
    return JsonResponse({'ok': True, 'id': acc.id})


@finance_access_required(api=True)
@require_POST
def account_update_api(request, account_id):
    company = get_default_company()
    acc = get_object_or_404(Account, id=account_id, company=company)
    data = _body(request)
    fields = {}
    for key in ('name', 'currency', 'type', 'initial_balance', 'color', 'is_business'):
        if key in data:
            fields[key] = data[key]
    account_service.update_account(acc, user=request.user, **fields)
    return JsonResponse({'ok': True})


@finance_access_required(api=True)
@require_POST
def account_archive_api(request, account_id):
    company = get_default_company()
    acc = get_object_or_404(Account, id=account_id, company=company)
    data = _body(request)
    account_service.archive_account(acc, user=request.user,
                                    archived=bool(data.get('archived', True)))
    return JsonResponse({'ok': True})


@finance_access_required(api=True)
@require_POST
def account_delete_api(request, account_id):
    company = get_default_company()
    acc = get_object_or_404(Account, id=account_id, company=company)
    if account_service.delete_account(acc, user=request.user):
        return JsonResponse({'ok': True})
    return JsonResponse({'ok': False, 'error': 'Неможливо видалити: за рахунком є операції'}, status=400)


@finance_access_required(api=True)
@require_POST
def accounts_reorder_api(request):
    data = _body(request)
    ids = data.get('order') or []
    account_service.reorder_accounts(ids, user=request.user)
    return JsonResponse({'ok': True})


@finance_access_required(api=True)
@require_POST
def account_correct_balance_api(request, account_id):
    company = get_default_company()
    acc = get_object_or_404(Account, id=account_id, company=company)
    data = _body(request)
    account_service.correct_balance(acc, user=request.user, target_balance=data.get('target', 0))
    acc.refresh_from_db()
    return JsonResponse({'ok': True, 'current_balance': str(acc.current_balance)})


# ----------------------------- Інтеграції (wizard + QR) -----------------------------

@finance_access_required(api=True)
@require_GET
def integration_providers_api(request):
    providers = integ_service.list_providers(
        country=request.GET.get('country'), search=request.GET.get('search'))
    return JsonResponse({'ok': True, 'providers': providers})


@finance_access_required(api=True)
@require_POST
def integration_start_api(request):
    data = _body(request)
    provider = data.get('provider')
    if provider not in dict(IntegrationConnection.PROVIDER_CHOICES):
        return JsonResponse({'ok': False, 'error': 'Невідомий провайдер'}, status=400)
    conn = integ_service.start_connection(provider, user=request.user)
    return JsonResponse({'ok': True, 'connection_id': conn.id, 'status': conn.status,
                         'qr_payload': f'twocomms-fin:{conn.id}:{provider}'})


@finance_access_required(api=True)
@require_GET
def integration_status_api(request, conn_id):
    company = get_default_company()
    conn = get_object_or_404(IntegrationConnection, id=conn_id, company=company)
    status = integ_service.poll_status(conn)
    return JsonResponse({'ok': True, 'status': status,
                         'status_display': conn.get_status_display()})


@finance_access_required(api=True)
@require_POST
def integration_refresh_qr_api(request, conn_id):
    company = get_default_company()
    conn = get_object_or_404(IntegrationConnection, id=conn_id, company=company)
    integ_service.refresh_qr(conn)
    return JsonResponse({'ok': True, 'qr_payload': f'twocomms-fin:{conn.id}:{conn.provider}'})


@finance_access_required(api=True)
@require_POST
def integration_link_api(request, conn_id):
    company = get_default_company()
    conn = get_object_or_404(IntegrationConnection, id=conn_id, company=company)
    data = _body(request)
    account = None
    if data.get('account'):
        account = company.accounts.filter(id=data.get('account')).first()
    acc = integ_service.link_account(
        conn, user=request.user, account=account,
        new_account_name=(data.get('new_account_name') or '').strip() or None,
        sync_from=data.get('sync_from') or None,
    )
    return JsonResponse({'ok': True, 'account_id': acc.id if acc else None})


@finance_access_required(api=True)
@require_POST
def integration_cancel_api(request, conn_id):
    company = get_default_company()
    conn = get_object_or_404(IntegrationConnection, id=conn_id, company=company)
    integ_service.cancel_connection(conn, user=request.user)
    return JsonResponse({'ok': True})


# ----------------------------- Імпорт виписки -----------------------------

@finance_access_required(api=True)
@require_POST
def import_preview_api(request):
    f = request.FILES.get('file')
    if not f:
        return JsonResponse({'ok': False, 'error': 'Файл не надано'}, status=400)
    rows = import_service.parse_file(f, filename=f.name)
    # Зберігаємо розпарсене у сесії для подальшого підтвердження.
    request.session['fin_import_rows'] = rows[:2000]
    return JsonResponse({'ok': True, 'count': len(rows),
                         'preview': import_service.preview_rows(rows)})


@finance_access_required(api=True)
@require_POST
def import_confirm_api(request):
    company = get_default_company()
    data = _body(request)
    account = company.accounts.filter(id=data.get('account')).first()
    if not account:
        return JsonResponse({'ok': False, 'error': 'Оберіть рахунок для імпорту'}, status=400)
    rows = request.session.get('fin_import_rows') or []
    if not rows:
        return JsonResponse({'ok': False, 'error': 'Немає даних для імпорту. Завантажте файл знову.'}, status=400)
    result = import_service.import_rows(rows, user=request.user, account=account,
                                        apply_rules=bool(data.get('apply_rules', True)))
    request.session.pop('fin_import_rows', None)
    return JsonResponse({'ok': True, **result})
