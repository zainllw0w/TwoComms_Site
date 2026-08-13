"""
Regression tests for storefront product detail and product AJAX endpoints.
"""

from __future__ import annotations

from html.parser import HTMLParser
import json
from pathlib import Path
import shutil
import tempfile
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import translation

from orders.models import Order, OrderItem
from product_catalog.models import ImageOptimizationJob
from productcolors.models import Color, ProductColorImage, ProductColorVariant
from reviews.models import Review, ReviewStatus
from storefront.models import Category, Product, ProductFAQ, ProductFitOption, ProductImage
from storefront.views.product import _dedupe_product_faq_items, get_product_variants

PNG_PIXEL = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)

PRODUCT_DETAIL_TEST_CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "product-detail-tests-default",
    },
    "fragments": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "product-detail-tests-fragments",
    },
    "ratelimit": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "product-detail-tests-ratelimit",
    },
}

PDP_HERO_RENDER_TEST_SETTINGS = {
    "CACHES": PRODUCT_DETAIL_TEST_CACHES,
    "COMPRESS_ENABLED": False,
    "COMPRESS_OFFLINE": False,
    "NOVA_POSHTA_FALLBACK_ENABLED": False,
    "STORAGES": {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    },
}


class _ProductHeroParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hero_attributes = {}
        self.hero_avif_srcsets = []
        self.preload_image_srcsets = []
        self.meta_content = {}
        self._current_picture_avif_srcsets = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "picture":
            self._current_picture_avif_srcsets = []
        if tag == "source" and attributes.get("type") == "image/avif":
            self._current_picture_avif_srcsets.append(attributes.get("srcset", ""))
        if tag == "img" and attributes.get("id") == "mainProductImage":
            self.hero_attributes = attributes
            self.hero_avif_srcsets = list(self._current_picture_avif_srcsets)
        if (
            tag == "link"
            and attributes.get("rel") == "preload"
            and attributes.get("as") == "image"
        ):
            self.preload_image_srcsets.append(attributes.get("imagesrcset", ""))
        if tag == "meta":
            key = attributes.get("property") or attributes.get("name")
            if key in {"og:image", "og:image:alt", "twitter:image", "twitter:image:alt"}:
                self.meta_content[key] = attributes.get("content", "")

    def handle_endtag(self, tag):
        if tag == "picture":
            self._current_picture_avif_srcsets = []


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

        job = ImageOptimizationJob.objects.get(
            model_label="storefront.product",
            object_id=self.product.pk,
            field_name="home_card_image",
        )
        self.assertTrue(job.source_name.endswith("home-card-opt.png"))
        self.assertEqual(job.status, ImageOptimizationJob.Status.PENDING)
        self.assertEqual(job.stage, "queued")
        self.assertEqual(job.progress, 0)


