"""Шаблонні теги для рендеру іконок-«карток» рахунків."""
from __future__ import annotations

from django import template

from ..account_icons import icon_html as _icon_html

register = template.Library()


@register.simple_tag
def fin_account_icon(account, extra_class=''):
    """Рендерить прямокутну картку-іконку рахунку.

    ``account`` — dict (серіалізований рахунок) із ключами icon_type/
    icon_value/icon_data. Якщо іконки немає — повертає порожній рядок.
    """
    if not account:
        return ''
    get = account.get if isinstance(account, dict) else lambda k, d='': getattr(account, k, d)
    return _icon_html(
        get('icon_type', ''), get('icon_value', ''),
        get('icon_data', '') or get('icon_image', ''), extra_class)
