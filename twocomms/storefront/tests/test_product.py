"""
Regression tests for storefront product detail and product AJAX endpoints.
"""

from __future__ import annotations

from pathlib import Path
import shutil
import tempfile
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from productcolors.models import Color, ProductColorImage, ProductColorVariant
from storefront.models import Category, Product, ProductFitOption, ProductImage

PNG_PIXEL = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


class ProductViewTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._media_root = tempfile.mkdtemp(prefix="product_view_tests_")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls._media_root, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        self.feed_task_patcher = patch(
            "storefront.signals.generate_google_merchant_feed_task.apply_async",
            return_value=None,
        )
        self.feed_task_mock = self.feed_task_patcher.start()
        self.addCleanup(self.feed_task_patcher.stop)
        self.image_task_patcher = patch(
            "storefront.signals.optimize_image_field_task.delay",
            return_value=None,
        )
        self.optimize_image_mock = self.image_task_patcher.start()
        self.addCleanup(self.image_task_patcher.stop)
        self.category = Category.objects.create(
            name="Test Category",
            slug="test-category",
            is_active=True,
        )
        self.product = Product.objects.create(
            title="Test Product",
            slug="test-product",
            category=self.category,
            price=1000,
            description="Test description",
            status="published",
        )

    def _image_file(self, name: str) -> SimpleUploadedFile:
        return SimpleUploadedFile(name, PNG_PIXEL, content_type="image/png")


class ProductHomepageImageTests(ProductViewTestCase):
    def test_homepage_image_prefers_home_card_image(self):
        with self.settings(MEDIA_ROOT=self._media_root):
            self.product.main_image = self._image_file("main.png")
            self.product.home_card_image = self._image_file("home-card.png")
            self.product.save(update_fields=["main_image", "home_card_image"])

        self.assertTrue(self.product.homepage_image.name.endswith("home-card.png"))

    def test_homepage_image_falls_back_to_display_image_chain(self):
        with self.settings(MEDIA_ROOT=self._media_root):
            color = Color.objects.create(name="Black", primary_hex="#000000")
            variant = ProductColorVariant.objects.create(
                product=self.product,
                color=color,
                order=0,
                is_default=True,
            )
            ProductColorImage.objects.create(
                variant=variant,
                image=self._image_file("variant-home-fallback.png"),
                order=0,
            )

        self.assertTrue(self.product.homepage_image.name.endswith("variant-home-fallback.png"))

    def test_home_card_image_enqueues_optimization(self):
        with self.settings(MEDIA_ROOT=self._media_root):
            self.product.home_card_image = self._image_file("home-card-opt.png")
            self.product.save(update_fields=["home_card_image"])

        self.optimize_image_mock.assert_any_call("storefront.Product", self.product.pk, "home_card_image")


