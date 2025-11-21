"""
Сигналы для автоматического обновления фидов при изменении товаров
"""
import logging
import os
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.conf import settings
from .tasks import generate_google_merchant_feed_task, optimize_image_field_task

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
        
        # Вызываем задачу Celery асинхронно
        generate_google_merchant_feed_task.delay()
        
        logger.info(f"Запущена фоновая задача обновления Google Merchant feed")
        
    except Exception as e:
        logger.error(f"Ошибка при обновлении Google Merchant feed: {e}", exc_info=True)
















def _enqueue_image_optimization(instance, field_name: str):
    """
    Push heavy image optimization work to Celery so it does not block request lifecycle.
    Falls back to synchronous execution if Celery broker is unavailable (useful in dev).
    """
    image_field = getattr(instance, field_name, None)
    if not image_field:
        return
    if not getattr(instance, 'pk', None):
        return
    try:
        optimize_image_field_task.delay(instance._meta.label, instance.pk, field_name)
    except Exception as exc:  # pragma: no cover - Celery not running locally
        logger.warning(
            "Celery broker unavailable, running inline optimization for %s.%s (id=%s): %s",
            instance.__class__.__name__,
            field_name,
            instance.pk,
            exc
        )
        try:
            optimize_image_field_task(instance._meta.label, instance.pk, field_name)
        except Exception as inner:
            logger.error("Inline image optimization failed for %s.%s: %s", instance, field_name, inner, exc_info=True)


# ===== Image Optimization Signals =====
from .models import ProductImage, CatalogOptionValue, SizeGrid, PrintProposal
from productcolors.models import ProductColorImage, ProductColorVariant


@receiver(post_save, sender=Product)
def optimize_product_main_image(sender, instance, **kwargs):
    if instance.main_image:
        _enqueue_image_optimization(instance, 'main_image')


@receiver(post_save, sender=ProductImage)
def optimize_product_extra_image(sender, instance, **kwargs):
    if instance.image:
        _enqueue_image_optimization(instance, 'image')


@receiver(post_save, sender=ProductColorImage)
def optimize_product_color_image(sender, instance, **kwargs):
    if instance.image:
        _enqueue_image_optimization(instance, 'image')


@receiver(post_save, sender=CatalogOptionValue)
def optimize_catalog_option_image(sender, instance, **kwargs):
    if instance.image:
        _enqueue_image_optimization(instance, 'image')


@receiver(post_save, sender=SizeGrid)
def optimize_size_grid_image(sender, instance, **kwargs):
    if instance.image:
        _enqueue_image_optimization(instance, 'image')


@receiver(post_save, sender=PrintProposal)
def optimize_print_proposal_image(sender, instance, **kwargs):
    if instance.image:
        _enqueue_image_optimization(instance, 'image')
