"""
Unified media handling for product builder workflows.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional

from django.core.files.uploadedfile import UploadedFile
from django.db import models, transaction

from productcolors.models import ProductColorImage, ProductColorVariant
from storefront.models import Product, ProductImage


@dataclass
class VariantImagePayload:
    """
    Simplified representation of a colour variant image form row.

    Attributes:
        instance: Existing `ProductColorImage` if the row edits one.
        uploaded_file: Uploaded file (new image) or `FieldFile` for existing.
        alt_text: Alt text from the form.
        order: Desired order (may be None).
        delete: Whether the row is marked for deletion.
    """

    instance: Optional[ProductColorImage]
    uploaded_file: Optional[UploadedFile]
    alt_text: str
    order: Optional[int]
    delete: bool = False


def formset_to_variant_payloads(formset) -> List[VariantImagePayload]:
    """
    Convert a bound inline formset into a list of `VariantImagePayload`.

    Skips invalid forms (caller should ensure `formset.is_valid()`).
    """
    payloads: List[VariantImagePayload] = []
    for form in formset.forms:
        cleaned = getattr(form, "cleaned_data", None)
        if cleaned is None:
            continue
        payloads.append(
            VariantImagePayload(
                instance=form.instance if getattr(form.instance, "pk", None) else None,
                uploaded_file=cleaned.get("image") or getattr(form.instance, "image", None),
                alt_text=(cleaned.get("alt_text") or "").strip(),
                order=cleaned.get("order"),
                delete=bool(cleaned.get("DELETE")),
            )
        )
    return payloads


def _normalise_ordered_payloads(
    payloads: Iterable[VariantImagePayload],
) -> List[VariantImagePayload]:
    """
    Apply deterministic ordering to payloads, filling gaps with sequential ints.
    """
    surviving = [payload for payload in payloads if not payload.delete]
    surviving.sort(
        key=lambda payload: (
            payload.order if payload.order is not None else 10_000,
            payload.instance.pk if payload.instance else 10_000,
        )
    )

    ordered: List[VariantImagePayload] = []
    for index, payload in enumerate(surviving):
        payload.order = index
        ordered.append(payload)
    return ordered


@transaction.atomic
def sync_variant_images(
    variant: ProductColorVariant,
    payloads: Iterable[VariantImagePayload],
    *,
    auto_assign_product_main: bool = True,
) -> List[ProductColorImage]:
    """
    Persist colour variant images using unified rules (ordering, clean-up).

    Returns a list of images that remain after synchronisation.
    """
    ordered_payloads = _normalise_ordered_payloads(payloads)
    keep_ids: List[int] = []
    results: List[ProductColorImage] = []

    for payload in ordered_payloads:
        if payload.instance:
            image_obj = payload.instance
        else:
            image_obj = ProductColorImage(variant=variant)

        if payload.uploaded_file:
            image_obj.image = payload.uploaded_file
        elif not getattr(image_obj, "image", None):
            # Skip entries without image data.
            continue

        image_obj.variant = variant
        image_obj.order = payload.order or 0
        image_obj.alt_text = payload.alt_text or image_obj.alt_text or ""
        image_obj.save()
        keep_ids.append(image_obj.pk)
        results.append(image_obj)

    # Remove images not present in the payload.
    if keep_ids:
        variant.images.exclude(pk__in=keep_ids).delete()
    else:
        variant.images.all().delete()

    if auto_assign_product_main:
        assign_primary_image_from_variants(variant.product)

    return results


def assign_primary_image_from_variants(product: Product) -> None:
    """
    Ensure the product has a main image by borrowing the first variant image.
    """
    if product.main_image:
        return
    variant = product.color_variants.order_by("order", "id").first()
    if not variant:
        return
    first_image = variant.images.order_by("order", "id").first()
    if not first_image:
        return
    product.main_image = first_image.image
    product.save(update_fields=["main_image"])


def append_product_gallery(
    product: Product,
    files: Optional[Iterable[UploadedFile]],
) -> List[ProductImage]:
    """
    Append uploaded files to the product gallery (extra images).

    The first uploaded file also becomes the main image if missing.
    """
    created: List[ProductImage] = []
    if not files:
        return created

    next_order = (
        product.images.aggregate(max_order=models.Max("order")).get("max_order") or 0
    )

    for uploaded in files:
        if not uploaded:
            continue
        image_obj = ProductImage.objects.create(
            product=product,
            image=uploaded,
            order=next_order,
        )
        next_order += 1
        created.append(image_obj)

    if created and not product.main_image:
        product.main_image = created[0].image
        product.save(update_fields=["main_image"])

    return created
