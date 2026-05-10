"""Phase 21 (PR-6, T16.2) — audit published products for missing imagery.

Lists every published product that would NOT contribute any
``<image:image>`` row to ``sitemap-images.xml``, so the catalog
team can fix listings before Google's image-sitemap crawl picks
up empty stubs.

Usage::

    python manage.py audit_product_images

    # CSV-friendly output for spreadsheets:
    python manage.py audit_product_images --csv

    # Include products that DO have images but only one (catalog
    # cards look bad with a single hero):
    python manage.py audit_product_images --thin-threshold=2

The command is read-only and never writes to the DB.
"""

from __future__ import annotations

import csv

from django.core.management.base import BaseCommand

from storefront.models import Product


def _safe_url(field) -> str:
    """Return the ``.url`` of a FileField/ImageField if it has a name,
    else empty string. Handles unsaved/cleared file fields silently.
    """
    try:
        return field.url if field else ""
    except (ValueError, AttributeError):
        return ""


def _count_images(product) -> int:
    """Cheap-ish image count for one product.

    Counts:
      * main_image (1 if set)
      * gallery rows (``ProductImage`` ⇒ ``product.images``)
      * colour-variant photos (``ProductColorVariant.images``)

    Deduplicated by URL so we don't double-count a hero that's also
    set as the first colour-variant photo.
    """
    seen: set[str] = set()

    main = _safe_url(getattr(product, "main_image", None))
    if main:
        seen.add(main)

    try:
        for img in product.images.all():
            url = _safe_url(getattr(img, "image", None))
            if url:
                seen.add(url)
    except Exception:
        pass

    try:
        for variant in product.color_variants.all():
            for img in variant.images.all():
                url = _safe_url(getattr(img, "image", None))
                if url:
                    seen.add(url)
    except Exception:
        pass

    return len(seen)


class Command(BaseCommand):
    help = (
        "List published products with zero (or thin) image counts so the "
        "team can backfill assets before Google re-crawls sitemap-images."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--thin-threshold",
            type=int,
            default=1,
            help=(
                "Treat products with FEWER than this many images as "
                "problematic (default: 1, i.e. only zero-image products)."
            ),
        )
        parser.add_argument(
            "--csv",
            action="store_true",
            default=False,
            help="Output CSV instead of human-friendly table.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Cap output to N rows.",
        )

    def handle(self, *args, **options):
        threshold = max(1, int(options["thin_threshold"]))
        emit_csv = bool(options["csv"])
        limit = options["limit"]

        products = (
            Product.objects.filter(status="published")
            .select_related("category")
            .prefetch_related("images", "color_variants__images")
            .order_by("category__slug", "id")
        )

        problem_rows: list[tuple[int, str, str, str, int]] = []
        for product in products:
            count = _count_images(product)
            if count < threshold:
                problem_rows.append((
                    product.id,
                    (getattr(product.category, "slug", "") or "—"),
                    product.slug or "—",
                    product.title or "—",
                    count,
                ))
            if limit is not None and len(problem_rows) >= limit:
                break

        if emit_csv:
            # Route through ``self.stdout`` so ``call_command(stdout=...)``
            # in tests / scripted runs captures the output.
            writer = csv.writer(self.stdout)
            writer.writerow(["product_id", "category_slug", "slug", "title", "image_count"])
            for row in problem_rows:
                writer.writerow(row)
            return

        if not problem_rows:
            self.stdout.write(self.style.SUCCESS(
                f"All published products have at least {threshold} image(s). ✅"
            ))
            return

        self.stdout.write(self.style.WARNING(
            f"Found {len(problem_rows)} product(s) below the threshold "
            f"({threshold}):"
        ))
        self.stdout.write("")
        for pid, cat, slug, title, count in problem_rows:
            self.stdout.write(
                f"  #{pid:>5}  cat={cat:<14}  slug={slug:<32}  imgs={count}  {title}"
            )
