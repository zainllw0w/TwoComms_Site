from __future__ import annotations

import hashlib
import json
from datetime import timedelta
from uuid import uuid4

from django.db import IntegrityError, close_old_connections, connection, models, transaction
from django.tasks.backends.base import BaseTaskBackend
from django.tasks.base import Task, TaskError, TaskResult, TaskResultStatus
from django.tasks.exceptions import TaskResultDoesNotExist
from django.utils import timezone
from django.utils.json import normalize_json

from .models import DurableTask


class InvalidTaskPayload(ValueError):
    """Task name or payload is outside the durable adapter contract."""


class TaskNotOwned(RuntimeError):
    """A stale worker attempted to mutate a reclaimed task."""


ALLOWED_TASKS: dict[str, object] = {}


def register_task(task_name: str, callback):
    if not isinstance(task_name, str) or not task_name or len(task_name) > 255:
        raise InvalidTaskPayload("task name must be a non-empty string")
    if not isinstance(callback, Task) and not callable(callback):
        raise InvalidTaskPayload("callback must be a callable or Django Task")
    ALLOWED_TASKS[task_name] = callback
    return callback


def _json_payload(payload: object) -> dict:
    if not isinstance(payload, dict):
        raise InvalidTaskPayload("payload must be a JSON object")
    try:
        encoded = json.dumps(
            normalize_json(payload),
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
        )
        normalized = json.loads(encoded)
    except (TypeError, ValueError) as exc:
        raise InvalidTaskPayload("payload must contain JSON-safe values") from exc
    return normalized


