from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from management.models import Client, DuplicateReview, ManagementLead
from management.services.dedupe import DedupeZone, evaluate_duplicate_zone


class DedupeServiceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="dedupe_mgr", password="x", is_staff=True)

    def test_exact_phone_match_without_shared_flag_is_auto_block(self):
        existing = Client.objects.create(
            shop_name="Alpha Store",
            phone="+380671112233",
            full_name="Owner",
            owner=self.user,
        )

        decision = evaluate_duplicate_zone(
            shop_name="Alpha Store",
            phone="+380671112233",
            website_url="",
            owner=self.user,
        )

        self.assertEqual(decision.zone, DedupeZone.AUTO_BLOCK)
        self.assertEqual(decision.candidates[0]["kind"], "client")
        self.assertEqual(decision.candidates[0]["id"], existing.id)

    def test_exact_phone_match_for_shared_phone_goes_to_review(self):
        Client.objects.create(
            shop_name="Shared Line Shop",
            phone="+380671112233",
            full_name="Owner",
            owner=self.user,
            is_shared_phone=True,
            phone_group_id="switchboard-a",
        )

        decision = evaluate_duplicate_zone(
            shop_name="Another Shared Shop",
            phone="+380671112233",
            website_url="",
            owner=self.user,
        )

        self.assertEqual(decision.zone, DedupeZone.REVIEW)


@override_settings(ROOT_URLCONF="twocomms.urls_management")
class LeadCreateDedupeApiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="dedupe_api_mgr", password="x", is_staff=True)
        self.client.force_login(self.user)

    def test_lead_create_returns_structured_auto_block_for_duplicate(self):
        existing = Client.objects.create(
            shop_name="Alpha Store",
            phone="+380671112233",
            full_name="Owner",
            owner=self.user,
        )

        response = self.client.post(
            "/leads/api/create/",
            {
                "shop_name": "Alpha Store",
                "phone": "+380671112233",
                "full_name": "Owner",
            },
            secure=True,
        )

        self.assertEqual(response.status_code, 409)
        payload = response.json()
        self.assertEqual(payload["zone"], DedupeZone.AUTO_BLOCK)
        self.assertEqual(payload["candidates"][0]["id"], existing.id)

    def test_lead_create_creates_duplicate_review_for_shared_phone(self):
        Client.objects.create(
            shop_name="Shared Line Shop",
            phone="+380671112233",
            full_name="Owner",
            owner=self.user,
            is_shared_phone=True,
            phone_group_id="switchboard-a",
        )

        response = self.client.post(
            "/leads/api/create/",
            {
                "shop_name": "Potential Shared Shop",
                "phone": "+380671112233",
                "full_name": "Owner",
            },
            secure=True,
        )

        self.assertEqual(response.status_code, 409)
        payload = response.json()
        self.assertEqual(payload["zone"], DedupeZone.REVIEW)
        self.assertTrue(payload["duplicate_review_id"])


