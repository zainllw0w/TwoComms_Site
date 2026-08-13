"""Retired legacy FAQ refresh entry point.

The Phase-13 ``autofill_product_seo`` command wrote five universal
FAQs per product where Q3/Q4/Q5 ("Скільки триває доставка?", "Як
повернути або обміняти товар?", "Чи можна замовити з власним
принтом?") were *byte-identical* across all 65 PDPs. Google clusters
FAQ rich-result candidates by question string and surfaces a rich
result for at most one URL per cluster, so 65 PDPs effectively
competed for one rich-result slot.

FAQ synthesis is disabled. Existing rows remain untouched for a separate
exact-signature, backup-first cleanup command.

The command remains for compatibility but performs no rewrites while the
generator is retired. Human-written and legacy rows are both left untouched.

Usage:
    python manage.py refresh_product_faqs              # apply
    python manage.py refresh_product_faqs --dry-run    # preview
    python manage.py refresh_product_faqs --slug XYZ   # single product
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from storefront.models import Product
from storefront.services.product_copy_v2 import STANDARD_CATEGORY_SLUGS


class Command(BaseCommand):
    help = "Retired: scan scope only; no FAQ rows are changed."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview changes without writing.",
        )
        parser.add_argument(
            "--slug",
            action="append",
            default=[],
            help="Limit to specific slug(s). Can be repeated.",
        )
        parser.add_argument(
            "--include-drafts",
            action="store_true",
            help="Process drafts and archived products too.",
        )

    def handle(self, *args, **opts):
        qs = Product.objects.filter(
            category__slug__in=STANDARD_CATEGORY_SLUGS,
        ).select_related("category").order_by("id")
        if not opts["include_drafts"]:
            qs = qs.filter(status="published")
        if opts["slug"]:
            qs = qs.filter(slug__in=opts["slug"])

        dry = opts["dry_run"]
        total = qs.count()
        self.stdout.write(self.style.NOTICE(
            f"Scanning retired FAQ refresh scope: {total} product(s)"
            f"{' (DRY-RUN)' if dry else ''}…"
        ))

        self.stdout.write(self.style.WARNING(
            "Retired: no FAQ rows were changed; use the guarded exact-signature "
            "cleanup command for reviewed legacy data."
        ))
        self.stdout.write(f"\nProducts scanned: {total}\nFAQs rewritten:   0")
        if dry:
            self.stdout.write(self.style.WARNING(
                "Dry-run: no changes saved."
            ))
