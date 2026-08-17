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
