"""Побудова URL'ів для зв'язку основного бота замовлень зі складом."""
from __future__ import annotations

from django.conf import settings

from warehouse.models import WriteOffRequest


def get_storage_base_url() -> str:
    return (
        getattr(settings, "WAREHOUSE_SUBDOMAIN_URL", "https://storage.twocomms.shop")
        or "https://storage.twocomms.shop"
    ).rstrip("/")


def build_storage_writeoff_url(order) -> str:
    """Створює (або повертає існуючий pending) WriteOffRequest та формує URL."""
    pending = order.warehouse_write_off_requests.filter(
        status=WriteOffRequest.STATUS_PENDING
    ).first()
    if pending is None:
        pending = WriteOffRequest.objects.create(order=order)
    return f"{get_storage_base_url()}/order/{pending.token}/write-off/"
