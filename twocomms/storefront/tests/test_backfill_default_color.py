"""Tests for ``manage.py backfill_default_color``.

Covers:
1. Creates a single ``ProductColorVariant`` (linked to the canonical
   "Чорний" colour) for each published product without variants.
2. Skips products that already have any variant — re-running is a no-op.
3. ``--dry-run`` writes nothing.
4. ``--include-drafts`` also touches non-published products.
5. Variant slug is auto-generated to ``black`` (so the catalog filter
   ``?color=black`` immediately surfaces the product).
6. The new variant is marked ``is_default=True`` and ``order=0`` so it
   sorts first in PDP / catalog preview.
"""
from __future__ import annotations

from io import StringIO
from unittest.mock import patch

from django.core.cache import cache, caches
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from productcolors.models import Color, ProductColorVariant
from storefront.models import Category, Product


class _Base(TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        caches["fragments"].clear()
        for target in (
            "storefront.signals.generate_google_merchant_feed_task.apply_async",
            "storefront.signals.enqueue_indexnow_urls",
        ):
            p = patch(target)
            self.addCleanup(p.stop)
            p.start()

        self.cat = Category.objects.create(
            name="Худі", slug="hoodie-bf", is_active=True,
        )
        self.black = Color.objects.create(name="Чорний", primary_hex="#000000")
        self.coyote = Color.objects.create(name="Кайот", primary_hex="#A98463")

        self.published_no_variant = Product.objects.create(
            title="Без варіантів — published",
            slug="bf-no-variant-pub",
            category=self.cat,
            price=1000,
            status="published",
        )
        self.draft_no_variant = Product.objects.create(
            title="Без варіантів — draft",
            slug="bf-no-variant-draft",
            category=self.cat,
            price=1000,
            status="draft",
        )
        self.with_variant = Product.objects.create(
            title="З варіантом",
            slug="bf-with-variant",
            category=self.cat,
            price=1000,
            status="published",
        )
        ProductColorVariant.objects.create(
            product=self.with_variant, color=self.coyote,
            order=0, is_default=True,
        )

    def _run(self, *args):
        out = StringIO()
        call_command("backfill_default_color", *args, stdout=out)
        return out.getvalue()


class BackfillDefaultColorTests(_Base):
    def test_creates_variant_for_published_only_by_default(self):
        self._run()
        self.assertTrue(
            ProductColorVariant.objects.filter(
                product=self.published_no_variant, color=self.black
            ).exists(),
            "published product without variants should receive a black default",
        )
        self.assertFalse(
            ProductColorVariant.objects.filter(product=self.draft_no_variant).exists(),
            "drafts must be skipped unless --include-drafts is passed",
        )

    def test_skips_products_that_already_have_a_variant(self):
        before = ProductColorVariant.objects.filter(product=self.with_variant).count()
        self._run()
        after = ProductColorVariant.objects.filter(product=self.with_variant).count()
        self.assertEqual(before, after, "command must not touch products with variants")

    def test_dry_run_writes_nothing(self):
        before_total = ProductColorVariant.objects.count()
        out = self._run("--dry-run")
        after_total = ProductColorVariant.objects.count()
        self.assertEqual(before_total, after_total)
        self.assertIn("dry-run", out)
        self.assertIn(self.published_no_variant.slug, out)

    def test_include_drafts_flag(self):
        self._run("--include-drafts")
        self.assertTrue(
            ProductColorVariant.objects.filter(product=self.draft_no_variant).exists(),
        )

    def test_idempotent(self):
        self._run()
        first = ProductColorVariant.objects.count()
        self._run()
        second = ProductColorVariant.objects.count()
        self.assertEqual(first, second)

    def test_created_variant_metadata(self):
        self._run()
        variant = ProductColorVariant.objects.get(
            product=self.published_no_variant
        )
        self.assertEqual(variant.color_id, self.black.id)
        self.assertTrue(variant.is_default)
        self.assertEqual(variant.order, 0)
        # Slug must resolve to ``black`` so the catalog filter
        # ``?color=black`` immediately surfaces the product. The
        # ``ProductColorVariant._generate_url_slug`` method maps the
        # canonical "Чорний" Color name through the english slug map.
        self.assertEqual(variant.slug, "black")

    def test_errors_when_no_black_colour_exists(self):
        Color.objects.filter(pk=self.black.pk).delete()
        # Also remove any stray "чорн"/"black" name matches.
        Color.objects.filter(name__icontains="чорн").delete()
        Color.objects.filter(name__icontains="black").delete()
        with self.assertRaises(CommandError):
            self._run()

    def test_resolves_black_by_name_when_hex_differs(self):
        self.black.primary_hex = "#1A1A1A"  # not exactly #000000
        self.black.save()
        # Should still resolve via the name hint "чорн".
        self._run()
        self.assertTrue(
            ProductColorVariant.objects.filter(
                product=self.published_no_variant, color=self.black
            ).exists(),
        )
