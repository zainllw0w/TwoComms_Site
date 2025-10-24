"""
Storefront views package.

Рефакторинг views.py на модульную структуру.

Этот файл обеспечивает обратную совместимость, импортируя все views
из соответствующих модулей и из старого views.py.

Структура:
- utils.py - Утилиты и helper функции
- auth.py - Аутентификация (login, register, logout)
- catalog.py - Каталог товаров (в разработке)
- product.py - Детали товара (в разработке)
- cart.py - Корзина (в разработке)
- checkout.py - Оформление заказа (в разработке)
- profile.py - Профиль пользователя (в разработке)
- admin.py - Админ панель (в разработке)
- api.py - AJAX/API endpoints (в разработке)
- static_pages.py - Статические страницы (в разработке)
"""

# ==================== НОВЫЕ МОДУЛИ ====================

# Утилиты
from .utils import (
    cache_page_for_anon,
    unique_slugify,
    get_cart_from_session,
    save_cart_to_session,
    calculate_cart_total,
    get_favorites_from_session,
    save_favorites_to_session,
    HOME_PRODUCTS_PER_PAGE,
)

# Аутентификация
from .auth import (
    # Forms
    LoginForm,
    RegisterForm,
    ProfileSetupForm,
    # Views
    login_view,
    register_view,
    logout_view,
)


# ==================== ВРЕМЕННЫЙ ИМПОРТ ИЗ СТАРОГО views.py ====================
# TODO: Постепенно мигрировать все функции в соответствующие модули

# Импортируем все остальное из старого views.py
# Это обеспечивает обратную совместимость во время рефакторинга
import sys
import os

# Получаем путь к старому views.py (на уровень выше)
parent_dir = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, parent_dir)

try:
    # Импортируем старый модуль views
    from storefront import views as _old_views
    
    # Список функций/классов для НЕ импорта (уже есть в новых модулях)
    _exclude = {
        'cache_page_for_anon',
        'unique_slugify',
        'LoginForm',
        'RegisterForm', 
        'ProfileSetupForm',
        'login_view',
        'register_view',
        'logout_view',
        # Технические атрибуты Python
        '__name__',
        '__doc__',
        '__package__',
        '__loader__',
        '__spec__',
        '__file__',
        '__cached__',
        '__builtins__',
    }
    
    # Импортируем все остальное из старого views
    for name in dir(_old_views):
        if not name.startswith('_') and name not in _exclude:
            globals()[name] = getattr(_old_views, name)
            
finally:
    # Убираем parent_dir из sys.path
    if parent_dir in sys.path:
        sys.path.remove(parent_dir)


# ==================== ЭКСПОРТЫ ====================

__all__ = [
    # Utils
    'cache_page_for_anon',
    'unique_slugify',
    'get_cart_from_session',
    'save_cart_to_session',
    'calculate_cart_total',
    'get_favorites_from_session',
    'save_favorites_to_session',
    'HOME_PRODUCTS_PER_PAGE',
    
    # Auth Forms
    'LoginForm',
    'RegisterForm',
    'ProfileSetupForm',
    
    # Auth Views
    'login_view',
    'register_view',
    'logout_view',
    
    # TODO: Добавить экспорты из других модулей по мере их создания
]

