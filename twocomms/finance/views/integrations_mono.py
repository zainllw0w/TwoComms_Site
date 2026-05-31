"""API-в'юхи інтеграції Monobank: підключення за токеном, вибір рахунків,
синхронізація, налаштування, відключення та вебхук.

Безпека:
- усі ендпоінти (окрім вебхука) — лише для фінанс-адмінів (decorator);
- токен приймається тільки POST/JSON, ніколи не логується й не повертається;
- вебхук публічний, але автентифікується секретом у шляху URL (constant-time
  порівняння) + перевіркою, що conn активне.
"""
from __future__ import annotations

import datetime as dt
import json

from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from ..models import Account, IntegrationConnection, get_default_company
from ..permissions import finance_access_required
from ..services import mono as mono_service
from ..services import mono_api


def _body(request):
    if request.content_type and 'application/json' in request.content_type:
        try:
            return json.loads(request.body or '{}')
        except (ValueError, TypeError):
            return {}
    return request.POST


def _conn_public(conn: IntegrationConnection) -> dict:
    """Безпечне представлення підключення для UI (без токена)."""
    return {
        'id': conn.id,
        'provider': conn.provider,
        'provider_display': conn.get_provider_display(),
        'status': conn.status,
        'method': conn.connection_method,
        'client_name': conn.client_name,
        'token_mask': conn.token_mask,
        'has_token': conn.has_token,
        'auto_sync': conn.auto_sync,
        'webhook_url': conn.webhook_url,
        'last_sync_at': timezone.localtime(conn.last_sync_at).strftime('%Y-%m-%d %H:%M')
        if conn.last_sync_at else '',
        'error': conn.error_message,
        'accounts': [
            {'id': a.id, 'name': a.name, 'is_business': a.is_business,
             'auto_sync': a.auto_sync, 'currency': a.currency,
             'balance': str(a.current_balance), 'masked_pan': a.masked_pan,
             'external_kind': a.external_kind}
            for a in conn.accounts.all()
        ],
    }


# ----------------------------- Підключення за токеном -----------------------------

@finance_access_required(api=True)
@require_POST
def mono_connect_api(request):
    """Приймає API-токен Monobank, валідує, шифрує і зберігає підключення."""
    data = _body(request)
    token = (data.get('token') or '').strip()
    if not token:
        return JsonResponse({'ok': False, 'error': 'Введіть API-токен'}, status=400)
    try:
        conn = mono_service.connect_with_token(token, user=request.user)
    except mono_api.MonoAuthError:
        return JsonResponse({'ok': False, 'error': 'Невалідний токен. Перевірте ключ у застосунку monobank.'}, status=400)
    except mono_api.MonoRateLimitError:
        return JsonResponse({'ok': False, 'error': 'Забагато запитів до Monobank. Спробуйте за хвилину.'}, status=429)
    except mono_api.MonoApiError as exc:
        return JsonResponse({'ok': False, 'error': str(exc)}, status=502)
    return JsonResponse({'ok': True, 'connection': _conn_public(conn)})


@finance_access_required(api=True)
@require_GET
def mono_accounts_api(request, conn_id):
    """Повертає рахунки клієнта Monobank для вибору (без створення)."""
    company = get_default_company()
    conn = get_object_or_404(IntegrationConnection, id=conn_id, company=company)
    try:
        accounts = mono_service.discover_accounts(conn)
    except mono_api.MonoRateLimitError:
        return JsonResponse({'ok': False, 'error': 'Ліміт Monobank (1 запит/хв). Зачекайте.'}, status=429)
    except mono_api.MonoApiError as exc:
        return JsonResponse({'ok': False, 'error': str(exc)}, status=502)
    return JsonResponse({'ok': True, 'accounts': accounts})


