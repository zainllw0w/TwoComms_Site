"""SEO molecular-upgrade US-15 — translation coverage report.

Computes per-product translation completeness across uk/ru/en for the
fields registered in ``storefront.translation.ProductTranslationOptions``.
A field counts as "translated" when its locale-specific column has a
non-empty trimmed value distinct from the Ukrainian baseline.

Usage::

    python manage.py check_translation_coverage
    python manage.py check_translation_coverage --json
    python manage.py check_translation_coverage --threshold 70
    python manage.py check_translation_coverage --product-id 12

The default report prints aggregate stats followed by the bottom-10
worst-translated products (CP-15.1 / CP-15.2 evidence).
"""
from __future__ import annotations

import json
from typing import Dict, Iterable, List, Tuple

from django.core.management.base import BaseCommand


# Fields tracked by ProductTranslationOptions. Keep in sync with
# ``storefront.translation``.
TRACKED_FIELDS = (
    "title",
    "short_description",
    "description",
    "full_description",
    "target_audience",
    "care_instructions",
    "main_image_alt",
    "seo_title",
    "seo_description",
    "seo_keywords",
    "seo_bottom_html",
)

LOCALES = ("uk", "ru", "en")


def _norm(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _coverage_for(product, locale: str) -> Tuple[int, int, List[str]]:
    """Return (translated_count, total, missing_fields) for ``locale``."""
    translated = 0
    missing: List[str] = []
    for field in TRACKED_FIELDS:
        uk_value = _norm(getattr(product, f"{field}_uk", ""))
        loc_value = _norm(getattr(product, f"{field}_{locale}", ""))
        # Skip fields that are also empty in UK — they don't count
        # towards completeness in either direction.
        if not uk_value:
            continue
        if locale == "uk":
            translated += 1  # baseline is by definition translated
            continue
        # For ru / en we require a non-empty locale value that is not a
        # byte-for-byte copy of the UK fallback.
        if loc_value and loc_value != uk_value:
            translated += 1
        else:
            missing.append(field)
    total = sum(
        1 for field in TRACKED_FIELDS if _norm(getattr(product, f"{field}_uk", ""))
    )
    return translated, total, missing


def _percent(translated: int, total: int) -> float:
    return (100.0 * translated / total) if total else 0.0


class Command(BaseCommand):
    help = "Report translation coverage per product / locale (US-15)."

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true", help="Emit JSON instead of human-readable.")
        parser.add_argument("--threshold", type=int, default=70, help="Highlight products below this %% translated.")
        parser.add_argument("--product-id", type=int, help="Limit to one product id for debugging.")

    def handle(self, *args, **opts):
        from storefront.models import Product

        as_json = bool(opts.get("json"))
        threshold = int(opts.get("threshold") or 70)
        product_id = opts.get("product_id")

        qs = Product.objects.all().order_by("id")
        if product_id:
            qs = qs.filter(id=product_id)

        per_product: List[Dict[str, object]] = []
        agg: Dict[str, Dict[str, int]] = {locale: {"sum": 0, "count": 0, "below": 0} for locale in LOCALES}

        for product in qs:
            row: Dict[str, object] = {
                "id": product.id,
                "slug": product.slug,
                "title": product.title,
                "locales": {},
            }
            for locale in LOCALES:
                translated, total, missing = _coverage_for(product, locale)
                pct = _percent(translated, total)
                row["locales"][locale] = {
                    "translated": translated,
                    "total": total,
                    "percent": round(pct, 1),
                    "missing_fields": missing,
                }
                if total:
                    agg[locale]["sum"] += pct
                    agg[locale]["count"] += 1
                    if pct < threshold:
                        agg[locale]["below"] += 1
            per_product.append(row)

        summary: Dict[str, object] = {"locales": {}, "products": len(per_product), "threshold": threshold}
        for locale in LOCALES:
            data = agg[locale]
            avg = (data["sum"] / data["count"]) if data["count"] else 0.0
            summary["locales"][locale] = {
                "average_percent": round(avg, 1),
                "products_below_threshold": data["below"],
                "total_evaluated": data["count"],
            }

        worst = sorted(
            per_product,
            key=lambda r: (
                r["locales"]["ru"]["percent"] + r["locales"]["en"]["percent"]
            ),
        )[:10]

        report = {"summary": summary, "worst_offenders": worst}

        if as_json:
            self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
            return

        self.stdout.write(self.style.NOTICE(
            f"=== Translation coverage ({len(per_product)} products) ==="
        ))
        for locale in LOCALES:
            sm = summary["locales"][locale]
            self.stdout.write(
                f"  {locale}: avg {sm['average_percent']}%  | "
                f"below {threshold}%: {sm['products_below_threshold']} / {sm['total_evaluated']}"
            )
        self.stdout.write("")
        self.stdout.write(self.style.NOTICE("Worst-translated 10 (ru+en sum):"))
        for row in worst:
            ru = row["locales"]["ru"]
            en = row["locales"]["en"]
            self.stdout.write(
                f"  #{row['id']:>3} {row['slug']:<30} | ru {ru['percent']:>5.1f}% "
                f"({len(ru['missing_fields'])} missing) | en {en['percent']:>5.1f}% "
                f"({len(en['missing_fields'])} missing)"
            )
