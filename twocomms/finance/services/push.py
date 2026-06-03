"""Відправка web-push повідомлень фінансового кабінету.

Переюзає VAPID-конфіг проєкту (WEB_PUSH_VAPID_*), що вже налаштований для
основного сайту. Підписки зберігаються у finance.PushSubscription, логи —
у finance.NotificationLog. Звіти будуються з рушія здоров'я та P&L.

Усе деградує безпечно: якщо pywebpush недоступний або VAPID не налаштований,
функції повертають структуру з помилкою, не валлячи виклик.
"""
from __future__ import annotations

import json
from importlib import import_module

from django.conf import settings
from django.utils import timezone

try:
    from pywebpush import WebPushException, webpush
except ModuleNotFoundError:
    WebPushException = RuntimeError
    webpush = None


def is_configured() -> bool:
    return bool(getattr(settings, 'WEB_PUSH_ENABLED', False) and webpush is not None)


def _resolve_private_key(private_key):
    """Підтримка як raw-ключа, так і PEM (як у storefront)."""
    normalized = (private_key or '').strip()
    if not normalized:
        return None
    if '-----BEGIN' not in normalized:
        return normalized
    try:
        vapid_module = import_module('py_vapid')
    except ModuleNotFoundError:
        return None
    vapid_class = getattr(vapid_module, 'Vapid01', None) or getattr(vapid_module, 'Vapid', None)
    if vapid_class is None:
        return None
    try:
        return vapid_class.from_pem(normalized.encode('utf-8'))
    except Exception:
        return None


def _vapid_claims():
    subject = (getattr(settings, 'WEB_PUSH_VAPID_SUBJECT', '') or '').strip()
    return {'sub': subject} if subject else {'sub': 'mailto:admin@twocomms.shop'}


def send_to_user(user, title: str, body: str, *, url: str = '/', tag: str = 'finance',
                 notification_type: str = 'custom', report_data=None) -> dict:
    """Надсилає push усім активним підпискам користувача. Повертає підсумок."""
    from ..models_settings import PushSubscription, NotificationLog

    if not is_configured():
        return {'ok': False, 'error': 'web_push_not_configured', 'sent': 0, 'failed': 0}

    private_key = _resolve_private_key(getattr(settings, 'WEB_PUSH_VAPID_PRIVATE_KEY', ''))
    if private_key is None:
        return {'ok': False, 'error': 'vapid_private_key_invalid', 'sent': 0, 'failed': 0}

    subscriptions = PushSubscription.objects.filter(user=user, is_active=True)
    icon = _abs(getattr(settings, 'WEB_PUSH_ICON_PATH', '/static/img/favicon-192x192.png'))
    payload = json.dumps({
        'title': title,
        'body': body,
        'icon': icon,
        'badge': icon,
        'url': url,
        'tag': tag,
        'timestamp': int(timezone.now().timestamp() * 1000),
    })

    sent = 0
    failed = 0
    last_error = ''
    for sub in subscriptions:
        try:
            webpush(
                subscription_info={
                    'endpoint': sub.endpoint,
                    'keys': {'p256dh': sub.p256dh, 'auth': sub.auth},
                },
                data=payload,
                vapid_private_key=private_key,
                vapid_claims=_vapid_claims(),
                ttl=86400,
                timeout=10,
            )
            sent += 1
            sub.last_used = timezone.now()
            sub.save(update_fields=['last_used'])
        except WebPushException as exc:
            failed += 1
            last_error = str(exc)[:255]
            status = getattr(getattr(exc, 'response', None), 'status_code', None)
            if status in (404, 410):
                sub.is_active = False
                sub.save(update_fields=['is_active'])
        except Exception as exc:
            failed += 1
            last_error = str(exc)[:255]

    # Лог.
    try:
        NotificationLog.objects.create(
            user=user, notification_type=notification_type,
            title=title, body=body, success=(failed == 0 and sent > 0),
            error_message=last_error, report_data=report_data,
        )
    except Exception:
        pass

    return {'ok': sent > 0, 'sent': sent, 'failed': failed,
            'error': last_error if failed else ''}


def _abs(path):
    base = (getattr(settings, 'SITE_BASE_URL', '') or '').rstrip('/')
    if not path:
        return base
    if path.startswith(('http://', 'https://')):
        return path
    return f'{base}/{path.lstrip("/")}'


# --------------------------------------------------------------------------
# Контент звітів
# --------------------------------------------------------------------------

