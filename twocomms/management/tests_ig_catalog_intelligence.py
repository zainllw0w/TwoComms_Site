from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from management.services.ig_catalog_graph import build_catalog_graph
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
        self.category = Category.objects.create(name="T-shirts", slug="catalog-intelligence")
        self.product = Product.objects.create(
            title="Classic Raven T-shirt",
            slug="classic-tshirt",
            category=self.category,
            price=790,
            status=ProductStatus.PUBLISHED,
        )
        self.color = Color.objects.create(
            name="Black", primary_hex="#111111"
        )
        self.variant = ProductColorVariant.objects.create(
            product=self.product,
            color=self.color,
            slug="black",
            stock=3,
        )
        ProductFitOption.objects.create(
            product=self.product, code="classic", label="Classic", is_active=True
        )
        self.profile = ProductSalesSemanticProfile.objects.create(product=self.product)
        self.verifier = get_user_model().objects.create_user(username="catalog-verifier")


class TrustedProductReferenceTests(CatalogIntelligenceFixture):
    def test_exact_localized_storefront_url_resolves_published_slug(self):
        result = resolve_product_reference(
            "https://twocomms.shop/ru/product/classic-tshirt/?utm=x#size"
        )

        self.assertEqual(result.product_id, self.product.pk)
        self.assertTrue(result.is_exact)
        self.assertEqual(result.source, ReferenceSource.STOREFRONT)

    def test_lookalike_host_userinfo_port_and_unknown_slug_fail_closed(self):
        for value in (
            "https://twocomms.shop.evil.test/product/classic-tshirt/",
            "https://user@twocomms.shop/product/classic-tshirt/",
            "https://twocomms.shop:444/product/classic-tshirt/",
            "https://twocomms.shop/product/missing/",
        ):
            with self.subTest(value=value):
                self.assertFalse(resolve_product_reference(value).is_exact)

    def test_owned_color_and_fit_segments_are_preserved_as_constraints(self):
        result = resolve_product_reference(
            "https://twocomms.shop/product/classic-tshirt/black/classic/"
        )

        self.assertTrue(result.is_exact)
        self.assertEqual(dict(result.constraints), {"color": "black", "fit": "classic"})

    def test_unknown_option_segment_fails_closed(self):
        result = resolve_product_reference(
            "https://twocomms.shop/product/classic-tshirt/not-a-real-option/"
        )

        self.assertFalse(result.is_exact)
        self.assertEqual(result.reason, "invalid_product_option")

    def test_conflicting_urls_for_same_product_require_clarification(self):
        pink = Color.objects.create(name="Pink", primary_hex="#ff99aa")
        ProductColorVariant.objects.create(
            product=self.product, color=pink, slug="pink", stock=1
        )
        result = resolve_product_reference(
            "https://twocomms.shop/product/classic-tshirt/black/ "
            "https://twocomms.shop/product/classic-tshirt/pink/"
        )

        self.assertFalse(result.is_exact)
        self.assertEqual(result.reason, "conflicting_product_options")

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
    def test_draft_semantics_do_not_change_digest_but_verified_head_does(self):
        first = build_catalog_graph()
        create_semantic_revision(
            profile=self.profile,
            status="draft",
            source="free_text",
            aliases={"en": ["Raven candidate"]},
            traits={"back_decoration": "none"},
        )
        self.assertEqual(build_catalog_graph().digest, first.digest)

        create_semantic_revision(
            profile=self.profile,
            status="verified",
            source="manager",
            aliases={"en": ["Classic Raven T-shirt"]},
            traits={"back_decoration": "none"},
            verified_by=self.verifier,
            verified_at=timezone.now(),
        )
        self.profile.refresh_from_db()
        verified = build_catalog_graph()
        self.assertNotEqual(verified.digest, first.digest)
        self.assertEqual(verified.products[0].semantic_revision_id, self.profile.effective_revision_id)

    def test_bot_vision_metadata_never_enters_authoritative_graph(self):
        self.variant.metadata = {"bot_vision": {"summary": "invented raven claim"}}
        self.variant.save(update_fields=("metadata",))

        snapshot = build_catalog_graph()

        self.assertNotIn("invented raven claim", snapshot.canonical_json)
