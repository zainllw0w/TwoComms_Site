"""Evidence-bound Nova Poshta delivery state for Instagram deals."""

from __future__ import annotations

from django.utils import timezone


DELIVERY_SOURCE_DIRECTORY = "nova_poshta_directory"


def delivery_refs_present(deal) -> bool:
    return all(
        str(getattr(deal, field, "") or "").strip()
        for field in ("np_settlement_ref", "np_city_ref", "np_warehouse_ref")
    )


def has_validated_delivery(deal) -> bool:
    return (
        getattr(deal, "delivery_status", "") == deal.DeliveryStatus.VALIDATED
        and delivery_refs_present(deal)
        and str(getattr(deal, "delivery_source", "") or "").strip()
        == DELIVERY_SOURCE_DIRECTORY
    )


def delivery_validation_error(deal) -> str:
    if not delivery_refs_present(deal):
        return "Потрібні підтверджені Ref міста та відділення Нової Пошти."
    if getattr(deal, "delivery_status", "") != deal.DeliveryStatus.VALIDATED:
        return "Вибір доставки ще не підтверджено довідником Нової Пошти."
    if str(getattr(deal, "delivery_source", "") or "").strip() != DELIVERY_SOURCE_DIRECTORY:
        return "Джерело вибору доставки не підтверджене довідником Нової Пошти."
    return ""


def apply_directory_selection(deal, selection, *, source: str = DELIVERY_SOURCE_DIRECTORY):
    """Persist a signed ``NovaPoshtaDeliverySelection`` on an IG deal."""
    deal.np_city = str(selection.city or "")[:160]
    deal.np_office = str(selection.np_office or "")[:255]
    deal.np_settlement_ref = str(selection.settlement_ref or "")[:36]
    deal.np_city_ref = str(selection.city_ref or "")[:36]
    deal.np_warehouse_ref = str(selection.warehouse_ref or "")[:36]
    deal.np_warehouse_kind = str(selection.warehouse_kind or "branch")[:16]
    deal.delivery_status = deal.DeliveryStatus.VALIDATED
    deal.delivery_source = str(source or DELIVERY_SOURCE_DIRECTORY)[:32]
    deal.delivery_error = ""
    deal.delivery_verified_at = timezone.now()
    return deal
