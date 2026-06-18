from django.test import TestCase

from management.models import ManagementLead


class ManagementLeadAICacheFieldsTests(TestCase):
    def test_ai_cache_fields_default_empty(self):
        lead = ManagementLead.objects.create(shop_name="Test Shop", phone="0501112233")
        self.assertIsNone(lead.ai_score)
        self.assertEqual(lead.ai_verdict, "")
        self.assertIsNone(lead.ai_checked_at)

    def test_ai_cache_fields_persist(self):
        from django.utils import timezone
        lead = ManagementLead.objects.create(shop_name="Test Shop", phone="0501112233")
        lead.ai_score = 82
        lead.ai_verdict = "fit"
        lead.ai_checked_at = timezone.now()
        lead.save(update_fields=["ai_score", "ai_verdict", "ai_checked_at"])
        lead.refresh_from_db()
        self.assertEqual(lead.ai_score, 82)
        self.assertEqual(lead.ai_verdict, "fit")
        self.assertIsNotNone(lead.ai_checked_at)


from unittest.mock import patch

from management.models import LeadAICheck
from management.services import lead_checker as lc


class BandMappingTests(TestCase):
    def test_band_for_score(self):
        self.assertEqual(lc.band_for_score(85), "fit")
        self.assertEqual(lc.band_for_score(70), "fit")
        self.assertEqual(lc.band_for_score(69), "maybe")
        self.assertEqual(lc.band_for_score(40), "maybe")
        self.assertEqual(lc.band_for_score(39), "unfit")
        self.assertEqual(lc.band_for_score(0), "unfit")

    def test_niche_for_band(self):
        self.assertEqual(lc.niche_for_band("fit"), ManagementLead.NicheStatus.NICHE)
        self.assertEqual(lc.niche_for_band("maybe"), ManagementLead.NicheStatus.MAYBE)
        self.assertEqual(lc.niche_for_band("unfit"), ManagementLead.NicheStatus.NON_NICHE)

    def test_criteria_has_ten_keys(self):
        self.assertEqual(len(lc.CRITERIA), 10)
        keys = [c[0] for c in lc.CRITERIA]
        self.assertIn("custom_print_potential", keys)
        self.assertIn("collab_potential", keys)
        self.assertEqual(len(set(keys)), 10)


class ContextBuildTests(TestCase):
    def test_build_lead_context_includes_key_fields(self):
        lead = ManagementLead.objects.create(
            shop_name="Coyote Wear", phone="0501112233", city="Харків",
            website_url="https://coyotewear.example",
            extra_data={"types": ["clothing_store"], "formattedAddress": "вул. Сумська, 1"},
        )
        ctx = lc.build_lead_context(lead)
        self.assertIn("Coyote Wear", ctx)
        self.assertIn("Харків", ctx)
        self.assertIn("coyotewear.example", ctx)
        self.assertIn("clothing_store", ctx)
        self.assertIn("Сумська", ctx)

    def test_fetch_website_text_strips_html_and_truncates(self):
        html = "<html><head><style>x{}</style></head><body><h1>Hello</h1><p>" + ("A" * 9000) + "</p></body></html>"

        class FakeResp:
            status_code = 200
            text = html
            headers = {"content-type": "text/html"}

        with patch.object(lc.requests, "get", return_value=FakeResp()):
            text, ok = lc.fetch_website_text("https://x.example")
        self.assertTrue(ok)
        self.assertIn("Hello", text)
        self.assertNotIn("<h1>", text)
        self.assertLessEqual(len(text), lc.WEBSITE_TEXT_LIMIT)

    def test_fetch_website_text_handles_failure(self):
        with patch.object(lc.requests, "get", side_effect=Exception("boom")):
            text, ok = lc.fetch_website_text("https://x.example")
        self.assertFalse(ok)
        self.assertEqual(text, "")

    def test_fetch_website_text_empty_url(self):
        text, ok = lc.fetch_website_text("")
        self.assertFalse(ok)
        self.assertEqual(text, "")


class SystemPromptTests(TestCase):
    def test_prompt_mentions_brand_audience_and_channels(self):
        prompt = lc.build_system_prompt()
        self.assertIn("TwoComms", prompt)
        self.assertIn("streetwear", prompt.lower())
        self.assertIn("40", prompt)
        self.assertIn("custom_print", prompt)
        self.assertIn("wholesale", prompt)
        self.assertIn("collab", prompt)
        for key, _title in lc.CRITERIA:
            self.assertIn(key, prompt)
        self.assertIn("JSON", prompt)
        self.assertIn("overall_score", prompt)


