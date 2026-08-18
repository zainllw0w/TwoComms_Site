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

    def test_api_tab_and_checker_panel_are_admin_only_siblings(self):
        self.assertIn("{% if bot_is_admin %}", self.template)
        self.assertIn('data-tab="api">API</button>', self.template)
        self.assertNotIn('data-tab="api">API-ключі</button>', self.template)
        self.assertIn('data-panel="api"', self.template)
        for element_id in (
            "gemini-health-summary",
            "gemini-health-fallback",
            "gemini-health-keys",
            "gemini-health-feedback",
        ):
            self.assertIn(f'id="{element_id}"', self.template)
        self.assertIn("'API key '+String(index)", self.template)
        self.assertIn("for(let index=1;index<=6;index+=1)", self.template)

        tab_start = self.template.index('data-tab="api"')
        tab_guard_start = self.template.rindex("{% if bot_is_admin %}", 0, tab_start)
        tab_guard_end = self.template.index("{% endif %}", tab_start)
        self.assertLess(tab_guard_start, tab_start)
        self.assertLess(tab_start, tab_guard_end)
        settings_start = self.template.index('data-panel="settings"')
        settings_end = self.template.index("</section>", settings_start)
        panel_start = self.template.index('data-panel="api"')
        panel_guard_start = self.template.rindex("{% if bot_is_admin %}", 0, panel_start)
        panel_guard_end = self.template.index("{% endif %}", panel_start)
        checker_start = self.template.index('class="bot-card gemini-health-card"')
        panel_end = self.template.index("</section>", panel_start)
        self.assertLess(settings_start, settings_end)
        self.assertLess(settings_end, panel_guard_start)
        self.assertLess(panel_guard_start, panel_start)
        self.assertLess(panel_start, checker_start)
        self.assertLess(checker_start, panel_end)
        self.assertLess(panel_end, panel_guard_end)

    def test_read_snapshot_is_api_lazy_passively_refreshed_and_never_provider_polled(self):
        start = self.template.index("const GeminiHealth=(function(){")
        end = self.template.index("/* ============", start + 32)
        source = self.template[start:end]

        self.assertIn("{% url \"management_bot_gemini_health_api\" %}", source)
        self.assertIn("fetch(healthUrl,{headers:{'X-Requested-With':'XMLHttpRequest'}})", source)
        self.assertIn("document.hidden", source)
        self.assertIn("function apiIsActive()", source)
        self.assertIn("active.dataset.tab==='api'", source)
        self.assertIn("if(btn.dataset.tab==='api'&&!loaded.geminiHealth)", self.template)
        self.assertIn("GeminiHealth.syncTimers()", self.template)
        self.assertIn("setInterval", source)
        self.assertIn("60000", source)
        self.assertIn("visibilitychange", source)
        self.assertIn("seconds_until_next_check", source)
        self.assertIn("gemini-health-countdown", self.template)
        self.assertNotIn("setTimeout", source)
        self.assertIn("load({passive:true})", source)
        self.assertNotIn("probe_key", source)

        timer_source = source[source.index("setInterval"):]
        self.assertNotIn("fetch(probeUrl", timer_source)

    def test_countdown_duration_is_pinned_until_the_hourly_deadline_changes(self):
        start = self.template.index("const GeminiHealth=(function(){")
        end = self.template.index("/* ============", start + 32)
        source = self.template[start:end]

        self.assertIn(
            "if(nextDeadline!==countdownDeadline){countdownDeadline=nextDeadline;countdownDueReloadedFor=0;countdownDuration=seconds>0?seconds:3600;}",
            source,
        )
        self.assertNotIn(
            "if(nextDeadline!==countdownDeadline){countdownDeadline=nextDeadline;countdownDueReloadedFor=0;}\n      countdownDuration=seconds>0?seconds:3600;updateCountdown();",
            source,
        )

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
            "not_needed",
            "insufficient_observations",
            "stale",
            "error",
            "data.http_code",
        ):
            self.assertIn(contract, source)
        for legend_label in ("Успішне", "Відновлено", "Помилка", "Немає даних"):
            self.assertIn(legend_label, self.template)

    def test_rails_merge_generation_before_metadata_per_bucket(self):
        start = self.template.index("const GeminiHealth=(function(){")
        end = self.template.index("/* ============", start + 32)
        source = self.template[start:end]

        for contract in (
            "function mergeEvidence(generation,metadata)",
            "const mergedHistory=Array.from({length:24}",
            "const generationStatus=normalizeObservation(generationBucket.status)",
            "if(generationStatus!=='no_observation')",
            "const metadataStatus=normalizeObservation(metadataBucket.status)",
            "if(metadataStatus!=='no_observation')",
            "return metadataBucket;",
            "history:mergedHistory",
            "const evidenceData=mergeEvidence(generation,metadata)",
        ):
            self.assertIn(contract, source)
        self.assertLess(
            source.index("if(generationStatus!=='no_observation')"),
            source.index("if(metadataStatus!=='no_observation')"),
        )

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

    def test_api_rows_keep_fixed_rail_statistics_columns(self):
        for contract in (
            "--gemini-health-meta-width:320px",
            "grid-template-columns:34px minmax(0,1fr) var(--gemini-health-meta-width)",
            "min-height:32px",
            "text-overflow:ellipsis",
            "gemini-health-model-detail",
            "--gemini-health-meta-width:clamp(190px,28vw,320px)",
        ):
            self.assertIn(contract, self.template)
        self.assertNotIn("minmax(124px,auto)", self.template)

    def test_api_rails_reflow_before_the_medium_width_grid_can_clip_them(self):
        for contract in (
            "@media(max-width:1280px)",
            ".gemini-health-models{grid-column:1/-1;grid-row:2;}",
            "@media(max-width:640px)",
            ".gemini-health-rail-scroll{overflow-x:auto;padding-bottom:3px;}",
        ):
            self.assertIn(contract, self.template)

    def test_api_section_query_opens_the_api_tab(self):
        self.assertIn(
            "if(initialQuery.get('section')==='api') initialTab='api';",
            self.template,
        )
        self.assertNotIn("if(initialTab==='api'", self.template)
