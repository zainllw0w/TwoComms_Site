from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from fable5.models import (
    ColorProfile,
    GarmentFlow,
    GarmentFlowCategory,
    ProductOptionProfile,
    VariantDetails,
    VariantFitRule,
)
from management.services.ig_catalog_candidates import rank_candidates
from management.services.ig_catalog_graph import build_catalog_graph
from management.services.ig_commerce_types import CommerceTurnRequest
from management.services.ig_product_references import (
    ReferenceSource,
    resolve_product_reference,
)
from productcolors.models import Color, ProductColorVariant
from storefront.models import (
    Category,
    Product,
    ProductFitOption,
    ProductSalesSemanticProfile,
    ProductStatus,
)
from storefront.services.product_sales_semantics import create_semantic_revision


class CatalogIntelligenceFixture(TestCase):
    def setUp(self):
        self.category = Category.objects.create(
            name="T-shirts",
            slug="catalog-intelligence",
        )
        self.product = Product.objects.create(
            title="Classic Raven T-shirt",
            slug="classic-tshirt",
            category=self.category,
            price=790,
            status=ProductStatus.PUBLISHED,
        )
        self.color = Color.objects.create(name="Black", primary_hex="#111111")
        self.variant = ProductColorVariant.objects.create(
            product=self.product,
            color=self.color,
            slug="black",
            stock=3,
            price_override=790,
        )
        ProductFitOption.objects.create(
            product=self.product,
            code="classic",
            label="Classic",
            is_active=True,
            is_default=True,
        )
        self.profile = ProductSalesSemanticProfile.objects.create(product=self.product)
        self.verifier = get_user_model().objects.create_user(username="catalog-verifier")

    def verify_semantics(self, *, aliases=None, traits=None, profile=None):
        profile = profile or self.profile
        return create_semantic_revision(
            profile=profile,
            status="verified",
            source="manager",
            aliases=aliases or {"en": [profile.product.title]},
            traits=traits or {},
            verified_by=self.verifier,
            verified_at=timezone.now(),
        )


class TrustedProductReferenceTests(CatalogIntelligenceFixture):
    def test_exact_localized_storefront_url_resolves_published_slug(self):
        result = resolve_product_reference(
            "https://twocomms.shop/ru/product/classic-tshirt/?utm=x#size"
        )

        self.assertEqual(result.product_id, self.product.pk)
        self.assertTrue(result.is_exact)
        self.assertEqual(result.source, ReferenceSource.STOREFRONT)

    def test_lookalike_host_userinfo_port_http_and_unknown_slug_fail_closed(self):
        for value in (
            "https://twocomms.shop.evil.test/product/classic-tshirt/",
            "https://user@twocomms.shop/product/classic-tshirt/",
            "https://twocomms.shop:444/product/classic-tshirt/",
            "http://twocomms.shop/product/classic-tshirt/",
            "https://twocomms.shop/product/missing/",
        ):
            with self.subTest(value=value):
                self.assertFalse(resolve_product_reference(value).is_exact)

    def test_standard_explicit_https_port_is_trusted(self):
        result = resolve_product_reference(
            "https://twocomms.shop:443/product/classic-tshirt/"
        )

        self.assertTrue(result.is_exact)
        self.assertEqual(result.product_id, self.product.pk)

    def test_owned_color_and_fit_segments_are_preserved_as_constraints(self):
        result = resolve_product_reference(
            "https://twocomms.shop/product/classic-tshirt/black/classic/"
        )

        self.assertTrue(result.is_exact)
        self.assertEqual(dict(result.constraints), {"color": "black", "fit": "classic"})

    def test_duplicate_or_unknown_option_segment_fails_closed(self):
        for path in ("black/black/", "not-a-real-option/"):
            with self.subTest(path=path):
                result = resolve_product_reference(
                    f"https://twocomms.shop/product/classic-tshirt/{path}"
                )
                self.assertFalse(result.is_exact)
                self.assertEqual(result.reason, "invalid_product_option")

    def test_conflicting_urls_for_same_product_require_clarification(self):
        pink = Color.objects.create(name="Pink", primary_hex="#ff99aa")
        ProductColorVariant.objects.create(
            product=self.product,
            color=pink,
            slug="pink",
            stock=1,
        )
        result = resolve_product_reference(
            "https://twocomms.shop/product/classic-tshirt/black/ "
            "https://twocomms.shop/product/classic-tshirt/pink/"
        )

        self.assertFalse(result.is_exact)
        self.assertEqual(result.reason, "conflicting_product_options")

    def test_urls_for_different_products_require_clarification(self):
        other = Product.objects.create(
            title="Other",
            slug="other-product",
            category=self.category,
            price=500,
            status=ProductStatus.PUBLISHED,
        )
        result = resolve_product_reference(
            "https://twocomms.shop/product/classic-tshirt/ "
            f"https://twocomms.shop/product/{other.slug}/"
        )

        self.assertFalse(result.is_exact)
        self.assertEqual(result.reason, "multiple_products_require_clarification")

    def test_instagram_post_or_reel_is_evidence_not_an_invented_sku(self):
        for url in (
            "https://www.instagram.com/p/ABC123/",
            "https://instagram.com/reel/XYZ987/?igsh=abc",
        ):
            with self.subTest(url=url):
                result = resolve_product_reference(url)
                self.assertFalse(result.is_exact)
                self.assertEqual(result.source, ReferenceSource.INSTAGRAM_POST)
                self.assertEqual(result.reason, "instagram_catalog_match_required")
                self.assertTrue(result.external_reference)

    def test_screenshot_match_remains_a_candidate_until_verified(self):
        result = resolve_product_reference(
            "",
            media_evidence=[{
                "kind": "screenshot",
                "product_id": self.product.pk,
                "confidence": 0.99,
                "verified_mapping": False,
            }],
        )

        self.assertFalse(result.is_exact)
        self.assertEqual(result.source, ReferenceSource.SCREENSHOT)
        self.assertEqual(result.candidate_product_ids, (self.product.pk,))
        self.assertEqual(result.reason, "visual_match_requires_confirmation")

    def test_verified_instagram_media_mapping_can_resolve_one_product(self):
        result = resolve_product_reference(
            "https://www.instagram.com/p/ABC123/",
            media_evidence=[{
                "kind": "instagram_post",
                "external_reference": "p:ABC123",
                "product_id": self.product.pk,
                "verified_mapping": True,
            }],
        )

        self.assertTrue(result.is_exact)
        self.assertEqual(result.product_id, self.product.pk)
        self.assertEqual(result.source, ReferenceSource.INSTAGRAM_POST)


