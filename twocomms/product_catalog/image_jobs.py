"""Durable image optimization jobs used by the catalog editor.

Uploads are intentionally split into two phases: the request persists the
image and a pending job, then a short-lived background thread performs the
existing WebP/AVIF optimizer. The persisted row is also recoverable through
``reconcile_image_optimization_jobs``, so a web-process restart does not leave
the editor with an orphaned queue entry.
"""

from __future__ import annotations

import concurrent.futures
import logging
from datetime import timedelta
from threading import Lock
from uuid import uuid4

from django.apps import apps
from django.conf import settings
from django.db import close_old_connections, transaction
from django.db.models import F
from django.utils import timezone

from .models import ImageOptimizationJob

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = (
    ImageOptimizationJob.Status.PENDING,
    ImageOptimizationJob.Status.RUNNING,
)
STALE_JOB_AFTER = timedelta(minutes=30)
_IMAGE_JOB_EXECUTOR = None
_IMAGE_JOB_EXECUTOR_LOCK = Lock()
_IMAGE_JOB_SCHEDULED = set()
_IMAGE_JOB_SCHEDULED_LOCK = Lock()


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


def _optimized_variants_current(instance, field_name: str) -> bool:
    image_field = getattr(instance, field_name, None)
    try:
        source_path = image_field.path
    except Exception:
        return False
    from pathlib import Path

    from storefront.services.image_variants import optimized_variants_are_current

    path = Path(source_path)
    return path.exists() and optimized_variants_are_current(path)


def image_job_payload(instance, field_name: str = "image") -> dict:
    job = latest_image_job(instance, field_name)
    if job is None:
        payload = {
            "id": None,
            "status": "saved",
            "stage": "saved",
            "progress": 100,
            "error_message": "",
            "attempts": 0,
            "updated_at": None,
        }
        if _source_name(instance, field_name) and not _optimized_variants_current(
            instance, field_name
        ):
            payload.update(
                status=ImageOptimizationJob.Status.ERROR,
                stage="error",
                progress=0,
                error_message="Оптимізовані файли відсутні або застаріли",
            )
        return payload
    if (
        job.status == ImageOptimizationJob.Status.COMPLETED
        and not _optimized_variants_current(instance, field_name)
    ):
        payload = _job_payload(job)
        payload.update(
            status=ImageOptimizationJob.Status.ERROR,
            stage="error",
            progress=0,
            error_message="Оптимізовані файли відсутні або застаріли",
        )
        return payload
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
            lease_token="",
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
        transaction.on_commit(
            lambda job_id=job.pk: schedule_image_optimization(job_id),
            robust=True,
        )
    return job


def _resolve_instance(job: ImageOptimizationJob):
    try:
        app_label, model_name = job.model_label.split(".", 1)
        model = apps.get_model(app_label, model_name)
    except (ValueError, LookupError):
        return None
    return model.objects.filter(pk=job.object_id).first()


def _mark(
    job_id: int,
    *,
    expected_status=None,
    expected_lease_token=None,
    **values,
) -> int:
    jobs = ImageOptimizationJob.objects.filter(pk=job_id)
    if expected_status is not None:
        jobs = jobs.filter(status=expected_status)
    if expected_lease_token is not None:
        jobs = jobs.filter(lease_token=expected_lease_token)
    return jobs.update(**values, updated_at=timezone.now())


