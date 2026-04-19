from django.core.management.base import BaseCommand

from storefront.models import Category, Product
from storefront.services.indexnow import (
    get_category_public_url,
    get_core_indexnow_urls,
    get_product_public_url,
    is_indexnow_configured,
    submit_indexnow_urls,
)


class Command(BaseCommand):
    help = "Submit current public URLs to IndexNow for Bing-powered discovery."

    def add_arguments(self, parser):
        parser.add_argument("--url", action="append", default=[], help="Absolute URL to submit. Can be repeated.")
        parser.add_argument("--core", action="store_true", help="Include core public landing pages.")
        parser.add_argument("--products", action="store_true", help="Include published product pages.")
        parser.add_argument("--categories", action="store_true", help="Include active category pages.")
        parser.add_argument("--limit", type=int, default=0, help="Optional limit for products/categories.")
        parser.add_argument("--dry-run", action="store_true", help="Print collected URLs without submitting.")

    def handle(self, *args, **options):
        include_core = options["core"]
        include_products = options["products"]
        include_categories = options["categories"]

        if not any((include_core, include_products, include_categories, options["url"])):
            self.stdout.write(
                self.style.WARNING(
                    "Nothing selected. Use --url, --core, --products, or --categories to submit only changed URLs."
                )
            )
            return

        urls: list[str] = list(options["url"])

        if include_core:
            urls.extend(get_core_indexnow_urls())

        limit = options["limit"] or None

        if include_products:
            queryset = Product.objects.filter(status="published").only("slug", "status").order_by("-published_at", "-id")
            if limit:
                queryset = queryset[:limit]
            urls.extend(filter(None, (get_product_public_url(product) for product in queryset)))

        if include_categories:
            queryset = Category.objects.filter(is_active=True).only("slug", "is_active").order_by("order", "name")
            if limit:
                queryset = queryset[:limit]
            urls.extend(filter(None, (get_category_public_url(category) for category in queryset)))

        unique_urls = list(dict.fromkeys(urls))
        if not unique_urls:
            self.stdout.write(self.style.WARNING("No public URLs collected for IndexNow."))
            return

        self.stdout.write(f"Collected {len(unique_urls)} URL(s) for IndexNow.")

        if options["dry_run"]:
            preview = "\n".join(unique_urls[:20])
            self.stdout.write(preview)
            if len(unique_urls) > 20:
                self.stdout.write(f"... and {len(unique_urls) - 20} more")
            return

        if not is_indexnow_configured():
            self.stdout.write(self.style.WARNING("IndexNow is not configured. Set INDEXNOW_KEY before submitting."))
            return

        submitted = submit_indexnow_urls(unique_urls)
        if submitted:
            self.stdout.write(self.style.SUCCESS(f"IndexNow accepted {len(unique_urls)} URL(s)."))
            return

        self.stdout.write(self.style.WARNING("IndexNow submission was skipped or returned no-op."))
