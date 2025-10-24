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
            # Check if user is authenticated (hasattr check for safety)
            if hasattr(request, 'user') and request.user.is_authenticated:
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
















