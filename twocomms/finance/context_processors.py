"""Контекст-процесор фінансового кабінету.

Додає у шаблони дані лівої фінансової панелі та шапки. Працює лише на
піддомені fin.* і лише для авторизованих фінансових адмінів — на решті
сайту нічого не додає (щоб не впливати на основний storefront/management).

На етапі Блоку 1 повертає базовий каркас (порожні суми). У Блоці 2+ сюди
підключаються реальні рахунки, баланси та планові платежі.
"""
from __future__ import annotations

from django.core.exceptions import DisallowedHost

from .permissions import user_is_finance_admin


def _is_finance_host(request) -> bool:
    try:
        host = request.get_host().split(':')[0].lower()
    except DisallowedHost:
        return False
    return host.startswith('fin.')


def finance_shell_context(request):
    if not _is_finance_host(request):
        return {}
    user = getattr(request, 'user', None)
    if user is None or not user_is_finance_admin(user):
        return {}

    # Базовий каркас лівої панелі. Реальні значення підставляються у Блоці 2,
    # коли з'являються моделі Account/Transaction.
    return {
        'fin_company_name': 'TwoComms',
        'fin_base_currency': '₴',
        'fin_total_balance': None,
        'fin_accounts': [],
        'fin_planned_income': None,
        'fin_planned_expense': None,
        'fin_forecast_balance': None,
        'fin_planned_period_label': '1 міс',
    }