@override_settings(ROOT_URLCONF="twocomms.urls_management")
class LeadProcessDedupeApiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="lead_process_mgr", password="x", is_staff=True)
        self.client.force_login(self.user)

    def _base_payload(self):
        return {
            "shop_name": "Target Shop",
            "phone": "+380671112233",
            "website_url": "https://target.example.com",
            "full_name": "Owner",
            "role": Client.Role.MANAGER,
            "source": "instagram",
            "call_result": Client.CallResult.THINKING,
        }

    def test_lead_process_returns_structured_auto_block_for_duplicate_client(self):
        lead = ManagementLead.objects.create(
            shop_name="Target Shop",
            phone="+380501234567",
            full_name="Owner",
            status=ManagementLead.Status.BASE,
            added_by=self.user,
        )
        existing = Client.objects.create(
            shop_name="Alpha Store",
            phone="+380671112233",
            full_name="Owner",
            owner=self.user,
        )

        response = self.client.post(
            f"/leads/api/{lead.id}/process/",
            self._base_payload(),
            secure=True,
        )

        self.assertEqual(response.status_code, 409)
        payload = response.json()
        self.assertEqual(payload["zone"], DedupeZone.AUTO_BLOCK)
        self.assertEqual(payload["candidates"][0]["id"], existing.id)
        self.assertFalse(Client.objects.filter(shop_name="Target Shop", phone="+380671112233").exists())

    def test_lead_process_creates_duplicate_review_for_shared_phone(self):
        lead = ManagementLead.objects.create(
            shop_name="Target Shop",
            phone="+380501234567",
            full_name="Owner",
            status=ManagementLead.Status.BASE,
            added_by=self.user,
        )
        Client.objects.create(
            shop_name="Shared Line Shop",
            phone="+380671112233",
            full_name="Owner",
            owner=self.user,
            is_shared_phone=True,
            phone_group_id="switchboard-a",
        )

        response = self.client.post(
            f"/leads/api/{lead.id}/process/",
            self._base_payload(),
            secure=True,
        )

        self.assertEqual(response.status_code, 409)
        payload = response.json()
        self.assertEqual(payload["zone"], DedupeZone.REVIEW)
        self.assertTrue(payload["duplicate_review_id"])
        self.assertEqual(DuplicateReview.objects.count(), 1)

    def test_lead_process_ignores_current_lead_when_phone_unchanged(self):
        lead = ManagementLead.objects.create(
            shop_name="Target Shop",
            phone="+380501234567",
            full_name="Owner",
            status=ManagementLead.Status.BASE,
            added_by=self.user,
        )

        response = self.client.post(
            f"/leads/api/{lead.id}/process/",
            {
                **self._base_payload(),
                "phone": "+380501234567",
            },
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        lead.refresh_from_db()
        self.assertEqual(lead.status, ManagementLead.Status.CONVERTED)

    def test_lead_process_persists_structured_negative_outcome_reason(self):
        lead = ManagementLead.objects.create(
            shop_name="Target Shop",
            phone="+380501234567",
            full_name="Owner",
            status=ManagementLead.Status.BASE,
            added_by=self.user,
        )

        response = self.client.post(
            f"/leads/api/{lead.id}/process/",
            {
                **self._base_payload(),
                "call_result": Client.CallResult.NO_ANSWER,
                "call_result_reason_code": "busy",
                "call_result_contact_attempts": "3",
                "call_result_contact_channel": "phone",
            },
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        created = Client.objects.get(shop_name="Target Shop", owner=self.user)
        self.assertEqual(created.call_result_reason_code, "busy")
        self.assertEqual(created.call_result_context["attempts"], 3)
        self.assertEqual(created.call_result_context["contact_channel"], "phone")
        self.assertIn("Спроб: 3", created.call_result_details)


@override_settings(ROOT_URLCONF="twocomms.urls_management")
class ParsingModerationDedupeApiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="parser_admin_mgr", password="x", is_staff=True)
        self.client.force_login(self.user)

    def test_parser_approve_returns_structured_auto_block_for_duplicate_client(self):
        lead = ManagementLead.objects.create(
            shop_name="Moderation Shop",
            phone="+380501234567",
            full_name="Owner",
            status=ManagementLead.Status.MODERATION,
            lead_source=ManagementLead.LeadSource.PARSER,
            added_by=self.user,
        )
        existing = Client.objects.create(
            shop_name="Alpha Store",
            phone="+380671112233",
            full_name="Owner",
            owner=self.user,
        )

        response = self.client.post(
            f"/parsing/api/leads/{lead.id}/action/",
            {
                "action": "approve",
                "shop_name": "Moderation Shop",
                "phone": "+380671112233",
                "full_name": "Owner",
            },
            secure=True,
        )

        self.assertEqual(response.status_code, 409)
        payload = response.json()
        self.assertEqual(payload["zone"], DedupeZone.AUTO_BLOCK)
        self.assertEqual(payload["candidates"][0]["id"], existing.id)
        lead.refresh_from_db()
        self.assertEqual(lead.status, ManagementLead.Status.MODERATION)

    def test_parser_save_creates_duplicate_review_for_shared_phone(self):
        lead = ManagementLead.objects.create(
            shop_name="Moderation Shop",
            phone="+380501234567",
            full_name="Owner",
            status=ManagementLead.Status.MODERATION,
            lead_source=ManagementLead.LeadSource.PARSER,
            added_by=self.user,
        )
        Client.objects.create(
            shop_name="Shared Line Shop",
            phone="+380671112233",
            full_name="Owner",
            owner=self.user,
            is_shared_phone=True,
            phone_group_id="switchboard-a",
        )

        response = self.client.post(
            f"/parsing/api/leads/{lead.id}/action/",
            {
                "action": "save",
                "shop_name": "Moderation Shop",
                "phone": "+380671112233",
                "full_name": "Owner",
            },
            secure=True,
        )

        self.assertEqual(response.status_code, 409)
        payload = response.json()
        self.assertEqual(payload["zone"], DedupeZone.REVIEW)
        self.assertTrue(payload["duplicate_review_id"])
        self.assertEqual(DuplicateReview.objects.count(), 1)


@override_settings(ROOT_URLCONF="twocomms.urls_management")
class HomeClientDedupeAndReasonTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="home_mgr", password="x", is_staff=True)
        self.client.force_login(self.user)

    def test_home_create_returns_structured_duplicate_conflict(self):
        existing = Client.objects.create(
            shop_name="Alpha Store",
            phone="+380671112233",
            full_name="Owner",
            owner=self.user,
        )

        response = self.client.post(
            "/",
            {
                "shop_name": "Alpha Store",
                "phone": "+380671112233",
                "full_name": "Owner",
                "role": Client.Role.MANAGER,
                "call_result": Client.CallResult.THINKING,
                "next_call_type": "no_follow",
            },
            secure=True,
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 409)
        payload = response.json()
        self.assertEqual(payload["zone"], DedupeZone.AUTO_BLOCK)
        self.assertEqual(payload["candidates"][0]["id"], existing.id)
        self.assertEqual(Client.objects.count(), 1)

    def test_home_create_stores_structured_not_interested_reason(self):
        response = self.client.post(
            "/",
            {
                "shop_name": "Reason Shop",
                "phone": "+380671112244",
                "full_name": "Owner",
                "role": Client.Role.MANAGER,
                "source": "instagram",
                "call_result": Client.CallResult.NOT_INTERESTED,
                "call_result_reason_code": "current_supplier",
                "call_result_reason_note": "Працюють по діючому договору до кінця сезону",
                "next_call_type": "no_follow",
            },
            secure=True,
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        created = Client.objects.get(shop_name="Reason Shop", owner=self.user)
        self.assertEqual(created.call_result_reason_code, "current_supplier")
        self.assertEqual(created.call_result_reason_note, "Працюють по діючому договору до кінця сезону")
        self.assertEqual(created.call_result_context["note"], "Працюють по діючому договору до кінця сезону")
        self.assertIn("Причина:", created.call_result_details)

    def test_home_page_renders_reason_capture_fields(self):
        response = self.client.get("/", secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Причина результату")
        self.assertContains(response, "Кількість спроб")
        self.assertContains(response, "Основний канал")
