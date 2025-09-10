"""
Сигналы для автоматической генерации AI-контента при создании товаров и категорий
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from .models import Product, Category
from .seo_utils import SEOKeywordGenerator, SEOContentOptimizer
import os


@receiver(post_save, sender=Product)
def generate_ai_content_for_product(sender, instance, created, **kwargs):
    """Автоматически генерирует AI-контент для нового товара"""
    if not created:
        return  # Только для новых товаров
    
    # Проверяем настройки AI
    api_key = getattr(settings, 'OPENAI_API_KEY', None) or os.environ.get('OPENAI_API_KEY')
    if not api_key:
        return  # API ключ не настроен
    
    use_keywords = getattr(settings, 'USE_AI_KEYWORDS', False)
    use_descriptions = getattr(settings, 'USE_AI_DESCRIPTIONS', False)
    
    if not use_keywords and not use_descriptions:
        return  # AI функции отключены
    
    try:
        # Генерируем AI-ключевые слова
        if use_keywords:
            ai_keywords = SEOKeywordGenerator.generate_product_keywords_ai(instance)
            if ai_keywords:
                instance.ai_keywords = ', '.join(ai_keywords)
        
        # Генерируем AI-описание
        if use_descriptions:
            ai_description = SEOContentOptimizer.generate_ai_product_description(instance)
            if ai_description:
                instance.ai_description = ai_description
        
        # Отмечаем что контент сгенерирован и сохраняем
        if (use_keywords and instance.ai_keywords) or (use_descriptions and instance.ai_description):
            instance.ai_content_generated = True
            # Используем update_fields чтобы избежать рекурсии
            instance.save(update_fields=['ai_keywords', 'ai_description', 'ai_content_generated'])
    
    except Exception as e:
        # Логируем ошибку, но не прерываем создание товара
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f'Ошибка генерации AI-контента для товара {instance.id}: {str(e)}')


@receiver(post_save, sender=Category)
def generate_ai_content_for_category(sender, instance, created, **kwargs):
    """Автоматически генерирует AI-контент для новой категории"""
    if not created:
        return  # Только для новых категорий
    
    # Проверяем настройки AI
    api_key = getattr(settings, 'OPENAI_API_KEY', None) or os.environ.get('OPENAI_API_KEY')
    if not api_key:
        return  # API ключ не настроен
    
    use_keywords = getattr(settings, 'USE_AI_KEYWORDS', False)
    use_descriptions = getattr(settings, 'USE_AI_DESCRIPTIONS', False)
    
    if not use_keywords and not use_descriptions:
        return  # AI функции отключены
    
    try:
        # Генерируем AI-ключевые слова
        if use_keywords:
            ai_keywords = SEOKeywordGenerator.generate_category_keywords_ai(instance)
            if ai_keywords:
                instance.ai_keywords = ', '.join(ai_keywords)
        
        # Генерируем AI-описание
        if use_descriptions:
            ai_description = SEOContentOptimizer.generate_ai_category_description(instance)
            if ai_description:
                instance.ai_description = ai_description
        
        # Отмечаем что контент сгенерирован и сохраняем
        if (use_keywords and instance.ai_keywords) or (use_descriptions and instance.ai_description):
            instance.ai_content_generated = True
            # Используем update_fields чтобы избежать рекурсии
            instance.save(update_fields=['ai_keywords', 'ai_description', 'ai_content_generated'])
    
    except Exception as e:
        # Логируем ошибку, но не прерываем создание категории
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f'Ошибка генерации AI-контента для категории {instance.id}: {str(e)}')
