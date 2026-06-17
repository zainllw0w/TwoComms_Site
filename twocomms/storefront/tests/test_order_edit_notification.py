"""Тести Telegram-сповіщення про редагування замовлення."""
from __future__ import annotations

from decimal import Decimal
from unittest import mock

from django.test import TestCase

from orders.telegram_notifications import TelegramNotifier


def _diff_with_changes():
    return {
        'items': {
            'added': [{'label': 'Футболка · Чорний · XXL', 'qty': 1, 'unit_price': Decimal('880.00')}],
            'removed': [{'label': 'Футболка · Ментол · XXL', 'qty': 1, 'unit_price': Decimal('880.00')}],
            'changed': [],
        },
        'total': {'old': Decimal('880.00'), 'new': Decimal('760.00'), 'delta': Decimal('-120.00')},
        'delivery': None,
        'payment': None,
        'customer': None,
        'has_changes': True,
    }


class _Order:
    order_number = 'TWC14062026N01'
    full_name = 'Лагош Олег'
    phone = '+380500234363'


class OrderEditNotificationTests(TestCase):
    def setUp(self):
        self.notifier = TelegramNotifier(bot_token='token', chat_id='100', admin_id='100')

    def test_message_contains_order_number_and_title(self):
        msg = self.notifier.format_order_edit_message(_Order(), _diff_with_changes())
        self.assertIn('TWC14062026N01', msg)
        self.assertIn('відредаговано', msg.lower())

    def test_message_lists_removed_and_added(self):
        msg = self.notifier.format_order_edit_message(_Order(), _diff_with_changes())
        self.assertIn('Ментол', msg)
        self.assertIn('Чорний', msg)

    def test_message_shows_total_delta(self):
        msg = self.notifier.format_order_edit_message(_Order(), _diff_with_changes())
        self.assertIn('760', msg)
        self.assertIn('-120', msg.replace('−', '-'))

    def test_message_includes_editor_name(self):
        msg = self.notifier.format_order_edit_message(_Order(), _diff_with_changes(), changed_by='admin')
        self.assertIn('admin', msg)

    def test_send_calls_send_message_when_changes(self):
        with mock.patch.object(self.notifier, 'send_message', return_value=True) as send:
            result = self.notifier.send_order_edit_notification(_Order(), _diff_with_changes())
        self.assertTrue(result)
        send.assert_called_once()

    def test_send_skips_when_no_changes(self):
        empty = {
            'items': {'added': [], 'removed': [], 'changed': []},
            'total': None, 'delivery': None, 'payment': None, 'customer': None,
            'has_changes': False,
        }
        with mock.patch.object(self.notifier, 'send_message', return_value=True) as send:
            result = self.notifier.send_order_edit_notification(_Order(), empty)
        self.assertFalse(result)
        send.assert_not_called()
