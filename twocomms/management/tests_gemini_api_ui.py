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
        self.assertIn("slotOrder.forEach((slotId,index)", self.template)
        self.assertIn("sourceBySlot.get(slotId)", self.template)

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
        self.assertNotIn("seconds_until_next_check", source)
        self.assertNotIn("gemini-health-countdown", self.template)
        self.assertNotIn("setTimeout", source)
        self.assertIn("load({passive:true})", source)
        self.assertNotIn("probe_key", source)

        timer_source = source[source.index("setInterval"):]
        self.assertNotIn("fetch(probeUrl", timer_source)

    def test_automatic_provider_countdown_is_removed(self):
        start = self.template.index("const GeminiHealth=(function(){")
        end = self.template.index("/* ============", start + 32)
        source = self.template[start:end]

        self.assertNotIn("countdownDeadline", source)
        self.assertNotIn("updateCountdown", source)
        self.assertNotIn("next_check_at", source)

    def test_probe_is_an_explicit_click_and_uses_allowlisted_form_fields(self):
        start = self.template.index("const GeminiHealth=(function(){")
        end = self.template.index("/* ============", start + 32)
        source = self.template[start:end]

        self.assertIn("{% url \"management_bot_gemini_health_probe_api\" %}", source)
        self.assertIn("method:'POST'", source)
        self.assertIn("body.append('slot_id'", source)
        self.assertNotIn("GEMINI_API", source)
        self.assertIn("body.append('model'", source)
        self.assertIn("probeButton.addEventListener('click'", source)
        self.assertIn("load()", source)
        self.assertNotIn("custom_gemini_key", source)
        self.assertNotIn("provider_body", source)
        self.assertNotIn("token_count", source)

    def test_rows_render_accessible_four_model_rails_and_semantic_states(self):
        start = self.template.index("const GeminiHealth=(function(){")
        end = self.template.index("/* ============", start + 32)
        source = self.template[start:end]

        for contract in (
            "Array.from({length:24}",
            "gemini-3.7-flash",
            "gemini-3.6-flash",
            "gemini-3.5-flash",
            "gemini-3.5-flash-lite",
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

    def test_api_checker_explains_metadata_ready_and_not_needed_states(self):
        start = self.template.index("const GeminiHealth=(function(){")
        end = self.template.index("/* ============", start + 32)
        source = self.template[start:end]

        self.assertIn("liveStateLabels={LIVE:'LIVE',READY:'ПЕРЕВІРЕНО'", source)
        self.assertIn(
            "not_needed:'Не перевірялась: основний маршрут уже успішний'",
            source,
        )
        self.assertIn(".gemini-health-segment.is-not_needed", self.template)
        self.assertIn(".gemini-health-legend .not-needed", self.template)
        self.assertNotIn("Не перевірялась: 3.7 успішна", self.template)
        self.assertIn("metadata_observations", source)
        self.assertIn(
            "integer(summaryData.observations)+integer(summaryData.metadata_observations)",
            source,
        )

    def test_visible_checker_copy_distinguishes_live_from_verified_metadata(self):
        panel_start = self.template.index('data-panel="api"')
        panel_end = self.template.index("{% endif %}", panel_start)
        panel = self.template[panel_start:panel_end]

        self.assertIn("<strong>LIVE</strong> означає успішну реальну генерацію", panel)
        self.assertIn("Ручна кнопка виконує лише token-free metadata GET", panel)
        self.assertIn("автоматичних provider-перевірок немає", panel)
        self.assertIn("Остання ручна metadata-діагностика", panel)
        self.assertNotIn("Щогодини автоматична перевірка", panel)
        self.assertIn("<span>ПЕРЕВІРЕНО</span>", panel)
        self.assertNotIn("<span>READY</span>", panel)

    def test_checker_shows_saved_manual_batch_completeness(self):
        panel_start = self.template.index('data-panel="api"')
        panel_end = self.template.index("{% endif %}", panel_start)
        panel = self.template[panel_start:panel_end]
        source_start = self.template.index("const GeminiHealth=(function(){")
        source_end = self.template.index("/* ============", source_start + 32)
        source = self.template[source_start:source_end]

        self.assertIn('id="gemini-health-batch"', panel)
        self.assertIn("latest_metadata_batch", source)
        self.assertIn("checked_aliases", source)
        self.assertIn("expected_aliases", source)
        self.assertIn("complete", source)
        self.assertNotIn("hourly batch", source)

    def test_generation_rails_keep_metadata_as_separate_capability_detail(self):
        start = self.template.index("const GeminiHealth=(function(){")
        end = self.template.index("/* ============", start + 32)
        source = self.template[start:end]

        for contract in (
            "function metadataEvidenceText(data)",
            "function renderModel(modelConfig,modelData,keyLabel,metadataData)",
            "const history=Array.isArray(data.history)?data.history:[]",
            "const metadataDetail=metadataEvidenceText(metadataData)",
            "renderModel(model,generation,label,metadata)",
        ):
            self.assertIn(contract, source)
        self.assertNotIn("function mergeEvidence", source)
        self.assertNotIn("return metadataBucket", source)

    def test_fallback_copy_uses_actual_models_and_neutral_timeout_reason(self):
        start = self.template.index("const GeminiHealth=(function(){")
        end = self.template.index("/* ============", start + 32)
        source = self.template[start:end]

        for contract in (
            "'model timeout':'Модель не відповіла вчасно'",
            "const from=models.some(item=>item.id===data.from_model)?data.from_model:''",
            "const to=models.some(item=>item.id===data.to_model)?data.to_model:''",
            "const routeLabel=from&&to?from+' → '+to:'Перемикання моделі'",
        ):
            self.assertIn(contract, source)
        self.assertNotIn("'3.7 timed out'", source)
        self.assertNotIn("?data.from_model:'gemini-3.7-flash'", source)

    def test_snapshot_schema_and_project_slots_are_strict_and_stable(self):
        start = self.template.index("const GeminiHealth=(function(){")
        end = self.template.index("/* ============", start + 32)
        source = self.template[start:end]

        for contract in (
            "const schemaVersion=5",
            "const slotOrder=['gslot_7f3a','gslot_c921','gslot_18de','gslot_a604','gslot_52bb','gslot_e17c']",
            "function normalizeSnapshot(data)",
            "Number(data.schema_version)!==schemaVersion",
            "const bySlot=new Map()",
            "bySlot.has(slotId)",
            "bySlot.size!==slotOrder.length",
            "String(item.display_label||'')!==expectedLabel",
            "const normalized=normalizeSnapshot(data)",
        ):
            self.assertIn(contract, source)
        self.assertNotIn("source[index-1]", source)

    def test_health_route_and_status_dom_use_projected_text_only(self):
        start = self.template.index("const GeminiHealth=(function(){")
        end = self.template.index("/* ============", start + 32)
        source = self.template[start:end]

        self.assertIn("element.textContent=text", source)
        self.assertNotIn("latestRoute.request_id", source)
        self.assertIn("element.textContent=text||''", self.template)
        self.assertIn("esc(it.event)", self.template)
        self.assertIn("esc(it.detail)", self.template)

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
