"""Э3.7 — один resolver варианта, наличия и медиа для всех трёх потребителей."""
from unittest.mock import patch

from django.test import TestCase

from management.services import ig_catalog_media
from management.services.ig_offer_resolver import (
    OfferStatus,
    resolve_client_color_variant,
    resolve_offer,
)


class _FakeDecision:
    def __init__(self, status, reason):
        self.status = status
        self.reason = reason
        self.allocation = None


class OfferResolverStatusTests(TestCase):
    """Три потребителя обязаны получить один статус на одинаковых данных."""

    def _resolve(self, status, reason, *, published=True):
        from management.services.ig_availability import AvailabilityStatus

        mapping = {
            "allocatable": AvailabilityStatus.ALLOCATABLE,
            "unavailable": AvailabilityStatus.UNAVAILABLE,
            "unknown": AvailabilityStatus.UNKNOWN,
        }
        with patch(
            "management.services.ig_offer_resolver._product_is_published",
            return_value=published,
        ), patch(
            "management.services.ig_offer_resolver._aggregate_stock", return_value=0
        ), patch(
            "management.services.ig_offer_resolver.resolve_allocation",
            return_value=_FakeDecision(mapping[status], reason),
        ):
            return resolve_offer(product_id=7, color_variant_id=3, size="L")

    def test_allocatable_is_in_stock(self):
        resolution = self._resolve("allocatable", "catalog_variant_stock")
        self.assertEqual(resolution.status, OfferStatus.IN_STOCK)
        self.assertTrue(resolution.purchasable)
        self.assertEqual(resolution.customer_visible_availability, "в наявності")

    def test_zero_stock_is_made_to_order_not_unavailable(self):
        """Каталог обещал «під замовлення» — resolver обязан говорить то же."""
        for reason in (
            "insufficient_catalog_variant_stock",
            "insufficient_warehouse_stock",
        ):
            resolution = self._resolve("unavailable", reason)
            self.assertEqual(resolution.status, OfferStatus.MADE_TO_ORDER, reason)
            self.assertTrue(resolution.purchasable)
            self.assertIn("під замовлення", resolution.customer_visible_availability)

    def test_disabled_size_is_never_made_to_order(self):
        """Отключённый размер нельзя «отшить за 1-3 дня»."""
        for reason in ("size_disabled", "fit_not_supported", "invalid_quantity"):
            resolution = self._resolve("unavailable", reason)
            self.assertEqual(resolution.status, OfferStatus.UNAVAILABLE, reason)
            self.assertFalse(resolution.purchasable)

    def test_untracked_inventory_is_made_to_order(self):
        for reason in ("inventory_policy_missing", "inventory_untracked"):
            resolution = self._resolve("unknown", reason)
            self.assertEqual(resolution.status, OfferStatus.MADE_TO_ORDER, reason)

    def test_ambiguous_mapping_is_unknown_and_says_nothing_to_the_customer(self):
        for reason in ("inventory_mapping_missing", "inventory_mapping_ambiguous"):
            resolution = self._resolve("unknown", reason)
            self.assertEqual(resolution.status, OfferStatus.UNKNOWN, reason)
            self.assertFalse(resolution.purchasable)
            self.assertEqual(resolution.customer_visible_availability, "")

    def test_unpublished_product_is_never_offered(self):
        resolution = self._resolve("allocatable", "catalog_variant_stock", published=False)
        self.assertEqual(resolution.status, OfferStatus.UNAVAILABLE)
        self.assertEqual(resolution.reason, "product_not_published")

    def test_invalid_product_id_is_unknown(self):
        self.assertEqual(resolve_offer(product_id=0).status, OfferStatus.UNKNOWN)
        self.assertEqual(resolve_offer(product_id="x").status, OfferStatus.UNKNOWN)

    def test_aggregate_stock_is_diagnostic_only(self):
        from management.services.ig_availability import AvailabilityStatus

        with patch(
            "management.services.ig_offer_resolver._product_is_published",
            return_value=True,
        ), patch(
            "management.services.ig_offer_resolver._aggregate_stock", return_value=99
        ), patch(
            "management.services.ig_offer_resolver.resolve_allocation",
            return_value=_FakeDecision(
                AvailabilityStatus.UNAVAILABLE, "size_disabled"
            ),
        ):
            resolution = resolve_offer(product_id=7, color_variant_id=3, size="L")
        self.assertEqual(resolution.diagnostic_aggregate_stock, 99)
        self.assertEqual(
            resolution.status,
            OfferStatus.UNAVAILABLE,
            "агрегированный остаток не должен переопределять точное решение",
        )

    def test_exact_media_scope_follows_the_resolved_variant(self):
        resolution = self._resolve("allocatable", "catalog_variant_stock")
        self.assertEqual(resolution.exact_media_scope, (7, 3))


class ClientVariantResolutionTests(TestCase):
    """Двусмысленный цвет — это отсутствие доказательства, а не «возьмём первый»."""

    class _Color:
        def __init__(self, name, slug=""):
            self.name = name
            self.slug = slug

    class _Variant:
        def __init__(self, pk, color):
            self.pk = pk
            self.color = color

    class _Client:
        def __init__(self, color):
            self.current_color = color

    def _resolve(self, color_text, variants):
        with patch(
            "productcolors.models.ProductColorVariant.objects"
        ) as objects:
            objects.filter.return_value.select_related.return_value.order_by.return_value = variants
            return resolve_client_color_variant(self._Client(color_text), 7)

    def test_unambiguous_colour_resolves_to_one_variant(self):
        variants = [
            self._Variant(11, self._Color("Чорний")),
            self._Variant(12, self._Color("Білий")),
        ]
        variant_id, reason = self._resolve("чорний", variants)
        self.assertEqual(variant_id, 11)
        self.assertEqual(reason, "")

    def test_ambiguous_colour_returns_no_variant_with_a_reason(self):
        variants = [
            self._Variant(11, self._Color("Чорний")),
            self._Variant(12, self._Color("Чорний меланж")),
        ]
        variant_id, reason = self._resolve("чорний", variants)
        self.assertIsNone(variant_id)
        self.assertEqual(reason, "color_match_ambiguous")

    def test_unknown_colour_returns_a_reason(self):
        variants = [self._Variant(11, self._Color("Чорний"))]
        variant_id, reason = self._resolve("оливковий", variants)
        self.assertIsNone(variant_id)
        self.assertEqual(reason, "color_match_not_found")

    def test_no_selected_colour_returns_a_reason(self):
        variant_id, reason = resolve_client_color_variant(self._Client(""), 7)
        self.assertIsNone(variant_id)
        self.assertEqual(reason, "color_not_selected")


class CatalogMediaScopeTests(TestCase):
    """NEW-CAT-002 — фото приходит из того же resolved variant."""

    def test_stale_selection_revision_sends_nothing(self):
        selection = ig_catalog_media.select_catalog_media(
            (7,), selection_revision="3", expected_revision="4"
        )
        self.assertEqual(selection.state, ig_catalog_media.CatalogMediaState.AMBIGUOUS)
        self.assertEqual(selection.fallback_reason, "stale_selection_revision")
        self.assertEqual(selection.items, ())

    def test_matching_revision_is_not_treated_as_stale(self):
        selection = ig_catalog_media.select_catalog_media(
            (), selection_revision="4", expected_revision="4"
        )
        self.assertNotEqual(selection.fallback_reason, "stale_selection_revision")

    def test_selection_exposes_a_fallback_reason_field(self):
        selection = ig_catalog_media.select_catalog_media(())
        self.assertEqual(selection.fallback_reason, "")
