"""
Coverage for the AnalyticsExclusion helper layer:
- snapshot caching + invalidation,
- IP / CIDR / user / visitor / UA / path matching,
- queryset Q-builders return falsy ``Q()`` when nothing is configured.
"""
from __future__ import annotations

from django.core.cache import cache
from django.test import RequestFactory, TestCase

from storefront.analytics_exclusions import (
    CACHE_KEY,
    action_exclusion_q,
    get_snapshot,
    invalidate_snapshot,
    is_request_excluded,
    order_exclusion_q,
    pageview_exclusion_q,
    session_exclusion_q,
    utm_session_exclusion_q,
)
from storefront.models import AnalyticsExclusion


class AnalyticsExclusionSnapshotTests(TestCase):
    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()

    def test_snapshot_groups_entries_by_kind(self):
        AnalyticsExclusion.objects.create(kind="ip", value="192.168.1.10")
        AnalyticsExclusion.objects.create(kind="ip", value="10.0.0.0/24")
        AnalyticsExclusion.objects.create(kind="user", value="42")
        AnalyticsExclusion.objects.create(kind="visitor", value="vid-x")
        AnalyticsExclusion.objects.create(kind="user_agent", value="HeadlessChrome")
        AnalyticsExclusion.objects.create(kind="path", value="/admin-panel/")

        invalidate_snapshot()
        snap = get_snapshot()
        self.assertIn("192.168.1.10", snap.ips)
        self.assertEqual(len(snap.networks), 1)
        self.assertIn(42, snap.user_ids)
        self.assertIn("vid-x", snap.visitor_ids)
        self.assertIn("headlesschrome", snap.user_agents)
        self.assertIn("/admin-panel/", snap.paths)

    def test_inactive_exclusions_are_ignored(self):
        AnalyticsExclusion.objects.create(kind="ip", value="1.2.3.4", is_active=False)
        invalidate_snapshot()
        snap = get_snapshot()
        self.assertNotIn("1.2.3.4", snap.ips)

    def test_empty_snapshot_is_falsy(self):
        invalidate_snapshot()
        snap = get_snapshot()
        self.assertTrue(snap.is_empty)
        self.assertFalse(session_exclusion_q())
        self.assertFalse(utm_session_exclusion_q())
        self.assertFalse(pageview_exclusion_q())
        self.assertFalse(action_exclusion_q())
        self.assertFalse(order_exclusion_q())

    def test_is_request_excluded_matches_ip_and_cidr(self):
        AnalyticsExclusion.objects.create(kind="ip", value="10.0.0.0/24")
        invalidate_snapshot()

        request = self.factory.get("/", HTTP_X_FORWARDED_FOR="10.0.0.5")
        self.assertTrue(is_request_excluded(request, ip="10.0.0.5"))
        self.assertFalse(is_request_excluded(request, ip="11.0.0.5"))

    def test_is_request_excluded_matches_user_agent_substring(self):
        AnalyticsExclusion.objects.create(kind="user_agent", value="Acme-Bot")
        invalidate_snapshot()

        request = self.factory.get("/", HTTP_USER_AGENT="Mozilla/5.0 (Acme-Bot/1.0)")
        self.assertTrue(is_request_excluded(request))

    def test_is_request_excluded_matches_path_prefix(self):
        AnalyticsExclusion.objects.create(kind="path", value="/internal/")
        invalidate_snapshot()

        request = self.factory.get("/internal/dashboard/")
        self.assertTrue(is_request_excluded(request))

        public = self.factory.get("/catalog/")
        self.assertFalse(is_request_excluded(public))

    def test_invalidation_drops_cache(self):
        AnalyticsExclusion.objects.create(kind="ip", value="9.9.9.9")
        get_snapshot()
        self.assertIsNotNone(cache.get(CACHE_KEY))
        invalidate_snapshot()
        self.assertIsNone(cache.get(CACHE_KEY))
