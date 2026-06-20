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

    def test_criteria_includes_apparel_focus_and_eleven_keys(self):
        self.assertEqual(len(lc.CRITERIA), 11)
        keys = [c[0] for c in lc.CRITERIA]
        self.assertIn("apparel_focus", keys)
        self.assertIn("custom_print_potential", keys)
        self.assertIn("collab_potential", keys)
        self.assertEqual(len(set(keys)), 11)


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
            "sells_third_party_brands": "yes",
            "own_production": "no",
            "brand_summary": "UA streetwear бренд",
            "audience_guess": "молодь, патріоти",
            "instagram_url": "https://instagram.com/coyote",
            "criteria": [{"key": k, "score": 8, "comment": "ok"} for k, _ in lc.CRITERIA],
            "comment": "гарний кандидат",
            "recommendation": "пропонувати колаб",
            "sources": [{"title": "IG", "url": "https://instagram.com/coyote"}],
        }
        norm = lc.normalize_result(raw)
        # overall тепер рахується НА СЕРВЕРІ з критеріїв (усі=8 → 80), модельні 82 ігноруються
        self.assertEqual(norm["overall_score"], 80)
        self.assertEqual(norm["verdict_category"], "brand")
        self.assertEqual(norm["partnership_fit"], ["wholesale", "collab"])
        self.assertEqual(len(norm["criteria"]), 11)

    def test_normalize_clamps_and_defaults(self):
        norm = lc.normalize_result({"overall_score": 250, "criteria": []})
        # порожні критерії → 0 (server-computed), модельні 250 ігноруються
        self.assertEqual(norm["overall_score"], 0)
        self.assertEqual(norm["confidence"], "low")
        self.assertEqual(norm["verdict_category"], "other")
        self.assertEqual(norm["partnership_fit"], [])
        self.assertEqual(len(norm["criteria"]), 11)
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
            # scoring v2: для fit потрібні докази співпраці з чужими брендами
            "sells_third_party_brands": "yes",
            "own_production": "no",
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
        self.assertEqual(check.overall_score, 80)  # server-computed з критеріїв (усі=8)
        self.assertEqual(check.model_used, "gemini-2.5-flash")
        gm.assert_called_once()
        lead.refresh_from_db()
        self.assertEqual(lead.ai_score, 80)
        self.assertEqual(lead.ai_verdict, "fit")
        self.assertIsNotNone(lead.ai_checked_at)
        self.assertEqual(lead.niche_status, ManagementLead.NicheStatus.NICHE)

    def test_score_lead_maybe_band_maps_niche(self):
        lead = ManagementLead.objects.create(shop_name="Shop2", phone="0501112244")
        raw = self._raw(55)
        # критерії ~5 → server-computed ~50 = maybe (apparel_focus=5 → без гейту)
        raw["criteria"] = [{"key": k, "score": 5, "comment": "c"} for k, _ in lc.CRITERIA]
        fake = {"parsed": raw, "usage": {}, "model": "m"}
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


class CheckerKeysExhaustedTests(TestCase):
    def test_quota_exhaustion_raises_and_does_not_mark_lead(self):
        from management.models import ManagementLead, LeadAICheck
        from management.services.call_ai_analysis import CallAIAnalysisError
        lead = ManagementLead.objects.create(shop_name="Q", phone="0509990000",
                                             lead_source=ManagementLead.LeadSource.PARSER)
        err = CallAIAnalysisError("Усі ключі/моделі Gemini недоступні (квота/перевантаження). Спроби: ...")
        with patch.object(lc, "gemini_generate_grounded", side_effect=err), \
             patch.object(lc, "fetch_website_text", return_value=("", False)):
            with self.assertRaises(lc.CheckerKeysExhausted):
                lc.score_lead(lead)
        lead.refresh_from_db()
        self.assertIsNone(lead.ai_checked_at)   # лід НЕ позначено перевіреним
        self.assertEqual(lead.ai_verdict, "")
        self.assertEqual(LeadAICheck.objects.filter(lead=lead).count(), 0)  # processing-чек видалено

    def test_real_eval_error_marks_lead_error(self):
        from management.models import ManagementLead, LeadAICheck
        from management.services.call_ai_analysis import CallAIAnalysisError
        lead = ManagementLead.objects.create(shop_name="E", phone="0509990001",
                                             lead_source=ManagementLead.LeadSource.PARSER)
        with patch.object(lc, "gemini_generate_grounded", side_effect=CallAIAnalysisError("Помилка запиту")), \
             patch.object(lc, "fetch_website_text", return_value=("", False)):
            check = lc.score_lead(lead)
        lead.refresh_from_db()
        self.assertEqual(check.status, LeadAICheck.Status.ERROR)
        self.assertEqual(lead.ai_verdict, "error")
        self.assertIsNotNone(lead.ai_checked_at)


class CheckerScoreCalibrationTests(TestCase):
    """Фаза 2: overall рахується на сервері з критеріїв (фікс «завжди ~85»);
    жорсткий apparel-гейт — бренд продає ОДЯГ, тож магазин без одягу = unfit,
    навіть якщо мілітарі-аудиторія висока."""

    def _by(self, default=5, **over):
        bk = {k: default for k, _ in lc.CRITERIA}
        bk.update(over)
        return bk

    def test_all_high_real_apparel_fit_is_fit(self):
        score = lc.compute_overall_from_criteria(self._by(default=9))
        self.assertGreaterEqual(score, 70)
        self.assertEqual(lc.band_for_score(score), "fit")

    def test_all_mid_is_maybe(self):
        score = lc.compute_overall_from_criteria(self._by(default=5))
        self.assertEqual(score, 50)
        self.assertEqual(lc.band_for_score(score), "maybe")

    def test_apparel_gate_caps_non_apparel_to_unfit(self):
        # все високо, але магазин НЕ продає одяг + мілітарі-аудиторія максимум
        score = lc.compute_overall_from_criteria(
            self._by(default=8, apparel_focus=1, military_tactical=10)
        )
        self.assertLessEqual(score, 25)
        self.assertEqual(lc.band_for_score(score), "unfit")

    def test_weak_apparel_capped_below_fit(self):
        score = lc.compute_overall_from_criteria(self._by(default=9, apparel_focus=4))
        self.assertLessEqual(score, 55)
        self.assertNotEqual(lc.band_for_score(score), "fit")

    def test_military_alone_does_not_make_fit_or_maybe(self):
        # тільки military_tactical=10, решта (вкл. apparel) низькі → не проходить
        score = lc.compute_overall_from_criteria(
            self._by(default=2, military_tactical=10)
        )
        self.assertLess(score, 40)
        self.assertEqual(lc.band_for_score(score), "unfit")

    def test_military_tactical_has_no_direct_weight(self):
        # підняття лише military_tactical НЕ змінює score (вага 0 — лише контекст)
        base = lc.compute_overall_from_criteria(self._by(default=6, military_tactical=0))
        hi = lc.compute_overall_from_criteria(self._by(default=6, military_tactical=10))
        self.assertEqual(base, hi)

    def test_normalize_result_ignores_inflated_model_score(self):
        raw = {
            "overall_score": 85,  # модель завищила
            "criteria": [{"key": k, "score": 1, "comment": ""} for k, _ in lc.CRITERIA],
            "verdict_category": "voentorg", "confidence": "high",
        }
        norm = lc.normalize_result(raw)
        self.assertLess(norm["overall_score"], 25)  # усі критерії=1 → низько, не 85
