"""Демо-дані для фінансового кабінету (позначаються is_demo=True, видаляються)."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from ..models import (
    Account, Category, Counterparty, Project, Tag, Transaction, get_default_company,
)
from . import balances as balance_service


SYSTEM_INCOME_CATEGORIES = [
    'Продажі', 'Послуги', 'Повернення коштів', 'Інвестиції', 'Інші доходи',
]
SYSTEM_EXPENSE_CATEGORIES = [
    'Закупівля товару', 'Зарплати', 'Оренда', 'Реклама та маркетинг',
    'Логістика та доставка', 'Комісії та банк', 'Податки', 'Сервіси та підписки',
    'Виробництво', 'Інші витрати',
]


def ensure_system_categories(company) -> None:
    """Створює базові системні категорії, якщо їх ще немає."""
    order = 0
    for name in SYSTEM_INCOME_CATEGORIES:
        Category.objects.get_or_create(
            company=company, name=name, type=Category.TYPE_INCOME,
            defaults={'is_system': True, 'sort_order': order},
        )
        order += 1
    for name in SYSTEM_EXPENSE_CATEGORIES:
        Category.objects.get_or_create(
            company=company, name=name, type=Category.TYPE_EXPENSE,
            defaults={'is_system': True, 'sort_order': order},
        )
        order += 1


def clear_demo(company) -> dict:
    """Видаляє всі демо-дані компанії."""
    counts = {}
    counts['transactions'] = Transaction.objects.filter(company=company, is_demo=True).delete()[0]
    counts['accounts'] = Account.objects.filter(company=company, is_demo=True).delete()[0]
    counts['projects'] = Project.objects.filter(company=company, is_demo=True).delete()[0]
    counts['counterparties'] = Counterparty.objects.filter(company=company, is_demo=True).delete()[0]
    counts['tags'] = Tag.objects.filter(company=company, is_demo=True).delete()[0]
    counts['categories'] = Category.objects.filter(company=company, is_demo=True).delete()[0]
    return counts


def seed_demo_company() -> dict:
    """Створює демо-набір: рахунки, проєкти, контрагенти, теги, операції."""
    company = get_default_company()
    ensure_system_categories(company)

    # Рахунки.
    accounts_spec = [
        ('Готівка', 'cash', 'UAH', Decimal('15000')),
        ('ПриватБанк ФОП', 'bank', 'UAH', Decimal('142300')),
        ('monobank картка', 'card', 'UAH', Decimal('38750')),
        ('Wise USD', 'wallet', 'USD', Decimal('2100')),
    ]
    accounts = []
    for i, (name, atype, cur, init) in enumerate(accounts_spec):
        acc, _ = Account.objects.get_or_create(
            company=company, name=name, is_demo=True,
            defaults={'type': atype, 'currency': cur, 'initial_balance': init,
                      'current_balance': init, 'sort_order': i,
                      'initial_balance_date': timezone.now().date() - timedelta(days=90)},
        )
        accounts.append(acc)

    # Проєкти.
    projects = []
    for i, pname in enumerate(['Власний магазин', 'Rozetka', 'Instagram', 'PromUA']):
        p, _ = Project.objects.get_or_create(company=company, name=pname, is_demo=True,
                                             defaults={'sort_order': i})
        projects.append(p)

    # Контрагенти.
    counterparties = []
    for cname, ctype in [('Клієнт роздріб', 'client'), ('Тканини UA', 'supplier'),
                         ('Нова Пошта', 'supplier'), ('Facebook Ads', 'supplier')]:
        c, _ = Counterparty.objects.get_or_create(company=company, name=cname, is_demo=True,
                                                  defaults={'type': ctype})
        counterparties.append(c)

    # Теги.
    for tname in ['терміново', 'опт', 'роздріб', 'реклама']:
        Tag.objects.get_or_create(company=company, name=tname, is_demo=True)

    # Категорії-довідники.
    inc_sales = Category.objects.filter(company=company, name='Продажі').first()
    exp_goods = Category.objects.filter(company=company, name='Закупівля товару').first()
    exp_ads = Category.objects.filter(company=company, name='Реклама та маркетинг').first()
    exp_logistics = Category.objects.filter(company=company, name='Логістика та доставка').first()

    # Операції за останні ~60 днів.
    now = timezone.now()
    demo_txns = [
        (Transaction.TYPE_INCOME, Decimal('8500'), accounts[1], inc_sales, counterparties[0], projects[1], 5),
        (Transaction.TYPE_INCOME, Decimal('3200'), accounts[2], inc_sales, counterparties[0], projects[2], 8),
        (Transaction.TYPE_INCOME, Decimal('12750'), accounts[1], inc_sales, counterparties[0], projects[0], 12),
        (Transaction.TYPE_EXPENSE, Decimal('21000'), accounts[1], exp_goods, counterparties[1], projects[0], 15),
        (Transaction.TYPE_EXPENSE, Decimal('4500'), accounts[2], exp_ads, counterparties[3], projects[2], 7),
        (Transaction.TYPE_EXPENSE, Decimal('1850'), accounts[0], exp_logistics, counterparties[2], projects[1], 3),
        (Transaction.TYPE_INCOME, Decimal('6400'), accounts[2], inc_sales, counterparties[0], projects[3], 20),
        (Transaction.TYPE_EXPENSE, Decimal('9800'), accounts[1], exp_goods, counterparties[1], projects[0], 25),
    ]
    for ttype, amount, acc, cat, cp, proj, days_ago in demo_txns:
        Transaction.objects.create(
            company=company, type=ttype, status=Transaction.STATUS_ACTUAL,
            amount=amount, currency=acc.currency, amount_base=amount,
            account=acc, date_actual=now - timedelta(days=days_ago),
            date_agreement=now - timedelta(days=days_ago + 1),
            category=cat, counterparty=cp, project=proj,
            comment='Демо-операція', source='manual', is_demo=True,
        )

    # Планові операції (майбутнє).
    Transaction.objects.create(
        company=company, type=Transaction.TYPE_EXPENSE, status=Transaction.STATUS_PLANNED,
        amount=Decimal('18000'), currency='UAH', amount_base=Decimal('18000'),
        account=accounts[1], date_actual=now + timedelta(days=5),
        category=exp_goods, counterparty=counterparties[1], project=projects[0],
        comment='Планова закупівля', source='manual', is_demo=True,
    )
    Transaction.objects.create(
        company=company, type=Transaction.TYPE_INCOME, status=Transaction.STATUS_PLANNED,
        amount=Decimal('25000'), currency='UAH', amount_base=Decimal('25000'),
        account=accounts[1], date_actual=now + timedelta(days=10),
        category=inc_sales, counterparty=counterparties[0], project=projects[0],
        comment='Очікуване надходження', source='manual', is_demo=True,
    )

    # Переказ між рахунками.
    Transaction.objects.create(
        company=company, type=Transaction.TYPE_TRANSFER, status=Transaction.STATUS_ACTUAL,
        amount=Decimal('5000'), currency='UAH', amount_base=Decimal('5000'),
        account=accounts[1], to_account=accounts[0], to_amount=Decimal('5000'),
        date_actual=now - timedelta(days=10), comment='Зняття готівки', source='manual', is_demo=True,
    )

    balance_service.recalc_all_balances(company)
    return {
        'accounts': len(accounts),
        'projects': len(projects),
        'counterparties': len(counterparties),
        'transactions': Transaction.objects.filter(company=company, is_demo=True).count(),
    }