class ProductDetailTests(ProductViewTestCase):
    def test_product_faq_items_drop_exact_duplicate_pairs_deterministically(self):
        ProductFAQ.objects.create(
            product=self.product,
            question="  Where is the print? ",
            answer="Printed on the back.",
            order=0,
            is_active=True,
        )
        ProductFAQ.objects.create(
            product=self.product,
            question="where is the print?",
            answer="Printed   on the back.",
            order=1,
            is_active=True,
        )

        items = _dedupe_product_faq_items(self.product)

        self.assertEqual(items, [
            {"question": "Where is the print?", "answer": "Printed on the back."},
        ])

    def _configure_selected_color_hero(self, prefix):
        self.product.main_image = self._image_file(f"{prefix}-base.png")
        self.product.save(update_fields=["main_image"])

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
        selected_image_name = f"{prefix}-white.png"
        ProductColorImage.objects.create(
            variant=selected_variant,
            image=self._image_file(selected_image_name),
            alt_text="White hero",
            order=0,
        )
        optimized_dir = Path(self._media_root) / "product_colors" / "optimized"
        optimized_dir.mkdir(parents=True, exist_ok=True)
        (optimized_dir / f"{prefix}-white_768w.avif").write_bytes(b"avif")
        return selected_variant, f"{prefix}-base.png", selected_image_name

    def _assert_selected_color_hero(
        self,
        response,
        base_image_name,
        selected_image_name,
        expected_alt="White hero",
    ):
        parser = _ProductHeroParser()
        parser.feed(response.content.decode())

        self.assertTrue(parser.hero_attributes)
        hero_src = parser.hero_attributes.get("src") or ""
        hero_alt = parser.hero_attributes.get("alt") or ""
        self.assertTrue(hero_src.endswith(selected_image_name))
        self.assertNotIn(base_image_name, hero_src)
        self.assertIn(expected_alt, hero_alt)
        self.assertTrue(
            any(
                f"{Path(selected_image_name).stem}_768w.avif 768w" in srcset
                for srcset in parser.preload_image_srcsets
            )
        )
        self.assertTrue(
            any(
                f"{Path(selected_image_name).stem}_768w.avif 768w" in srcset
                for srcset in parser.hero_avif_srcsets
            )
        )

    def _assert_selected_color_social_metadata(self, response, selected_image_name):
        parser = _ProductHeroParser()
        parser.feed(response.content.decode())

        self.assertIn(selected_image_name, parser.meta_content["og:image"])
        self.assertEqual(parser.meta_content["og:image:alt"], "White hero")
        self.assertIn(selected_image_name, parser.meta_content["twitter:image"])
        self.assertEqual(parser.meta_content["twitter:image:alt"], "White hero")

    @override_settings(**PDP_HERO_RENDER_TEST_SETTINGS)
    def test_ru_and_en_selected_color_media_alt_use_locale_owned_fallback(self):
        """A single legacy color-image alt must not leak into RU/EN PDPs."""
        with self.settings(MEDIA_ROOT=self._media_root):
            self.product.title_uk = "Тестова футболка"
            self.product.title_ru = "Тестовая футболка"
            self.product.title_en = "Test T-shirt"
            self.product.save(update_fields=["title", "title_uk", "title_ru", "title_en"])

            black = Color.objects.create(
                name="Чорний", primary_hex="#000000"
            )
            variant = ProductColorVariant.objects.create(
                product=self.product,
                color=black,
                order=0,
                is_default=True,
            )
            ProductColorImage.objects.create(
                variant=variant,
                image=self._image_file("localized-alt-black.png"),
                alt_text="Чорна футболка — український alt",
                order=0,
            )

            for language, expected_title, expected_color in (
                ("ru", "Тестовая футболка", "Чёрный"),
                ("en", "Test T-shirt", "Black"),
            ):
                with self.subTest(language=language), translation.override(language):
                    response = self.client.get(
                        f"/{language}/product/{self.product.slug}/"
                    )

                self.assertEqual(response.status_code, 200)
                alt = response.context["color_variants"][0]["images"][0]["alt"]
                self.assertIn(expected_title, alt)
                self.assertIn(expected_color, alt)
                self.assertNotIn("український alt", alt)

                parser = _ProductHeroParser()
                parser.feed(response.content.decode())
                self.assertEqual(parser.hero_attributes.get("alt"), alt)
                self.assertEqual(parser.meta_content["og:image:alt"], alt)
                self.assertEqual(parser.meta_content["twitter:image:alt"], alt)

    @override_settings(**PDP_HERO_RENDER_TEST_SETTINGS)
    def test_ru_and_en_explicit_color_paths_keep_media_alt_locale_safe(self):
        """Explicit color-owner PDPs use the same locale-safe alt resolver."""
        with self.settings(MEDIA_ROOT=self._media_root):
            self.product.title_uk = "Тестова футболка"
            self.product.title_ru = "Тестовая футболка"
            self.product.title_en = "Test T-shirt"
            self.product.save(update_fields=["title", "title_uk", "title_ru", "title_en"])

            black = Color.objects.create(name="Чорний", primary_hex="#000000")
            variant = ProductColorVariant.objects.create(
                product=self.product,
                color=black,
                order=0,
                is_default=True,
            )
            ProductColorImage.objects.create(
                variant=variant,
                image=self._image_file("localized-path-alt-black.png"),
                alt_text="Чорна футболка — український alt",
                order=0,
            )

            for language, expected_title, expected_color in (
                ("ru", "Тестовая футболка", "Чёрный"),
                ("en", "Test T-shirt", "Black"),
            ):
                with self.subTest(language=language), translation.override(language):
                    response = self.client.get(
                        f"/{language}/product/{self.product.slug}/{variant.slug}/"
                    )

                self.assertEqual(response.status_code, 200)
                alt = response.context["color_variants"][0]["images"][0]["alt"]
                self.assertIn(expected_title, alt)
                self.assertIn(expected_color, alt)
                self.assertNotIn("український alt", alt)

                parser = _ProductHeroParser()
                parser.feed(response.content.decode())
                self.assertEqual(parser.hero_attributes.get("alt"), alt)
                self.assertEqual(parser.meta_content["og:image:alt"], alt)
                self.assertEqual(parser.meta_content["twitter:image:alt"], alt)

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
        self.assertContains(response, 'product-detail.css?v=20260812-cargo-drop-v1', html=False)
        self.assertContains(response, 'product-media-fit.css?v=20260808-merch-v1', html=False)
        self.assertContains(response, 'product-reviews.css?v=20260511-pdp-layout-v8', html=False)
        self.assertContains(response, 'product-detail.js?v=20260813-gallery-i18n-v1', html=False)
        self.assertContains(response, 'product-media-fit.js?v=20260808-merch-v1', html=False)

    def test_product_detail_does_not_publish_unowned_fallback_product_claims(self):
        response = self.client.get(reverse("product", args=[self.product.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "95% бавовна, 5% еластан", html=False)
        self.assertNotContains(response, "190 г/м²", html=False)
        self.assertNotContains(response, "Принт витримує багато прань", html=False)
        self.assertNotContains(response, "Зроблено в Україні з любов'ю", html=False)

    def test_product_detail_fallback_delivery_copy_does_not_guess_a_numeric_window(self):
        response = self.client.get(reverse("product", args=[self.product.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "1–2 дні по Україні після підтвердження замовлення", html=False)
        self.assertContains(response, "/delivery/", html=False)

    def test_product_detail_shell_does_not_guess_numeric_delivery_windows(self):
        response = self.client.get(reverse("product", args=[self.product.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "1–3 робочі дні по Україні", html=False)
        self.assertNotContains(response, "1-3 дні Новою Поштою", html=False)
        self.assertContains(response, "Доставка та оплата", html=False)
        self.assertContains(response, reverse("delivery"), html=False)

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

    def test_product_detail_purchase_bar_cta_does_not_stretch_to_trust_column(self):
        css_path = Path(__file__).resolve().parents[2] / "twocomms_django_theme/static/css/product-detail.css"
        css = css_path.read_text(encoding="utf-8")

        add_button_rule = css.split(".tc-add-btn {", 1)[1].split("}", 1)[0]
        self.assertIn("grid-template-columns: minmax(120px, 0.28fr) minmax(244px, 1fr) minmax(232px, 0.6fr)", css)
        self.assertIn("align-items: center", css)
        self.assertIn("align-self: center", add_button_rule)
        self.assertIn("height: 60px", add_button_rule)
        self.assertIn("max-height: 60px", add_button_rule)
        self.assertIn(".tc-purchase-side .tc-purchase-trust-link span", css)
        self.assertIn('body:has(#product-reviews .tc-reviews__form-wrap[open]) .tc-sticky-mobile', css)

    def test_product_detail_discount_price_stays_on_one_line(self):
        css_path = Path(__file__).resolve().parents[2] / "twocomms_django_theme/static/css/product-detail.css"
        css = css_path.read_text(encoding="utf-8")

        price_value_rules = [
            rule.split("}", 1)[0]
            for rule in css.split(".tc-price-values {")[1:]
        ]

        self.assertGreaterEqual(len(price_value_rules), 1)
        self.assertTrue(
            all("flex-wrap: nowrap;" in rule for rule in price_value_rules),
            "The current, original, and discount prices must remain in one row at every breakpoint.",
        )
        self.assertIn("white-space: nowrap;", price_value_rules[0])

    def test_product_detail_breadcrumbs_have_a_readable_route_specific_surface(self):
        css_path = Path(__file__).resolve().parents[2] / "twocomms_django_theme/static/css/product-detail.css"
        css = css_path.read_text(encoding="utf-8")

        self.assertIn('html[data-route-name="product"] .breadcrumb-nav {', css)
        self.assertIn("position: relative;", css)
        self.assertIn("z-index: 3;", css)
        self.assertIn("background: var(--pdp-surface-strong);", css)
        self.assertIn('html[data-route-name="product"] .breadcrumb-item.active {', css)
        self.assertIn("color: var(--pdp-text);", css)
        self.assertIn("overflow-wrap: anywhere;", css)
        self.assertIn("padding: 8px 10px !important;", css)

    def test_product_detail_reviews_prefill_registered_buyer_identity(self):
        User = get_user_model()
        user = User.objects.create_user(
            username="reviewbuyer",
            password="x",
            first_name="Олена",
            last_name="Клієнт",
            email="buyer@example.com",
        )
        order = Order.objects.create(
            user=user,
            full_name="Олена Клієнт",
            phone="+380991112233",
            email="buyer@example.com",
            city="Kyiv",
            np_office="1",
            pay_type="cod",
            payment_status="paid",
        )
        OrderItem.objects.create(
            order=order,
            product=self.product,
            qty=1,
            unit_price=1000,
            line_total=1000,
        )

        self.client.force_login(user)
        response = self.client.get(reverse("product", args=[self.product.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["product_customer_has_paid_order"])
        self.assertContains(response, "Підпис відгуку")
        self.assertContains(response, "Олена Клієнт")
        self.assertContains(response, "Покупка підтверджена")
        self.assertContains(response, 'value="Олена Клієнт"', html=False)
        self.assertContains(response, 'value="buyer@example.com"', html=False)

    def test_product_detail_review_cards_show_account_and_purchase_statuses(self):
        User = get_user_model()
        buyer = User.objects.create_user(username="verified-reviewer", password="x")
        Review.objects.create(
            product=self.product,
            user=buyer,
            author_name="Покупець",
            rating=5,
            title="Сильна якість",
            body="Тканина щільна, посадка рівна, принт після прання без змін.",
            status=ReviewStatus.APPROVED,
            is_verified_purchase=True,
        )
        Review.objects.create(
            product=self.product,
            author_name="Гість",
            rating=4,
            body="Гарний товар, але покупку на акаунт не привʼязував.",
            status=ReviewStatus.APPROVED,
            is_verified_purchase=False,
        )

        response = self.client.get(reverse("product", args=[self.product.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Зареєстрований користувач")
        self.assertContains(response, "Купив товар")
        self.assertContains(response, "Гостьовий відгук")
        self.assertContains(response, "Покупка не підтверджена")

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
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.redirect_chain[0][1], 301)
        self.assertEqual(response.context["preselected_color"], selected_variant.pk)
        self.assertEqual(response.context["color_variants"][0]["id"], selected_variant.pk)

    @override_settings(**PDP_HERO_RENDER_TEST_SETTINGS)
    def test_product_base_path_prerenders_active_default_color_hero_and_preload(self):
        """The base PDP SSR frame must match the default swatch used by hydration."""
        with self.settings(MEDIA_ROOT=self._media_root):
            self.product.main_image = self._image_file("base-url-main.png")
            self.product.save(update_fields=["main_image"])

            black = Color.objects.create(name="Black", primary_hex="#000000")
            default_variant = ProductColorVariant.objects.create(
                product=self.product,
                color=black,
                order=0,
                is_default=True,
            )
            selected_image_name = "base-url-black.png"
            ProductColorImage.objects.create(
                variant=default_variant,
                image=self._image_file(selected_image_name),
                alt_text="Black hero",
                order=0,
            )
            optimized_dir = Path(self._media_root) / "product_colors" / "optimized"
            optimized_dir.mkdir(parents=True, exist_ok=True)
            (optimized_dir / "base-url-black_768w.avif").write_bytes(b"avif")

            response = self.client.get(
                reverse("product", args=[self.product.slug]),
                secure=True,
            )

        self.assertEqual(response.status_code, 200)
        self._assert_selected_color_hero(
            response,
            "base-url-main.png",
            selected_image_name,
            expected_alt="Black hero",
        )

    @override_settings(**PDP_HERO_RENDER_TEST_SETTINGS)
    def test_product_base_path_keeps_social_alt_matched_to_main_social_image(self):
        """A default-color hero must not rewrite alt text for a main-image OG card."""
        with self.settings(MEDIA_ROOT=self._media_root):
            self.product.main_image = self._image_file("base-social-main.png")
            self.product.main_image_alt = "Main social hero"
            self.product.save(update_fields=["main_image", "main_image_alt"])

            black = Color.objects.create(name="Black", primary_hex="#000000")
            default_variant = ProductColorVariant.objects.create(
                product=self.product,
                color=black,
                order=0,
                is_default=True,
            )
            ProductColorImage.objects.create(
                variant=default_variant,
                image=self._image_file("base-social-black.png"),
                alt_text="Black color hero",
                order=0,
            )

            response = self.client.get(
                reverse("product", args=[self.product.slug]),
                secure=True,
            )

        parser = _ProductHeroParser()
        parser.feed(response.content.decode())
        self.assertEqual(response.status_code, 200)
        self.assertIn("base-social-main.png", parser.meta_content["og:image"])
        self.assertEqual(parser.meta_content["og:image:alt"], "Main social hero")
        self.assertIn("base-social-main.png", parser.meta_content["twitter:image"])
        self.assertEqual(parser.meta_content["twitter:image:alt"], "Main social hero")

    @override_settings(**PDP_HERO_RENDER_TEST_SETTINGS)
    def test_product_without_main_image_keeps_social_alt_with_display_color_image(self):
        """Base social metadata must follow the first display-color image, not the default swatch."""
        with self.settings(MEDIA_ROOT=self._media_root):
            black = Color.objects.create(name="Black", primary_hex="#000000")
            coyote = Color.objects.create(name="Coyote", primary_hex="#A98463")
            display_variant = ProductColorVariant.objects.create(
                product=self.product,
                color=black,
                order=0,
                is_default=False,
            )
            default_variant = ProductColorVariant.objects.create(
                product=self.product,
                color=coyote,
                order=1,
                is_default=True,
            )
            ProductColorImage.objects.create(
                variant=display_variant,
                image=self._image_file("no-main-black.png"),
                alt_text="Black social image",
                order=0,
            )
            ProductColorImage.objects.create(
                variant=default_variant,
                image=self._image_file("no-main-coyote.png"),
                alt_text="Coyote default hero",
                order=0,
            )

            response = self.client.get(
                reverse("product", args=[self.product.slug]),
                secure=True,
            )

        parser = _ProductHeroParser()
        parser.feed(response.content.decode())
        self.assertEqual(response.status_code, 200)
        self.assertTrue(parser.hero_attributes.get("src", "").endswith("no-main-coyote.png"))
        self.assertIn("no-main-black.png", parser.meta_content["og:image"])
        self.assertEqual(parser.meta_content["og:image:alt"], "Black social image")
        self.assertIn("no-main-black.png", parser.meta_content["twitter:image"])
        self.assertEqual(parser.meta_content["twitter:image:alt"], "Black social image")

    @override_settings(**PDP_HERO_RENDER_TEST_SETTINGS)
    def test_product_color_path_prerenders_selected_color_hero_and_preload(self):
        """The first server-rendered gallery frame must match a color URL."""
        with self.settings(MEDIA_ROOT=self._media_root):
            selected_variant, base_image_name, selected_image_name = (
                self._configure_selected_color_hero("color-url")
            )

            response = self.client.get(
                reverse(
                    "product",
                    kwargs={"slug": self.product.slug, "v1": selected_variant.slug},
                ),
                secure=True,
            )

        self.assertEqual(response.status_code, 200)
        self._assert_selected_color_hero(response, base_image_name, selected_image_name)
        self._assert_selected_color_social_metadata(response, selected_image_name)

    @override_settings(**PDP_HERO_RENDER_TEST_SETTINGS)
    def test_product_color_size_path_prerenders_selected_color_hero_and_preload(self):
        """Non-self-canonical color plus size URLs retain their selected hero."""
        with self.settings(MEDIA_ROOT=self._media_root):
            selected_variant, base_image_name, selected_image_name = (
                self._configure_selected_color_hero("color-size-url")
            )

            response = self.client.get(
                reverse(
                    "product",
                    kwargs={
                        "slug": self.product.slug,
                        "v1": selected_variant.slug,
                        "v2": "m",
                    },
                ),
                secure=True,
            )

        self.assertEqual(response.status_code, 200)
        self._assert_selected_color_hero(response, base_image_name, selected_image_name)

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

    def test_product_detail_localizes_standard_fit_selector_for_ru_and_en(self):
        tshirt_category = Category.objects.create(
            name="Футболки",
            slug="localized-tshirt-fit",
            is_active=True,
        )
        product = Product.objects.create(
            title="Локалізована футболка",
            title_ru="Локализованная футболка",
            title_en="Localized T-shirt",
            slug="localized-tshirt-fit",
            category=tshirt_category,
            price=1000,
            description="Перевірка локалізації посадки.",
            status="published",
        )
        ProductFitOption.objects.create(
            product=product,
            code="classic",
            label="Класична",
            is_default=True,
            order=0,
        )
        ProductFitOption.objects.create(
            product=product,
            code="oversize",
            label="Оверсайз",
            order=1,
        )

        matrix = {
            "ru": ("Посадка", "Классическая", "Оверсайз"),
            "en": ("Fit", "Classic", "Oversize"),
        }
        for language, expected in matrix.items():
            with self.subTest(language=language), translation.override(language):
                response = self.client.get(
                    f"/{language}/product/{product.slug}/",
                )
                html = response.content.decode("utf-8")

                self.assertEqual(response.status_code, 200)
                self.assertIn(
                    f'<div class="tc-selector-head"><span>{expected[0]}</span></div>',
                    html,
                )
                self.assertIn(f"<strong>{expected[1]}</strong>", html)
                self.assertIn(f"<strong>{expected[2]}</strong>", html)
                self.assertNotIn("<strong>Класична</strong>", html)

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

        response = self.client.get(
            reverse("product", args=[product.slug]),
            {"fit": "oversize"},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.redirect_chain[0][1], 301)
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

    def test_product_detail_renders_active_product_faq_tab_and_schema(self):
        ProductFAQ.objects.create(
            product=self.product,
            question="Це чоловіча чи жіноча футболка?",
            answer="Це футболка унісекс.",
            order=0,
            is_active=True,
        )
        ProductFAQ.objects.create(
            product=self.product,
            question="  це чоловіча чи жіноча футболка? ",
            answer="Це   футболка унісекс.",
            order=1,
            is_active=True,
        )
        ProductFAQ.objects.create(
            product=self.product,
            question="Неактивне питання",
            answer="Не має показуватись.",
            order=2,
            is_active=False,
        )

        response = self.client.get(reverse("product", args=[self.product.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["product_faq_items"]), 1)
        self.assertEqual(response.context["product_faq_items"][0]["question"], "Це чоловіча чи жіноча футболка?")
        self.assertContains(response, 'data-pdp-tab="faq"', html=False)
        self.assertContains(response, 'id="panel-faq"', html=False)
        self.assertContains(response, "FAQ товару")
        self.assertContains(response, "Це футболка унісекс.")
        self.assertContains(response, '"@type": "FAQPage"', html=False)
        self.assertEqual(
            response.content.decode().count("Це чоловіча чи жіноча футболка?"),
            2,
        )
        self.assertNotContains(response, "Неактивне питання")


class GetProductImagesTests(ProductViewTestCase):
    def test_get_product_images_returns_main_and_gallery(self):
        with self.settings(MEDIA_ROOT=self._media_root):
            self.product.main_image = self._image_file("main.png")
            self.product.main_image_alt = "Main alt"
            self.product.save(update_fields=["main_image", "main_image_alt"])
            ProductImage.objects.create(
                product=self.product,
                image=self._image_file("gallery.png"),
                alt_text="Gallery alt",
                order=0,
            )

            response = self.client.get(reverse("get_product_images", args=[self.product.pk]))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["count"], 2)
        self.assertTrue(payload["images"][0]["is_main"])
        self.assertFalse(payload["images"][1]["is_main"])
        self.assertEqual(payload["images"][0]["alt"], "Main alt")
        self.assertEqual(payload["images"][1]["alt"], "Gallery alt")

    def test_get_product_images_returns_404_for_missing_product(self):
        response = self.client.get(reverse("get_product_images", args=[99999]))

        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.json()["success"])


class GetProductVariantsTests(ProductViewTestCase):
    def test_ru_and_en_variants_ajax_uses_locale_owned_media_alt_fallback(self):
        self.product.title_uk = "Тестова футболка"
        self.product.title_ru = "Тестовая футболка"
        self.product.title_en = "Test T-shirt"
        self.product.save(update_fields=["title", "title_uk", "title_ru", "title_en"])
        black = Color.objects.create(name="Чорний", primary_hex="#000000")
        variant = ProductColorVariant.objects.create(
            product=self.product,
            color=black,
            order=0,
            is_default=True,
        )
        ProductColorImage.objects.create(
            variant=variant,
            image=SimpleUploadedFile("localized-ajax-alt-black.png", PNG_PIXEL, content_type="image/png"),
            alt_text="Чорна футболка — український alt",
            order=0,
        )

        for language, expected_title, expected_color in (
            ("ru", "Тестовая футболка", "Чёрный"),
            ("en", "Test T-shirt", "Black"),
        ):
            with self.subTest(language=language):
                with translation.override(language):
                    request = RequestFactory().get(
                        reverse("get_product_variants", args=[self.product.pk])
                    )
                    request.LANGUAGE_CODE = language
                    response = get_product_variants(request, self.product.pk)

            self.assertEqual(response.status_code, 200)
            image = json.loads(response.content)["variants"][0]["images"][0]
            self.assertIn(expected_title, image["alt"])
            self.assertIn(expected_color, image["alt"])
            self.assertNotIn("український alt", image["alt"])

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
        self.assertEqual(variants_by_id[secondary_variant.pk]["images"][0]["alt"], "Side")

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
        self.assertEqual(image_payload["alt"], "Optimized")

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
