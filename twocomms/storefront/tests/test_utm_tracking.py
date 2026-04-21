from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from orders.models import Order
from storefront.models import SiteSession, UTMSession
from storefront.utm_tracking import record_order_action


class RecordOrderActionTests(TestCase):
    def _build_order(self, *, session_key: str, user=None, utm_session=None):
        return Order.objects.create(
            user=user,
            session_key=session_key,
            utm_session=utm_session,
            full_name='Тестовий клієнт',
            phone='+380991112233',
            city='Київ',
            np_office='Відділення №4',
            pay_type='online_full',
            total_sum=Decimal('1499.00'),
            status='new',
        )

    def test_record_order_action_links_purchase_to_existing_sessions(self):
        user = get_user_model().objects.create_user(username='utm-user', password='pass12345')
        site_session = SiteSession.objects.create(session_key='sess-auth-1', user=user)
        utm_session = UTMSession.objects.create(
            session=site_session,
            session_key='sess-auth-1',
            utm_source='instagram',
        )
        order = self._build_order(session_key='sess-auth-1', user=user)

        action = record_order_action(
            'purchase',
            order,
            cart_value=float(order.total_sum),
            metadata={'source': 'monobank'},
        )

        self.assertIsNotNone(action)
        self.assertEqual(action.utm_session_id, utm_session.id)
        self.assertEqual(action.site_session_id, site_session.id)
        self.assertEqual(action.user_id, user.id)
        self.assertEqual(action.order_id, order.id)
        self.assertEqual(action.order_number, order.order_number)
        self.assertEqual(action.metadata['source'], 'monobank')

        utm_session.refresh_from_db()
        self.assertTrue(utm_session.is_converted)
        self.assertEqual(utm_session.conversion_type, 'purchase')

    def test_record_order_action_supports_guest_orders_via_order_utm_session(self):
        site_session = SiteSession.objects.create(session_key='sess-guest-1')
        utm_session = UTMSession.objects.create(
            session=site_session,
            session_key='sess-guest-1',
            utm_source='facebook',
        )
        order = self._build_order(
            session_key='sess-guest-1',
            utm_session=utm_session,
        )

        action = record_order_action(
            'lead',
            order,
            cart_value=float(order.total_sum),
            metadata={'source': 'monobank'},
        )

        self.assertIsNotNone(action)
        self.assertEqual(action.utm_session_id, utm_session.id)
        self.assertEqual(action.site_session_id, site_session.id)
        self.assertIsNone(action.user)
        self.assertEqual(action.action_type, 'lead')

        utm_session.refresh_from_db()
        self.assertTrue(utm_session.is_converted)
        self.assertEqual(utm_session.conversion_type, 'lead')
