"""Signals: автоматичне створення Group 'warehouse_admins' на post_migrate."""
from __future__ import annotations

from django.apps import apps
from django.db.models.signals import post_migrate
from django.dispatch import receiver

from warehouse.permissions import WAREHOUSE_GROUP_NAME


@receiver(post_migrate)
def ensure_warehouse_group(sender, **kwargs):
    """Гарантує наявність групи 'warehouse_admins' у БД."""
    if sender.label != "warehouse":
        return
    try:
        Group = apps.get_model("auth", "Group")
        Group.objects.get_or_create(name=WAREHOUSE_GROUP_NAME)
    except Exception:
        pass
