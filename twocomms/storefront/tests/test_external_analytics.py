from unittest.mock import Mock, patch

import requests
from django.test import TestCase

from storefront.services.external_analytics import get_clarity_status, get_ga4_status


class ExternalAnalyticsTests(TestCase):
    @patch.dict(
        "os.environ",
        {"GA4_PROPERTY_ID": "G-109EFTWM05"},
        clear=False,
    )
    def test_ga4_status_rejects_measurement_id_as_property_id(self):
        status = get_ga4_status(test_connection=False)
        self.assertEqual(status["status"], "warning")
        self.assertIn("numeric", status["message"])

    @patch.dict(
        "os.environ",
        {"CLARITY_API_TOKEN": "clarity-token"},
        clear=False,
    )
    @patch("storefront.services.external_analytics._clarity_request")
    def test_clarity_status_uses_uncached_live_check_and_surfaces_http_status(self, clarity_request_mock):
        response = Mock(status_code=403)
        clarity_request_mock.side_effect = requests.HTTPError("403 Client Error", response=response)

        status = get_clarity_status(test_connection=True)

        clarity_request_mock.assert_called_once_with(num_of_days=1, use_cache=False)
        self.assertEqual(status["status"], "error")
        self.assertEqual(status["details"]["http_status"], 403)
