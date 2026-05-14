from unittest.mock import Mock, patch

import requests
from django.core.cache import cache
from django.test import TestCase

from storefront.services import external_analytics as ext
from storefront.services.external_analytics import (
    ClarityQuotaExhausted,
    _clarity_budget_allows_call,
    _clarity_request,
    _record_clarity_call,
    get_clarity_quota_state,
    get_clarity_status,
    get_ga4_status,
)


class ExternalAnalyticsTests(TestCase):
    def setUp(self):
        cache.clear()
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

        clarity_request_mock.assert_called_once_with(
            num_of_days=1, use_cache=False, allow_reserve=True
        )
        self.assertEqual(status["status"], "error")
        self.assertEqual(status["details"]["http_status"], 403)
        self.assertIn("Settings", status["message"])  # actionable instruction

    @patch.dict(
        "os.environ",
        {"CLARITY_API_TOKEN": "clarity-token"},
        clear=False,
    )
    @patch("storefront.services.external_analytics._clarity_request")
    def test_clarity_status_treats_5xx_as_warning_not_error(self, clarity_request_mock):
        """Microsoft-side outages must not paint the dashboard red."""
        response = Mock(status_code=500)
        clarity_request_mock.side_effect = requests.HTTPError("500 Server Error", response=response)

        status = get_clarity_status(test_connection=True)

        self.assertEqual(status["status"], "warning")
        self.assertEqual(status["details"]["http_status"], 500)
        self.assertIn("тимчасово недоступний", status["message"])

    @patch.dict(
        "os.environ",
        {"CLARITY_API_TOKEN": "clarity-token"},
        clear=False,
    )
    @patch("storefront.services.external_analytics._http_get_with_retry")
    def test_clarity_request_counts_against_daily_quota(self, http_mock):
        """Every live call (success or failure) must increment the counter."""
        ok = Mock()
        ok.status_code = 200
        ok.json.return_value = []
        ok.raise_for_status.return_value = None
        http_mock.return_value = ok

        state_before = get_clarity_quota_state()
        _clarity_request(num_of_days=1, use_cache=False)
        state_after = get_clarity_quota_state()

        self.assertEqual(state_after["used"], state_before["used"] + 1)

    @patch.dict(
        "os.environ",
        {"CLARITY_API_TOKEN": "clarity-token"},
        clear=False,
    )
    def test_clarity_request_refuses_call_once_budget_is_exhausted(self):
        """Pre-flight check stops us from torching the 10/day quota."""
        # Burn the budget down to the reserve floor.
        for _ in range(ext.CLARITY_DAILY_BUDGET - ext.CLARITY_BUDGET_RESERVE):
            _record_clarity_call()

        self.assertFalse(_clarity_budget_allows_call())
        with self.assertRaises(ClarityQuotaExhausted):
            _clarity_request(num_of_days=1, use_cache=False)

    @patch.dict(
        "os.environ",
        {"CLARITY_API_TOKEN": "clarity-token"},
        clear=False,
    )
    def test_clarity_status_reports_quota_when_exhausted(self):
        """When budget is exhausted we must short-circuit before any live ping."""
        for _ in range(ext.CLARITY_DAILY_BUDGET):
            _record_clarity_call()

        status = get_clarity_status(test_connection=True)

        self.assertEqual(status["status"], "warning")
        self.assertIn("квота", status["message"].lower())
        self.assertEqual(status["details"]["daily_quota_remaining"], 0)
