from datetime import timedelta

from django.apps import apps
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from management.models import Client, ClientInteractionAttempt, CommercialOfferEmailLog, DuplicateReview, Shop, normalize_phone


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
        client = Client.objects.create(
            shop_name="Phase Shop",
            phone="+380671110188",
            full_name="Phase Owner",
            owner=self.user,
            call_result=Client.CallResult.THINKING,
            manager_note="Загальна нотатка по клієнту.",
            next_call_at=timezone.now() + timedelta(hours=2),
        )
        first_attempt = ClientInteractionAttempt.objects.create(
            client=client,
            manager=self.user,
            result=Client.CallResult.THINKING,
            reason_note="Попросив передзвонити після 18:00.",
            details="Фаза 1: сказав передзвонити після 18:00.",
            next_call_at=timezone.now() + timedelta(hours=1),
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
        flat = {
            item["shop"]: item
            for _, items in grouped
            for item in items
        }
        payload = flat["Phase Shop"]
        self.assertEqual(payload["current_phase_label"], "Фаза 2")
        self.assertIn("погодження", payload["current_phase_summary"])
        self.assertIn("після 18:00", payload["phase_history_json"])
        self.assertTrue(payload["show_phase_badge"])

    def test_home_page_hides_phase_badge_until_real_third_phase(self):
        client = Client.objects.create(
            shop_name="Early Phase Shop",
            phone="+380671110189",
            full_name="Early Owner",
            owner=self.user,
            call_result=Client.CallResult.THINKING,
            next_call_at=timezone.now() + timedelta(hours=2),
        )
        ClientInteractionAttempt.objects.create(
            client=client,
            manager=self.user,
            result=Client.CallResult.THINKING,
            reason_note="Просив передзвонити трохи пізніше.",
            details="Фаза 1: просив передзвонити пізніше.",
            next_call_at=timezone.now() + timedelta(hours=2),
        )

        response = self.client.get("/", secure=True)

        self.assertEqual(response.status_code, 200)
        grouped = response.context["grouped_clients"]
        flat = {
            item["shop"]: item
            for _, items in grouped
            for item in items
        }
        payload = flat["Early Phase Shop"]
        self.assertFalse(payload["show_phase_badge"])
