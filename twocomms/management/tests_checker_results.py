"""Вкладка «Перевірені» (модерація AI-перевірених лідів):
серіалізація статусу/мережі + фільтр статусу + масове відхилення мережі."""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from management.checker_views import _results_queryset, serialize_lead_check
from management.models import LeadNetwork, ManagementLead

User = get_user_model()

_MGMT = dict(
    ROOT_URLCONF="twocomms.urls_management",
    ALLOWED_HOSTS=["testserver", "management.twocomms.shop", "localhost", "127.0.0.1"],
    SECURE_SSL_REDIRECT=False,
)


def _checked_lead(**kw):
    defaults = dict(
        lead_source=ManagementLead.LeadSource.PARSER,
        ai_checked_at=timezone.now(),
        ai_score=70,
        ai_verdict="fit",
        status=ManagementLead.Status.MODERATION,
    )
    defaults.update(kw)
    return ManagementLead.objects.create(**defaults)


class SerializeLeadCheckTests(TestCase):
    def test_includes_moderation_and_network_fields(self):
        net = LeadNetwork.objects.create(canonical_name="Мілітарист", slug="militarist")
        lead = _checked_lead(shop_name="Мілітарист №1", phone="0501110001",
                             network=net, rejection_reason="не текстиль")
        data = serialize_lead_check(lead)
        self.assertEqual(data["status"], ManagementLead.Status.MODERATION)
        self.assertEqual(data["status_display"], lead.get_status_display())
        self.assertEqual(data["rejection_reason"], "не текстиль")
        self.assertIn("requires_phone_completion", data)
        self.assertIsNotNone(data["network"])
        self.assertEqual(data["network"]["name"], "Мілітарист")
        self.assertEqual(data["network"]["policy"], net.policy)
        self.assertIn("policy_label", data["network"])

    def test_network_none_when_standalone(self):
        lead = _checked_lead(shop_name="Соло", phone="0501110002")
        self.assertIsNone(serialize_lead_check(lead)["network"])


class ResultsStatusFilterTests(TestCase):
    def setUp(self):
        _checked_lead(shop_name="Mod", phone="0501110010", status=ManagementLead.Status.MODERATION)
        _checked_lead(shop_name="Base", phone="0501110011", status=ManagementLead.Status.BASE)
        _checked_lead(shop_name="Rej", phone="0501110012", status=ManagementLead.Status.REJECTED)

    def test_queryset_filters_by_status(self):
        self.assertEqual(_results_queryset("all", "", "moderation").count(), 1)
        self.assertEqual(_results_queryset("all", "", "rejected").count(), 1)
        self.assertEqual(_results_queryset("all", "", "all").count(), 3)
        self.assertEqual(_results_queryset("all", "", "").count(), 3)


@override_settings(**_MGMT)
class ResultsApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("resadmin", password="x", is_staff=True)
        self.client.force_login(self.admin)
        _checked_lead(shop_name="Mod", phone="0501110020", status=ManagementLead.Status.MODERATION)
        _checked_lead(shop_name="Base", phone="0501110021", status=ManagementLead.Status.BASE)
        _checked_lead(shop_name="Rej", phone="0501110022", status=ManagementLead.Status.REJECTED)

    def test_status_counts_present(self):
        resp = self.client.get(reverse("management_checker_results_api"))
        self.assertEqual(resp.status_code, 200)
        sc = resp.json()["results"]["status_counts"]
        self.assertEqual(sc["moderation"], 1)
        self.assertEqual(sc["base"], 1)
        self.assertEqual(sc["rejected"], 1)
        self.assertEqual(sc["all"], 3)

    def test_status_filter_narrows_rows(self):
        resp = self.client.get(reverse("management_checker_results_api"), {"status": "rejected"})
        rows = resp.json()["results"]["rows"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["shop_name"], "Rej")


@override_settings(**_MGMT)
class NetworkRejectLeadsTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("netrej", password="x", is_staff=True)
        self.client.force_login(self.admin)
        self.net = LeadNetwork.objects.create(canonical_name="Мілітарист", slug="militarist-2")
        self.leads = [
            ManagementLead.objects.create(
                shop_name=f"Мілітарист {i}", phone=f"050111003{i}",
                lead_source=ManagementLead.LeadSource.PARSER, network=self.net,
                status=ManagementLead.Status.MODERATION,
            ) for i in range(3)
        ]

    def test_reject_leads_blocks_network_and_rejects_all(self):
        url = reverse("management_network_update_api", args=[self.net.id])
        resp = self.client.post(url, {"action": "reject_leads", "rejection_reason": "снаряга без текстилю"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["rejected_count"], 3)
        self.net.refresh_from_db()
        self.assertEqual(self.net.policy, LeadNetwork.Policy.BLOCK_NO_COLLAB)
        self.assertTrue(self.net.is_confirmed)
        for lead in self.leads:
            lead.refresh_from_db()
            self.assertEqual(lead.status, ManagementLead.Status.REJECTED)
            self.assertEqual(lead.rejection_reason, "снаряга без текстилю")


@override_settings(**_MGMT)
class ResultsPanelRenderTests(TestCase):
    def test_leadgen_renders_moderation_cards_scaffold(self):
        admin = User.objects.create_user("resrender", password="x", is_staff=True)
        self.client.force_login(admin)
        resp = self.client.get(reverse("management_parsing"), HTTP_HOST="management.twocomms.shop", secure=True)
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        # Нова поверхня модерації перевірених
        self.assertIn('id="chk-statusbar"', html)
        self.assertIn('data-status="moderation"', html)
        self.assertIn('id="chk-list"', html)
        self.assertIn("data-moderate-url-template", html)
        self.assertIn("data-network-update-template", html)
        self.assertIn("cardHtml", html)
        # Стара таблиця/модалка прибрані
        self.assertNotIn("checker-results-table", html)
        self.assertNotIn("checker-detail-modal", html)
