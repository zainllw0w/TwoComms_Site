"""
Сигналы для автоматического обновления фидов при изменении товаров.

Production-хост не располагает Celery-брокером, поэтому вместо Celery apply_async
мы просто выставляем "dirty" flag в tmp/feeds, а cron периодически запускает
`manage.py regenerate_feeds_if_dirty` с debounce. См. services/feeds_queue.py.
"""
import logging
from django.conf import settings
from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver
from .tasks import generate_google_merchant_feed_task, optimize_image_field_task  # noqa: F401 — kept for backward-compat with tests that patch signals.generate_google_merchant_feed_task

from .models import Category, CategoryColorLanding, Product, ProductImage
from productcolors.models import Color, ProductColorImage, ProductColorVariant
from .services.feeds_queue import mark_feeds_dirty
from .services.indexnow import enqueue_indexnow_urls, get_product_public_url

logger = logging.getLogger(__name__)


def _schedule_marketplace_feed_update(reason: str, *, include_in_tests: bool = False):
    """Mark marketplace feeds as dirty; cron-worker will rebuild (see services/feeds_queue.py)."""
    if getattr(settings, "TESTING", False) and not include_in_tests:
        return

    # Run after commit so we only flag feeds dirty once the data is durable.
    def _on_commit():
        try:
            mark_feeds_dirty(reason=reason)
            logger.debug("feeds marked dirty: %s", reason)
        except Exception as exc:  # pragma: no cover - defensive branch
            logger.error("Failed to mark feeds dirty (%s): %s", reason, exc, exc_info=True)

    try:
        transaction.on_commit(_on_commit)
    except Exception:  # pragma: no cover - no active transaction
        _on_commit()


