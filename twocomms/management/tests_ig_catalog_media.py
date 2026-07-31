from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase

from management.services import bot_catalog
from management.services import instagram_bot as bot
from management.services.ig_catalog_media import (
    CatalogMediaDeliveryState,
    CatalogMediaItem,
    CatalogMediaSelection,
    CatalogMediaState,
    send_catalog_media,
    select_catalog_media,
)
from productcolors.models import Color, ProductColorImage, ProductColorVariant
from storefront.models import Category, Product, ProductFitOption, ProductStatus


class InstagramCatalogContextTests(TestCase):
    def setUp(self):
        category = Category.objects.create(name="Футболки", slug="ig-catalog-shirts")
        self.product = Product.objects.create(
            title="Футболка Night Shift",
            slug="ig-catalog-night-shift",
            category=category,
            price=950,
            status=ProductStatus.PUBLISHED,
        )
        ProductFitOption.objects.create(
            product=self.product,
            code="classic",
            label="Класична",
            is_active=True,
        )
        ProductFitOption.objects.create(
            product=self.product,
            code="oversize",
            label="Оверсайз",
            is_active=True,
        )
        blue = Color.objects.create(name="Синя", primary_hex="#1d4ed8")
        black = Color.objects.create(name="Чорна", primary_hex="#111111")
        self.blue = ProductColorVariant.objects.create(
            product=self.product,
            color=blue,
            stock=3,
            sku="NS-BLUE",
        )
        self.black = ProductColorVariant.objects.create(
            product=self.product,
            color=black,
            stock=2,
            sku="NS-BLACK",
        )

    @patch("management.services.bot_catalog.resolve_catalog_sizes", return_value={"classic": ["S", "M", "L"], "oversize": ["XS", "S", "M"]})
    def test_context_exposes_exact_variant_fit_and_size_contract(self, _sizes):
        text = bot_catalog._build()

        self.assertIn(f"id={self.product.pk}", text)
        self.assertIn(f"variant_id={self.blue.pk}", text)
        self.assertIn(f"variant_id={self.black.pk}", text)
        self.assertIn("classic: S/M/L", text)
        self.assertIn("oversize: XS/S/M", text)
        self.assertIn("не вигадуй", text.lower())

    def test_show_products_control_keeps_exact_ids_and_catalog_link_is_explicit(self):
        clean, control = bot._extract_control(
            "Покажу фото [SHOW_PRODUCTS:12,34] [CATALOG_LINK]"
        )

        self.assertEqual(clean, "Покажу фото")
        self.assertEqual(control["show_products"], "12,34")
        self.assertTrue(control["catalog_link"])


class InstagramCatalogMediaTests(TestCase):
    def setUp(self):
        category = Category.objects.create(name="Худі", slug="ig-catalog-media")
        self.product = Product.objects.create(
            title="Худі Media",
            slug="ig-catalog-media-hoodie",
            category=category,
            price=1200,
            status=ProductStatus.PUBLISHED,
        )
        color = Color.objects.create(name="Чорна", primary_hex="#111111")
        variant = ProductColorVariant.objects.create(
            product=self.product,
            color=color,
            stock=4,
        )
        for index in range(5):
            ProductColorImage.objects.create(
                variant=variant,
                order=index,
                image=SimpleUploadedFile(
                    f"media-{index}.jpg",
                    b"jpeg-placeholder",
                    content_type="image/jpeg",
                ),
            )

    def test_selector_caps_real_images_and_returns_no_product_url(self):
        selection = select_catalog_media([self.product.pk])

        self.assertEqual(selection.state, CatalogMediaState.READY)
        self.assertEqual(len(selection.items), 4)
        self.assertTrue(all(item.url.startswith("https://") for item in selection.items))
        self.assertTrue(all("/product/" not in item.url for item in selection.items))

    def test_selector_reports_empty_for_missing_or_unpublished_product(self):
        self.product.status = ProductStatus.DRAFT
        self.product.save(update_fields=["status"])

        selection = select_catalog_media([self.product.pk])

        self.assertEqual(selection.state, CatalogMediaState.EMPTY)
        self.assertEqual(selection.items, ())


class InstagramCatalogMediaTransportTests(SimpleTestCase):
    def _selection(self):
        return CatalogMediaSelection(
            state=CatalogMediaState.READY,
            items=(
                CatalogMediaItem("https://twocomms.shop/media/one.jpg", "One", "One", 1),
                CatalogMediaItem("https://twocomms.shop/media/two.jpg", "Two", "Two", 2),
            ),
            requested_product_ids=(1, 2),
        )

    @patch("management.services.instagram_bot.get_page_token", return_value="token")
    @patch("management.services.instagram_bot._provider_account_id", return_value="account")
    @patch(
        "management.services.instagram_bot._provider_http",
        side_effect=[(200, '{"message_id":"mid-1"}'), (500, "provider failed")],
    )
    def test_transport_reports_partial_without_replaying_first_image(
        self, provider_http, _account, _token
    ):
        result = send_catalog_media(object(), "recipient", self._selection())

        self.assertEqual(result.state, CatalogMediaDeliveryState.PARTIAL)
        self.assertEqual(result.sent_count, 1)
        self.assertEqual(result.attempted_count, 2)
        self.assertEqual(result.provider_message_ids, ("mid-1",))
        self.assertEqual(provider_http.call_count, 2)

    @patch("management.services.instagram_bot.get_page_token", return_value="token")
    @patch("management.services.instagram_bot._provider_account_id", return_value="account")
    @patch("management.services.instagram_bot._provider_http", side_effect=TimeoutError("unknown"))
    def test_transport_reports_ambiguous_provider_result(
        self, provider_http, _account, _token
    ):
        result = send_catalog_media(object(), "recipient", self._selection())

        self.assertEqual(result.state, CatalogMediaDeliveryState.AMBIGUOUS)
        self.assertEqual(result.sent_count, 0)
        self.assertEqual(result.attempted_count, 1)
        provider_http.assert_called_once()
