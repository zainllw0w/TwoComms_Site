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


def build_color_seo_overrides_summary(limit: int = 50) -> Dict[str, Any]:
    """Phase 19h — colour-aware SEO copy override summary.

    Returns active overrides + counts by scope so the SEO dashboard
    can surface "X overrides active" with deep links into the Django
    admin changelist for editing.
    """
    try:
        from ..models import CatalogColorSeoOverride, Category
    except Exception:
        return {"rows": [], "counts": {}, "categories_with_swatches": []}

    try:
        rows_qs = (
            CatalogColorSeoOverride.objects
            .select_related("category")
            .order_by("scope", "color_slug", "category__order")[:limit]
        )
        rows = [
            {
                "id": row.id,
                "scope": row.scope,
                "scope_label": row.get_scope_display(),
                "color_slug": row.color_slug,
                "category_name": row.category.name if row.category_id else "",
                "category_slug": row.category.slug if row.category_id else "",
                "h2": (row.h2 or "")[:80],
                "is_active": row.is_active,
                "has_body": bool(row.body_html),
                "has_queries": bool(row.queries_json),
                "updated_at": row.updated_at,
            }
            for row in rows_qs
        ]
        counts = {
            "total": CatalogColorSeoOverride.objects.count(),
            "active": CatalogColorSeoOverride.objects.filter(is_active=True).count(),
            "general": CatalogColorSeoOverride.objects.filter(scope="general").count(),
            "brand": CatalogColorSeoOverride.objects.filter(scope="brand").count(),
            "category": CatalogColorSeoOverride.objects.filter(scope="category").count(),
        }
        categories_with_swatches = list(
            Category.objects.filter(is_active=True)
            .exclude(showcase_swatch_hexes=[])
            .values("id", "name", "slug", "showcase_swatch_hexes")
        )
    except Exception:
        return {"rows": [], "counts": {}, "categories_with_swatches": []}

    return {
        "rows": rows,
        "counts": counts,
        "categories_with_swatches": categories_with_swatches,
    }


def build_category_seo_overrides() -> List[Dict[str, Any]]:
    """Phase 21 (PR-A2) — list of categories with their manual SEO
    override fields exposed for inline editing in the custom admin's
    SEO section. Returns dicts (not models) so the template stays
    decoupled and so we can pre-compute fallback hints.
    """
    from ..models import Category

    rows = []
    for cat in (
        Category.objects
        .filter(is_active=True)
        .order_by("order", "name")
        .only(
            "id", "name", "slug",
            "seo_title", "seo_h1", "seo_description",
        )
    ):
        rows.append({
            "id": cat.id,
            "name": cat.name,
            "slug": cat.slug,
            "seo_title": cat.seo_title or "",
            "seo_h1": cat.seo_h1 or "",
            "seo_description": cat.seo_description or "",
            # Fallback strings shown as placeholders so the editor sees
            # what the page renders when the override is empty.
            "fallback_title": f"{cat.name} — TwoComms",
            "fallback_h1": cat.name,
            "fallback_description": (
                f"Купити {cat.name.lower()} в TwoComms. Якісний стріт & "
                "мілітарі одяг з ексклюзивним дизайном і швидкою доставкою "
                "по Україні."
            ),
            "public_url": f"/catalog/{cat.slug}/",
        })
    return rows


def build_seo_dashboard_context() -> Dict[str, Any]:
    """Top-level helper used by the ``?section=seo`` admin view."""
    return {
        "sitemap_summary": build_sitemap_summary(),
        "ai_panel": build_ai_panel(),
        "seo_blocks_summary": build_seo_blocks_summary(),
        "color_seo_overrides": build_color_seo_overrides_summary(),
        # Phase 21 (PR-A2) — inline editor for category seo_title /
        # seo_h1 / seo_description right inside the custom admin.
        "category_seo_overrides": build_category_seo_overrides(),
    }
