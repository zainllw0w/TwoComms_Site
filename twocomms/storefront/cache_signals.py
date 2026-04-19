"""
Сигналы инфраструктуры кеша: инвалидация категорий и связанных данных.
"""
from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from cache_utils import get_fragment_cache
from .models import Category
from .services.indexnow import enqueue_indexnow_urls, get_category_public_url


@receiver(pre_save, sender=Category)
def remember_previous_category_public_url(sender, instance, **kwargs):
    if not instance.pk:
        instance._indexnow_previous_public_url = None
        return

    previous = Category.objects.filter(pk=instance.pk).only("slug", "is_active").first()
    instance._indexnow_previous_public_url = get_category_public_url(previous)


@receiver([post_save, post_delete], sender=Category)
def invalidate_category_cache(sender, **kwargs):
    """
    Очищает кэш категорий при изменении/удалении.
    """
    cache_backend = get_fragment_cache()
    cache_backend.delete('categories:ordered')


@receiver(post_save, sender=Category)
def submit_category_to_indexnow_on_save(sender, instance, **kwargs):
    previous_url = getattr(instance, "_indexnow_previous_public_url", None)
    current_url = get_category_public_url(instance)
    urls = [url for url in (previous_url, current_url) if url]
    if not urls:
        return

    transaction.on_commit(lambda: enqueue_indexnow_urls(urls))


@receiver(post_delete, sender=Category)
def submit_category_to_indexnow_on_delete(sender, instance, **kwargs):
    public_url = get_category_public_url(instance)
    if not public_url:
        return

    transaction.on_commit(lambda: enqueue_indexnow_urls([public_url]))
