"""Тести Phase 3 / Task 13 — вкладка «Клиенти» (CRM IG-клієнтів).

JSON-API списку карток і детальної (переписка, кружечки воронки, summary,
угоди, замовлення). Доступ лише адмінам.
"""
from decimal import Decimal
from datetime import timedelta
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import uuid

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from management.models import (
    IgClient,
    IgConversationAnalysisSnapshot,
    InstagramBotLog,
    InstagramBotMessage,
)
from management.ig_bot_models import (
    IgDeal,
    IgOrderAttribution,
    IgPaymentConfirmationReview,
    IgPaymentProjection,
    IgPaymentReviewDecision,
    IgPostSaleCase,
)
from management.bot_access import META_REVIEWER_GROUP_NAME
from management.bot_views import _group_signal_rows, _review_media_groups

User = get_user_model()

MGMT = override_settings(
    ROOT_URLCONF="twocomms.urls_management",
    SECURE_SSL_REDIRECT=False,
)


class ClientWorkspaceTemplateContractTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.template = (
            Path(__file__).with_name("templates") / "management" / "bot.html"
        ).read_text(encoding="utf-8")

    def test_orders_is_a_dedicated_tab_after_statistics_not_an_overview_card(self):
        self.assertIn('data-tab="orders"', self.template)
        self.assertIn('id="badge-orders-action"', self.template)
        self.assertIn('data-panel="orders"', self.template)
        self.assertLess(
            self.template.index('data-tab="stats"'),
            self.template.index('data-tab="orders"'),
        )

    def test_clients_workspace_has_bounded_pagination_controls(self):
        for contract in (
            'id="bot-clients-pager"',
            'id="bot-clients-prev"',
            'id="bot-clients-page-label"',
            'id="bot-clients-next"',
            "params.set('page', String(currentPage))",
            "currentPage=1;load(searchEl.value.trim())",
            "currentView=btn.getAttribute('data-client-view')||'all';currentPage=1",
        ):
            self.assertIn(contract, self.template)

        self.assertIn("'Показано '+pageInfo.start_item+'–'+pageInfo.end_item+' з '+pageInfo.total_items", self.template)

    def test_client_context_is_a_third_desktop_column_and_a_small_screen_drawer(self):
        for contract in (
            "grid-template-columns:minmax(260px,320px) minmax(0,1fr) minmax(300px,380px)",
            'class="bot-client-context-shell"',
            "window.matchMedia('(min-width:1201px)')",
            "desktopContext.matches",
            "contextShell.scrollIntoView({block:'nearest'})",
        ):
            self.assertIn(contract, self.template)

    def test_client_context_gear_is_a_reversible_desktop_toggle(self):
        for contract in (
            "ClientContextDrawer.toggle(advanced)",
            "data-context-open",
            "localStorage.getItem('twocomms.bot.context.open')",
            "localStorage.setItem('twocomms.bot.context.open'",
            "advanced.setAttribute('aria-expanded'",
            ".bot-clients-workspace[data-context-open=\"false\"]",
        ):
            self.assertIn(contract, self.template)

    def test_client_context_toggle_keeps_mobile_drawer_semantics(self):
        for contract in (
            "desktopContext.matches",
            "panel.setAttribute('role','dialog')",
            "panel.setAttribute('aria-modal','true')",
            "document.body.classList.add('bot-client-context-open')",
            "document.body.classList.remove('bot-client-context-open')",
        ):
            self.assertIn(contract, self.template)

    def test_client_workspace_stretches_all_desktop_panes_to_one_rhythm(self):
        for contract in (
            ".bot-clients-workspace{display:grid;",
            "align-items:stretch;",
            "height:clamp(620px,calc(100vh - 24px),760px);",
            ".bot-clients-sidebar{padding:12px;position:sticky;top:12px;display:flex;flex-direction:column;}",
            ".bot-clients-list{max-height:none;min-height:0;flex:1;",
        ):
            self.assertIn(contract, self.template)

    def test_client_context_toggle_state_stays_in_sync_when_other_drawers_open(self):
        for contract in (
            "data-client-context-toggle",
            "function syncToggleControls()",
            "ClientContextDrawer.close(null,{persist:false,restoreFocus:false})",
            "function close(trigger,{persist=true,restoreFocus=true}={})",
        ):
            self.assertIn(contract, self.template)

    def test_mobile_client_drawer_raises_its_owning_workspace_above_global_header(self):
        for contract in (
            ".management-body.bot-client-context-open .workspace{z-index:41}",
            "document.body.classList.add('bot-client-context-open')",
            "document.body.classList.remove('bot-client-context-open')",
        ):
            self.assertIn(contract, self.template)

    def test_destructive_actions_require_confirmation_and_report_failures(self):
        for contract in (
            "Зупинити відповіді бота для всіх клієнтів?",
            "Приховати цього клієнта з активної черги",
            "Позначити цього клієнта як втраченого",
            "Видалити цю інструкцію без можливості відновлення?",
            'id="bot-global-feedback"',
            'id="bot-kb-feedback"',
            "if(!response.ok||!data.success)throw new Error",
        ):
            self.assertIn(contract, self.template)

        self.assertNotIn(".catch(()=>{})", self.template)

    def test_relative_time_distinguishes_future_and_overdue_followups(self):
        for contract in (
            "function relativeTime(iso,{due=false}={})",
            "Прострочено на ",
            "Через ",
            "relativeTime(c.next_followup_at,{due:true})",
            "relativeTime(item.due_at,{due:true})",
            "bot-time-overdue",
        ):
            self.assertIn(contract, self.template)

    def test_stats_keep_zero_stages_define_metrics_and_use_accessible_main_tabs(self):
        for contract in (
            'id="bot-tabs" role="tablist"',
            'class="bot-tab active" role="tab" aria-selected="true"',
            "t.setAttribute('aria-selected',t===btn?'true':'false')",
            "const funnel=funnelOrder.map(key=>",
            "unverified:'Оплату ще не підтверджено'",
            "spam:'Спам'",
            "cold:'Неактивні'",
            "function stat(k,v,help)",
            "title=\"'+esc(help)+'\"",
            "value===0?0:(value||'')",
        ):
            self.assertIn(contract, self.template)

    def test_payment_reconciliation_exposes_all_bounded_amount_evidence_links(self):
        self.assertIn("evidenceIds.slice(0,6).forEach", self.template)
        self.assertIn("managerEvidenceIds.slice(0,6).forEach", self.template)
        self.assertNotIn('id="bot-payment-review"', self.template)
        self.assertNotIn('id="bot-payment-review-list"', self.template)

    def test_amount_evidence_links_never_fall_back_to_receipt_watermark(self):
        self.assertNotIn(
            "[decision.evidence_watermark_message_id].filter(Boolean)",
            self.template,
        )
        self.assertIn("Суми, знайдені у переписці", self.template)
        self.assertIn("amount_evidence.forEach", self.template)

    def test_orders_workspace_has_semantic_filters_list_and_contextual_drawer(self):
        for contract in (
            'id="bot-orders-filters"',
            'data-orders-view="action"',
            'data-orders-view="confirmed"',
            'data-orders-view="all"',
            'id="bot-orders-list"',
            'id="bot-orders-detail"',
            'role="tablist"',
            'aria-label="Фільтр замовлень"',
            'aria-live="polite"',
            'management_bot_orders_workspace_api',
        ):
            self.assertIn(contract, self.template)

    def test_client_workspace_exposes_all_non_hidden_conversations_separately(self):
        self.assertIn('data-client-view="active">Активні', self.template)
        self.assertIn('class="bot-mini-btn active" data-client-view="all">Усі', self.template)
        self.assertIn('data-client-view="hidden">Приховані', self.template)
        self.assertIn("let currentView='all';", self.template)

    def test_client_filters_use_three_primary_choices_and_an_accessible_disclosure(self):
        self.assertIn('class="bot-client-filter-primary"', self.template)
        self.assertIn('class="bot-client-filter-disclosure"', self.template)
        primary_start = self.template.index('class="bot-client-filter-primary"')
        primary_end = self.template.index('class="bot-client-filter-disclosure"')
        primary_markup = self.template[primary_start:primary_end]
        for value in ("all", "active", "paid"):
            self.assertIn(f'data-client-view="{value}"', primary_markup)
        for value in (
            "due",
            "delivery-blocked",
            "hidden",
            "spam-cold",
            "ads",
            "complaints",
            "wholesale",
            "collaboration",
            "reactions",
        ):
            self.assertNotIn(f'data-client-view="{value}"', primary_markup)
            self.assertIn(f'data-client-view="{value}"', self.template)

        for contract in (
            'id="bot-client-filter-toggle"',
            'aria-expanded="false"',
            'aria-controls="bot-client-filter-advanced"',
            'id="bot-client-filter-advanced"',
            'id="bot-client-filter-active-label"',
            "function setAdvancedFiltersOpen(open,{restoreFocus=false}={})",
            "event.key!=='Escape'",
            "!filtersEl.contains(event.target)",
            "syncFilterDisclosure(btn)",
            ".bot-client-filter-primary{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));",
        ):
            self.assertIn(contract, self.template)

    def test_dialog_actions_use_one_primary_and_three_stable_secondary_cells(self):
        for contract in (
            ".bot-action-primary>.bot-client-action{width:100%;",
            ".bot-action-state-buttons{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));",
            ".bot-client-action.pause{background:#4a3512;",
            ".bot-client-action.lost{background:#2c1519;",
            "c.bot_paused?'▶ Відновити':'⏸ Зупинити'",
            "c.hidden?'↩ Повернути':'Приховати'",
            "node('button','bot-client-action lost','Втрачено')",
            "node('button','bot-client-action reset','Скинути')",
            "lost.setAttribute('aria-label','Позначити клієнта як втрачено')",
            "reset.setAttribute('aria-label','Скинути воронку')",
        ):
            self.assertIn(contract, self.template)

    def test_client_rows_render_the_server_commercial_visual_state_without_replacing_actions(self):
        for contract in (
            ".bot-client-row.commercial-paid:not(.needs-action):not(.post-sale-action)",
            ".bot-client-row.commercial-shipped:not(.needs-action):not(.post-sale-action)",
            "c.commercial_visual_state",
            "c.commercial_visual_state_label",
            "bot-commercial-badge",
        ):
            self.assertIn(contract, self.template)
        self.assertIn("row.addEventListener('keydown'", self.template)

    def test_status_ui_distinguishes_daemon_liveness_from_broken_ingress(self):
        self.assertIn("st.state==='ingress_degraded'", self.template)
        self.assertIn("Прийом повідомлень порушено", self.template)
        self.assertIn("Процес працює, але нові повідомлення не надходять", self.template)

    def test_live_chat_applies_incremental_stage_and_funnel_updates(self):
        self.assertIn('"funnel": _funnel_progress_for_stage(c, operational_stage)', Path(__file__).with_name("bot_views.py").read_text(encoding="utf-8"))
        self.assertIn("function applyIncrementalConversationState(d)", self.template)
        self.assertIn("applyIncrementalConversationState(d)", self.template)

    def test_evidence_link_auto_pages_bounded_history_without_reversing_rows(self):
        self.assertIn("async function revealRequestedMessage", self.template)
        self.assertIn("while(!evidence&&convHasOlder&&pages<20)", self.template)
        self.assertIn("Повідомлення #'+target+' не знайдено", self.template)
        self.assertIn("(d.messages||[]).forEach(m=>", self.template)
        self.assertNotIn("(d.messages||[]).slice().reverse().forEach(m=>", self.template)

    def test_order_resolution_actions_are_explicit_and_rejection_has_reason(self):
        for visible_copy in (
            "Прив'язати існуюче",
            "Створити нове",
            "Причина відхилення",
            "Підтвердити оплату",
            "Відхилити",
        ):
            self.assertIn(visible_copy, self.template)
        self.assertIn("body.append('action','manager_reject')", self.template)
        self.assertIn("body.append('reason_code'", self.template)
        self.assertIn("body.append('reason_text'", self.template)
        self.assertNotIn("if(action==='confirm'&&result.data.order_url)", self.template)

    def test_manager_confirmation_posts_exact_amount_and_shows_money_breakdown(self):
        self.assertIn("Сума, яку фактично перевірив менеджер", self.template)
        self.assertIn("confirmed_amount", self.template)
        self.assertIn("До сплати", self.template)
        self.assertIn("Сума до знижки", self.template)
        self.assertIn("Знижка", self.template)
        self.assertIn("Запитано зараз", self.template)
        self.assertIn("Підтверджено отримано", self.template)
        self.assertIn("Залишок", self.template)
        self.assertIn("Суми Monobank і менеджера не збігаються", self.template)
        self.assertIn("Виконання та прив’язка заблоковані до звірки", self.template)
        self.assertIn("reconciliation.setAttribute('role','alert')", self.template)
        self.assertIn("reconciliation.setAttribute('aria-live','assertive')", self.template)
        self.assertIn("const canResolveOrder=!payment.needs_reconciliation", self.template)
        self.assertIn("displayedOrderTotal!=='—'?displayedOrderTotal+' грн':'—'", self.template)
        self.assertIn("function reconciliationMessage(payment)", self.template)
        self.assertIn("Monobank зафіксував часткове повернення", self.template)
        self.assertIn("Уточнити підтверджену суму", self.template)
        self.assertIn("action:'clarify_amount'", self.template)

    def test_provider_truth_copy_cannot_read_like_the_manager_rejected_payment(self):
        self.assertIn("Monobank не підтвердив оплату", self.template)
        self.assertIn("Monobank ще не підтвердив оплату", self.template)

    def test_order_detail_explains_the_post_confirmation_next_step(self):
        for contract in (
            "bot-order-progress",
            "Перевірка оплати",
            "Прив’язка замовлення",
            "Виконання",
            "Оплату підтверджено — тепер оберіть існуюче замовлення або створіть нове.",
        ):
            self.assertIn(contract, self.template)
        self.assertIn("renderOrderProgress(inner,item)", self.template)
        self.assertIn(
            "if(state==='needs_order_resolution'&&canResolveOrder)renderActions(inner,item,options||{})",
            self.template,
        )
        self.assertIn(
            "if(state!=='needs_order_resolution'&&state!=='payment_reconciliation')renderActions(inner,item,options||{})",
            self.template,
        )

    def test_payment_drawer_escapes_the_management_workspace_stacking_context(self):
        self.assertIn(".bot-drawer,.bot-drawer *{box-sizing:border-box;}", self.template)
        self.assertIn("document.body.appendChild(drawer)", self.template)

    def test_client_workspace_has_action_cta_order_history_and_collapsible_signals(self):
        for contract in (
            "bot-client-order-action",
            "bot-client-orders",
            "bot-analysis-disclosure",
            "Потрібно підтвердити оплату",
            "Потрібно прив'язати замовлення",
            "Історія замовлень",
            "Відкрити замовлення",
        ):
            self.assertIn(contract, self.template)
        self.assertIn("PaymentReviewDrawer.open", self.template)
        self.assertNotIn("Категорія діалогу</div><div class=\"bot-category-value\"", self.template)

    def test_client_workspace_has_audited_order_assignment_controls(self):
        for contract in (
            "Прив\\'язка замовлень",
            "Точний номер існуючого замовлення",
            "management_bot_client_order_link_api",
            "management_bot_client_order_unlink_api",
            "bot-assignment-unlink",
            "Вкажіть причину, щоб зберегти аудит.",
            "submit.disabled=!reason.value.trim()",
            "manual_order_url",
            "assignment_history",
        ):
            self.assertIn(contract, self.template)
        self.assertNotIn("window.prompt('Причина відв'язки", self.template)

    def test_assignment_action_opens_a_dedicated_searchable_order_drawer(self):
        for contract in (
            'id="bot-assignment-drawer"',
            "OrderAssignmentDrawer",
            "renderAssignmentPicker",
            "Пошук за номером, клієнтом, телефоном, товаром або ТТН",
            "Оберіть замовлення зі списку або вставте точний номер вручну",
            "orderCandidatesBase",
            "candidate.selectable",
            "candidate.blocked_reason_label",
            "limit:'40'",
            "setAttribute('aria-disabled',candidate.selectable?'false':'true')",
            "candidates.setAttribute('aria-busy','true')",
            "const optionRows=()=>Array.from(candidates.querySelectorAll('[role=\"option\"]'))",
            "function restoreDrawerFocus()",
            ".bot-drawer .bot-assignment-picker .bot-order-candidates{margin-top:0;max-height:360px;overflow-y:auto",
        ):
            self.assertIn(contract, self.template)
        self.assertIn(
            "assignmentAction.addEventListener('click',()=>OrderAssignmentDrawer.open(d,assignmentAction))",
            self.template,
        )
        self.assertNotIn(
            "assignmentAction.addEventListener('click',()=>ClientContextDrawer.open(assignmentAction))",
            self.template,
        )
        self.assertIn(
            "renderAssignments(contextEl,d,id,{interactive:false})",
            self.template,
        )

    def test_client_workspace_exposes_post_sale_state_and_drawer_controls(self):
        for contract in (
            "bot-post-sale-strip",
            "bot-post-sale-card",
            "Обмін / повернення",
            "Початковий розмір",
            "Бажаний розмір",
            "Пов’язане замовлення",
            "Зберегти звернення",
            "postSale.order_choices",
            "caseItem.action_url",
        ):
            self.assertIn(contract, self.template)

    def test_client_list_and_stats_expose_post_sale_and_custom_date_controls(self):
        for contract in (
            "post-sale-action",
            "post_sale_type_label",
            'id="bot-stats-date-from"',
            'id="bot-stats-date-to"',
            'id="bot-stats-apply-range"',
        ):
            self.assertIn(contract, self.template)

    def test_stats_default_to_seven_days(self):
        self.assertIn(
            'class="bot-mini-btn active" data-stats-days="7">7 днів',
            self.template,
        )
        self.assertIn("let rangeDays=7;", self.template)
        self.assertNotIn(
            'class="bot-mini-btn active" data-stats-days="30">30 днів',
            self.template,
        )

    def test_client_workspace_exposes_confirmed_funnel_reset(self):
        self.assertIn("Скинути воронку", self.template)
        self.assertIn("data-act='reset-funnel'", self.template)
        self.assertIn("reset_funnel_confirmation", self.template)
        self.assertIn("confirm_reset", self.template)

    def test_client_workspace_has_two_primary_panes_and_context_drawer(self):
        for contract in (
            'class="bot-clients-workspace"',
            'class="bot-clients-sidebar"',
            'id="bot-client-conversation"',
            'id="bot-client-context"',
            'id="bot-client-drawer"',
            'id="bot-client-mobile-nav"',
            'data-client-pane="list"',
            'data-client-pane="conversation"',
            'aria-controls="bot-clients-list"',
            'aria-controls="bot-client-conversation"',
        ):
            self.assertIn(contract, self.template)
        self.assertNotIn('data-client-pane="context"', self.template)
        self.assertNotIn('aria-controls="bot-client-context"', self.template)
        self.assertNotIn(".bot-client-detail{max-height:560px;overflow-y:auto", self.template)

    def test_payment_review_uses_contextual_accessible_drawer(self):
        for contract in (
            'id="bot-payment-drawer"',
            'role="dialog"',
            'aria-modal="true"',
            'id="bot-payment-drawer-close"',
            "function restoreDrawerFocus",
            "event.key==='Escape'",
            "trapDrawerFocus",
        ):
            self.assertIn(contract, self.template)

    def test_drawer_focus_trap_wraps_from_the_dialog_panel_itself(self):
        self.assertIn(
            "document.activeElement===panel||!panel.contains(document.activeElement)",
            self.template,
        )
        self.assertIn("(event.shiftKey?last:first).focus()", self.template)
        self.assertIn("body.querySelector('[data-review-autofocus]')", self.template)
        self.assertIn("target.scrollIntoView({block:'center'})", self.template)

    def test_drawer_opens_on_the_current_action_instead_of_hiding_it_below_mobile_fold(self):
        self.assertIn("function focusDrawerAction()", self.template)
        self.assertEqual(self.template.count("requestAnimationFrame(focusDrawerAction)"), 2)

    def test_drawer_and_workspace_controls_have_unique_ids(self):
        self.assertIn(
            "const scopeId='bot-verification-scope-'+item.review_id+(options&&options.drawer?'-drawer':'-workspace')",
            self.template,
        )
        self.assertIn("scopeLabel.htmlFor=scopeId", self.template)
        self.assertIn("scope.id=scopeId", self.template)

    def test_successful_payment_action_refreshes_the_open_client_context(self):
        self.assertIn("async function refreshClient(id)", self.template)
        self.assertIn("await Clients.refreshClient((item.client||{}).id)", self.template)
        self.assertIn(
            "return {load:load,detail:detail,refreshClient:refreshClient}",
            self.template,
        )

    def test_post_mutation_refresh_failure_uses_server_response_not_stale_card(self):
        for contract in (
            "function applyMutationResult(item,data)",
            "const optimistic=applyMutationResult(item,data)",
            "await load({throwOnError:true})",
            "Дію збережено, але свіжі дані не завантажилися.",
        ):
            self.assertIn(contract, self.template)
        self.assertIn("if(options&&options.throwOnError)throw error", self.template)

    def test_workspace_payment_confirmation_focuses_the_new_order_resolution_action(self):
        self.assertIn("function focusWorkspaceAction(item)", self.template)
        self.assertIn(
            "PaymentReviewDrawer.currentReviewId()===Number(item.review_id)",
            self.template,
        )
        self.assertIn(
            "detailEl.querySelector('[data-review-autofocus]')",
            self.template,
        )
        self.assertIn("target.scrollIntoView({block:'center'})", self.template)
        self.assertGreaterEqual(
            self.template.count("requestAnimationFrame(()=>focusWorkspaceAction("),
            3,
        )

    def test_drawer_restore_focus_has_a_stable_client_fallback_after_refresh(self):
        self.assertIn("document.querySelector('.bot-client-row.active')", self.template)
        self.assertNotIn("document.querySelector('[data-client-pane=\"context\"]')", self.template)
        self.assertIn(".find(candidate=>candidate&&candidate.offsetParent!==null)", self.template)
        self.assertIn("function restoreDrawerFocus()", self.template)

    def test_chat_header_shows_potential_and_factual_truth_separately(self):
        """IMP-019 осознанно заменил подпись «ймовірність».

        Контракт теста — «прогноз и факт показаны раздельно» — сохранён и усилен:
        прогноз теперь подписан тем, чем он является («намір купити зараз»), а
        факт покупки получил собственный бейдж. Прежняя безымянная «ймовірність»
        и была первопричиной жалобы заказчика: у оплатившего клиента она
        читалась как «0% — не купит» (F-SCORE-001, DR-002).
        """
        for contract in (
            "bot-potential-strip",
            "намір купити зараз",
            "bot-buyer-badge",
            "впевненість",
            "На чому базується",
            "Monobank: ",
            "Менеджер: ",
            "Фізичних замовлень: ",
        ):
            self.assertIn(contract, self.template)
        self.assertIn("const p=d.potential||{}", self.template)
        self.assertNotIn("p.factual_payment", self.template)
        self.assertNotIn("p.factual_order_count", self.template)
        self.assertNotIn("'ймовірність'", self.template)

    def test_existing_order_resolution_uses_searchable_cards_and_structured_override(self):
        for contract in (
            "management_bot_order_candidates_api",
            "review_id",
            "override_code",
            "override_reason",
            "historical_fulfilled_order",
            "payment_state_mismatch",
            "historical_import",
        ):
            self.assertIn(contract, self.template)
        self.assertNotIn(
            "postReview(item,'link_order',{order_identifier:value,override_reason:override.value}",
            self.template,
        )

    def test_drawer_keeps_receipts_and_bottom_actions_reachable(self):
        for contract in (
            "height:100dvh",
            "max-height:100dvh",
            "overflow-y:auto",
            "overscroll-behavior:contain",
            ".bot-drawer .bot-order-candidates{max-height:none;overflow:visible;}",
            ".bot-drawer .bot-order-actions.is-sticky{position:sticky;bottom:0",
        ):
            self.assertIn(contract, self.template)
        self.assertNotIn(".bot-drawer .bot-order-actions.is-sticky{bottom:-", self.template)

    def test_orders_load_ignores_stale_responses_after_a_newer_filter_request(self):
        self.assertIn("let loadGeneration=0", self.template)
        self.assertIn("const requestGeneration=++loadGeneration", self.template)
        self.assertIn("if(requestGeneration!==loadGeneration)return false", self.template)

    def test_orders_workspace_deduplicates_rows_for_one_canonical_order(self):
        self.assertIn("const seenOrderIds=new Set()", self.template)
        self.assertIn("if(orderId&&seenOrderIds.has(orderId))return", self.template)
        self.assertIn("if(orderId)seenOrderIds.add(orderId)", self.template)

    def test_payment_truth_and_verification_scope_are_not_visually_collapsed(self):
        for visible_copy in (
            "Оплата через Monobank",
            "Перевірка менеджера",
            "Що підтверджено",
            "Повна оплата",
            "Передоплата",
            "Заявлений платіж",
        ):
            self.assertIn(visible_copy, self.template)
        self.assertNotIn("Provider payment", self.template)
        self.assertNotIn("Обсяг підтвердження", self.template)
        for technical_copy in (
            "Provider: ",
            "provider не підтверджено",
            "Provider скасував",
            "статус provider",
            "provider-даних",
            "Структурована причина override",
            "Обов’язкове пояснення для override",
            "Пояснення override",
            "Override не потрібен",
            "Додайте пояснення до override",
            "audited fallback",
            "Бар'єр відповідей",
        ):
            self.assertNotIn(technical_copy, self.template)
        self.assertIn("verification_scope", self.template)
        self.assertIn("managerTruthLabel", self.template)
        self.assertIn("providerTruthLabel", self.template)
        self.assertIn(
            "[['','Оберіть, що підтверджено'],['full_payment','Повна оплата'],['prepayment','Передоплата']]",
            self.template,
        )
        self.assertNotIn(
            "['prepayment','Передоплата'],['payment_claim','Заявлений платіж']",
            self.template,
        )

    def test_linked_order_is_persistent_in_chat_without_reopening_payment_action(self):
        for contract in (
            "function renderLinkedOrderStrip(d)",
            "const linkedOrders=((d.orders&&d.orders.items)||[])",
            "Оплату підтверджено менеджером",
            "Відкрити замовлення",
            "renderLinkedOrderStrip(d)",
        ):
            self.assertIn(contract, self.template)
        self.assertIn(
            "if(active&&active.approval&&active.approval.needs_action)",
            self.template,
        )

    def test_client_first_viewport_includes_fulfillment_and_next_action(self):
        self.assertIn("Стан виконання", self.template)
        self.assertIn("Наступна дія", self.template)
        self.assertIn("fulfillmentLabel", self.template)

    def test_order_lines_include_selected_variant_and_origin(self):
        self.assertIn("optionValues", self.template)
        self.assertIn("Походження замовлення", self.template)
        self.assertIn("Джерело оплати", self.template)

    def test_client_order_history_counts_only_real_linked_orders(self):
        self.assertIn(
            "const linked=((d.orders&&d.orders.items)||[]).filter(item=>item&&item.order&&item.order.id);",
            self.template,
        )
        self.assertIn("const seenOrderIds=new Set()", self.template)
        self.assertIn("if(seenOrderIds.has(orderId))return false", self.template)
        self.assertIn("section(root,'Історія замовлень',orders.length)", self.template)
        self.assertNotIn("esc(rows.length)", self.template)

    def test_escape_does_not_discard_an_order_form_while_editing(self):
        self.assertIn(
            "event.target.closest('input,select,textarea')",
            self.template,
        )

    def test_order_resolution_copy_is_consistently_ukrainian(self):
        self.assertIn("Нове замовлення не створюється автоматично", self.template)
        self.assertNotIn("Новий заказ", self.template)

    def test_workspace_has_reduced_motion_and_target_responsive_breakpoints(self):
        self.assertIn("@media(prefers-reduced-motion:reduce)", self.template)
        for width in (880, 560, 390, 320):
            self.assertIn(f"@media(max-width:{width}px)", self.template)
        self.assertIn("overflow-x:hidden", self.template)
        self.assertIn(".bot-orders-detail{", self.template)
        self.assertIn("overflow:visible", self.template)
        self.assertNotIn(".bot-orders-detail{position:relative;min-width:0;background:#0a0e15;border:1px solid #1e2736;border-radius:16px;padding:18px;min-height:620px;overflow:hidden;}", self.template)

    def test_mobile_orders_workspace_uses_one_page_scroll_without_nested_list_scroll(self):
        self.assertIn(
            ".bot-orders-list{max-height:none;overflow:visible}",
            self.template,
        )
        self.assertNotIn(
            ".bot-orders-list{max-height:340px}",
            self.template,
        )


