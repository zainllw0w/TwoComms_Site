"""Recover catalog image jobs after a web-process restart or worker failure."""

from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from product_catalog.image_jobs import run_image_optimization_job
from product_catalog.models import ImageOptimizationJob


class Command(BaseCommand):
    help = "Requeue stale catalog image jobs and process a bounded batch."

    def add_arguments(self, parser):
        parser.add_argument("--max-jobs", type=int, default=20)
        parser.add_argument("--stale-after-seconds", type=int, default=1800)
        parser.add_argument(
            "--retention-days",
            type=int,
            default=30,
            help="Delete completed/error/cancelled jobs older than this many days.",
        )
        parser.add_argument(
            "--cleanup-limit",
            type=int,
            default=1000,
            help="Maximum terminal history rows to delete per run.",
        )
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        max_jobs = options["max_jobs"]
        stale_after = options["stale_after_seconds"]
        retention_days = options["retention_days"]
        cleanup_limit = options["cleanup_limit"]
        if max_jobs < 1:
            raise CommandError("--max-jobs must be positive")
        if stale_after < 1:
            raise CommandError("--stale-after-seconds must be positive")
        if retention_days < 1:
            raise CommandError("--retention-days must be positive")
        if cleanup_limit < 1:
            raise CommandError("--cleanup-limit must be positive")

        now = timezone.now()
        cutoff = now - timedelta(seconds=stale_after)
        retention_cutoff = now - timedelta(days=retention_days)
        terminal_statuses = (
            ImageOptimizationJob.Status.COMPLETED,
            ImageOptimizationJob.Status.ERROR,
            ImageOptimizationJob.Status.CANCELLED,
        )
        newer_job = ImageOptimizationJob.objects.filter(
            model_label=OuterRef("model_label"),
            object_id=OuterRef("object_id"),
            field_name=OuterRef("field_name"),
        ).filter(
            Q(created_at__gt=OuterRef("created_at"))
            | Q(created_at=OuterRef("created_at"), id__gt=OuterRef("id"))
        )
        cleanup_ids = list(
            ImageOptimizationJob.objects.annotate(has_newer_job=Exists(newer_job))
            .filter(
                status__in=terminal_statuses,
                updated_at__lt=retention_cutoff,
                has_newer_job=True,
            )
            .order_by("updated_at", "id")
            .values_list("id", flat=True)[:cleanup_limit]
        )
        cleaned = 0
        if not options["dry_run"] and cleanup_ids:
            cleaned, _ = ImageOptimizationJob.objects.filter(id__in=cleanup_ids).delete()

        stale = list(
            ImageOptimizationJob.objects.filter(
                status=ImageOptimizationJob.Status.RUNNING,
                updated_at__lt=cutoff,
            )
            .order_by("updated_at", "id")
            .values_list("id", "updated_at")[:max_jobs]
        )
        stale_ids = [job_id for job_id, _updated_at in stale]

        if not options["dry_run"] and stale_ids:
            ImageOptimizationJob.objects.filter(
                id__in=stale_ids,
                status=ImageOptimizationJob.Status.RUNNING,
                updated_at__lt=cutoff,
            ).update(
                status=ImageOptimizationJob.Status.PENDING,
                stage="queued",
                progress=0,
                error_message="",
                lease_token="",
                started_at=None,
                updated_at=now,
            )

        pending_ids = list(
            ImageOptimizationJob.objects.filter(
                status=ImageOptimizationJob.Status.PENDING,
            )
            .order_by("created_at", "id")
            .values_list("id", flat=True)[:max_jobs]
        )

        if not options["dry_run"]:
            for job_id in pending_ids:
                run_image_optimization_job(job_id)

        mode = "would process" if options["dry_run"] else "processed"
        self.stdout.write(
            f"Reconciled image jobs: requeued={len(stale_ids)} "
            f"{mode}={len(pending_ids)} cleaned={cleaned if not options['dry_run'] else len(cleanup_ids)}"
        )
