from unittest.mock import Mock, patch

from django.conf import settings
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, override_settings

from orders.nova_poshta_middleware import NovaPoshtaFallbackMiddleware


class NovaPoshtaBackgroundOwnershipTests(SimpleTestCase):
    def test_request_stack_does_not_install_tracking_middleware(self):
        self.assertNotIn(
            "orders.nova_poshta_middleware.NovaPoshtaFallbackMiddleware",
            settings.MIDDLEWARE,
        )

    @override_settings(NOVA_POSHTA_FALLBACK_ENABLED=True)
    def test_legacy_flag_cannot_start_request_owned_tracking_thread(self):
        request = RequestFactory().get("/", HTTP_HOST="twocomms.shop")
        get_response = Mock(return_value=HttpResponse("ok"))
        middleware = NovaPoshtaFallbackMiddleware(get_response)

        with patch("threading.Thread") as thread:
            response = middleware(request)

        self.assertEqual(response.status_code, 200)
        get_response.assert_called_once_with(request)
        thread.assert_not_called()
