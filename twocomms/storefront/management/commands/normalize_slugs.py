"""
SEO Audit 2026-05-15 — P0 slug normalisation command.

Fixes the following problems found in 49% of published product slugs:
  - Leading hyphens (``-my-little-baby`` → ``my-little-baby``)
  - Trailing hyphens (``-225-tshirt-`` → ``225-tshirt``)
  - Underscores (``Hoodie_Silent_Winter`` → ``hoodie-silent-winter``)
  - Uppercase (``Idea-hd`` → ``idea-hd``)
  - Double hyphens (``a--b`` → ``a-b``)

For every changed slug the command creates a ``django.contrib.redirects.Redirect``
(301) from the old URL to the new one so Google and existing links keep working.

Usage:
    python manage.py normalize_slugs --dry-run   # preview changes
    python manage.py normalize_slugs              # apply changes
"""

import re
from django.conf import settings
from django.contrib.redirects.models import Redirect
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand

from storefront.models import Product


def _normalise(slug: str) -> str:
    """Return a clean, SEO-friendly slug."""
    s = slug.strip("-").lower().replace("_", "-")
    s = re.sub(r"-{2,}", "-", s)          # collapse double hyphens
    s = s.strip("-")                       # safety strip after collapse
    return s


# Manually curated typo fixes (old_slug → new_slug).
# Only applied when the product's current slug exactly matches a key.
_TYPO_FIXES = {
    "clasic-tshort": "classic-tshirt",
    "buisness-money": "business-money",
    "buisness-money-hd": "business-money-hd",
    "buisness-money-ls": "business-money-ls",
}


class Command(BaseCommand):
    help = "Normalise product slugs and create 301 redirects for changed URLs."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview changes without writing to the database.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        products = Product.objects.all().order_by("id")

        site = Site.objects.get_current()
        changes = []

        for product in products:
            old_slug = product.slug

            # 1. Apply typo fix if one exists
            new_slug = _TYPO_FIXES.get(old_slug, old_slug)

            # 2. Normalise (strip hyphens, lowercase, etc.)
            new_slug = _normalise(new_slug)

            if new_slug == old_slug:
                continue

            # Check uniqueness — if another product already uses new_slug,
            # append the product pk to disambiguate.
            if Product.objects.filter(slug=new_slug).exclude(pk=product.pk).exists():
                new_slug = f"{new_slug}-{product.pk}"
                new_slug = _normalise(new_slug)

            old_path = f"/product/{old_slug}/"
            new_path = f"/product/{new_slug}/"

            changes.append((product, old_slug, new_slug, old_path, new_path))

        if not changes:
            self.stdout.write(self.style.SUCCESS("All slugs are already normalised."))
            return

        self.stdout.write(f"\n{'DRY RUN — ' if dry_run else ''}Found {len(changes)} slug(s) to fix:\n")

        for product, old_slug, new_slug, old_path, new_path in changes:
            self.stdout.write(f"  [{product.pk}] {old_slug!r} → {new_slug!r}")

        if dry_run:
            self.stdout.write(self.style.WARNING("\nDry-run mode — no changes written."))
            return

        self.stdout.write("")

        for product, old_slug, new_slug, old_path, new_path in changes:
            product.slug = new_slug
            product.save(update_fields=["slug"])

            # Create 301 redirect (or update if one already exists)
            Redirect.objects.update_or_create(
                site=site,
                old_path=old_path,
                defaults={"new_path": new_path},
            )
            self.stdout.write(self.style.SUCCESS(
                f"  ✓ [{product.pk}] {old_slug!r} → {new_slug!r}  (301 redirect created)"
            ))

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. {len(changes)} slug(s) normalised with 301 redirects."
            f"\nNext steps:"
            f"\n  1. Run `python manage.py reindex_indexnow` to notify search engines"
            f"\n  2. Verify sitemap at /sitemap-products.xml"
            f"\n  3. Request re-crawl in Google Search Console"
        ))
