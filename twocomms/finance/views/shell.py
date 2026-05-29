"""Каркасні views для розділів, що наповнюються у наступних блоках."""
from __future__ import annotations

from django.shortcuts import render

from ..permissions import finance_access_required

_SECTIONS = {
    'finance_analytics': ('analytics', 'Аналітика',
                          'Cash Flow, P&L, дебіторка, кредиторка, баланс, план/факт.'),
    'finance_ai': ('ai', 'AI радник',
                   'Фінансовий помічник: аналіз витрат, прогноз, перевірка платежів.'),
    'finance_invoices': ('invoices', 'Рахунки-фактури',
                         'Виставлення рахунків клієнтам, ПДВ, контроль оплат.'),
    'finance_rules': ('rules', 'Автоправила',
                      'Автоматичне заповнення категорій, проектів і контрагентів.'),
    'finance_users': ('users', 'Користувачі', 'Доступи, ролі та ефективність використання.'),
}


def _shell(request, url_name):
    tab, title, subtitle = _SECTIONS[url_name]
    return render(request, 'finance/coming_soon.html', {
        'section_title': title, 'section_subtitle': subtitle, 'active_tab': tab,
    })


@finance_access_required
def analytics(request):
    return _shell(request, 'finance_analytics')


@finance_access_required
def ai_advisor(request):
    return _shell(request, 'finance_ai')


@finance_access_required
def invoices(request):
    return _shell(request, 'finance_invoices')


@finance_access_required
def rules(request):
    return _shell(request, 'finance_rules')


@finance_access_required
def users(request):
    return _shell(request, 'finance_users')
