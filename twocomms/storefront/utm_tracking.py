"""
Функции для отслеживания действий пользователей в системе UTM-аналитики.

Используется для записи событий в воронке конверсий:
- Просмотры страниц и товаров
- Добавление/удаление товаров из корзины
- Начало оформления заказа
- Лиды (предоплата)
- Покупки (полная оплата)
"""

import logging
from typing import Optional
from .analytics_audience import build_audience_snapshot, merge_audience_metadata
from .models import UTMSession, SiteSession, UserAction
from .utm_utils import calculate_action_points

logger = logging.getLogger(__name__)


def record_user_action(
    request,
    action_type: str,
    product_id: Optional[int] = None,
    product_name: Optional[str] = None,
    cart_value: Optional[float] = None,
    order_id: Optional[int] = None,
    order_number: Optional[str] = None,
    metadata: Optional[dict] = None,
    **kwargs
) -> Optional[UserAction]:
    """
    Записывает действие пользователя для UTM-аналитики.

    Args:
        request: Django request object
        action_type: Тип действия (из UserAction.ACTION_TYPES)
        product_id: ID товара (для product_view, add_to_cart)
        product_name: Название товара
        cart_value: Сумма корзины или заказа
        order_id: ID заказа (для lead, purchase)
        order_number: Номер заказа
        metadata: Дополнительные метаданные (dict)
        **kwargs: Дополнительные параметры

    Returns:
        UserAction или None
    """
    try:
        # Получаем session_key
        session_key = request.session.session_key
        if not session_key:
            request.session.save()
            session_key = request.session.session_key

        if not session_key:
            logger.warning("Could not get session_key for user action")
            return None

        # Получаем UTM сессию
        utm_session = None
        try:
            utm_session = UTMSession.objects.get(session_key=session_key)
        except UTMSession.DoesNotExist:
            logger.debug(f"No UTM session found for session_key: {session_key}")

        # Получаем Site сессию
        site_session = None
        try:
            site_session = SiteSession.objects.get(session_key=session_key)
        except SiteSession.DoesNotExist:
            logger.debug(f"No Site session found for session_key: {session_key}")

        # Получаем пользователя
        user = request.user if request.user.is_authenticated else None

        # Рассчитываем баллы за действие
        points = calculate_action_points(
            action_type,
            cart_value=cart_value,
            order_value=cart_value,
            **kwargs
        )

        base_metadata = dict(metadata or {})
        visitor_id = getattr(request, 'analytics_visitor_id', None)
        if visitor_id and 'visitor_id' not in base_metadata:
            base_metadata['visitor_id'] = visitor_id
        if hasattr(request, 'analytics_first_touch_data') and request.analytics_first_touch_data and 'first_touch' not in base_metadata:
            base_metadata['first_touch'] = request.analytics_first_touch_data
        audience_snapshot = getattr(request, 'analytics_audience_snapshot', None)
        if audience_snapshot is None:
            audience_snapshot = build_audience_snapshot(
                user=user,
                ip_value=getattr(site_session, 'ip_address', None),
                existing_payload=getattr(site_session, 'first_touch_data', None),
            )
        base_metadata = merge_audience_metadata(base_metadata, audience_snapshot)

        # Создаем запись действия
        action = UserAction.objects.create(
            utm_session=utm_session,
            site_session=site_session,
            user=user,
            action_type=action_type,
            page_path=request.path[:512] if hasattr(request, 'path') else None,
            product_id=product_id,
            product_name=product_name[:255] if product_name else None,
            cart_value=cart_value,
            order_id=order_id,
            order_number=order_number[:20] if order_number else None,
            metadata=base_metadata,
            points_earned=points,
        )

        logger.info(f"Recorded user action: {action_type} (points: {points})")
        return action

    except Exception as e:
        logger.error(f"Error recording user action: {e}", exc_info=True)
        return None


def record_page_view(request, page_path: Optional[str] = None):
    """Записывает просмотр страницы"""
    return record_user_action(
        request,
        action_type='page_view',
        metadata={'page_path': page_path or request.path}
    )


def record_product_view(request, product_id: int, product_name: Optional[str] = None):
    """Записывает просмотр товара"""
    return record_user_action(
        request,
        action_type='product_view',
        product_id=product_id,
        product_name=product_name
    )


