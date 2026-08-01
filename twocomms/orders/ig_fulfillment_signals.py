"""Wake durable Instagram fulfillment after relevant order transitions."""

import logging

from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import Order

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=Order)
def track_instagram_fulfillment_changes(sender, instance, using, **kwargs):
    instance._ig_fulfillment_wakeup = False
    if not instance.pk:
        return
    previous = (
        Order.objects.using(using)
        .filter(pk=instance.pk)
        .values("tracking_number", "status", "shipment_status")
        .first()
    )
    if previous is None:
        return
    instance._ig_fulfillment_wakeup = bool(
        previous["tracking_number"] != instance.tracking_number
        or previous["status"] != instance.status
        or previous["shipment_status"] != instance.shipment_status
    )


@receiver(post_save, sender=Order)
def wake_instagram_fulfillment(sender, instance, created, using, **kwargs):
    if created or not getattr(instance, "_ig_fulfillment_wakeup", False):
        return

    order_id = instance.pk

    def wake():
        try:
            from management.services.ig_order_fulfillment import kick_order_fulfillment

            kick_order_fulfillment(order_id)
        except Exception:
            logger.exception(
                "Could not wake Instagram fulfillment for order %s",
                order_id,
            )

    transaction.on_commit(wake, using=using)
