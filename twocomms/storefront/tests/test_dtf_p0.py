from django.test import TestCase, override_settings


@override_settings(
    ALLOWED_HOSTS=["testserver", "dtf.twocomms.shop", "twocomms.shop"],
    COMPRESS_ENABLED=False,
    COMPRESS_OFFLINE=False,
)
class DtfP0RoutesTests(TestCase):
    def test_quality_page_returns_200(self):
        response = self.client.get("/quality/", secure=True)
        self.assertEqual(response.status_code, 200)

    def test_price_page_returns_200(self):
        response = self.client.get("/price/", secure=True)
        self.assertEqual(response.status_code, 200)

    def test_prices_redirects_to_price(self):
        response = self.client.get("/prices/", follow=False, secure=True)
        self.assertEqual(response.status_code, 301)
        self.assertTrue(response["Location"].endswith("/price/"))

    def test_robots_points_to_current_host_sitemap(self):
        response = self.client.get("/robots.txt", headers={"host": "dtf.twocomms.shop"}, secure=True)
        body = response.content.decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Sitemap: https://dtf.twocomms.shop/sitemap.xml", body)
        self.assertNotIn("https://twocomms.shop/sitemap.xml", body)

    def test_sitemap_uses_request_host_and_contains_price(self):
        response = self.client.get("/sitemap.xml", headers={"host": "dtf.twocomms.shop"}, secure=True)
        body = response.content.decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertIn("https://dtf.twocomms.shop/price/", body)
        self.assertNotIn("https://twocomms.shop/", body)
