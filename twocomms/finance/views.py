"""Каркасні views фінансового кабінету.

На етапі Блоку 1 кожен розділ рендерить shell із заголовком та заглушкою
(empty/coming-soon стан). У наступних блоках в'юхи замінюються повноцінними
реалізаціями (журнал платежів, аналітика, календар тощо).
"""
from __future__ import annotations

from django.shortcuts import render

from .permissions import finance_access_required

# Метадані розділів для шапки/заглушок.
_SECTIONS = {
    'finance_home': {
        'tab': 'payments',
        'title': 'Платежі',
        'subtitle': 'Журнал доходів, витрат, переказів і планових платежів.',
    },
    'finance_analytics': {
        'tab': 'analytics',
        'title': 'Аналітика',
        'subtitle': 'Cash Flow, P&L, дебіторка, кредиторка, баланс, план/факт.',
    },
    'finance_ai': {
        'tab': 'ai',
        'title': 'AI радник',
        'subtitle': 'Фінансовий помічник: аналіз витрат, прогноз, перевірка платежів.',
    },
    'finance_calendar': {
        'tab': 'calendar',
        'title': 'Календар',
        'subtitle': 'Прогноз залишку коштів по днях.',
    },
    'finance_invoices': {
        'tab': 'invoices',
        'title': 'Рахунки-фактури',
        'subtitle': 'Виставлення рахунків клієнтам, ПДВ, контроль оплат.',
    },
    'finance_rules': {
        'tab': 'rules',
        'title': 'Автоправила',
        'subtitle': 'Автоматичне заповнення категорій, проектів і контрагентів.',
    },
    'finance_users': {
        'tab': 'users',
        'title': 'Користувачі',
        'subtitle': 'Доступи, ролі та ефективність використання.',
    },
    'finance_accounts': {
        'tab': 'payments',
        'title': 'Рахунки',
        'subtitle': 'Керування рахунками, стартові баланси та інтеграції.',
    },
}


def _render_shell(request, url_name):
    meta = _SECTIONS.get(url_name, {})
    return render(request, 'finance/coming_soon.html', {
        'section_title': meta.get('title', 'Розділ'),
        'section_subtitle': meta.get('subtitle', ''),
        'active_tab': meta.get('tab', ''),
    })


@finance_access_required
def payments(request):
    return _render_shell(request, 'finance_home')


@finance_access_required
def analytics(request):
    return _render_shell(request, 'finance_analytics')


@finance_access_required
def ai_advisor(request):
    return _render_shell(request, 'finance_ai')


@finance_access_required
def calendar(request):
    return _render_shell(request, 'finance_calendar')


@finance_access_required
def invoices(request):
    return _render_shell(request, 'finance_invoices')


@finance_access_required
def rules(request):
    return _render_shell(request, 'finance_rules')


@finance_access_required
def users(request):
    return _render_shell(request, 'finance_users')


@finance_access_required
def accounts(request):
    return _render_shell(request, 'finance_accounts')
