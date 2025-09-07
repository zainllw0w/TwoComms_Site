"""
Система A/B тестирования для оптимизации конверсии
"""
from django.core.cache import cache
from django.utils import timezone
import hashlib
import random

class ABTestManager:
    """
    Менеджер A/B тестов
    """
    
    def __init__(self, user_id=None, session_key=None):
        self.user_id = user_id
        self.session_key = session_key
        self.cache_timeout = 86400  # 24 часа
    
    def get_variant(self, test_name, variants=None, default_variant='A'):
        """
        Получает вариант для A/B теста
        """
        if variants is None:
            variants = ['A', 'B']
        
        # Создаем уникальный ключ для пользователя/сессии
        user_key = self.user_id or self.session_key or 'anonymous'
        
        # Генерируем детерминированный хэш
        hash_input = f"{test_name}_{user_key}"
        hash_value = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
        
        # Выбираем вариант на основе хэша
        variant_index = hash_value % len(variants)
        variant = variants[variant_index]
        
        # Кэшируем результат
        cache_key = f"ab_test_{test_name}_{user_key}"
        cache.set(cache_key, variant, self.cache_timeout)
        
        # Логируем участие в тесте
        self._log_test_participation(test_name, variant, user_key)
        
        return variant
    
    def _log_test_participation(self, test_name, variant, user_key):
        """
        Логирует участие в A/B тесте
        """
        # Здесь можно добавить логику для сохранения в базу данных
        # или отправки в аналитику
        pass
    
    def track_conversion(self, test_name, conversion_type, value=None):
        """
        Отслеживает конверсию для A/B теста
        """
        user_key = self.user_id or self.session_key or 'anonymous'
        cache_key = f"ab_test_{test_name}_{user_key}"
        variant = cache.get(cache_key)
        
        if variant:
            # Логируем конверсию
            self._log_conversion(test_name, variant, conversion_type, value, user_key)
    
    def _log_conversion(self, test_name, variant, conversion_type, value, user_key):
        """
        Логирует конверсию
        """
        # Здесь можно добавить логику для сохранения в базу данных
        # или отправки в аналитику
        pass

# Предустановленные A/B тесты
class HomePageTests:
    """
    A/B тесты для главной страницы
    """
    
    @staticmethod
    def get_hero_layout_variant(user_id=None, session_key=None):
        """
        Тест макета героя на главной странице
        """
        manager = ABTestManager(user_id, session_key)
        return manager.get_variant(
            'hero_layout',
            ['centered', 'left_aligned', 'right_aligned'],
            'centered'
        )
    
    @staticmethod
    def get_cta_button_variant(user_id=None, session_key=None):
        """
        Тест кнопки призыва к действию
        """
        manager = ABTestManager(user_id, session_key)
        return manager.get_variant(
            'cta_button',
            ['primary', 'outline', 'gradient'],
            'primary'
        )
    
    @staticmethod
    def get_product_grid_variant(user_id=None, session_key=None):
        """
        Тест сетки товаров
        """
        manager = ABTestManager(user_id, session_key)
        return manager.get_variant(
            'product_grid',
            ['grid_3', 'grid_4', 'grid_5'],
            'grid_4'
        )

class ProductPageTests:
    """
    A/B тесты для страницы товара
    """
    
    @staticmethod
    def get_image_gallery_variant(user_id=None, session_key=None):
        """
        Тест галереи изображений
        """
        manager = ABTestManager(user_id, session_key)
        return manager.get_variant(
            'image_gallery',
            ['carousel', 'grid', 'single_large'],
            'carousel'
        )
    
    @staticmethod
    def get_add_to_cart_variant(user_id=None, session_key=None):
        """
        Тест кнопки добавления в корзину
        """
        manager = ABTestManager(user_id, session_key)
        return manager.get_variant(
            'add_to_cart',
            ['button_large', 'button_small', 'button_with_icon'],
            'button_large'
        )

class CheckoutTests:
    """
    A/B тесты для процесса оформления заказа
    """
    
    @staticmethod
    def get_checkout_layout_variant(user_id=None, session_key=None):
        """
        Тест макета страницы оформления заказа
        """
        manager = ABTestManager(user_id, session_key)
        return manager.get_variant(
            'checkout_layout',
            ['single_column', 'two_column', 'step_by_step'],
            'single_column'
        )
    
    @staticmethod
    def get_payment_methods_variant(user_id=None, session_key=None):
        """
        Тест отображения способов оплаты
        """
        manager = ABTestManager(user_id, session_key)
        return manager.get_variant(
            'payment_methods',
            ['all_visible', 'progressive_disclosure', 'recommended_first'],
            'all_visible'
        )

# Контекстный процессор для A/B тестов
def ab_test_context(request):
    """
    Контекстный процессор для A/B тестов
    """
    user_id = request.user.id if request.user.is_authenticated else None
    session_key = request.session.session_key
    
    return {
        'ab_test_hero_layout': HomePageTests.get_hero_layout_variant(user_id, session_key),
        'ab_test_cta_button': HomePageTests.get_cta_button_variant(user_id, session_key),
        'ab_test_product_grid': HomePageTests.get_product_grid_variant(user_id, session_key),
        'ab_test_image_gallery': ProductPageTests.get_image_gallery_variant(user_id, session_key),
        'ab_test_add_to_cart': ProductPageTests.get_add_to_cart_variant(user_id, session_key),
        'ab_test_checkout_layout': CheckoutTests.get_checkout_layout_variant(user_id, session_key),
        'ab_test_payment_methods': CheckoutTests.get_payment_methods_variant(user_id, session_key),
    }
