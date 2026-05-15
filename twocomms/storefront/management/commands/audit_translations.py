"""Audit translation completeness across modeltranslation fields.

Usage:
    python manage.py audit_translations
    python manage.py audit_translations --json    # machine-readable
"""
from __future__ import annotations

import json
from collections import OrderedDict

from django.core.management.base import BaseCommand

from storefront.models import Category, Product, ProductFAQ


_LOCALES = ("uk", "ru", "en")

_MODELS = (
    (
        Category,
        (
            "name",
            "description",
            "seo_text_title",
            "seo_intro_html",
            "seo_title",
            "seo_h1",
            "seo_description",
        ),
    ),
    (
        Product,
        (
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
        ),
    ),
    (
        ProductFAQ,
        (
            "question",
            "answer",
        ),
    ),
)


class Command(BaseCommand):
    help = "Audit translation fill rates across modeltranslation fields."

    def add_arguments(self, parser):
        parser.add_argument(
            "--json",
            action="store_true",
            help="Emit machine-readable JSON instead of a console table.",
        )

    def handle(self, *args, json_output=False, **options):
        report = OrderedDict()
        for model_cls, fields in _MODELS:
            rows = list(model_cls.objects.all())
            total = len(rows)
            model_report = OrderedDict()
            for field in fields:
                cells = {loc: 0 for loc in _LOCALES}
                for obj in rows:
                    for loc in _LOCALES:
                        val = getattr(obj, f"{field}_{loc}", None)
                        if val is not None and str(val).strip():
                            cells[loc] += 1
                model_report[field] = {
                    loc: {
                        "filled": cells[loc],
                        "missing": total - cells[loc],
                        "pct": round(cells[loc] / total * 100) if total else 0,
                    }
                    for loc in _LOCALES
                }
            report[model_cls.__name__] = {"total": total, "fields": model_report}

        if json_output:
            self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
            return

        for model_name, data in report.items():
            self.stdout.write(self.style.MIGRATE_HEADING(
                f"\n=== {model_name} (n={data['total']}) ==="
            ))
            for field, locales in data["fields"].items():
                line = f"  {field:30s}"
                for loc in _LOCALES:
                    cell = locales[loc]
                    line += f" | {loc}: {cell['pct']:3d}% ({cell['missing']:3d} miss)"
                self.stdout.write(line)
