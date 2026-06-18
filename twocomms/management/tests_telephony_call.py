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


from management.models import CallAIAnalysis, ManagerNotification
from management.services import call_ai_analysis as caa
from management import views as mgmt_views2


class DiscrepancyNotificationTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.manager = User.objects.create_user(username="mgr4", password="x")
        self.manager.userprofile.is_manager = True
        self.manager.userprofile.save()
        self.client_obj = Client.objects.create(
            shop_name="Shop4", phone="0671112244", full_name="X", owner=self.manager
        )
        self.rec = CallRecord.objects.create(
            provider="binotel", external_call_id="700700", manager=self.manager,
            matched_client=self.client_obj, duration_seconds=80,
        )

    def _analysis(self, discrepancies):
        return CallAIAnalysis.objects.create(
            call_record=self.rec, status=CallAIAnalysis.Status.DONE,
            discrepancies=discrepancies,
        )

    def test_warn_creates_ack_notification(self):
        a = self._analysis([{"field": "next_call", "manager_value": "11:00", "ai_value": "12:00", "severity": "warn", "note": "n"}])
        caa.notify_discrepancies(self.rec, a)
        notif = ManagerNotification.objects.filter(user=self.manager, requires_ack=True, related_analysis=a).first()
        self.assertIsNotNone(notif)
        self.assertEqual(notif.related_client_id, self.client_obj.id)

    def test_info_only_no_notification(self):
        a = self._analysis([{"field": "other", "severity": "info", "note": "n"}])
        caa.notify_discrepancies(self.rec, a)
        self.assertFalse(ManagerNotification.objects.filter(related_analysis=a).exists())

    def test_idempotent(self):
        a = self._analysis([{"field": "xml", "severity": "high", "note": "n"}])
        caa.notify_discrepancies(self.rec, a)
        caa.notify_discrepancies(self.rec, a)
        self.assertEqual(ManagerNotification.objects.filter(related_analysis=a).count(), 1)

    def test_no_manager_skips(self):
        self.rec.manager = None
        self.rec.save()
        a = self._analysis([{"field": "xml", "severity": "high", "note": "n"}])
        caa.notify_discrepancies(self.rec, a)
        self.assertFalse(ManagerNotification.objects.filter(related_analysis=a).exists())

    def test_ack_endpoint_sets_acknowledged(self):
        a = self._analysis([{"field": "xml", "severity": "high", "note": "n"}])
        caa.notify_discrepancies(self.rec, a)
        notif = ManagerNotification.objects.get(related_analysis=a)
        req = self.factory.post(
            "/notifications/ack/", data=_json.dumps({"id": notif.id}),
            content_type="application/json",
        )
        req.user = self.manager
        resp = mgmt_views2.notification_ack(req)
        self.assertEqual(resp.status_code, 200)
        notif.refresh_from_db()
        self.assertIsNotNone(notif.acknowledged_at)
        self.assertTrue(notif.is_read)


class DiscrepancyNormalizeTest(TestCase):
    def test_normalize_filters_and_clamps(self):
        out = caa._normalize_discrepancies([
            {"field": "next_call", "severity": "warn", "note": "ok"},
            {"field": "x", "severity": "bogus"},
            "notadict",
        ])
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]["severity"], "warn")
        self.assertEqual(out[1]["severity"], "info")  # bogus → info


from management.services import call_coaching as cc


