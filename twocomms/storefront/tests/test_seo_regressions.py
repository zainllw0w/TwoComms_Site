from unittest.mock import patch

from decimal import Decimal

from django.test import Client, RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from orders.models import Order
from storefront.models import Category, Product
from storefront.views.static_pages import static_sitemap


class ProductPageSeoRegressionTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.category = Category.objects.create(
            name="SEO Test Category",
            slug="seo-test-category",
            is_active=True,
        )
        self.product = Product.objects.create(
            title="SEO Test Product",
            slug="seo-test-product",
            category=self.category,
            price=100,
            description="SEO regression coverage product.",
            status="published",
        )

    def test_product_page_does_not_leak_template_syntax(self):
        response = self.client.get(reverse("product", kwargs={"slug": self.product.slug}), follow=True)

        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")

        self.assertNotIn("{% optimized_image", html)
        self.assertNotIn("{#", html)
        self.assertNotIn('data-offer-id-map="{"', html)

    def test_product_page_prefers_manual_meta_and_social_preview_fallback(self):
        self.product.seo_title = "SEO Title Override для товару"
        self.product.seo_description = "Акуратний SEO опис для перевірки метатегів без обривів."
        self.product.seo_keywords = "seo override, twocomms, test product"
        self.product.save(update_fields=["seo_title", "seo_description", "seo_keywords"])

        response = self.client.get(reverse("product", kwargs={"slug": self.product.slug}), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<title>SEO Title Override для товару</title>", html=False)
        self.assertContains(response, 'content="Акуратний SEO опис для перевірки метатегів без обривів."', html=False)
        self.assertContains(response, 'content="seo override, twocomms, test product"', html=False)
        self.assertContains(response, "social-preview.jpg", html=False)
        self.assertContains(response, 'property="og:image:alt"', html=False)


class OrderSuccessSeoRegressionTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.order = Order.objects.create(
            full_name="SEO Test User",
            phone="+380991112233",
            email="seo@example.com",
            city="Kyiv",
            np_office="1",
            pay_type="cod",
            payment_status="unpaid",
            total_sum=Decimal("200.00"),
        )

    def test_order_success_page_is_noindex(self):
        response = self.client.get(reverse("order_success", kwargs={"order_id": self.order.id}), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'content="noindex, nofollow"', html=False)


@override_settings(NOVA_POSHTA_FALLBACK_ENABLED=False)
class ServicePageSeoMetaRegressionTests(SimpleTestCase):
    def setUp(self):
        self.client = Client()

    def test_key_service_pages_override_default_social_meta(self):
        cases = [
            (
                reverse("about"),
                '<meta property="twitter:title" content="TwoComms — не крапка. Продовження.">',
            ),
            (
                reverse("contacts"),
                '<meta property="twitter:title" content="Контакти — TwoComms">',
            ),
            (
                reverse("delivery"),
                '<meta property="og:title" content="Доставка і оплата — TwoComms">',
            ),
            (
                reverse("cooperation"),
                '<meta property="og:title" content="Співпраця з TwoComms — дропшипінг, опт і бренд-партнерства">',
            ),
        ]

        for url, expected_meta in cases:
            with self.subTest(url=url):
                response = self.client.get(url, follow=True)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, expected_meta, html=False)

    def test_about_page_uses_brand_story_layout(self):
        response = self.client.get(reverse("about"), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'pro-brand-page pb-page',
            html=False,
        )
        self.assertContains(response, 'data-pro-brand-video', html=False)
        self.assertNotContains(response, 'data-brand-scroll', html=False)
        self.assertContains(response, 'aria-label="Breadcrumb"', html=False)
        self.assertContains(response, '"@type": "FAQPage"', html=False)
        self.assertContains(response, 'href="https://testserver/pro-brand/"', html=False)
        self.assertContains(response, 'content="https://testserver/pro-brand/"', html=False)
        self.assertContains(response, '"@type": ["Organization", "OnlineStore"]', html=False)
        self.assertContains(response, 'data-page-shell="marketing"', html=False)
        self.assertContains(response, 'data-analytics-mode="passive"', html=False)
        self.assertNotContains(response, 'points-modal-template', html=False)
        self.assertNotContains(response, 'js/ui-fallback.js', html=False)

    def test_legacy_about_url_redirects_to_pro_brand(self):
        response = self.client.get("/about/", secure=True, follow=False)

        self.assertEqual(response.status_code, 301)
        self.assertEqual(response["Location"], "/pro-brand/")

    def test_llms_txt_prefers_pro_brand_canonical_url(self):
        response = self.client.get("/llms.txt", secure=True)

        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8")
        self.assertIn("https://testserver/pro-brand/", body)
        self.assertNotIn("https://testserver/about/", body)

    def test_delivery_page_faq_schema_matches_visible_content(self):
        response = self.client.get(reverse("delivery"), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '"@type": "FAQPage"', html=False)
        self.assertContains(response, "Чи можна оплатити товар при отриманні?")
        self.assertNotContains(response, "Чи є таблиця розмірів?")

    @patch("storefront.views.static_pages.SizeGrid.objects.filter")
    @patch("storefront.views.static_pages.Product.objects.filter")
    def test_support_pages_render_breadcrumb_schema_consistently(self, product_filter_mock, size_grid_filter_mock):
        product_filter_mock.return_value.exclude.return_value.select_related.return_value.only.return_value.order_by.return_value.__getitem__.return_value = []
        size_grid_filter_mock.return_value.select_related.return_value.order_by.return_value = []

        routes = [
            reverse("help_center"),
            reverse("faq"),
            reverse("delivery"),
            reverse("returns"),
            reverse("privacy_policy"),
            reverse("terms_of_service"),
            reverse("about"),
            reverse("news"),
            reverse("size_guide"),
        ]

        for url in routes:
            with self.subTest(url=url):
                response = self.client.get(url, follow=True)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, '"@type": "BreadcrumbList"', html=False)
                self.assertContains(response, 'aria-label="Breadcrumb"', html=False)


class CategoryNavigationSeoRegressionTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.category = Category.objects.create(
            name="Breadcrumb Category",
            slug="breadcrumb-category",
            is_active=True,
        )

    def test_category_page_renders_visible_breadcrumbs(self):
        response = self.client.get(reverse("catalog_by_cat", kwargs={"cat_slug": self.category.slug}), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'aria-label="breadcrumb"', html=False)
        self.assertContains(response, f'href="{reverse("catalog")}"', html=False)
        self.assertContains(response, self.category.name)

    def test_catalog_root_renders_breadcrumbs_and_breadcrumb_schema(self):
        response = self.client.get(reverse("catalog"), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'aria-label="breadcrumb"', html=False)
        self.assertContains(response, reverse("home"))
        self.assertContains(response, '"@type": "BreadcrumbList"', html=False)


class SitemapSeoRegressionTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.factory = RequestFactory()

    def test_sitemap_prefers_pro_brand_url_and_not_legacy_about(self):
        request = self.factory.get(reverse("django.contrib.sitemaps.views.sitemap"), secure=True)
        response = static_sitemap(request)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "https://testserver/pro-brand/")
        self.assertNotContains(response, "https://testserver/about/")


class HeaderCtaSeoRegressionTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_header_primary_cta_points_to_custom_print(self):
        response = self.client.get(reverse("home"), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f"class='btn btn-sm btn-gradient-suggest me-3' href='{reverse('custom_print')}'",
            html=False,
        )
        self.assertNotContains(
            response,
            f"class='btn btn-sm btn-gradient-suggest me-3' href='{reverse('add_print')}'",
            html=False,
        )


class AddPrintSeoRegressionTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_add_print_page_is_noindex_follow(self):
        response = self.client.get(reverse("add_print"), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'content="noindex, follow"', html=False)


class PublicUrlIndexationSeoRegressionTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_pricelist_page_redirects_to_wholesale(self):
        response = self.client.get(reverse("pricelist_page"), secure=True, follow=False)

        self.assertEqual(response.status_code, 301)
        self.assertEqual(response["Location"], reverse("wholesale_page"))

    def test_utility_pages_are_noindex_follow(self):
        cases = [reverse("wholesale_order_form"), reverse("test_analytics")]

        for url in cases:
            with self.subTest(url=url):
                response = self.client.get(url, follow=True)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'content="noindex, follow"', html=False)


