"""Locale publication eligibility for standard storefront products.

Modeltranslation properties intentionally fall back to Ukrainian.  That is
useful for the customer-facing language switcher, but it cannot decide
whether a RU/EN URL is an indexable locale owner.  This module reads the raw
translated columns and keeps the publication policy in one place for PDPs,
hreflang and sitemaps.
"""

from __future__ import annotations

SUPPORTED_LOCALES = ("uk", "ru", "en")

# These fields are visible or feed the primary product metadata.  A locale
# needs an owned title, SEO title/description and at least one owned
# editorial/product description before it can become an indexable owner.
_EDITORIAL_FIELDS = (
    "full_description",
    "description",
    "short_description",
    "target_audience",
    "care_instructions",
    "seo_bottom_html",
)

PRODUCT_SITEMAP_FIELDS = (
    "id",
    "slug",
    "updated_at",
    "published_at",
    *(
        f"{field}_{locale}"
        for field in ("title", "seo_title", "seo_description", *_EDITORIAL_FIELDS)
        for locale in ("ru", "en")
    ),
)


def _raw_value(instance, field: str, locale: str) -> str:
    """Read a modeltranslation column without invoking fallback logic."""

    locale = (locale or "uk").split("-", 1)[0].lower()
    if locale == "uk":
        # The canonical Ukrainian column is populated by the existing base
        # field on older rows, so accept it as the UK owner.
        candidates = (f"{field}_uk", field)
    else:
        candidates = (f"{field}_{locale}",)
    for candidate in candidates:
        value = instance.__dict__.get(candidate)
        if value is None:
            try:
                value = getattr(instance, candidate)
            except AttributeError:
                value = ""
        if str(value or "").strip():
            return str(value).strip()
    return ""


def _localized_faqs(product, locale: str) -> bool:
    """Return whether every active FAQ pair has an owned translation.

    Empty FAQ sets are valid: the PDP does not render a FAQ block in that
    case.  A partially translated set is not an indexable locale owner.
    """

    try:
        rows = product.faqs.all()
    except Exception:
        # Fail closed if the relation cannot be checked. A transient data
        # error must not turn a fallback-language page into an owner.
        return False
    for row in rows:
        if not getattr(row, "is_active", True):
            continue
        if not _raw_value(row, "question", locale):
            return False
        if not _raw_value(row, "answer", locale):
            return False
    return True


def locale_is_indexable(product, locale: str) -> bool:
    """Whether ``product`` owns enough content for ``locale`` indexing."""

    locale = (locale or "uk").split("-", 1)[0].lower()
    if locale not in SUPPORTED_LOCALES:
        return False
    if locale == "uk":
        return True
    if not _raw_value(product, "title", locale):
        return False
    if not _raw_value(product, "seo_title", locale):
        return False
    if not _raw_value(product, "seo_description", locale):
        return False
    if not any(_raw_value(product, field, locale) for field in _EDITORIAL_FIELDS):
        return False
    return _localized_faqs(product, locale)


def indexable_locales(product) -> tuple[str, ...]:
    """Return the deterministic locale set for sitemap/hreflang owners."""

    return tuple(
        locale for locale in SUPPORTED_LOCALES if locale_is_indexable(product, locale)
    )


def publication_context(product, locale: str) -> dict[str, object]:
    """Build the small context payload consumed by standard PDP templates."""

    locale = (locale or "uk").split("-", 1)[0].lower()
    eligible = indexable_locales(product)
    return {
        "eligible_locales": eligible,
        "indexable": locale in eligible,
    }


def uk_only_publication_context(locale: str) -> dict[str, object]:
    """Publication signals for landing models with UK-only source copy."""

    code = (locale or "uk").split("-", 1)[0].lower()
    return {"eligible_locales": ("uk",), "indexable": code == "uk"}
