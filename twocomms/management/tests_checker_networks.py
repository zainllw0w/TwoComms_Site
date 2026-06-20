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


from management.services import network_resolver as nr


class NetworkKeyTests(TestCase):
    def test_translit_merges_cyrillic_latin(self):
        self.assertEqual(nr.network_match_key("Arber"), nr.network_match_key("Арбер"))

    def test_generic_detected(self):
        self.assertTrue(nr.is_generic_name("військторг"))
        self.assertTrue(nr.is_generic_name("Магазин"))
        self.assertFalse(nr.is_generic_name("Rozetka"))


class ClassifyClusterTests(TestCase):
    def _lead(self, name, phone, website=""):
        return ManagementLead.objects.create(
            shop_name=name, phone=phone, website_url=website,
            lead_source=ManagementLead.LeadSource.PARSER,
        )

    def test_single_is_standalone(self):
        self._lead("Coyote Wear", "0501112233", "https://coyote.example")
        res = nr.resolve_all()
        self.assertEqual(res["standalone"], 1)
        self.assertEqual(LeadNetwork.objects.count(), 0)

    def test_shared_website_is_network(self):
        for i in range(3):
            self._lead("Rozetka", f"050111220{i}", "https://rozetka.com.ua")
        nr.resolve_all()
        self.assertEqual(LeadNetwork.objects.count(), 1)
        net = LeadNetwork.objects.first()
        self.assertEqual(net.leads.count(), 3)
        self.assertEqual(net.policy, LeadNetwork.Policy.NEEDS_REVIEW)
        self.assertEqual(net.members_count, 3)

    def test_generic_not_merged(self):
        for i in range(4):
            self._lead("Військторг", f"050999100{i}")
        nr.resolve_all()
        self.assertEqual(LeadNetwork.objects.count(), 0)
        self.assertTrue(all(l.needs_disambiguation for l in ManagementLead.objects.all()))

    def test_translit_cluster_merged(self):
        self._lead("Arber", "0501110001", "https://arber.ua")
        self._lead("Арбер", "0501110002", "https://arber.com.ua")
        nr.resolve_all()
        self.assertEqual(LeadNetwork.objects.count(), 1)

    def test_idempotent(self):
        for i in range(3):
            self._lead("Sinsay", f"050222330{i}", "https://sinsay.com")
        nr.resolve_all()
        nr.resolve_all()
        self.assertEqual(LeadNetwork.objects.count(), 1)
        self.assertEqual(LeadNetwork.objects.first().leads.count(), 3)
