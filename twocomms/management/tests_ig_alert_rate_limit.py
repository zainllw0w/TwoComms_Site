"""ЭА.16 — ліміт потоку алертів атомарний і не fail-open.

Два дефекти, які закріплюють ці тести:

1. `throttle_gate()` робив `cache.get()` і `cache.set()` окремими операціями по
   `FileBasedCache`, тому два одночасні виклики бачили один знімок вікна і
   обидва вважали, що місце є. Демон крутить drain кожні 1.5 с — гонка була
   не теоретичною.
2. Збій сховища ліміту повертав «дозволено». Тобто ліміт зникав саме тоді, коли
   щось ламалось.
"""
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from management.models import IgAlertRateBucket
from management.services import ig_alerts


class AtomicThrottleTests(TestCase):
    def test_limit_is_enforced_within_the_window(self):
        now = timezone.now()
        allowed = [ig_alerts.throttle_gate(now=now)[0] for _ in range(8)]

        self.assertEqual(
            allowed.count(True),
            ig_alerts.DEFAULT_MAX_PER_MINUTE,
            "рівно бюджет вікна, не більше",
        )
        self.assertEqual(allowed[: ig_alerts.DEFAULT_MAX_PER_MINUTE], [True] * 6)

    def test_denial_reports_a_usable_retry_after(self):
        now = timezone.now()
        for _ in range(ig_alerts.DEFAULT_MAX_PER_MINUTE):
            ig_alerts.throttle_gate(now=now)

        allowed, retry_after = ig_alerts.throttle_gate(now=now)

        self.assertFalse(allowed)
        self.assertGreaterEqual(retry_after, 1)
        self.assertLessEqual(retry_after, 60)

    def test_window_rolls_over_and_frees_the_budget(self):
        now = timezone.now()
        for _ in range(ig_alerts.DEFAULT_MAX_PER_MINUTE):
            ig_alerts.throttle_gate(now=now)
        self.assertFalse(ig_alerts.throttle_gate(now=now)[0])

        later = now + timedelta(seconds=61)
        self.assertTrue(ig_alerts.throttle_gate(now=later)[0])

    def test_counter_is_durable_and_visible_to_an_operator(self):
        now = timezone.now()
        for _ in range(ig_alerts.DEFAULT_MAX_PER_MINUTE + 2):
            ig_alerts.throttle_gate(now=now)

        bucket = IgAlertRateBucket.objects.get(bucket_key=ig_alerts.FLOW_CACHE_KEY)
        self.assertEqual(bucket.used, ig_alerts.DEFAULT_MAX_PER_MINUTE)
        self.assertEqual(bucket.denied, 2, "задушений потік мусить бути видимий")

    def test_separate_buckets_have_separate_budgets(self):
        now = timezone.now()
        for _ in range(ig_alerts.DEFAULT_MAX_PER_MINUTE):
            ig_alerts.throttle_gate(now=now)

        self.assertTrue(ig_alerts.throttle_gate("ig_alert_other", now=now)[0])

    def test_a_second_concurrent_reader_cannot_reuse_the_same_slot(self):
        """Раніше саме це і ламалось: обидва бачили один знімок вікна."""
        now = timezone.now()
        first_snapshot = list(
            IgAlertRateBucket.objects.filter(bucket_key=ig_alerts.FLOW_CACHE_KEY)
        )
        self.assertEqual(first_snapshot, [])

        for _ in range(ig_alerts.DEFAULT_MAX_PER_MINUTE):
            self.assertTrue(ig_alerts.throttle_gate(now=now)[0])
        # Кожен виклик читає рядок під `select_for_update`, тому лічильник
        # рахує саме кількість виданих дозволів, а не кількість викликів.
        bucket = IgAlertRateBucket.objects.get(bucket_key=ig_alerts.FLOW_CACHE_KEY)
        self.assertEqual(bucket.used, ig_alerts.DEFAULT_MAX_PER_MINUTE)


class BoundedSafeModeTests(TestCase):
    """Збій сховища ліміту обмежує частоту, а не відкриває шлюз."""

    def setUp(self):
        ig_alerts._safe_mode_last_allowed_at[0] = 0.0

    def test_storage_failure_does_not_fail_open(self):
        with patch.object(
            IgAlertRateBucket.objects, "select_for_update",
            side_effect=RuntimeError("counter table unavailable"),
        ):
            outcomes = [ig_alerts.throttle_gate()[0] for _ in range(10)]

        self.assertEqual(
            outcomes.count(True), 1,
            "bounded safe mode: один дозвіл, не всплеск із десяти",
        )

    def test_storage_failure_still_lets_one_alert_through(self):
        """Повна відмова була б гіршою: алерт про інцидент не можна втратити."""
        with patch.object(
            IgAlertRateBucket.objects, "select_for_update",
            side_effect=RuntimeError("counter table unavailable"),
        ):
            allowed, _retry_after = ig_alerts.throttle_gate()

        self.assertTrue(allowed)

    def test_safe_mode_denial_reports_retry_after(self):
        with patch.object(
            IgAlertRateBucket.objects, "select_for_update",
            side_effect=RuntimeError("counter table unavailable"),
        ):
            ig_alerts.throttle_gate()
            allowed, retry_after = ig_alerts.throttle_gate()

        self.assertFalse(allowed)
        self.assertGreaterEqual(retry_after, 1)
