"""Phase 17 — simple fit-toggle UI for the custom admin product builder."""
from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase

from storefront.models import Category, Product, ProductFitOption
from storefront.forms import (
    ProductFitToggleForm,
    ensure_default_fit_options_for_tshirt,
)


class _Base(TestCase):
    def setUp(self):
        super().setUp()
        for target in (
            "storefront.signals.generate_google_merchant_feed_task.apply_async",
            "storefront.signals.enqueue_indexnow_urls",
        ):
            p = patch(target)
            self.addCleanup(p.stop)
            p.start()
        self.tshirt_cat = Category.objects.create(
            name="Футболки", slug="tshirts", is_active=True,
        )
        self.hoodie_cat = Category.objects.create(
            name="Худі", slug="hoodie", is_active=True,
        )

    def _make_product(self, *, title="Футболка X", category=None, **extra):
        return Product.objects.create(
            title=title,
            slug=extra.pop("slug", title.lower().replace(" ", "-")),
            category=category or self.tshirt_cat,
            price=extra.pop("price", 800),
            status=extra.pop("status", "published"),
            **extra,
        )


class FormInitialTests(_Base):

    def test_legacy_tshirt_with_no_rows_defaults_to_both_on(self):
        product = self._make_product()
        form = ProductFitToggleForm(product=product)
        self.assertTrue(form.initial["fit_classic_enabled"])
        self.assertTrue(form.initial["fit_oversize_enabled"])
        self.assertEqual(form.initial["fit_default"], "classic")

    def test_initial_reflects_existing_state(self):
        product = self._make_product()
        ProductFitOption.objects.create(
            product=product, code="classic", label="Класична",
            is_active=False, is_default=False, order=0,
        )
        ProductFitOption.objects.create(
            product=product, code="oversize", label="Оверсайз",
            is_active=True, is_default=True, order=1,
        )
        form = ProductFitToggleForm(product=product)
        self.assertFalse(form.initial["fit_classic_enabled"])
        self.assertTrue(form.initial["fit_oversize_enabled"])
        self.assertEqual(form.initial["fit_default"], "oversize")


class FormSaveTests(_Base):

    def _post_save(self, product, **fields):
        data = {
            "fit_toggle-fit_classic_enabled": "on",
            "fit_toggle-fit_oversize_enabled": "on",
            "fit_toggle-fit_default": "classic",
        }
        for k, v in fields.items():
            key = f"fit_toggle-{k}"
            if v is False:
                data.pop(key, None)
            else:
                data[key] = "on" if v is True else v
        form = ProductFitToggleForm(data=data, product=product, prefix="fit_toggle")
        self.assertTrue(form.is_valid(), form.errors)
        form.save(product)
        return form

    def test_save_creates_both_rows_when_both_enabled(self):
        product = self._make_product()
        self._post_save(product)
        rows = list(product.fit_options.order_by("order", "id"))
        self.assertEqual([r.code for r in rows], ["classic", "oversize"])
        self.assertTrue(all(r.is_active for r in rows))
        defaults = [r for r in rows if r.is_default]
        self.assertEqual(len(defaults), 1)
        self.assertEqual(defaults[0].code, "classic")

    def test_save_disables_only_classic(self):
        product = self._make_product()
        # Bootstrap the canonical pair first.
        self._post_save(product)
        # Now disable classic via a save round-trip.
        self._post_save(
            product,
            fit_classic_enabled=False,
            fit_default="oversize",
        )
        rows = {r.code: r for r in product.fit_options.all()}
        self.assertFalse(rows["classic"].is_active)
        self.assertTrue(rows["oversize"].is_active)
        self.assertTrue(rows["oversize"].is_default)
        self.assertFalse(rows["classic"].is_default)

    def test_disabling_both_leaves_no_active_default(self):
        product = self._make_product()
        self._post_save(product)
        self._post_save(
            product,
            fit_classic_enabled=False,
            fit_oversize_enabled=False,
            fit_default="",
        )
        rows = list(product.fit_options.all())
        self.assertTrue(all(not r.is_active for r in rows))
        self.assertFalse(any(r.is_default for r in rows))

    def test_save_does_not_touch_custom_codes(self):
        product = self._make_product()
        ProductFitOption.objects.create(
            product=product, code="regular", label="Регуляр",
            is_active=True, is_default=False, order=2,
        )
        self._post_save(product)
        # The unrelated row stays alive.
        regular = product.fit_options.get(code="regular")
        self.assertTrue(regular.is_active)

    def test_clean_coerces_default_to_active_code(self):
        product = self._make_product()
        # User asks default=classic but disables it; oversize stays on.
        form = self._post_save(
            product,
            fit_classic_enabled=False,
            fit_default="classic",
        )
        # The clean step pushed the default to "oversize".
        self.assertEqual(form.cleaned_data["fit_default"], "oversize")
        self.assertTrue(product.fit_options.get(code="oversize").is_default)


class EnsureDefaultsTests(_Base):

    def test_creates_pair_for_tshirt_without_rows(self):
        product = self._make_product()
        created = ensure_default_fit_options_for_tshirt(product)
        self.assertTrue(created)
        rows = list(product.fit_options.order_by("order", "id"))
        self.assertEqual([r.code for r in rows], ["classic", "oversize"])
        self.assertTrue(rows[0].is_default)  # classic
        self.assertFalse(rows[1].is_default)

    def test_no_op_when_rows_exist(self):
        product = self._make_product()
        ProductFitOption.objects.create(
            product=product, code="oversize", label="Оверсайз",
            is_active=True, is_default=True, order=0,
        )
        created = ensure_default_fit_options_for_tshirt(product)
        self.assertFalse(created)
        self.assertEqual(product.fit_options.count(), 1)

    def test_skipped_for_non_tshirt(self):
        product = self._make_product(
            title="Худі чорне", category=self.hoodie_cat, slug="hd-1",
        )
        created = ensure_default_fit_options_for_tshirt(product)
        self.assertFalse(created)
        self.assertEqual(product.fit_options.count(), 0)

    def test_skipped_when_selector_disabled(self):
        product = self._make_product(fit_selector_enabled=False)
        created = ensure_default_fit_options_for_tshirt(product)
        self.assertFalse(created)
        self.assertEqual(product.fit_options.count(), 0)


class StorefrontIntegrationTests(_Base):
    """The PDP view auto-heals legacy tshirts on first render."""

    def test_pdp_view_creates_pair_on_first_visit(self):
        product = self._make_product()
        self.assertEqual(product.fit_options.count(), 0)

        from storefront.views.product import _resolve_fit_options
        options = _resolve_fit_options(product)
        # Both rows now exist and are returned.
        self.assertEqual(product.fit_options.count(), 2)
        codes = [o.code for o in options]
        self.assertIn("classic", codes)
        self.assertIn("oversize", codes)
