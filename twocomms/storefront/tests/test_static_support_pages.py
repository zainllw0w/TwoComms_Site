from unittest.mock import patch

from django.test import Client, RequestFactory, SimpleTestCase, override_settings
from django.urls import reverse

from storefront.support_content import DELIVERY_FAQ_ITEMS
from storefront.views.static_pages import static_sitemap


@override_settings(NOVA_POSHTA_FALLBACK_ENABLED=False)
class SupportStaticPagesTests(SimpleTestCase):
    def setUp(self):
        self.client = Client()
        self.factory = RequestFactory()

    @patch("storefront.views.static_pages.SizeGrid.objects.filter")
    @patch("storefront.views.static_pages.Category.objects.filter")
    @patch("storefront.views.static_pages.Product.objects.filter")
    def test_support_pages_are_available(self, product_filter_mock, category_filter_mock, size_grid_filter_mock):
        product_filter_mock.return_value.exclude.return_value.select_related.return_value.only.return_value.order_by.return_value.__getitem__.return_value = []
        category_filter_mock.return_value.only.return_value = []
        size_grid_filter_mock.return_value.select_related.return_value.order_by.return_value = []

        route_names = [
            "about",
            "delivery",
            "help_center",
            "faq",
            "size_guide",
            "care_guide",
            "order_tracking",
            "site_map_page",
            "news",
            "returns",
            "privacy_policy",
            "terms_of_service",
        ]

        for route_name in route_names:
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name), secure=True)
                self.assertEqual(response.status_code, 200)

    def test_help_center_links_to_faq_without_rendering_duplicate_faq_block(self):
        response = self.client.get(reverse("help_center"), secure=True)

        self.assertNotContains(response, '"@type": "FAQPage"', html=False)
        self.assertNotContains(response, "Поширені запитання")
        self.assertContains(response, reverse("faq"))
        self.assertContains(response, reverse("delivery"))
        self.assertContains(response, reverse("size_guide"))

    def test_footer_uses_symmetric_clusters_without_old_highlight_copy(self):
        response = self.client.get(reverse("about"), secure=True)

        self.assertContains(response, "Покупка")
        self.assertContains(response, "Підтримка")
        self.assertContains(response, "Бренд")
        self.assertContains(response, "Швидкий доступ")
        self.assertContains(response, "All Rights Reserved © TWOCOMMS, 2026")
        self.assertNotContains(response, "FAQ моменти")
        self.assertNotContains(response, "TwoComms: сервіс, підтримка, новини бренду")

    def test_about_page_uses_dedicated_brand_layout_while_delivery_keeps_support_shell(self):
        about_response = self.client.get(reverse("about"), secure=True)
        self.assertEqual(about_response.status_code, 200)
        self.assertContains(about_response, 'class="pro-brand-page"', html=False)
        self.assertContains(about_response, 'data-pro-brand-video', html=False)
        self.assertNotContains(about_response, 'data-brand-scroll', html=False)
        self.assertContains(about_response, 'aria-label="Breadcrumb"', html=False)

        delivery_response = self.client.get(reverse("delivery"), secure=True)
        self.assertEqual(delivery_response.status_code, 200)
        self.assertContains(delivery_response, 'class="support-shell', html=False)
        self.assertContains(delivery_response, 'aria-label="Breadcrumb"', html=False)

    def test_legacy_about_path_redirects_to_new_brand_url(self):
        response = self.client.get("/about/", secure=True, follow=False)

        self.assertEqual(response.status_code, 301)
        self.assertEqual(response["Location"], "/pro-brand/")

    def test_delivery_page_uses_delivery_specific_faq_content(self):
        response = self.client.get(reverse("delivery"), secure=True)

        self.assertContains(response, '"@type": "FAQPage"', html=False)
        for item in DELIVERY_FAQ_ITEMS:
            self.assertContains(response, item["question"])
        self.assertNotContains(response, "Чи є таблиця розмірів?")

    @patch("storefront.views.static_pages.SizeGrid.objects.filter")
    def test_size_guide_page_hides_confirmed_blocks_when_no_db_guides_exist(self, size_grid_filter_mock):
        size_grid_filter_mock.return_value.select_related.return_value.order_by.return_value = []

        response = self.client.get(reverse("size_guide"), secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Confirmed guides")
        self.assertNotContains(response, "Футболка базова")
        self.assertNotContains(response, "Довжина (A)")

    @patch("storefront.views.static_pages.Category.objects.filter")
    @patch("storefront.views.static_pages.Product.objects.filter")
    def test_sitemap_contains_support_pages(self, product_filter_mock, category_filter_mock):
        product_filter_mock.return_value.only.return_value = []
        category_filter_mock.return_value.only.return_value = []

        request = self.factory.get(reverse("django.contrib.sitemaps.views.sitemap"))
        response = static_sitemap(request)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "http://testserver/dopomoga/")
        self.assertContains(response, "http://testserver/faq/")
        self.assertContains(response, "http://testserver/rozmirna-sitka/")
        self.assertContains(response, "http://testserver/doglyad-za-odyagom/")
        self.assertContains(response, "http://testserver/vidstezhennya-zamovlennya/")
        self.assertContains(response, "http://testserver/mapa-saytu/")
        self.assertContains(response, "http://testserver/pro-brand/")
        self.assertNotContains(response, "http://testserver/about/")