@receiver(post_save, sender=Product)
def update_google_merchant_feed_on_product_save(sender, instance, created, **kwargs):
    """
    Автоматически обновляет marketplace feeds при создании или обновлении товара.
    Использует debounce (5 минут), чтобы избежать частых перегенераций при массовых изменениях.
    """
    action = "создан" if created else "обновлен"
    _schedule_marketplace_feed_update(f"Товар {instance.title} (ID: {instance.id}) {action}", include_in_tests=True)


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
    Автоматически обновляет marketplace feeds при удалении товара.
    Использует debounce (5 минут).
    """
    _schedule_marketplace_feed_update(f"Товар {instance.title} (ID: {instance.id}) удален", include_in_tests=True)


@receiver([post_save, post_delete], sender=Category)
@receiver([post_save, post_delete], sender=ProductImage)
@receiver([post_save, post_delete], sender=Color)
@receiver([post_save, post_delete], sender=ProductColorVariant)
@receiver([post_save, post_delete], sender=ProductColorImage)
def update_marketplace_feeds_on_related_catalog_change(sender, instance, **kwargs):
    """Regenerate feed snapshots when related catalog data changes."""
    _schedule_marketplace_feed_update(f"Изменены данные фида: {sender.__name__} (ID: {getattr(instance, 'pk', '-')})")


@receiver(post_delete, sender=Product)
def submit_product_to_indexnow_on_delete(sender, instance, **kwargs):
    public_url = get_product_public_url(instance)
    if not public_url:
        return

    transaction.on_commit(lambda: enqueue_indexnow_urls([public_url]))


def _enqueue_image_optimization(instance, field_name: str):
    """Run image optimization inline after commit.

    Production runs without Celery, so attempting ``.delay()`` only adds a
    failed-RPC round-trip before falling back to sync. We schedule the work
    via ``transaction.on_commit`` so request latency is preserved: control
    returns to the user immediately and optimization runs in the same
    worker after the response is flushed but before the transaction is
    recycled.
    """
    image_field = getattr(instance, field_name, None)
    if not image_field:
        return
    if not getattr(instance, 'pk', None):
        return

    label = instance._meta.label
    pk = instance.pk

    def _run():
        try:
            optimize_image_field_task(label, pk, field_name)
        except Exception as inner:  # pragma: no cover - defensive branch
            logger.error(
                "Inline image optimization failed for %s.%s (id=%s): %s",
                label, field_name, pk, inner, exc_info=True,
            )

    try:
        transaction.on_commit(_run)
    except Exception:  # pragma: no cover - no active transaction
        _run()


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


# ===== Auto-resize + WebP intake hook (B22 root) =====
#
# Closes the original-bloat problem at the source: every new upload
# through any of the catalog-image fields is downscaled to 1600x2000
# and re-encoded as WebP *before* the row hits the DB. The legacy
# post_save responsive-variant pipeline above stays in place so the
# storefront still gets `<dir>/optimized/<stem>_<width>w.{webp,avif}`
# siblings for the srcset rendering — image_intake just makes sure
# the **original** that those siblings derive from is already small.
from .services.image_intake import process_image_field as _intake_process

_INTAKE_TARGETS = {
    Product: ("main_image", "home_card_image"),
    ProductImage: ("image",),
    ProductColorImage: ("image",),
    Category: ("cover", "icon"),
    CatalogOptionValue: ("image",),
    SizeGrid: ("image",),
    PrintProposal: ("image",),
}


@receiver(pre_save)
def compress_uploaded_image_originals(sender, instance, raw=False, **kwargs):
    """Pillow-resize + WebP-encode any freshly-uploaded image fields.

    Hooked as a global pre_save with an explicit sender dispatch so we
    do not pay reflection cost on hot non-image models (Order, Cart,
    Session, …). Skips ``raw=True`` saves (fixtures, dumpdata) and
    silently no-ops on DB reads where ``FieldFile.file`` is the on-disk
    handle rather than an incoming upload — see ``_should_process``.
    """
    if raw:
        return
    field_names = _INTAKE_TARGETS.get(sender)
    if not field_names:
        return
    for fname in field_names:
        field = getattr(instance, fname, None)
        if not field:
            continue
        try:
            _intake_process(field)
        except Exception as exc:  # pragma: no cover - defensive branch
            logger.warning(
                "compress_uploaded_image_originals failed on %s.%s (id=%s): %s",
                sender.__name__, fname, getattr(instance, "pk", None), exc,
            )



# ===== Color × Category landing pages — IndexNow =====

@receiver(pre_save, sender=CategoryColorLanding)
def remember_previous_color_landing_state(sender, instance, **kwargs):
    """Capture the previous public URL & published flag before save.

    We need both to (a) ping IndexNow when a landing flips published →
    unpublished (the URL becomes a 404 and Google should drop it) and
    (b) ping when an existing landing's slug or category changes.
    """
    if not instance.pk:
        instance._indexnow_previous_url = None
        instance._indexnow_previously_published = False
        return

    previous = (
        CategoryColorLanding.objects
        .filter(pk=instance.pk)
        .select_related("category")
        .only("color_slug", "is_published", "category__slug")
        .first()
    )
    if previous is None or not previous.category_id or not previous.color_slug:
        instance._indexnow_previous_url = None
        instance._indexnow_previously_published = False
        return

    instance._indexnow_previous_url = (
        f"/catalog/{previous.category.slug}/{previous.color_slug}/"
    )
    instance._indexnow_previously_published = bool(previous.is_published)


@receiver(post_save, sender=CategoryColorLanding)
def submit_color_landing_to_indexnow(sender, instance, **kwargs):
    """Ping IndexNow when a colour-category landing changes visibility.

    Cases:
        * New publication → ping the new URL.
        * URL slug or category changed while published → ping both old
          and new URLs (old becomes 404 → drop from index).
        * Unpublication → ping the old URL so search engines re-crawl.
    """
    previous_url = getattr(instance, "_indexnow_previous_url", None)
    previously_published = getattr(instance, "_indexnow_previously_published", False)

    current_url = ""
    if instance.is_published and instance.category_id and instance.color_slug:
        current_url = f"/catalog/{instance.category.slug}/{instance.color_slug}/"

    urls = []
    if previously_published and previous_url and previous_url != current_url:
        urls.append(previous_url)
    if instance.is_published and current_url:
        urls.append(current_url)
    # Dedupe while preserving order.
    urls = list(dict.fromkeys(u for u in urls if u))
    if not urls:
        return

    transaction.on_commit(lambda: enqueue_indexnow_urls(urls))


@receiver(post_delete, sender=CategoryColorLanding)
def submit_color_landing_to_indexnow_on_delete(sender, instance, **kwargs):
    if not instance.is_published or not instance.category_id or not instance.color_slug:
        return
    try:
        url = f"/catalog/{instance.category.slug}/{instance.color_slug}/"
    except Exception:  # pragma: no cover - defensive
        return
    transaction.on_commit(lambda: enqueue_indexnow_urls([url]))
