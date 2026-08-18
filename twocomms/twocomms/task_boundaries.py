"""Explicit sync ORM boundaries for future async/task adapters.

Django's ORM transactions remain synchronous in Django 6.1.  A task adapter
must therefore cross an async or worker boundary with a scalar identifier,
then resolve its state and write it inside a fresh synchronous transaction.
This module keeps that rule in one small, reusable contract instead of
relying on each adapter to remember the connection lifecycle details.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar
from uuid import UUID

from asgiref.sync import sync_to_async
from django.db import close_old_connections, connections, transaction
from django.db.models import Model


TaskID = int | str | UUID
Result = TypeVar("Result")


class HeavyTaskBackendUnavailable(RuntimeError):
    """Raised when heavy work has no proven durable task backend."""


_DURABLE_CAPABILITY_ATTR = "supports_durable_enqueue"


def _backend_path(backend: object) -> str:
    backend_type = backend if isinstance(backend, type) else type(backend)
    return f"{backend_type.__module__}.{backend_type.__qualname__}"


def _resolve_task_backend(alias: str) -> object:
    """Resolve a configured Django Tasks backend, failing closed on errors."""

    try:
        from django.tasks import task_backends

        return task_backends[alias]
    except Exception as exc:  # pragma: no cover - exercised by integration setup
        raise HeavyTaskBackendUnavailable(
            f"Cannot verify durable backend alias {alias!r}; "
            "heavy task enqueue is blocked"
        ) from exc


def require_durable_task_backend(
    backend: object | None = None,
    *,
    alias: str = "default",
    task_name: str | None = None,
) -> object:
    """Return a backend only when it explicitly proves durable enqueue.

    Django's built-in ``ImmediateBackend`` and ``DummyBackend`` are useful for
    development, but neither provides a worker-backed queue.  Unknown backend
    implementations also fail closed until their adapter exposes the explicit
    ``supports_durable_enqueue = True`` capability marker after infrastructure
    validation.
    """

    if backend is None:
        backend = _resolve_task_backend(alias)

    backend_path = _backend_path(backend)
    task_label = f" {task_name!r}" if task_name else ""

    try:
        from django.tasks.backends.dummy import DummyBackend
        from django.tasks.backends.immediate import ImmediateBackend

        builtin_non_durable = isinstance(backend, (ImmediateBackend, DummyBackend))
    except Exception:  # pragma: no cover - Django 6.1 always provides both
        builtin_non_durable = backend_path in {
            "django.tasks.backends.immediate.ImmediateBackend",
            "django.tasks.backends.dummy.DummyBackend",
        }

    if builtin_non_durable or getattr(backend, _DURABLE_CAPABILITY_ATTR, False) is not True:
        raise HeavyTaskBackendUnavailable(
            f"Heavy task enqueue{task_label} is blocked: backend "
            f"{backend_path!r} is not proven durable; configure a worker-backed "
            f"adapter with {_DURABLE_CAPABILITY_ATTR}=True"
        )

    return backend


def enqueue_heavy_task(task: object, *args: object, **kwargs: object) -> object:
    """Enqueue a Django 6.1 Task only after the durable-backend gate."""

    try:
        backend = task.get_backend()  # type: ignore[attr-defined]
    except Exception as exc:
        raise HeavyTaskBackendUnavailable(
            "Cannot inspect the heavy task backend; enqueue is blocked"
        ) from exc

    require_durable_task_backend(
        backend,
        alias=getattr(task, "backend", "default"),
        task_name=getattr(task, "name", None),
    )
    return task.enqueue(*args, **kwargs)  # type: ignore[attr-defined]


async def aenqueue_heavy_task(task: object, *args: object, **kwargs: object) -> object:
    """Async counterpart of :func:`enqueue_heavy_task`."""

    try:
        backend = task.get_backend()  # type: ignore[attr-defined]
    except Exception as exc:
        raise HeavyTaskBackendUnavailable(
            "Cannot inspect the heavy task backend; enqueue is blocked"
        ) from exc

    require_durable_task_backend(
        backend,
        alias=getattr(task, "backend", "default"),
        task_name=getattr(task, "name", None),
    )
    return await task.aenqueue(*args, **kwargs)  # type: ignore[attr-defined]


def _validate_task_id(value: object) -> TaskID:
    """Return a supported task identifier, rejecting ORM state at the edge."""

    if isinstance(value, Model):
        raise TypeError("task adapters must receive a scalar ID, not an ORM instance")
    if isinstance(value, bool) or not isinstance(value, (int, str, UUID)):
        raise TypeError("task adapters must receive a scalar ID")
    return value


def run_in_sync_transaction(
    task_id: object,
    operation: Callable[[TaskID], Result],
    *,
    using: str = "default",
) -> Result:
    """Run an ID-based task operation in its own synchronous transaction.

    Callers should invoke this from the worker/task context, not from a
    request's transaction.  Failing closed when the selected connection is
    already inside ``atomic()`` prevents a request transaction from leaking
    into a future async adapter.  The callback receives only the validated
    scalar identifier; it must resolve any ORM objects inside this boundary.
    """

    scalar_id = _validate_task_id(task_id)
    connection = connections[using]
    if connection.in_atomic_block:
        raise RuntimeError(
            "sync task transaction must start outside an existing transaction"
        )

    close_old_connections()
    try:
        with transaction.atomic(using=using):
            return operation(scalar_id)
    finally:
        # Worker threads must not retain a request/task connection for a later
        # job.  ``close_old_connections`` is Django's supported lifecycle hook.
        close_old_connections()


async def run_in_async_task_boundary(
    task_id: object,
    operation: Callable[[TaskID], Result],
    *,
    using: str = "default",
) -> Result:
    """Bridge a future async task adapter to the synchronous ORM contract.

    Pass a scalar ID before awaiting this function and resolve ORM state only
    inside ``operation``.  ``thread_sensitive=True`` keeps Django's
    thread-local connection and transaction state on the synchronous side of
    the boundary.  No production task uses this adapter yet; it is the
    required entry point for a future async caller.
    """

    return await sync_to_async(run_in_sync_transaction, thread_sensitive=True)(
        task_id,
        operation,
        using=using,
    )