class CustomPrintSeoRegressionTests(TestCase):
    def setUp(self):
        self.client = Client(
            HTTP_HOST="twocomms.shop",
            SERVER_PORT="443",
            **{"wsgi.url_scheme": "https"},
        )

    def test_custom_print_page_has_breadcrumbs_and_faq_layer(self):
        response = self.client.get(reverse("custom_print"), secure=True, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'aria-label="Breadcrumb"', html=False)
        self.assertContains(response, "Поширені питання про кастомний друк")
        self.assertContains(response, '"@type": "FAQPage"', html=False)


class WholesaleSeoRegressionTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_wholesale_page_exposes_visible_faq_content(self):
        response = self.client.get(reverse("wholesale_page"), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Поширені питання про оптові закупівлі")
        self.assertContains(response, "Який мінімальний обсяг оптового замовлення у TwoComms?")


class CooperationSeoRegressionTests(TestCase):
    def setUp(self):
        self.client = Client(
            HTTP_HOST="twocomms.shop",
            SERVER_PORT="443",
            **{"wsgi.url_scheme": "https"},
        )

    def test_cooperation_page_has_breadcrumbs_meta_and_faq_layer(self):
        response = self.client.get(reverse("cooperation"), secure=True, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            '<meta property="og:title" content="Співпраця з TwoComms — дропшипінг, опт і бренд-партнерства">',
            html=False,
        )
        self.assertContains(response, 'aria-label="Breadcrumb"', html=False)
        self.assertContains(response, "Поширені питання про співпрацю")
        self.assertContains(response, '"@type": "FAQPage"', html=False)


class RobotsTxtAiSearchRegressionTests(TestCase):
    def setUp(self):
        self.client = Client(
            HTTP_HOST="twocomms.shop",
            SERVER_PORT="443",
            **{"wsgi.url_scheme": "https"},
        )

    def test_robots_txt_allows_ai_search_and_training_bots_for_maximum_discoverability(self):
        response = self.client.get(reverse("robots_txt"), secure=True)

        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8")

        self.assertIn("User-agent: OAI-SearchBot\nAllow: /", body)
        self.assertIn("User-agent: ChatGPT-User\nAllow: /", body)
        self.assertIn("User-agent: Claude-SearchBot\nAllow: /", body)
        self.assertIn("User-agent: Claude-User\nAllow: /", body)
        self.assertIn("User-agent: PerplexityBot\nAllow: /", body)
        self.assertIn("User-agent: Perplexity-User\nAllow: /", body)
        self.assertIn("User-agent: Google-Extended\nAllow: /", body)
        self.assertIn("User-agent: GPTBot\nAllow: /", body)
        self.assertIn("User-agent: CCBot\nAllow: /", body)
        self.assertIn("User-agent: ClaudeBot\nAllow: /", body)
        self.assertIn("User-agent: anthropic-ai\nAllow: /", body)
        self.assertIn("Disallow: /search/", body)
        self.assertIn("Sitemap: https://twocomms.shop/sitemap.xml", body)


class LlmsTxtSeoRegressionTests(TestCase):
    def setUp(self):
        self.client = Client(
            HTTP_HOST="twocomms.shop",
            SERVER_PORT="443",
            **{"wsgi.url_scheme": "https"},
        )

    def test_llms_txt_exposes_primary_brand_and_commerce_routes(self):
        response = self.client.get(reverse("llms_txt"), secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/plain; charset=utf-8")

        body = response.content.decode("utf-8")
        self.assertIn("# TwoComms", body)
        self.assertIn("https://twocomms.shop/custom-print/", body)
        self.assertIn("https://twocomms.shop/wholesale/", body)
        self.assertIn("https://twocomms.shop/catalog/", body)
        self.assertIn("https://twocomms.shop/sitemap.xml", body)

    def test_well_known_llms_txt_alias_resolves(self):
        primary = self.client.get(reverse("llms_txt"), secure=True)
        response = self.client.get("/.well-known/llms.txt", secure=True)

        self.assertEqual(primary.status_code, 200)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/plain; charset=utf-8")
        self.assertEqual(response.content.decode("utf-8"), primary.content.decode("utf-8"))

    def test_llms_txt_excludes_utility_and_internal_routes(self):
        response = self.client.get(reverse("llms_txt"), secure=True)

        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8")

        for disallowed_path in (
            "/search/",
            "/cart/",
            "/checkout/",
            "/admin/",
            "/api/",
            "/test-analytics/",
            "/wholesale/order-form/",
        ):
            with self.subTest(disallowed_path=disallowed_path):
                self.assertNotIn(disallowed_path, body)
