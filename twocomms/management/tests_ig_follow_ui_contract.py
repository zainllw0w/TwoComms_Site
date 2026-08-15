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

