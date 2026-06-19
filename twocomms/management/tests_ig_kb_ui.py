"""Тести Phase 8 / Task 23 — CRUD інструкцій/посилань/реклами у вкладці «Бот»."""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from management.models import BotAdCampaign, BotInstruction, BotQuickLink

User = get_user_model()
MGMT = override_settings(ROOT_URLCONF="twocomms.urls_management")


@MGMT
class BotKbApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("kbadm", password="x", is_staff=True)
        self.client.force_login(self.admin)

    def test_create_instruction(self):
        r = self.client.post(reverse("management_bot_kb_save_api"), {
            "type": "instruction", "title": "Графік", "body": "Працюємо щодня 10-20",
        })
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["success"])
        self.assertTrue(BotInstruction.objects.filter(title="Графік").exists())

    def test_create_quicklink(self):
        r = self.client.post(reverse("management_bot_kb_save_api"), {
            "type": "quicklink", "kind": "size_chart", "label": "Сітка худі",
            "url": "https://ig/hl/hoodie", "garment_type": "hoodie",
        })
        self.assertEqual(r.status_code, 200)
        self.assertTrue(BotQuickLink.objects.filter(url="https://ig/hl/hoodie").exists())

    def test_create_adcampaign(self):
        r = self.client.post(reverse("management_bot_kb_save_api"), {
            "type": "adcampaign", "ad_id": "555", "title": "Hoodie промо", "theme": "hoodie",
        })
        self.assertEqual(r.status_code, 200)
        self.assertTrue(BotAdCampaign.objects.filter(ad_id="555").exists())

    def test_delete_instruction(self):
        inst = BotInstruction.objects.create(title="X", body="Y")
        r = self.client.post(reverse("management_bot_kb_save_api"), {
            "type": "instruction", "op": "delete", "id": inst.id,
        })
        self.assertEqual(r.status_code, 200)
        self.assertFalse(BotInstruction.objects.filter(id=inst.id).exists())

    def test_list_returns_all_types(self):
        BotInstruction.objects.create(title="І", body="b")
        BotQuickLink.objects.create(kind="catalog", label="Каталог", url="https://c")
        r = self.client.get(reverse("management_bot_kb_api"))
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(any(i["title"] == "І" for i in data["instructions"]))
        self.assertTrue(any(q["label"] == "Каталог" for q in data["quick_links"]))

    def test_requires_admin(self):
        self.client.logout()
        u = User.objects.create_user("plain", password="x")
        self.client.force_login(u)
        r = self.client.get(reverse("management_bot_kb_api"))
        self.assertEqual(r.status_code, 403)
