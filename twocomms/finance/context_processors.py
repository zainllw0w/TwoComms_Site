"""Контекст-процесор фінансового кабінету.

Додає у шаблони дані лівої фінансової панелі. Працює лише на піддомені fin.*
і лише для авторизованих фінансових адмінів — на решті сайту нічого не додає.
"""
from __future__ import annotations

import datetime as dt

from django.core.exceptions import DisallowedHost
from django.utils import timezone

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

    # Імпорти всередині, щоб уникнути навантаження на не-fin запити.
    try:
        from .models import get_default_company
        from .services import balances as balance_service
        from .services import serializers as ser
        from .services import warehouse_link
    except Exception:
        return {}

    try:
        company = get_default_company()
        today = timezone.localdate()
        month_start = today.replace(day=1)
        month_end = (month_start + dt.timedelta(days=32)).replace(day=1) - dt.timedelta(days=1)

        total = balance_service.total_actual_balance(company)
        planned = balance_service.planned_totals(company, month_start, month_end)
        forecast = (total + planned['income'] + planned['expense'])
        accounts = balance_service.account_sidebar_data(company)
        frozen = warehouse_link.frozen_in_warehouse()

        return {
            'fin_company_name': company.name,
            'fin_base_currency': ser.currency_symbol(company.base_currency),
            'fin_total_balance': ser.money(total, company.base_currency),
            'fin_accounts': accounts,
            'fin_frozen_warehouse': ser.money(frozen, company.base_currency),
            'fin_frozen_raw': frozen,
            'fin_planned_income': ser.money(planned['income'], company.base_currency, signed=True),
            'fin_planned_expense': ser.money(planned['expense'], company.base_currency, signed=True),
            'fin_forecast_balance': ser.money(forecast, company.base_currency),
            'fin_planned_period_label': '1 міс',
        }
    except Exception:
        # На випадок незастосованих міграцій тощо — не ламаємо сторінку.
        return {
            'fin_company_name': 'TwoComms',
            'fin_base_currency': '₴',
        }