class CatalogGraphTests(CatalogIntelligenceFixture):
    def test_thermo_only_graph_uses_sellable_1450_and_never_serializes_base_1090(self):
        self.product.price = 1090
        self.product.save(update_fields=("price",))
        self.variant.price_override = 1050
        self.variant.save(update_fields=("price_override",))
        ColorProfile.objects.create(color=self.color, is_thermo=True)
        VariantDetails.objects.create(
            variant=self.variant,
            price_delta=400,
            price_delta_reason="thermo",
        )
        VariantFitRule.objects.create(
            variant=self.variant,
            fit_code="classic",
            is_enabled=True,
        )

        graph = build_catalog_graph()
        product = graph.products[0]

        self.assertEqual(product.pricing.minimum, Decimal("1450.00"))
        self.assertEqual(product.pricing.maximum, Decimal("1450.00"))
        self.assertEqual(product.pricing.display, "1450")
        self.assertTrue(product.pricing.configurations[0].is_thermo)
        self.assertNotIn('"1090"', graph.canonical_json)

        ranked = rank_candidates(
            graph,
            CommerceTurnRequest(exact_product_id=self.product.pk),
        )
        self.assertEqual(ranked.candidates[0].pricing.display, "1450")
        self.assertNotIn('"1090"', ranked.canonical_json)

    def test_fit_constraint_reduces_price_range_to_surviving_configurations(self):
        self.product.price = 800
        self.product.save(update_fields=("price",))
        self.variant.price_override = 800
        self.variant.save(update_fields=("price_override",))
        ProductFitOption.objects.create(
            product=self.product,
            code="oversize",
            label="Oversize",
            is_active=True,
        )
        ProductOptionProfile.objects.create(
            product=self.product,
            option_key="fit=oversize",
            option_values={"fit": "oversize"},
            price_delta=150,
            price_delta_reason="oversize blank",
        )

        graph = build_catalog_graph()
        self.assertEqual(graph.products[0].pricing.display, "800-950")

        classic = rank_candidates(
            graph,
            CommerceTurnRequest(
                exact_product_id=self.product.pk,
                hard={"fit": "classic"},
            ),
        )
        oversize = rank_candidates(
            graph,
            CommerceTurnRequest(
                exact_product_id=self.product.pk,
                hard={"fit": "oversize"},
            ),
        )
        self.assertEqual(classic.candidates[0].pricing.display, "800")
        self.assertEqual(oversize.candidates[0].pricing.display, "950")
        self.assertNotIn('"800.00"', oversize.canonical_json)

    def test_matrix_over_limit_has_unknown_price_without_base_fallback(self):
        self.product.price = 1090
        self.product.save(update_fields=("price",))
        self.variant.price_override = 1450
        self.variant.save(update_fields=("price_override",))
        flow = GarmentFlow.objects.create(
            code="catalog-intelligence-large-matrix",
            name="Large matrix",
            axes=[{
                "code": f"option{index}",
                "label": f"Option {index}",
                "options": [
                    {"code": "a", "label": "A"},
                    {"code": "b", "label": "B"},
                ],
            } for index in range(8)],
        )
        GarmentFlowCategory.objects.create(flow=flow, category=self.category)

        with self.assertLogs("management.services.ig_catalog_pricing", level="WARNING"):
            graph = build_catalog_graph()

        pricing = graph.products[0].pricing
        self.assertEqual(pricing.configurations, ())
        self.assertIsNone(pricing.minimum)
        self.assertIsNone(pricing.maximum)
        self.assertFalse(pricing.exact)
        self.assertEqual(pricing.display, "")
        self.assertNotIn('"1090"', graph.canonical_json)

        ranked = rank_candidates(
            graph,
            CommerceTurnRequest(exact_product_id=self.product.pk),
        )
        self.assertEqual(ranked.candidates[0].pricing.configurations, ())
        self.assertNotIn('"1090"', ranked.canonical_json)

    def test_authoritative_price_change_changes_digest(self):
        first = build_catalog_graph()
        self.variant.price_override = 890
        self.variant.save(update_fields=("price_override",))
        second = build_catalog_graph()
        self.assertNotEqual(second.digest, first.digest)

        VariantDetails.objects.create(variant=self.variant, price_delta=60)
        third = build_catalog_graph()
        self.assertNotEqual(third.digest, second.digest)

    def test_draft_semantics_and_bot_vision_do_not_change_digest_but_verified_head_does(self):
        first = build_catalog_graph()
        create_semantic_revision(
            profile=self.profile,
            status="draft",
            source="free_text",
            aliases={"en": ["Raven candidate"]},
            traits={"back_decoration": "none"},
        )
        self.variant.metadata = {"bot_vision": {"summary": "invented raven claim"}}
        self.variant.save(update_fields=("metadata",))
        unchanged = build_catalog_graph()
        self.assertEqual(unchanged.digest, first.digest)
        self.assertNotIn("invented raven claim", unchanged.canonical_json)

        self.verify_semantics(
            aliases={"en": ["Classic Raven T-shirt"]},
            traits={"back_decoration": "none"},
        )
        self.profile.refresh_from_db()
        verified = build_catalog_graph()
        self.assertNotEqual(verified.digest, first.digest)
        self.assertEqual(
            verified.products[0].semantic_revision_id,
            self.profile.effective_revision_id,
        )

    def test_graph_prepares_pricing_once_and_has_bounded_query_growth(self):
        for index in range(3):
            product = Product.objects.create(
                title=f"Bounded {index}",
                slug=f"bounded-{index}",
                category=self.category,
                price=800,
                status=ProductStatus.PUBLISHED,
            )
            ProductColorVariant.objects.create(
                product=product,
                color=Color.objects.create(
                    name=f"Color {index}",
                    primary_hex=f"#{index + 1:06x}",
                ),
                price_override=800 + index,
            )

        from management.services import ig_catalog_graph

        real_prepare = ig_catalog_graph.prepare_pricing_context
        with patch.object(
            ig_catalog_graph,
            "prepare_pricing_context",
            wraps=real_prepare,
        ) as prepare:
            with CaptureQueriesContext(connection) as captured:
                graph = build_catalog_graph()

        self.assertEqual(len(graph.products), 4)
        prepare.assert_called_once()
        self.assertLessEqual(
            len(captured),
            35,
            f"catalog graph query budget exceeded: {len(captured)}",
        )


