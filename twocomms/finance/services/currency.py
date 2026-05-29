"""Перерахунок валют у базову валюту компанії."""
from __future__ import annotations

from decimal import Decimal

from django.utils import timezone

from ..models import CurrencyRate


def get_rate(company, currency_from: str, currency_to: str, on_date=None) -> Decimal:
    """Останній відомий курс на дату (або раніше). 1.0, якщо валюти збігаються."""
    if currency_from == currency_to:
        return Decimal('1')
    if on_date is None:
        on_date = timezone.now().date()
    rate = (CurrencyRate.objects
            .filter(company=company, currency_from=currency_from,
                    currency_to=currency_to, date__lte=on_date)
            .order_by('-date').first())
    if rate:
        return rate.rate
    # Спробувати зворотний курс.
    inv = (CurrencyRate.objects
           .filter(company=company, currency_from=currency_to,
                   currency_to=currency_from, date__lte=on_date)
           .order_by('-date').first())
    if inv and inv.rate:
        return (Decimal('1') / inv.rate).quantize(Decimal('0.000001'))
    return Decimal('1')


def convert(company, amount: Decimal, currency_from: str, currency_to: str = None,
            on_date=None) -> Decimal:
    """Перерахунок суми у базову валюту (або задану currency_to)."""
    if amount is None:
        return Decimal('0')
    currency_to = currency_to or company.base_currency
    rate = get_rate(company, currency_from, currency_to, on_date)
    return (Decimal(amount) * rate).quantize(Decimal('0.01'))
