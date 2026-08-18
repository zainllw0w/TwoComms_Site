from datetime import timedelta

from django.tasks import Task
from django.tasks.exceptions import InvalidTask
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from task_runtime.models import DurableTask
from task_runtime.runtime import (
    ALLOWED_TASKS,
    DurableTaskBackend,
    InvalidTaskPayload,
    NO_SIDE_EFFECT_TASKS,
    TaskNotOwned,
    claim_due_tasks,
    enqueue_durable_task,
    finish_task,
    reclaim_expired_tasks,
    run_bounded_worker,
)


def canary_task(*, object_id):
    return {"object_id": object_id}


def context_task(context, *, object_id):
    return {"object_id": object_id}


CANARY_NAME = f"{canary_task.__module__}.{canary_task.__qualname__}"


class DurableTaskContractTests(SimpleTestCase):
    def setUp(self):
        ALLOWED_TASKS[CANARY_NAME] = canary_task
        NO_SIDE_EFFECT_TASKS.add(CANARY_NAME)
        self.addCleanup(ALLOWED_TASKS.pop, CANARY_NAME)
        self.addCleanup(NO_SIDE_EFFECT_TASKS.discard, CANARY_NAME)

    def test_allowlist_rejects_unknown_task_and_non_json_payload(self):
        with self.assertRaises(InvalidTaskPayload):
            enqueue_durable_task("unknown.task", {"object_id": 1}, "key-1")
        with self.assertRaises(InvalidTaskPayload):
            enqueue_durable_task(CANARY_NAME, {"object_id": object()}, "key-2")


class DurableTaskDatabaseTests(TestCase):
    def setUp(self):
        ALLOWED_TASKS[CANARY_NAME] = canary_task
        NO_SIDE_EFFECT_TASKS.add(CANARY_NAME)
        self.addCleanup(ALLOWED_TASKS.pop, CANARY_NAME)
        self.addCleanup(NO_SIDE_EFFECT_TASKS.discard, CANARY_NAME)

    def test_idempotency_and_bounded_claim(self):
        first = enqueue_durable_task(CANARY_NAME, {"object_id": 7}, "same-key")
        duplicate = enqueue_durable_task(CANARY_NAME, {"object_id": 7}, "same-key")
        self.assertEqual(first.pk, duplicate.pk)
        self.assertEqual(DurableTask.objects.count(), 1)
        with self.assertRaises(InvalidTaskPayload):
            enqueue_durable_task(CANARY_NAME, {"object_id": 8}, "same-key")
        claimed = claim_due_tasks(limit=1, lease_seconds=30, worker_id="worker-a")
        self.assertEqual([job.pk for job in claimed], [first.pk])
        self.assertEqual(claim_due_tasks(limit=1, lease_seconds=30, worker_id="worker-b"), [])

    def test_reclaim_and_fencing_protects_stale_owner(self):
        job = enqueue_durable_task(CANARY_NAME, {"object_id": 8}, "reclaim-key")
        claimed = claim_due_tasks(limit=1, lease_seconds=1, worker_id="worker-a")[0]
        DurableTask.objects.filter(pk=job.pk).update(
            lease_expires_at=timezone.now() - timedelta(seconds=1)
        )
        self.assertEqual(reclaim_expired_tasks(limit=10), 1)
        replacement = claim_due_tasks(limit=1, lease_seconds=30, worker_id="worker-b")[0]
        self.assertNotEqual(claimed.lease_token, replacement.lease_token)
        with self.assertRaises(TaskNotOwned):
            finish_task(job.pk, claimed.lease_token, success=True)
        finish_task(job.pk, replacement.lease_token, success=True)
        self.assertEqual(DurableTask.objects.get(pk=job.pk).status, DurableTask.Status.DONE)

    def test_backend_is_explicitly_durable_and_enqueues_json(self):
        backend = DurableTaskBackend(alias="durable", params={})
        self.assertTrue(backend.supports_durable_enqueue)
        task = Task(func=canary_task, backend="durable")
        first = backend.enqueue(task, (), {"object_id": 7})
        second = backend.enqueue(task, (), {"object_id": 7})
        self.assertNotEqual(first.id, second.id)
        self.assertEqual(DurableTask.objects.count(), 2)

    def test_context_tasks_fail_closed_before_enqueue(self):
        with self.assertRaises(InvalidTask):
            Task(func=context_task, backend="durable", takes_context=True)

    def test_fenced_task_is_lost_and_does_not_abort_batch(self):
        def lose_lease(*, object_id):
            DurableTask.objects.filter(pk=object_id).update(lease_token="new-owner")
            return {"object_id": object_id}

        lose_name = f"{lose_lease.__module__}.{lose_lease.__qualname__}"
        success_name = f"{canary_task.__module__}.{canary_task.__qualname__}.second"
        ALLOWED_TASKS[lose_name] = lose_lease
        ALLOWED_TASKS[success_name] = canary_task
        NO_SIDE_EFFECT_TASKS.add(lose_name)
        NO_SIDE_EFFECT_TASKS.add(success_name)
        self.addCleanup(ALLOWED_TASKS.pop, lose_name)
        self.addCleanup(ALLOWED_TASKS.pop, success_name)
        self.addCleanup(NO_SIDE_EFFECT_TASKS.discard, lose_name)
        self.addCleanup(NO_SIDE_EFFECT_TASKS.discard, success_name)

        first = enqueue_durable_task(lose_name, {"object_id": 0}, "lost-key")
        DurableTask.objects.filter(pk=first.pk).update(payload={"object_id": first.pk})
        second = enqueue_durable_task(success_name, {"object_id": 2}, "second-key")

        outcome = run_bounded_worker(limit=2, lease_seconds=30, worker_id="worker-a")

        self.assertEqual(outcome, {"claimed": 2, "completed": 1, "failed": 0, "lost": 1})
        self.assertEqual(DurableTask.objects.get(pk=second.pk).status, DurableTask.Status.DONE)
        self.assertEqual(DurableTask.objects.get(pk=first.pk).status, DurableTask.Status.RUNNING)
