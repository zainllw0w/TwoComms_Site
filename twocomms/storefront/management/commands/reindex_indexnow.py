"""Bulk-reindex via IndexNow.

This is the high-level companion to ``submit_indexnow_urls``. While
``submit_indexnow_urls`` accepts ad-hoc URL flags, ``reindex_indexnow``
sweeps the catalog with sensible defaults and supports an incremental
``--since-days`` mode for periodic re-pings.

Usage:
    # Submit core landing pages + every published product + every active category
    python manage.py reindex_indexnow --all

    # Only products updated in the last 7 days
    python manage.py reindex_indexnow --products --since-days=7

    # Dry run: print URLs, don't ping IndexNow
    python manage.py reindex_indexnow --all --dry-run
"""

from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from storefront.models import Category, Product
from storefront.services.indexnow import (
    INDEXNOW_BATCH_SIZE,
    get_category_public_url,
    get_core_indexnow_urls,
    get_product_public_url,
    is_indexnow_configured,
    submit_indexnow_urls,
)


class Command(BaseCommand):
    help = "Bulk-resubmit public URLs to IndexNow with batching and optional --since-days filter."

    def add_arguments(self, parser):
        parser.add_argument("--core", action="store_true", help="Include core public landing pages.")
        parser.add_argument("--products", action="store_true", help="Include published product pages.")
        parser.add_argument("--categories", action="store_true", help="Include active category pages.")
        parser.add_argument(
            "--all",
            action="store_true",
            help="Shortcut for --core --products --categories.",
        )
        parser.add_argument(
            "--since-days",
            type=int,
            default=0,
            help="Only include products/categories with updated_at within last N days.",
        )
        parser.add_argument("--limit", type=int, default=0, help="Optional cap per source group.")
        parser.add_argument(
            "--batch-size",
            type=int,
            default=INDEXNOW_BATCH_SIZE,
            help=f"URLs per HTTP call (default {INDEXNOW_BATCH_SIZE}).",
        )
        parser.add_argument(
            "--retries",
            type=int,
            default=2,
            help="Retry attempts per batch on transient errors (default 2).",
        )
        parser.add_argument("--dry-run", action="store_true", help="Print URLs without submitting.")

    def handle(self, *args, **options):
        include_core = options["core"] or options["all"]
        include_products = options["products"] or options["all"]
        include_categories = options["categories"] or options["all"]

        if not any((include_core, include_products, include_categories)):
            self.stdout.write(
                self.style.WARNING(
                    "Nothing selected. Pass --core, --products, --categories, or --all."
                )
            )
            return

        since_days = max(0, int(options["since_days"]))
        since_dt = timezone.now() - timedelta(days=since_days) if since_days else None
        limit = options["limit"] or None

        urls: list[str] = []

        if include_core:
            core_urls = get_core_indexnow_urls()
            urls.extend(core_urls)
            self.stdout.write(f"  core: {len(core_urls)} URL(s)")

        if include_products:
            qs = Product.objects.filter(status="published").only("slug", "status", "updated_at")
            if since_dt is not None:
                qs = qs.filter(updated_at__gte=since_dt)
            qs = qs.order_by("-updated_at", "-id")
            if limit:
                qs = qs[:limit]
            product_urls = [u for u in (get_product_public_url(p) for p in qs) if u]
            urls.extend(product_urls)
            self.stdout.write(f"  products: {len(product_urls)} URL(s)")

        if include_categories:
            qs = Category.objects.filter(is_active=True).only("slug", "is_active", "updated_at")
            if since_dt is not None:
                qs = qs.filter(updated_at__gte=since_dt)
            qs = qs.order_by("order", "name")
            if limit:
                qs = qs[:limit]
            category_urls = [u for u in (get_category_public_url(c) for c in qs) if u]
            urls.extend(category_urls)
            self.stdout.write(f"  categories: {len(category_urls)} URL(s)")

        unique_urls = list(dict.fromkeys(urls))
        if not unique_urls:
            self.stdout.write(self.style.WARNING("No public URLs collected."))
            return

        self.stdout.write(f"Total unique: {len(unique_urls)} URL(s)")

        if options["dry_run"]:
            preview = "\n".join(unique_urls[:20])
            self.stdout.write(preview)
            if len(unique_urls) > 20:
                self.stdout.write(f"... and {len(unique_urls) - 20} more")
            return

        if not is_indexnow_configured():
            self.stdout.write(
                self.style.WARNING("IndexNow is not configured. Set INDEXNOW_KEY before submitting.")
            )
            return

        ok = submit_indexnow_urls(
            unique_urls,
            batch_size=options["batch_size"],
            retries=options["retries"],
        )
        if ok:
            self.stdout.write(self.style.SUCCESS(f"IndexNow accepted {len(unique_urls)} URL(s)."))
        else:
            self.stdout.write(
                self.style.ERROR(
                    "IndexNow submission had failures. Check logs for retry/error details."
                )
            )