class FunnelProgressTests(TestCase):
    def test_progress_marks_done_up_to_current(self):
        c = IgClient.get_or_create_for_sender("p1")
        c.set_stage(IgClient.Stage.CHECKOUT)
        by = {p["stage"]: p for p in c.funnel_progress()}
        self.assertTrue(by["new"]["done"])
        self.assertTrue(by["checkout"]["done"])
        self.assertTrue(by["checkout"]["current"])
        self.assertFalse(by["paid"]["done"])


class SignalGroupingTests(SimpleTestCase):
    def test_grouping_keeps_latest_event_and_hides_duplicate_rows(self):
        grouped = _group_signal_rows([
            {
                "type": "size_concern",
                "value": "S",
                "confidence": "0.80",
                "time": "2026-07-24T10:00:00+03:00",
            },
            {
                "type": "size_concern",
                "value": "M",
                "confidence": "0.95",
                "time": "2026-07-24T10:05:00+03:00",
            },
            {
                "type": "checkout_started",
                "value": "",
                "confidence": "0.90",
                "time": "2026-07-24T10:04:00+03:00",
            },
        ])

        self.assertEqual([row["type"] for row in grouped], ["size_concern", "checkout_started"])
        self.assertEqual(grouped[0]["count"], 2)
        self.assertEqual(grouped[0]["latest_value"], "M")
        self.assertEqual(grouped[0]["latest_time"], "2026-07-24T10:05:00+03:00")
        self.assertEqual(grouped[0]["type_label"], "Розмір")

    def test_media_grouping_has_a_bounded_source_scan(self):
        media = [{"role": "unknown", "url": f"https://cdn.example/{idx}.jpg"} for idx in range(1000)]
        media.append({"role": "receipt", "url": "https://cdn.example/late-receipt.jpg"})

        grouped = _review_media_groups({"media": media})

        self.assertEqual(len(grouped["unknown"]), 20)
        self.assertEqual(grouped["receipts"], [])


