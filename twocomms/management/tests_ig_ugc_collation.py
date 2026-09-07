from unittest.mock import patch

from django.core.cache import cache
from django.db import OperationalError
from django.test import SimpleTestCase, override_settings

from management.services.ig_ugc_assessment import reconcile_pending_ugc_media


@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
class UgcCollationFaultTests(SimpleTestCase):
    def tearDown(self):
        cache.clear()

    def test_sql_shape_fault_defers_only_ugc_without_repeated_queries(self):
        with patch(
            "management.services.ig_ugc_assessment.pending_ugc_review_notifications",
            side_effect=OperationalError(1267, "synthetic collation mismatch"),
        ) as selector:
            with self.assertLogs("management.services.ig_ugc_assessment", level="ERROR") as logged:
                first = reconcile_pending_ugc_media(limit=1)
            second = reconcile_pending_ugc_media(limit=1)
        self.assertEqual(first["collation_deferred"], 1)
        self.assertEqual(second["collation_deferred"], 1)
        self.assertEqual(selector.call_count, 1)
        self.assertEqual(len(logged.output), 1)
        self.assertEqual(first["selected"], 0)

    def test_connection_outage_is_not_hidden_as_permanent_sql_fault(self):
        with patch(
            "management.services.ig_ugc_assessment.pending_ugc_review_notifications",
            side_effect=OperationalError(2013, "synthetic disconnect"),
        ), self.assertRaises(OperationalError):
            reconcile_pending_ugc_media(limit=1)
