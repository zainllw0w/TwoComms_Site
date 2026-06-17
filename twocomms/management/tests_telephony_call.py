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


import json as _json

from django.test import RequestFactory

from management import views as mgmt_views


class AdminTelephonySaveEndpointTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.admin = User.objects.create_user(username="adm", password="x", is_staff=True)
        self.manager = User.objects.create_user(username="mgr2", password="x")
        self.manager.userprofile.is_manager = True
        self.manager.userprofile.save()

    def _call(self, actor, payload):
        req = self.factory.post(
            f"/admin-panel/user/{self.manager.id}/telephony/",
            data=_json.dumps(payload), content_type="application/json",
        )
        req.user = actor
        return mgmt_views.admin_manager_telephony_save_api(req, self.manager.id)

    def test_requires_staff(self):
        resp = self._call(self.manager, {"binotel_internal_number": "901"})
        self.assertEqual(resp.status_code, 403)

    def test_staff_can_set_line(self):
        resp = self._call(self.admin, {"binotel_internal_number": "901"})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(_json.loads(resp.content).get("ok"))
        self.manager.userprofile.refresh_from_db()
        self.assertEqual(self.manager.userprofile.binotel_internal_number, "901")

    def test_invalid_line_rejected(self):
        resp = self._call(self.admin, {"binotel_internal_number": "abc!!"})
        self.assertEqual(resp.status_code, 400)

    def test_empty_clears_line(self):
        self.manager.userprofile.binotel_internal_number = "901"
        self.manager.userprofile.save()
        resp = self._call(self.admin, {"binotel_internal_number": ""})
        self.assertEqual(resp.status_code, 200)
        self.manager.userprofile.refresh_from_db()
        self.assertEqual(self.manager.userprofile.binotel_internal_number, "")

    def test_dossier_includes_binotel_line(self):
        self.manager.userprofile.binotel_internal_number = "777"
        self.manager.userprofile.save()
        from management.services.dossier import build_manager_dossier
        dossier = build_manager_dossier(self.manager)
        self.assertEqual(dossier["manager"]["binotel_internal_number"], "777")


from management.models import CallRecord
from management import binotel_webhook


class WebhookLinkEnqueueTest(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(username="mgr3", password="x")
        self.client_obj = Client.objects.create(
            shop_name="S", phone="0671112233", full_name="X", owner=self.manager
        )

    def _record(self, gcid="555000111"):
        return CallRecord.objects.create(provider="binotel", external_call_id=gcid)

    def test_meaningful_answered_call_enqueued_and_linked(self):
        rec = self._record()
        session = CallSession.objects.create(
            manager=self.manager, client=self.client_obj, phone="0671112233",
            general_call_id=rec.external_call_id, status=CallSession.Status.TALKING,
        )
        binotel_webhook._link_call_session_and_enqueue(
            rec, {"disposition": "ANSWER", "bill_seconds": 65}
        )
        rec.refresh_from_db()
        session.refresh_from_db()
        self.assertEqual(rec.ai_status, CallRecord.AiStatus.PENDING)
        self.assertEqual(rec.manager_id, self.manager.id)
        self.assertEqual(rec.matched_client_id, self.client_obj.id)
        self.assertEqual(session.call_record_id, rec.id)
        self.assertEqual(session.status, CallSession.Status.ENDED)

    def test_short_call_not_enqueued(self):
        rec = self._record("555000222")
        binotel_webhook._link_call_session_and_enqueue(
            rec, {"disposition": "ANSWER", "bill_seconds": 8}
        )
        rec.refresh_from_db()
        self.assertEqual(rec.ai_status, CallRecord.AiStatus.NONE)

    def test_noanswer_not_enqueued(self):
        rec = self._record("555000333")
        binotel_webhook._link_call_session_and_enqueue(
            rec, {"disposition": "NOANSWER", "bill_seconds": 0}
        )
        rec.refresh_from_db()
        self.assertEqual(rec.ai_status, CallRecord.AiStatus.NONE)


from management import call_views


class ClientCallsAccessTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.owner = User.objects.create_user(username="owner", password="x")
        self.owner.userprofile.is_manager = True
        self.owner.userprofile.save()
        self.other = User.objects.create_user(username="other2", password="x")
        self.other.userprofile.is_manager = True
        self.other.userprofile.save()
        self.admin = User.objects.create_user(username="adm3", password="x", is_staff=True)
        self.client_obj = Client.objects.create(
            shop_name="S", phone="0671112233", full_name="X", owner=self.owner
        )
        self.rec = CallRecord.objects.create(
            provider="binotel", external_call_id="900900", matched_client=self.client_obj,
            manager=self.owner, duration_seconds=60, payload={"disposition": "ANSWER"},
        )

    def _calls(self, actor):
        req = self.factory.get(f"/api/call/client-calls/?client_id={self.client_obj.id}")
        req.user = actor
        return call_views.client_calls(req)

    def test_owner_sees_calls_without_score(self):
        resp = self._calls(self.owner)
        self.assertEqual(resp.status_code, 200)
        data = _json.loads(resp.content)
        self.assertTrue(data["success"])
        self.assertFalse(data["is_admin"])
        self.assertEqual(len(data["calls"]), 1)
        self.assertNotIn("ai", data["calls"][0])  # менеджеру бали не віддаємо
        self.assertTrue(data["calls"][0]["has_recording"])

    def test_other_manager_forbidden(self):
        resp = self._calls(self.other)
        self.assertEqual(resp.status_code, 403)

    def test_access_helper(self):
        self.assertTrue(call_views._can_access_call_record(self.owner, self.rec))
        self.assertTrue(call_views._can_access_call_record(self.admin, self.rec))
        self.assertFalse(call_views._can_access_call_record(self.other, self.rec))
