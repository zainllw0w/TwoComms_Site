from django import template

register = template.Library()

@register.filter
def multiply(value, arg):
    """Умножает value на arg"""
    try:
        return int(value) * int(arg)
    except (ValueError, TypeError):
        return 0
