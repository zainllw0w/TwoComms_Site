"""
Persistent (DB-backed) cart for authenticated users.

Корзина хранится в сессии (`request.session['cart']` и `request.session['custom_print_cart']`),
поэтому каждое устройство имеет свою сессию и свою корзину. Чтобы у одного пользователя
была единая корзина на всех устройствах (мобильный/десктоп), мы дублируем содержимое
сессии в БД для авторизованных пользователей и синхронизируем его в обе стороны:

* при логине/регистрации — мерджим анонимную сессионную корзину с сохранённой в БД (signal);
* при каждом запросе — middleware подтягивает данные из БД в сессию (если сессия пуста)
  и записывает обратно при изменении корзины в течение запроса.

Здесь хранится сырое содержимое сессии, чтобы:
* не дублировать бизнес-логику (нормализация цен, опции posadki, кастомные принты);
* поддержать как стандартные товары, так и `custom_print_cart` без отдельной модели;
* минимизировать инвазивность (cart views остаются session-based).
"""

from __future__ import annotations

from django.conf import settings
from django.db import models


class UserCart(models.Model):
    """
    Постоянная корзина авторизованного пользователя.

    Хранит сырое содержимое сессии корзины (`cart` + `custom_print_cart` + промокод),
    чтобы все устройства одного аккаунта видели один и тот же набор товаров.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='persistent_cart',
        verbose_name='Користувач',
    )
    cart_data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Кошик (звичайні товари)',
        help_text='Snapshot of request.session["cart"]',
    )
    custom_cart_data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Кастомний кошик',
        help_text='Snapshot of request.session["custom_print_cart"]',
    )
    promo_code_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='Активний промокод',
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Оновлено')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Створено')

    class Meta:
        verbose_name = 'Постійний кошик'
        verbose_name_plural = 'Постійні кошики'

    def __str__(self) -> str:
        items = len(self.cart_data or {})
        custom = len(self.custom_cart_data or {})
        return f'UserCart<{self.user_id}> items={items} custom={custom}'

    @property
    def is_empty(self) -> bool:
        return not (self.cart_data or self.custom_cart_data)