def _bounded_limit(value: int, *, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1 or value > maximum:
        raise ValueError("bounded task limit is invalid")
    return value


def enqueue_durable_task(task_name: str, payload: object, idempotency_key: str, *, available_at=None):
    if task_name not in ALLOWED_TASKS:
        raise InvalidTaskPayload(f"task {task_name!r} is not allowlisted")
    if not isinstance(idempotency_key, str) or not idempotency_key or len(idempotency_key) > 180:
        raise InvalidTaskPayload("idempotency_key must be a non-empty string")
    normalized = _json_payload(payload)
    available_at = available_at or timezone.now()
    try:
        with transaction.atomic():
            job = DurableTask.objects.create(
                task_name=task_name,
                payload=normalized,
                idempotency_key=idempotency_key,
                available_at=available_at,
            )
    except IntegrityError:
        job = DurableTask.objects.get(idempotency_key=idempotency_key)
        if job.task_name != task_name or job.payload != normalized:
            raise InvalidTaskPayload("idempotency key is already bound to another payload")
    return job


def reclaim_expired_tasks(*, limit=100):
    limit = _bounded_limit(limit, maximum=1000)
    now = timezone.now()
    with transaction.atomic():
        jobs = (
            DurableTask.objects.filter(
                status=DurableTask.Status.RUNNING,
                lease_expires_at__lt=now,
            )
            .order_by("id")[:limit]
        )
        ids = list(jobs.values_list("id", flat=True))
        if not ids:
            return 0
        return DurableTask.objects.filter(
            id__in=ids,
            status=DurableTask.Status.RUNNING,
        ).update(
            status=DurableTask.Status.PENDING,
            lease_token="",
            lease_expires_at=None,
            worker_id="",
            last_error="lease expired; reclaimed",
            completed_at=None,
        )


def claim_due_tasks(*, limit=25, lease_seconds=60, worker_id):
    limit = _bounded_limit(limit, maximum=1000)
    if (
        isinstance(lease_seconds, bool)
        or not isinstance(lease_seconds, int)
        or lease_seconds < 1
        or lease_seconds > 3600
    ):
        raise ValueError("bounded lease duration is invalid")
    if not isinstance(worker_id, str) or not worker_id or len(worker_id) > 128:
        raise ValueError("worker_id must be a non-empty string")

    now = timezone.now()
    token_until = now + timedelta(seconds=lease_seconds)
    claimed = []
    with transaction.atomic():
        queryset = DurableTask.objects.filter(
            status=DurableTask.Status.PENDING,
            available_at__lte=now,
        ).order_by("id")[:limit]
        if connection.features.has_select_for_update_skip_locked:
            queryset = queryset.select_for_update(skip_locked=True)
        else:
            queryset = queryset.select_for_update()
        rows = list(queryset)
        for row in rows:
            token = uuid4().hex
            changed = DurableTask.objects.filter(
                pk=row.pk,
                status=DurableTask.Status.PENDING,
            ).update(
                status=DurableTask.Status.RUNNING,
                lease_token=token,
                lease_expires_at=token_until,
                worker_id=worker_id,
                attempts=models.F("attempts") + 1,
                started_at=now,
            )
            if changed:
                row.refresh_from_db()
                claimed.append(row)
    return claimed


def finish_task(task_id, lease_token: str, *, success: bool, result=None, error=""):
    if not isinstance(lease_token, str) or not lease_token:
        raise TaskNotOwned(f"task {task_id} lease is no longer owned")
    normalized_result = None
    if success:
        try:
            normalized_result = _json_payload(result) if isinstance(result, dict) else normalize_json(result)
            json.dumps(normalized_result, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise InvalidTaskPayload("task result must be JSON-safe") from exc
    values = {
        "status": DurableTask.Status.DONE if success else DurableTask.Status.FAILED,
        "result": normalized_result if success else None,
        "last_error": "" if success else str(error)[:1000],
        "lease_token": "",
        "lease_expires_at": None,
        "completed_at": timezone.now(),
    }
    changed = DurableTask.objects.filter(
        pk=task_id,
        status=DurableTask.Status.RUNNING,
        lease_token=lease_token,
    ).update(**values)
    if changed != 1:
        raise TaskNotOwned(f"task {task_id} lease is no longer owned")


def _invoke(callback, payload):
    if isinstance(callback, Task):
        return callback.call(*payload.get("args", []), **payload.get("kwargs", {}))
    return callback(**payload)


def run_bounded_worker(*, limit=25, lease_seconds=60, worker_id="cron"):
    close_old_connections()
    try:
        reclaim_expired_tasks(limit=limit)
        rows = claim_due_tasks(
            limit=limit,
            lease_seconds=lease_seconds,
            worker_id=worker_id,
        )
        completed = failed = 0
        for row in rows:
            callback = ALLOWED_TASKS.get(row.task_name)
            try:
                if callback is None:
                    raise InvalidTaskPayload(f"task {row.task_name!r} is not registered")
                value = _invoke(callback, row.payload)
                finish_task(row.pk, row.lease_token, success=True, result=value)
                completed += 1
            except Exception as exc:
                finish_task(
                    row.pk,
                    row.lease_token,
                    success=False,
                    error=f"{type(exc).__name__}: {exc}",
                )
                failed += 1
        return {"claimed": len(rows), "completed": completed, "failed": failed}
    finally:
        close_old_connections()


class DurableTaskBackend(BaseTaskBackend):
    """Opt-in MariaDB-backed adapter; the project default stays ImmediateBackend."""

    supports_durable_enqueue = True
    supports_defer = True
    supports_get_result = True

    def enqueue(self, task, args, kwargs):
        self.validate_task(task)
        payload = {
            "args": normalize_json(list(args)),
            "kwargs": normalize_json(kwargs),
        }
        try:
            json.dumps(payload, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise InvalidTaskPayload("Django task arguments must be JSON-safe") from exc
        if task.module_path not in ALLOWED_TASKS:
            raise InvalidTaskPayload(f"task {task.module_path!r} is not allowlisted")
        digest = hashlib.sha256(
            json.dumps(
                {"task": task.module_path, **payload},
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        row = enqueue_durable_task(
            task.module_path,
            payload,
            digest,
            available_at=task.run_after,
        )
        return self._result(task, row)

    def get_result(self, result_id):
        try:
            row = DurableTask.objects.get(pk=result_id)
        except DurableTask.DoesNotExist as exc:
            raise TaskResultDoesNotExist from exc
        callback = ALLOWED_TASKS.get(row.task_name)
        if callback is None:
            raise TaskResultDoesNotExist
        task = callback if isinstance(callback, Task) else Task(func=callback, backend=self.alias)
        return self._result(task, row)

    def _result(self, task, row):
        status = {
            DurableTask.Status.PENDING: TaskResultStatus.READY,
            DurableTask.Status.RUNNING: TaskResultStatus.RUNNING,
            DurableTask.Status.DONE: TaskResultStatus.SUCCESSFUL,
            DurableTask.Status.FAILED: TaskResultStatus.FAILED,
        }[row.status]
        errors = []
        if row.last_error:
            errors.append(
                TaskError(
                    exception_class_path="builtins.RuntimeError",
                    traceback=row.last_error,
                )
            )
        payload = row.payload if isinstance(row.payload, dict) else {}
        result = TaskResult(
            task=task,
            id=str(row.pk),
            status=status,
            enqueued_at=row.created_at,
            started_at=row.started_at,
            last_attempted_at=row.updated_at,
            finished_at=row.completed_at,
            args=payload.get("args", []),
            kwargs=payload.get("kwargs", {}),
            backend=self.alias,
            errors=errors,
            worker_ids=[row.worker_id] if row.worker_id else [],
        )
        if status == TaskResultStatus.SUCCESSFUL:
            object.__setattr__(result, "_return_value", row.result)
        return result
