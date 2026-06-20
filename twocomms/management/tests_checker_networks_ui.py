"""Блок D: API/рендер поверхні керування мережами."""
import json

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from management.models import LeadNetwork, ManagementLead

User = get_user_model()


@override_settings(
    ROOT_URLCONF="twocomms.urls_management",
    ALLOWED_HOSTS=["testserver", "management.twocomms.shop", "localhost", "127.0.0.1"],
    SECURE_SSL_REDIRECT=False,
)
class NetworksApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("netadmin", password="x", is_staff=True)
        self.client.force_login(self.admin)
        self.net = LeadNetwork.objects.create(
            canonical_name="Rozetka", slug="rozetka", members_count=5, suggested_by_ai=True,
        )
        for i in range(2):
            ManagementLead.objects.create(
                shop_name="Rozetka", phone="05011100" + str(i), network=self.net,
                lead_source=ManagementLead.LeadSource.PARSER,
            )

    def test_list_returns_network_with_stats(self):
        resp = self.client.get(reverse("management_networks_list_api"))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["networks"]["stats"]["total"], 1)
        self.assertEqual(data["networks"]["stats"]["suggested"], 1)
        row = data["networks"]["rows"][0]
        self.assertEqual(row["canonical_name"], "Rozetka")
        self.assertEqual(len(row["members"]), 2)
        self.assertTrue(data["networks"]["policy_choices"])

    def test_filter_by_state_confirmed_excludes_unconfirmed(self):
        resp = self.client.get(reverse("management_networks_list_api"), {"state": "confirmed"})
        self.assertEqual(resp.json()["networks"]["total"], 0)

    def test_set_policy_updates_network(self):
        url = reverse("management_network_update_api", args=[self.net.id])
        resp = self.client.post(url, {"policy": "recheck_each", "extra_instructions": "перевір текстиль"})
        self.assertEqual(resp.status_code, 200)
        self.net.refresh_from_db()
        self.assertEqual(self.net.policy, LeadNetwork.Policy.RECHECK_EACH)
        self.assertEqual(self.net.extra_instructions, "перевір текстиль")

    def test_confirm_sets_confirmed_by_and_activates_policy(self):
        url = reverse("management_network_update_api", args=[self.net.id])
        resp = self.client.post(url, {"action": "confirm", "policy": "block_no_collab"})
        self.assertEqual(resp.status_code, 200)
        self.net.refresh_from_db()
        self.assertTrue(self.net.is_confirmed)
        self.assertEqual(self.net.confirmed_by_id, self.admin.id)
        # Блок B має тепер приймати рішення skip для цієї мережі
        from management.services import network_policy
        lead = self.net.leads.first()
        lead.refresh_from_db()
        self.assertEqual(network_policy.resolve_decision(lead).action, "skip_block")

    def test_apply_known_band_validation(self):
        url = reverse("management_network_update_api", args=[self.net.id])
        resp = self.client.post(url, {"policy": "apply_known_verdict", "known_verdict_band": "bogus"})
        self.assertEqual(resp.status_code, 400)

    def test_invalid_policy_rejected(self):
        url = reverse("management_network_update_api", args=[self.net.id])
        resp = self.client.post(url, {"policy": "nope"})
        self.assertEqual(resp.status_code, 400)

    def test_non_staff_denied(self):
        self.client.logout()
        plain = User.objects.create_user("plain", password="x")
        self.client.force_login(plain)
        resp = self.client.get(reverse("management_networks_list_api"))
        self.assertIn(resp.status_code, (302, 403))


@override_settings(
    ROOT_URLCONF="twocomms.urls_management",
    ALLOWED_HOSTS=["testserver", "management.twocomms.shop", "localhost", "127.0.0.1"],
    SECURE_SSL_REDIRECT=False,
)
class NetworksPanelRenderTests(TestCase):
    def test_leadgen_renders_networks_segment(self):
        admin = User.objects.create_user("netadmin2", password="x", is_staff=True)
        self.client.force_login(admin)
        resp = self.client.get(reverse("management_parsing"), HTTP_HOST="management.twocomms.shop", secure=True)
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn('data-section="networks"', html)
        self.assertIn('id="netops"', html)
        self.assertIn("window.initNetworksPage", html)
