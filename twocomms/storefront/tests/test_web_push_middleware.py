from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, override_settings

from twocomms.middleware import ForceHTTPSMiddleware


@override_settings(DEBUG=False)
class ForceHTTPSMiddlewareTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = ForceHTTPSMiddleware(lambda request: HttpResponse("ok"))

    def test_service_worker_path_skips_https_redirect(self):
        request = self.factory.get("/sw.js", secure=False, HTTP_HOST="twocomms.shop")

        response = self.middleware.process_request(request)

        self.assertIsNone(response)

