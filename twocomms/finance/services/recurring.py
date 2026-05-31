"""Сервіс для генерації recurring транзакцій — БЛОК 3."""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

from django.db import transaction as db_transaction
from django.utils import timezone

from ..models import RecurrenceRule, Transaction, get_default_company
from . import transactions as txn_service


def calculate_next_occurrence(rule: RecurrenceRule, from_date: dt.date = None) -> dt.date | None:
    """Розраховує наступну дату спрацювання правила.

    Args:
        rule: Правило повторення
        from_date: Дата від якої рахувати (за замовчуванням сьогодні)

    Returns:
        Наступна дата спрацювання або None якщо правило завершене
    """
    if from_date is None:
        from_date = timezone.localdate()

    # Якщо правило має end_date і воно вже минуло
    if rule.end_date and from_date > rule.end_date:
        return None

    # Якщо правило має count і вже згенеровано достатньо
    if rule.count:
        generated_count = rule.transactions.filter(
            status=Transaction.STATUS_PLANNED
        ).count()
        if generated_count >= rule.count:
            return None

    # Розрахунок наступної дати залежно від frequency
    if rule.frequency == 'daily':
        next_date = from_date + dt.timedelta(days=rule.interval)
    elif rule.frequency == 'weekly':
        next_date = from_date + dt.timedelta(weeks=rule.interval)
    elif rule.frequency == 'monthly':
        # Додаємо місяці
        month = from_date.month + rule.interval
        year = from_date.year
        while month > 12:
            month -= 12
            year += 1

        # Якщо вказано конкретний день місяця
        if rule.by_month_day:
            day = min(rule.by_month_day, 28)  # Безпечний день
        else:
            day = from_date.day

        try:
            next_date = dt.date(year, month, day)
        except ValueError:
            # Якщо день не існує в місяці (напр. 31 лютого)
            import calendar
            last_day = calendar.monthrange(year, month)[1]
            next_date = dt.date(year, month, last_day)

    elif rule.frequency == 'yearly':
        next_date = dt.date(
            from_date.year + rule.interval,
            from_date.month,
            from_date.day
        )
    else:
        # custom або невідомий тип
        return None

    # Перевіряємо чи не виходить за end_date
    if rule.end_date and next_date > rule.end_date:
        return None

    return next_date


@db_transaction.atomic
def generate_planned_transaction(rule: RecurrenceRule, for_date: dt.date, *, user) -> Transaction | None:
    """Створює планову транзакцію на основі правила.

    Args:
        rule: Правило повторення
        for_date: Дата для якої створюємо транзакцію
        user: Користувач який ініціює створення

    Returns:
        Створена транзакція або None якщо не вдалось створити
    """
    if not rule.is_active:
        return None

    # Перевіряємо чи вже існує транзакція на цю дату
    existing = Transaction.objects.filter(
        company=rule.company,
        recurrence_rule=rule,
        date_actual__date=for_date,
        status=Transaction.STATUS_PLANNED,
    ).exists()

    if existing:
        return None

    # Створюємо планову транзакцію
    txn = txn_service.create_transaction(
        user=user,
        type=rule.template_type,
        amount=rule.template_amount or Decimal('0'),
        account=rule.template_account,
        currency=rule.template_account.currency if rule.template_account else 'UAH',
        category=rule.template_category,
        comment=rule.template_comment or f'Автоматично: {rule}',
        date_actual=timezone.make_aware(dt.datetime.combine(for_date, dt.time(12, 0))),
        status=Transaction.STATUS_PLANNED,
        recurrence_rule=rule,
        source='recurring',
    )

    # Оновлюємо last_generated_at
    rule.last_generated_at = timezone.now()
    rule.save(update_fields=['last_generated_at'])

    return txn


def generate_upcoming_transactions(rule: RecurrenceRule, *, user, days_ahead: int = 60) -> list[Transaction]:
    """Генерує планові транзакції на N днів вперед.

    Args:
        rule: Правило повторення
        user: Користувач
        days_ahead: На скільки днів вперед генерувати

    Returns:
        Список створених транзакцій
    """
    if not rule.is_active or not rule.auto_create:
        return []

    today = timezone.localdate()
    horizon = today + dt.timedelta(days=days_ahead)
    created = []

    # Починаємо з next_occurrence або start_date
    current_date = rule.next_occurrence or rule.start_date

    while current_date and current_date <= horizon:
        # Створюємо транзакцію
        txn = generate_planned_transaction(rule, current_date, user=user)
        if txn:
            created.append(txn)

        # Розраховуємо наступну дату
        current_date = calculate_next_occurrence(rule, current_date)

    # Оновлюємо next_occurrence
    if current_date:
        rule.next_occurrence = current_date
        rule.save(update_fields=['next_occurrence'])

    return created


def process_all_recurring_rules(*, user, days_ahead: int = 60) -> dict:
    """Обробляє всі активні recurring правила.

    Args:
        user: Користувач
        days_ahead: На скільки днів вперед генерувати

    Returns:
        Статистика: {'rules_processed': int, 'transactions_created': int}
    """
    company = get_default_company()
    rules = RecurrenceRule.objects.filter(
        company=company,
        is_active=True,
    )

    stats = {'rules_processed': 0, 'transactions_created': 0}

    for rule in rules:
        created = generate_upcoming_transactions(rule, user=user, days_ahead=days_ahead)
        stats['rules_processed'] += 1
        stats['transactions_created'] += len(created)

    return stats
