from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Получает элемент из словаря по ключу"""
    if isinstance(dictionary, dict):
        return dictionary.get(key)
    return None
