"""
Phase 22b — Indexing target builder.

Single source of truth for "every URL on twocomms.shop that is allowed
into the search index". Used by:

* The admin "submit to Google / IndexNow" buttons — so the operator
  can pick groups and languages and get the exact same URL list that
  appears in the sitemap.
* The IndexNow / Google Indexing background pingers — they used to
  have their own narrow definition of "core URLs"; this module lets
  them share the canonical taxonomy.

Design principles:

1. **Mirror the sitemap.** If a URL appears in ``sitemap-*.xml`` it is
   indexable; if it does not, we never ping it. That keeps "what we
   submit" and "what we tell Google to crawl" in lock-step.
2. **Group by intent.** Groups (``static`` / ``products`` /
   ``categories`` / ``product_variants`` / ``color_landings``) match
   the sitemap sections so the admin UI can offer the same toggles.
3. **Language-aware.** Each grouping function accepts a ``languages``
   set; the resulting URLs are prefixed with ``/<lang>/`` for non-default
   languages (UK is the default and stays prefix-free, mirroring
   ``i18n_patterns(prefix_default_language=False)``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from django.conf import settings
from django.urls import reverse
from django.utils import translation
from django.utils import timezone

from .indexnow import build_absolute_url, get_site_base_url


GROUP_STATIC = "static"
GROUP_PRODUCTS = "products"
GROUP_CATEGORIES = "categories"
GROUP_PRODUCT_VARIANTS = "product_variants"
GROUP_COLOR_LANDINGS = "color_landings"
GROUP_BLOG = "blog"

ALL_GROUPS = (
    GROUP_STATIC,
    GROUP_PRODUCTS,
    GROUP_CATEGORIES,
    GROUP_PRODUCT_VARIANTS,
    GROUP_COLOR_LANDINGS,
    GROUP_BLOG,
)

GROUP_LABELS = {
    GROUP_STATIC: "Статичні сторінки",
    GROUP_PRODUCTS: "Товари (PDP)",
    GROUP_CATEGORIES: "Категорії",
    GROUP_PRODUCT_VARIANTS: "Варіанти товарів (колір/крій)",
    GROUP_COLOR_LANDINGS: "Color × Category лендинги",
    GROUP_BLOG: "Новини та блог",
}


def get_default_language() -> str:
    """Return the default language code (UK in our setup)."""
    return getattr(settings, "LANGUAGE_CODE", "uk").split("-")[0].lower()


def get_supported_languages() -> list[str]:
    """Return the language codes we ship translations for."""
    raw = getattr(settings, "LANGUAGES", []) or []
    out = []
    for entry in raw:
        if isinstance(entry, (list, tuple)) and entry:
            code = str(entry[0]).split("-")[0].lower()
            if code and code not in out:
                out.append(code)
    if not out:
        out = ["uk"]
    return out


def build_lang_prefix(lang: str) -> str:
    """Return ``""`` for the default language and ``"/<code>"`` otherwise.

    Mirrors Django's ``i18n_patterns(prefix_default_language=False)``.
    """
    code = (lang or "").strip().lower()
    if not code or code == get_default_language():
        return ""
    return f"/{code}"


# ---------------------------------------------------------------------------
# Static pages
# ---------------------------------------------------------------------------

# Mirrors PUBLIC_STATIC_ROUTE_NAMES in storefront/sitemaps.py. Kept in
# sync manually because importing the sitemap module here would create
# a circular import via Sitemap → models → signals → google_indexing.
PUBLIC_STATIC_ROUTE_NAMES = (
    "home",
    "catalog",
    "delivery",
    "about",
    "contacts",
    "cooperation",
    "custom_print",
    "wholesale_page",
    "help_center",
    "faq",
    "size_guide",
    "care_guide",
    "order_tracking",
    "site_map_page",
    "blog",
    "returns",
    "privacy_policy",
    "terms_of_service",
)


def build_static_urls(languages: Iterable[str]) -> list[str]:
    out: list[str] = []
    for lang in languages:
        prefix = build_lang_prefix(lang)
        # ``reverse`` picks the URL based on the current activate()
        # locale only when the URLConf does locale-aware routing.
        # Since our routes use ``i18n_patterns(prefix_default_language=False)``
        # the path itself is identical in UA/RU/EN; only the prefix
        # differs. We therefore ``activate(default)`` once and prepend
        # the prefix manually — much faster than activating per URL.
        with translation.override(get_default_language()):
            for route in PUBLIC_STATIC_ROUTE_NAMES:
                try:
                    path = reverse(route)
                except Exception:
                    continue
                if not path:
                    continue
                # ``reverse`` strips the language prefix when locale==default,
                # so we can safely prepend our own.
                if not path.startswith("/"):
                    path = "/" + path
                out.append(build_absolute_url(f"{prefix}{path}"))
    return _dedupe(out)


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------

def build_product_urls(languages: Iterable[str]) -> list[str]:
    from ..models import Product

    slugs = list(
        Product.objects
        .filter(status="published")
        .exclude(slug="")
        .values_list("slug", flat=True)
    )
    out: list[str] = []
    for lang in languages:
        prefix = build_lang_prefix(lang)
        for slug in slugs:
            out.append(build_absolute_url(f"{prefix}/product/{slug}/"))
    return _dedupe(out)


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------

def build_category_urls(languages: Iterable[str]) -> list[str]:
    from ..models import Category

    slugs = list(
        Category.objects
        .filter(is_active=True)
        .exclude(slug="")
        .values_list("slug", flat=True)
    )
    out: list[str] = []
    for lang in languages:
        prefix = build_lang_prefix(lang)
        for slug in slugs:
            out.append(build_absolute_url(f"{prefix}/catalog/{slug}/"))
    return _dedupe(out)


# ---------------------------------------------------------------------------
# Product variants (one-segment colour / fit URLs)
# ---------------------------------------------------------------------------

def build_product_variant_urls(languages: Iterable[str]) -> list[str]:
    """Mirror ``ProductVariantSitemap``: ``/product/<slug>/<colour-or-fit>/``.

    Sitemap currently emits these without alternates because the page
    is the same colour-only filter on a PDP, but if the operator opts
    in to multilingual indexing we still produce the localised
    versions — Google merges them based on hreflang on the underlying
    PDP.
    """
    from ..models import Product

    products = (
        Product.objects
        .filter(status="published")
        .exclude(slug="")
        .prefetch_related("color_variants", "fit_options")
        .only("id", "slug")
    )

    pairs: list[tuple[str, str]] = []
    for product in products:
        for cv in product.color_variants.all():
            slug = (cv.slug or "").strip()
            if slug:
                pairs.append((product.slug, slug))
        for fit in product.fit_options.all():
            if getattr(fit, "is_active", True) and getattr(fit, "code", ""):
                pairs.append((product.slug, fit.code))

    out: list[str] = []
    for lang in languages:
        prefix = build_lang_prefix(lang)
        for product_slug, leaf in pairs:
            out.append(
                build_absolute_url(f"{prefix}/product/{product_slug}/{leaf}/")
            )
    return _dedupe(out)


# ---------------------------------------------------------------------------
# Color × category landings
# ---------------------------------------------------------------------------

def build_color_landing_urls(languages: Iterable[str]) -> list[str]:
    try:
        from ..models import CategoryColorLanding
    except Exception:
        return []
    pairs = list(
        CategoryColorLanding.objects
        .filter(is_published=True)
        .select_related("category")
        .values_list("category__slug", "color_slug")
    )
    out: list[str] = []
    for lang in languages:
        prefix = build_lang_prefix(lang)
        for cat_slug, color_slug in pairs:
            if not (cat_slug and color_slug):
                continue
            out.append(
                build_absolute_url(f"{prefix}/catalog/{cat_slug}/{color_slug}/")
            )
    return _dedupe(out)


# ---------------------------------------------------------------------------
# Blog
# ---------------------------------------------------------------------------

def build_blog_urls(languages: Iterable[str]) -> list[str]:
    from ..models import BlogCategory, BlogPost

    categories = list(
        BlogCategory.objects
        .filter(is_active=True)
        .exclude(slug="")
        .select_related("parent")
        .only("slug", "parent", "parent__slug")
    )
    post_slugs = list(
        BlogPost.objects
        .filter(is_published=True, published_at__lte=timezone.now())
        .exclude(slug="")
        .values_list("slug", flat=True)
    )

    out: list[str] = []
    for lang in languages:
        prefix = build_lang_prefix(lang)
        out.append(build_absolute_url(f"{prefix}/blog/"))
        for category in categories:
            if category.parent_id and category.parent:
                path = f"/blog/category/{category.parent.slug}/{category.slug}/"
            else:
                path = f"/blog/category/{category.slug}/"
            out.append(build_absolute_url(f"{prefix}{path}"))
        for slug in post_slugs:
            out.append(build_absolute_url(f"{prefix}/blog/{slug}/"))
    return _dedupe(out)


# ---------------------------------------------------------------------------
# Aggregator
# ---------------------------------------------------------------------------

GROUP_BUILDERS = {
    GROUP_STATIC: build_static_urls,
    GROUP_PRODUCTS: build_product_urls,
    GROUP_CATEGORIES: build_category_urls,
    GROUP_PRODUCT_VARIANTS: build_product_variant_urls,
    GROUP_COLOR_LANDINGS: build_color_landing_urls,
    GROUP_BLOG: build_blog_urls,
}


@dataclass
class TargetSnapshot:
    """A grouped list of indexable URLs.

    ``per_group`` keeps the per-section breakdown so the admin UI can
    show "Static: 54, Products: 195, …" without re-running the queries.
    """

    languages: list[str]
    groups: list[str]
    per_group: dict[str, list[str]] = field(default_factory=dict)

    @property
    def all_urls(self) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for group in self.groups:
            for url in self.per_group.get(group, []):
                if url not in seen:
                    seen.add(url)
                    out.append(url)
        return out

    @property
    def total(self) -> int:
        return len(self.all_urls)

    def to_dict(self, *, preview_limit: int = 25) -> dict:
        return {
            "languages": self.languages,
            "groups": self.groups,
            "totals_by_group": {g: len(self.per_group.get(g, [])) for g in self.groups},
            "total": self.total,
            "preview": self.all_urls[:preview_limit],
        }


def build_targets(
    *,
    groups: Iterable[str] | None = None,
    languages: Iterable[str] | None = None,
) -> TargetSnapshot:
    """Build a snapshot of every indexable URL for the chosen filter.

    ``groups=None`` defaults to all known groups; ``languages=None``
    defaults to ``settings.LANGUAGES``.
    """
    chosen_groups = [g for g in (groups or ALL_GROUPS) if g in GROUP_BUILDERS]
    chosen_languages = []
    seen_lang: set[str] = set()
    for raw in languages or get_supported_languages():
        code = str(raw or "").strip().lower()
        if code and code not in seen_lang:
            seen_lang.add(code)
            chosen_languages.append(code)
    if not chosen_languages:
        chosen_languages = [get_default_language()]

    snapshot = TargetSnapshot(
        languages=chosen_languages,
        groups=chosen_groups,
    )
    for group in chosen_groups:
        builder = GROUP_BUILDERS.get(group)
        if not builder:
            continue
        try:
            urls = builder(chosen_languages)
        except Exception:
            urls = []
        snapshot.per_group[group] = _dedupe(urls)
    return snapshot


def _dedupe(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


__all__ = [
    "GROUP_STATIC",
    "GROUP_PRODUCTS",
    "GROUP_CATEGORIES",
    "GROUP_PRODUCT_VARIANTS",
    "GROUP_COLOR_LANDINGS",
    "GROUP_BLOG",
    "ALL_GROUPS",
    "GROUP_LABELS",
    "TargetSnapshot",
    "build_targets",
    "build_static_urls",
    "build_product_urls",
    "build_category_urls",
    "build_product_variant_urls",
    "build_color_landing_urls",
    "build_blog_urls",
    "get_supported_languages",
    "get_default_language",
]