@finance_access_required(api=True)
@require_POST
def mono_link_api(request, conn_id):
    """Прив'язує обрані рахунки Monobank і одразу робить backfill історії."""
    company = get_default_company()
    conn = get_object_or_404(IntegrationConnection, id=conn_id, company=company)
    data = _body(request)
    ext_ids = data.get('external_ids') or []
    if isinstance(ext_ids, str):
        ext_ids = [x for x in ext_ids.split(',') if x.strip()]
    sync_from = None
    if data.get('sync_from'):
        try:
            sync_from = dt.date.fromisoformat(data['sync_from'])
        except (ValueError, TypeError):
            sync_from = None

    # Рахунки беремо з кешованого client-info (без зайвого запиту до ліміту).
    client = mono_service._client_for(conn)
    try:
        mono_accounts = {a.id: a for a in client.accounts()}
    except mono_api.MonoApiError as exc:
        return JsonResponse({'ok': False, 'error': str(exc)}, status=502)

    linked = []
    for ext in ext_ids:
        ma = mono_accounts.get(ext)
        if ma is None:
            continue
        # Баланс виставляється миттєво всередині link_mono_account.
        acc = mono_service.link_mono_account(conn, ma, user=request.user, sync_from=sync_from)
        linked.append(acc)

    # Початкове підтягування історії: лише одне вікно (≤30 діб) на рахунок, щоб
    # не впертись у ліміт 1 запит/60с. Решту історії добере крон поступово.
    totals = {'created': 0, 'skipped': 0, 'errors': [], 'rate_limited': False}
    for acc in linked:
        try:
            res = mono_service.sync_account(acc, user=request.user, full=True,
                                            client=client, max_windows=1)
            totals['created'] += res.get('created', 0)
            totals['skipped'] += res.get('skipped', 0)
            totals['rate_limited'] = totals['rate_limited'] or res.get('rate_limited', False)
        except mono_api.MonoApiError as exc:
            totals['errors'].append(str(exc))
    if linked:
        mono_service.reconcile_internal_transfers(company, user=request.user)
        # Best-effort: підписуємось на push нових транзакцій (тільки в проді).
        try:
            mono_service.register_webhook(conn)
        except Exception:  # noqa: BLE001
            pass

    return JsonResponse({'ok': True, 'linked': len(linked), **totals,
                         'connection': _conn_public(conn)})


# ----------------------------- Синхронізація / налаштування -----------------------------

@finance_access_required(api=True)
@require_POST
def mono_sync_api(request, conn_id):
    """Ручна синхронізація всіх авто-рахунків підключення."""
    company = get_default_company()
    conn = get_object_or_404(IntegrationConnection, id=conn_id, company=company)
    data = _body(request)
    # Обмежуємо к-сть statement-вікон за один клік (ліміт Monobank 1/60с):
    # повний backfill добере крон. full=True розширює добір до 3 вікон.
    max_windows = 3 if data.get('full') else 2
    try:
        summary = mono_service.sync_connection(conn, user=request.user,
                                               full=bool(data.get('full')),
                                               max_windows_per_account=max_windows)
    except mono_api.MonoApiError as exc:
        return JsonResponse({'ok': False, 'error': str(exc)}, status=502)
    return JsonResponse({'ok': True, **summary, 'connection': _conn_public(conn)})


@finance_access_required(api=True)
@require_POST
def mono_account_settings_api(request, account_id):
    """Налаштування прив'язаного рахунку: is_business, auto_sync, назва."""
    company = get_default_company()
    acc = get_object_or_404(Account, id=account_id, company=company)
    data = _body(request)
    fields = []
    if 'is_business' in data:
        acc.is_business = bool(data['is_business'])
        fields.append('is_business')
    if 'auto_sync' in data:
        acc.auto_sync = bool(data['auto_sync'])
        fields.append('auto_sync')
    if data.get('name'):
        acc.name = str(data['name']).strip()[:255]
        fields.append('name')
    if fields:
        acc.save(update_fields=fields)
    return JsonResponse({'ok': True})


@finance_access_required(api=True)
@require_POST
def mono_disconnect_api(request, conn_id):
    company = get_default_company()
    conn = get_object_or_404(IntegrationConnection, id=conn_id, company=company)
    mono_service.disconnect(conn, user=request.user)
    return JsonResponse({'ok': True})


@finance_access_required(api=True)
@require_GET
def mono_connections_api(request):
    """Перелік активних monobank-підключень (для модалки налаштувань)."""
    company = get_default_company()
    conns = company.integrations.filter(provider='monobank').exclude(status='disconnected')
    return JsonResponse({'ok': True, 'connections': [_conn_public(c) for c in conns]})


# ----------------------------- Вебхук (публічний, секрет у шляху) -----------------------------

@csrf_exempt
@require_http_methods(["GET", "POST"])
def mono_webhook(request, conn_id, secret):
    """Push нової транзакції від Monobank. Автентифікація — секрет у шляху URL."""
    import hmac
    conn = IntegrationConnection.objects.filter(
        id=conn_id, provider='monobank').exclude(status='disconnected').first()
    if conn is None or not conn.webhook_secret:
        return JsonResponse({'ok': False}, status=404)
    if not hmac.compare_digest(secret, conn.webhook_secret):
        return JsonResponse({'ok': False}, status=403)
    if request.method == 'GET':
        return HttpResponse(status=200)
    try:
        payload = json.loads(request.body or '{}')
    except (ValueError, TypeError):
        return JsonResponse({'ok': False}, status=400)
    try:
        mono_service.process_webhook(conn, payload, user=None)
    except Exception:  # noqa: BLE001 — завжди 200, щоб Monobank не ретраїв вічно
        return JsonResponse({'ok': True})
    return JsonResponse({'ok': True})
