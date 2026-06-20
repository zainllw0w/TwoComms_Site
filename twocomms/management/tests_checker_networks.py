"""Блок A (network core): LeadNetwork + NetworkAlias + резолвер класифікації."""
from django.db import IntegrityError
from django.test import TestCase

from management.models import LeadNetwork, NetworkAlias, ManagementLead


class LeadNetworkModelTests(TestCase):
    def test_create_defaults(self):
        n = LeadNetwork.objects.create(canonical_name="Rozetka", slug="rozetka")
        self.assertEqual(n.policy, LeadNetwork.Policy.NEEDS_REVIEW)
        self.assertEqual(n.kind, LeadNetwork.Kind.UNKNOWN)
        self.assertEqual(n.collaboration_evidence, "")
        self.assertEqual(n.members_count, 0)
        self.assertIsNone(n.confirmed_by_id)
        self.assertFalse(n.is_confirmed)


class NetworkAliasTests(TestCase):
    def test_alias_unique_per_type_value(self):
        n = LeadNetwork.objects.create(canonical_name="Arber", slug="arber")
        NetworkAlias.objects.create(network=n, key_type="name", key_value="arber")
        with self.assertRaises(IntegrityError):
            NetworkAlias.objects.create(network=n, key_type="name", key_value="arber")


class ManagementLeadNetworkFieldsTests(TestCase):
    def test_lead_network_defaults(self):
        lead = ManagementLead.objects.create(shop_name="S", phone="0501112233")
        self.assertIsNone(lead.network_id)
        self.assertEqual(lead.network_membership_source, "")
        self.assertFalse(lead.needs_disambiguation)
