from datetime import datetime, timedelta
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from management.models import (
    Client,
    ClientFollowUp,
    ClientInteractionAttempt,
    CommercialOfferEmailLog,
    DuplicateReview,
    Shop,
    normalize_phone,
)


class UaPhoneNormalizationTests(TestCase):
    def test_normalize_phone_handles_common_ua_variants(self):
        self.assertEqual(normalize_phone("+38 (067) 111-22-33"), "+380671112233")
        self.assertEqual(normalize_phone("380671112233"), "+380671112233")
        self.assertEqual(normalize_phone("067-111-22-33"), "+380671112233")
        self.assertEqual(normalize_phone("67 111 22 33"), "+380671112233")
        self.assertEqual(normalize_phone("80671112233"), "+380671112233")


@override_settings(ROOT_URLCONF="twocomms.urls_management")
class ClientEntryPreviewApiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="preview_mgr", password="x", is_staff=True)
        self.client.force_login(self.user)

    def test_preview_endpoint_detects_exact_duplicate_for_ua_variant_number(self):
        existing = Client.objects.create(
            shop_name="Alpha Store",
            phone="+380671112233",
            full_name="Owner",
            owner=self.user,
            call_result=Client.CallResult.THINKING,
        )

        response = self.client.get(
            "/clients/dedupe-preview/",
            {
                "shop_name": "Alpha Store",
                "phone": "80671112233",
                "website_url": "",
            },
            secure=True,
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["zone"], "auto_block")
        self.assertTrue(payload["has_warning"])
        self.assertEqual(payload["candidates"][0]["id"], existing.id)
        self.assertIn("owner_display", payload["candidates"][0])
        self.assertIn("last_contact_display", payload["candidates"][0])
        self.assertIn("last_result_display", payload["candidates"][0])

    def test_preview_endpoint_returns_soft_warning_for_name_and_site_match(self):
        Client.objects.create(
            shop_name="Fashion Hub",
            phone="+380671112233",
            website_url="https://fashion.example.com",
            full_name="Owner",
            owner=self.user,
            call_result=Client.CallResult.NOT_INTERESTED,
        )

        response = self.client.get(
            "/clients/dedupe-preview/",
            {
                "shop_name": "Fashion Hub",
                "phone": "+380991112233",
                "website_url": "https://fashion.example.com",
            },
            secure=True,
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["zone"], "suggestion")
        self.assertTrue(payload["has_warning"])
        self.assertEqual(payload["candidates"][0]["last_result_display"], "Не цікавить")


