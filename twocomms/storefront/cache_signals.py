"""
Сигналы инфраструктуры кеша: инвалидация категорий и связанных данных.
"""
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from cache_utils import get_fragment_cache
from .models import Category


@receiver([post_save, post_delete], sender=Category)
def invalidate_category_cache(sender, **kwargs):
    """
    Очищает кэш категорий при изменении/удалении.
    """
    cache_backend = get_fragment_cache()
    cache_backend.delete('categories:ordered')
