"""AI радник (rule-based): відповіді будуються детерміновано з даних компанії.

На цьому етапі без LLM — інтент розпізнається за ключовими словами, відповідь
рахується зі звітів/транзакцій. Інтерфейс готовий до підключення OpenAI пізніше.
"""
from __future__ import annotations

import datetime as dt
from collections import Counter
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from ..models import Transaction
from . import balances as balance_service
from . import reports as rep
from . import reports_debt as repd
from . import serializers as ser


def _m(company, v, signed=False):
    return ser.money(v, company.base_currency, signed=signed)


QUICK_PROMPTS = [
    {'key': 'overview', 'title': 'Загальна картина місяця', 'icon': '📊'},
    {'key': 'expenses', 'title': 'Аналіз витрат', 'icon': '💸'},
    {'key': 'forecast', 'title': 'Що буде з залишком', 'icon': '🔮'},
    {'key': 'receivables', 'title': 'Хто винен грошей', 'icon': '🤝'},
]


def answer(company, question: str) -> dict:
    """Повертає {answer, data?} за текстовим запитом."""
    q = (question or '').lower()

    def has(*words):
        return any(w in q for w in words)

    if has('картин', 'місяц', 'загальн', 'overview', 'підсумок'):
        return _overview(company)
    if has('витрат', 'куди піш', 'куди пішл', 'expenses', 'spend', 'топ'):
        return _expenses(company)
    if has('прогноз', 'залиш', 'forecast', 'буде з'):
        return _forecast(company)
    if has('винен', 'дебітор', 'борг', 'receivab'):
        return _receivables(company)
    if has('кредитор', 'кому винн', 'payab'):
        return _payables(company)
    if has('без катег', 'не заповн', 'категорі'):
        return _uncategorized(company)
    if has('прибут', 'profit', 'маржа', 'p&l', 'пнл'):
        return _profit(company)
    return {'answer': (
        'Я можу розповісти про загальну картину місяця, проаналізувати витрати, '
        'показати прогноз залишку, дебіторку/кредиторку, операції без категорії та прибуток. '
        'Спитайте, наприклад: «куди пішли гроші цього місяця?»'
    )}


def _overview(company):
    data = rep.pnl(company, {'period': 'month'})
    cf = rep.cash_flow(company, {'period': 'month'})
    total = balance_service.total_actual_balance(company)
    txt = (f'За поточний місяць доходи склали {_m(company, data["income"])}, '
           f'витрати {_m(company, data["expenses"])}, прибуток {_m(company, data["profit"], signed=True)}. '
           f'Чистий грошовий потік {_m(company, cf["net"], signed=True)}. '
           f'Зараз на рахунках {_m(company, total)}.')
    return {'answer': txt}


def _expenses(company):
    data = rep.cash_flow(company, {'period': 'month'})
    cats = data['expense_by_category'][:5]
    if not cats:
        return {'answer': 'За поточний місяць витрат не зафіксовано.'}
    lines = [f'• {c["name"]}: {_m(company, Decimal(str(c["total"])))}' for c in cats]
    return {'answer': 'Топ витрат за місяць:\n' + '\n'.join(lines)}


def _forecast(company):
    today = timezone.localdate()
    month_start = today.replace(day=1)
    month_end = (month_start + dt.timedelta(days=32)).replace(day=1) - dt.timedelta(days=1)
    forecast = balance_service.forecast_balance(company, month_start, month_end)
    total = balance_service.total_actual_balance(company)
    return {'answer': (f'Поточний залишок: {_m(company, total)}. '
                       f'З урахуванням планових платежів до кінця місяця прогноз: {_m(company, forecast)}.')}


def _receivables(company):
    data = repd.receivables(company)
    if not data['rows']:
        return {'answer': 'Наразі немає очікуваних надходжень (дебіторки).'}
    top = data['rows'][:5]
    lines = [f'• {r["counterparty"]}: {_m(company, r["amount"])}{" (прострочено)" if r["overdue"] else ""}' for r in top]
    return {'answer': f'Загальна дебіторка: {_m(company, data["total"])}.\n' + '\n'.join(lines)}


def _payables(company):
    data = repd.payables(company)
    if not data['rows']:
        return {'answer': 'Наразі немає запланованих списань (кредиторки).'}
    return {'answer': f'Загальна кредиторка: {_m(company, data["total"])} ({len(data["rows"])} зобов\'язань).'}


def _uncategorized(company):
    qs = Transaction.objects.filter(company=company, status=Transaction.STATUS_ACTUAL,
                                    category__isnull=True).exclude(type=Transaction.TYPE_TRANSFER)
    count = qs.count()
    if not count:
        return {'answer': 'Усі фактичні операції мають категорію — чудово!'}
    return {'answer': f'Знайдено {count} операцій без категорії. Рекомендую заповнити їх або створити автоправило.'}


def _profit(company):
    data = rep.pnl(company, {'period': 'month'})
    return {'answer': (f'Прибуток за місяць: {_m(company, data["profit"], signed=True)} '
                       f'(дохід {_m(company, data["income"])} − витрати {_m(company, data["expenses"])}), '
                       f'маржа {round(data["margin"], 1)}%.')}


# ----------------------------- Інструменти перевірки -----------------------------

def check_payments(company):
    """Знаходить проблемні операції (ТЗ 09 §6)."""
    issues = []
    actual = Transaction.objects.filter(company=company, status=Transaction.STATUS_ACTUAL)

    no_cat = actual.exclude(type=Transaction.TYPE_TRANSFER).filter(category__isnull=True).count()
    if no_cat:
        issues.append({'level': 'warning', 'text': f'{no_cat} операцій без категорії'})

    no_cp = actual.exclude(type=Transaction.TYPE_TRANSFER).filter(counterparty__isnull=True).count()
    if no_cp:
        issues.append({'level': 'info', 'text': f'{no_cp} операцій без контрагента'})

    no_proj = actual.exclude(type=Transaction.TYPE_TRANSFER).filter(project__isnull=True).count()
    if no_proj:
        issues.append({'level': 'info', 'text': f'{no_proj} операцій без проекту'})

    # Потенційні дублі: однакові сума+дата+рахунок. Групуємо у Python за
    # локальною датою, щоб не залежати від tz-таблиць MySQL (CONVERT_TZ).
    seen = Counter()
    for acc_id, amt, da in actual.values_list('account', 'amount', 'date_actual'):
        if da is None:
            continue
        seen[(acc_id, amt, timezone.localtime(da).date())] += 1
    dups = sum(1 for cnt in seen.values() if cnt > 1)
    if dups:
        issues.append({'level': 'warning', 'text': f'{dups} груп потенційних дублів (однакові сума/дата/рахунок)'})

    # Від'ємні залишки.
    neg = company.accounts.filter(current_balance__lt=0, is_archived=False).count()
    if neg:
        issues.append({'level': 'danger', 'text': f'{neg} рахунків з від\'ємним залишком'})

    if not issues:
        issues.append({'level': 'ok', 'text': 'Проблем не знайдено — дані в порядку.'})
    return issues


def check_report(company):
    """Перевірка звіту: аномалії, баланс, розбіжності."""
    issues = []
    bs = repd.balance_sheet(company)
    if not bs['balanced']:
        issues.append({'level': 'warning', 'text': f'Баланс не сходиться, розбіжність {_m(company, bs["difference"], signed=True)}'})
    else:
        issues.append({'level': 'ok', 'text': 'Баланс сходиться (активи = пасиви).'})
    issues.extend(check_payments(company))
    return issues
