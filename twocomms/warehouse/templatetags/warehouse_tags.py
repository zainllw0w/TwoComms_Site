"""Custom template tags / filters for warehouse templates."""
from __future__ import annotations

from django import template

register = template.Library()


@register.filter(name="dictkey")
def dictkey(value, key):
    """Get value from dict by dynamic key.

    Usage in template: ``{{ mydict|dictkey:varname }}``
    """
    if value is None:
        return None
    try:
        return value.get(key)
    except AttributeError:
        try:
            return value[key]
        except (KeyError, TypeError, IndexError):
            return None


@register.filter(name="qty_class")
def qty_class(qty):
    """CSS class based on qty value."""
    try:
        n = int(qty)
    except (TypeError, ValueError):
        return "qty-zero"
    if n <= 0:
        return "qty-zero"
    if n < 3:
        return "qty-low"
    return "qty-positive"


@register.filter(name="ua_money")
def ua_money(value):
    """Format integer as 'X XXX ₴' with Ukrainian thin spaces."""
    try:
        n = int(round(float(value or 0)))
    except (TypeError, ValueError):
        return "0 ₴"
    formatted = f"{n:,}".replace(",", "\u00a0")
    return f"{formatted}\u00a0₴"
