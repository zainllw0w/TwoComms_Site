from datetime import timedelta
from io import StringIO
from types import SimpleNamespace
from unittest.mock import ANY, patch

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from management.ig_bot_models import IgClient, IgFollowRefreshJob


class FollowReconciliationCommandTests(TestCase):
    def test_limit_one_never_processes_more_than_one_item_across_payment_and_follow_queues(self):
        from management.services.ig_follow_reconcile import (
            reconcile_follow_intelligence_once,
        )

        now = timezone.now()
        preparation = SimpleNamespace(pk=101)
        follow_job = SimpleNamespace(
            pk=202,
            status=IgFollowRefreshJob.Status.PENDING,
            due_at=now - timedelta(minutes=1),
            next_attempt_at=None,
            lease_expires_at=None,
        )

        with (
            patch(
                "management.services.ig_follow_reconcile._due_payment_follow_preparations",
                return_value=[preparation],
            ),
            patch(
                "management.services.ig_follow_reconcile._due_follow_jobs",
                return_value=[follow_job],
            ),
            patch(
                "management.services.ig_follow_reconcile._due_ugc_deliveries",
                return_value=[],
            ),
            patch(
                "management.services.ig_follow_cta.reconcile_expired_follow_reservations",
                return_value={},
            ),
            patch(
                "management.services.ig_follow_cta.process_payment_follow_preparation",
                return_value="prepared",
            ) as process_payment,
            patch(
                "management.services.ig_follow_state.run_follow_refresh_job",
                return_value="known",
            ) as run_follow,
            patch(
                "management.services.ig_ugc_rewards.process_external_ugc_reward_delivery"
            ) as process_ugc,
        ):
            counts = reconcile_follow_intelligence_once(limit=1, now=now)

        self.assertEqual(
            counts["payment_selected"]
            + counts["follow_selected"]
            + counts["ugc_selected"],
            1,
        )
        process_payment.assert_called_once_with(preparation.pk, now=now)
        run_follow.assert_not_called()
        process_ugc.assert_not_called()

    def test_reconcile_processes_only_due_follow_jobs_within_bound(self):
        client = IgClient.objects.create(igsid="reconcile-follow-client")
        now = timezone.now()
        due = IgFollowRefreshJob.objects.create(
            client=client,
            due_at=now - timedelta(minutes=1),
            status=IgFollowRefreshJob.Status.PENDING,
        )
        future = IgFollowRefreshJob.objects.create(
            client=IgClient.objects.create(igsid="reconcile-follow-future"),
            due_at=now + timedelta(hours=1),
            status=IgFollowRefreshJob.Status.PENDING,
        )
        output = StringIO()
        with patch(
            "management.services.ig_follow_state.run_follow_refresh_job",
            return_value="known",
        ) as run:
            call_command(
                "reconcile_ig_follow_intelligence",
                limit=1,
                stdout=output,
            )

        run.assert_called_once_with(due.pk, now=ANY)
        future.refresh_from_db()
        self.assertEqual(future.status, IgFollowRefreshJob.Status.PENDING)
        self.assertIn("follow_selected=1", output.getvalue())

    def test_reconcile_dry_run_does_not_run_provider_jobs(self):
        client = IgClient.objects.create(igsid="reconcile-follow-dry")
        IgFollowRefreshJob.objects.create(
            client=client,
            due_at=timezone.now() - timedelta(minutes=1),
            status=IgFollowRefreshJob.Status.PENDING,
        )
        with patch("management.services.ig_follow_state.run_follow_refresh_job") as run:
            call_command(
                "reconcile_ig_follow_intelligence",
                limit=10,
                dry_run=True,
                stdout=StringIO(),
            )
        run.assert_not_called()


class FollowReconciliationFairnessTests(TestCase):
    def test_ugc_quota_is_reserved_when_follow_queue_is_continuously_due(self):
        """A busy follow queue must not starve mandatory reward delivery."""
        from management.services.ig_follow_reconcile import (
            select_reconciliation_batch,
        )

        now = timezone.now()
        follow_jobs = [
            SimpleNamespace(
                pk=index,
                status=IgFollowRefreshJob.Status.PENDING,
                due_at=now - timedelta(minutes=index + 1),
                next_attempt_at=None,
                lease_expires_at=None,
            )
            for index in range(1, 5)
        ]
        deliveries = [
            SimpleNamespace(
                pk=90,
                state="pending",
                due_at=now - timedelta(minutes=1),
                lease_expires_at=None,
            )
        ]

        selected_follow, selected_ugc = select_reconciliation_batch(
            follow_jobs,
            deliveries,
            limit=3,
            now=now,
        )

        self.assertEqual([row.pk for row in selected_follow], [1, 2])
        self.assertEqual([row.pk for row in selected_ugc], [90])

    def test_follow_retry_uses_next_attempt_at_not_original_due_at(self):
        from management.services.ig_follow_reconcile import is_follow_job_due

        now = timezone.now()
        delayed = SimpleNamespace(
            status=IgFollowRefreshJob.Status.FAILED,
            due_at=now - timedelta(hours=2),
            next_attempt_at=now + timedelta(hours=1),
            lease_expires_at=None,
        )

        self.assertFalse(is_follow_job_due(delayed, now=now))

    def test_daemon_reconciler_runs_even_when_reply_processing_is_disabled(self):
        from management.management.commands.run_instagram_bot import (
            _follow_intelligence_worker,
        )

        stop_event = __import__("threading").Event()

        def reconcile_once(**kwargs):
            stop_event.set()
            return {"follow_selected": 0, "ugc_selected": 0}

        with patch(
            "management.services.ig_follow_reconcile.reconcile_follow_intelligence_once",
            side_effect=reconcile_once,
        ) as reconcile, patch(
            "management.management.commands.run_instagram_bot.maintenance_status",
            return_value={"active": False},
        ):
            _follow_intelligence_worker(stop_event)

        reconcile.assert_called_once()
