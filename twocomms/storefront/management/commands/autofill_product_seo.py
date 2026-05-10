"""Phase 13 — fill empty SEO/content fields on products.

Usage:
    python manage.py autofill_product_seo               # all published, with FAQs
    python manage.py autofill_product_seo --dry-run     # preview
    python manage.py autofill_product_seo --include-drafts
    python manage.py autofill_product_seo --slug HD-twocomms-...
    python manage.py autofill_product_seo --limit 50
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from storefront.models import Product, ProductFAQ
from storefront.services.product_seo_autofill import autofill_queryset


class Command(BaseCommand):
    help = (
        "Fill empty SEO/content fields on Product rows (idempotent: "
        "never overwrites populated values). Creates 5 standard FAQs "
        "for products that have none."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true",
                            help="Preview changes without writing.")
        parser.add_argument("--include-drafts", action="store_true",
                            help="Process drafts and archived products too.")
        parser.add_argument("--slug", action="append", default=[],
                            help="Limit to specific slug(s). Can be repeated.")
        parser.add_argument("--limit", type=int, default=0,
                            help="Optional maximum number of products to process.")

    def handle(self, *args, **opts):
        qs = Product.objects.all().order_by("id")
        if not opts["include_drafts"]:
            qs = qs.filter(status="published")
        if opts["slug"]:
            qs = qs.filter(slug__in=opts["slug"])
        if opts["limit"]:
            qs = qs[:opts["limit"]]

        total = qs.count()
        self.stdout.write(self.style.NOTICE(
            f"Autofilling {total} product(s){' (DRY-RUN)' if opts['dry_run'] else ''}…"
        ))
        report = autofill_queryset(qs, faq_model=ProductFAQ,
                                   dry_run=opts["dry_run"])

        self.stdout.write(self.style.SUCCESS(
            f"\nProcessed: {report.products_seen}\n"
            f"Changed:   {report.products_changed}\n"
            f"FAQs created: {report.faqs_created}"
        ))
        if report.fields_filled:
            self.stdout.write("\nField fill counts:")
            for f, n in sorted(report.fields_filled.items()):
                self.stdout.write(f"  {f:24s} {n}")
        if opts["dry_run"]:
            self.stdout.write(self.style.WARNING(
                "\nDry-run: no changes saved."
            ))
