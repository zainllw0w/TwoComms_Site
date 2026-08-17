"""Executable contract for sync transaction boundaries around task adapters."""

from __future__ import annotations

from threading import Thread, get_ident
from unittest.mock import MagicMock, patch

from asgiref.sync import async_to_sync
from django.db import connection, transaction
from django.test import TransactionTestCase

from orders.models import Order


class SyncTaskTransactionBoundaryTests(TransactionTestCase):
    """A future async/task adapter must re-enter ORM work from an ID."""

    def test_runner_rejects_orm_instances_before_entering_a_task(self):
        from twocomms.task_boundaries import run_in_sync_transaction

        with self.assertRaisesRegex(TypeError, "scalar ID"):
            run_in_sync_transaction(Order(), lambda _order_id: None)

    def test_runner_owns_sync_transaction_on_worker_connection(self):
        from twocomms.task_boundaries import run_in_sync_transaction

        observed: dict[str, object] = {}

        def callback(task_id: int) -> int:
            observed["thread_id"] = get_ident()
            observed["task_id"] = task_id
            observed["inside_atomic"] = connection.in_atomic_block
            return task_id

        with transaction.atomic():
            request_thread_id = get_ident()
            self.assertTrue(connection.in_atomic_block)

            worker_error: list[BaseException] = []

            def worker() -> None:
                try:
                    observed["result"] = run_in_sync_transaction(42, callback)
                except BaseException as exc:  # pragma: no cover - assertion below
                    worker_error.append(exc)

            thread = Thread(target=worker, name="django61-boundary-contract")
            thread.start()
            thread.join(timeout=5)

            self.assertFalse(thread.is_alive(), "worker did not finish")
            self.assertEqual(worker_error, [])
            self.assertEqual(observed["result"], 42)
            self.assertEqual(observed["task_id"], 42)
            self.assertTrue(observed["inside_atomic"])
            self.assertNotEqual(observed["thread_id"], request_thread_id)
            # The request transaction remains owned by the request thread.
            self.assertTrue(connection.in_atomic_block)

    def test_runner_rejects_call_from_an_existing_request_transaction(self):
        from twocomms.task_boundaries import run_in_sync_transaction

        with transaction.atomic():
            with self.assertRaisesRegex(RuntimeError, "outside an existing transaction"):
                run_in_sync_transaction(42, lambda _task_id: None)

    def test_async_adapter_defers_orm_lookup_until_the_sync_transaction(self):
        from twocomms.task_boundaries import run_in_async_task_boundary

        order = Order.objects.create(
            full_name="Async boundary",
            phone="+380000000001",
            city="Kyiv",
            np_office="1",
        )
        observed: dict[str, object] = {}

        def resolve_order(task_id: int) -> int:
            observed["inside_atomic"] = connection.in_atomic_block
            observed["resolved_order_id"] = Order.objects.get(pk=task_id).pk
            return task_id

        result = async_to_sync(run_in_async_task_boundary)(order.pk, resolve_order)

        self.assertEqual(result, order.pk)
        self.assertTrue(observed["inside_atomic"])
        self.assertEqual(observed["resolved_order_id"], order.pk)

    def test_runner_uses_selected_alias_and_refreshes_connections(self):
        from twocomms.task_boundaries import run_in_sync_transaction

        selected_connection = MagicMock()
        selected_connection.in_atomic_block = False
        atomic = MagicMock()

        with (
            patch("twocomms.task_boundaries.connections", {"task": selected_connection}),
            patch("twocomms.task_boundaries.transaction.atomic", atomic),
            patch("twocomms.task_boundaries.close_old_connections") as lifecycle,
        ):
            result = run_in_sync_transaction(42, lambda task_id: task_id, using="task")

        self.assertEqual(result, 42)
        self.assertEqual(atomic.call_args_list, [((), {"using": "task"})])
        self.assertEqual(lifecycle.call_count, 2)
