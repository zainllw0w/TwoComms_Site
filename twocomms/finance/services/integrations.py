"""Інтеграції банків/сервісів: каркас із QR-сценарієм (mock-статуси) та
прив'язкою рахунку. Реальні банківські API підключаються пізніше (ТЗ 05 §6-7)."""
from __future__ import annotations

from django.utils import timezone

from ..models import Account, IntegrationConnection, get_default_company
from . import audit as audit_service

# Каталог провайдерів для wizard (групи + країна для фільтра).
PROVIDER_CATALOG = [
    {'key': 'privatbank', 'name': 'PrivatBank Business', 'country': 'UA', 'group': 'bank'},
    {'key': 'monobank', 'name': 'monobank', 'country': 'UA', 'group': 'bank'},
    {'key': 'mono_business', 'name': 'ТОВ monobank', 'country': 'UA', 'group': 'bank'},
    {'key': 'novapay', 'name': 'NovaPay', 'country': 'UA', 'group': 'bank'},
    {'key': 'pumb', 'name': 'ПУМБ', 'country': 'UA', 'group': 'bank'},
    {'key': 'credit_dnipro', 'name': 'Credit Dnipro', 'country': 'UA', 'group': 'bank'},
    {'key': 'ukrgasbank', 'name': 'Укргазбанк', 'country': 'UA', 'group': 'bank'},
    {'key': 'payoneer', 'name': 'Payoneer', 'country': 'INT', 'group': 'bank'},
    {'key': 'wise', 'name': 'Wise', 'country': 'INT', 'group': 'bank'},
    {'key': 'crypto', 'name': 'Криптогаманець', 'country': 'INT', 'group': 'crypto'},
    {'key': 'tron', 'name': 'TRON', 'country': 'INT', 'group': 'crypto'},
    {'key': 'fondy', 'name': 'Fondy', 'country': 'UA', 'group': 'service'},
    {'key': 'western_bid', 'name': 'Western Bid', 'country': 'INT', 'group': 'service'},
    {'key': 'checkbox', 'name': 'Checkbox', 'country': 'UA', 'group': 'service'},
    {'key': 'poster', 'name': 'Poster', 'country': 'UA', 'group': 'service'},
    {'key': 'vchasno_kasa', 'name': 'Вчасно.Каса', 'country': 'UA', 'group': 'service'},
    {'key': 'hutko', 'name': 'Hutko', 'country': 'UA', 'group': 'service'},
]


def list_providers(country=None, search=None):
    items = PROVIDER_CATALOG
    if country and country != 'all':
        items = [p for p in items if p['country'] == country]
    if search:
        s = search.lower()
        items = [p for p in items if s in p['name'].lower()]
    return items


def start_connection(provider, *, user) -> IntegrationConnection:
    """Створює pending-підключення та переводить у waiting_for_scan (QR)."""
    company = get_default_company()
    conn = IntegrationConnection.objects.create(
        company=company, provider=provider, status='waiting_for_scan',
    )
    audit_service.log_action(user, 'create', 'integration', conn.id,
                             summary=f'Підключення {conn.get_provider_display()}', company=company)
    return conn


def poll_status(conn: IntegrationConnection, *, simulate_step=True) -> str:
    """Імітація переходу станів QR-сценарію: waiting → connecting → success.

    У реальній інтеграції тут була б перевірка статусу у провайдера.
    """
    if not simulate_step:
        return conn.status
    transitions = {
        'waiting_for_scan': 'connecting',
        'connecting': 'success',
    }
    new_status = transitions.get(conn.status)
    if new_status:
        conn.status = new_status
        if new_status == 'success':
            conn.last_sync_at = timezone.now()
        conn.save(update_fields=['status', 'last_sync_at'])
    return conn.status


def refresh_qr(conn: IntegrationConnection) -> IntegrationConnection:
    conn.status = 'waiting_for_scan'
    conn.error_message = ''
    conn.save(update_fields=['status', 'error_message'])
    return conn


def cancel_connection(conn: IntegrationConnection, *, user) -> None:
    conn.status = 'disconnected'
    conn.save(update_fields=['status'])
    audit_service.log_action(user, 'disconnect', 'integration', conn.id,
                             summary=conn.get_provider_display(), company=conn.company)


def link_account(conn: IntegrationConnection, *, user, account=None, new_account_name=None,
                 sync_from=None) -> Account:
    """Прив'язує існуючий рахунок або створює новий під інтеграцію."""
    from . import accounts as account_service
    company = conn.company
    if account is None and new_account_name:
        account = account_service.create_account(
            user=user, name=new_account_name,
            currency=company.base_currency, type='bank',
        )
    if account is not None:
        account.integration = conn
        account.save(update_fields=['integration'])
        conn.sync_from = sync_from
        conn.save(update_fields=['sync_from'])
    return account
