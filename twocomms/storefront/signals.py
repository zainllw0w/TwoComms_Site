"""
Сигналы для автоматического обновления фидов при изменении товаров
"""
import logging
import os
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.conf import settings
from django.core.management import call_command
from .tasks import generate_google_merchant_feed_task

from .models import Product

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Product)
def update_google_merchant_feed_on_product_save(sender, instance, created, **kwargs):
    """
    Автоматически обновляет Google Merchant feed при создании или обновлении товара
    """
    try:
        action = "создан" if created else "обновлен"
        logger.info(f"Товар {instance.title} (ID: {instance.id}) {action}. Обновляем Google Merchant feed...")
        
        # Определяем путь к файлу feed в media
        media_root = getattr(settings, 'MEDIA_ROOT', os.path.join(settings.BASE_DIR, 'media'))
        output_path = os.path.join(media_root, 'google-merchant-v3.xml')
        
        # Вызываем задачу Celery асинхронно
        generate_google_merchant_feed_task.delay()
        
        logger.info(f"Запущена фоновая задача обновления Google Merchant feed")
        
    except Exception as e:
        logger.error(f"Ошибка при обновлении Google Merchant feed: {e}", exc_info=True)


@receiver(post_delete, sender=Product)
def update_google_merchant_feed_on_product_delete(sender, instance, **kwargs):
    """
    Автоматически обновляет Google Merchant feed при удалении товара
    """
    try:
        logger.info(f"Товар {instance.title} (ID: {instance.id}) удален. Обновляем Google Merchant feed...")
        
        # Определяем путь к файлу feed в media
        media_root = getattr(settings, 'MEDIA_ROOT', os.path.join(settings.BASE_DIR, 'media'))
        output_path = os.path.join(media_root, 'google-merchant-v3.xml')
        
        # Вызываем задачу Celery асинхронно
        generate_google_merchant_feed_task.delay()
        
        logger.info(f"Запущена фоновая задача обновления Google Merchant feed")
        
    except Exception as e:
        logger.error(f"Ошибка при обновлении Google Merchant feed: {e}", exc_info=True)















