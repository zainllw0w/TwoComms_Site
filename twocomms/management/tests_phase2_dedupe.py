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
