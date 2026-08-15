from dataclasses import replace
from datetime import timedelta
import inspect
import json
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from management.models import (
    IgClient,
    IgCommercialEpisode,
    IgFollowCtaDecision,
    IgFollowState,
    InstagramBotMessage,
    InstagramBotSettings,
)
from management.services import ig_follow_cta
from management.services.ig_follow_state import FollowStateView


class FollowLiveReplyContractTests(TestCase):
    def setUp(self):
        self.now = timezone.now().replace(microsecond=0)
        self.client = IgClient.objects.create(
            igsid="follow-live-client",
            language="uk",
            stage=IgClient.Stage.PAYMENT_PENDING,
            first_contact_at=self.now - timedelta(hours=1),
            last_message_at=self.now,
        )
        self.episode = IgCommercialEpisode.objects.create(
            client=self.client,
            sequence=1,
            materialization_key="episode:follow-live:1",
            opened_watermark_message_id=0,
        )
        self.client.current_commercial_episode = self.episode
        self.client.save(update_fields=["current_commercial_episode", "updated_at"])
        self.message = InstagramBotMessage.objects.create(
            sender_id=self.client.igsid,
            client=self.client,
            role=InstagramBotMessage.Role.USER,
            text="Я ще подумаю",
            status=InstagramBotMessage.Status.DONE,
        )
        IgFollowState.objects.create(
            client=self.client,
            state=IgFollowState.State.NOT_FOLLOWING,
            revision=4,
            observed_at=self.now,
            expires_at=self.now + timedelta(hours=1),
            last_result=IgFollowState.CheckResult.KNOWN,
        )
        self.view = FollowStateView(
            state=IgFollowState.State.NOT_FOLLOWING,
            last_known_state=IgFollowState.State.NOT_FOLLOWING,
            fresh=True,
            stale=False,
            revision=4,
            observed_at=self.now,
            first_observed_following_at=None,
            source="instagram_login",
            last_result=IgFollowState.CheckResult.KNOWN,
            error_kind="",
            next_retry_at=None,
        )
        self.base = "Добре, я поруч, якщо захочете уточнити розмір."
        self.candidate = (
            "Якщо вам близький наш підхід, будемо раді бачити вас серед підписників."
        )

    def _opportunity(self, *, trigger_key=""):
        with patch(
            "management.services.ig_follow_cta.effective_follow_state",
            return_value=self.view,
        ), patch(
            "management.services.ig_follow_cta._latest_hesitation_analysis",
            return_value=object(),
        ):
            opportunity = ig_follow_cta.evaluate_follow_opportunity(
                client=self.client,
                opportunity=IgFollowCtaDecision.Opportunity.HESITATION,
                episode=self.episode,
                source_message=self.message,
                base_text=self.base,
                now=self.now,
            )
        return replace(opportunity, trigger_key=trigger_key) if trigger_key else opportunity

    def test_eligible_reply_uses_one_exact_combined_snapshot_and_receipt(self):
        decision = ig_follow_cta.prepare_follow_decision(
            self._opportunity(),
            candidate_text=self.candidate,
        )
        with patch(
            "management.services.ig_follow_cta.effective_follow_state",
            return_value=self.view,
        ), patch(
            "management.services.ig_follow_cta._latest_hesitation_analysis",
            return_value=object(),
        ):
            authorized = ig_follow_cta.authorize_follow_cta(
                decision.pk,
                current_base_text=self.base,
                now=self.now,
            )
        self.assertIsNotNone(authorized)
        self.assertEqual(authorized.final_text, f"{self.base} {self.candidate}")
        self.assertEqual(len(ig_follow_cta._split_for_send(authorized.final_text)), 1)
        ig_follow_cta.finalize_follow_delivery(
            decision.pk,
            outcome="sent",
            provider_message_ids=("mid-live",),
            now=self.now,
        )
        decision.refresh_from_db()
        self.assertEqual(decision.state, IgFollowCtaDecision.State.SENT)
        self.assertEqual(decision.final_text, authorized.final_text)
        self.assertEqual(decision.provider_message_ids, ["mid-live"])

    def test_new_inbound_or_follow_revision_change_removes_only_cta(self):
        first = ig_follow_cta.prepare_follow_decision(
            self._opportunity(trigger_key="live:new-inbound"),
            candidate_text=self.candidate,
        )
        InstagramBotMessage.objects.create(
            sender_id=self.client.igsid,
            client=self.client,
            role=InstagramBotMessage.Role.USER,
            text="І ще одне питання",
            status=InstagramBotMessage.Status.DONE,
        )
        with patch(
            "management.services.ig_follow_cta.effective_follow_state",
            return_value=self.view,
        ), patch(
            "management.services.ig_follow_cta._latest_hesitation_analysis",
            return_value=object(),
        ):
            self.assertIsNone(
                ig_follow_cta.authorize_follow_cta(
                    first.pk,
                    current_base_text=self.base,
                    now=self.now,
                )
            )
        self.assertEqual(self.base, first.base_text)
        ig_follow_cta.finalize_follow_delivery(
            first.pk,
            outcome="cancelled_before_io",
            now=self.now,
        )

        InstagramBotMessage.objects.filter(
            client=self.client,
            text="І ще одне питання",
        ).delete()
        second = ig_follow_cta.prepare_follow_decision(
            self._opportunity(trigger_key="live:revision"),
            candidate_text=self.candidate,
        )
        following = replace(
            self.view,
            state=IgFollowState.State.FOLLOWING,
            last_known_state=IgFollowState.State.FOLLOWING,
            revision=5,
        )
        with patch(
            "management.services.ig_follow_cta.effective_follow_state",
            return_value=following,
        ), patch(
            "management.services.ig_follow_cta._latest_hesitation_analysis",
            return_value=object(),
        ):
            self.assertIsNone(
                ig_follow_cta.authorize_follow_cta(
                    second.pk,
                    current_base_text=self.base,
                    now=self.now,
                )
            )

    def test_invalid_candidate_keeps_base_reply_and_never_reserves(self):
        decision = ig_follow_cta.prepare_follow_decision(
            self._opportunity(trigger_key="live:invalid"),
            candidate_text="Підпишіться і отримайте 10%: https://twocomms.shop",
        )
        self.assertEqual(decision.state, IgFollowCtaDecision.State.SUPPRESSED)
        self.assertEqual(decision.final_text, "")
        self.assertEqual(decision.base_text, self.base)
        self.assertIsNone(
            ig_follow_cta.authorize_follow_cta(
                decision.pk,
                current_base_text=self.base,
                now=self.now,
            )
        )

    def test_timeout_before_io_releases_but_after_io_is_ambiguous(self):
        before = ig_follow_cta.prepare_follow_decision(
            self._opportunity(trigger_key="live:before-io"),
            candidate_text=self.candidate,
        )
        with patch(
            "management.services.ig_follow_cta.effective_follow_state",
            return_value=self.view,
        ), patch(
            "management.services.ig_follow_cta._latest_hesitation_analysis",
            return_value=object(),
        ):
            self.assertIsNotNone(
                ig_follow_cta.authorize_follow_cta(
                    before.pk,
                    current_base_text=self.base,
                    now=self.now,
                )
            )
        ig_follow_cta.finalize_follow_delivery(
            before.pk,
            outcome="cancelled_before_io",
            now=self.now,
        )
        before.refresh_from_db()
        self.assertEqual(before.state, IgFollowCtaDecision.State.CANCELLED)
        self.assertIsNone(before.episode_slot_key)

        after = ig_follow_cta.prepare_follow_decision(
            self._opportunity(trigger_key="live:after-io"),
            candidate_text=self.candidate,
        )
        with patch(
            "management.services.ig_follow_cta.effective_follow_state",
            return_value=self.view,
        ), patch(
            "management.services.ig_follow_cta._latest_hesitation_analysis",
            return_value=object(),
        ):
            self.assertIsNotNone(
                ig_follow_cta.authorize_follow_cta(
                    after.pk,
                    current_base_text=self.base,
                    now=self.now,
                )
            )
        ig_follow_cta.finalize_follow_delivery(
            after.pk,
            outcome="provider_io_started",
            now=self.now,
        )
        ig_follow_cta.finalize_follow_delivery(
            after.pk,
            outcome="cancelled_before_io",
            now=self.now,
        )
        after.refresh_from_db()
        self.assertEqual(after.state, IgFollowCtaDecision.State.AMBIGUOUS)

    def test_provider_boundary_revalidates_follow_revision_and_releases_unsent_slot(self):
        decision = ig_follow_cta.prepare_follow_decision(
            self._opportunity(trigger_key="live:provider-boundary-followed"),
            candidate_text=self.candidate,
        )
        with patch(
            "management.services.ig_follow_cta.effective_follow_state",
            return_value=self.view,
        ), patch(
            "management.services.ig_follow_cta._latest_hesitation_analysis",
            return_value=object(),
        ):
            authorized = ig_follow_cta.authorize_follow_cta(
                decision.pk,
                current_base_text=self.base,
                now=self.now,
            )
        self.assertIsNotNone(authorized)
        ig_follow_cta.finalize_follow_delivery(
            decision.pk,
            outcome="provider_io_started",
            now=self.now,
        )

        state = IgFollowState.objects.get(client=self.client)
        state.state = IgFollowState.State.FOLLOWING
        state.revision = 5
        state.observed_at = self.now
        state.expires_at = self.now + timedelta(hours=1)
        state.save(update_fields=["state", "revision", "observed_at", "expires_at", "updated_at"])
        following = replace(
            self.view,
            state=IgFollowState.State.FOLLOWING,
            last_known_state=IgFollowState.State.FOLLOWING,
            revision=5,
        )
        with patch(
            "management.services.ig_follow_cta.effective_follow_state",
            return_value=following,
        ), patch(
            "management.services.ig_follow_cta._latest_hesitation_analysis",
            return_value=object(),
        ):
            with ig_follow_cta.follow_provider_request_boundary(
                authorized,
                now=self.now,
            ) as allowed:
                self.assertFalse(allowed)

        decision.refresh_from_db()
        self.assertEqual(decision.state, IgFollowCtaDecision.State.CANCELLED)
        self.assertIsNone(decision.provider_io_started_at)
        self.assertIsNone(decision.episode_slot_key)
        self.assertIsNone(decision.sent_scope_key)
        self.assertEqual(decision.lease_token, "")

    def test_provider_boundary_allows_unchanged_reserved_decision(self):
        decision = ig_follow_cta.prepare_follow_decision(
            self._opportunity(trigger_key="live:provider-boundary-current"),
            candidate_text=self.candidate,
        )
        with patch(
            "management.services.ig_follow_cta.effective_follow_state",
            return_value=self.view,
        ), patch(
            "management.services.ig_follow_cta._latest_hesitation_analysis",
            return_value=object(),
        ):
            authorized = ig_follow_cta.authorize_follow_cta(
                decision.pk,
                current_base_text=self.base,
                now=self.now,
            )
        self.assertIsNotNone(authorized)
        ig_follow_cta.finalize_follow_delivery(
            decision.pk,
            outcome="provider_io_started",
            now=self.now,
        )

        with patch(
            "management.services.ig_follow_cta.effective_follow_state",
            return_value=self.view,
        ), patch(
            "management.services.ig_follow_cta._latest_hesitation_analysis",
            return_value=object(),
        ):
            with ig_follow_cta.follow_provider_request_boundary(
                authorized,
                now=self.now,
            ) as allowed:
                self.assertTrue(allowed)

        decision.refresh_from_db()
        self.assertEqual(decision.state, IgFollowCtaDecision.State.RESERVED)
        self.assertIsNotNone(decision.provider_io_started_at)
        self.assertEqual(decision.lease_token, authorized.lease_token)

    def test_live_worker_wires_final_provider_boundary_and_base_reply_fallback(self):
        from management.services import instagram_bot

        source = inspect.getsource(instagram_bot._process_one_inside_reply_boundary)
        self.assertIn("follow_provider_request_boundary", source)
        self.assertIn("provider_request_boundary_factory=", source)
        self.assertIn("_follow_boundary_requires_base_fallback", source)

    def test_only_pre_request_follow_boundary_rejection_uses_base_fallback(self):
        from management.services.instagram_bot import (
            ProviderDeliveryReceipt,
            _follow_boundary_requires_base_fallback,
        )

        rejected = ProviderDeliveryReceipt(
            ok=False,
            kind="cancelled",
            hint="provider request boundary rejected the send",
            planned_chunk_count=1,
            delivered_chunk_count=0,
            failure_boundary="chunk:1:provider_request_rejected",
        )
        self.assertTrue(
            _follow_boundary_requires_base_fallback(
                rejected,
                follow_authorized=object(),
            )
        )
        self.assertFalse(
            _follow_boundary_requires_base_fallback(
                replace(rejected, delivered_chunk_count=1),
                follow_authorized=object(),
            )
        )
        self.assertFalse(
            _follow_boundary_requires_base_fallback(
                replace(rejected, kind="unknown"),
                follow_authorized=object(),
            )
        )
        self.assertFalse(
            _follow_boundary_requires_base_fallback(
                rejected,
                follow_authorized=None,
            )
        )

    @patch("management.services.instagram_bot._provider_account_id", return_value="ig-account")
    @patch("management.services.instagram_bot.get_page_token", return_value="page-token")
    @patch(
        "management.services.instagram_bot._provider_http",
        return_value=(200, '{"message_id":"mid-base-only"}'),
    )
    def test_safe_boundary_downgrade_sends_and_persists_exact_base_text_once(
        self,
        provider_http,
        _page_token,
        _account_id,
    ):
        from management.services import instagram_bot

        decision = ig_follow_cta.prepare_follow_decision(
            self._opportunity(trigger_key="live:provider-boundary-base-fallback"),
            candidate_text=self.candidate,
        )
        with patch(
            "management.services.ig_follow_cta.effective_follow_state",
            return_value=self.view,
        ), patch(
            "management.services.ig_follow_cta._latest_hesitation_analysis",
            return_value=object(),
        ):
            authorized = ig_follow_cta.authorize_follow_cta(
                decision.pk,
                current_base_text=self.base,
                now=self.now,
            )
        self.assertIsNotNone(authorized)

        following = replace(
            self.view,
            state=IgFollowState.State.FOLLOWING,
            last_known_state=IgFollowState.State.FOLLOWING,
            revision=5,
        )
        marker_calls = []

        def mark_provider_io_started():
            marker_calls.append("marker")
            ig_follow_cta.finalize_follow_delivery(
                decision.pk,
                outcome="provider_io_started",
                now=self.now,
            )
            return True

        with patch(
            "management.services.ig_follow_cta.effective_follow_state",
            return_value=following,
        ), patch(
            "management.services.ig_follow_cta._latest_hesitation_analysis",
            return_value=object(),
        ):
            receipt = instagram_bot.send_text(
                InstagramBotSettings.load(),
                self.client.igsid,
                authorized.final_text,
                provider_io_started_callback=mark_provider_io_started,
                provider_request_boundary_factory=lambda **_kwargs: (
                    ig_follow_cta.follow_provider_request_boundary(
                        authorized,
                        now=self.now,
                    )
                ),
                return_receipt=True,
            )

        provider_http.assert_called_once()
        payload = json.loads(provider_http.call_args.kwargs["data"])
        self.assertEqual(payload["message"]["text"], self.base)
        self.assertTrue(receipt.ok)
        self.assertEqual(receipt.provider_message_ids, ("mid-base-only",))
        self.assertEqual(receipt.request_text, self.base)
        self.assertEqual(marker_calls, ["marker"])

        self.message.status = InstagramBotMessage.Status.PROCESSING
        self.message.save(update_fields=["status"])
        instagram_bot._persist_reply_delivery_evidence(
            self.message,
            original_text=receipt.request_text,
            planned_chunk_count=receipt.planned_chunk_count,
            delivered_chunk_count=receipt.delivered_chunk_count,
            provider_message_ids=receipt.provider_message_ids,
        )
        self.message.refresh_from_db()
        self.assertEqual(self.message.delivery_original_text, self.base)
        self.assertEqual(self.message.delivery_provider_message_ids, ["mid-base-only"])

        decision.refresh_from_db()
        self.assertEqual(decision.state, IgFollowCtaDecision.State.CANCELLED)
        self.assertIsNone(decision.provider_io_started_at)

    def test_stale_authorization_cannot_mutate_a_replaced_lease(self):
        decision = ig_follow_cta.prepare_follow_decision(
            self._opportunity(trigger_key="live:stale-authorization"),
            candidate_text=self.candidate,
        )
        with patch(
            "management.services.ig_follow_cta.effective_follow_state",
            return_value=self.view,
        ), patch(
            "management.services.ig_follow_cta._latest_hesitation_analysis",
            return_value=object(),
        ):
            authorized = ig_follow_cta.authorize_follow_cta(
                decision.pk,
                current_base_text=self.base,
                now=self.now,
            )
        self.assertIsNotNone(authorized)

        replacement_lease = "replacement-worker-lease"
        IgFollowCtaDecision.objects.filter(pk=decision.pk).update(
            lease_token=replacement_lease,
        )
        signature = inspect.signature(ig_follow_cta.finalize_follow_delivery)
        self.assertIn("lease_token", signature.parameters)

        ig_follow_cta.finalize_follow_delivery(
            decision.pk,
            outcome="provider_io_started",
            lease_token=authorized.lease_token,
            now=self.now,
        )
        ig_follow_cta.finalize_follow_delivery(
            decision.pk,
            outcome="ambiguous",
            lease_token=authorized.lease_token,
            now=self.now,
        )

        decision.refresh_from_db()
        self.assertEqual(decision.state, IgFollowCtaDecision.State.RESERVED)
        self.assertEqual(decision.lease_token, replacement_lease)
        self.assertIsNone(decision.provider_io_started_at)
