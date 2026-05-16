"""
Сигналы для синхронизации корзины при авторизации пользователя.

Когда пользователь логинится (login/register/social-login), Django отправляет
сигнал ``user_logged_in``. Здесь мы перехватываем его и мерджим анонимную
сессионную корзину с сохранённой в БД, чтобы у юзера не "терялись" товары,
добавленные из guest-сессии.
"""

from __future__ import annotations

import logging

from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from .cart_sync import merge_session_into_db

logger = logging.getLogger('storefront.cart.sync')


@receiver(user_logged_in)
def merge_anonymous_cart_on_login(sender, request, user, **kwargs):  # noqa: D401
    """Объединяет анонимную сессионную корзину с DB-корзиной залогиненного юзера."""

    if request is None or user is None:
        return
    try:
        merge_session_into_db(request, user)
    except Exception:  # pragma: no cover - safety net
        logger.warning('Failed to merge cart on login for user=%s', getattr(user, 'pk', None), exc_info=True)