@MGMT
class ClientsApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("adm", password="x", is_staff=True)
        self.client.force_login(self.admin)
        self.c = IgClient.get_or_create_for_sender("igX")
        self.c.display_name = "Іван"
        self.c.save()
        InstagramBotMessage.objects.create(
            sender_id="igX", client=self.c, role="user", text="привіт"
        )

    def test_clients_list(self):
        r = self.client.get(reverse("management_bot_clients_api"))
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data["success"])
        self.assertTrue(any(cl["name"] == "Іван" for cl in data["clients"]))

    def test_clients_list_is_paginated_without_overlap_and_reports_real_range(self):
        IgClient.objects.bulk_create([
            IgClient(igsid=f"ig-page-{index:03d}")
            for index in range(205)
        ])

        first = self.client.get(reverse("management_bot_clients_api")).json()
        second = self.client.get(
            reverse("management_bot_clients_api"), {"page": 2}
        ).json()

        self.assertEqual(len(first["clients"]), 100)
        self.assertEqual(first["total"], 206)
        self.assertEqual(first["pagination"], {
            "page": 1,
            "page_size": 100,
            "total_items": 206,
            "total_pages": 3,
            "start_item": 1,
            "end_item": 100,
            "has_previous": False,
            "has_next": True,
        })
        self.assertEqual(len(second["clients"]), 100)
        self.assertEqual(second["pagination"]["start_item"], 101)
        self.assertEqual(second["pagination"]["end_item"], 200)
        self.assertTrue(second["pagination"]["has_previous"])
        self.assertTrue(second["pagination"]["has_next"])
        self.assertFalse(
            {row["id"] for row in first["clients"]}
            & {row["id"] for row in second["clients"]}
        )

    def test_clients_list_clamps_invalid_page_and_page_size(self):
        IgClient.objects.bulk_create([
            IgClient(igsid=f"ig-clamp-{index:03d}")
            for index in range(45)
        ])

        response = self.client.get(
            reverse("management_bot_clients_api"),
            {"page": 999, "page_size": 20},
        ).json()
        invalid = self.client.get(
            reverse("management_bot_clients_api"),
            {"page": "broken", "page_size": "broken"},
        ).json()

        self.assertEqual(len(response["clients"]), 6)
        self.assertEqual(response["pagination"]["page"], 3)
        self.assertEqual(response["pagination"]["start_item"], 41)
        self.assertEqual(response["pagination"]["end_item"], 46)
        self.assertFalse(response["pagination"]["has_next"])
        self.assertEqual(invalid["pagination"]["page"], 1)
        self.assertEqual(invalid["pagination"]["page_size"], 100)

    @override_settings(SITE_BASE_URL="https://shop.example.test")
    def test_client_detail_uses_storefront_urlconf_for_signed_manual_order(self):
        response = self.client.get(
            reverse("management_bot_client_detail_api", args=[self.c.pk])
        )

        self.assertEqual(response.status_code, 200, response.content)
        manual_order_url = response.json()["orders"]["manual_order_url"]
        self.assertTrue(
            manual_order_url.startswith(
                "https://shop.example.test/admin-panel/orders/manual/create/?"
            ),
            manual_order_url,
        )
        self.assertIn(f"ig_client={self.c.pk}", manual_order_url)
        self.assertIn("ig_client_token=", manual_order_url)

    def analysis(self, client, interaction_type, *, key):
        return IgConversationAnalysisSnapshot.objects.create(
            client=client,
            dedupe_key=key,
            score_band=IgConversationAnalysisSnapshot.Band.EXPLORING,
            interaction_type=interaction_type,
            analysis_model="rules",
            rules_version="ui-test",
        )

    def test_clients_show_localized_latest_interaction_and_category_filter(self):
        self.analysis(
            self.c,
            IgConversationAnalysisSnapshot.InteractionType.SUPPORT_COMPLAINT,
            key="ui-support",
        )
        other = IgClient.get_or_create_for_sender("ig-info")
        self.analysis(
            other,
            IgConversationAnalysisSnapshot.InteractionType.INFORMATION_ONLY,
            key="ui-info",
        )

        data = self.client.get(reverse("management_bot_clients_api") + "?view=complaints").json()

        self.assertEqual(data["total"], 1)
        row = data["clients"][0]
        self.assertEqual(row["id"], self.c.id)
        self.assertEqual(row["interaction_type"], "support_complaint")
        self.assertEqual(row["interaction_type_label"], "Підтримка / скарга")
        self.assertEqual(row["interaction_tone"], "support")
        self.assertEqual(row["analysis_band_label"], "Вивчає")

    def test_category_filter_uses_latest_snapshot_and_excludes_hidden(self):
        self.analysis(
            self.c,
            IgConversationAnalysisSnapshot.InteractionType.SUPPORT_COMPLAINT,
            key="ui-old-support",
        )
        self.analysis(
            self.c,
            IgConversationAnalysisSnapshot.InteractionType.INFORMATION_ONLY,
            key="ui-latest-info",
        )
        hidden = IgClient.get_or_create_for_sender("ig-hidden-support")
        hidden.hidden_at = timezone.now()
        hidden.save(update_fields=["hidden_at", "updated_at"])
        self.analysis(
            hidden,
            IgConversationAnalysisSnapshot.InteractionType.SUPPORT_COMPLAINT,
            key="ui-hidden-support",
        )

        data = self.client.get(reverse("management_bot_clients_api") + "?view=complaints").json()

        self.assertEqual(data["total"], 0)

    def test_stats_category_breakdown_excludes_hidden_clients(self):
        self.analysis(
            self.c,
            IgConversationAnalysisSnapshot.InteractionType.SUPPORT_COMPLAINT,
            key="ui-visible-stats-support",
        )
        hidden = IgClient.get_or_create_for_sender("ig-hidden-stats-support")
        hidden.hidden_at = timezone.now()
        hidden.save(update_fields=["hidden_at", "updated_at"])
        self.analysis(
            hidden,
            IgConversationAnalysisSnapshot.InteractionType.SUPPORT_COMPLAINT,
            key="ui-hidden-stats-support",
        )

        data = self.client.get(reverse("management_bot_stats_api") + "?days=0").json()
        support = next(
            row for row in data["interactions"] if row["type"] == "support_complaint"
        )

        self.assertEqual(support["label"], "Підтримка / скарга")
        self.assertEqual(support["count"], 1)

    def test_clients_list_exposes_ukrainian_delivery_block_status(self):
        setattr(self.c, "delivery_status", "message_request_check")
        setattr(self.c, "delivery_error", "Перевірте Запити на повідомлення в Instagram.")
        self.c.save()

        r = self.client.get(reverse("management_bot_clients_api") + "?view=delivery-blocked")

        self.assertEqual(r.status_code, 200)
        data = r.json()
        row = next(client for client in data["clients"] if client["id"] == self.c.id)
        self.assertEqual(row.get("delivery_status"), "message_request_check")
        self.assertIn("Запити", row.get("delivery_status_label", ""))

    def test_client_detail(self):
        r = self.client.get(reverse("management_bot_client_detail_api", args=[self.c.id]))
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["client"]["id"], self.c.id)
        self.assertTrue(any(m["text"] == "привіт" for m in data["messages"]))
        self.assertGreaterEqual(len(data["funnel"]), 5)

    def test_client_detail_exposes_bounded_commercial_workspace_contract(self):
        review = IgPaymentConfirmationReview.objects.create(
            client=self.c,
            dedupe_key="client-workspace-review",
            evidence={
                "media": [
                    {"role": "receipt", "local_url": "/media/receipt.jpg"},
                    {"role": "product", "local_url": "/media/product.jpg"},
                ],
                "order_draft": {
                    "items": [{"title": "Футболка Харків", "qty": 2}],
                    "uncertainty_reasons": ["Потрібно підтвердити колір"],
                },
            },
        )

        data = self.client.get(
            reverse("management_bot_client_detail_api", args=[self.c.id])
        ).json()

        for key in (
            "automation", "interaction", "payment", "fulfillment",
            "review", "orders", "patterns",
        ):
            self.assertIn(key, data)
        self.assertEqual(data["review"]["pending_count"], 1)
        self.assertEqual(data["review"]["active"]["id"], review.id)
        self.assertEqual(len(data["review"]["active"]["media"]["receipts"]), 1)
        self.assertEqual(len(data["review"]["active"]["media"]["products"]), 1)
        self.assertEqual(data["orders"]["items"][0]["review_id"], review.id)
        self.assertEqual(data["patterns"]["source"], "episode_message_roles")
        self.assertIn("message_counts", data["patterns"])

    def test_client_detail_finds_actionable_review_older_than_bounded_history(self):
        actionable = IgPaymentConfirmationReview.objects.create(
            client=self.c,
            dedupe_key="older-actionable-review",
        )
        for index in range(21):
            IgPaymentConfirmationReview.objects.create(
                client=self.c,
                dedupe_key=f"newer-terminal-review-{index}",
                status=IgPaymentConfirmationReview.Status.CANCELLED,
            )

        data = self.client.get(
            reverse("management_bot_client_detail_api", args=[self.c.id])
        ).json()

        self.assertEqual(data["review"]["pending_count"], 1)
        self.assertEqual(len(data["review"]["history"]), 20)
        self.assertNotIn(
            actionable.id,
            [row["review_id"] for row in data["review"]["history"]],
        )
        self.assertEqual(data["review"]["active"]["review_id"], actionable.id)

    def test_client_detail_keeps_automation_and_payment_truth_separate(self):
        self.c.bot_paused = True
        self.c.manager_takeover = True
        self.c.paused_reason = "Менеджер уточнює замовлення"
        self.c.save(update_fields=[
            "bot_paused", "manager_takeover", "paused_reason", "updated_at",
        ])
        review = IgPaymentConfirmationReview.objects.create(
            client=self.c,
            dedupe_key="client-workspace-confirmed-review",
            evidence={"order_draft": {
                "items": [{"title": "Футболка", "qty": 1}],
                "quoted_total": "950.00",
            }},
        )
        IgPaymentReviewDecision.objects.create(
            review=review,
            client=self.c,
            decision=IgPaymentReviewDecision.Decision.MANAGER_VERIFIED,
            verification_source="manager",
            verification_scope=IgPaymentReviewDecision.VerificationScope.FULL_PAYMENT,
            confirmed_amount=Decimal("950.00"),
            amount_source="manager_input",
            actor=self.admin,
            actor_source=IgPaymentReviewDecision.ActorSource.MANAGEMENT_USER,
            actor_external_id=str(self.admin.pk),
            review_status_before=IgPaymentConfirmationReview.Status.PENDING,
            review_status_after=IgPaymentConfirmationReview.Status.CONFIRMED,
        )
        review.status = IgPaymentConfirmationReview.Status.CONFIRMED
        review.confirmed_by = self.admin
        review.confirmed_at = timezone.now()
        review.save(update_fields=["status", "confirmed_by", "confirmed_at", "updated_at"])

        data = self.client.get(
            reverse("management_bot_client_detail_api", args=[self.c.id])
        ).json()

        self.assertEqual(data["automation"]["owner"], "manager")
        self.assertEqual(data["automation"]["paused_reason"], "Менеджер уточнює замовлення")
        self.assertEqual(data["payment"]["manager_truth"], "manager_verified")
        self.assertEqual(data["payment"]["provider_truth"], "unverified")
        self.assertEqual(data["review"]["confirmed_count"], 1)
        self.assertEqual(data["review"]["history"][0]["decision_history"][0]["decision"], "manager_verified")
        self.assertIn(
            "ig_payment_review=",
            data["review"]["history"][0]["approval"]["create_order_url"],
        )

    def test_historical_paid_archive_is_green_and_not_actionable_without_fake_order(self):
        review = IgPaymentConfirmationReview.objects.create(
            client=self.c,
            dedupe_key="client-historical-paid-archive",
            status=IgPaymentConfirmationReview.Status.CONFIRMED,
            evidence={"order_draft": {"quoted_total": "1760.00"}},
            resolution_kind=IgPaymentConfirmationReview.ResolutionKind.HISTORICAL_PAID_ARCHIVED,
            resolution_note="Старе виконане замовлення, локальний Order не збережено",
            resolved_at=timezone.now(),
            resolved_by=self.admin,
        )
        IgPaymentReviewDecision.objects.create(
            review=review,
            client=self.c,
            decision=IgPaymentReviewDecision.Decision.MANAGER_VERIFIED,
            verification_source="manager",
            verification_scope=IgPaymentReviewDecision.VerificationScope.FULL_PAYMENT,
            confirmed_amount=Decimal("1760.00"),
            amount_source="manager_input",
            actor=self.admin,
            actor_source=IgPaymentReviewDecision.ActorSource.MANAGEMENT_USER,
            actor_external_id=str(self.admin.pk),
            review_status_before=IgPaymentConfirmationReview.Status.PENDING,
            review_status_after=IgPaymentConfirmationReview.Status.CONFIRMED,
        )
        self.c.stage = IgClient.Stage.PAID
        self.c.save(update_fields=["stage", "updated_at"])

        detail = self.client.get(
            reverse("management_bot_client_detail_api", args=[self.c.id])
        ).json()
        row = next(
            item
            for item in self.client.get(
                reverse("management_bot_clients_api") + "?view=paid"
            ).json()["clients"]
            if item["id"] == self.c.id
        )

        self.assertIsNone(detail["review"]["active"])
        self.assertEqual(
            detail["review"]["history"][0]["approval"]["state"],
            "historical_paid_archived",
        )
        self.assertFalse(detail["review"]["history"][0]["approval"]["needs_action"])
        self.assertEqual(row["stage"], IgClient.Stage.PAID)
        self.assertTrue(row["commercially_confirmed"])

    def test_paid_client_with_open_exchange_keeps_green_stage_and_post_sale_badge(self):
        from orders.models import Order

        order = Order.objects.create(
            full_name="Post Sale Paid",
            phone="0500000000",
            city="Київ",
            np_office="1",
            total_sum=Decimal("2100.00"),
            payment_status="paid",
            status="ship",
        )
        review = IgPaymentConfirmationReview.objects.create(
            client=self.c,
            order=order,
            dedupe_key="post-sale-paid-review",
            status=IgPaymentConfirmationReview.Status.CONFIRMED,
            evidence={"order_draft": {"quoted_total": "2100.00"}},
        )
        decision = IgPaymentReviewDecision.objects.create(
            review=review,
            client=self.c,
            decision=IgPaymentReviewDecision.Decision.MANAGER_VERIFIED,
            verification_source="manager",
            verification_scope=IgPaymentReviewDecision.VerificationScope.FULL_PAYMENT,
            confirmed_amount=Decimal("2100.00"),
            amount_source="manager_input",
            actor=self.admin,
            actor_source=IgPaymentReviewDecision.ActorSource.MANAGEMENT_USER,
            actor_external_id=str(self.admin.pk),
            review_status_before=IgPaymentConfirmationReview.Status.PENDING,
            review_status_after=IgPaymentConfirmationReview.Status.CONFIRMED,
        )
        attribution = IgOrderAttribution.objects.create(
            order=order,
            client=self.c,
            creation_mode="linked_existing",
            payment_source="manager_verified",
            payment_review=review,
            manager_decision=decision,
        )
        source = InstagramBotMessage.objects.create(
            sender_id=self.c.igsid,
            client=self.c,
            role=InstagramBotMessage.Role.USER,
            text="Є розміри для заміни?",
        )
        IgPostSaleCase.objects.create(
            client=self.c,
            order=order,
            commercial_episode=getattr(attribution, "commercial_episode", None),
            source_message=source,
            case_type=IgPostSaleCase.CaseType.EXCHANGE,
            status=IgPostSaleCase.Status.OPEN,
        )
        self.c.stage = IgClient.Stage.PAID
        self.c.save(update_fields=["stage", "updated_at"])

        rows = self.client.get(reverse("management_bot_clients_api")).json()["clients"]
        row = next(item for item in rows if item["id"] == self.c.id)

        self.assertEqual(row["stage"], IgClient.Stage.ORDER_CREATED)
        self.assertEqual(row["post_sale_type"], IgPostSaleCase.CaseType.EXCHANGE)
        self.assertEqual(row["post_sale_type_label"], "Обмін")
        self.assertTrue(row["post_sale_needs_action"])

    def test_new_pending_review_does_not_mask_provider_confirmed_truth(self):
        paid_deal = IgDeal.objects.create(
            client=self.c,
            amount=Decimal("950.00"),
            payment_truth=IgDeal.PaymentTruth.CONFIRMED,
        )
        IgPaymentProjection.objects.create(
            client=self.c,
            deal=paid_deal,
            truth=IgDeal.PaymentTruth.CONFIRMED,
            gross_amount=Decimal("950.00"),
        )
        IgPaymentConfirmationReview.objects.create(
            client=self.c,
            dedupe_key="newer-pending-review",
        )

        data = self.client.get(
            reverse("management_bot_client_detail_api", args=[self.c.id])
        ).json()

        self.assertEqual(data["payment"]["provider_truth"], "confirmed")
        self.assertEqual(data["payment"]["provider_source"], "provider_projection")

    def test_latest_manager_truth_is_not_lost_behind_twenty_newer_reviews(self):
        verified = IgPaymentConfirmationReview.objects.create(
            client=self.c,
            dedupe_key="older-verified-review",
            status=IgPaymentConfirmationReview.Status.CONFIRMED,
        )
        decision = IgPaymentReviewDecision.objects.create(
            review=verified,
            client=self.c,
            decision=IgPaymentReviewDecision.Decision.MANAGER_VERIFIED,
            verification_source="manager",
            verification_scope=IgPaymentReviewDecision.VerificationScope.FULL_PAYMENT,
            confirmed_amount=Decimal("1800.00"),
            amount_source="manager_input",
            actor=self.admin,
            actor_source=IgPaymentReviewDecision.ActorSource.MANAGEMENT_USER,
            actor_external_id=str(self.admin.pk),
            review_status_before=IgPaymentConfirmationReview.Status.PENDING,
            review_status_after=IgPaymentConfirmationReview.Status.CONFIRMED,
        )
        for index in range(21):
            IgPaymentConfirmationReview.objects.create(
                client=self.c,
                dedupe_key=f"newer-review-{index}",
            )

        data = self.client.get(
            reverse("management_bot_client_detail_api", args=[self.c.id])
        ).json()

        self.assertEqual(data["payment"]["manager_truth"], "manager_verified")
        self.assertEqual(data["payment"]["manager_decision"]["id"], decision.id)

    def test_manager_verified_linked_order_keeps_paid_stage_without_provider_deal(self):
        from orders.models import Order

        self.c.stage = IgClient.Stage.PAID
        self.c.save(update_fields=["stage", "updated_at"])
        order = Order.objects.create(
            order_number="TWC-YANA-REGRESSION",
            full_name="Ніколаєнко Яна",
            phone="380502034719",
            total_sum=Decimal("2100.00"),
            payment_status="paid",
            status="ship",
            tracking_number="20451495591085",
            source="manual",
            sale_source="Instagram",
        )
        review = IgPaymentConfirmationReview.objects.create(
            client=self.c,
            dedupe_key="yana-manager-linked-no-deal",
            status=IgPaymentConfirmationReview.Status.CONFIRMED,
            order=order,
        )
        decision = IgPaymentReviewDecision.objects.create(
            review=review,
            client=self.c,
            decision=IgPaymentReviewDecision.Decision.MANAGER_VERIFIED,
            verification_source="manager",
            verification_scope=IgPaymentReviewDecision.VerificationScope.FULL_PAYMENT,
            confirmed_amount=Decimal("2100.00"),
            amount_source="manager_input",
            actor=self.admin,
            actor_source=IgPaymentReviewDecision.ActorSource.MANAGEMENT_USER,
            actor_external_id=str(self.admin.pk),
            review_status_before=IgPaymentConfirmationReview.Status.PENDING,
            review_status_after=IgPaymentConfirmationReview.Status.CONFIRMED,
        )
        attribution = IgOrderAttribution.objects.create(
            order=order,
            client=self.c,
            payment_review=review,
            manager_decision=decision,
            creation_mode="linked_existing",
            payment_source="manager_verified",
        )
        from management.services.ig_commercial_episodes import ensure_episode_for_attribution

        episode = ensure_episode_for_attribution(attribution)
        self.assertEqual(episode.state, "order_created")

        detail = self.client.get(
            reverse("management_bot_client_detail_api", args=[self.c.id])
        ).json()
        clients = self.client.get(
            reverse("management_bot_clients_api") + f"?client_id={self.c.id}"
        ).json()
        all_clients = self.client.get(
            reverse("management_bot_clients_api") + "?view=all"
        ).json()
        active_clients = self.client.get(
            reverse("management_bot_clients_api") + "?view=active"
        ).json()
        list_card = next(item for item in clients["clients"] if item["id"] == self.c.id)

        for card in (detail["client"], list_card):
            self.assertEqual(card["stage_raw"], IgClient.Stage.PAID)
            self.assertEqual(card["stage"], IgClient.Stage.ORDER_CREATED)
            self.assertEqual(card["stage_label"], "Замовлення створено")
            self.assertTrue(card["commercially_confirmed"])
            self.assertEqual(card["commercial_confirmation_source"], "manager_verified_order")
        funnel = {item["stage"]: item for item in detail["funnel"]}
        self.assertTrue(funnel[IgClient.Stage.ORDER_CREATED]["current"])
        self.assertTrue(funnel[IgClient.Stage.ORDER_CREATED]["done"])
        self.assertFalse(funnel[IgClient.Stage.DONE]["done"])
        self.assertEqual(detail["payment"]["provider_truth"], "unverified")
        self.assertEqual(detail["payment"]["manager_truth"], "manager_verified")
        self.assertTrue(detail["payment"]["authoritative_for_fulfillment"])
        self.assertIsNone(detail["review"]["active"])
        self.assertEqual(detail["orders"]["physical_count"], 1)
        self.assertEqual(len(detail["orders"]["items"]), 1)
        self.assertEqual(detail["orders"]["items"][0]["order"]["id"], order.id)
        self.assertEqual(
            detail["orders"]["items"][0]["approval"]["state"],
            "linked_existing",
        )
        self.assertIn(
            self.c.id,
            [item["id"] for item in all_clients["clients"]],
            "A manager-confirmed order must remain available in the complete conversation archive.",
        )
        self.assertNotIn(
            self.c.id,
            [item["id"] for item in active_clients["clients"]],
            "A completed paid sale must not remain in the active work queue.",
        )

    def test_commercial_visual_state_prioritizes_active_shipment_with_tracking(self):
        from orders.models import Order
        from management.services.ig_order_assignments import link_order_to_client

        paid_deal = IgDeal.objects.create(
            client=self.c,
            amount=Decimal("2100.00"),
            payment_truth=IgDeal.PaymentTruth.CONFIRMED,
        )
        IgPaymentProjection.objects.create(
            client=self.c,
            deal=paid_deal,
            truth=IgDeal.PaymentTruth.CONFIRMED,
            gross_amount=Decimal("2100.00"),
        )
        order = Order.objects.create(
            full_name="Відправлене замовлення",
            phone="380502034719",
            city="Київ",
            np_office="1",
            total_sum=Decimal("2100.00"),
            payment_status="paid",
            status="ship",
            tracking_number="20451495591085",
        )
        link_order_to_client(order, client=self.c, actor=self.admin)

        list_card = next(
            item
            for item in self.client.get(
                reverse("management_bot_clients_api") + f"?client_id={self.c.id}"
            ).json()["clients"]
            if item["id"] == self.c.id
        )
        detail_card = self.client.get(
            reverse("management_bot_client_detail_api", args=[self.c.id])
        ).json()["client"]

        for card in (list_card, detail_card):
            self.assertEqual(card["commercial_visual_state"], "shipped")
            self.assertEqual(card["commercial_visual_state_label"], "Відправлено")

    def test_commercial_visual_state_keeps_confirmed_payment_green_without_tracking(self):
        from orders.models import Order
        from management.services.ig_order_assignments import link_order_to_client

        order = Order.objects.create(
            full_name="Оплачене замовлення",
            phone="380502034720",
            city="Київ",
            np_office="1",
            total_sum=Decimal("950.00"),
            payment_status="paid",
            status="ship",
        )
        link_order_to_client(order, client=self.c, actor=self.admin)

        card = next(
            item
            for item in self.client.get(
                reverse("management_bot_clients_api") + f"?client_id={self.c.id}"
            ).json()["clients"]
            if item["id"] == self.c.id
        )

        self.assertEqual(card["commercial_visual_state"], "paid")
        self.assertEqual(card["commercial_visual_state_label"], "Оплачено")

    def test_commercial_visual_state_keeps_delivered_order_green_after_shipment(self):
        from orders.models import Order
        from management.services.ig_order_assignments import link_order_to_client

        paid_deal = IgDeal.objects.create(
            client=self.c,
            amount=Decimal("2100.00"),
            payment_truth=IgDeal.PaymentTruth.CONFIRMED,
        )
        IgPaymentProjection.objects.create(
            client=self.c,
            deal=paid_deal,
            truth=IgDeal.PaymentTruth.CONFIRMED,
            gross_amount=Decimal("2100.00"),
        )
        order = Order.objects.create(
            full_name="Доставлене замовлення",
            phone="380502034722",
            city="Київ",
            np_office="1",
            total_sum=Decimal("2100.00"),
            payment_status="paid",
            status="done",
            tracking_number="20451495591087",
        )
        link_order_to_client(order, client=self.c, actor=self.admin)

        card = next(
            item
            for item in self.client.get(
                reverse("management_bot_clients_api") + f"?client_id={self.c.id}"
            ).json()["clients"]
            if item["id"] == self.c.id
        )

        self.assertEqual(card["commercial_visual_state"], "paid")
        self.assertEqual(card["commercial_visual_state_label"], "Оплачено")

    def test_commercial_visual_state_never_treats_direct_delivery_error_as_shipment(self):
        paid_deal = IgDeal.objects.create(
            client=self.c,
            amount=Decimal("950.00"),
            payment_truth=IgDeal.PaymentTruth.CONFIRMED,
        )
        IgPaymentProjection.objects.create(
            client=self.c,
            deal=paid_deal,
            truth=IgDeal.PaymentTruth.CONFIRMED,
            gross_amount=Decimal("950.00"),
        )
        self.c.delivery_status = "message_request_check"
        self.c.delivery_error = "Перевірте Запити на повідомлення в Instagram."
        self.c.save(update_fields=["delivery_status", "delivery_error", "updated_at"])

        card = next(
            item
            for item in self.client.get(
                reverse("management_bot_clients_api") + f"?client_id={self.c.id}"
            ).json()["clients"]
            if item["id"] == self.c.id
        )

        self.assertEqual(card["commercial_visual_state"], "paid")
        self.assertEqual(card["delivery_status"], "message_request_check")

    def test_commercial_visual_state_ignores_an_unassigned_shipped_order(self):
        from orders.models import Order
        from management.services.ig_order_assignments import (
            link_order_to_client,
            unlink_order_from_client,
        )

        order = Order.objects.create(
            full_name="Відв'язане замовлення",
            phone="380502034721",
            city="Київ",
            np_office="1",
            total_sum=Decimal("1200.00"),
            payment_status="paid",
            status="ship",
            tracking_number="20451495591086",
        )
        assignment = link_order_to_client(order, client=self.c, actor=self.admin)
        unlink_order_from_client(
            order,
            client=self.c,
            actor=self.admin,
            expected_version=assignment.version,
            reason_code="test_unlink",
            reason="Тестуємо, що знята прив'язка не виглядає відправленою.",
        )

        card = next(
            item
            for item in self.client.get(
                reverse("management_bot_clients_api") + f"?client_id={self.c.id}"
            ).json()["clients"]
            if item["id"] == self.c.id
        )

        self.assertEqual(card["commercial_visual_state"], "")
        self.assertEqual(card["commercial_visual_state_label"], "")

    def test_incremental_detail_projects_operational_stage_for_open_chat(self):
        from orders.models import Order
        from management.services.ig_commercial_episodes import ensure_episode_for_attribution

        self.c.stage = IgClient.Stage.PAID
        self.c.save(update_fields=["stage", "updated_at"])
        order = Order.objects.create(
            order_number="TWC-INCREMENTAL-STAGE",
            full_name="Іван",
            phone="380000000000",
            total_sum=Decimal("950.00"),
            payment_status="paid",
            status="ship",
        )
        review = IgPaymentConfirmationReview.objects.create(
            client=self.c,
            dedupe_key="incremental-stage-review",
            status=IgPaymentConfirmationReview.Status.CONFIRMED,
            order=order,
        )
        decision = IgPaymentReviewDecision.objects.create(
            review=review,
            client=self.c,
            decision=IgPaymentReviewDecision.Decision.MANAGER_VERIFIED,
            verification_source="manager",
            verification_scope=IgPaymentReviewDecision.VerificationScope.FULL_PAYMENT,
            confirmed_amount=Decimal("950.00"),
            amount_source="manager_input",
            actor=self.admin,
            actor_source=IgPaymentReviewDecision.ActorSource.MANAGEMENT_USER,
            actor_external_id=str(self.admin.pk),
            review_status_before=IgPaymentConfirmationReview.Status.PENDING,
            review_status_after=IgPaymentConfirmationReview.Status.CONFIRMED,
        )
        attribution = IgOrderAttribution.objects.create(
            order=order,
            client=self.c,
            payment_review=review,
            manager_decision=decision,
            creation_mode="linked_existing",
            payment_source="manager_verified",
        )
        episode = ensure_episode_for_attribution(attribution)
        response = self.client.get(
            reverse("management_bot_client_detail_api", args=[self.c.id])
            + "?after_id=0"
        )
        self.assertEqual(response.status_code, 200)

        response = self.client.get(
            reverse("management_bot_client_detail_api", args=[self.c.id])
            + f"?after_id={self.c.messages.order_by('id').first().id}"
        )
        payload = response.json()
        self.assertEqual(payload["stage"], IgClient.Stage.ORDER_CREATED)
        self.assertEqual(payload["stage_label"], "Замовлення створено")
        funnel = {item["stage"]: item for item in payload["funnel"]}
        self.assertTrue(funnel[IgClient.Stage.ORDER_CREATED]["current"])
        self.assertEqual(episode.state, "order_created")

    def test_all_view_includes_every_non_hidden_conversation(self):
        paid = IgClient.get_or_create_for_sender("ig-all-paid")
        paid.stage = IgClient.Stage.PAID
        paid.save(update_fields=["stage", "updated_at"])
        cold = IgClient.get_or_create_for_sender("ig-all-cold")
        cold.stage = IgClient.Stage.COLD
        cold.save(update_fields=["stage", "updated_at"])
        spam = IgClient.get_or_create_for_sender("ig-all-spam")
        spam.stage = IgClient.Stage.SPAM
        spam.save(update_fields=["stage", "updated_at"])
        hidden = IgClient.get_or_create_for_sender("ig-all-hidden")
        hidden.hidden_at = timezone.now()
        hidden.save(update_fields=["hidden_at", "updated_at"])

        data = self.client.get(
            reverse("management_bot_clients_api") + "?view=all"
        ).json()
        ids = {item["id"] for item in data["clients"]}

        self.assertTrue({self.c.id, paid.id, cold.id, spam.id}.issubset(ids))
        self.assertNotIn(hidden.id, ids)

    def test_default_view_includes_every_non_hidden_conversation(self):
        paid = IgClient.get_or_create_for_sender("ig-default-paid")
        paid.stage = IgClient.Stage.PAID
        paid.save(update_fields=["stage", "updated_at"])
        cold = IgClient.get_or_create_for_sender("ig-default-cold")
        cold.stage = IgClient.Stage.COLD
        cold.save(update_fields=["stage", "updated_at"])
        spam = IgClient.get_or_create_for_sender("ig-default-spam")
        spam.stage = IgClient.Stage.SPAM
        spam.save(update_fields=["stage", "updated_at"])
        hidden = IgClient.get_or_create_for_sender("ig-default-hidden")
        hidden.hidden_at = timezone.now()
        hidden.save(update_fields=["hidden_at", "updated_at"])

        data = self.client.get(reverse("management_bot_clients_api")).json()
        ids = {item["id"] for item in data["clients"]}

        self.assertTrue({self.c.id, paid.id, cold.id, spam.id}.issubset(ids))
        self.assertNotIn(hidden.id, ids)

    def test_meta_reviewer_cannot_read_commercial_client_detail(self):
        self.client.logout()
        reviewer = User.objects.create_user("meta_detail_reviewer", password="x")
        group = Group.objects.create(name=META_REVIEWER_GROUP_NAME)
        reviewer.groups.add(group)
        self.client.force_login(reviewer)

        response = self.client.get(
            reverse("management_bot_client_detail_api", args=[self.c.id])
        )

        self.assertEqual(response.status_code, 403)

    def test_requires_admin(self):
        self.client.logout()
        nonadmin = User.objects.create_user("u", password="x")
        self.client.force_login(nonadmin)
        r = self.client.get(reverse("management_bot_clients_api"))
        self.assertEqual(r.status_code, 403)


