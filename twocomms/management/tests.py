from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from .models import Client, ClientFollowUp, Report
from .stats_service import compute_kpd, parse_stats_range
from .views import _close_followups_for_report, _sync_client_followup


class StatsRangeTests(TestCase):
    def test_parse_today_range(self):
        r = parse_stats_range({"period": "today"}, now=timezone.now())
        self.assertEqual(r.period, "today")
        self.assertEqual(r.start_date, timezone.localdate())
        self.assertEqual(r.end_date, timezone.localdate())
        self.assertLess(r.start, r.end)


class KpdTests(TestCase):
    def test_kpd_non_negative(self):
        cfg = {"kpd": {}, "advice": {}}
        metrics = {
            "active_seconds": 0,
            "points": 0,
            "processed": 0,
            "success_weighted": 0,
            "followups_total": 0,
            "followups_missed": 0,
            "cp_email_sent": 0,
            "shops_created": 0,
            "invoices_created": 0,
            "report_days_required": 0,
            "report_days_late": 0,
        }
        out = compute_kpd(metrics, cfg)
        self.assertGreaterEqual(out["value"], 0.0)

    def test_kpd_penalty_reduces_value(self):
        cfg = {"kpd": {}, "advice": {}}
        base = {
            "active_seconds": 3 * 3600,
            "points": 120,
            "processed": 30,
            "success_weighted": 10,
            "cp_email_sent": 2,
            "shops_created": 1,
            "invoices_created": 1,
            "report_days_required": 5,
            "report_days_late": 0,
        }
        ok = compute_kpd({**base, "followups_total": 10, "followups_missed": 0}, cfg)["value"]
        bad = compute_kpd({**base, "followups_total": 10, "followups_missed": 5}, cfg)["value"]
        self.assertGreater(ok, bad)


class FollowUpTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="mgr", password="x")

    def test_followup_created_and_closed(self):
        now = timezone.now()
        due = now + timedelta(hours=2)
        client = Client.objects.create(
            shop_name="S",
            phone="+380000000000",
            full_name="N",
            owner=self.user,
            next_call_at=due,
        )
        _sync_client_followup(client, None, client.next_call_at, now)

        fu = ClientFollowUp.objects.get(client=client, owner=self.user)
        self.assertEqual(fu.status, ClientFollowUp.Status.OPEN)

        # Clear next_call_at -> cancelled
        prev = client.next_call_at
        client.next_call_at = None
        client.save(update_fields=["next_call_at"])
        _sync_client_followup(client, prev, client.next_call_at, now + timedelta(minutes=5))

        fu.refresh_from_db()
        self.assertEqual(fu.status, ClientFollowUp.Status.CANCELLED)

    def test_followup_reschedule_vs_done(self):
        now = timezone.now()
        due = now + timedelta(hours=5)
        client = Client.objects.create(
            shop_name="S",
            phone="+380000000000",
            full_name="N",
            owner=self.user,
            next_call_at=due,
        )
        _sync_client_followup(client, None, client.next_call_at, now)
        fu = ClientFollowUp.objects.get(client=client, owner=self.user)

        # Reschedule before due -> rescheduled
        new_due = now + timedelta(hours=6)
        prev = client.next_call_at
        client.next_call_at = new_due
        client.save(update_fields=["next_call_at"])
        _sync_client_followup(client, prev, client.next_call_at, now + timedelta(minutes=10))
        fu.refresh_from_db()
        self.assertEqual(fu.status, ClientFollowUp.Status.RESCHEDULED)

        # New open followup exists
        self.assertTrue(
            ClientFollowUp.objects.filter(client=client, owner=self.user, status=ClientFollowUp.Status.OPEN).exists()
        )

        # Move after original due -> done
        open_fu = ClientFollowUp.objects.filter(client=client, owner=self.user, status=ClientFollowUp.Status.OPEN).first()
        later = timezone.now() + timedelta(hours=10)
        prev2 = client.next_call_at
        client.next_call_at = later
        client.save(update_fields=["next_call_at"])
        _sync_client_followup(client, prev2, client.next_call_at, now + timedelta(hours=7))
        open_fu.refresh_from_db()
        self.assertIn(open_fu.status, {ClientFollowUp.Status.DONE, ClientFollowUp.Status.RESCHEDULED})

    def test_followups_marked_missed_on_report(self):
        now = timezone.now()
        due = now + timedelta(hours=1)
        client = Client.objects.create(
            shop_name="S",
            phone="+380000000000",
            full_name="N",
            owner=self.user,
            next_call_at=due,
        )
        _sync_client_followup(client, None, client.next_call_at, now)

        report = Report.objects.create(owner=self.user, points=0, processed=0)
        _close_followups_for_report(report)

        fu = ClientFollowUp.objects.get(client=client, owner=self.user)
        self.assertEqual(fu.status, ClientFollowUp.Status.MISSED)
        self.assertEqual(fu.closed_by_report_id, report.id)
