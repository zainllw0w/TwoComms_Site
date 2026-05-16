"""
Synchronization layer between session-based cart and the persistent ``UserCart``.

Алгоритм:

* ``hydrate_session_from_db`` — на входящем запросе берёт корзину пользователя из БД
  и подкачивает её в ``request.session``, если в сессии пусто, либо если в БД есть
  изменения с другого устройства.
* ``persist_session_to_db`` — на исходящем ответе сохраняет ``request.session['cart']``
  и ``request.session['custom_print_cart']`` обратно в БД.
* ``merge_session_into_db`` — вызывается из ``user_logged_in`` сигнала: переносит
  анонимную сессионную корзину в БД, объединяя с уже сохранённой (без потерь и
  дублирования количества).

Все операции защищены от исключений: ошибка синхронизации не должна ронять запрос.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

from django.contrib.auth import get_user_model
from django.db import transaction

from storefront.custom_print_config import SESSION_CUSTOM_CART_KEY

from .cart_models import UserCart

logger = logging.getLogger('storefront.cart.sync')

SESSION_CART_KEY = 'cart'
SESSION_PROMO_KEY = 'promo_code_id'
# Метка в сессии, чтобы понимать, читали ли мы уже DB-кошик в этом запросе.
SESSION_SYNCED_FLAG = '_cart_db_revision'

User = get_user_model()


def _ensure_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _normalize_qty(value: Any, default: int = 1) -> int:
    try:
        qty = int(value)
    except (TypeError, ValueError):
        return default
    return qty if qty > 0 else default


def _merge_standard_carts(primary: Dict[str, Any], secondary: Dict[str, Any]) -> Dict[str, Any]:
    """
    Объединяет два словаря обычной корзины. Если один и тот же ключ
    (product_id:size:color:fit) встречается в обоих, количества складываются.
    """

    merged: Dict[str, Any] = {}
    for source in (primary, secondary):
        if not isinstance(source, dict):
            continue
        for key, item in source.items():
            if not isinstance(item, dict):
                continue
            existing = merged.get(key)
            if existing is None:
                merged[key] = dict(item)
                merged[key]['qty'] = _normalize_qty(item.get('qty'))
                continue
            existing_qty = _normalize_qty(existing.get('qty'))
            incoming_qty = _normalize_qty(item.get('qty'))
            existing['qty'] = existing_qty + incoming_qty
            # Сохраняем актуальные метаданные (label/size/color), если их не было.
            for meta_key, meta_val in item.items():
                if meta_key == 'qty':
                    continue
                if meta_val and not existing.get(meta_key):
                    existing[meta_key] = meta_val
    return merged


def _merge_custom_carts(primary: Dict[str, Any], secondary: Dict[str, Any]) -> Dict[str, Any]:
    """
    Кастомные позиции уникальны по lead_id, поэтому достаточно union без удвоения.
    Если ключ уже есть, сохраняем версию с большим количеством (защита от рассинхрона).
    """

    merged: Dict[str, Any] = {}
    for source in (primary, secondary):
        if not isinstance(source, dict):
            continue
        for key, item in source.items():
            if not isinstance(item, dict):
                continue
            existing = merged.get(key)
            if existing is None:
                merged[key] = dict(item)
                continue
            try:
                if int(item.get('quantity') or 0) > int(existing.get('quantity') or 0):
                    merged[key] = dict(item)
            except (TypeError, ValueError):
                pass
    return merged


def _read_session_cart(session) -> Tuple[Dict[str, Any], Dict[str, Any], Optional[int]]:
    cart = _ensure_dict(session.get(SESSION_CART_KEY))
    custom_cart = _ensure_dict(session.get(SESSION_CUSTOM_CART_KEY))
    promo_raw = session.get(SESSION_PROMO_KEY)
    try:
        promo_id = int(promo_raw) if promo_raw is not None else None
    except (TypeError, ValueError):
        promo_id = None
    return cart, custom_cart, promo_id


def _write_session_cart(session, cart: Dict[str, Any], custom_cart: Dict[str, Any], promo_id: Optional[int]) -> None:
    session[SESSION_CART_KEY] = cart or {}
    if custom_cart:
        session[SESSION_CUSTOM_CART_KEY] = custom_cart
    else:
        session.pop(SESSION_CUSTOM_CART_KEY, None)
    if promo_id is not None:
        session[SESSION_PROMO_KEY] = promo_id
    else:
        session.pop(SESSION_PROMO_KEY, None)
    session.modified = True


def _resolve_promo(session_promo: Optional[int], db_promo: Optional[int]) -> Optional[int]:
    """
    Если у пользователя есть активный промокод в сессии — он приоритетнее
    (значит, юзер только что его применил). Иначе берём из БД.
    """

    if session_promo:
        return session_promo
    return db_promo


def _carts_equal(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    return (a or {}) == (b or {})


def get_user_cart(user) -> UserCart:
    """Возвращает (или создаёт) запись UserCart для пользователя."""

    cart, _ = UserCart.objects.get_or_create(user=user)
    return cart


def hydrate_session_from_db(request) -> None:
    """
    Подтягивает корзину пользователя из БД в сессию.

    Вызывается на входе запроса. Если в сессии пусто, заполняем из БД.
    Если данные есть — мерджим, чтобы не потерять только что добавленный товар.
    """

    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return

    try:
        session = request.session
    except AttributeError:
        return

    if session.get(SESSION_SYNCED_FLAG):
        return

    try:
        db_cart = get_user_cart(user)
    except Exception:
        logger.warning('Failed to load UserCart for user=%s', getattr(user, 'pk', None), exc_info=True)
        return

    session_cart, session_custom_cart, session_promo = _read_session_cart(session)

    db_cart_data = _ensure_dict(db_cart.cart_data)
    db_custom_data = _ensure_dict(db_cart.custom_cart_data)
    db_promo = db_cart.promo_code_id

    if not session_cart and not session_custom_cart and not session_promo:
        # Сессия пуста — просто берём из БД.
        if db_cart_data or db_custom_data or db_promo:
            _write_session_cart(session, db_cart_data, db_custom_data, db_promo)
    else:
        merged_cart = _merge_standard_carts(session_cart, db_cart_data)
        merged_custom = _merge_custom_carts(session_custom_cart, db_custom_data)
        merged_promo = _resolve_promo(session_promo, db_promo)
        if (
            not _carts_equal(merged_cart, session_cart)
            or not _carts_equal(merged_custom, session_custom_cart)
            or merged_promo != session_promo
        ):
            _write_session_cart(session, merged_cart, merged_custom, merged_promo)

    session[SESSION_SYNCED_FLAG] = db_cart.pk
    session.modified = True


def persist_session_to_db(request) -> None:
    """
    Сохраняет содержимое сессии корзины в БД.

    Вызывается перед отправкой ответа. Если пользователь анонимный — ничего не делаем.
    """

    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return

    try:
        session = request.session
    except AttributeError:
        return

    session_cart, session_custom_cart, session_promo = _read_session_cart(session)

    try:
        with transaction.atomic():
            db_cart, _ = UserCart.objects.select_for_update().get_or_create(user=user)
            db_cart_data = _ensure_dict(db_cart.cart_data)
            db_custom_data = _ensure_dict(db_cart.custom_cart_data)
            db_promo = db_cart.promo_code_id

            if (
                _carts_equal(session_cart, db_cart_data)
                and _carts_equal(session_custom_cart, db_custom_data)
                and session_promo == db_promo
            ):
                return

            db_cart.cart_data = session_cart or {}
            db_cart.custom_cart_data = session_custom_cart or {}
            db_cart.promo_code_id = session_promo
            db_cart.save(update_fields=['cart_data', 'custom_cart_data', 'promo_code_id', 'updated_at'])
    except Exception:
        logger.warning('Failed to persist cart for user=%s', getattr(user, 'pk', None), exc_info=True)


def merge_session_into_db(request, user) -> None:
    """
    Сценарий логина/регистрации: пользователь зашёл, его анонимная сессионная корзина
    объединяется с уже сохранённой в БД и записывается обратно как в сессию, так и в БД.
    """

    if not user or not getattr(user, 'pk', None):
        return

    try:
        session = request.session
    except AttributeError:
        return

    session_cart, session_custom_cart, session_promo = _read_session_cart(session)

    try:
        with transaction.atomic():
            db_cart, _ = UserCart.objects.select_for_update().get_or_create(user=user)
            db_cart_data = _ensure_dict(db_cart.cart_data)
            db_custom_data = _ensure_dict(db_cart.custom_cart_data)
            db_promo = db_cart.promo_code_id

            merged_cart = _merge_standard_carts(session_cart, db_cart_data)
            merged_custom = _merge_custom_carts(session_custom_cart, db_custom_data)
            merged_promo = _resolve_promo(session_promo, db_promo)

            db_cart.cart_data = merged_cart or {}
            db_cart.custom_cart_data = merged_custom or {}
            db_cart.promo_code_id = merged_promo
            db_cart.save(update_fields=['cart_data', 'custom_cart_data', 'promo_code_id', 'updated_at'])
    except Exception:
        logger.warning('Failed to merge anonymous cart into DB for user=%s', getattr(user, 'pk', None), exc_info=True)
        return

    _write_session_cart(session, merged_cart, merged_custom, merged_promo)
    session[SESSION_SYNCED_FLAG] = db_cart.pk
    session.modified = True
