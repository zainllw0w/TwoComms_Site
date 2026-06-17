"""Тести для click-to-call фундаменту (Фаза 0–1): ClientPhone, CallSession,
сервіс telephony_call. Без реальних викликів Binotel — лише локальна логіка."""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase

from management.models import CallSession, Client, ClientPhone
from management.services import telephony_call as tc

User = get_user_model()


class ClientPhoneModelTest(TestCase):
    def test_save_normalizes_number(self):
        client = Client.objects.create(shop_name="Shop", phone="+380671112233", full_name="X")
        phone = ClientPhone.objects.create(
            client=client, number="+38 (097) 765-43-21", category=ClientPhone.Category.PERSONAL
        )
        self.assertEqual(phone.number_normalized, "+380977654321")
        self.assertEqual(phone.number_last7, "7654321")

    def test_primary_ordering(self):
        client = Client.objects.create(shop_name="Shop", phone="0671112233", full_name="X")
        ClientPhone.objects.create(client=client, number="0671112233", is_primary=False)
        ClientPhone.objects.create(client=client, number="0501112233", is_primary=True)
        first = client.phones.all().first()
        self.assertTrue(first.is_primary)


class TelephonyCallServiceTest(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(username="mgr", password="x")
        # профіль зі статусом менеджера, але без лінії Binotel
        self.profile = self.manager.userprofile
        self.profile.is_manager = True
        self.profile.save()

    def test_no_line_raises(self):
        with self.assertRaises(tc.CallStartError):
            tc.start_outbound_call(self.manager, "0671234567")

    def test_get_manager_internal_number(self):
        self.assertEqual(tc.get_manager_internal_number(self.manager), "")
        self.profile.binotel_internal_number = "901"
        self.profile.save()
        # перечитати з БД
        self.manager.refresh_from_db()
        self.assertEqual(tc.get_manager_internal_number(self.manager), "901")

    def test_invalid_phone_raises(self):
        self.profile.binotel_internal_number = "901"
        self.profile.save()
        self.manager.refresh_from_db()
        with self.assertRaises(tc.CallStartError):
            tc.start_outbound_call(self.manager, "abc")

    def test_attach_session_to_client(self):
        client = Client.objects.create(shop_name="S", phone="0671112233", full_name="X", owner=self.manager)
        session = CallSession.objects.create(
            manager=self.manager, phone="0671112233", status=CallSession.Status.ENDED
        )
        attached = tc.attach_session_to_client(
            manager=self.manager, session_id=session.id, client=client
        )
        self.assertIsNotNone(attached)
        session.refresh_from_db()
        self.assertEqual(session.client_id, client.id)

    def test_attach_session_wrong_manager_ignored(self):
        other = User.objects.create_user(username="other", password="x")
        client = Client.objects.create(shop_name="S", phone="0671112233", full_name="X")
        session = CallSession.objects.create(manager=other, phone="0671112233")
        result = tc.attach_session_to_client(
            manager=self.manager, session_id=session.id, client=client
        )
        self.assertIsNone(result)

    def test_serialize_session_shape(self):
        session = CallSession.objects.create(
            manager=self.manager, phone="0671112233", status=CallSession.Status.DIALING
        )
        data = tc.serialize_session(session)
        self.assertEqual(data["session_id"], session.id)
        self.assertTrue(data["is_active"])
        self.assertIn("status_display", data)