@MGMT
class ClientsPageRenderTests(TestCase):
    def test_bot_page_has_tabbed_structure(self):
        admin = User.objects.create_user("adm2", password="x", is_staff=True)
        self.client.force_login(admin)
        r = self.client.get(reverse("management_bot"))
        self.assertEqual(r.status_code, 200)
        html = r.content.decode("utf-8")
        # Основні робочі вкладки
        self.assertIn("Клієнти", html)
        self.assertIn("Налаштування", html)
        self.assertIn("Інструкції", html)
        self.assertIn("Огляд", html)
        self.assertIn("Замовлення", html)
        # таб-структура (панелі)
        self.assertIn('data-tab="clients"', html)
        self.assertIn('data-panel="clients"', html)
        self.assertIn('data-panel="settings"', html)
        self.assertIn('data-panel="kb"', html)
        self.assertIn("bot-tab-ind", html)  # анімований індикатор
        self.assertIn("Дані недоступні", html)
        self.assertIn("Сповіщення, які потребують перевірки", html)
        self.assertIn("/bot/api/notifications/review/", html)
        self.assertIn("Скарги / підтримка", html)
        self.assertIn('data-client-view="wholesale"', html)
        self.assertIn('data-client-view="collaboration"', html)
        self.assertIn('data-client-view="reactions"', html)
        self.assertIn("bot-client-commercial", html)
        self.assertNotIn("Категорія діалогу</div>", html)
        self.assertIn("Категорії діалогів", html)

    def test_bot_page_inline_scripts_have_valid_javascript_syntax(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node is required for inline script syntax validation")

        admin = User.objects.create_user("adm_js", password="x", is_staff=True)
        self.client.force_login(admin)
        response = self.client.get(reverse("management_bot"))

        self.assertEqual(response.status_code, 200)
        scripts = [
            script.strip()
            for script in re.findall(
                r"<script(?:\s[^>]*)?>(.*?)</script>",
                response.content.decode("utf-8"),
                flags=re.S | re.I,
            )
            if script.strip()
        ]
        self.assertGreater(len(scripts), 0)
        for script in scripts:
            with tempfile.NamedTemporaryFile(
                "w", suffix=".js", delete=False, encoding="utf-8"
            ) as handle:
                handle.write(script)
                path = handle.name
            try:
                result = subprocess.run(
                    [node, "--check", path], capture_output=True, text=True
                )
            finally:
                os.unlink(path)
            self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)