class ProductDetailTests(ProductViewTestCase):
    def test_product_detail_page_loads_published_product(self):
        response = self.client.get(reverse("product", args=[self.product.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["product"].pk, self.product.pk)
        self.assertContains(response, self.product.title)
        self.assertEqual(response.context["breadcrumbs"][-1]["name"], self.product.title)

    def test_product_detail_renders_single_share_action_and_delivery_tab(self):
        response = self.client.get(reverse("product", args=[self.product.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-share-action="native"', html=False)
        self.assertNotContains(response, 'class="tc-share-row"', html=False)
        self.assertNotContains(response, 'data-share-action="telegram"', html=False)
        self.assertNotContains(response, 'data-share-action="facebook"', html=False)
        self.assertNotContains(response, 'data-share-action="x"', html=False)
        self.assertNotContains(response, 'data-share-action="copy"', html=False)
        self.assertContains(response, 'data-pdp-tab="delivery"', html=False)
        self.assertContains(response, 'id="panel-delivery"', html=False)
        self.assertContains(response, 'data-add-to-cart=', html=False)
        self.assertContains(response, 'product-detail.css?v=20260428-pdp-share-solo-v6', html=False)
        self.assertContains(response, 'product-media-fit.css?v=20260428-media-fit-v1', html=False)
        self.assertContains(response, 'product-detail.js?v=20260428-image-sources-v1', html=False)
        self.assertContains(response, 'product-media-fit.js?v=20260428-media-fit-v1', html=False)

    def test_product_detail_renders_description_collapse_hooks(self):
        self.product.full_description = "\n".join(
            [
                "ВАЙБ: КРИЖАНА СВІЖІСТЬ",
                "Колір має значення. Ми обрали цей відтінок для чистого образу.",
                "Тканина рівня люкс, м'яка і приємна до тіла.",
                "Посилені шви та еластичні манжети для довговічності.",
            ]
            * 3
        )
        self.product.save(update_fields=["full_description"])

        response = self.client.get(reverse("product", args=[self.product.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ВАЙБ: КРИЖАНА СВІЖІСТЬ")
        self.assertContains(response, 'class="tc-desc-collapse is-collapsible is-collapsed"', html=False)
        self.assertContains(response, 'data-pdp-description-collapse', html=False)
        self.assertContains(response, 'data-pdp-description-content', html=False)
        self.assertContains(response, 'data-pdp-description-toggle', html=False)
        self.assertContains(response, 'aria-expanded="false"', html=False)
        self.assertContains(response, f'aria-controls="tc-desc-content-{self.product.id}"', html=False)
        self.assertContains(response, "<noscript>", html=False)

    def test_product_detail_css_keeps_desktop_sizes_in_one_scroll_row(self):
        css_path = Path(__file__).resolve().parents[2] / "twocomms_django_theme/static/css/product-detail.css"
        css = css_path.read_text(encoding="utf-8")

        self.assertIn("display: flex", css)
        self.assertIn("flex-wrap: nowrap", css)
        self.assertIn("flex: 0 0 68px", css)
        self.assertIn(".btn-check:focus-visible + .tc-size-option", css)
        self.assertNotIn("grid-template-columns: repeat(5, 68px)", css)

    def test_product_detail_media_fit_assets_define_wide_only_cover_mode(self):
        static_root = Path(__file__).resolve().parents[2] / "twocomms_django_theme/static"
        css = (static_root / "css/product-media-fit.css").read_text(encoding="utf-8")
        js = (static_root / "js/product-media-fit.js").read_text(encoding="utf-8")

        self.assertIn(".tc-media-stage.tc-media-fit-wide .tc-media-hero-img", css)
        self.assertIn("object-fit: cover", css)
        self.assertIn("object-fit: contain", css)
        self.assertIn("const WIDE_RATIO = 1.42", js)
        self.assertIn("MutationObserver", js)

    def test_product_detail_returns_404_for_unpublished_product(self):
        self.product.status = "draft"
        self.product.save(update_fields=["status"])

        response = self.client.get(reverse("product", args=[self.product.slug]))

        self.assertEqual(response.status_code, 404)

    def test_product_detail_moves_preselected_color_to_front(self):
        black = Color.objects.create(name="Black", primary_hex="#000000")
        white = Color.objects.create(name="White", primary_hex="#FFFFFF")
        ProductColorVariant.objects.create(
            product=self.product,
            color=black,
            order=0,
            is_default=True,
        )
        selected_variant = ProductColorVariant.objects.create(
            product=self.product,
            color=white,
            order=1,
            is_default=False,
        )

        response = self.client.get(
            reverse("product", args=[self.product.slug]),
            {"color": str(selected_variant.pk)},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["preselected_color"], selected_variant.pk)
        self.assertEqual(response.context["color_variants"][0]["id"], selected_variant.pk)

    def test_product_detail_shows_fit_selector_for_tshirts(self):
        tshirt_category = Category.objects.create(
            name="Футболки",
            slug="futbolki",
            is_active=True,
        )
        product = Product.objects.create(
            title="Футболка тестова",
            slug="test-tshirt-fit",
            category=tshirt_category,
            price=1000,
            description="Fit selector coverage.",
            status="published",
        )
        ProductFitOption.objects.create(
            product=product,
            code="classic",
            label="Класичний",
            description="Прямий крій, стандартна посадка",
            is_default=True,
            order=0,
        )
        ProductFitOption.objects.create(
            product=product,
            code="oversize",
            label="Оверсайз",
            description="Вільний крій, спущене плече",
            order=1,
        )

        response = self.client.get(reverse("product", args=[product.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-fit-selector', html=False)
        self.assertContains(response, "Класичний")
        self.assertContains(response, "Оверсайз")

    def test_product_detail_preselects_fit_from_url_for_tshirts(self):
        tshirt_category = Category.objects.create(
            name="Футболки",
            slug="futbolki-preselect",
            is_active=True,
        )
        product = Product.objects.create(
            title="Футболка з посадкою",
            slug="test-tshirt-fit-preselected",
            category=tshirt_category,
            price=1000,
            description="Fit selector preselect coverage.",
            status="published",
        )
        ProductFitOption.objects.create(
            product=product,
            code="classic",
            label="Класичний",
            is_default=True,
            order=0,
        )
        ProductFitOption.objects.create(
            product=product,
            code="oversize",
            label="Оверсайз",
            order=1,
        )

        response = self.client.get(reverse("product", args=[product.slug]), {"fit": "oversize"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["preselected_fit_code"], "oversize")
        self.assertContains(response, 'id="fit-oversize"', html=False)
        self.assertContains(response, 'value="oversize"', html=False)

    def test_product_detail_hides_fit_selector_for_non_tshirts(self):
        longsleeve_category = Category.objects.create(
            name="Лонгсліви",
            slug="longsleeve",
            is_active=True,
        )
        product = Product.objects.create(
            title="Лонгслів тестовий",
            slug="test-longsleeve-fit-hidden",
            category=longsleeve_category,
            price=1000,
            description="Fit selector hidden coverage.",
            status="published",
        )
        ProductFitOption.objects.create(
            product=product,
            code="classic",
            label="Класичний",
            description="Прямий крій",
            is_default=True,
            order=0,
        )

        response = self.client.get(reverse("product", args=[product.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'data-fit-selector', html=False)
        self.assertNotContains(response, "Оверсайз")


class GetProductImagesTests(ProductViewTestCase):
    def test_get_product_images_returns_main_and_gallery(self):
        with self.settings(MEDIA_ROOT=self._media_root):
            self.product.main_image = self._image_file("main.png")
            self.product.save(update_fields=["main_image"])
            ProductImage.objects.create(
                product=self.product,
                image=self._image_file("gallery.png"),
                order=0,
            )

            response = self.client.get(reverse("get_product_images", args=[self.product.pk]))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["count"], 2)
        self.assertTrue(payload["images"][0]["is_main"])
        self.assertFalse(payload["images"][1]["is_main"])

    def test_get_product_images_returns_404_for_missing_product(self):
        response = self.client.get(reverse("get_product_images", args=[99999]))

        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.json()["success"])


class GetProductVariantsTests(ProductViewTestCase):
    def test_get_product_variants_returns_current_contract(self):
        with self.settings(MEDIA_ROOT=self._media_root):
            default_color = Color.objects.create(name="Black", primary_hex="#000000")
            secondary_color = Color.objects.create(
                name="Split",
                primary_hex="#FFFFFF",
                secondary_hex="#111111",
            )
            default_variant = ProductColorVariant.objects.create(
                product=self.product,
                color=default_color,
                order=0,
                is_default=True,
            )
            secondary_variant = ProductColorVariant.objects.create(
                product=self.product,
                color=secondary_color,
                order=1,
                is_default=False,
            )
            ProductColorImage.objects.create(
                variant=secondary_variant,
                image=self._image_file("variant.png"),
                alt_text="Side",
                order=0,
            )

            response = self.client.get(reverse("get_product_variants", args=[self.product.pk]))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["count"], 2)

        variants_by_id = {variant["id"]: variant for variant in payload["variants"]}
        self.assertEqual(variants_by_id[default_variant.pk]["primary_hex"], "#000000")
        self.assertTrue(variants_by_id[default_variant.pk]["is_default"])
        self.assertEqual(variants_by_id[secondary_variant.pk]["secondary_hex"], "#111111")
        self.assertEqual(len(variants_by_id[secondary_variant.pk]["images"]), 1)

    def test_get_product_variants_returns_optimized_image_sources(self):
        with self.settings(MEDIA_ROOT=self._media_root):
            color = Color.objects.create(name="Optimized", primary_hex="#123456")
            variant = ProductColorVariant.objects.create(
                product=self.product,
                color=color,
                order=0,
                is_default=True,
            )
            color_image = ProductColorImage.objects.create(
                variant=variant,
                image=self._image_file("variant-optimized.png"),
                alt_text="Optimized",
                order=0,
            )
            image_path = Path(color_image.image.path)
            optimized_dir = image_path.parent / "optimized"
            optimized_dir.mkdir(parents=True, exist_ok=True)
            for suffix in ("640w.avif", "640w.webp"):
                (optimized_dir / f"{image_path.stem}_{suffix}").write_bytes(PNG_PIXEL)
            for extension in ("avif", "webp"):
                (optimized_dir / f"{image_path.stem}.{extension}").write_bytes(PNG_PIXEL)

            response = self.client.get(reverse("get_product_variants", args=[self.product.pk]))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        image_payload = payload["variants"][0]["images"][0]

        self.assertIsInstance(image_payload, dict)
        self.assertTrue(image_payload["original_url"].endswith("/product_colors/variant-optimized.png"))
        self.assertIn("/optimized/variant-optimized_640w.avif 640w", image_payload["avif_srcset"])
        self.assertIn("/optimized/variant-optimized_640w.webp 640w", image_payload["webp_srcset"])
        self.assertTrue(image_payload["url"].endswith("/optimized/variant-optimized_640w.webp"))

    def test_get_product_variants_returns_404_for_missing_product(self):
        response = self.client.get(reverse("get_product_variants", args=[99999]))

        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.json()["success"])


class QuickViewTests(ProductViewTestCase):
    def test_quick_view_returns_json_html_fragment(self):
        response = self.client.get(reverse("quick_view", args=[self.product.pk]))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertIn(self.product.title, payload["html"])
        self.assertIn(str(self.product.final_price), payload["html"])

    def test_quick_view_returns_404_for_unpublished_product(self):
        self.product.status = "draft"
        self.product.save(update_fields=["status"])

        response = self.client.get(reverse("quick_view", args=[self.product.pk]))

        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.json()["success"])
