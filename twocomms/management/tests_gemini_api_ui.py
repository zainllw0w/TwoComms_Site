"""Focused static contracts for the Gemini API health dashboard."""

from pathlib import Path

from django.test import SimpleTestCase


class GeminiApiHealthTemplateContractTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.template = (
            Path(__file__).with_name("templates")
            / "management"
            / "bot.html"
        ).read_text(encoding="utf-8")

    def test_checker_is_admin_only_and_embedded_in_settings(self):
        self.assertIn("{% if bot_is_admin %}", self.template)
        self.assertNotIn('data-tab="api"', self.template)
        self.assertNotIn('data-panel="api"', self.template)
        for element_id in (
            "gemini-health-summary",
            "gemini-health-fallback",
            "gemini-health-keys",
            "gemini-health-feedback",
        ):
            self.assertIn(f'id="{element_id}"', self.template)
        self.assertIn("'API key '+String(index)", self.template)

        settings_start = self.template.index('data-panel="settings"')
        settings_end = self.template.index("</section>", settings_start)
        checker_start = self.template.index('class="bot-card gemini-health-card"')
        self.assertLess(settings_start, checker_start)
        self.assertLess(checker_start, settings_end)
        self.assertIn("function geminiHealthIsActive()", self.template)
        self.assertNotIn("apiIsActive", self.template)

    def test_read_snapshot_is_lazy_manual_and_never_provider_polled(self):
        start = self.template.index("const GeminiHealth=(function(){")
        end = self.template.index("/* ============", start + 32)
        source = self.template[start:end]

        self.assertIn("{% url \"management_bot_gemini_health_api\" %}", source)
        self.assertIn("fetch(healthUrl,{headers:{'X-Requested-With':'XMLHttpRequest'}})", source)
        self.assertIn("document.hidden", source)
        self.assertIn("if(btn.dataset.tab==='settings'&&!loaded.geminiHealth)", self.template)
        self.assertNotIn("setInterval", source)
        self.assertNotIn("setTimeout", source)
        self.assertNotIn("probe_key", source)

    def test_probe_is_an_explicit_click_and_uses_allowlisted_form_fields(self):
        start = self.template.index("const GeminiHealth=(function(){")
        end = self.template.index("/* ============", start + 32)
        source = self.template[start:end]

        self.assertIn("{% url \"management_bot_gemini_health_probe_api\" %}", source)
        self.assertIn("method:'POST'", source)
        self.assertIn("body.append('key_name'", source)
        self.assertIn("body.append('model'", source)
        self.assertIn("probeButton.addEventListener('click'", source)
        self.assertIn("load()", source)
        self.assertNotIn("custom_gemini_key", source)
        self.assertNotIn("provider_body", source)
        self.assertNotIn("token_count", source)

    def test_rows_render_accessible_two_model_rails_and_semantic_states(self):
        start = self.template.index("const GeminiHealth=(function(){")
        end = self.template.index("/* ============", start + 32)
        source = self.template[start:end]

        for contract in (
            "Array.from({length:24}",
            "gemini-3.7-flash",
            "gemini-3.6-flash",
            "aria-label",
            "title=",
            "success",
            "recovered",
            "terminal",
            "no_observation",
            "insufficient_observations",
            "stale",
            "error",
        ):
            self.assertIn(contract, source)
        for legend_label in ("Успішне", "Відновлено", "Помилка", "Немає даних"):
            self.assertIn(legend_label, self.template)

    def test_api_styles_stack_narrow_and_honor_reduced_motion(self):
        for contract in (
            ".gemini-health-row",
            ".gemini-health-rail",
            ".gemini-health-segment",
            "@media(max-width:880px)",
            "@media(max-width:560px)",
            "@media(prefers-reduced-motion:reduce)",
            "min-width:10px",
        ):
            self.assertIn(contract, self.template)

    def test_legacy_api_section_query_opens_settings(self):
        self.assertIn("initialQuery.get('section')==='api'", self.template)
        self.assertIn("initialTab='settings'", self.template)
