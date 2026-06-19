"""Фаза 2: фільтри черги модерації (ключове слово, AI-вердикт) + AI-поля у картці."""
from django.test import TestCase
from django.utils import timezone

from management.models import ManagementLead
from management.parsing_views import _moderation_payload, _serialize_moderation_lead


class ModerationFilterTests(TestCase):
    def _lead(self, **kw):
        data = dict(
            status=ManagementLead.Status.MODERATION,
            lead_source=ManagementLead.LeadSource.PARSER,
        )
        data.update(kw)
        return ManagementLead.objects.create(**data)

    def test_keyword_filter_matches_parser_keyword(self):
        self._lead(shop_name="A", phone="0501110001", parser_keyword="магазин одягу")
        self._lead(shop_name="B", phone="0501110002", parser_keyword="зброя оптика")
        payload = _moderation_payload(keyword="одяг")
        names = [i["shop_name"] for i in payload["items"]]
        self.assertIn("A", names)
        self.assertNotIn("B", names)
        self.assertEqual(payload["filters"]["keyword"], "одяг")

    def test_verdict_filter_keeps_only_matching(self):
        self._lead(shop_name="Fit", phone="0501110003", ai_verdict="fit", ai_checked_at=timezone.now())
        self._lead(shop_name="Unfit", phone="0501110004", ai_verdict="unfit", ai_checked_at=timezone.now())
        payload = _moderation_payload(verdict="fit")
        names = [i["shop_name"] for i in payload["items"]]
        self.assertEqual(names, ["Fit"])

    def test_verdict_unchecked_filter(self):
        self._lead(shop_name="Checked", phone="0501110005", ai_verdict="fit", ai_checked_at=timezone.now())
        self._lead(shop_name="New", phone="0501110006")
        payload = _moderation_payload(verdict="unchecked")
        names = [i["shop_name"] for i in payload["items"]]
        self.assertEqual(names, ["New"])

    def test_combined_city_and_keyword(self):
        self._lead(shop_name="KH", phone="0501110007", city="Харків", parser_keyword="одяг")
        self._lead(shop_name="KY", phone="0501110008", city="Київ", parser_keyword="одяг")
        payload = _moderation_payload(city="Харків", keyword="одяг")
        names = [i["shop_name"] for i in payload["items"]]
        self.assertEqual(names, ["KH"])

    def test_serialize_includes_ai_fields(self):
        lead = self._lead(shop_name="X", phone="0501110009", ai_score=72, ai_verdict="fit",
                          ai_checked_at=timezone.now())
        data = _serialize_moderation_lead(lead)
        self.assertEqual(data["ai_score"], 72)
        self.assertEqual(data["ai_verdict"], "fit")
        self.assertEqual(data["ai_verdict_display"], "Підходить")
