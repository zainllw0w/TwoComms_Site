"""Durable image optimization jobs used by the catalog editor.

Uploads are intentionally split into two phases: the request persists the
image and a pending job, then a short-lived background thread performs the
existing WebP/AVIF optimizer. The persisted row is also recoverable through
``reconcile_image_optimization_jobs``, so a web-process restart does not leave
the editor with an orphaned queue entry.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from threading import Thread

from django.apps import apps
from django.db import close_old_connections, transaction
from django.db.models import F
from django.utils import timezone

from .models import ImageOptimizationJob

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = (
    ImageOptimizationJob.Status.PENDING,
    ImageOptimizationJob.Status.RUNNING,
)
STALE_JOB_AFTER = timedelta(minutes=5)


def _model_label(instance) -> str:
    return instance._meta.label_lower


def _source_name(instance, field_name: str) -> str:
    image_field = getattr(instance, field_name, None)
    return getattr(image_field, "name", "") or ""


def _job_payload(job: ImageOptimizationJob | None) -> dict:
    if job is None:
        return {}
    return {
        "id": job.pk,
        "status": job.status,
        "stage": job.stage,
        "progress": job.progress,
        "error_message": job.error_message or "",
        "attempts": job.attempts,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
    }


def latest_image_job(instance, field_name: str = "image") -> ImageOptimizationJob | None:
    return (
        ImageOptimizationJob.objects.filter(
            model_label=_model_label(instance), object_id=instance.pk, field_name=field_name
        )
        .order_by("-created_at", "-id")
        .first()
    )


def image_job_payload(instance, field_name: str = "image") -> dict:
    job = latest_image_job(instance, field_name)
    if job is None:
        return {
            "id": None,
            "status": "saved",
            "stage": "saved",
            "progress": 100,
            "error_message": "",
            "attempts": 0,
            "updated_at": None,
        }
    return _job_payload(job)


def enqueue_image_optimization(instance, field_name: str = "image") -> ImageOptimizationJob | None:
    """Persist a queued job and schedule exactly one runner after commit."""
    source_name = _source_name(instance, field_name)
    if not source_name or not getattr(instance, "pk", None):
        return None

    now = timezone.now()
    identity = {
        "model_label": _model_label(instance),
        "object_id": instance.pk,
        "field_name": field_name,
    }
    with transaction.atomic():
        ImageOptimizationJob.objects.filter(
            **identity,
            status__in=ACTIVE_STATUSES,
        ).update(
            status=ImageOptimizationJob.Status.CANCELLED,
            stage="superseded",
            progress=100,
            completed_at=now,
            updated_at=now,
        )
        job = ImageOptimizationJob.objects.create(
            **identity,
            source_name=source_name,
            status=ImageOptimizationJob.Status.PENDING,
            stage="queued",
            progress=0,
        )
        transaction.on_commit(lambda job_id=job.pk: schedule_image_optimization(job_id))
    return job


def _resolve_instance(job: ImageOptimizationJob):
    try:
        app_label, model_name = job.model_label.split(".", 1)
        model = apps.get_model(app_label, model_name)
    except (ValueError, LookupError):
        return None
    return model.objects.filter(pk=job.object_id).first()


def _mark(job_id: int, *, expected_status=None, **values) -> int:
    jobs = ImageOptimizationJob.objects.filter(pk=job_id)
    if expected_status is not None:
        jobs = jobs.filter(status=expected_status)
    return jobs.update(**values, updated_at=timezone.now())


def run_image_optimization_job(job_id: int) -> None:
    """Run one job idempotently and persist a terminal state."""
    now = timezone.now()
    claimed = ImageOptimizationJob.objects.filter(
        pk=job_id,
        status=ImageOptimizationJob.Status.PENDING,
    ).update(
        status=ImageOptimizationJob.Status.RUNNING,
        stage="optimizing",
        progress=None,
        error_message="",
        started_at=now,
        attempts=F("attempts") + 1,
        updated_at=now,
    )
    if claimed != 1:
        return

    job = ImageOptimizationJob.objects.get(pk=job_id)

    instance = _resolve_instance(job)
    if instance is None:
        _mark(
            job.pk,
            status=ImageOptimizationJob.Status.CANCELLED,
            stage="cancelled",
            progress=100,
            error_message="",
            completed_at=timezone.now(),
            expected_status=ImageOptimizationJob.Status.RUNNING,
        )
        return

    image_field = getattr(instance, job.field_name, None)
    if not image_field or _source_name(instance, job.field_name) != job.source_name:
        _mark(
            job.pk,
            status=ImageOptimizationJob.Status.CANCELLED,
            stage="superseded",
            progress=100,
            error_message="",
            completed_at=timezone.now(),
            expected_status=ImageOptimizationJob.Status.RUNNING,
        )
        return

    try:
        from storefront.tasks import optimize_image_field_task
        from storefront.services.image_variants import optimized_variants_are_current

        optimize_image_field_task(job.model_label, job.object_id, job.field_name)
        current_instance = _resolve_instance(job)
        if (
            current_instance is None
            or _source_name(current_instance, job.field_name) != job.source_name
        ):
            _mark(
                job.pk,
                status=ImageOptimizationJob.Status.CANCELLED,
                stage="superseded",
                progress=100,
                error_message="",
                completed_at=timezone.now(),
                expected_status=ImageOptimizationJob.Status.RUNNING,
            )
            return
        try:
            source_path = getattr(current_instance, job.field_name).path
        except Exception as exc:
            raise RuntimeError("Не вдалося визначити файл зображення") from exc
        from pathlib import Path

        path = Path(source_path)
        if not path.exists() or not optimized_variants_are_current(path):
            raise RuntimeError("Оптимізовані WebP/AVIF-версії ще не готові")
    except Exception as exc:  # pragma: no cover - exercised through API retry tests
        logger.exception("Image optimization job %s failed", job_id)
        _mark(
            job.pk,
            status=ImageOptimizationJob.Status.ERROR,
            stage="error",
            progress=0,
            error_message=str(exc)[:1000],
            completed_at=timezone.now(),
            expected_status=ImageOptimizationJob.Status.RUNNING,
        )
        return

    _mark(
        job.pk,
        status=ImageOptimizationJob.Status.COMPLETED,
        stage="ready",
        progress=100,
        error_message="",
        completed_at=timezone.now(),
        expected_status=ImageOptimizationJob.Status.RUNNING,
    )


def schedule_image_optimization(job_id: int) -> None:
    """Start a daemon runner without making the upload request wait."""
    def runner():
        close_old_connections()
        try:
            run_image_optimization_job(job_id)
        finally:
            close_old_connections()

    thread = Thread(target=runner, daemon=True)
    thread.start()


def resume_image_optimization(instance, field_name: str = "image") -> ImageOptimizationJob | None:
    """Recover a persisted pending/stale job when an editor reconnects."""
    job = latest_image_job(instance, field_name)
    if job is None:
        return None
    if (
        job.status == ImageOptimizationJob.Status.RUNNING
        and job.updated_at < timezone.now() - STALE_JOB_AFTER
    ):
        recovered = ImageOptimizationJob.objects.filter(
            pk=job.pk,
            status=ImageOptimizationJob.Status.RUNNING,
            updated_at=job.updated_at,
        ).update(
            status=ImageOptimizationJob.Status.PENDING,
            stage="queued",
            progress=0,
            error_message="",
            updated_at=timezone.now(),
        )
        if recovered:
            job.refresh_from_db()
    if job.status == ImageOptimizationJob.Status.PENDING:
        schedule_image_optimization(job.pk)
    return job


def retry_image_optimization(instance, field_name: str = "image") -> ImageOptimizationJob | None:
    """Reset the latest job or create one, then schedule one fresh attempt."""
    job = latest_image_job(instance, field_name)
    if job is None:
        return enqueue_image_optimization(instance, field_name)
    if job.status in ACTIVE_STATUSES or job.status == ImageOptimizationJob.Status.COMPLETED:
        return job
    job.status = ImageOptimizationJob.Status.PENDING
    job.stage = "queued"
    job.progress = 0
    job.error_message = ""
    job.source_name = _source_name(instance, field_name)
    job.started_at = None
    job.completed_at = None
    job.save(update_fields=("status", "stage", "progress", "error_message", "source_name", "started_at", "completed_at", "updated_at"))
    transaction.on_commit(lambda job_id=job.pk: schedule_image_optimization(job_id))
    return job


def cancel_image_jobs(instance, field_name: str = "image") -> int:
    return ImageOptimizationJob.objects.filter(
        model_label=_model_label(instance),
        object_id=instance.pk,
        field_name=field_name,
        status__in=ACTIVE_STATUSES,
    ).update(
        status=ImageOptimizationJob.Status.CANCELLED,
        stage="cancelled",
        progress=100,
        completed_at=timezone.now(),
        updated_at=timezone.now(),
    )


__all__ = [
    "cancel_image_jobs",
    "enqueue_image_optimization",
    "image_job_payload",
    "latest_image_job",
    "resume_image_optimization",
    "retry_image_optimization",
    "run_image_optimization_job",
    "schedule_image_optimization",
]