class NormalizeResultTests(TestCase):
    def test_normalize_full_result(self):
        raw = {
            "overall_score": 82,
            "verdict_category": "brand",
            "partnership_fit": ["wholesale", "collab", "bogus_channel"],
            "confidence": "high",
            "brand_summary": "UA streetwear бренд",
            "audience_guess": "молодь, патріоти",
            "instagram_url": "https://instagram.com/coyote",
            "criteria": [{"key": k, "score": 8, "comment": "ok"} for k, _ in lc.CRITERIA],
            "comment": "гарний кандидат",
            "recommendation": "пропонувати колаб",
            "sources": [{"title": "IG", "url": "https://instagram.com/coyote"}],
        }
        norm = lc.normalize_result(raw)
        self.assertEqual(norm["overall_score"], 82)
        self.assertEqual(norm["verdict_category"], "brand")
        self.assertEqual(norm["partnership_fit"], ["wholesale", "collab"])
        self.assertEqual(len(norm["criteria"]), 10)

    def test_normalize_clamps_and_defaults(self):
        norm = lc.normalize_result({"overall_score": 250, "criteria": []})
        self.assertEqual(norm["overall_score"], 100)
        self.assertEqual(norm["confidence"], "low")
        self.assertEqual(norm["verdict_category"], "other")
        self.assertEqual(norm["partnership_fit"], [])
        self.assertEqual(len(norm["criteria"]), 10)
        self.assertEqual(norm["criteria"][0]["score"], 0)

    def test_normalize_derives_score_when_missing(self):
        crit = [{"key": k, "score": 5, "comment": ""} for k, _ in lc.CRITERIA]
        norm = lc.normalize_result({"criteria": crit})
        self.assertEqual(norm["overall_score"], 50)

    def test_normalize_bad_score_value(self):
        norm = lc.normalize_result({"overall_score": "abc", "criteria": []})
        self.assertEqual(norm["overall_score"], 0)


class ScoreLeadTests(TestCase):
    def _raw(self, score):
        return {
            "overall_score": score,
            "verdict_category": "brand",
            "partnership_fit": ["wholesale"],
            "confidence": "high",
            "brand_summary": "ok",
            "criteria": [{"key": k, "score": 8, "comment": "c"} for k, _ in lc.CRITERIA],
            "comment": "good",
            "recommendation": "pitch",
            "sources": [{"title": "t", "url": "https://x"}],
        }

    def test_score_lead_saves_check_and_updates_cache(self):
        lead = ManagementLead.objects.create(shop_name="Shop", phone="0501112233", website_url="")
        fake = {"parsed": self._raw(82), "usage": {"totalTokenCount": 100}, "model": "gemini-2.5-flash"}
        with patch.object(lc, "gemini_generate_grounded", return_value=fake) as gm, \
             patch.object(lc, "fetch_website_text", return_value=("", False)):
            check = lc.score_lead(lead)
        self.assertEqual(check.status, LeadAICheck.Status.DONE)
        self.assertEqual(check.overall_score, 82)
        self.assertEqual(check.model_used, "gemini-2.5-flash")
        gm.assert_called_once()
        lead.refresh_from_db()
        self.assertEqual(lead.ai_score, 82)
        self.assertEqual(lead.ai_verdict, "fit")
        self.assertIsNotNone(lead.ai_checked_at)
        self.assertEqual(lead.niche_status, ManagementLead.NicheStatus.NICHE)

    def test_score_lead_maybe_band_maps_niche(self):
        lead = ManagementLead.objects.create(shop_name="Shop2", phone="0501112244")
        fake = {"parsed": self._raw(55), "usage": {}, "model": "m"}
        with patch.object(lc, "gemini_generate_grounded", return_value=fake), \
             patch.object(lc, "fetch_website_text", return_value=("", False)):
            lc.score_lead(lead)
        lead.refresh_from_db()
        self.assertEqual(lead.ai_verdict, "maybe")
        self.assertEqual(lead.niche_status, ManagementLead.NicheStatus.MAYBE)

    def test_score_lead_handles_gemini_error(self):
        from management.services.call_ai_analysis import CallAIAnalysisError
        lead = ManagementLead.objects.create(shop_name="Shop3", phone="0501112255")
        with patch.object(lc, "gemini_generate_grounded", side_effect=CallAIAnalysisError("boom")), \
             patch.object(lc, "fetch_website_text", return_value=("", False)):
            check = lc.score_lead(lead)
        self.assertEqual(check.status, LeadAICheck.Status.ERROR)
        self.assertIn("boom", check.error)
        lead.refresh_from_db()
        self.assertEqual(lead.ai_verdict, "error")
        self.assertIsNotNone(lead.ai_checked_at)

    def test_score_lead_passes_api_key(self):
        lead = ManagementLead.objects.create(shop_name="Shop4", phone="0501112266")
        fake = {"parsed": self._raw(70), "usage": {}, "model": "m"}
        with patch.object(lc, "gemini_generate_grounded", return_value=fake) as gm, \
             patch.object(lc, "fetch_website_text", return_value=("", False)):
            lc.score_lead(lead, api_key="custom-key")
        _, kwargs = gm.call_args
        self.assertEqual(kwargs.get("api_key"), "custom-key")


class NormalizeVerdictCategoryTests(TestCase):
    def test_unknown_category_maps_to_other(self):
        out = lc.normalize_result({"overall_score": 20, "verdict_category": "wholesale_supplier", "criteria": []})
        self.assertEqual(out["verdict_category"], "wholesale_supplier")  # тепер у списку
        out2 = lc.normalize_result({"overall_score": 10, "verdict_category": "zzz_invalid", "criteria": []})
        self.assertEqual(out2["verdict_category"], "other")

    def test_empty_category_defaults_other(self):
        out = lc.normalize_result({"overall_score": 50, "criteria": []})
        self.assertEqual(out["verdict_category"], "other")
