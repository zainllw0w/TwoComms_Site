"""
Phase 11 — SEO admin dashboard context builders.

Provides three slices of data for ``?section=seo`` of the custom admin
panel:

* ``sitemap_summary`` — number of URLs in each sub-sitemap registered in
  ``twocomms/urls.py`` (static / products / product variants / categories
  / images).
* ``ai_panel`` — products and categories that opted into AI generation
  (``ai_generation_enabled=True``), their last generation status, and a
  flag whether the OpenAI integration is actually wired (settings + key).
* ``seo_blocks_summary`` — Phase 10 ``CategorySeoBlock`` counts per
  category, used to nudge content managers towards categories that still
  have no enriched SEO blocks.

Pure functions, no I/O outside of ORM queries.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List

from django.conf import settings
from django.db.models import Count, Q


def _has_openai_api_key() -> bool:
    return bool(
        getattr(settings, "OPENAI_API_KEY", None)
        or os.environ.get("OPENAI_API_KEY")
    )


def build_sitemap_summary() -> List[Dict[str, Any]]:
    """Return per-section URL counts for the sitemap-index."""
    from ..models import Category, Product
    from ..sitemaps import (
        ProductVariantSitemap,
        StaticViewSitemap,
    )

    static_count = len(StaticViewSitemap().items())
    products_count = Product.objects.filter(status="published").count()
    categories_count = Category.objects.filter(is_active=True).count()

    # Variant sitemap items() is computed (not a queryset). Materialise once.
    try:
        variants_count = len(list(ProductVariantSitemap().items()))
    except Exception:
        # Defensive: never let dashboard break if variant aggregation
        # raises (e.g. broken size context).
        variants_count = 0

    images_count = (
        Product.objects
        .filter(status="published")
        .filter(Q(main_image__isnull=False) & ~Q(main_image=""))
        .count()
    )

    sections = [
        {"key": "static", "label": "Статичні сторінки",
         "url": "/sitemap-static.xml", "count": static_count},
        {"key": "products", "label": "Товари",
         "url": "/sitemap-products.xml", "count": products_count},
        {"key": "variants", "label": "Варіанти товарів (Phase 7.4)",
         "url": "/sitemap-product-variants.xml", "count": variants_count},
        {"key": "categories", "label": "Категорії",
         "url": "/sitemap-categories.xml", "count": categories_count},
        {"key": "images", "label": "Зображення (Image Sitemap)",
         "url": "/sitemap-images.xml", "count": images_count},
    ]
    total = sum(s["count"] for s in sections)
    sections.append({
        "key": "total", "label": "Всього URL", "url": "/sitemap.xml",
        "count": total, "is_total": True,
    })
    return sections


def build_ai_panel() -> Dict[str, Any]:
    """Return AI generation status and opt-in objects."""
    from ..models import Category, Product

    ai_products = list(
        Product.objects
        .filter(ai_generation_enabled=True)
        .only("id", "title", "slug", "status",
              "ai_content_generated", "updated_at")
        .order_by("-updated_at")[:50]
    )
    ai_categories = list(
        Category.objects
        .filter(ai_generation_enabled=True)
        .only("id", "name", "slug", "is_active",
              "ai_content_generated", "updated_at")
        .order_by("-updated_at")[:50]
    )

    return {
        "ai_products": ai_products,
        "ai_categories": ai_categories,
        "ai_settings": {
            "use_keywords": bool(getattr(settings, "USE_AI_KEYWORDS", False)),
            "use_descriptions": bool(getattr(settings, "USE_AI_DESCRIPTIONS", False)),
            "has_api_key": _has_openai_api_key(),
            "auto_on_create": bool(getattr(
                settings, "AUTO_GENERATE_AI_CONTENT_ON_CREATE", False
            )),
        },
        "ai_counts": {
            "products_total": Product.objects.filter(ai_generation_enabled=True).count(),
            "products_generated": Product.objects.filter(
                ai_generation_enabled=True, ai_content_generated=True
            ).count(),
            "categories_total": Category.objects.filter(ai_generation_enabled=True).count(),
            "categories_generated": Category.objects.filter(
                ai_generation_enabled=True, ai_content_generated=True
            ).count(),
        },
    }


def build_seo_blocks_summary(limit: int = 20) -> List[Dict[str, Any]]:
    """Per-category Phase 10 SEO block counts (active categories only)."""
    from ..models import Category

    rows = (
        Category.objects.filter(is_active=True)
        .annotate(
            blocks_total=Count("seo_blocks"),
            blocks_active=Count(
                "seo_blocks", filter=Q(seo_blocks__is_active=True)
            ),
        )
        .order_by("-blocks_active", "order", "name")
        .values("id", "name", "slug", "seo_text_title",
                "blocks_total", "blocks_active")
    )
    return list(rows[:limit])


def build_seo_dashboard_context() -> Dict[str, Any]:
    """Top-level helper used by the ``?section=seo`` admin view."""
    return {
        "sitemap_summary": build_sitemap_summary(),
        "ai_panel": build_ai_panel(),
        "seo_blocks_summary": build_seo_blocks_summary(),
    }
