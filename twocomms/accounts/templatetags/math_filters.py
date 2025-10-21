from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


@register.filter
def multiply(value, arg):
    """Умножает value на arg"""
    try:
        return int(value) * int(arg)
    except (ValueError, TypeError):
        return 0


@register.filter(name="abs_value")
def abs_value(value):
    """
    Возвращает абсолютное значение для числовых аргументов.
    Сохраняет тип Decimal, если он был исходно.
    """
    if value is None:
        return 0

    try:
        return abs(value)
    except TypeError:
        try:
            decimal_value = Decimal(str(value))
        except (InvalidOperation, ValueError):
            return value
        return abs(decimal_value)
