"""Regression contracts for fail-closed Django 6.1 heavy-task dispatch."""

from __future__ import annotations

import asyncio

from django.tasks.backends.dummy import DummyBackend
from django.tasks.backends.immediate import ImmediateBackend
from django.test import SimpleTestCase

from twocomms.task_boundaries import (
    HeavyTaskBackendUnavailable,
    aenqueue_heavy_task,
    enqueue_heavy_task,
    require_durable_task_backend,
)


class _Task:
    name = "heavy_task"

    def __init__(self, backend):
        self._backend = backend
        self.enqueued = []

    def get_backend(self):
        return self._backend

    def enqueue(self, *args, **kwargs):
        self.enqueued.append((args, kwargs))
        return "queued"

    async def aenqueue(self, *args, **kwargs):
        self.enqueued.append((args, kwargs))
        return "async-queued"


class _ProvenDurableBackend:
    supports_durable_enqueue = True


class HeavyTaskBackendGuardTests(SimpleTestCase):
    def test_default_backend_is_resolved_and_rejected(self):
        with self.assertRaisesRegex(
            HeavyTaskBackendUnavailable,
            r"ImmediateBackend.*durable",
        ):
            require_durable_task_backend(task_name="heavy_task")

    def test_immediate_backend_is_rejected_before_task_execution(self):
        backend = ImmediateBackend(alias="default", params={})
        task = _Task(backend)

        with self.assertRaisesRegex(
            HeavyTaskBackendUnavailable,
            r"heavy_task.*ImmediateBackend.*durable",
        ):
            enqueue_heavy_task(task, 42)

        self.assertEqual(task.enqueued, [])

    def test_dummy_backend_is_rejected_as_non_durable(self):
        backend = DummyBackend(alias="default", params={})

        with self.assertRaises(HeavyTaskBackendUnavailable):
            require_durable_task_backend(backend, task_name="heavy_task")

    def test_unknown_backend_is_rejected_without_explicit_capability_proof(self):
        with self.assertRaises(HeavyTaskBackendUnavailable):
            require_durable_task_backend(object(), task_name="heavy_task")

    def test_explicit_durable_capability_allows_enqueue(self):
        backend = _ProvenDurableBackend()
        task = _Task(backend)

        self.assertIs(require_durable_task_backend(backend), backend)
        self.assertEqual(enqueue_heavy_task(task, 42, priority=3), "queued")
        self.assertEqual(task.enqueued, [((42,), {"priority": 3})])

    def test_async_enqueue_uses_the_same_guard(self):
        task = _Task(_ProvenDurableBackend())

        self.assertEqual(asyncio.run(aenqueue_heavy_task(task)), "async-queued")
        self.assertEqual(task.enqueued, [((), {})])
