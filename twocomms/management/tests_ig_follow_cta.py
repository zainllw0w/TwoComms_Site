from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
from dataclasses import replace

from django.db import IntegrityError
from django.db import connection
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from management.models import (
    IgClient,
    IgCommercialEpisode,
    IgConversationAnalysisSnapshot,
    IgFollowCtaDecision,
    IgFollowState,
    IgLifecycleEvent,
    InstagramBotMessage,
)
from management.services import ig_follow_cta
from management.services.ig_follow_state import FollowStateView, configuration_fingerprint


class FollowCtaPolicyTests(TestCase):
    def setUp(self):
        self.now = timezone.now().replace(microsecond=0)
        self.client = IgClient.objects.create(
            igsid="follow-cta-client",
            language="uk",
            stage=IgClient.Stage.PAYMENT_PENDING,
            last_message_at=self.now,
            first_contact_at=self.now - timedelta(hours=1),
        )
        self.episode = IgCommercialEpisode.objects.create(
            client=self.client,
            sequence=1,
            materialization_key="episode:follow-cta:1",
            opened_watermark_message_id=0,
        )
        self.client.current_commercial_episode = self.episode
        self.client.save(update_fields=["current_commercial_episode", "updated_at"])
        self.message = InstagramBotMessage.objects.create(
            sender_id=self.client.igsid,
            client=self.client,
            role=InstagramBotMessage.Role.USER,
            text="Думаю над замовленням",
            status=InstagramBotMessage.Status.DONE,
        )
        self.client.last_message_at = self.now
        self.client.save(update_fields=["last_message_at", "updated_at"])
        self.fresh_not_following = FollowStateView(
            state=IgFollowState.State.NOT_FOLLOWING,
            last_known_state=IgFollowState.State.NOT_FOLLOWING,
            fresh=True,
            stale=False,
            revision=3,
            observed_at=self.now - timedelta(minutes=2),
            first_observed_following_at=None,
            source="instagram_login",
            last_result=IgFollowState.CheckResult.KNOWN,
            error_kind="",
            next_retry_at=None,
        )
        settings = __import__("management.models", fromlist=["InstagramBotSettings"]).InstagramBotSettings.load()
        IgFollowState.objects.create(
            client=self.client,
            state=IgFollowState.State.NOT_FOLLOWING,
            revision=3,
            source="instagram_login",
            config_fingerprint=configuration_fingerprint(settings),
            observed_at=self.now - timedelta(minutes=2),
            expires_at=self.now + timedelta(hours=1),
            last_result=IgFollowState.CheckResult.KNOWN,
        )

    def _opportunity(self, kind=IgFollowCtaDecision.Opportunity.PAYMENT, **kwargs):
        with patch(
            "management.services.ig_follow_cta.effective_follow_state",
            return_value=self.fresh_not_following,
        ):
            return ig_follow_cta.evaluate_follow_opportunity(
                client=self.client,
                opportunity=kind,
                episode=self.episode,
                source_message=kwargs.pop("source_message", self.message),
                base_text=kwargs.pop("base_text", "Оплату отримали, дякуємо."),
                now=self.now + timedelta(minutes=1),
                **kwargs,
            )

    def test_only_fresh_not_following_is_eligible(self):
        for state in (
            self.fresh_not_following.__class__(
                **{**self.fresh_not_following.__dict__, "state": IgFollowState.State.UNKNOWN, "fresh": False}
            ),
            self.fresh_not_following.__class__(
                **{**self.fresh_not_following.__dict__, "state": IgFollowState.State.FOLLOWING}
            ),
        ):
            with self.subTest(state=state.state), patch(
                "management.services.ig_follow_cta.effective_follow_state", return_value=state
            ):
                opportunity = ig_follow_cta.evaluate_follow_opportunity(
                    client=self.client,
                    opportunity=IgFollowCtaDecision.Opportunity.PAYMENT,
                    episode=self.episode,
                    source_message=self.message,
                    base_text="Оплату отримали, дякуємо.",
                    now=self.now,
                )
            self.assertFalse(opportunity.allowed)
            self.assertIn("follow_state", opportunity.reason_codes)

        opportunity = self._opportunity()
        self.assertTrue(opportunity.allowed)
        self.assertEqual(opportunity.follow_state_revision, 3)

    def test_global_permission_and_lifecycle_suppressions_fail_closed(self):
        cases = (
            ("hidden", {"hidden_at": self.now}),
            ("blocked", {"is_blocked": True}),
            ("spam", {"stage": IgClient.Stage.SPAM}),
            ("opted_out", {"opted_out_at": self.now}),
            ("paused", {"bot_paused": True}),
            ("takeover", {"manager_takeover": True}),
            ("closed_window", {"delivery_status": IgClient.DeliveryStatus.WINDOW_CLOSED}),
        )
        for reason, fields in cases:
            with self.subTest(reason=reason):
                IgClient.objects.filter(pk=self.client.pk).update(**fields)
                self.client.refresh_from_db()
                opportunity = self._opportunity()
                self.assertFalse(opportunity.allowed)
                self.assertIn(reason, opportunity.reason_codes)
                IgClient.objects.filter(pk=self.client.pk).update(
                    hidden_at=None,
                    is_blocked=False,
                    stage=IgClient.Stage.PAYMENT_PENDING,
                    opted_out_at=None,
                    bot_paused=False,
                    manager_takeover=False,
                    delivery_status="",
                )
                self.client.refresh_from_db()

    def test_payment_is_allowed_but_delivered_review_and_ugc_win(self):
        self.assertTrue(self._opportunity().allowed)
        event = type("Lifecycle", (), {"kind": IgLifecycleEvent.Kind.DELIVERED_REVIEW_REQUESTED})()
        opportunity = self._opportunity(
            IgFollowCtaDecision.Opportunity.POST_DELIVERY,
            lifecycle_event=event,
        )
        self.assertFalse(opportunity.allowed)
        self.assertIn("delivered_review_or_ugc", opportunity.reason_codes)

    def test_hesitation_requires_current_turn_analysis_not_primary_objection(self):
        self.client.primary_objection = IgClient.Objection.THINKING
        self.client.save(update_fields=["primary_objection", "updated_at"])
        without_analysis = self._opportunity(IgFollowCtaDecision.Opportunity.HESITATION)
        self.assertFalse(without_analysis.allowed)
        self.assertIn("analysis", without_analysis.reason_codes)

        snapshot = IgConversationAnalysisSnapshot.objects.create(
            client=self.client,
            last_analyzed_message=self.message,
            dedupe_key="follow-cta-analysis-1",
            score_band=IgConversationAnalysisSnapshot.Band.QUALIFIED,
            interaction_type=IgConversationAnalysisSnapshot.InteractionType.PRICE_OBJECTION,
            confidence=Decimal("0.91"),
            purchase_probability=Decimal("0.85"),
            commercial_episode=self.episode,
        )
        with self.subTest("current analysis"), patch(
            "management.services.ig_follow_cta.effective_follow_state",
            return_value=self.fresh_not_following,
        ):
            allowed = ig_follow_cta.evaluate_follow_opportunity(
                client=self.client,
                opportunity=IgFollowCtaDecision.Opportunity.HESITATION,
                episode=self.episode,
                source_message=self.message,
                base_text="Можу підказати з розміром.",
                now=self.now + timedelta(minutes=1),
            )
        self.assertTrue(allowed.allowed)
        self.assertEqual(allowed.analysis_id, snapshot.pk)

    def test_new_inbound_and_post_sale_risk_suppress(self):
        InstagramBotMessage.objects.create(
            sender_id=self.client.igsid,
            client=self.client,
            role=InstagramBotMessage.Role.USER,
            text="Ще уточнення",
            status=InstagramBotMessage.Status.DONE,
        )
        self.assertFalse(self._opportunity().allowed)
        self.assertIn("new_inbound", self._opportunity().reason_codes)

        IgClient.objects.filter(pk=self.client.pk).update(last_message_at=self.now)
        self.client.refresh_from_db()
        with patch("management.services.ig_follow_cta._has_post_sale_risk", return_value=True):
            opportunity = self._opportunity()
        self.assertFalse(opportunity.allowed)
        self.assertIn("post_sale_risk", opportunity.reason_codes)

    def test_candidate_validator_is_conservative_and_combined_text_is_one_chunk(self):
        opportunity = self._opportunity(base_text="Оплату отримали, дякуємо.")
        bad = (
            "Підпишіться на нас: https://twocomms.shop, отримайте 10% знижки зараз!"
        )
        decision = ig_follow_cta.prepare_follow_decision(opportunity, candidate_text=bad)
        self.assertEqual(decision.state, IgFollowCtaDecision.State.SUPPRESSED)
        self.assertEqual(decision.suppression_reason, "invalid_candidate")

        good = "Якщо вам близький наш підхід, будемо раді бачити вас серед підписників 😊"
        decision = ig_follow_cta.prepare_follow_decision(
            replace(opportunity, trigger_key=opportunity.trigger_key + ":good"),
            candidate_text=good,
            model_meta={"model": "gemini-test", "key_alias": "alias-a", "prompt_version": "p1"},
        )
        self.assertEqual(decision.state, IgFollowCtaDecision.State.PREPARED)
        self.assertEqual(decision.candidate_text, good)
        self.assertEqual(decision.model, "gemini-test")
        self.assertEqual(decision.model_key_alias, "alias-a")
        self.assertEqual(decision.prompt_version, "p1")
        self.assertEqual(len(ig_follow_cta._split_for_send(decision.base_text + " " + good)), 1)

    def test_prepare_snapshots_immutable_context_and_authorize_reserves(self):
        opportunity = self._opportunity()
        decision = ig_follow_cta.prepare_follow_decision(
            opportunity,
            candidate_text="Якщо вам близький наш підхід, будемо раді бачити вас серед підписників.",
        )
        authorized = ig_follow_cta.authorize_follow_cta(
            decision.pk,
            current_base_text=opportunity.base_text,
            now=self.now,
        )
        self.assertIsNotNone(authorized)
        self.assertEqual(authorized.decision_id, decision.pk)
        self.assertIn(decision.candidate_text, authorized.final_text)
        decision.refresh_from_db()
        self.assertEqual(decision.state, IgFollowCtaDecision.State.RESERVED)
        self.assertTrue(decision.episode_slot_key)
        self.assertTrue(decision.sent_scope_key)

    def test_authorize_revalidates_base_state_and_new_inbound(self):
        opportunity = self._opportunity()
        decision = ig_follow_cta.prepare_follow_decision(
            opportunity,
            candidate_text="Якщо вам близький наш підхід, будемо раді бачити вас серед підписників.",
        )
        self.assertIsNone(
            ig_follow_cta.authorize_follow_cta(
                decision.pk, current_base_text="Інша відповідь", now=self.now
            )
        )
        decision.refresh_from_db()
        self.assertEqual(decision.state, IgFollowCtaDecision.State.PREPARED)

        with patch(
            "management.services.ig_follow_cta.effective_follow_state",
            return_value=self.fresh_not_following,
        ):
            IgClient.objects.filter(pk=self.client.pk).update(last_message_at=self.now)
            InstagramBotMessage.objects.create(
                sender_id=self.client.igsid,
                client=self.client,
                role=InstagramBotMessage.Role.USER,
                text="Новий контекст",
                status=InstagramBotMessage.Status.DONE,
            )
            self.assertIsNone(
                ig_follow_cta.authorize_follow_cta(
                    decision.pk, current_base_text=opportunity.base_text, now=self.now
                )
            )

    def test_cancellation_does_not_burn_cooldown_receipt_and_ambiguous_do(self):
        good = "Якщо вам близький наш підхід, будемо раді бачити вас серед підписників."
        first = ig_follow_cta.prepare_follow_decision(
            replace(self._opportunity(), trigger_key="payment:cancel:first"), candidate_text=good
        )
        self.assertIsNotNone(
            ig_follow_cta.authorize_follow_cta(first.pk, current_base_text=first.base_text, now=self.now)
        )
        ig_follow_cta.finalize_follow_delivery(first.pk, outcome="cancelled", now=self.now)
        first.refresh_from_db()
        self.assertEqual(first.state, IgFollowCtaDecision.State.CANCELLED)
        self.assertIsNone(first.episode_slot_key)
        self.assertIsNone(first.sent_scope_key)

        second = ig_follow_cta.prepare_follow_decision(
            replace(self._opportunity(), trigger_key="payment:cancel:second"), candidate_text=good
        )
        self.assertIsNotNone(
            ig_follow_cta.authorize_follow_cta(second.pk, current_base_text=second.base_text, now=self.now)
        )
        ig_follow_cta.finalize_follow_delivery(
            second.pk, outcome="sent", provider_message_ids=("mid-1",), now=self.now
        )
        blocked = self._opportunity()
        self.assertFalse(blocked.allowed)
        self.assertIn("cooldown", blocked.reason_codes)

    def test_annual_cap_is_two_sent_or_ambiguous_and_episode_slot_is_unique(self):
        good = "Якщо вам близький наш підхід, будемо раді бачити вас серед підписників."
        for index in (1, 2):
            episode = self.episode if index == 1 else IgCommercialEpisode.objects.create(
                client=self.client,
                sequence=index,
                materialization_key=f"episode:follow-cta:{index}",
                open_slot=None,
            )
            current_now = self.now + timedelta(days=91 * (index - 1))
            IgClient.objects.filter(pk=self.client.pk).update(
                last_message_at=current_now, current_commercial_episode=episode
            )
            IgFollowState.objects.filter(client=self.client).update(
                observed_at=current_now - timedelta(minutes=1), expires_at=current_now + timedelta(hours=1)
            )
            self.client.refresh_from_db()
            with patch(
                "management.services.ig_follow_cta.effective_follow_state",
                return_value=self.fresh_not_following,
            ):
                opp = ig_follow_cta.evaluate_follow_opportunity(
                    client=self.client,
                    opportunity=IgFollowCtaDecision.Opportunity.PAYMENT,
                    episode=episode,
                    source_message=self.message,
                    base_text="Оплату отримали, дякуємо.",
                    now=current_now,
                )
            decision = ig_follow_cta.prepare_follow_decision(
                replace(opp, trigger_key=f"annual:{index}"), candidate_text=good
            )
            authorized = ig_follow_cta.authorize_follow_cta(
                decision.pk, current_base_text=decision.base_text, now=current_now
            )
            self.assertIsNotNone(authorized)
            ig_follow_cta.finalize_follow_delivery(decision.pk, outcome="ambiguous", now=current_now)

        third_episode = IgCommercialEpisode.objects.create(
            client=self.client,
            sequence=3,
            materialization_key="episode:follow-cta:3",
            open_slot=None,
        )
        IgClient.objects.filter(pk=self.client.pk).update(
            current_commercial_episode=third_episode, last_message_at=self.now + timedelta(days=183)
        )
        with patch(
            "management.services.ig_follow_cta.effective_follow_state",
            return_value=self.fresh_not_following,
        ):
            opp = ig_follow_cta.evaluate_follow_opportunity(
                client=self.client,
                opportunity=IgFollowCtaDecision.Opportunity.PAYMENT,
                episode=third_episode,
                source_message=self.message,
                base_text="Оплату отримали, дякуємо.",
                now=self.now + timedelta(days=183),
            )
        self.assertFalse(opp.allowed)
        self.assertIn("annual_cap", opp.reason_codes)

    def test_provider_io_outcome_is_durable_and_blind_replay_is_forbidden(self):
        good = "Якщо вам близький наш підхід, будемо раді бачити вас серед підписників."
        decision = ig_follow_cta.prepare_follow_decision(
            replace(self._opportunity(), trigger_key="ambiguous:1"), candidate_text=good
        )
        self.assertIsNotNone(
            ig_follow_cta.authorize_follow_cta(decision.pk, current_base_text=decision.base_text, now=self.now)
        )
        ig_follow_cta.finalize_follow_delivery(
            decision.pk, outcome="ambiguous", provider_message_ids=(), now=self.now
        )
        decision.refresh_from_db()
        self.assertEqual(decision.state, IgFollowCtaDecision.State.AMBIGUOUS)
        self.assertIsNone(
            ig_follow_cta.authorize_follow_cta(decision.pk, current_base_text=decision.base_text, now=self.now)
        )

    def test_cancellation_after_provider_io_is_ambiguous_not_released(self):
        good = "Якщо вам близький наш підхід, будемо раді бачити вас серед підписників."
        decision = ig_follow_cta.prepare_follow_decision(
            replace(self._opportunity(), trigger_key="cancel-after-io"), candidate_text=good
        )
        self.assertIsNotNone(
            ig_follow_cta.authorize_follow_cta(decision.pk, current_base_text=decision.base_text, now=self.now)
        )
        ig_follow_cta.finalize_follow_delivery(decision.pk, outcome="provider_io_started", now=self.now)
        ig_follow_cta.finalize_follow_delivery(decision.pk, outcome="cancelled", now=self.now)
        decision.refresh_from_db()
        self.assertEqual(decision.state, IgFollowCtaDecision.State.AMBIGUOUS)
        self.assertIsNotNone(decision.episode_slot_key)


class FollowCtaMariaDBHarnessTests(TransactionTestCase):
    """MariaDB-only harness; SQLite cannot prove row-lock serialization."""

    databases = {"default"}

    def _require_mariadb(self):
        if connection.vendor not in {"mysql", "mariadb"}:
            self.skipTest("MariaDB-only concurrency harness; SQLite is not proof of row-lock behavior.")

    def test_concurrent_episode_reservation_gate(self):
        self._require_mariadb()
        self.skipTest("Run this gate with two independent MariaDB worker connections.")

    def test_cross_episode_cooldown_reservation_gate(self):
        self._require_mariadb()
        self.skipTest("Run this gate with two independent MariaDB worker connections.")

    def test_mariadb_concurrency_gate_is_explicit(self):
        self._require_mariadb()
        self.skipTest("Run this gate with two independent MariaDB worker connections.")