@MGMT
class OrdersWorkspaceApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("orders_api_admin", password="x", is_staff=True)
        self.client.force_login(self.admin)
        self.customer = IgClient.get_or_create_for_sender("orders-api-client")
        self.pending = IgPaymentConfirmationReview.objects.create(
            client=self.customer,
            dedupe_key="orders-api-pending",
            evidence={
                "order_draft": {
                    "items": [{"title": "Футболка", "qty": 1, "size": "S"}],
                    "quoted_total": "950.00",
                    "uncertainty_reasons": [],
                },
                "media": [
                    {"role": "receipt", "local_url": "/media/check.jpg"},
                    {"role": "custom_reference", "local_url": "/media/custom.jpg"},
                    {"role": "unknown", "local_url": "/media/unknown.jpg"},
                ],
            },
        )
        self.confirmed = IgPaymentConfirmationReview.objects.create(
            client=self.customer,
            dedupe_key="orders-api-confirmed",
            status=IgPaymentConfirmationReview.Status.CONFIRMED,
        )

    @override_settings(SITE_BASE_URL="https://shop.example.test")
    def test_manual_order_link_reports_origin_version_and_unlink_capability(self):
        from orders.models import Order

        order = Order.objects.create(
            full_name="Website buyer",
            phone="380501112233",
            total_sum=Decimal("790.00"),
            payment_status="paid",
            source="website",
        )
        response = self.client.post(
            reverse(
                "management_bot_client_order_link_api",
                args=[self.customer.pk],
            ),
            {
                "order_identifier": order.order_number,
                "operation_id": str(uuid.uuid4()),
            },
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()["assignment"]
        self.assertEqual(payload["order"]["number"], order.order_number)
        self.assertEqual(payload["source"], "manager_manual")
        self.assertEqual(payload["actor"]["id"], self.admin.pk)
        self.assertEqual(payload["version"], 1)
        self.assertTrue(payload["can_unlink"])
        self.assertEqual(
            payload["capabilities"]["ttn_action_url"],
            f"https://shop.example.test/admin-panel/orders/{order.pk}/nova-poshta/",
        )

        unlink_response = self.client.post(
            reverse(
                "management_bot_client_order_unlink_api",
                args=[self.customer.pk, payload["id"]],
            ),
            {
                "expected_version": payload["version"],
                "reason_code": "manager_correction",
                "reason": "The manager selected the wrong order first.",
            },
        )
        self.assertEqual(unlink_response.status_code, 200, unlink_response.content)
        self.assertEqual(unlink_response.json()["assignment"]["state"], "unassigned")
        history = self.client.get(
            reverse("management_bot_client_detail_api", args=[self.customer.pk])
        ).json()["orders"]["assignment_history"]
        self.assertEqual(history[0]["kind"], "unlinked")

    def test_manual_order_link_conflict_and_stale_unlink_are_409(self):
        from management.models import IgClient
        from orders.models import Order

        order = Order.objects.create(
            full_name="Website buyer",
            phone="380501112233",
            total_sum=Decimal("790.00"),
            payment_status="paid",
            source="website",
        )
        first = self.client.post(
            reverse("management_bot_client_order_link_api", args=[self.customer.pk]),
            {"order_identifier": order.order_number},
        )
        self.assertEqual(first.status_code, 200, first.content)
        other = IgClient.get_or_create_for_sender("orders-api-other-client")
        conflict = self.client.post(
            reverse("management_bot_client_order_link_api", args=[other.pk]),
            {"order_identifier": order.order_number},
        )
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(conflict.json()["error_code"], "assignment_conflict")

        stale = self.client.post(
            reverse(
                "management_bot_client_order_unlink_api",
                args=[self.customer.pk, first.json()["assignment"]["id"]],
            ),
            {
                "expected_version": 0,
                "reason_code": "manager_correction",
                "reason": "stale drawer",
            },
        )
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(stale.json()["error_code"], "assignment_version_conflict")

    def test_orders_workspace_has_action_confirmed_all_counts(self):
        response = self.client.get(reverse("management_bot_orders_workspace_api"))

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["section"], "orders")
        self.assertEqual(data["view"], "action")
        self.assertEqual(data["counts"], {"action": 2, "confirmed": 1, "all": 2})
        self.assertEqual(
            {item["review_id"] for item in data["items"]},
            {self.pending.id, self.confirmed.id},
        )
        item = next(row for row in data["items"] if row["review_id"] == self.pending.id)
        self.assertTrue(item["approval"]["needs_action"])
        self.assertEqual(item["client"]["id"], self.customer.id)
        self.assertEqual(item["draft"]["items"][0]["qty"], 1)
        self.assertEqual(len(item["media"]["receipts"]), 1)
        self.assertEqual(len(item["media"]["custom_print"]), 1)
        self.assertEqual(len(item["media"]["unknown"]), 1)
        self.assertIn(f"review={self.pending.id}", item["workspace_url"])

    def test_legacy_payment_review_deep_link_resolves_superseded_row_to_canonical_review(self):
        duplicate = IgPaymentConfirmationReview.objects.create(
            client=self.customer,
            dedupe_key="orders-api-superseded-legacy-link",
            status=IgPaymentConfirmationReview.Status.SUPERSEDED,
            superseded_by=self.pending,
        )

        response = self.client.get(
            reverse("management_bot_payment_reviews_api"),
            {"id": duplicate.pk},
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["items"][0]["id"], self.pending.pk)
        self.assertTrue(payload["items"][0]["selected"])

    def test_legacy_amount_clarification_opens_in_action_queue(self):
        from management.ig_bot_models import IgPaymentReviewDecision

        IgPaymentReviewDecision.objects.create(
            review=self.confirmed,
            client=self.customer,
            decision=IgPaymentReviewDecision.Decision.MANAGER_VERIFIED,
            verification_source="manager",
            verification_scope=IgPaymentReviewDecision.VerificationScope.PAYMENT_CLAIM,
            confirmed_amount=None,
            actor=self.admin,
            actor_source=IgPaymentReviewDecision.ActorSource.MANAGEMENT_USER,
            actor_external_id=str(self.admin.pk),
            review_status_before=IgPaymentConfirmationReview.Status.PENDING,
            review_status_after=IgPaymentConfirmationReview.Status.CONFIRMED,
        )

        data = self.client.get(
            reverse("management_bot_orders_workspace_api")
            + f"?view=all&review={self.confirmed.pk}"
        ).json()
        item = next(row for row in data["items"] if row["review_id"] == self.confirmed.pk)

        self.assertEqual(item["approval"]["state"], "amount_clarification")
        self.assertTrue(item["approval"]["can_clarify_amount"])
        self.assertIn("view=action", item["workspace_url"])

    def test_order_candidate_exposes_full_payment_amount_conflict_before_link(self):
        from management.services.ig_payment_review import record_review_decision
        from orders.models import Order, OrderItem

        review = IgPaymentConfirmationReview.objects.create(
            client=self.customer,
            dedupe_key="orders-api-candidate-amount-mismatch",
            evidence={"order_draft": {"quoted_total": "500.00"}},
        )
        record_review_decision(
            review,
            actor=self.admin,
            decision="manager_verified",
            verification_scope="full_payment",
            confirmed_amount="500.00",
        )
        order = Order.objects.create(
            full_name="Яна",
            phone="380502034719",
            total_sum=Decimal("2000.00"),
            payment_status="paid",
        )
        OrderItem.objects.create(
            order=order,
            title="Базова футболка",
            size="S",
            qty=1,
            unit_price=Decimal("1050.00"),
            line_total=Decimal("1050.00"),
        )
        OrderItem.objects.create(
            order=order,
            title="Оверсайз",
            size="XS",
            qty=1,
            unit_price=Decimal("950.00"),
            line_total=Decimal("950.00"),
        )

        response = self.client.get(
            reverse("management_bot_order_candidates_api"),
            {"client_id": self.customer.pk, "review_id": review.pk},
            secure=True,
        )
        item = next(row for row in response.json()["items"] if row["id"] == order.pk)

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            item["items"],
            [
                {
                    "title": "Базова футболка",
                    "size": "S",
                    "qty": 1,
                    "unit_price": "1050.00",
                    "line_total": "1050.00",
                },
                {
                    "title": "Оверсайз",
                    "size": "XS",
                    "qty": 1,
                    "unit_price": "950.00",
                    "line_total": "950.00",
                },
            ],
        )
        self.assertTrue(item["requires_override"])
        self.assertIn("payment_amount_mismatch", item["override_conflicts"])
        self.assertEqual(
            item["allowed_override_codes"],
            ["payment_state_mismatch", "historical_import"],
        )

    def test_reconciliation_conflict_disables_order_resolution_in_api(self):
        from management.ig_bot_models import IgDeal, IgPaymentProjection
        from management.services.ig_payment_review import record_review_decision

        deal = IgDeal.objects.create(
            client=self.customer,
            amount=Decimal("790.00"),
            requested_payment_amount=Decimal("790.00"),
        )
        review = IgPaymentConfirmationReview.objects.create(
            client=self.customer,
            deal=deal,
            dedupe_key="orders-api-reconciliation",
        )
        record_review_decision(
            review,
            actor=self.admin,
            decision="manager_verified",
            verification_scope="prepayment",
            confirmed_amount="315.00",
        )
        IgPaymentProjection.objects.create(
            deal=deal,
            client=self.customer,
            truth=IgDeal.PaymentTruth.CONFIRMED,
            gross_amount=Decimal("790.00"),
        )

        data = self.client.get(
            reverse("management_bot_orders_workspace_api")
            + f"?view=all&review={review.pk}"
        ).json()
        item = data["items"][0]

        self.assertTrue(item["payment"]["needs_reconciliation"])
        self.assertFalse(item["approval"]["can_link_existing"])
        self.assertFalse(item["approval"]["can_create"])
        self.assertEqual(item["approval"]["state"], "payment_reconciliation")
        self.assertIn("view=action", item["workspace_url"])

    def test_linked_order_with_later_reconciliation_stays_in_action_queue(self):
        from management.ig_bot_models import IgDeal, IgPaymentProjection
        from management.services.ig_payment_review import record_review_decision
        from orders.models import Order

        deal = IgDeal.objects.create(
            client=self.customer,
            amount=Decimal("1280.00"),
            requested_payment_amount=Decimal("1280.00"),
        )
        order = Order.objects.create(
            full_name="Яна",
            phone="380502034719",
            total_sum=Decimal("1280.00"),
        )
        review = IgPaymentConfirmationReview.objects.create(
            client=self.customer,
            deal=deal,
            order=order,
            dedupe_key="orders-api-linked-reconciliation",
        )
        record_review_decision(
            review,
            actor=self.admin,
            decision="manager_verified",
            verification_scope="prepayment",
            confirmed_amount="315.00",
        )
        IgPaymentProjection.objects.create(
            deal=deal,
            client=self.customer,
            truth=IgDeal.PaymentTruth.CONFIRMED,
            gross_amount=Decimal("1280.00"),
        )

        data = self.client.get(
            reverse("management_bot_orders_workspace_api") + "?view=action"
        ).json()
        item = next(row for row in data["items"] if row["review_id"] == review.pk)

        self.assertEqual(item["approval"]["state"], "payment_reconciliation")
        self.assertTrue(item["approval"]["needs_action"])
        self.assertIn("view=action", item["workspace_url"])

    def test_manager_confirmation_conflict_returns_reconciliation_next_action(self):
        from management.ig_bot_models import IgDeal, IgPaymentProjection

        deal = IgDeal.objects.create(
            client=self.customer,
            amount=Decimal("790.00"),
            requested_payment_amount=Decimal("790.00"),
        )
        review = IgPaymentConfirmationReview.objects.create(
            client=self.customer,
            deal=deal,
            dedupe_key="orders-api-action-reconciliation",
        )
        IgPaymentProjection.objects.create(
            deal=deal,
            client=self.customer,
            truth=IgDeal.PaymentTruth.CONFIRMED,
            gross_amount=Decimal("790.00"),
        )

        response = self.client.post(
            reverse("management_bot_payment_review_action_api", args=[review.pk]),
            {
                "action": "manager_verify",
                "verification_scope": "prepayment",
                "confirmed_amount": "315.00",
            },
        )
        payload = response.json()

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(payload["next_action"], "reconcile_payment")
        self.assertTrue(payload["payment"]["needs_reconciliation"])
        self.assertFalse(payload["order_resolution"]["required"])
        self.assertEqual(payload["order_resolution"]["create_new"]["url"], "")

    def test_orders_workspace_supports_confirmed_and_client_scope(self):
        other = IgClient.get_or_create_for_sender("orders-api-other")
        IgPaymentConfirmationReview.objects.create(
            client=other,
            dedupe_key="orders-api-other-pending",
        )
        url = reverse("management_bot_orders_workspace_api")

        data = self.client.get(
            f"{url}?view=confirmed&client_id={self.customer.id}"
        ).json()

        self.assertEqual([item["review_id"] for item in data["items"]], [self.confirmed.id])

    def test_discounted_attributed_order_exposes_subtotal_discount_and_payable_total(self):
        from management.ig_bot_models import IgOrderAttribution
        from orders.models import Order

        order = Order.objects.create(
            full_name="Яна",
            phone="380502034719",
            total_sum=Decimal("2180.00"),
            discount_amount=Decimal("80.00"),
        )
        IgOrderAttribution.objects.create(
            order=order,
            client=self.customer,
            creation_mode="linked_existing",
            payment_source="manager_verified",
        )

        data = self.client.get(
            reverse("management_bot_orders_workspace_api") + "?view=confirmed"
        ).json()
        item = next(row for row in data["items"] if row["order"]["id"] == order.pk)

        self.assertEqual(item["order"]["subtotal"], "2180.00")
        self.assertEqual(item["order"]["discount_amount"], "80.00")
        self.assertEqual(item["order"]["amount"], "2100.00")
        self.assertEqual(item["draft"]["quoted_total"], "2100.00")

    def test_orders_workspace_supports_exact_review_deep_link_selector(self):
        data = self.client.get(
            reverse("management_bot_orders_workspace_api")
            + f"?view=all&review={self.pending.id}"
        ).json()

        self.assertEqual(data["selected_review_id"], self.pending.id)
        self.assertEqual([item["review_id"] for item in data["items"]], [self.pending.id])

    def test_hidden_client_is_excluded_from_counts_and_items(self):
        hidden = IgClient.get_or_create_for_sender("orders-api-hidden")
        hidden.hidden_at = timezone.now()
        hidden.save(update_fields=["hidden_at", "updated_at"])
        IgPaymentConfirmationReview.objects.create(
            client=hidden,
            dedupe_key="orders-api-hidden-review",
        )

        data = self.client.get(reverse("management_bot_orders_workspace_api")).json()

        self.assertEqual(data["counts"], {"action": 2, "confirmed": 1, "all": 2})
        self.assertNotIn(hidden.id, [item["client"]["id"] for item in data["items"]])

    def test_orders_workspace_requires_staff_permission(self):
        self.client.logout()
        user = User.objects.create_user("orders_api_user", password="x")
        self.client.force_login(user)

        response = self.client.get(reverse("management_bot_orders_workspace_api"))

        self.assertEqual(response.status_code, 403)

    def test_confirmed_workspace_exposes_decision_history_catalog_links_and_create_url(self):
        self.confirmed.evidence = {
            "catalog_matches": [{
                "status": "matched",
                "product_id": 17,
                "title": "Kharkiv Pink",
                "url": "https://twocomms.shop/product/kharkiv-pink/",
                "confidence": "0.96",
            }],
            "order_draft": {
                "items": [{"title": "Kharkiv Pink", "qty": 2, "fit": "oversize"}],
                "quoted_total": "1800.00",
            },
        }
        self.confirmed.save(update_fields=["evidence", "updated_at"])
        IgPaymentReviewDecision.objects.create(
            review=self.confirmed,
            client=self.customer,
            decision=IgPaymentReviewDecision.Decision.MANAGER_VERIFIED,
            verification_source="manager",
            verification_scope=IgPaymentReviewDecision.VerificationScope.FULL_PAYMENT,
            confirmed_amount=Decimal("1800.00"),
            amount_source="manager_input",
            actor=self.admin,
            actor_source=IgPaymentReviewDecision.ActorSource.MANAGEMENT_USER,
            actor_external_id=str(self.admin.pk),
            review_status_before=IgPaymentConfirmationReview.Status.PENDING,
            review_status_after=IgPaymentConfirmationReview.Status.CONFIRMED,
        )

        data = self.client.get(
            reverse("management_bot_orders_workspace_api") + "?view=confirmed"
        ).json()

        item = data["items"][0]
        self.assertEqual(item["id"], self.confirmed.id)
        self.assertEqual(item["draft"]["catalog_candidates"][0]["product_id"], 17)
        self.assertEqual(item["decision_history"][0]["decision"], "manager_verified")
        self.assertTrue(item["approval"]["can_create"])
        self.assertEqual(item["approval"]["state"], "needs_order_resolution")
        self.assertEqual(item["order_url"], "")
        self.assertIn("ig_payment_review=", item["approval"]["create_order_url"])
        self.assertIn("view=action", item["workspace_url"])

    def test_workspace_drops_dangerous_media_and_untrusted_product_urls(self):
        self.pending.evidence = {
            "media": [
                {"role": "receipt", "url": "javascript:alert(1)"},
                {"role": "product", "local_url": "data:text/html,unsafe"},
            ],
            "catalog_matches": [{
                "status": "matched",
                "title": "Unsafe",
                "url": "https://evil.example/phishing",
            }],
        }
        self.pending.save(update_fields=["evidence", "updated_at"])

        data = self.client.get(reverse("management_bot_orders_workspace_api")).json()
        item = next(row for row in data["items"] if row["review_id"] == self.pending.id)

        self.assertNotIn("url", item["media"]["receipts"][0])
        self.assertNotIn("local_url", item["media"]["products"][0])
        self.assertNotIn("url", item["draft"]["catalog_candidates"][0])

    def test_workspace_bounds_and_whitelists_untrusted_evidence_shapes(self):
        oversized = "x" * 5000
        self.pending.evidence = {
            "media": [{
                "role": "receipt",
                "message_id": {"nested": oversized},
                "source_message_id": "42",
                "product_id": "17",
                "product_title": oversized,
                "confidence": {"nested": "0.99"},
                "url": "https://cdn.example/check.jpg",
                "unexpected": {"secret": oversized},
            }],
            "catalog_matches": [{
                "status": "matched",
                "product_id": "17",
                "title": oversized,
                "url": "https://twocomms.shop/product/kharkiv/",
                "source_message_ids": [str(value) for value in range(50)] + [{"nested": 1}],
                "variant_candidates": [
                    {"id": "4", "color": oversized, "sku": oversized, "nested": {"x": 1}},
                ],
                "unexpected": {"secret": oversized},
            }],
            "order_draft": {
                "items": [{
                    "product_id": "17",
                    "title": oversized,
                    "qty": "2",
                    "size": "XS",
                    "fit": "oversize",
                    "price_evidence_message_ids": [str(value) for value in range(50)],
                    "catalog": {
                        "product_id": "17",
                        "title": oversized,
                        "url": "https://twocomms.shop/product/kharkiv/",
                        "unexpected": {"secret": oversized},
                    },
                    "unexpected": {"secret": oversized},
                }],
                "quoted_total": {"nested": oversized},
                "packaging_preference": oversized,
                "delivery": {
                    "full_name": oversized,
                    "phone": ["nested"],
                    "city": "Харків",
                    "office": "Поштомат 21586",
                    "unexpected": {"secret": oversized},
                },
                "uncertainty_reasons": [oversized, {"nested": oversized}],
            },
        }
        self.pending.save(update_fields=["evidence", "updated_at"])

        data = self.client.get(reverse("management_bot_orders_workspace_api")).json()
        item = next(row for row in data["items"] if row["review_id"] == self.pending.id)
        media = item["media"]["receipts"][0]
        match = item["draft"]["catalog_candidates"][0]
        draft_item = item["draft"]["items"][0]
        delivery = item["draft"]["delivery"]

        self.assertEqual(set(media), {
            "role", "source_message_id", "product_id", "product_title", "url",
        })
        self.assertEqual(media["source_message_id"], 42)
        self.assertEqual(media["product_id"], 17)
        self.assertLessEqual(len(media["product_title"]), 240)
        self.assertEqual(set(match), {
            "status", "product_id", "title", "url", "source_message_ids",
            "variant_candidates",
        })
        self.assertEqual(match["product_id"], 17)
        self.assertEqual(match["source_message_ids"], list(range(20)))
        self.assertEqual(
            set(match["variant_candidates"][0]),
            {"id", "color", "sku"},
        )
        self.assertLessEqual(len(match["variant_candidates"][0]["color"]), 80)
        self.assertEqual(set(draft_item), {
            "product_id", "title", "qty", "size", "fit",
            "price_evidence_message_ids", "catalog",
        })
        self.assertEqual(draft_item["qty"], 2)
        self.assertEqual(draft_item["price_evidence_message_ids"], list(range(20)))
        self.assertNotIn("unexpected", draft_item["catalog"])
        self.assertEqual(set(delivery), {"full_name", "city", "office"})
        self.assertLessEqual(len(delivery["full_name"]), 180)
        self.assertEqual(item["draft"]["quoted_total"], "")
        self.assertLessEqual(len(item["draft"]["packaging_preference"]), 160)
        self.assertEqual(len(item["draft"]["uncertainty_reasons"]), 1)
        self.assertLessEqual(len(item["draft"]["uncertainty_reasons"][0]), 240)

    def test_all_workspace_includes_provider_attributed_order_without_review(self):
        from management.ig_bot_models import IgOrderAttribution
        from orders.models import Order

        order = Order.objects.create(
            full_name="Іван Петренко",
            phone="380501112233",
            city="Харків",
            np_office="Відділення №1",
            total_sum=Decimal("1200.00"),
            payment_status="paid",
            source="manual",
            sale_source="Instagram",
        )
        IgOrderAttribution.objects.create(
            order=order,
            client=self.customer,
            creation_mode="provider_auto",
            payment_source="provider_projection",
            negotiated_total=Decimal("1200.00"),
            price_source="conversation_accepted",
            item_provenance=[{"title": "Kharkiv Pink", "qty": 1, "fit": "classic"}],
        )

        data = self.client.get(
            reverse("management_bot_orders_workspace_api") + "?view=all"
        ).json()

        provider_card = next(item for item in data["items"] if item["order"].get("id") == order.id)
        self.assertIsNone(provider_card["review_id"])
        self.assertEqual(provider_card["approval"]["state"], "confirmed")
        self.assertEqual(provider_card["payment"]["provider_truth"], "confirmed")
        self.assertEqual(provider_card["draft"]["items"][0]["fit"], "classic")
        self.assertEqual(data["counts"], {"action": 2, "confirmed": 2, "all": 3})

    def test_order_creation_mode_distinguishes_created_new_and_linked_existing(self):
        from management.ig_bot_models import IgOrderAttribution
        from orders.models import Order

        def make_order(total):
            return Order.objects.create(
                full_name="Іван Петренко",
                phone="380501112233",
                city="Харків",
                np_office="Відділення №1",
                total_sum=Decimal(total),
                source="manual",
                sale_source="Instagram",
            )

        created_order = make_order("900.00")
        self.confirmed.order = created_order
        self.confirmed.save(update_fields=["order", "updated_at"])
        IgOrderAttribution.objects.create(
            order=created_order,
            client=self.customer,
            payment_review=self.confirmed,
            creation_mode="manager_review",
            payment_source="manager_verified",
        )
        linked_review = IgPaymentConfirmationReview.objects.create(
            client=self.customer,
            dedupe_key="orders-api-linked-existing",
            status=IgPaymentConfirmationReview.Status.CONFIRMED,
        )
        linked_order = make_order("1100.00")
        linked_review.order = linked_order
        linked_review.save(update_fields=["order", "updated_at"])
        IgOrderAttribution.objects.create(
            order=linked_order,
            client=self.customer,
            payment_review=linked_review,
            creation_mode="linked_existing",
            payment_source="manager_verified",
        )

        data = self.client.get(
            reverse("management_bot_orders_workspace_api") + "?view=confirmed"
        ).json()
        states = {item["review_id"]: item["approval"]["state"] for item in data["items"]}

        self.assertEqual(states[self.confirmed.id], "created_new")
        self.assertEqual(states[linked_review.id], "linked_existing")

    def test_get_endpoints_keep_unsuperseded_review_history_read_only(self):
        """Legacy repair is explicit; read endpoints do not mutate review history."""
        from management.ig_bot_models import IgOrderAttribution
        from management.services.ig_payment_review import reconcile_duplicate_payment_review
        from orders.models import Order

        evidence = {
            "claim_anchor": "a" * 64,
            "amount_evidence": [
                {"kind": "payment_evidence", "amount": "2100", "message_id": 237}
            ],
            "media": [
                {"role": "receipt", "message_id": 238, "url": "https://cdn.test/receipt.jpg"}
            ],
            "order_draft": {
                "quoted_total": "2100",
                "currency": "UAH",
                "items": [
                    {"title": "SXS", "size": "S", "qty": 1, "unit_price": "1050"},
                    {"title": "SXS", "size": "XS", "qty": 1, "unit_price": "1050"},
                ],
                "delivery": {"city": "Харків", "office": "Вокзальна"},
            },
        }
        order = Order.objects.create(
            full_name="Яна",
            phone="380502034719",
            city="Харків",
            np_office="Вокзальна",
            total_sum=Decimal("2100.00"),
            payment_status="paid",
        )
        canonical = IgPaymentConfirmationReview.objects.create(
            client=self.customer,
            dedupe_key="canonical-payment-review",
            status=IgPaymentConfirmationReview.Status.CONFIRMED,
            order=order,
            evidence=evidence,
            watermark_message_id=242,
        )
        IgOrderAttribution.objects.create(
            order=order,
            client=self.customer,
            payment_review=canonical,
            creation_mode="linked_existing",
            payment_source="manager_verified",
        )
        duplicate = IgPaymentConfirmationReview.objects.create(
            client=self.customer,
            dedupe_key="older-watermark-duplicate",
            status=IgPaymentConfirmationReview.Status.CONFIRMED,
            evidence=evidence,
            watermark_message_id=238,
        )
        IgPaymentReviewDecision.objects.create(
            review=duplicate,
            client=self.customer,
            decision=IgPaymentReviewDecision.Decision.MANAGER_VERIFIED,
            verification_source="manager",
            verification_scope=IgPaymentReviewDecision.VerificationScope.FULL_PAYMENT,
            confirmed_amount=Decimal("2100.00"),
            amount_source="manager_input",
            amount_evidence_message_ids=[237],
            actor=self.admin,
            actor_source=IgPaymentReviewDecision.ActorSource.MANAGEMENT_USER,
            actor_external_id=str(self.admin.pk),
            review_status_before=IgPaymentConfirmationReview.Status.PENDING,
            review_status_after=IgPaymentConfirmationReview.Status.CONFIRMED,
        )
        response = self.client.get(
            reverse("management_bot_orders_workspace_api")
            + f"?view=action&review={duplicate.pk}",
            secure=True,
        )
        self.assertEqual(response.status_code, 200, response.content)

        candidates = self.client.get(
            reverse("management_bot_order_candidates_api"),
            {"client_id": self.customer.pk, "review_id": duplicate.pk},
            secure=True,
        )
        self.assertEqual(candidates.status_code, 200, candidates.content)

        detail = self.client.get(
            reverse("management_bot_client_detail_api", args=[self.customer.pk]),
            secure=True,
        )
        self.assertEqual(detail.status_code, 200, detail.content)

        duplicate.refresh_from_db()
        self.assertEqual(duplicate.status, IgPaymentConfirmationReview.Status.CONFIRMED)
        self.assertIsNone(duplicate.order_id)
        self.assertIsNone(duplicate.superseded_by_id)

        self.assertEqual(reconcile_duplicate_payment_review(duplicate).pk, canonical.pk)
        duplicate.refresh_from_db()
        self.assertEqual(duplicate.status, IgPaymentConfirmationReview.Status.SUPERSEDED)
        self.assertEqual(duplicate.superseded_by_id, canonical.pk)

        selected = self.client.get(
            reverse("management_bot_orders_workspace_api")
            + f"?view=action&review={duplicate.pk}",
            secure=True,
        )
        self.assertEqual(selected.status_code, 200, selected.content)
        selected_data = selected.json()
        self.assertEqual(selected_data["selected_review_id"], canonical.pk)
        self.assertEqual(
            [item["review_id"] for item in selected_data["items"]],
            [canonical.pk],
        )

        detail = self.client.get(
            reverse("management_bot_client_detail_api", args=[self.customer.pk]),
            secure=True,
        )
        self.assertEqual(detail.status_code, 200, detail.content)
        detail_data = detail.json()
        self.assertEqual(detail_data["review"]["total_count"], 3)
        self.assertEqual(detail_data["orders"]["review_count"], 3)
        self.assertIn(canonical.pk, [item["review_id"] for item in detail_data["review"]["history"]])
        self.assertNotIn(duplicate.pk, [item["review_id"] for item in detail_data["review"]["history"]])

    def test_legacy_provider_attempt_is_not_promoted_to_confirmed_truth(self):
        from management.ig_bot_models import IgOrderAttribution
        from orders.models import Order

        order = Order.objects.create(
            full_name="Іван Петренко",
            phone="380501112233",
            city="Харків",
            np_office="Відділення №1",
            total_sum=Decimal("700.00"),
            source="manual",
            sale_source="Instagram",
        )
        IgOrderAttribution.objects.create(
            order=order,
            client=self.customer,
            creation_mode="provider_auto",
            payment_source="provider_attempt",
        )

        data = self.client.get(
            reverse("management_bot_orders_workspace_api") + "?view=all"
        ).json()
        card = next(item for item in data["items"] if item["order"].get("id") == order.id)

        self.assertEqual(card["payment"]["provider_truth"], "unverified")
        self.assertFalse(card["payment"]["authoritative_for_fulfillment"])

    def test_orphaned_review_attribution_remains_visible_as_order_card(self):
        from management.ig_bot_models import IgOrderAttribution
        from orders.models import Order

        order = Order.objects.create(
            full_name="Іван Петренко",
            phone="380501112233",
            city="Харків",
            np_office="Відділення №1",
            total_sum=Decimal("800.00"),
            source="manual",
            sale_source="Instagram",
        )
        orphan_review = IgPaymentConfirmationReview.objects.create(
            client=self.customer,
            dedupe_key="orphan-review-attribution",
            status=IgPaymentConfirmationReview.Status.CONFIRMED,
            order=order,
        )
        attribution = IgOrderAttribution.objects.create(
            order=order,
            client=self.customer,
            payment_review=orphan_review,
            creation_mode="linked_existing",
            payment_source="manager_verified",
        )
        orphan_review.delete()
        self.assertTrue(IgOrderAttribution.objects.filter(pk=attribution.pk).exists())

        data = self.client.get(
            reverse("management_bot_orders_workspace_api") + "?view=all"
        ).json()

        self.assertTrue(any(item["order"].get("id") == order.id for item in data["items"]))


