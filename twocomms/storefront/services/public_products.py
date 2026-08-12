"""Shared eligibility for public, commerce-bearing product records."""

from __future__ import annotations

from django.db.models import QuerySet

from ..models import Product, ProductStatus


def public_products_queryset() -> QuerySet[Product]:
    """Return products that have a public URL and a usable selling price.

    This is the base-product set shared by public SEO and commerce surfaces.
    Variant/size expansion belongs to the merchant-feed layer and must not be
    performed here.
    """

    return Product.objects.filter(
        status=ProductStatus.PUBLISHED,
        price__gt=0,
    ).exclude(slug="")
