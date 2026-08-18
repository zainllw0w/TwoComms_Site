from unittest.mock import patch

from django.core import signing
from django.test import TestCase
from django.urls import reverse

from storefront.models import PageView, PromoCode, QrDeviceGrant
from storefront.views.qr import QR_COOKIE, QR_COOKIE_SALT


class QrThanksTests(TestCase):
    request_headers = {
        "HTTP_ACCEPT": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "HTTP_ACCEPT_LANGUAGE": "uk",
        "HTTP_USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/140.0.0.0 Safari/537.36"
        ),
        "REMOTE_ADDR": "192.0.2.17",
    }

    @patch("threading.Thread")
    def test_qr_get_keeps_promo_cookie_and_pageviews_without_request_owned_alert(
        self, thread_class
    ):
        url = reverse("qr_thanks")

        first_response = self.client.get(url, **self.request_headers)

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(first_response.headers["X-Robots-Tag"], "noindex, nofollow")
        self.assertEqual(PromoCode.objects.count(), 1)
        self.assertEqual(QrDeviceGrant.objects.count(), 1)
        self.assertEqual(PageView.objects.filter(path=url, is_bot=False).count(), 1)
        promo = PromoCode.objects.get()
        self.assertEqual(
            signing.loads(first_response.cookies[QR_COOKIE].value, salt=QR_COOKIE_SALT),
            promo.code,
        )
        self.assertNotIn("qr_scan_notified", self.client.session)

        second_response = self.client.get(url, **self.request_headers)

        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(PromoCode.objects.count(), 1)
        self.assertEqual(QrDeviceGrant.objects.count(), 1)
        self.assertEqual(PageView.objects.filter(path=url, is_bot=False).count(), 2)
        self.assertEqual(
            signing.loads(second_response.cookies[QR_COOKIE].value, salt=QR_COOKIE_SALT),
            promo.code,
        )
        self.assertNotIn("qr_scan_notified", self.client.session)
        thread_class.assert_not_called()