@MGMT
class ClientPauseResumeApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("adm3", password="x", is_staff=True)
        self.client.force_login(self.admin)
        self.c = IgClient.get_or_create_for_sender("igPause")

    def test_pause(self):
        r = self.client.post(reverse("management_bot_client_pause_api", args=[self.c.id]))
        self.assertEqual(r.status_code, 200)
        self.c.refresh_from_db()
        self.assertTrue(self.c.bot_paused)

    def test_resume_clears_takeover(self):
        self.c.bot_paused = True
        self.c.manager_takeover = True
        self.c.save()
        r = self.client.post(reverse("management_bot_client_resume_api", args=[self.c.id]))
        self.assertEqual(r.status_code, 200)
        self.c.refresh_from_db()
        self.assertFalse(self.c.bot_paused)
        self.assertFalse(self.c.manager_takeover)

    def test_opt_out_requires_explicit_manual_consent_and_audits_opt_in(self):
        self.c.bot_paused = True
        self.c.paused_reason = "opt_out"
        self.c.opted_out_at = timezone.now()
        self.c.opt_out_message_id = 123
        self.c.save(update_fields=[
            "bot_paused", "paused_reason", "opted_out_at", "opt_out_message_id", "updated_at",
        ])
        url = reverse("management_bot_client_resume_api", args=[self.c.id])

        refused = self.client.post(url)

        self.assertEqual(refused.status_code, 409)
        self.assertTrue(refused.json()["requires_opt_in_confirmation"])
        self.c.refresh_from_db()
        self.assertTrue(self.c.bot_paused)
        self.assertIsNone(self.c.opted_in_at)

        accepted = self.client.post(url, {"confirm_opt_in": "1"})

        self.assertEqual(accepted.status_code, 200)
        self.c.refresh_from_db()
        self.assertFalse(self.c.bot_paused)
        self.assertEqual(self.c.opted_in_by_id, self.admin.id)
        self.assertGreaterEqual(self.c.opted_in_at, self.c.opted_out_at)
        self.assertTrue(
            InstagramBotLog.objects.filter(event="manual_opt_in", detail__contains=f"user={self.admin.id}").exists()
        )


