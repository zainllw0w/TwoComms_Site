"""Static contracts for the compact manager follow indicator.

The indicator is deliberately rendered only in the open conversation header.
These checks protect the accessibility and polling invariants without needing
to boot a browser for every Django test run.
"""

from pathlib import Path

from django.test import SimpleTestCase


class FollowIndicatorTemplateContractTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.template = (
            Path(__file__).with_name("templates")
            / "management"
            / "bot.html"
        ).read_text(encoding="utf-8")

    def test_header_indicator_has_accessible_state_and_provenance_contract(self):
        for contract in (
            "function followIndicatorSignature(follow)",
            "role','img'",
            "indicator.tabIndex=0",
            "aria-describedby",
            "data-follow-revision",
            "data-follow-signature",
            "Джерело: ",
            "Помилка перевірки: ",
            "Повторна перевірка після ",
            "Перше зафіксоване спостереження підписки: ",
        ):
            self.assertIn(contract, self.template)

    def test_incremental_poll_is_a_noop_for_an_unchanged_follow_snapshot(self):
        start = self.template.index("function updateFollowIndicator(")
        end = self.template.index("function stageCls(", start)
        source = self.template[start:end]
        self.assertIn("currentIndicator.dataset.followSignature", source)
        self.assertIn("incomingSignature", source)
        self.assertIn("return;", source)
        self.assertIn("current.replaceWith(renderFollowIndicator(follow,id))", source)

    def test_indicator_keyboard_contract_prevents_scroll_and_closes_tooltip(self):
        for contract in (
            "aria-keyshortcuts",
            "indicator.addEventListener('keydown'",
            "event.key===' '",
            "event.preventDefault()",
            "event.key==='Escape'",
            "indicator.blur()",
            "is-tooltip-dismissed",
            "bot-follow-indicator:focus + .bot-follow-tooltip",
            "@media(max-width:240px)",
            "data-url-name=\"management_bot\"",
        ):
            self.assertIn(contract, self.template)

    def test_indicator_keyboard_tooltip_contract_prevents_scroll_and_escapes(self):
        start = self.template.index("function renderFollowIndicator(")
        end = self.template.index("function updateFollowIndicator(", start)
        source = self.template[start:end]
        self.assertIn("indicator.addEventListener('keydown'", source)
        self.assertIn("event.key==='Enter'||event.key===' '", source)
        self.assertIn("event.preventDefault()", source)
        self.assertIn("event.key==='Escape'", source)
        self.assertIn("indicator.blur()", source)

    def test_management_shell_reflows_at_effective_two_hundred_percent_width(self):
        self.assertIn("@media(max-width:240px)", self.template)
        start = self.template.index("@media(max-width:240px)")
        source = self.template[start : start + 1200]
        for contract in (
            ".global-header",
            ".brand-title",
            ".bot-tabs",
            ".bot-conversation-head",
            ".bot-conversation-title-row",
        ):
            self.assertIn(contract, source)

    def test_all_visual_states_remain_distinct_and_sidebar_stays_dense(self):
        for state in (
            "fresh-following",
            "fresh-not-following",
            "stale-follow",
            "unknown-follow",
        ):
            self.assertIn(state, self.template)

        row_start = self.template.index("function reconcileClients")
        row_end = self.template.index("function currentQuery()", row_start)
        self.assertNotIn("follow-indicator", self.template[row_start:row_end])
