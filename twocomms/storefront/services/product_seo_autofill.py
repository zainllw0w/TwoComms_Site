"""Fail-closed identifier autofill for standard Product rows.

Only the owner-safe title and image identifier can be generated. Historical
material, weight, durability, shrinkage, origin, donation, service and FAQ
boilerplate is retired until reviewed facts are supplied.

The service is invoked by the ``autofill_product_seo`` management
command. It can also be called directly from views or signals when
a new product is created.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from django.utils import translation

from .product_copy_v2 import STANDARD_CATEGORY_SLUGS


# --------------------------------------------------------------- TEMPLATES

# Per-category copy templates. Variables: {title}, {category_singular},
# {category_genitive}, {colour_list}, {price}.

CATEGORY_LABEL = {
    "hoodie":      ("худі",      "худі",      "худі"),
    "tshirts":     ("футболка",  "футболки",  "футболку"),
    "long-sleeve": ("лонгслів",  "лонгсліва", "лонгслів"),
}

# Default fallback for unknown categories.
DEFAULT_LABEL = ("товар", "товару", "товар")


def _labels(category_slug: str | None) -> tuple[str, str, str]:
    """(nominative-singular, genitive-singular, accusative) for category."""
    return CATEGORY_LABEL.get((category_slug or "").lower(), DEFAULT_LABEL)


def _raw_uk(product, field_name: str) -> str:
    """Read a Ukrainian source field without modeltranslation fallback."""
    value = getattr(product, f"{field_name}_uk", "")
    return value.strip() if isinstance(value, str) else ""


SEO_TITLE_MAX = 60


def _build_seo_title(product) -> str:
    """Build a concise owner-safe title with a stable brand suffix.

    The category label uses the accusative form after «купити». The
    60-character value is a project-level output limit; it is not a claim
    about a universal search-engine display or ranking threshold.
    """
    category_slug = (getattr(getattr(product, "category", None), "slug", "") or "").lower()
    if category_slug not in STANDARD_CATEGORY_SLUGS:
        return ""
    nom, _, acc = _labels(category_slug)
    base = _raw_uk(product, "title")
    if not base:
        return ""
    suffix = " — TwoComms"
    # Add category if title doesn't already contain it (use accusative
    # because the leading «Купити» is a transitive verb).
    if nom.casefold() not in base.casefold():
        candidate = f"Купити {base} ({acc}){suffix}"
    else:
        candidate = f"Купити {base}{suffix}"
    if len(candidate) <= SEO_TITLE_MAX:
        return candidate
    # Trim the title body, not the suffix; avoid cutting inside a word.
    budget = SEO_TITLE_MAX - len(suffix)
    if budget > 0 and len(base) > budget:
        head = base[:budget].rsplit(" ", 1)[0]
    else:
        head = base[:budget] if budget > 0 else base
    return head + suffix


def _build_seo_description(product) -> str:
    """Return no generated claim until a reviewed fact owner exists."""
    return ""


def _build_seo_keywords(product) -> str:
    """Keyword stuffing has no owner; leave the field empty."""
    return ""


def _build_main_image_alt(product) -> str:
    """Return an identifier-only alt label without unsupported claims."""
    category_slug = (getattr(getattr(product, "category", None), "slug", "") or "").lower()
    if category_slug not in STANDARD_CATEGORY_SLUGS:
        return ""
    nom, _, _ = _labels(category_slug)
    title = _raw_uk(product, "title")
    if not title:
        return ""
    text = f"{title} — {nom} TwoComms"
    return text[:200]


def _build_short_description(product) -> str:
    """Do not synthesize editorial copy without a reviewed owner."""
    return ""


def _build_care_instructions(product) -> str:
    """Return no generated care policy until a reviewed fact owner exists."""
    return ""


def _build_target_audience(product) -> str:
    """Return no generated audience copy without an editorial owner."""
    return ""


def _build_full_description(product) -> str:
    """Return no generated long-form copy without reviewed source facts."""
    return ""


# Retained as an empty compatibility constant for callers/tests that imported
# the former universal template. No generated FAQ wording is published.
UNIVERSAL_FAQS: list[tuple[str, str]] = []


def _build_faqs(product) -> list[tuple[str, str]]:
    """Do not synthesize FAQ rows; reviewed ProductFAQ owns these facts."""
    return []


# --------------------------------------------------------------- ENGINE

@dataclass
class AutofillReport:
    products_seen: int = 0
    products_changed: int = 0
    fields_filled: dict = field(default_factory=dict)
    faqs_created: int = 0

    def bump(self, field_name: str) -> None:
        self.fields_filled[field_name] = self.fields_filled.get(field_name, 0) + 1


# Map of (Product field name → builder callable). Builder is called only
# when the field is empty / whitespace.
FIELD_BUILDERS = {
    "seo_title":          _build_seo_title,
    "main_image_alt":     _build_main_image_alt,
}


def _is_blank(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    return False


def autofill_product(product, *, faq_model, dry_run: bool = False,
                     report: AutofillReport | None = None) -> AutofillReport:
    """Fill only blank owner-safe identifiers; never create editorial FAQs.

    ``faq_model`` is passed in so the function works equally from a
    management command (real ``ProductFAQ``) and from data migrations
    (historical model via ``apps.get_model``)."""
    report = report or AutofillReport()
    report.products_seen += 1

    category_slug = (getattr(getattr(product, "category", None), "slug", "") or "").lower()
    if category_slug not in STANDARD_CATEGORY_SLUGS:
        return report

    if not _raw_uk(product, "title"):
        return report

    update_fields: list[str] = []
    with translation.override("uk"):
        for field_name, builder in FIELD_BUILDERS.items():
            raw_field_name = f"{field_name}_uk"
            current = getattr(product, raw_field_name, None)
            if not _is_blank(current):
                continue
            new_value = builder(product)
            if not new_value:
                continue
            setattr(product, raw_field_name, new_value)
            update_fields.append(raw_field_name)
            report.bump(raw_field_name)

    if update_fields and not dry_run:
        product.save(update_fields=update_fields)

    if update_fields:
        report.products_changed += 1
    return report


def autofill_queryset(queryset: "QuerySet", *, faq_model,
                      dry_run: bool = False) -> AutofillReport:
    """Run ``autofill_product`` over a queryset of Products."""
    report = AutofillReport()
    for product in queryset.select_related("category"):
        autofill_product(product, faq_model=faq_model, dry_run=dry_run,
                         report=report)
    return report
