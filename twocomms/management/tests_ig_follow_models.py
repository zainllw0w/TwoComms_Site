from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from management.models import (
    IgClient,
    IgFollowCapabilityState,
    IgFollowCtaDecision,
    IgFollowObservation,
    IgFollowRefreshJob,
    IgFollowState,
)


class IgFollowModelTests(TestCase):
    def setUp(self):
        self.client_record = IgClient.objects.create(igsid="follow-model-client")

    def test_follow_state_is_one_projection_per_client_with_unknown_default(self):
        state = IgFollowState.objects.create(client=self.client_record)

        self.assertEqual(state.state, IgFollowState.State.UNKNOWN)
        self.assertEqual(state.revision, 0)
        self.assertEqual(state.refresh_generation, 0)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                IgFollowState.objects.create(client=self.client_record)

    def test_refresh_job_is_coalesced_one_per_client(self):
        job = IgFollowRefreshJob.objects.create(
            client=self.client_record,
            requested_generation=2,
            triggers=["payment"],
        )

        self.assertEqual(job.status, IgFollowRefreshJob.Status.PENDING)
        self.assertEqual(job.requested_generation, 2)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                IgFollowRefreshJob.objects.create(client=self.client_record)

    def test_observation_is_append_only(self):
        observation = IgFollowObservation.objects.create(
            client=self.client_record,
            revision=1,
            trigger="payment",
            result=IgFollowObservation.Result.KNOWN,
            observed_value=False,
            field_present=True,
            field_type="bool",
            config_fingerprint="a" * 64,
        )

        observation.trigger = "hesitation"
        with self.assertRaises(ValueError):
            observation.save(update_fields=["trigger"])
        with self.assertRaises(ValueError):
            observation.delete()
        with self.assertRaises(ValueError):
            IgFollowObservation.objects.filter(pk=observation.pk).update(
                trigger="hesitation"
            )

    def test_capability_state_has_fail_closed_defaults(self):
        capability = IgFollowCapabilityState.objects.create(singleton_key=1)

        self.assertEqual(
            capability.status,
            IgFollowCapabilityState.Status.UNKNOWN,
        )
        self.assertEqual(capability.consecutive_failures, 0)
        self.assertFalse(capability.is_probe_blocked(now=timezone.now()))

    def test_decision_identity_is_immutable_and_delete_is_blocked(self):
        decision = IgFollowCtaDecision.objects.create(
            trigger_key="payment:attempt:1",
            client=self.client_record,
            opportunity=IgFollowCtaDecision.Opportunity.PAYMENT,
            follow_state_revision=3,
            conversation_watermark=17,
            context_fingerprint="b" * 64,
            base_text="Оплату отримали.",
        )

        decision.trigger_key = "payment:attempt:2"
        with self.assertRaises(ValueError):
            decision.save(update_fields=["trigger_key"])
        with self.assertRaises(ValueError):
            decision.delete()
        with self.assertRaises(ValueError):
            IgFollowCtaDecision.objects.filter(pk=decision.pk).update(
                opportunity=IgFollowCtaDecision.Opportunity.HESITATION
            )

    def test_episode_slot_is_unique_when_reserved(self):
        IgFollowCtaDecision.objects.create(
            trigger_key="payment:attempt:3",
            client=self.client_record,
            opportunity=IgFollowCtaDecision.Opportunity.PAYMENT,
            episode_slot_key="episode:99",
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                IgFollowCtaDecision.objects.create(
                    trigger_key="hesitation:message:4",
                    client=self.client_record,
                    opportunity=IgFollowCtaDecision.Opportunity.HESITATION,
                    episode_slot_key="episode:99",
                )

    def test_nullable_episode_slot_allows_suppressed_decisions(self):
        first = IgFollowCtaDecision.objects.create(
            trigger_key="suppressed:1",
            client=self.client_record,
            opportunity=IgFollowCtaDecision.Opportunity.PAYMENT,
            state=IgFollowCtaDecision.State.SUPPRESSED,
        )
        second = IgFollowCtaDecision.objects.create(
            trigger_key="suppressed:2",
            client=self.client_record,
            opportunity=IgFollowCtaDecision.Opportunity.POST_DELIVERY,
            state=IgFollowCtaDecision.State.SUPPRESSED,
        )

        self.assertIsNone(first.episode_slot_key)
        self.assertIsNone(second.episode_slot_key)
