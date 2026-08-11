"""PDP continuity contracts for structured merchandising assignments."""

from pathlib import Path
from unittest.mock import patch

from django.test import TestCase
from django.test import SimpleTestCase
from django.urls import reverse

from fable5.models import (
    AudienceTag,
    ColorProfile,
    MerchCollection,
    ProductAudience,
    ProductMerchCollection,
)
from productcolors.models import Color, ProductColorVariant
from storefront.models import Category, Product
from storefront.seo_utils import StructuredDataGenerator
from storefront.services.product_merchandising import build_product_merchandising_context


class ProductMerchandisingContextTests(TestCase):
    def setUp(self):
        merchant_patcher = patch(
            "storefront.signals.generate_google_merchant_feed_task.apply_async"
        )
        indexnow_patcher = patch("storefront.signals.enqueue_indexnow_urls")
        self.addCleanup(merchant_patcher.stop)
        self.addCleanup(indexnow_patcher.stop)
        merchant_patcher.start()
        indexnow_patcher.start()

        self.category = Category.objects.create(
            name="Футболки",
            slug="tshirts",
            is_active=True,
        )
        self.product = Product.objects.create(
            title="Тестова футболка",
            slug="test-merch-tshirt",
            category=self.category,
            price=1090,
            status="published",
        )
        self.brigades, _ = MerchCollection.objects.get_or_create(
            slug="brigades",
            defaults={
                "kind": MerchCollection.Kind.THEME,
                "name_uk": "Бригади",
                "name_ru": "Бригады",
                "name_en": "Brigades",
                "order": 20,
            },
        )
        self.brigades.kind = MerchCollection.Kind.THEME
        self.brigades.name_uk = "Бригади"
        self.brigades.name_ru = "Бригады"
        self.brigades.name_en = "Brigades"
        self.brigades.order = 20
        self.brigades.parent = None
        self.brigades.indexable = False
        self.brigades.is_active = True
        self.brigades.save()
        self.brigade_225, _ = MerchCollection.objects.get_or_create(
            slug="225",
            defaults={
                "kind": MerchCollection.Kind.BRIGADE,
                "parent": self.brigades,
                "name_uk": "225 ОШП",
                "name_ru": "225 ОШП",
                "name_en": "225 Assault Regiment",
                "order": 21,
                "indexable": True,
            },
        )
        self.brigade_225.kind = MerchCollection.Kind.BRIGADE
        self.brigade_225.parent = self.brigades
        self.brigade_225.name_uk = "225 ОШП"
        self.brigade_225.name_ru = "225 ОШП"
        self.brigade_225.name_en = "225 Assault Regiment"
        self.brigade_225.order = 21
        self.brigade_225.indexable = True
        self.brigade_225.is_active = True
        self.brigade_225.save()
        self.unisex, _ = AudienceTag.objects.get_or_create(
            code="unisex",
            defaults={
                "label_uk": "Унісекс",
                "label_ru": "Унисекс",
                "label_en": "Unisex",
                "order": 10,
            },
        )
        self.unisex.label_uk = "Унісекс"
        self.unisex.label_ru = "Унисекс"
        self.unisex.label_en = "Unisex"
        self.unisex.order = 10
        self.unisex.is_active = True
        self.unisex.save()
        self.women, _ = AudienceTag.objects.get_or_create(
            code="women",
            defaults={
                "label_uk": "Жіночий",
                "label_ru": "Женский",
                "label_en": "Women",
                "order": 20,
            },
        )
        self.women.label_uk = "Жіночий"
        self.women.label_ru = "Женский"
        self.women.label_en = "Women"
        self.women.order = 20
        self.women.is_active = True
        self.women.save()
        ProductMerchCollection.objects.create(
            product=self.product,
            collection=self.brigades,
        )
        ProductMerchCollection.objects.create(
            product=self.product,
            collection=self.brigade_225,
            order=1,
        )
        ProductAudience.objects.create(product=self.product, tag=self.unisex)
        ProductAudience.objects.create(product=self.product, tag=self.women)

    def test_context_keeps_leaf_collection_and_all_structured_audiences(self):
        context = build_product_merchandising_context(self.product, language="uk")

        self.assertEqual([row["slug"] for row in context["collections"]], ["225"])
        self.assertEqual(
            [row["code"] for row in context["audiences"]],
            ["unisex", "women"],
        )
        self.assertEqual(context["analytics"]["collection_codes"], ["225"])
        self.assertEqual(
            context["analytics"]["audience_codes"],
            ["unisex", "women"],
        )

    def test_selected_variant_truth_controls_thermo_context(self):
        ordinary = build_product_merchandising_context(
            self.product,
            language="uk",
            selected_variant_context={"is_thermo": False},
        )
        thermo = build_product_merchandising_context(
            self.product,
            language="uk",
            selected_variant_context={
                "is_thermo": True,
                "thermo_note": "Реагує на тепло",
                "price_difference": 300,
                "price_delta_reason": "Термохромна тканина",
            },
        )

        self.assertFalse(ordinary["variant"]["is_thermo"])
        self.assertTrue(thermo["variant"]["is_thermo"])
        self.assertEqual(thermo["variant"]["price_difference"], 300)
        self.assertEqual(thermo["variant"]["price_reason"], "Термохромна тканина")

    def test_product_schema_uses_real_assignments_without_universal_style_claim(self):
        schema = StructuredDataGenerator.generate_product_schema(self.product)

        properties = {
            str(row.get("name")): str(row.get("value"))
            for row in schema["additionalProperty"]
        }
        self.assertNotIn("Стріт & Мілітарі", properties.values())
        self.assertEqual(properties["Колекція"], "225 ОШП")
        self.assertEqual(properties["Аудиторія"], "Унісекс, Жіночий")
        self.assertNotIn("suggestedGender", schema.get("audience", {}))

    def test_pdp_renders_context_after_price_and_exposes_analytics_codes(self):
        color = Color.objects.create(name="thermo black", primary_hex="#111111")
        variant = ProductColorVariant.objects.create(
            product=self.product,
            color=color,
            is_default=True,
        )
        ColorProfile.objects.create(
            color=color,
            is_thermo=True,
            thermo_note="Реагує на тепло",
        )

        response = self.client.get(reverse("product", args=[self.product.slug]))

        self.assertEqual(response.status_code, 200)
        context = response.context["product_merchandising_context"]
        self.assertTrue(context["variant"]["is_thermo"])
        html = response.content.decode()
        self.assertLess(html.index('class="tc-product-title"'), html.index('data-pdp-merchandising'))
        self.assertLess(html.index('class="tc-price-row"'), html.index('data-pdp-merchandising'))
        self.assertContains(response, 'data-merch-audiences="unisex|women"', html=False)
        self.assertContains(response, 'data-merch-collections="225"', html=False)
        self.assertContains(response, 'data-merch-thermo="1"', html=False)
        self.assertContains(response, "225 ОШП")
        self.assertNotContains(response, ">Бригади<", html=False)

    def test_mobile_merchandising_context_stays_compact_and_scrollable(self):
        css_path = (
            Path(__file__).resolve().parents[2]
            / "twocomms_django_theme"
            / "static"
            / "css"
            / "product-detail.css"
        )
        css = css_path.read_text(encoding="utf-8")
        mobile_css = css.split("@media (max-width: 767.98px)", 1)[1]

        self.assertIn(".tc-pdp-merchandising__item--thermo", mobile_css)
        self.assertIn("overflow-x: auto", mobile_css)
        self.assertNotIn("flex: 1 1 100%", mobile_css)

    def test_pdp_uses_fresh_merchandising_asset_release_key(self):
        response = self.client.get(reverse("product", args=[self.product.slug]))

        self.assertContains(
            response,
            "css/product-detail.css?v=20260811-gallery-v5",
            html=False,
        )
        self.assertContains(
            response,
            "js/product-detail.js?v=20260811-gallery-v6",
            html=False,
        )


class PdpMerchandisingLayoutContractTests(SimpleTestCase):
    def test_mobile_source_order_prioritizes_price_before_merchandising_context(self):
        template_path = (
            Path(__file__).resolve().parents[2]
            / "twocomms_django_theme"
            / "templates"
            / "pages"
            / "product_detail.html"
        )
        template = template_path.read_text(encoding="utf-8")

        self.assertLess(
            template.index('class="tc-product-kicker"'),
            template.index("data-pdp-merchandising"),
        )
        self.assertLess(
            template.index('class="tc-price-row"'),
            template.index("data-pdp-merchandising"),
        )
