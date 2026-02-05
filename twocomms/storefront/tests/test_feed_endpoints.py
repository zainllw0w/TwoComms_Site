from django.test import TestCase, override_settings


@override_settings(
    ALLOWED_HOSTS=["testserver", "dtf.twocomms.shop", "twocomms.shop"],
    COMPRESS_ENABLED=False,
    COMPRESS_OFFLINE=False,
)
class FeedEndpointsSmokeTests(TestCase):
    def test_google_merchant_feed_is_not_server_error(self):
        response = self.client.get("/google_merchant_feed.xml", secure=True)

        self.assertNotEqual(response.status_code, 500)
        self.assertIn("xml", response["Content-Type"].lower())

    def test_prom_feed_is_not_server_error(self):
        response = self.client.get("/prom-feed.xml", secure=True)

        self.assertNotEqual(response.status_code, 500)
        self.assertIn("xml", response["Content-Type"].lower())
