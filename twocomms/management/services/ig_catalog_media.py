"""Catalog-owned media selection for Instagram product discovery.

The bot should show a small, trusted image set when a customer asks to see
products. This module deliberately returns media only: product URLs stay out
of the payload unless the caller explicitly asks for a link in the text flow.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import json

from django.conf import settings


MAX_CATALOG_MEDIA = 4


class CatalogMediaState(StrEnum):
    READY = "ready"
    PARTIAL = "partial"
    EMPTY = "empty"
    AMBIGUOUS = "ambiguous"


class CatalogMediaDeliveryState(StrEnum):
    SENT = "sent"
    PARTIAL = "partial"
    FAILED = "failed"
    AMBIGUOUS = "ambiguous"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class CatalogMediaItem:
    url: str
    title: str
    alt: str
    product_id: int


@dataclass(frozen=True)
class CatalogMediaSelection:
    state: CatalogMediaState
    items: tuple[CatalogMediaItem, ...] = ()
    requested_product_ids: tuple[int, ...] = ()
    missing_product_ids: tuple[int, ...] = ()


@dataclass(frozen=True)
class CatalogMediaDelivery:
    state: CatalogMediaDeliveryState
    sent_count: int = 0
    attempted_count: int = 0
    provider_message_ids: tuple[str, ...] = ()
    error: str = ""


def _base_url() -> str:
    return (
        str(getattr(settings, "SITE_BASE_URL", "") or "https://twocomms.shop")
        .rstrip("/")
    )


def _absolute_url(value) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if raw.startswith("https://"):
        return raw
    if raw.startswith("http://"):
        return "https://" + raw.split("://", 1)[1]
    return f"{_base_url()}/{raw.lstrip('/')}"


def _image_url(image_field) -> str:
    try:
        return _absolute_url(getattr(image_field, "url", ""))
    except Exception:
        return ""


def _variant_urls(variant) -> list[str]:
    urls: list[str] = []
    images = getattr(variant, "_prefetched_objects_cache", {}).get("images")
    if images is None:
        try:
            images = list(variant.images.order_by("order", "id")[:MAX_CATALOG_MEDIA])
        except Exception:
            images = []
    for image in images:
        url = _image_url(getattr(image, "image", None))
        if url and url not in urls:
            urls.append(url)
    return urls


def _product_urls(product) -> list[str]:
    urls: list[str] = []
    try:
        images = list(product.images.order_by("order", "id")[:MAX_CATALOG_MEDIA])
    except Exception:
        images = []
    for image in images:
        url = _image_url(getattr(image, "image", None))
        if url and url not in urls:
            urls.append(url)
    for field_name in ("main_image", "home_card_image", "display_image"):
        url = _image_url(getattr(product, field_name, None))
        if url and url not in urls:
            urls.append(url)
    return urls


def select_catalog_media(product_ids, *, limit: int = MAX_CATALOG_MEDIA) -> CatalogMediaSelection:
    """Return up to four real images for published products.

    Variant images are preferred and only stocked variants are considered for
    automated discovery. Missing imagery is represented explicitly so callers
    can keep the text response and surface an operator-review state without
    inventing a URL.
    """
    try:
        requested = tuple(dict.fromkeys(int(value) for value in (product_ids or ())))
    except (TypeError, ValueError):
        return CatalogMediaSelection(CatalogMediaState.AMBIGUOUS)
    requested = tuple(value for value in requested if value > 0)
    if not requested:
        return CatalogMediaSelection(CatalogMediaState.EMPTY)
    try:
        from productcolors.models import ProductColorVariant
        from storefront.models import Product, ProductStatus

        products = list(
            Product.objects.filter(pk__in=requested, status=ProductStatus.PUBLISHED)
            .prefetch_related(
                "images",
                "color_variants__images",
                "color_variants__color",
            )
        )
    except Exception:
        return CatalogMediaSelection(CatalogMediaState.AMBIGUOUS, requested_product_ids=requested)

    by_id = {product.pk: product for product in products}
    missing = [product_id for product_id in requested if product_id not in by_id]
    selected: list[CatalogMediaItem] = []
    seen: set[str] = set()
    for product_id in requested:
        product = by_id.get(product_id)
        if product is None:
            continue
        candidates: list[str] = []
        variants = list(
            ProductColorVariant.objects.filter(product_id=product_id, stock__gt=0)
            .prefetch_related("images")
            .order_by("order", "id")
        )
        for variant in variants:
            candidates.extend(_variant_urls(variant))
        if not candidates:
            candidates = _product_urls(product)
        for url in candidates:
            if url in seen:
                continue
            seen.add(url)
            selected.append(
                CatalogMediaItem(
                    url=url,
                    title=str(product.title or "TwoComms")[:200],
                    alt=f"{product.title} — TwoComms"[:240],
                    product_id=product_id,
                )
            )
            if len(selected) >= max(1, min(int(limit), MAX_CATALOG_MEDIA)):
                break
        if len(selected) >= max(1, min(int(limit), MAX_CATALOG_MEDIA)):
            break

    if not selected:
        state = CatalogMediaState.EMPTY
    elif missing:
        state = CatalogMediaState.PARTIAL
    else:
        state = CatalogMediaState.READY
    return CatalogMediaSelection(
        state=state,
        items=tuple(selected),
        requested_product_ids=requested,
        missing_product_ids=tuple(missing),
    )


def parse_product_ids(raw) -> tuple[int, ...] | None:
    """Parse a model ``[SHOW_PRODUCTS:1,2]`` value without accepting junk."""
    if raw in (True, None, ""):
        return None
    if not isinstance(raw, str):
        return None
    values: list[int] = []
    for part in raw.replace(";", ",").split(","):
        try:
            value = int(part.strip())
        except (TypeError, ValueError):
            return None
        if value <= 0 or value in values:
            return None
        values.append(value)
    return tuple(values[:12]) if values else None


def send_catalog_media(
    settings_row,
    recipient_id: str,
    selection: CatalogMediaSelection,
    *,
    permission_boundary_factory=None,
) -> CatalogMediaDelivery:
    """Send selected images and report partial/ambiguous transport honestly."""
    from contextlib import nullcontext

    from management.services.instagram_bot import (
        _provider_account_id,
        _provider_http,
        _provider_message_id,
        _provider_url,
        get_page_token,
    )

    if not selection.items:
        return CatalogMediaDelivery(CatalogMediaDeliveryState.FAILED, error=selection.state)
    account_id = _provider_account_id(settings_row)
    page_token = get_page_token(settings_row)
    if not account_id or not page_token:
        return CatalogMediaDelivery(CatalogMediaDeliveryState.FAILED, error="provider_not_configured")

    sent = 0
    attempted = 0
    message_ids: list[str] = []
    for item in selection.items:
        boundary = permission_boundary_factory() if permission_boundary_factory else nullcontext(True)
        with boundary as allowed:
            if not allowed:
                return CatalogMediaDelivery(
                    CatalogMediaDeliveryState.CANCELLED,
                    sent_count=sent,
                    attempted_count=attempted,
                    provider_message_ids=tuple(message_ids),
                    error="permission_changed",
                )
            attempted += 1
            body = json.dumps(
                {
                    "recipient": {"id": recipient_id},
                    "message": {
                        "attachment": {
                            "type": "image",
                            "payload": {"url": item.url, "is_reusable": True},
                        }
                    },
                }
            ).encode("utf-8")
            try:
                code, response = _provider_http(
                    settings_row,
                    _provider_url(settings_row, f"/{account_id}/messages"),
                    token=page_token,
                    data=body,
                )
            except Exception:
                state = (
                    CatalogMediaDeliveryState.PARTIAL
                    if sent
                    else CatalogMediaDeliveryState.AMBIGUOUS
                )
                return CatalogMediaDelivery(
                    state,
                    sent_count=sent,
                    attempted_count=attempted,
                    provider_message_ids=tuple(message_ids),
                    error="provider_result_unknown",
                )
            if code != 200:
                state = (
                    CatalogMediaDeliveryState.PARTIAL
                    if sent
                    else CatalogMediaDeliveryState.FAILED
                )
                return CatalogMediaDelivery(
                    state,
                    sent_count=sent,
                    attempted_count=attempted,
                    provider_message_ids=tuple(message_ids),
                    error=f"provider_http_{int(code or 0)}",
                )
            sent += 1
            message_id = _provider_message_id(response)
            if message_id:
                message_ids.append(message_id)

    return CatalogMediaDelivery(
        CatalogMediaDeliveryState.SENT,
        sent_count=sent,
        attempted_count=attempted,
        provider_message_ids=tuple(message_ids),
    )
