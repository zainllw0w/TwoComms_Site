"""
Утилиты и helper функции для views модуля storefront.

Содержит общие функции, которые используются в разных view модулях.
"""

from functools import wraps
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
    
    Args:
        cart (dict): Данные корзины
        
    Returns:
        Decimal: Общая сумма
    """
    from decimal import Decimal
    
    total = Decimal('0')
    for item in cart.values():
        price = Decimal(str(item.get('price', 0)))
        qty = int(item.get('qty', 0))
        total += price * qty
    
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
