def run_image_optimization_job(job_id: int) -> None:
    """Run one job idempotently and persist a terminal state."""
    now = timezone.now()
    lease_token = uuid4().hex
    claimed = ImageOptimizationJob.objects.filter(
        pk=job_id,
        status=ImageOptimizationJob.Status.PENDING,
    ).update(
        status=ImageOptimizationJob.Status.RUNNING,
        stage="optimizing",
        progress=None,
        error_message="",
        lease_token=lease_token,
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
            lease_token="",
            completed_at=timezone.now(),
            expected_status=ImageOptimizationJob.Status.RUNNING,
            expected_lease_token=lease_token,
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
            lease_token="",
            completed_at=timezone.now(),
            expected_status=ImageOptimizationJob.Status.RUNNING,
            expected_lease_token=lease_token,
        )
        return

    try:
        from storefront.tasks import optimize_image_field_task
        from storefront.services.image_variants import optimized_variants_are_current

        def report_progress(stage, progress):
            _mark(
                job.pk,
                status=ImageOptimizationJob.Status.RUNNING,
                stage=stage,
                progress=progress,
                expected_status=ImageOptimizationJob.Status.RUNNING,
                expected_lease_token=lease_token,
            )

        _mark(
            job.pk,
            status=ImageOptimizationJob.Status.RUNNING,
            stage="loading",
            progress=5,
            expected_status=ImageOptimizationJob.Status.RUNNING,
            expected_lease_token=lease_token,
        )
        optimize_image_field_task(
            job.model_label,
            job.object_id,
            job.field_name,
            report_progress,
        )
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
                lease_token="",
                completed_at=timezone.now(),
                expected_status=ImageOptimizationJob.Status.RUNNING,
                expected_lease_token=lease_token,
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
            error_message=str(exc)[:1000],
            lease_token="",
            completed_at=timezone.now(),
            expected_status=ImageOptimizationJob.Status.RUNNING,
            expected_lease_token=lease_token,
        )
        return

    _mark(
        job.pk,
        status=ImageOptimizationJob.Status.COMPLETED,
        stage="ready",
        progress=100,
        error_message="",
        lease_token="",
        completed_at=timezone.now(),
        expected_status=ImageOptimizationJob.Status.RUNNING,
        expected_lease_token=lease_token,
    )


def _run_scheduled_image_job(job_id: int) -> None:
    close_old_connections()
    try:
        run_image_optimization_job(job_id)
    finally:
        with _IMAGE_JOB_SCHEDULED_LOCK:
            _IMAGE_JOB_SCHEDULED.discard(job_id)
        close_old_connections()


def _image_job_executor():
    global _IMAGE_JOB_EXECUTOR
    if _IMAGE_JOB_EXECUTOR is None:
        with _IMAGE_JOB_EXECUTOR_LOCK:
            if _IMAGE_JOB_EXECUTOR is None:
                worker_count = max(
                    1,
                    int(getattr(settings, "PRODUCT_CATALOG_IMAGE_WORKERS", 1)),
                )
                _IMAGE_JOB_EXECUTOR = concurrent.futures.ThreadPoolExecutor(
                    max_workers=worker_count,
                    thread_name_prefix="catalog-image",
                )
    return _IMAGE_JOB_EXECUTOR


def _image_job_submission_capacity() -> int:
    worker_count = max(
        1,
        int(getattr(settings, "PRODUCT_CATALOG_IMAGE_WORKERS", 1)),
    )
    queue_capacity = max(
        0,
        int(
            getattr(
                settings,
                "PRODUCT_CATALOG_IMAGE_QUEUE_CAPACITY",
                worker_count,
            )
        ),
    )
    return worker_count + queue_capacity


def schedule_image_optimization(job_id: int) -> None:
    """Submit work while keeping the executor's internal queue bounded."""
    if getattr(settings, "TESTING", False):
        return
    with _IMAGE_JOB_SCHEDULED_LOCK:
        if job_id in _IMAGE_JOB_SCHEDULED:
            return
        if len(_IMAGE_JOB_SCHEDULED) >= _image_job_submission_capacity():
            logger.info(
                "Image optimization job %s remains pending because local capacity is full",
                job_id,
            )
            return
        _IMAGE_JOB_SCHEDULED.add(job_id)
    try:
        _image_job_executor().submit(_run_scheduled_image_job, job_id)
    except Exception:
        with _IMAGE_JOB_SCHEDULED_LOCK:
            _IMAGE_JOB_SCHEDULED.discard(job_id)
        raise


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
            lease_token="",
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
    if job.status in ACTIVE_STATUSES:
        return job
    if (
        job.status == ImageOptimizationJob.Status.COMPLETED
        and _optimized_variants_current(instance, field_name)
    ):
        return job
    job.status = ImageOptimizationJob.Status.PENDING
    job.stage = "queued"
    job.progress = 0
    job.error_message = ""
    job.lease_token = ""
    job.source_name = _source_name(instance, field_name)
    job.started_at = None
    job.completed_at = None
    job.save(update_fields=("status", "stage", "progress", "error_message", "lease_token", "source_name", "started_at", "completed_at", "updated_at"))
    transaction.on_commit(
        lambda job_id=job.pk: schedule_image_optimization(job_id),
        robust=True,
    )
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
        lease_token="",
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