def record_add_to_cart(request, product_id: int, product_name: Optional[str] = None, cart_value: Optional[float] = None):
    """Записывает добавление товара в корзину"""
    return record_user_action(
        request,
        action_type='add_to_cart',
        product_id=product_id,
        product_name=product_name,
        cart_value=cart_value
    )


def record_remove_from_cart(request, product_id: int, product_name: Optional[str] = None, cart_value: Optional[float] = None):
    """Записывает удаление товара из корзины"""
    return record_user_action(
        request,
        action_type='remove_from_cart',
        product_id=product_id,
        product_name=product_name,
        cart_value=cart_value
    )


def record_initiate_checkout(request, cart_value: float):
    """Записывает начало оформления заказа"""
    return record_user_action(
        request,
        action_type='initiate_checkout',
        cart_value=cart_value
    )


def record_lead(request, order_id: int, order_number: str, cart_value: float):
    """
    Записывает лид (предоплата).
    Также помечает UTM-сессию как конверсионную.
    """
    action = record_user_action(
        request,
        action_type='lead',
        order_id=order_id,
        order_number=order_number,
        cart_value=cart_value
    )

    # Помечаем UTM-сессию как конверсионную
    try:
        session_key = request.session.session_key
        if session_key:
            utm_session = UTMSession.objects.get(session_key=session_key)
            utm_session.mark_as_converted(conversion_type='lead')
            logger.info(f"Marked UTM session as converted (lead): {utm_session}")
    except UTMSession.DoesNotExist:
        pass
    except Exception as e:
        logger.error(f"Error marking UTM session as converted: {e}")

    return action


def record_purchase(request, order_id: int, order_number: str, cart_value: float):
    """
    Записывает покупку (полная оплата).
    Также помечает UTM-сессию как конверсионную.
    """
    action = record_user_action(
        request,
        action_type='purchase',
        order_id=order_id,
        order_number=order_number,
        cart_value=cart_value
    )

    # Помечаем UTM-сессию как конверсионную
    try:
        session_key = request.session.session_key
        if session_key:
            utm_session = UTMSession.objects.get(session_key=session_key)
            utm_session.mark_as_converted(conversion_type='purchase')
            logger.info(f"Marked UTM session as converted (purchase): {utm_session}")
    except UTMSession.DoesNotExist:
        pass
    except Exception as e:
        logger.error(f"Error marking UTM session as converted: {e}")

    return action


def record_search(request, query: str):
    """Записывает поисковый запрос"""
    return record_user_action(
        request,
        action_type='search',
        metadata={'query': query}
    )


def record_custom_print_event(request, action_type: str, *, lead=None, step_key: Optional[str] = None, metadata: Optional[dict] = None):
    """Records a custom-print lifecycle event."""
    payload = dict(metadata or {})
    if lead is not None:
        payload.setdefault('lead_id', getattr(lead, 'pk', None))
        payload.setdefault('lead_number', getattr(lead, 'lead_number', ''))
        payload.setdefault('product_type', getattr(lead, 'product_type', ''))
        payload.setdefault('client_kind', getattr(lead, 'client_kind', ''))
        payload.setdefault('source', getattr(lead, 'source', ''))
    if step_key:
        payload['step_key'] = step_key
    return record_user_action(request, action_type=action_type, metadata=payload)


def record_survey_event(request, action_type: str, *, session=None, question_id: Optional[str] = None, metadata: Optional[dict] = None):
    """Records a survey lifecycle event."""
    payload = dict(metadata or {})
    if session is not None:
        payload.setdefault('survey_session_id', getattr(session, 'pk', None))
        payload.setdefault('survey_key', getattr(session, 'survey_key', ''))
        payload.setdefault('survey_status', getattr(session, 'status', ''))
    if question_id:
        payload['question_id'] = question_id
    return record_user_action(request, action_type=action_type, metadata=payload)


