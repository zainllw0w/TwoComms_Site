from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.db import OperationalError
from django.test import SimpleTestCase

from twocomms.db_resilience import retry_mysql_read, retry_mysql_read_view


class RetryMysqlReadTests(SimpleTestCase):
    @patch("twocomms.db_resilience.connections")
    def test_reconnects_once_after_mysql_disconnect(self, connections):
        db = connections.__getitem__.return_value
        db.in_atomic_block = False
        operation = Mock(
            side_effect=[OperationalError(2006, "server has gone away"), "ok"]
        )

        self.assertEqual(retry_mysql_read(operation), "ok")

        self.assertEqual(operation.call_count, 2)
        db.close.assert_called_once_with()

    @patch("twocomms.db_resilience.connections")
    def test_returns_explicit_fallback_after_second_disconnect(self, connections):
        db = connections.__getitem__.return_value
        db.in_atomic_block = False
        operation = Mock(side_effect=OperationalError(2013, "lost connection"))

        self.assertEqual(retry_mysql_read(operation, fallback=[]), [])

        self.assertEqual(operation.call_count, 2)
        self.assertEqual(db.close.call_count, 2)

    @patch("twocomms.db_resilience.connections")
    def test_does_not_retry_other_database_errors(self, connections):
        operation = Mock(side_effect=OperationalError(1040, "too many connections"))

        with self.assertRaises(OperationalError):
            retry_mysql_read(operation)

        operation.assert_called_once_with()
        connections.__getitem__.return_value.close.assert_not_called()

    @patch("twocomms.db_resilience.connections")
    def test_does_not_retry_inside_atomic_block(self, connections):
        db = connections.__getitem__.return_value
        db.in_atomic_block = True
        operation = Mock(side_effect=OperationalError(2006, "server has gone away"))

        with self.assertRaises(OperationalError):
            retry_mysql_read(operation)

        operation.assert_called_once_with()
        db.close.assert_not_called()

    @patch("twocomms.db_resilience.retry_mysql_read")
    def test_view_boundary_only_retries_safe_methods(self, retry):
        retry.side_effect = lambda operation, **_kwargs: operation()
        view = Mock(return_value="response")
        wrapped = retry_mysql_read_view(view)

        self.assertEqual(wrapped(SimpleNamespace(method="GET")), "response")
        self.assertEqual(retry.call_count, 1)

        self.assertEqual(wrapped(SimpleNamespace(method="POST")), "response")
        self.assertEqual(retry.call_count, 1)
        self.assertEqual(view.call_count, 2)
