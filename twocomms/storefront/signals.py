"""
Сигналы для автоматического обновления фидов при изменении товаров
"""
import logging
from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver
from .tasks import generate_google_merchant_feed_task, optimize_image_field_task

from .models import Product
from .services.indexnow import enqueue_indexnow_urls, get_product_public_url

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Product)
def update_google_merchant_feed_on_product_save(sender, instance, created, **kwargs):
    """
    Автоматически обновляет Google Merchant feed при создании или обновлении товара.
    Использует debounce (5 минут), чтобы избежать частых перегенераций при массовых изменениях.
    """
    try:
        from django.core.cache import cache
        LOCK_KEY = 'google_merchant_feed_update_pending'
        LOCK_TIMEOUT = 300  # 5 минут

        if not cache.get(LOCK_KEY):
            # Если обновления еще не запланировано, планируем через 5 минут
            generate_google_merchant_feed_task.apply_async(countdown=300)
            cache.set(LOCK_KEY, True, timeout=LOCK_TIMEOUT)

            action = "создан" if created else "обновлен"
            logger.info(f"Товар {instance.title} (ID: {instance.id}) {action}. Запланировано обновление Google Merchant feed через 5 минут.")
        else:
            logger.debug(f"Обновление Google Merchant feed уже запланировано.")

    except Exception as e:
        logger.error(f"Ошибка при планировании обновления Google Merchant feed: {e}", exc_info=True)


@receiver(pre_save, sender=Product)
def remember_previous_product_public_url(sender, instance, **kwargs):
    if not instance.pk:
        instance._indexnow_previous_public_url = None
        return

    previous = Product.objects.filter(pk=instance.pk).only("slug", "status").first()
    instance._indexnow_previous_public_url = get_product_public_url(previous)


@receiver(post_save, sender=Product)
def submit_product_to_indexnow_on_save(sender, instance, **kwargs):
    previous_url = getattr(instance, "_indexnow_previous_public_url", None)
    current_url = get_product_public_url(instance)
    urls = [url for url in (previous_url, current_url) if url]
    if not urls:
        return

    transaction.on_commit(lambda: enqueue_indexnow_urls(urls))


@receiver(post_delete, sender=Product)
def update_google_merchant_feed_on_product_delete(sender, instance, **kwargs):
    """
    Автоматически обновляет Google Merchant feed при удалении товара.
    Использует debounce (5 минут).
    """
    try:
        from django.core.cache import cache
        LOCK_KEY = 'google_merchant_feed_update_pending'
        LOCK_TIMEOUT = 300  # 5 минут

        if not cache.get(LOCK_KEY):
            generate_google_merchant_feed_task.apply_async(countdown=300)
            cache.set(LOCK_KEY, True, timeout=LOCK_TIMEOUT)

            logger.info(f"Товар {instance.title} (ID: {instance.id}) удален. Запланировано обновление Google Merchant feed через 5 минут.")
        else:
            logger.debug(f"Обновление Google Merchant feed уже запланировано.")

    except Exception as e:
        logger.error(f"Ошибка при планировании обновления Google Merchant feed: {e}", exc_info=True)


@receiver(post_delete, sender=Product)
def submit_product_to_indexnow_on_delete(sender, instance, **kwargs):
    public_url = get_product_public_url(instance)
    if not public_url:
        return

    transaction.on_commit(lambda: enqueue_indexnow_urls([public_url]))


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
from productcolors.models import ProductColorImage


IMAGE_OPTIMIZATION_FIELDS = {
    Product: ("main_image", "home_card_image"),
    ProductImage: ("image",),
    ProductColorImage: ("image",),
    CatalogOptionValue: ("image",),
    SizeGrid: ("image",),
    PrintProposal: ("image",),
}


def _image_field_name(instance, field_name: str) -> str:
    image_field = getattr(instance, field_name, None)
    return getattr(image_field, "name", "") or ""


@receiver(pre_save)
def remember_previous_image_field_names(sender, instance, raw=False, update_fields=None, **kwargs):
    field_names = IMAGE_OPTIMIZATION_FIELDS.get(sender)
    if raw or not field_names:
        return

    if update_fields is not None:
        update_fields = set(update_fields)
        field_names = tuple(field for field in field_names if field in update_fields)
        if not field_names:
            instance._twc_changed_image_fields = set()
            return

    if not getattr(instance, "pk", None):
        instance._twc_changed_image_fields = {
            field for field in field_names if _image_field_name(instance, field)
        }
        return

    previous = sender.objects.filter(pk=instance.pk).only(*field_names).first()
    if previous is None:
        instance._twc_changed_image_fields = {
            field for field in field_names if _image_field_name(instance, field)
        }
        return

    instance._twc_changed_image_fields = {
        field
        for field in field_names
        if _image_field_name(previous, field) != _image_field_name(instance, field)
    }


def _should_enqueue_image_optimization(instance, field_name: str, created=False, update_fields=None) -> bool:
    if not _image_field_name(instance, field_name):
        return False
    if update_fields is not None and field_name not in set(update_fields):
        return False
    if created:
        return True

    changed_fields = getattr(instance, "_twc_changed_image_fields", None)
    if changed_fields is not None:
        return field_name in changed_fields
    return True


@receiver(post_save, sender=Product)
def optimize_product_main_image(sender, instance, created=False, update_fields=None, **kwargs):
    if _should_enqueue_image_optimization(instance, "main_image", created=created, update_fields=update_fields):
        _enqueue_image_optimization(instance, 'main_image')
    if _should_enqueue_image_optimization(instance, "home_card_image", created=created, update_fields=update_fields):
        _enqueue_image_optimization(instance, 'home_card_image')


@receiver(post_save, sender=ProductImage)
def optimize_product_extra_image(sender, instance, created=False, update_fields=None, **kwargs):
    if _should_enqueue_image_optimization(instance, "image", created=created, update_fields=update_fields):
        _enqueue_image_optimization(instance, 'image')


@receiver(post_save, sender=ProductColorImage)
def optimize_product_color_image(sender, instance, created=False, update_fields=None, **kwargs):
    if _should_enqueue_image_optimization(instance, "image", created=created, update_fields=update_fields):
        _enqueue_image_optimization(instance, 'image')


@receiver(post_save, sender=CatalogOptionValue)
def optimize_catalog_option_image(sender, instance, created=False, update_fields=None, **kwargs):
    if _should_enqueue_image_optimization(instance, "image", created=created, update_fields=update_fields):
        _enqueue_image_optimization(instance, 'image')


@receiver(post_save, sender=SizeGrid)
def optimize_size_grid_image(sender, instance, created=False, update_fields=None, **kwargs):
    if _should_enqueue_image_optimization(instance, "image", created=created, update_fields=update_fields):
        _enqueue_image_optimization(instance, 'image')


@receiver(post_save, sender=PrintProposal)
def optimize_print_proposal_image(sender, instance, created=False, update_fields=None, **kwargs):
    if _should_enqueue_image_optimization(instance, "image", created=created, update_fields=update_fields):
        _enqueue_image_optimization(instance, 'image')