def record_order_action(
    action_type: str,
    order,
    *,
    request=None,
    cart_value: Optional[float] = None,
    metadata: Optional[dict] = None,
) -> Optional[UserAction]:
    """Records an order-level action even when payment confirmation arrives from a webhook."""
    try:
        session_key = None
        if request is not None:
            session_key = request.session.session_key
            if not session_key:
                request.session.save()
                session_key = request.session.session_key
        session_key = session_key or getattr(order, 'session_key', None)

        utm_session = getattr(order, 'utm_session', None)
        if utm_session is None and session_key:
            utm_session = UTMSession.objects.filter(session_key=session_key).first()

        site_session = SiteSession.objects.filter(session_key=session_key).first() if session_key else None
        user = getattr(order, 'user', None)
        if user is None and request is not None and getattr(request.user, 'is_authenticated', False):
            user = request.user

        points = calculate_action_points(
            action_type,
            cart_value=cart_value,
            order_value=cart_value,
        )

        base_metadata = dict(metadata or {})
        if request is not None:
            visitor_id = getattr(request, 'analytics_visitor_id', None)
            first_touch = getattr(request, 'analytics_first_touch_data', None)
        else:
            visitor_id = getattr(site_session, 'visitor_id', None) or getattr(utm_session, 'visitor_id', None)
            first_touch = getattr(site_session, 'first_touch_data', None)

        if visitor_id and 'visitor_id' not in base_metadata:
            base_metadata['visitor_id'] = visitor_id
        if first_touch and 'first_touch' not in base_metadata:
            base_metadata['first_touch'] = first_touch
        base_metadata = merge_audience_metadata(
            base_metadata,
            build_audience_snapshot(
                user=user,
                ip_value=getattr(site_session, 'ip_address', None),
                existing_payload=getattr(site_session, 'first_touch_data', None),
            ),
        )

        action = UserAction.objects.create(
            utm_session=utm_session,
            site_session=site_session,
            user=user,
            action_type=action_type,
            page_path=request.path[:512] if request is not None and hasattr(request, 'path') else None,
            cart_value=cart_value if cart_value is not None else getattr(order, 'total_sum', None),
            order_id=getattr(order, 'pk', None),
            order_number=(getattr(order, 'order_number', None) or '')[:20] or None,
            metadata=base_metadata,
            points_earned=points,
        )

        if utm_session is not None and action_type in {'lead', 'purchase'}:
            utm_session.mark_as_converted(conversion_type=action_type)

        logger.info("Recorded order action: %s for order %s", action_type, getattr(order, 'order_number', getattr(order, 'pk', None)))
        return action
    except Exception as e:
        logger.error(f"Error recording order action: {e}", exc_info=True)
        return None


def link_order_to_utm(request, order):
    """
    Связывает заказ с UTM-сессией.
    Копирует UTM-параметры в заказ для быстрого доступа.

    Args:
        request: Django request object
        order: Order instance
    """
    try:
        session_key = request.session.session_key or order.session_key
        if not session_key:
            logger.warning("No session_key to link order to UTM")
            return

        # Получаем UTM сессию
        utm_session = UTMSession.objects.get(session_key=session_key)

        # Связываем заказ с UTM
        order.utm_session = utm_session

        # Кэшируем UTM-параметры в заказе для быстрого доступа
        order.utm_source = utm_session.utm_source
        order.utm_medium = utm_session.utm_medium
        order.utm_campaign = utm_session.utm_campaign
        order.utm_content = utm_session.utm_content
        order.utm_term = utm_session.utm_term

        order.save(update_fields=[
            'utm_session', 'utm_source', 'utm_medium',
            'utm_campaign', 'utm_content', 'utm_term'
        ])

        logger.info(f"Linked order {order.order_number} to UTM session: {utm_session}")

    except UTMSession.DoesNotExist:
        logger.debug(f"No UTM session found for session_key: {session_key}")
    except Exception as e:
        logger.error(f"Error linking order to UTM: {e}", exc_info=True)


def mark_user_registered(request):
    """
    Отмечает в UTM-сессии, что пользователь зарегистрировался.
    Вызывается после успешной регистрации.
    """
    try:
        session_key = request.session.session_key
        if not session_key:
            logger.warning("No session_key to mark user registration")
            return

        utm_session = UTMSession.objects.get(session_key=session_key)
        utm_session.mark_user_registered()
        logger.info(f"Marked user as registered in UTM session: {utm_session}")

    except UTMSession.DoesNotExist:
        logger.debug(f"No UTM session found for session_key: {session_key}")
    except Exception as e:
        logger.error(f"Error marking user registration in UTM: {e}", exc_info=True)
