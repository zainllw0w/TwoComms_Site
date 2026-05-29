"""Розділ «Користувачі»: доступи + панель ефективності використання (ТЗ 11)."""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.shortcuts import render

from ..models import (
    AutomationRule, Invoice, Transaction, get_default_company,
)
from ..permissions import finance_access_required

User = get_user_model()


def _role_label(u):
    if u.is_superuser:
        return 'Власник / повний доступ'
    if u.is_staff:
        return 'Адміністратор'
    return 'Перегляд'


def effectiveness(company):
    """Чек-лист налаштування сервісу (кожен пункт = 1 бал)."""
    has_txns = Transaction.objects.filter(company=company).exists()
    has_rules = AutomationRule.objects.filter(company=company).exists()
    has_accounts = company.accounts.exists()
    has_invoices = Invoice.objects.filter(company=company).exists()
    has_projects = company.projects.exists()
    items = [
        {'key': 'accounts', 'label': 'Додати рахунки', 'done': has_accounts, 'url': '/accounts/', 'cta': 'Додати'},
        {'key': 'transactions', 'label': 'Дії з транзакціями', 'done': has_txns, 'url': '/', 'cta': 'Перейти'},
        {'key': 'rules', 'label': 'Автоправила', 'done': has_rules, 'url': '/rules/', 'cta': 'Додати'},
        {'key': 'invoices', 'label': 'Рахунки-фактури', 'done': has_invoices, 'url': '/invoices/', 'cta': 'Створити'},
        {'key': 'projects', 'label': 'Проекти', 'done': has_projects, 'url': '/', 'cta': 'Додати'},
    ]
    done = sum(1 for i in items if i['done'])
    return {'items': items, 'done': done, 'total': len(items),
            'percent': round(done / len(items) * 100)}


@finance_access_required
def users(request):
    company = get_default_company()
    qs = User.objects.filter(Q(is_superuser=True) | Q(is_staff=True)).order_by('-is_superuser', 'username')
    rows = []
    for u in qs:
        rows.append({
            'name': u.get_full_name() or u.get_username(),
            'email': u.email,
            'role': _role_label(u),
            'is_superuser': u.is_superuser,
            'last_login': u.last_login,
            'active': u.is_active,
        })
    return render(request, 'finance/users.html', {
        'active_tab': 'users',
        'users': rows,
        'effectiveness': effectiveness(company),
    })