class CatalogCandidateTests(CatalogIntelligenceFixture):
    def test_color_constraint_removes_other_variant_price_from_candidate(self):
        self.product.price = 1090
        self.product.save(update_fields=("price",))
        self.variant.price_override = 1090
        self.variant.save(update_fields=("price_override",))
        thermo_color = Color.objects.create(
            name="Thermo green",
            primary_hex="#55aa77",
        )
        thermo = ProductColorVariant.objects.create(
            product=self.product,
            color=thermo_color,
            slug="thermo-green",
            price_override=1050,
        )
        ColorProfile.objects.create(color=thermo_color, is_thermo=True)
        VariantDetails.objects.create(
            variant=thermo,
            price_delta=400,
            price_delta_reason="thermo",
        )

        graph = build_catalog_graph()
        self.assertEqual(graph.products[0].pricing.display, "1090-1450")
        reference = resolve_product_reference(
            "https://twocomms.shop/product/classic-tshirt/thermo-green/"
        )
        result = rank_candidates(
            graph,
            CommerceTurnRequest(
                exact_product_id=reference.product_id,
                hard=dict(reference.constraints),
            ),
        )

        self.assertEqual(result.candidates[0].pricing.display, "1450")
        self.assertNotIn('"1090.00"', result.canonical_json)

    def test_trusted_url_constraints_filter_candidate_price_snapshot(self):
        ProductFitOption.objects.create(
            product=self.product,
            code="oversize",
            label="Oversize",
            is_active=True,
        )
        ProductOptionProfile.objects.create(
            product=self.product,
            option_key="fit=oversize",
            option_values={"fit": "oversize"},
            price_delta=150,
        )
        reference = resolve_product_reference(
            "https://twocomms.shop/product/classic-tshirt/black/oversize/"
        )

        result = rank_candidates(
            build_catalog_graph(),
            CommerceTurnRequest(
                exact_product_id=reference.product_id,
                hard=dict(reference.constraints),
            ),
        )

        self.assertTrue(result.auto_select)
        self.assertEqual(result.selected_product_id, self.product.pk)
        self.assertEqual(result.candidates[0].pricing.display, "940")
        self.assertEqual(
            dict(result.candidates[0].constraints),
            {"color": "black", "fit": "oversize"},
        )

    def test_exact_verified_alias_title_then_hard_count_and_id_define_stable_order(self):
        self.verify_semantics(
            aliases={"en": ["Raven exact alias"]},
            traits={"back_decoration": "none", "front_decoration": "logo"},
        )
        second = Product.objects.create(
            title="Raven exact alias",
            slug="raven-second",
            category=self.category,
            price=790,
            status=ProductStatus.PUBLISHED,
        )
        second_color = Color.objects.create(name="Gray", primary_hex="#777777")
        ProductColorVariant.objects.create(
            product=second,
            color=second_color,
            price_override=790,
        )
        second_profile = ProductSalesSemanticProfile.objects.create(product=second)
        self.verify_semantics(
            profile=second_profile,
            aliases={"en": ["Other"]},
            traits={"back_decoration": "none"},
        )

        result = rank_candidates(
            build_catalog_graph(),
            CommerceTurnRequest(
                query="Raven exact alias",
                hard={"back_decoration": "none"},
            ),
        )

        self.assertEqual(
            [candidate.product_id for candidate in result.candidates[:2]],
            [self.product.pk, second.pk],
        )
        self.assertFalse(result.auto_select)

    def test_hard_mismatch_is_never_relaxed_and_visible_candidates_are_capped(self):
        self.verify_semantics(traits={"back_decoration": "none"})
        for index in range(4):
            product = Product.objects.create(
                title=f"Candidate {index}",
                slug=f"candidate-{index}",
                category=self.category,
                price=500,
                status=ProductStatus.PUBLISHED,
            )
            color = Color.objects.create(
                name=f"Candidate color {index}",
                primary_hex=f"#{index + 16:06x}",
            )
            ProductColorVariant.objects.create(product=product, color=color, price_override=500)
            profile = ProductSalesSemanticProfile.objects.create(product=product)
            self.verify_semantics(profile=profile, traits={"back_decoration": "none"})

        result = rank_candidates(
            build_catalog_graph(),
            CommerceTurnRequest(hard={"back_decoration": "none"}),
        )
        self.assertEqual(len(result.candidates), 3)

        impossible = rank_candidates(
            build_catalog_graph(),
            CommerceTurnRequest(
                exact_product_id=self.product.pk,
                hard={"back_decoration": "large"},
            ),
        )
        self.assertEqual(impossible.candidates, ())
        self.assertFalse(impossible.auto_select)
        self.assertIsNone(impossible.selected_product_id)