@MGMT
class ClientDetailCursorTests(TestCase):
    """Фаза 3: live chat — інкрементальна дозагрузка переписки через after_id."""

    def setUp(self):
        self.admin = User.objects.create_user("adm_cur", password="x", is_staff=True)
        self.client.force_login(self.admin)
        self.c = IgClient.get_or_create_for_sender("igCur")
        self.m0 = InstagramBotMessage.objects.create(
            sender_id="igCur", client=self.c, role="user", text="саме перше", mid="cur0"
        )
        self.m1 = InstagramBotMessage.objects.create(
            sender_id="igCur", client=self.c, role="user", text="перше", mid="cur1"
        )
        self.m2 = InstagramBotMessage.objects.create(
            sender_id="igCur", client=self.c, role="model", text="відповідь", mid="cur2"
        )

    def test_detail_messages_have_ids_and_last_id(self):
        r = self.client.get(reverse("management_bot_client_detail_api", args=[self.c.id]))
        data = r.json()
        self.assertTrue(all("id" in m for m in data["messages"]))
        self.assertEqual(data["last_message_id"], self.m2.id)

    def test_detail_prefers_provider_message_time_with_local_fallback(self):
        provider_time = timezone.now() - timedelta(days=30)
        self.m1.provider_created_at = provider_time
        self.m1.save(update_fields=["provider_created_at"])

        data = self.client.get(
            reverse("management_bot_client_detail_api", args=[self.c.id])
        ).json()
        messages = {message["id"]: message for message in data["messages"]}

        self.assertEqual(messages[self.m1.id]["time"], provider_time.isoformat())
        self.assertEqual(messages[self.m2.id]["time"], self.m2.created_at.isoformat())

    def test_detail_after_id_returns_only_new_messages(self):
        url = reverse("management_bot_client_detail_api", args=[self.c.id]) + f"?after_id={self.m1.id}"
        data = self.client.get(url).json()
        self.assertEqual([m["text"] for m in data["messages"]], ["відповідь"])
        self.assertEqual(data["last_message_id"], self.m2.id)
        self.assertEqual(data["stage"], IgClient.Stage.NEW)
        self.assertEqual(data["stage_label"], "Написав")
        self.assertEqual(len(data["funnel"]), len(IgClient.FUNNEL_ORDER))

    def test_detail_after_latest_returns_empty(self):
        url = reverse("management_bot_client_detail_api", args=[self.c.id]) + f"?after_id={self.m2.id}"
        data = self.client.get(url).json()
        self.assertEqual(data["messages"], [])
        self.assertEqual(data["last_message_id"], self.m2.id)

    def test_detail_before_id_returns_older_messages_with_cursor_metadata(self):
        url = reverse("management_bot_client_detail_api", args=[self.c.id]) + f"?before_id={self.m1.id}"
        data = self.client.get(url).json()

        self.assertEqual([message["id"] for message in data["messages"]], [self.m0.id])
        self.assertEqual(data["oldest_message_id"], self.m0.id)
        self.assertEqual(data["newest_message_id"], self.m0.id)
        self.assertFalse(data["has_older"])

    def test_initial_detail_exposes_older_history_cursor(self):
        for index in range(301):
            InstagramBotMessage.objects.create(
                sender_id="igCur",
                client=self.c,
                role="user",
                text=f"history-{index}",
                mid=f"history-{index}",
            )

        data = self.client.get(
            reverse("management_bot_client_detail_api", args=[self.c.id])
        ).json()

        self.assertEqual(len(data["messages"]), 300)
        self.assertTrue(data["has_older"])
        self.assertEqual(data["oldest_message_id"], data["messages"][0]["id"])