@override_settings(ROOT_URLCONF="twocomms.urls_management")
class HomeClientEntryValidationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="home_flow_mgr", password="x", is_staff=True)
        self.client.force_login(self.user)
        self.full_shop = Shop.objects.create(
            name="Full Shop",
            created_by=self.user,
            managed_by=self.user,
            shop_type=Shop.ShopType.FULL,
        )
        self.test_shop = Shop.objects.create(
            name="Test Shop",
            created_by=self.user,
            managed_by=self.user,
            shop_type=Shop.ShopType.TEST,
        )
        self.sent_cp = CommercialOfferEmailLog.objects.create(
            owner=self.user,
            recipient_email="owner@example.com",
            recipient_name="Owner",
            subject="КП",
            status=CommercialOfferEmailLog.Status.SENT,
        )

    def _base_payload(self):
        return {
            "shop_name": "Target Shop",
            "phone": "+380671112244",
            "website_url": "https://target.example.com",
            "full_name": "Owner",
            "role": Client.Role.MANAGER,
            "source": "instagram",
            "next_call_type": "no_follow",
        }

    def _scheduled_local_payload(self, *, hours=3):
        scheduled_at = timezone.localtime(timezone.now()).replace(second=0, microsecond=0) + timedelta(hours=hours)
        return {
            "next_call_type": "scheduled",
            "next_call_date": scheduled_at.strftime("%Y-%m-%d"),
            "next_call_time": scheduled_at.strftime("%H:%M"),
        }

    def test_sent_email_requires_cp_log_id(self):
        response = self.client.post(
            "/",
            {
                **self._base_payload(),
                "call_result": Client.CallResult.SENT_EMAIL,
            },
            secure=True,
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("КП", response.json()["error"])

    def test_sent_messenger_requires_type_and_target(self):
        response = self.client.post(
            "/",
            {
                **self._base_payload(),
                "call_result": Client.CallResult.SENT_MESSENGER,
            },
            secure=True,
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("месендж", response.json()["error"].lower())

    def test_xml_connected_requires_platform_and_resource_url(self):
        response = self.client.post(
            "/",
            {
                **self._base_payload(),
                "call_result": Client.CallResult.XML_CONNECTED,
            },
            secure=True,
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("xml", response.json()["error"].lower())

    def test_order_requires_owned_full_shop_link(self):
        response = self.client.post(
            "/",
            {
                **self._base_payload(),
                "call_result": Client.CallResult.ORDER,
            },
            secure=True,
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("магазин", response.json()["error"].lower())

    def test_test_batch_requires_owned_test_shop_link(self):
        response = self.client.post(
            "/",
            {
                **self._base_payload(),
                "call_result": Client.CallResult.TEST_BATCH,
            },
            secure=True,
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("тест", response.json()["error"].lower())

    def test_scheduled_callback_rejects_past_datetime(self):
        now_local = timezone.localtime(timezone.now()).replace(second=0, microsecond=0)
        past_local = now_local - timedelta(days=1)

        response = self.client.post(
            "/",
            {
                **self._base_payload(),
                "call_result": Client.CallResult.THINKING,
                "next_call_type": "scheduled",
                "next_call_date": past_local.strftime("%Y-%m-%d"),
                "next_call_time": past_local.strftime("%H:%M"),
            },
            secure=True,
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("майбут", response.json()["error"].lower())

    def test_exact_duplicate_requires_explicit_override_reason(self):
        Client.objects.create(
            shop_name="Existing Shop",
            phone="+380671112244",
            full_name="Owner",
            owner=self.user,
            call_result=Client.CallResult.THINKING,
        )

        blocked = self.client.post(
            "/",
            {
                **self._base_payload(),
                "call_result": Client.CallResult.THINKING,
            },
            secure=True,
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(blocked.status_code, 409)

        allowed = self.client.post(
            "/",
            {
                **self._base_payload(),
                "call_result": Client.CallResult.THINKING,
                "duplicate_override_reason": "Повторно додаю окремий підрозділ на спільному контакті після ручної перевірки.",
            },
            secure=True,
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(Client.objects.filter(phone="+380671112244").count(), 2)
        review = DuplicateReview.objects.order_by("-created_at").first()
        self.assertIsNotNone(review)
        self.assertEqual(review.status, DuplicateReview.Status.RESOLVED)
        self.assertIn("override_reason", review.incoming_payload)

    def test_successful_sent_email_creates_cp_link_and_interaction_attempt(self):
        response = self.client.post(
            "/",
            {
                **self._base_payload(),
                "call_result": Client.CallResult.SENT_EMAIL,
                "cp_log_id": str(self.sent_cp.id),
            },
            secure=True,
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        created = Client.objects.get(shop_name="Target Shop", owner=self.user)

        client_cp_link_model = apps.get_model("management", "ClientCPLink")
        interaction_model = apps.get_model("management", "ClientInteractionAttempt")

        self.assertTrue(
            client_cp_link_model.objects.filter(client=created, cp_log=self.sent_cp, linked_by=self.user).exists()
        )
        self.assertTrue(
            interaction_model.objects.filter(
                client=created,
                manager=self.user,
                result=Client.CallResult.SENT_EMAIL,
                cp_log=self.sent_cp,
            ).exists()
        )

    def test_manager_note_is_persisted_on_client_entry(self):
        response = self.client.post(
            "/",
            {
                **self._base_payload(),
                "call_result": Client.CallResult.THINKING,
                "manager_note": "Краще телефонувати після 20:00 та дублювати в Telegram.",
            },
            secure=True,
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        created = Client.objects.get(shop_name="Target Shop", owner=self.user)
        self.assertEqual(
            created.manager_note,
            "Краще телефонувати після 20:00 та дублювати в Telegram.",
        )

    def test_callback_continue_creates_new_today_phase_client_and_skips_duplicate_review(self):
        source = Client.objects.create(
            shop_name="Phase Source Shop",
            phone="+380671112277",
            website_url="https://phase-source.example.com",
            full_name="Phase Owner",
            role=Client.Role.OWNER,
            source="Instagram",
            owner=self.user,
            call_result=Client.CallResult.THINKING,
            manager_note="Базова нотатка по клієнту.",
            next_call_at=timezone.now() + timedelta(hours=2),
        )
        Client.objects.filter(id=source.id).update(created_at=timezone.now() - timedelta(days=1))

        response = self.client.post(
            "/",
            {
                "client_id": str(source.id),
                "phase_action": "continue",
                "shop_name": source.shop_name,
                "phone": source.phone,
                "website_url": source.website_url,
                "full_name": source.full_name,
                "role": source.role,
                "source": "instagram",
                "call_result": Client.CallResult.NO_ANSWER,
                "call_result_reason_code": "voicemail",
                "call_result_reason_note": "Знову не взяв слухавку.",
                "call_result_contact_attempts": "2",
                "call_result_contact_channel": "phone",
                "phase_comment": "Переходимо до наступної фази обробки.",
                "manager_note": "Базова нотатка по клієнту.",
                **self._scheduled_local_payload(hours=4),
            },
            secure=True,
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Client.objects.filter(phone=source.phone).count(), 2)
        latest = Client.objects.exclude(id=source.id).get(phone=source.phone)
        source.refresh_from_db()

        self.assertEqual(latest.previous_phase_id, source.id)
        self.assertEqual(latest.phase_root_id, source.id)
        self.assertEqual(latest.phase_number, 2)
        self.assertEqual(latest.call_result, Client.CallResult.NO_ANSWER)
        self.assertEqual(latest.owner, self.user)
        self.assertIsNone(source.next_call_at)
        self.assertFalse(DuplicateReview.objects.exists())
        self.assertTrue(
            ClientInteractionAttempt.objects.filter(
                client=latest,
                manager=self.user,
                result=Client.CallResult.NO_ANSWER,
            ).exists()
        )
        self.assertEqual(response.json()["latest"]["id"], latest.id)
        self.assertEqual(response.json()["processed_today"], 1)

    def test_callback_continue_reuses_existing_today_phase_without_second_card(self):
        source = Client.objects.create(
            shop_name="Phase Reuse Shop",
            phone="+380671112288",
            website_url="https://phase-reuse.example.com",
            full_name="Reuse Owner",
            role=Client.Role.OWNER,
            source="Instagram",
            owner=self.user,
            call_result=Client.CallResult.THINKING,
            next_call_at=timezone.now() + timedelta(hours=2),
        )
        Client.objects.filter(id=source.id).update(created_at=timezone.now() - timedelta(days=1))
        today_phase = Client.objects.create(
            shop_name=source.shop_name,
            phone=source.phone,
            website_url=source.website_url,
            full_name=source.full_name,
            role=source.role,
            source=source.source,
            owner=self.user,
            call_result=Client.CallResult.NO_ANSWER,
            previous_phase=source,
            phase_root=source,
            phase_number=2,
            next_call_at=timezone.now() + timedelta(hours=3),
        )

        response = self.client.post(
            "/",
            {
                "client_id": str(source.id),
                "phase_action": "continue",
                "shop_name": source.shop_name,
                "phone": source.phone,
                "website_url": source.website_url,
                "full_name": source.full_name,
                "role": source.role,
                "source": "instagram",
                "call_result": Client.CallResult.NO_ANSWER,
                "call_result_reason_code": "voicemail",
                "call_result_contact_attempts": "2",
                "call_result_contact_channel": "phone",
                **self._scheduled_local_payload(hours=5),
            },
            secure=True,
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Client.objects.filter(phone=source.phone).count(), 2)
        self.assertEqual(response.json()["latest"]["id"], today_phase.id)

    def test_callback_continue_from_today_projection_returns_projection_remove_ids(self):
        due_at = timezone.localtime(timezone.now()).replace(second=0, microsecond=0) + timedelta(hours=2)
        source = Client.objects.create(
            shop_name="Projection Source Shop",
            phone="+380671112287",
            website_url="https://projection-source.example.com",
            full_name="Projection Owner",
            role=Client.Role.OWNER,
            source="Instagram",
            owner=self.user,
            call_result=Client.CallResult.THINKING,
            manager_note="Базова нотатка по проєкції.",
            next_call_at=due_at,
        )
        Client.objects.filter(id=source.id).update(created_at=timezone.now() - timedelta(days=1))
        followup = ClientFollowUp.objects.create(
            client=source,
            owner=self.user,
            due_at=due_at,
            due_date=due_at.date(),
            grace_until=due_at + timedelta(hours=2),
        )

        response = self.client.post(
            "/",
            {
                "client_id": str(source.id),
                "phase_action": "continue",
                "shop_name": source.shop_name,
                "phone": source.phone,
                "website_url": source.website_url,
                "full_name": source.full_name,
                "role": source.role,
                "source": "instagram",
                "call_result": Client.CallResult.NO_ANSWER,
                "call_result_reason_code": "voicemail",
                "call_result_reason_note": "Переводимо reminder у реальну сьогоднішню фазу.",
                "call_result_contact_attempts": "2",
                "call_result_contact_channel": "phone",
                "manager_note": source.manager_note,
                "phase_comment": "Сьогодні дійшли до фактичної обробки.",
                **self._scheduled_local_payload(hours=5),
            },
            secure=True,
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(Client.objects.filter(phone=source.phone).count(), 2)
        latest = Client.objects.exclude(id=source.id).get(phone=source.phone)
        self.assertEqual(payload["latest"]["id"], latest.id)
        self.assertEqual(payload["processed_today"], 1)
        self.assertIn(str(followup.id), payload["projection_remove_ids"])
        self.assertTrue(any(item["id"] == latest.id for item in payload["family_updates"]))

    def test_regular_edit_syncs_shared_fields_across_phase_family_and_skips_family_dedupe(self):
        phase1 = Client.objects.create(
            shop_name="Phase Sync Shop",
            phone="+380671112299",
            website_url="https://phase-sync.example.com",
            full_name="Sync Owner",
            role=Client.Role.OWNER,
            source="Instagram",
            owner=self.user,
            call_result=Client.CallResult.THINKING,
            manager_note="Стара нотатка.",
        )
        Client.objects.filter(id=phase1.id).update(created_at=timezone.now() - timedelta(days=2))
        phase2 = Client.objects.create(
            shop_name=phase1.shop_name,
            phone=phase1.phone,
            website_url=phase1.website_url,
            full_name=phase1.full_name,
            role=phase1.role,
            source=phase1.source,
            owner=self.user,
            call_result=Client.CallResult.NO_ANSWER,
            previous_phase=phase1,
            phase_root=phase1,
            phase_number=2,
            next_call_at=timezone.now() + timedelta(hours=2),
            manager_note="Стара нотатка.",
        )

        response = self.client.post(
            "/",
            {
                "client_id": str(phase2.id),
                "phase_action": "edit",
                "shop_name": "Phase Sync Shop Updated",
                "phone": phase2.phone,
                "website_url": "https://phase-sync-updated.example.com",
                "full_name": "Sync Owner Updated",
                "role": Client.Role.SUPERVISOR,
                "source": "google_maps",
                "call_result": Client.CallResult.THINKING,
                "manager_note": "Нова загальна нотатка по сім'ї фаз.",
                **self._scheduled_local_payload(hours=6),
            },
            secure=True,
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        phase1.refresh_from_db()
        phase2.refresh_from_db()

        self.assertEqual(phase1.shop_name, "Phase Sync Shop Updated")
        self.assertEqual(phase2.shop_name, "Phase Sync Shop Updated")
        self.assertEqual(phase1.website_url, "https://phase-sync-updated.example.com")
        self.assertEqual(phase2.full_name, "Sync Owner Updated")
        self.assertEqual(phase1.role, Client.Role.SUPERVISOR)
        self.assertEqual(phase2.manager_note, "Нова загальна нотатка по сім'ї фаз.")
        self.assertEqual(phase1.call_result, Client.CallResult.THINKING)
        self.assertEqual(phase2.call_result, Client.CallResult.THINKING)
        self.assertFalse(DuplicateReview.objects.exists())

    def test_successful_order_and_test_batch_link_owned_shops(self):
        interaction_model = apps.get_model("management", "ClientInteractionAttempt")

        order_response = self.client.post(
            "/",
            {
                **self._base_payload(),
                "shop_name": "Order Shop",
                "phone": "+380671112255",
                "call_result": Client.CallResult.ORDER,
                "linked_shop_id": str(self.full_shop.id),
            },
            secure=True,
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(order_response.status_code, 200)
        order_client = Client.objects.get(shop_name="Order Shop", owner=self.user)
        self.assertTrue(
            interaction_model.objects.filter(client=order_client, linked_shop=self.full_shop, result=Client.CallResult.ORDER).exists()
        )

        test_response = self.client.post(
            "/",
            {
                **self._base_payload(),
                "shop_name": "Batch Shop",
                "phone": "+380671112266",
                "call_result": Client.CallResult.TEST_BATCH,
                "linked_shop_id": str(self.test_shop.id),
            },
            secure=True,
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(test_response.status_code, 200)
        test_client = Client.objects.get(shop_name="Batch Shop", owner=self.user)
        self.assertTrue(
            interaction_model.objects.filter(client=test_client, linked_shop=self.test_shop, result=Client.CallResult.TEST_BATCH).exists()
        )


@override_settings(ROOT_URLCONF="twocomms.urls_management")
class HomePageModalMarkupTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="markup_mgr", password="x", is_staff=True)
        self.client.force_login(self.user)

    def test_home_page_renders_realtime_dedupe_modal_contract(self):
        response = self.client.get("/", secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="client_duplicate_notice" hidden')
        self.assertContains(response, 'id="client-duplicate-summary-modal"')
        self.assertContains(response, "Якісно заповнені дані допомагають")
        self.assertContains(response, "Оберіть, коли краще нагадати про наступний контакт")
        self.assertContains(response, "duplicate_preview_url")

    def test_home_page_exposes_compact_client_payload_hints_for_hybrid_rows(self):
        client = Client.objects.create(
            shop_name="Compact Shop",
            phone="+380671110099",
            website_url="https://shop.example.com/catalog/super-long-path",
            full_name="Compact Owner",
            owner=self.user,
            call_result=Client.CallResult.ORDER,
            manager_note="Краще писати після 19:00.",
        )
        client.next_call_at = None
        client.save(update_fields=["next_call_at"])

        response = self.client.get("/", secure=True)

        self.assertEqual(response.status_code, 200)
        grouped = response.context["grouped_clients"]
        flat = {
            item["shop"]: item
            for _, items in grouped
            for item in items
        }
        payload = flat["Compact Shop"]
        self.assertEqual(payload["callback_visual_state"], "normal")
        self.assertTrue(payload["has_manager_note"])
        self.assertIn("19:00", payload["manager_note_preview"])
        self.assertEqual(payload["hostname_display"], "shop.example.com")

    def test_home_page_renders_callback_phase_contract_with_phase_comment(self):
        phase1 = Client.objects.create(
            shop_name="Phase Shop",
            phone="+380671110188",
            full_name="Phase Owner",
            owner=self.user,
            call_result=Client.CallResult.THINKING,
            call_result_details="Фаза 1: сказав передзвонити після 18:00.",
            manager_note="Загальна нотатка по клієнту.",
        )
        Client.objects.filter(id=phase1.id).update(created_at=timezone.now() - timedelta(days=1))
        ClientInteractionAttempt.objects.create(
            client=phase1,
            manager=self.user,
            result=Client.CallResult.THINKING,
            reason_note="Попросив передзвонити після 18:00.",
            details="Фаза 1: сказав передзвонити після 18:00.",
            next_call_at=timezone.now() + timedelta(hours=1),
        )
        client = Client.objects.create(
            shop_name="Phase Shop",
            phone="+380671110188",
            full_name="Phase Owner",
            owner=self.user,
            call_result=Client.CallResult.THINKING,
            call_result_details="Фаза 2: уточнює рішення з партнером.",
            manager_note="Загальна нотатка по клієнту.",
            next_call_at=timezone.now() + timedelta(hours=2),
            previous_phase=phase1,
            phase_root=phase1,
            phase_number=2,
        )
        ClientInteractionAttempt.objects.create(
            client=client,
            manager=self.user,
            result=Client.CallResult.THINKING,
            reason_note="Скаже після погодження з партнером.",
            details="Фаза 2: уточнює рішення з партнером.",
            next_call_at=timezone.now() + timedelta(hours=2),
        )

        response = self.client.get("/", secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="client_callback_current_phase"')
        self.assertContains(response, 'id="phase_comment"')
        self.assertContains(response, 'id="client_callback_previous_summary"')
        grouped = response.context["grouped_clients"]
        items = [item for _, rows in grouped for item in rows if item["phone"] == client.phone]
        payload = next(item for item in items if item["id"] == client.id)
        self.assertEqual(payload["current_phase_label"], "Фаза 2")
        self.assertIn("уточнює", payload["current_phase_summary"])
        self.assertIn("після 18:00", payload["phase_history_json"])
        self.assertTrue(payload["show_phase_badge"])

    def test_home_page_exposes_jump_cta_for_non_latest_phase_and_keeps_primary_cta_for_today_latest(self):
        phase1 = Client.objects.create(
            shop_name="Jump Phase Shop",
            phone="+380671110189",
            full_name="Jump Owner",
            owner=self.user,
            call_result=Client.CallResult.THINKING,
            next_call_at=timezone.now() + timedelta(hours=2),
        )
        Client.objects.filter(id=phase1.id).update(created_at=timezone.now() - timedelta(days=1))
        phase2 = Client.objects.create(
            shop_name=phase1.shop_name,
            phone=phase1.phone,
            full_name=phase1.full_name,
            owner=self.user,
            call_result=Client.CallResult.NO_ANSWER,
            previous_phase=phase1,
            phase_root=phase1,
            phase_number=2,
            next_call_at=timezone.now() + timedelta(hours=4),
        )

        response = self.client.get("/", secure=True)

        self.assertEqual(response.status_code, 200)
        grouped = response.context["grouped_clients"]
        items = [item for _, rows in grouped for item in rows if item["phone"] == phase1.phone]
        by_id = {item["id"]: item for item in items}

        self.assertEqual(by_id[phase1.id]["phase_action_state"], "jump")
        self.assertEqual(by_id[phase1.id]["phase_target_client_id"], phase2.id)
        self.assertFalse(by_id[phase1.id]["phase_is_latest"])
        self.assertFalse(by_id[phase1.id]["callback_available"])
        self.assertEqual(by_id[phase2.id]["phase_action_state"], "create")
        self.assertTrue(by_id[phase2.id]["phase_is_latest"])
        self.assertEqual(by_id[phase2.id]["phase_number"], 2)
        self.assertContains(response, "До активної фази")
        self.assertContains(response, "Наступна фаза")
        self.assertContains(response, f'id="client-row-{phase1.id}"')
        self.assertContains(response, f'id="client-row-{phase2.id}"')

    def test_home_page_keeps_today_latest_callback_cta_and_marks_attention_soon(self):
        tz = timezone.get_current_timezone()
        now_local = timezone.make_aware(datetime(2026, 3, 20, 3, 5), tz)
        due_at = timezone.make_aware(datetime(2026, 3, 20, 3, 30), tz)

        client = Client.objects.create(
            shop_name="Today Attention Shop",
            phone="+380671110211",
            full_name="Today Owner",
            owner=self.user,
            call_result=Client.CallResult.THINKING,
            next_call_at=due_at,
        )
        ClientFollowUp.objects.create(
            client=client,
            owner=self.user,
            due_at=due_at,
            due_date=due_at.date(),
            grace_until=due_at + timedelta(hours=2),
        )

        with patch("management.views.timezone.now", return_value=now_local), patch(
            "management.views.timezone.localdate", return_value=now_local.date()
        ), patch("management.services.followup_state.timezone.now", return_value=now_local):
            response = self.client.get("/", secure=True)

        self.assertEqual(response.status_code, 200)
        grouped = response.context["grouped_clients"]
        payload = next(
            item
            for _, rows in grouped
            for item in rows
            if item.get("row_kind") == "client" and item["id"] == client.id
        )
        self.assertEqual(payload["phase_action_state"], "create")
        self.assertEqual(payload["callback_attention_state"], "attention_soon")
        self.assertContains(response, "Наступна фаза")

    def test_home_page_renders_today_projection_row_and_keeps_source_row_passive(self):
        due_at = timezone.localtime(timezone.now()).replace(second=0, microsecond=0) + timedelta(hours=2)
        source = Client.objects.create(
            shop_name="Projection Markup Shop",
            phone="+380671110201",
            full_name="Projection Owner",
            owner=self.user,
            call_result=Client.CallResult.THINKING,
            manager_note="Нотатка для reminder-проєкції.",
            next_call_at=due_at,
        )
        Client.objects.filter(id=source.id).update(created_at=timezone.now() - timedelta(days=1))
        followup = ClientFollowUp.objects.create(
            client=source,
            owner=self.user,
            due_at=due_at,
            due_date=due_at.date(),
            grace_until=due_at + timedelta(hours=2),
        )

        response = self.client.get("/", secure=True)

        self.assertEqual(response.status_code, 200)
        grouped = response.context["grouped_clients"]
        source_payload = next(
            item
            for _, rows in grouped
            for item in rows
            if item.get("row_kind") == "client" and item["id"] == source.id
        )
        projection_payload = next(
            item
            for _, rows in grouped
            for item in rows
            if item.get("row_kind") == "followup_projection" and item["source_client_id"] == source.id
        )

        self.assertEqual(response.context["processed_today"], 0)
        self.assertTrue(source_payload["has_today_projection"])
        self.assertEqual(source_payload["phase_action_state"], "none")
        self.assertEqual(source_payload["callback_status_label"], "Нагадування на сьогодні відкрито")
        self.assertEqual(projection_payload["home_group_label"], "Сьогодні")
        self.assertEqual(projection_payload["row_dom_id"], f"client-reminder-{followup.id}")
        self.assertEqual(projection_payload["source_followup_id"], followup.id)
        self.assertEqual(projection_payload["callback_attention_state"], "scheduled_today")
        self.assertContains(response, f'id="client-reminder-{followup.id}"')
        self.assertContains(response, "Нагадування")
        self.assertContains(response, "Не зараховано в оброблені")

    def test_home_page_renders_result_help_trigger_instead_of_inline_details(self):
        Client.objects.create(
            shop_name="Popover Shop",
            phone="+380671110199",
            full_name="Popover Owner",
            owner=self.user,
            call_result=Client.CallResult.NO_ANSWER,
            call_result_details="Причина: Голосова пошта\nУточнення: відповів бот",
        )

        response = self.client.get("/", secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="result-detail-trigger info-dot"')
        self.assertContains(response, 'data-help-target="client-result-help-')
        self.assertContains(response, 'id="client-result-help-')
        self.assertNotContains(response, 'class="muted-detail"')

    def test_home_page_skips_result_help_trigger_without_details_and_exposes_create_phase_state(self):
        client = Client.objects.create(
            shop_name="Next Phase Shop",
            phone="+380671110200",
            full_name="Next Phase Owner",
            owner=self.user,
            call_result=Client.CallResult.THINKING,
            next_call_at=timezone.now() + timedelta(days=1, hours=3),
        )
        Client.objects.filter(id=client.id).update(created_at=timezone.now() - timedelta(days=1))

        response = self.client.get("/", secure=True)

        self.assertEqual(response.status_code, 200)
        grouped = response.context["grouped_clients"]
        flat = {
            item["shop"]: item
            for _, items in grouped
            for item in items
        }
        payload = flat["Next Phase Shop"]
        self.assertEqual(payload["phase_action_state"], "create")
        self.assertNotContains(response, 'data-help-target="client-result-help-')
