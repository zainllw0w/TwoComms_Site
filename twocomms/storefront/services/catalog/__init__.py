"""
Catalog-related service helpers (authoritative implementation).
"""

from .color_service import (
    ColorDeduplicationResult,
    ensure_color_identity,
    normalize_hex_code,
)
from .media_service import (
    VariantImagePayload,
    append_product_gallery,
    assign_primary_image_from_variants,
    formset_to_variant_payloads,
    sync_variant_images,
)

__all__ = [
    "ColorDeduplicationResult",
    "ensure_color_identity",
    "normalize_hex_code",
    "VariantImagePayload",
    "append_product_gallery",
    "assign_primary_image_from_variants",
    "formset_to_variant_payloads",
    "sync_variant_images",
]

