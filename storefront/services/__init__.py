"""
High-level service utilities for the storefront app.

This namespace collects cohesive service modules that encapsulate business
logic for the product catalog, colour management, media handling, etc.
"""

from . import product_builder  # noqa: F401
from .catalog import (  # noqa: F401
    ColorDeduplicationResult,
    VariantImagePayload,
    append_product_gallery,
    assign_primary_image_from_variants,
    ensure_color_identity,
    formset_to_variant_payloads,
    normalize_hex_code,
    sync_variant_images,
)

__all__ = [
    "product_builder",
    "ColorDeduplicationResult",
    "VariantImagePayload",
    "append_product_gallery",
    "assign_primary_image_from_variants",
    "ensure_color_identity",
    "formset_to_variant_payloads",
    "normalize_hex_code",
    "sync_variant_images",
]

