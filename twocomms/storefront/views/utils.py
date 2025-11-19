"""
Утилиты и helper функции для views модуля storefront.

Содержит общие функции, которые используются в разных view модулях.
"""

from functools import wraps
from django.db import transaction
from django.views.decorators.cache import cache_page


def cache_page_for_anon(timeout):
    """
    Кэширует страницу только для анонимных пользователей.
    
    Избегаем проблем с кэшированием персональных данных для авторизованных пользователей.
    Для authenticated пользователей кэширование отключается.
    
    Args:
        timeout (int): Время кэширования в секундах
        
    Returns:
        decorator: Декоратор для view функции
        
    Usage:
        @cache_page_for_anon(300)  # 5 минут
        def product_list(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if request.user.is_authenticated:
                # Авторизованные пользователи - без кэша
                return view_func(request, *args, **kwargs)
            # Анонимные пользователи - с кэшем
            return cache_page(timeout)(view_func)(request, *args, **kwargs)
        return _wrapped_view
    return decorator


def unique_slugify(model, base_slug):
    """
    Створює унікальний slug на основі base_slug для заданої моделі.
    
    Якщо slug вже існує, додає числовий суфікс (-2, -3, і т.д.) 
    до тих пір, поки не знайде унікальне значення.
    
    Args:
        model: Django модель (клас, не інстанс)
        base_slug (str): Базовий slug для генерації
        
    Returns:
        str: Унікальний slug
        
    Example:
        >>> unique_slugify(Product, 'my-product')
        'my-product'
        >>> unique_slugify(Product, 'my-product')  # якщо вже існує
        'my-product-2'
    """
    slug = base_slug or 'item'
    # Видаляємо зайві дефіси по краям
    slug = slug.strip('-') or 'item'
    
    uniq = slug
    i = 2
    
    # Перевіряємо унікальність, якщо вже існує - додаємо номер
    while model.objects.filter(slug=uniq).exists():
        uniq = f"{slug}-{i}"
        i += 1
    
    return uniq


def get_cart_from_session(request):
    """
    Извлекает корзину из сессии.
    
    Args:
        request: Django request object
        
    Returns:
        dict: Словарь с данными корзины
    """
    return request.session.get('cart', {})


def save_cart_to_session(request, cart):
    """
    Сохраняет корзину в сессию.
    
    Args:
        request: Django request object
        cart (dict): Данные корзины
    """
    request.session['cart'] = cart
    request.session.modified = True


def calculate_cart_total(cart):
    """
    Рассчитывает общую стоимость товаров в корзине.
    
    ВАЖНО: Цена ВСЕГДА берется из Product.final_price, а НЕ из сессии!
    Это обеспечивает актуальность цен и предотвращает манипуляции.
    
    Args:
        cart (dict): Данные корзины из сессии
        
    Returns:
        Decimal: Общая сумма
    """
    from decimal import Decimal
    from ..models import Product
    
    if not cart:
        return Decimal('0')
    
    # Получаем все товары одним запросом
    ids = [item['product_id'] for item in cart.values()]
    products = Product.objects.in_bulk(ids)
    
    total = Decimal('0')
    for item in cart.values():
        product = products.get(item['product_id'])
        if product:
            qty = int(item.get('qty', 0))
            total += product.final_price * qty
    
    return total


def get_favorites_from_session(request):
    """
    Получает избранные товары из сессии (для анонимных пользователей).
    
    Args:
        request: Django request object
        
    Returns:
        list: Список ID избранных товаров
    """
    return request.session.get('favorites', [])


def save_favorites_to_session(request, favorites):
    """
    Сохраняет избранные товары в сессию.
    
    Args:
        request: Django request object
        favorites (list): Список ID товаров
    """
    request.session['favorites'] = favorites
    request.session.modified = True


# Константы
HOME_PRODUCTS_PER_PAGE = 8
PRODUCTS_PER_PAGE = 16
SEARCH_RESULTS_PER_PAGE = 20


# ==================== MONOBANK & CART HELPERS ====================

import logging

monobank_logger = logging.getLogger('storefront.monobank')


_PAY_TYPE_CANONICAL_MAP = {
    # Canonical values
    'online_full': 'online_full',
    'prepay_200': 'prepay_200',
    # Legacy/full-payment aliases
    'full': 'online_full',
    'online': 'online_full',
    'online-full': 'online_full',
    'online_full_payment': 'online_full',
    'онлайн оплата (повна сума)': 'online_full',
    'оплата повністю': 'online_full',
    'оплатити повністю': 'online_full',
    # Legacy/prepayment aliases
    'prepay': 'prepay_200',
    'prepay200': 'prepay_200',
    'prepaid': 'prepay_200',
    'partial': 'prepay_200',
    'partial_payment': 'prepay_200',
    'cod': 'prepay_200',
    'внести передплату 200 грн': 'prepay_200',
    'передплата 200 грн': 'prepay_200',
    'передплата 200 грн (решта при отриманні)': 'prepay_200',
}


def _normalize_order_pay_type(value):
    """
    Возвращает каноническое значение pay_type для заказа.

    Всегда приводит строку к нижнему регистру и убирает пробелы, чтобы
    поддерживать устаревшие/локализованные значения.
    """
    if not value:
        return 'online_full'

    normalized = str(value).strip()
    if not normalized:
        return 'online_full'

    canonical = _PAY_TYPE_CANONICAL_MAP.get(normalized.lower())
    if canonical:
        return canonical

    # Если значение уже одно из допустимых - возвращаем его, иначе online_full
    if normalized in ('online_full', 'prepay_200'):
        return normalized

    return 'online_full'


def _reset_monobank_session(request, drop_pending=False):
    """
    Сбрасывает связанные с Mono checkout данные в сессии.
    
    Args:
        request: HTTP request
        drop_pending: Если True, отменяет pending заказ в БД
    """
    if drop_pending:
        pending_id = request.session.get('monobank_pending_order_id')
        if pending_id:
            try:
                from orders.models import Order
                qs = Order.objects.select_related('user').filter(
                    id=pending_id,
                    payment_provider__in=('monobank', 'monobank_checkout', 'monobank_pay')
                )
                if qs.exists():
                    qs.update(status='cancelled', payment_status='unpaid')
            except Exception:
                monobank_logger.debug(
                    'Failed to cancel pending Monobank order %s',
                    pending_id,
                    exc_info=True
                )

    for key in (
        'monobank_pending_order_id',
        'monobank_invoice_id',
        'monobank_order_id',
        'monobank_order_ref'
    ):
        if key in request.session:
            request.session.pop(key, None)

    request.session.modified = True


def _normalize_color_variant_id(raw):
    """
    Приводит значение идентификатора цветового варианта к int либо None.
    Отсекает плейсхолдеры вида 'default', 'null', 'None', 'false', 'undefined'.
    """
    if raw is None:
        return None
    if isinstance(raw, int):
        return raw if raw > 0 else None
    try:
        value = str(raw).strip()
    except Exception:
        return None
    if not value:
        return None
    lowered = value.lower()
    if lowered in {'default', 'none', 'null', 'false', 'undefined'}:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _get_color_variant_safe(color_variant_id):
    """
    Возвращает экземпляр ProductColorVariant либо None, не выбрасывая ошибок.
    """
    normalized_id = _normalize_color_variant_id(color_variant_id)
    if not normalized_id:
        return None
    try:
        from productcolors.models import ProductColorVariant
        return ProductColorVariant.objects.get(id=normalized_id)
    except (ProductColorVariant.DoesNotExist, ValueError, TypeError):
        return None
    except ImportError:
        return None


def _hex_to_name(hex_value: str):
    """Конвертирует hex цвета в украинское название."""
    if not hex_value:
        return None
    h = hex_value.strip().lstrip('#').upper()
    mapping = {
        '000000': 'чорний',
        'FFFFFF': 'білий',
        'FAFAFA': 'білий',
        'F5F5F5': 'білий',
        'FF0000': 'червоний',
        'C1382F': 'бордовий',
        'FFA500': 'помаранчевий',
        'FFFF00': 'жовтий',
        '00FF00': 'зелений',
        '0000FF': 'синій',
        '808080': 'сірий',
        'A52A2A': 'коричневий',
        '800080': 'фіолетовий',
    }
    return mapping.get(h)


def _translate_color_to_ukrainian(color_name):
    """Переводит название цвета на украинский."""
    if not color_name:
        return color_name
    # Простой маппинг, можно расширить
    translations = {
        'black': 'чорний',
        'white': 'білий',
        'red': 'червоний',
        'blue': 'синій',
        'green': 'зелений',
        'yellow': 'жовтий',
        'orange': 'помаранчевий',
        'purple': 'фіолетовий',
        'pink': 'рожевий',
        'gray': 'сірий',
        'grey': 'сірий',
        'brown': 'коричневий',
    }
    lower_name = color_name.lower()
    return translations.get(lower_name, color_name)


def _color_label_from_variant(color_variant):
    """
    Возвращает текстовую метку цвета из варианта.
    """
    if not color_variant:
        return None
    color = getattr(color_variant, 'color', None)
    if not color:
        return None
    name = (getattr(color, 'name', '') or '').strip()
    if name:
        return _translate_color_to_ukrainian(name)
    primary = (getattr(color, 'primary_hex', '') or '').strip()
    secondary = (getattr(color, 'secondary_hex', '') or '').strip()
    if secondary:
        label = _translate_color_to_ukrainian(
            '/'.join(filter(None, [_hex_to_name(primary), _hex_to_name(secondary)]))
        )
        if label:
            return label
        return f'{primary}+{secondary}'
    if primary:
        label = _hex_to_name(primary)
        if label:
            return label
        return primary
    return None


# ==================== MONOBANK HELPER FUNCTIONS ====================

# Константы статусов Monobank
MONOBANK_SUCCESS_STATUSES = {'success', 'hold'}
MONOBANK_PENDING_STATUSES = {'processing'}
MONOBANK_FAILURE_STATUSES = {
    'failure', 'expired', 'rejected', 'canceled', 'cancelled', 'reversed'
}


def _record_monobank_status(order, payload, source='api'):
    """
    Записывает статус платежа Monobank в заказ с блокировкой записи.
    
    Args:
        order: Объект заказа
        payload: Данные от Monobank API
        source: Источник данных ('api' или 'webhook')
    """
    if not payload or not order or not getattr(order, 'pk', None):
        return

    from orders.models import Order

    try:
        with transaction.atomic():
            locked_order = (
                Order.objects.select_for_update()
                .select_related('user')
                .get(pk=order.pk)
            )
            result = _record_monobank_status_locked(locked_order, payload, source)
    except Order.DoesNotExist:
        monobank_logger.error(
            'Failed to record Monobank status: order %s not found',
            getattr(order, 'pk', None),
        )
        return

    try:
        order.refresh_from_db()
    except Exception:
        # В большинстве случаев order передается только для идентификатора
        pass

    return result


def _record_monobank_status_locked(order, payload, source='api'):
    """Реализация логики записи статуса под транзакционной блокировкой."""
    from django.utils import timezone
    
    if not payload:
        return

    status = payload.get('status')
    payment_payload = order.payment_payload or {}
    history = payment_payload.get('history', [])
    history.append({
        'status': status,
        'data': payload,
        'source': source,
        'received_at': timezone.now().isoformat()
    })
    payment_payload['history'] = history[-20:]
    payment_payload['last_status'] = status
    payment_payload['last_update_source'] = source
    payment_payload['last_update_at'] = timezone.now().isoformat()
    order.payment_payload = payment_payload

    update_fields = ['payment_payload']

    if status in MONOBANK_SUCCESS_STATUSES:
        previous_status = order.payment_status
        normalized_previous = 'prepaid' if previous_status == 'partial' else previous_status

        raw_pay_type = getattr(order, 'pay_type', None)
        pay_type = _normalize_order_pay_type(raw_pay_type)
        target_status = 'prepaid' if pay_type == 'prepay_200' else 'paid'

        if normalized_previous == target_status:
            monobank_logger.info(
                f'⚠️ Order {order.order_number}: webhook повторно получен, '
                f'статус уже {target_status} (pay_type_raw={raw_pay_type}, normalized={pay_type}). '
                f'Пропускаем обновление.'
            )
            try:
                order.save(update_fields=['payment_payload'])
            except Exception:
                order.save()
            return

        if normalized_previous == 'paid' and target_status == 'prepaid':
            monobank_logger.warning(
                f'⚠️ Order {order.order_number}: pay_type={pay_type} требует статус prepaid, '
                f'но в заказе было {previous_status}. Исправляем.'
            )
        elif normalized_previous == 'prepaid' and target_status == 'paid':
            monobank_logger.warning(
                f'⚠️ Order {order.order_number}: pay_type={pay_type} требует статус paid, '
                f'но в заказе было {previous_status}. Исправляем.'
            )

        order.payment_status = target_status
        update_fields.append('payment_status')

        if target_status == 'prepaid':
            monobank_logger.info(
                f'✅ Order {order.order_number}: prepayment successful → payment_status=prepaid '
                f'(pay_type_raw={raw_pay_type}, normalized={pay_type}, previous_status={previous_status})'
            )
        else:
            monobank_logger.info(
                f'✅ Order {order.order_number}: full payment successful → payment_status=paid '
                f'(pay_type_raw={raw_pay_type}, normalized={pay_type}, previous_status={previous_status})'
            )

        try:
            order.save(update_fields=update_fields)
        except Exception:
            order.save()
        
        # Отправляем уведомления только если статус изменился
        if previous_status != order.payment_status:
            # Проверяем что Telegram уведомление еще не отправлено (защита от дублирования)
            payment_payload = order.payment_payload or {}
            telegram_notifications = payment_payload.get('telegram_notifications', {})
            telegram_sent = telegram_notifications.get('order_notification_sent', False)
            
            # 1. Telegram уведомление (только если еще не отправлено)
            if not telegram_sent:
                try:
                    from orders.telegram_notifications import TelegramNotifier
                    notifier = TelegramNotifier()
                    notifier.send_new_order_notification(order)
                    
                    # Сохраняем в payment_payload что уведомление отправлено
                    if 'telegram_notifications' not in payment_payload:
                        payment_payload['telegram_notifications'] = {}
                    payment_payload['telegram_notifications']['order_notification_sent'] = True
                    payment_payload['telegram_notifications']['order_notification_sent_at'] = timezone.now().isoformat()
                    payment_payload['telegram_notifications']['order_notification_status'] = order.payment_status
                    order.payment_payload = payment_payload
                    order.save(update_fields=['payment_payload'])
                    
                    monobank_logger.info(
                        f'📱 Telegram notification sent for order {order.order_number} '
                        f'(status: {previous_status} → {order.payment_status})'
                    )
                except Exception as e:
                    monobank_logger.exception(f'Failed to send Telegram notification for order {order.order_number}: {e}')
            else:
                monobank_logger.info(
                    f'⚠️ Order {order.order_number}: Telegram notification already sent '
                    f'(status changed: {previous_status} → {order.payment_status}), skipping duplicate'
                )
            
            # 2. Facebook событие
            try:
                from orders.facebook_conversions_service import get_facebook_conversions_service
                fb_service = get_facebook_conversions_service()
                
                if fb_service.enabled:
                    if order.payment_status == 'prepaid':
                        # Предоплата → Lead event
                        # Проверяем, не было ли уже отправлено
                        payment_payload = order.payment_payload or {}
                        facebook_events = payment_payload.get('facebook_events', {})
                        if not facebook_events.get('lead_sent', False):
                            success = fb_service.send_lead_event(order)
                            if success:
                                # Сохраняем в payment_payload что Lead отправлен
                                if 'facebook_events' not in payment_payload:
                                    payment_payload['facebook_events'] = {}
                                payment_payload['facebook_events']['lead_sent'] = True
                                payment_payload['facebook_events']['lead_sent_at'] = timezone.now().isoformat()
                                order.payment_payload = payment_payload
                                order.save(update_fields=['payment_payload'])
                                monobank_logger.info(f'📊 Facebook Lead event sent for order {order.order_number} (prepayment)')
                            else:
                                monobank_logger.warning(f'⚠️ Failed to send Facebook Lead event for order {order.order_number}')
                        else:
                            monobank_logger.info(f'📊 Facebook Lead event already sent for order {order.order_number} (prepayment), skipping')
                    elif order.payment_status == 'paid':
                        # Полная оплата → ТОЛЬКО Purchase событие
                        # Lead отправляется ТОЛЬКО для prepaid (предоплата)
                        payment_payload = order.payment_payload or {}
                        facebook_events = payment_payload.get('facebook_events', {})
                        
                        # Purchase для paid статуса
                        purchase_success = fb_service.send_purchase_event(order)
                        if purchase_success:
                            # Сохраняем в payment_payload что Purchase отправлен
                            if 'facebook_events' not in payment_payload:
                                payment_payload['facebook_events'] = {}
                            payment_payload['facebook_events']['purchase_sent'] = True
                            payment_payload['facebook_events']['purchase_sent_at'] = timezone.now().isoformat()
                            order.payment_payload = payment_payload
                            order.save(update_fields=['payment_payload'])
                            monobank_logger.info(f'✅ Facebook Purchase event sent for order {order.order_number} (full payment)')
                        else:
                            monobank_logger.warning(f'⚠️ Failed to send Facebook Purchase event for order {order.order_number}')
                else:
                    monobank_logger.warning(f'⚠️ Facebook Conversions API not enabled, skipping event')
            except Exception as e:
                monobank_logger.exception(f'Failed to send Facebook event for order {order.order_number}: {e}')

            # 3. TikTok Events API
            try:
                from orders.tiktok_events_service import get_tiktok_events_service
                tiktok_service = get_tiktok_events_service()

                if tiktok_service.enabled:
                    if order.payment_status == 'prepaid':
                        payment_payload = order.payment_payload or {}
                        tiktok_events = payment_payload.get('tiktok_events', {})

                        if not tiktok_events.get('lead_sent', False):
                            success = tiktok_service.send_lead_event(order)
                            if success:
                                if 'tiktok_events' not in payment_payload:
                                    payment_payload['tiktok_events'] = {}
                                payment_payload['tiktok_events']['lead_sent'] = True
                                payment_payload['tiktok_events']['lead_sent_at'] = timezone.now().isoformat()
                                order.payment_payload = payment_payload
                                order.save(update_fields=['payment_payload'])
                                monobank_logger.info(f'📈 TikTok Lead event sent for order {order.order_number} (prepayment)')
                            else:
                                monobank_logger.warning(f'⚠️ Failed to send TikTok Lead event for order {order.order_number}')
                        else:
                            monobank_logger.info(f'📈 TikTok Lead event already sent for order {order.order_number} (prepayment), skipping')

                    elif order.payment_status == 'paid':
                        # Полная оплата → ТОЛЬКО Purchase событие
                        # Lead отправляется ТОЛЬКО для prepaid (предоплата)
                        payment_payload = order.payment_payload or {}
                        tiktok_events = payment_payload.get('tiktok_events', {})

                        purchase_success = tiktok_service.send_purchase_event(order)
                        if purchase_success:
                            if 'tiktok_events' not in payment_payload:
                                payment_payload['tiktok_events'] = {}
                            payment_payload['tiktok_events']['purchase_sent'] = True
                            payment_payload['tiktok_events']['purchase_sent_at'] = timezone.now().isoformat()
                            order.payment_payload = payment_payload
                            order.save(update_fields=['payment_payload'])
                            monobank_logger.info(f'✅ TikTok Purchase event sent for order {order.order_number} (full payment)')
                        else:
                            monobank_logger.warning(f'⚠️ Failed to send TikTok Purchase event for order {order.order_number}')
                else:
                    monobank_logger.warning('⚠️ TikTok Events API not enabled, skipping events')
            except ImportError:
                monobank_logger.debug('TikTok Events service module not found, skipping')
            except Exception as e:
                monobank_logger.exception(f'Failed to send TikTok event for order {order.order_number}: {e}')
        
        return

    if status in MONOBANK_PENDING_STATUSES:
        order.payment_status = 'checking'
        update_fields.append('payment_status')
    elif status in MONOBANK_FAILURE_STATUSES:
        order.payment_status = 'unpaid'
        update_fields.append('payment_status')

    try:
        order.save(update_fields=update_fields)
    except Exception:
        order.save()


def _verify_monobank_signature(request):
    """
    Проверяет подпись Monobank webhook запроса.
    ВОССТАНОВЛЕНА РАБОЧАЯ ЛОГИКА из старого views.py
    
    Args:
        request: HTTP request с заголовком X-Sign
        
    Returns:
        bool: True если подпись валидна, False иначе
    """
    import base64
    from django.core.cache import cache
    from django.conf import settings
    
    try:
        signature = request.headers.get('X-Sign')
        if not signature:
            monobank_logger.warning('Missing X-Sign header in Monobank webhook')
            return False
        
        # Получаем публичный ключ из кеша или API
        MONOBANK_PUBLIC_KEY_CACHE_KEY = 'monobank_public_key'
        cached_key = cache.get(MONOBANK_PUBLIC_KEY_CACHE_KEY)
        
        if not cached_key:
            # Запрашиваем у API
            import requests
            response = requests.get(
                'https://api.monobank.ua/api/merchant/pubkey',
                headers={'X-Token': settings.MONOBANK_TOKEN},
                timeout=10
            )
            response.raise_for_status()
            cached_key = response.json().get('key')
            
            if cached_key:
                cache.set(MONOBANK_PUBLIC_KEY_CACHE_KEY, cached_key, 3600)
        
        if not cached_key:
            monobank_logger.error('Failed to get Monobank public key for verification')
            return False
        
        # Получаем тело запроса
        body = request.body
        
        # Проверяем подпись
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.hazmat.backends import default_backend
        
        # Загружаем публичный ключ
        public_key = serialization.load_pem_public_key(
            cached_key.encode(),
            backend=default_backend()
        )
        
        # Декодируем подпись из base64
        signature_bytes = base64.b64decode(signature)
        
        # Проверяем
        try:
            public_key.verify(
                signature_bytes,
                body,
                padding.PKCS1v15(),
                hashes.SHA256()
            )
            return True
        except Exception as verify_error:
            monobank_logger.warning(f'Monobank signature verification failed: {verify_error}')
            return False
            
    except Exception as e:
        monobank_logger.error(f'Error verifying Monobank signature: {e}', exc_info=True)
        return False


def _update_order_from_checkout_result(order, result, source='api'):
    """
    Обновляет заказ из результата Monobank checkout.
    
    Args:
        order: Объект заказа
        result: Результат от Monobank checkout API
        source: Источник данных ('api' или 'webhook')
    """
    # Преобразуем result в формат payload для _record_monobank_status
    payload = {
        'status': result.get('status', 'unknown'),
        'result': result
    }
    _record_monobank_status(order, payload, source=source)












def clear_cart(request):
    """
    Очистка корзины.
    
    Удаляет все товары из корзины и сбрасывает промокод.
    """
    request.session['cart'] = {}
    if 'promo_code_id' in request.session:
        del request.session['promo_code_id']
    if 'promo_code_data' in request.session:
        del request.session['promo_code_data']
    request.session.modified = True
