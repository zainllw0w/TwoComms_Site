from unittest.mock import patch

from django.test import Client, RequestFactory, SimpleTestCase, override_settings
from django.urls import reverse

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

    def test_help_center_exposes_faq_schema_and_core_links(self):
        response = self.client.get(reverse("help_center"), secure=True)

        self.assertContains(response, '"@type": "FAQPage"')
        self.assertContains(response, reverse("faq"))
        self.assertContains(response, reverse("delivery"))
        self.assertContains(response, reverse("order_tracking"))

    def test_home_footer_contains_support_navigation(self):
        response = self.client.get(reverse("help_center"), secure=True)

        self.assertContains(response, reverse("help_center"))
        self.assertContains(response, reverse("faq"))
        self.assertContains(response, reverse("size_guide"))
        self.assertContains(response, reverse("site_map_page"))

    def test_mobile_bottom_nav_does_not_render_profile_avatar_toggle(self):
        response = self.client.get(reverse("help_center"), secure=True)

        self.assertNotContains(response, 'id="user-toggle-mobile"', html=False)
        self.assertNotContains(response, "user-avatar-btn-mobile", html=False)

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