def build_daily_report(company) -> dict:
    """Щоденний звіт: доходи/витрати за сьогодні + баланс."""
    from .. models import Transaction
    from . import balances as balance_service
    from . import serializers as ser
    from .timeutil import day_start, day_end

    today = timezone.localdate()
    qs = (Transaction.objects.filter(company=company, status=Transaction.STATUS_ACTUAL,
                                     date_actual__gte=day_start(today), date_actual__lte=day_end(today))
          .exclude(excluded_from_reports=True).exclude(type=Transaction.TYPE_TRANSFER))
    from django.db.models import Sum
    from decimal import Decimal
    inc = qs.filter(type=Transaction.TYPE_INCOME).aggregate(s=Sum('amount_base'))['s'] or Decimal('0')
    exp = qs.filter(type=Transaction.TYPE_EXPENSE).aggregate(s=Sum('amount_base'))['s'] or Decimal('0')
    balance = balance_service.total_actual_balance(company)
    cur = company.base_currency

    title = 'Фінанси за сьогодні'
    parts = []
    if inc:
        parts.append(f'дохід {ser.money(inc, cur)}')
    if exp:
        parts.append(f'витрати {ser.money(exp, cur)}')
    if not parts:
        parts.append('операцій не було')
    body = f'{", ".join(parts).capitalize()}. Баланс: {ser.money(balance, cur)}.'
    return {'title': title, 'body': body,
            'data': {'income': float(inc), 'expense': float(exp), 'balance': float(balance)}}


def build_weekly_report(company) -> dict:
    """Тижневий звіт: P&L за 7 днів + ключові ризики зі здоров'я."""
    import datetime as dt
    from django.db.models import Sum
    from decimal import Decimal
    from .. models import Transaction
    from . import serializers as ser
    from . import health as health_service
    from .timeutil import day_start, day_end

    today = timezone.localdate()
    start = today - dt.timedelta(days=7)
    qs = (Transaction.objects.filter(company=company, status=Transaction.STATUS_ACTUAL,
                                     is_business=True,
                                     date_actual__gte=day_start(start), date_actual__lte=day_end(today))
          .exclude(excluded_from_reports=True).exclude(type=Transaction.TYPE_TRANSFER))
    inc = qs.filter(type=Transaction.TYPE_INCOME).aggregate(s=Sum('amount_base'))['s'] or Decimal('0')
    exp = qs.filter(type=Transaction.TYPE_EXPENSE).aggregate(s=Sum('amount_base'))['s'] or Decimal('0')
    profit = inc - exp
    cur = company.base_currency

    health = health_service.calculate_health(company)
    score = health['scores']['portfolio_final']

    title = 'Підсумок тижня'
    body = (f'Дохід {ser.money(inc, cur)}, витрати {ser.money(exp, cur)}, '
            f'прибуток {ser.money(profit, cur, signed=True)}. '
            f'Фінансове здоров\'я: {score}/100.')
    return {'title': title, 'body': body,
            'data': {'income': float(inc), 'expense': float(exp),
                     'profit': float(profit), 'health_score': score}}


def build_health_alert_report(company) -> dict | None:
    """Звіт-сповіщення про критичні ризики (лише якщо є critical alerts)."""
    from . import health as health_service
    health = health_service.calculate_health(company)
    alerts = [a for a in health['critical_alerts'] if a['severity'] in ('critical', 'high')]
    if not alerts:
        return None
    top = alerts[0]
    extra = f' (+{len(alerts) - 1} ще)' if len(alerts) > 1 else ''
    return {'title': f'⚠️ {top["title"]}',
            'body': f'{top["message"]}{extra}',
            'data': {'alerts': len(alerts), 'score': health['scores']['portfolio_final']}}


def build_planned_reminder_report(company) -> dict | None:
    """Нагадування про планові платежі на завтра (та прострочені сьогодні)."""
    import datetime as dt
    from django.db.models import Sum
    from decimal import Decimal
    from ..models import Transaction
    from . import serializers as ser
    from .timeutil import day_start, day_end

    today = timezone.localdate()
    tomorrow = today + dt.timedelta(days=1)
    qs = (Transaction.objects.filter(
            company=company, status=Transaction.STATUS_PLANNED,
            date_actual__gte=day_start(today), date_actual__lte=day_end(tomorrow))
          .exclude(excluded_from_reports=True))
    if not qs.exists():
        return None
    cur = company.base_currency
    inc = qs.filter(type=Transaction.TYPE_INCOME).aggregate(s=Sum('amount_base'))['s'] or Decimal('0')
    exp = qs.filter(type=Transaction.TYPE_EXPENSE).aggregate(s=Sum('amount_base'))['s'] or Decimal('0')
    count = qs.count()
    parts = []
    if exp:
        parts.append(f'до сплати {ser.money(exp, cur)}')
    if inc:
        parts.append(f'надходжень {ser.money(inc, cur)}')
    body = f'{count} планов(их) платеж(ів) на найближчу добу: {", ".join(parts) or "перевірте календар"}.'
    return {'title': 'Нагадування про платежі', 'body': body,
            'data': {'count': count, 'income': float(inc), 'expense': float(exp)}}