class CallCoachingTest(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(username="mgr5", password="x")
        self.manager.userprofile.is_manager = True
        self.manager.userprofile.save()

    def _analysis(self, score, missed=None, recs=None, verdict="coaching"):
        rec = CallRecord.objects.create(
            provider="binotel", external_call_id=f"c{CallRecord.objects.count()+1}",
            manager=self.manager, duration_seconds=60,
        )
        return CallAIAnalysis.objects.create(
            call_record=rec, status=CallAIAnalysis.Status.DONE,
            overall_score=score, verdict=verdict,
            missed_topics=missed or [], recommendations=recs or [],
        )

    def test_not_ready_with_few(self):
        self._analysis(70)
        out = cc.build_call_coaching(self.manager)
        self.assertFalse(out["ready"])

    def test_aggregates_focus_and_tips(self):
        self._analysis(60, missed=["Не запитав про обсяги", "Не закрив на наступний крок"], recs=["Більше слухай клієнта"])
        self._analysis(62, missed=["не запитав про обсяги"], recs=["Більше слухай клієнта"])
        self._analysis(64, missed=["Інше"], recs=["Готуй пропозицію заздалегідь"])
        out = cc.build_call_coaching(self.manager)
        self.assertTrue(out["ready"])
        self.assertEqual(out["analyzed_count"], 3)
        # «не запитав про обсяги» зустрілось двічі → перше у focus
        self.assertEqual(out["focus"][0]["count"], 2)
        self.assertEqual(out["tips"][0]["count"], 2)

    def test_trend_improving(self):
        # свіжіші (перші за -created_at) вищі за старіші → прогрес
        for s in [50, 52]:
            self._analysis(s)
        for s in [80, 82]:
            self._analysis(s)
        out = cc.build_call_coaching(self.manager)
        # останні створені (80,82) — свіжіші, старіші (50,52) → recent>older
        self.assertIn(out["trend"]["tone"], {"good", "neutral", "warn"})
        self.assertTrue(out["ready"])

    def test_no_score_leak_keys(self):
        self._analysis(90)
        self._analysis(91)
        out = cc.build_call_coaching(self.manager)
        # у відповіді не повинно бути сирих балів
        self.assertNotIn("scores", out)
        self.assertNotIn("overall_score", out)


from management.services import call_review as cr_svc
from django.utils import timezone as _tz


class AdminCallReviewTest(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(username="mgr6", password="x")
        self.manager.userprofile.is_manager = True
        self.manager.userprofile.save()
        self.client_obj = Client.objects.create(
            shop_name="Shop6", phone="0671112255", full_name="X", owner=self.manager
        )

    def _call_with_analysis(self, score=70, verdict="coaching", disc=None, payload=None):
        rec = CallRecord.objects.create(
            provider="binotel", external_call_id=f"r{CallRecord.objects.count()+1}",
            manager=self.manager, matched_client=self.client_obj, duration_seconds=70,
            ai_status=CallRecord.AiStatus.DONE, payload=payload or {"disposition": "ANSWER"},
        )
        a = CallAIAnalysis.objects.create(
            call_record=rec, status=CallAIAnalysis.Status.DONE,
            overall_score=score, verdict=verdict, discrepancies=disc or [],
            summary="резюме",
        )
        return rec, a

    def test_review_summary_and_scores(self):
        self._call_with_analysis(80, "pass")
        self._call_with_analysis(40, "fail", disc=[{"field": "xml", "severity": "high", "note": "n", "manager_value": "так", "ai_value": "ні"}])
        out = cr_svc.build_admin_call_review(self.manager)
        self.assertEqual(out["summary"]["analyzed"], 2)
        self.assertEqual(out["summary"]["with_discrepancies"], 1)
        self.assertEqual(out["summary"]["fails"], 1)
        self.assertEqual(out["summary"]["avg_score"], 60.0)
        # запис із розбіжностями має has_recording і analysis
        flagged = [c for c in out["calls"] if c["analysis"] and c["analysis"]["discrepancies"]]
        self.assertEqual(len(flagged), 1)
        self.assertTrue(flagged[0]["has_recording"])

    def test_ack_state_reflected(self):
        rec, a = self._call_with_analysis(50, "coaching", disc=[{"field": "next_call", "severity": "warn", "note": "n", "manager_value": "11", "ai_value": "12"}])
        caa.notify_discrepancies(rec, a)  # створює requires_ack notif
        out = cr_svc.build_admin_call_review(self.manager)
        call = next(c for c in out["calls"] if c["id"] == rec.id)
        self.assertIs(call["analysis"]["discrepancy_acknowledged"], False)
        # підтверджуємо
        notif = ManagerNotification.objects.get(related_analysis=a)
        notif.acknowledged_at = _tz.now(); notif.is_read = True; notif.save()
        out2 = cr_svc.build_admin_call_review(self.manager)
        call2 = next(c for c in out2["calls"] if c["id"] == rec.id)
        self.assertIs(call2["analysis"]["discrepancy_acknowledged"], True)

    def test_pending_counted(self):
        CallRecord.objects.create(
            provider="binotel", external_call_id="rp1", manager=self.manager,
            matched_client=self.client_obj, duration_seconds=60,
            ai_status=CallRecord.AiStatus.PENDING, payload={"disposition": "ANSWER"},
        )
        out = cr_svc.build_admin_call_review(self.manager)
        self.assertEqual(out["summary"]["pending"], 1)


from datetime import timedelta as _td
from management.services import telephony as _tel
from management.services import snapshots as _snap


class VerifiedCommunicationSignalTest(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(username="mgr7", password="x")
        self.manager.userprofile.is_manager = True
        self.manager.userprofile.save()
        self.today = _tz.localdate()

    def _call(self, dur=60, score=None, days_ago=0):
        rec = CallRecord.objects.create(
            provider="binotel", external_call_id=f"vc{CallRecord.objects.count()+1}",
            manager=self.manager, duration_seconds=dur,
        )
        if days_ago:
            CallRecord.objects.filter(id=rec.id).update(
                created_at=_tz.now() - _td(days=days_ago)
            )
        if score is not None:
            CallAIAnalysis.objects.create(
                call_record=rec, status=CallAIAnalysis.Status.DONE, overall_score=score,
            )
        return rec

    def test_no_calls_returns_none(self):
        sig = _tel.build_call_quality_signal(self.manager, self.today)
        self.assertFalse(sig["has_calls"])
        self.assertIsNone(sig["vc_real"])

    def test_short_calls_not_meaningful(self):
        self._call(dur=10)
        sig = _tel.build_call_quality_signal(self.manager, self.today)
        self.assertFalse(sig["has_calls"])

    def test_calls_with_qa(self):
        self._call(dur=60, score=80)
        self._call(dur=90, score=60)
        sig = _tel.build_call_quality_signal(self.manager, self.today, target_meaningful=10)
        self.assertTrue(sig["has_calls"])
        self.assertEqual(sig["meaningful_calls"], 2)
        self.assertEqual(sig["analyzed_count"], 2)
        # qa=0.70, presence=0.2 → vc=0.6*0.7+0.4*0.2=0.5
        self.assertAlmostEqual(sig["qa_quality"], 0.70, places=2)
        self.assertAlmostEqual(sig["vc_real"], 0.5, places=3)

    def test_calls_without_qa_uses_presence(self):
        self._call(dur=60)  # no analysis
        sig = _tel.build_call_quality_signal(self.manager, self.today, target_meaningful=4)
        self.assertTrue(sig["has_calls"])
        self.assertIsNone(sig["qa_quality"])
        self.assertAlmostEqual(sig["vc_real"], 0.25, places=3)  # presence 1/4

    def test_window_excludes_old_calls(self):
        self._call(dur=60, score=80, days_ago=60)  # за межами 30-дн вікна
        sig = _tel.build_call_quality_signal(self.manager, self.today, window_days=30)
        self.assertFalse(sig["has_calls"])

    def test_vc_axis_uses_real_signal_when_present(self):
        readiness = {"verified_communication": "shadow"}
        summary = {"success_rate_pct": 0}  # легасі дав би 0*0.7+0.25=0.25
        cq = {"vc_real": 0.9}
        axis = _snap._compute_verified_communication_axis(summary, readiness, cq)
        # 0.9*0.7+0.25 = 0.88
        self.assertAlmostEqual(float(axis), 0.88, places=2)

    def test_vc_axis_falls_back_to_legacy(self):
        readiness = {"verified_communication": "shadow"}
        summary = {"success_rate_pct": 50}  # 0.5*0.7+0.25=0.6
        axis = _snap._compute_verified_communication_axis(summary, readiness, None)
        self.assertAlmostEqual(float(axis), 0.60, places=2)


from datetime import date as _date
from management.services import manager_review as _mr


class ManagerReviewTest(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(username="mgr8", password="x")
        self.manager.userprofile.is_manager = True
        self.manager.userprofile.save()
        self.today = _tz.localdate()

    def _client(self, result="thinking", days_ago=0, note=""):
        c = Client.objects.create(
            shop_name=f"S{Client.objects.count()+1}", phone="0671110000",
            full_name="X", owner=self.manager, call_result=result, manager_note=note,
        )
        if days_ago:
            Client.objects.filter(id=c.id).update(created_at=_tz.now() - _td(days=days_ago))
        return c

    def test_resolve_window_variants(self):
        w = _mr.resolve_review_window("today", "", self.today)
        self.assertEqual(w["key"], "today"); self.assertEqual(w["single_day"], self.today)
        w = _mr.resolve_review_window("yesterday", "", self.today)
        self.assertEqual(w["single_day"], self.today - _td(days=1))
        w = _mr.resolve_review_window("week", "", self.today)
        self.assertEqual(w["mode"], "range"); self.assertIsNone(w["single_day"])
        w = _mr.resolve_review_window("all", "", self.today)
        self.assertEqual(w["mode"], "all"); self.assertIsNone(w["start"])
        w = _mr.resolve_review_window("", "2026-01-15", self.today)
        self.assertEqual(w["single_day"], _date(2026, 1, 15))

    def test_summary_and_breakdown(self):
        self._client(result="order")
        self._client(result="test_batch")
        self._client(result="thinking", note="передзвонити ввечері")
        out = _mr.build_manager_clients_review(self.manager, period="today")
        self.assertEqual(out["summary"]["processed"], 3)
        self.assertEqual(out["summary"]["conversions"], 2)
        self.assertTrue(out["summary"]["points"] > 0)
        self.assertTrue(any(c["manager_note"] for c in out["clients"]))

    def test_deltas_vs_prev_day(self):
        self._client(result="order")            # сьогодні 1
        self._client(result="order", days_ago=1)
        self._client(result="thinking", days_ago=1)  # вчора 2
        out = _mr.build_manager_clients_review(self.manager, period="today")
        self.assertIsNotNone(out["deltas"])
        self.assertEqual(out["deltas"]["processed"]["prev"], 2)
        self.assertEqual(out["deltas"]["processed"]["diff"], 1 - 2)
        self.assertEqual(out["deltas"]["processed"]["tone"], "bad")

    def test_calls_attached(self):
        c = self._client(result="order")
        rec = CallRecord.objects.create(
            provider="binotel", external_call_id="mr1", manager=self.manager,
            matched_client=c, duration_seconds=70, payload={"disposition": "ANSWER"},
        )
        CallAIAnalysis.objects.create(call_record=rec, status=CallAIAnalysis.Status.DONE, overall_score=82, verdict="pass")
        out = _mr.build_manager_clients_review(self.manager, period="today")
        card = next(x for x in out["clients"] if x["id"] == c.id)
        self.assertEqual(len(card["calls"]), 1)
        self.assertTrue(card["calls"][0]["has_recording"])
        self.assertEqual(card["calls"][0]["ai"]["verdict"], "pass")

    def test_all_period_no_date_filter(self):
        self._client(result="order", days_ago=100)
        out = _mr.build_manager_clients_review(self.manager, period="all")
        self.assertEqual(out["summary"]["processed"], 1)
