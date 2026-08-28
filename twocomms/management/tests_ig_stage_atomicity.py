"""Э3.2 — stage и audit event пишутся атомарно, тихого успеха больше нет."""
from unittest.mock import patch

from django.test import TestCase, TransactionTestCase

from management.models import IgClient, IgClientStageEvent
from management.services.ig_funnel_fsm import apply_stage


class AtomicStageTransitionTests(TransactionTestCase):
    """Стадия без evidence в таймлайне делает воронку недоверенной."""

    reset_sequences = True

    def setUp(self):
        self.ig_client = IgClient.get_or_create_for_sender("stage-atomic-sender")

    def test_successful_transition_writes_exactly_one_event(self):
        result = apply_stage(
            self.ig_client, IgClient.Stage.QUALIFYING, reason="inbound", actor="bot"
        )

        self.assertTrue(result.changed)
        self.ig_client.refresh_from_db()
        self.assertEqual(self.ig_client.stage, IgClient.Stage.QUALIFYING)
        events = IgClientStageEvent.objects.filter(client=self.ig_client)
        self.assertEqual(events.count(), 1)
        event = events.get()
        self.assertEqual(event.to_stage, IgClient.Stage.QUALIFYING)
        self.assertIn("inbound", event.reason)

    def test_event_write_failure_rolls_back_the_stage(self):
        """RED-репродьюсер: раньше стадия менялась, события не было, FSM молчал."""
        original_stage = self.ig_client.stage

        with patch.object(
            IgClientStageEvent.objects,
            "create",
            side_effect=RuntimeError("audit write exploded"),
        ):
            result = apply_stage(
                self.ig_client, IgClient.Stage.QUALIFYING, reason="inbound", actor="bot"
            )

        self.assertFalse(result.changed)
        self.assertEqual(result.refused, "write_failed")
        self.ig_client.refresh_from_db()
        self.assertEqual(
            self.ig_client.stage,
            original_stage,
            "стадия без evidence не должна остаться записанной",
        )
        self.assertEqual(IgClientStageEvent.objects.filter(client=self.ig_client).count(), 0)

    def test_failed_write_is_never_reported_as_success(self):
        with patch.object(
            IgClientStageEvent.objects,
            "create",
            side_effect=RuntimeError("audit write exploded"),
        ):
            result = apply_stage(
                self.ig_client, IgClient.Stage.CHECKOUT, reason="proposal", actor="bot"
            )
        self.assertFalse(result.changed)
        self.assertNotEqual(result.refused, "")


class StageGuardContractTests(TestCase):
    """Существующие гарантии FSM не должны сломаться атомарностью."""

    def setUp(self):
        self.ig_client = IgClient.get_or_create_for_sender("stage-guard-sender")

    def test_reason_is_still_required(self):
        result = apply_stage(self.ig_client, IgClient.Stage.QUALIFYING, reason="  ")
        self.assertFalse(result.changed)
        self.assertEqual(result.refused, "reason_required")
        self.assertEqual(IgClientStageEvent.objects.count(), 0)

    def test_unknown_stage_is_refused_without_writing_anything(self):
        result = apply_stage(self.ig_client, "not_a_stage", reason="x")
        self.assertFalse(result.changed)
        self.assertEqual(result.refused, "unknown_stage")
        self.assertEqual(IgClientStageEvent.objects.count(), 0)

    def test_fact_only_stage_still_requires_verified_fact(self):
        result = apply_stage(
            self.ig_client, IgClient.Stage.PAID, reason="model_said_so", actor="bot"
        )
        self.assertFalse(result.changed)
        self.assertEqual(result.refused, "fact_required")
        self.assertEqual(IgClientStageEvent.objects.count(), 0)

    def test_same_stage_is_not_an_event(self):
        apply_stage(self.ig_client, IgClient.Stage.QUALIFYING, reason="first")
        before = IgClientStageEvent.objects.count()
        result = apply_stage(self.ig_client, IgClient.Stage.QUALIFYING, reason="again")
        self.assertFalse(result.changed)
        self.assertEqual(result.refused, "same_stage")
        self.assertEqual(IgClientStageEvent.objects.count(), before)

    def test_regress_requires_an_explicit_allowance(self):
        apply_stage(self.ig_client, IgClient.Stage.CHECKOUT, reason="proposal")
        result = apply_stage(
            self.ig_client, IgClient.Stage.QUALIFYING, reason="recalculated"
        )
        self.assertFalse(result.changed)
        self.assertEqual(result.refused, "regress_not_allowed")

    def test_every_successful_transition_has_a_matching_event(self):
        stages = [IgClient.Stage.QUALIFYING, IgClient.Stage.CHECKOUT]
        for stage in stages:
            apply_stage(self.ig_client, stage, reason=f"to:{stage}")
        events = list(
            IgClientStageEvent.objects.filter(client=self.ig_client).order_by("id")
        )
        self.assertEqual(len(events), len(stages))
        self.assertEqual([event.to_stage for event in events], list(stages))
