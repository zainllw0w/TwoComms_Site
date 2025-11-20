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
















# ===== Image Optimization Signals =====

from pathlib import Path
from PIL import Image
import io
from django.core.files.base import ContentFile
from .models import ProductImage, CatalogOptionValue, SizeGrid, PrintProposal
from productcolors.models import ProductColorImage, ProductColorVariant

def generate_optimized_images(image_field, delete_original=False):
    """
    Генерирует WebP и AVIF версии изображения.
    """
    if not image_field:
        return

    try:
        path = Path(image_field.path)
        if not path.exists():
            return

        # Создаем папку optimized если её нет
        optimized_dir = path.parent / "optimized"
        optimized_dir.mkdir(exist_ok=True)

        # Базовое имя файла
        base_name = path.stem

        # Открываем изображение
        with Image.open(path) as img:
            # Конвертируем в RGB если нужно (для JPEG/WebP без прозрачности)
            if img.mode in ('RGBA', 'LA') and path.suffix.lower() in ('.jpg', '.jpeg'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[-1])
                img_to_save = background
            else:
                img_to_save = img

            # Генерируем WebP
            webp_path = optimized_dir / f"{base_name}.webp"
            if not webp_path.exists():
                img_to_save.save(webp_path, format='WEBP', quality=85, method=6)
                logger.info(f"Generated WebP for {path.name}")

            # Генерируем AVIF (если поддерживается)
            avif_path = optimized_dir / f"{base_name}.avif"
            if not avif_path.exists():
                try:
                    img_to_save.save(avif_path, format='AVIF', quality=85)
                    logger.info(f"Generated AVIF for {path.name}")
                except Exception:
                    # AVIF может не поддерживаться установленной версией Pillow/libavif
                    pass
            
            # Генерируем ресайзы для адаптивности (только WebP для экономии места)
            sizes = [320, 480, 640, 768, 960, 1280, 1600, 1920]
            for size in sizes:
                if img.width > size:
                    resize_path = optimized_dir / f"{base_name}_{size}w.webp"
                    if not resize_path.exists():
                        # Вычисляем высоту сохраняя пропорции
                        height = int((size / img.width) * img.height)
                        resized_img = img_to_save.resize((size, height), Image.Resampling.LANCZOS)
                        resized_img.save(resize_path, format='WEBP', quality=80, method=4)
                        
                    # Также генерируем AVIF ресайзы если возможно
                    resize_path_avif = optimized_dir / f"{base_name}_{size}w.avif"
                    if not resize_path_avif.exists():
                        try:
                            # Повторно не ресайзим, если уже есть resized_img, но тут проще заново или сохранить предыдущий
                            # Для простоты ресайзим заново или используем тот же объект если он в памяти
                            # Но так как мы в цикле, лучше просто ресайзить
                            height = int((size / img.width) * img.height)
                            resized_img = img_to_save.resize((size, height), Image.Resampling.LANCZOS)
                            resized_img.save(resize_path_avif, format='AVIF', quality=80)
                        except Exception:
                            pass

    except Exception as e:
        logger.error(f"Error optimizing image {image_field}: {e}")

@receiver(post_save, sender=Product)
def optimize_product_main_image(sender, instance, **kwargs):
    if instance.main_image:
        generate_optimized_images(instance.main_image)

@receiver(post_save, sender=ProductImage)
def optimize_product_extra_image(sender, instance, **kwargs):
    if instance.image:
        generate_optimized_images(instance.image)

@receiver(post_save, sender=ProductColorImage)
def optimize_product_color_image(sender, instance, **kwargs):
    if instance.image:
        generate_optimized_images(instance.image)

@receiver(post_save, sender=CatalogOptionValue)
def optimize_catalog_option_image(sender, instance, **kwargs):
    if instance.image:
        generate_optimized_images(instance.image)

@receiver(post_save, sender=SizeGrid)
def optimize_size_grid_image(sender, instance, **kwargs):
    if instance.image:
        generate_optimized_images(instance.image)

@receiver(post_save, sender=PrintProposal)
def optimize_print_proposal_image(sender, instance, **kwargs):
    if instance.image:
        generate_optimized_images(instance.image)
