import hashlib
import json
import threading
from datetime import timedelta
from decimal import Decimal

from django.db import close_old_connections, connection
from django.test import TestCase, TransactionTestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from unittest.mock import patch

from management.models import (
    IgAnalysisMaterialityEvent,
    IgClient,
    IgCommercialEpisode,
    IgConversationAnalysisJob,
    IgConversationAnalysisSnapshot,
    IgCustomerTurn,
    IgTurnMessage,
    InstagramBotMessage,
)
from management.services import ig_analysis_materiality as materiality
from management.tests_support import AnalysisPrivacyCleanupMixin


def _job(client, *, watermark=1):
    return IgConversationAnalysisJob.objects.create(
        client=client,
        watermark_message_id=watermark,
        due_at=timezone.now(),
        next_attempt_at=timezone.now(),
    )


def _message(client, text, *, role=InstagramBotMessage.Role.USER, artifact=None):
    return InstagramBotMessage.objects.create(
        client=client,
        sender_id=client.igsid,
        role=role,
        text=text,
        status=InstagramBotMessage.Status.DONE,
        turn_intelligence_artifact=artifact or {},
    )


def _turn(client, message, *, episode=None):
    now = timezone.now()
    turn = IgCustomerTurn.objects.create(
        client=client,
        episode=episode,
        primary_source_message=message,
        window_started_at=now,
        window_deadline=now,
        claim_state=IgCustomerTurn.ClaimState.CLAIMED,
    )
    IgTurnMessage.objects.create(
        turn=turn,
        message=message,
        ordinal=1,
        role=message.role,
    )
    return turn


def _event_digest(label):
    # Test-only semantic identity; production adapters use immutable revision
    # metadata and never customer text.
    return materiality._sha({"test_event": str(label)})


class MaterialityFunnelResetTests(TestCase):
    def test_reset_terminalizes_job_and_clears_every_claim_cursor(self):
        from management.services.ig_funnel_reset import reset_funnel

        client = IgClient.objects.create(igsid="mat-funnel-reset")
        job = IgConversationAnalysisJob.objects.create(
            client=client,
            status=IgConversationAnalysisJob.Status.PROCESSING,
            watermark_message_id=91,
            revision=7,
            due_at=timezone.now(),
            next_attempt_at=timezone.now(),
            lease_token="claimed-work",
            lease_until=timezone.now() + timedelta(minutes=5),
            claimed_watermark_message_id=91,
            claimed_revision=7,
            claimed_materiality_event_highwater=44,
            claimed_materiality_digest="a" * 64,
            claimed_authority_digest="b" * 64,
            claimed_artifact_digest="c" * 64,
        )

        result = reset_funnel(
            client_id=client.pk,
            actor=None,
            reason="materiality cursor reset regression",
        )

        self.assertTrue(result["ok"], result)
        job.refresh_from_db()
        self.assertEqual(job.status, IgConversationAnalysisJob.Status.SKIPPED)
        self.assertEqual(job.skip_reason, "funnel_reset")
        self.assertEqual(job.lease_token, "")
        self.assertIsNone(job.lease_until)
        self.assertEqual(job.claimed_watermark_message_id, 0)
        self.assertEqual(job.claimed_revision, 0)
        self.assertEqual(job.claimed_materiality_event_highwater, 0)
        self.assertEqual(job.claimed_materiality_digest, "")
        self.assertEqual(job.claimed_authority_digest, "")
        self.assertEqual(job.claimed_artifact_digest, "")


class MaterialityOffContractTests(TestCase):
    @override_settings(IG_ANALYSIS_MATERIALITY_MODE="off")
    def test_off_mode_performs_zero_ledger_or_shadow_job_writes(self):
        client = IgClient.objects.create(igsid="mat-off")
        job = _job(client)
        due_before = job.due_at

        event = materiality.record_materiality_event(
            client_id=client.pk,
            event_kind=IgAnalysisMaterialityEvent.Kind.CUSTOMER_TURN,
            event_digest="off-event",
            source_role=IgAnalysisMaterialityEvent.SourceRole.USER,
        )

        self.assertIsNone(event)
        self.assertFalse(IgAnalysisMaterialityEvent.objects.exists())
        job.refresh_from_db()
        self.assertEqual(job.materiality_digest, "")
        self.assertIsNone(job.first_unanalysed_at)
        self.assertEqual(job.due_at, due_before)

        message = _message(client, "Хочу футболку")
        turn = _turn(client, message)
        from management.services.ig_customer_turns import mark_turn_processed

        mark_turn_processed(turn.pk)
        self.assertFalse(IgAnalysisMaterialityEvent.objects.exists())

    def test_ledger_schema_has_no_customer_text_quote_or_payload(self):
        names = {
            field.name for field in IgAnalysisMaterialityEvent._meta.get_fields()
        }
        self.assertFalse(names & {"text", "quote", "payload", "raw_body"})

    @override_settings(IG_ANALYSIS_MATERIALITY_MODE="shadow")
    def test_ledger_identity_is_append_only_at_model_boundary(self):
        client = IgClient.objects.create(igsid="mat-append-only")
        _job(client)
        source = _message(client, "append-only source")
        event = materiality.record_materiality_event(
            client_id=client.pk,
            event_kind=IgAnalysisMaterialityEvent.Kind.CUSTOMER_TURN,
            event_digest=_event_digest("append-only"),
            source_role=IgAnalysisMaterialityEvent.SourceRole.USER,
            source_message_id=source.pk,
        )

        event.event_digest = "changed"
        with self.assertRaises(ValueError):
            event.save()
        with self.assertRaises(ValueError):
            IgAnalysisMaterialityEvent.objects.filter(pk=event.pk).update(
                event_digest="changed"
            )
        with self.assertRaises(ValueError):
            event.delete()


class LegacySelectorCompatibilityTests(TestCase):
    def setUp(self):
        self.now = timezone.now().replace(microsecond=0)
        self.client = IgClient.objects.create(igsid="mat-legacy-select")
        self.episode = IgCommercialEpisode.objects.create(
            client=self.client,
            sequence=1,
            open_slot=1,
            materialization_key="mat-legacy-select:episode:1",
        )
        self.client.current_commercial_episode = self.episode
        self.client.save(update_fields=["current_commercial_episode", "updated_at"])
        self.source = _message(self.client, "Я подумаю")
        self.job = _job(self.client, watermark=self.source.pk)
        self.qualifying = IgConversationAnalysisSnapshot.objects.create(
            client=self.client,
            commercial_episode=self.episode,
            last_analyzed_message=self.source,
            dedupe_key="mat-legacy-select:qualifying",
            score_band=IgConversationAnalysisSnapshot.Band.QUALIFIED,
            interaction_type=(
                IgConversationAnalysisSnapshot.InteractionType.PRICE_OBJECTION
            ),
            purchase_probability=Decimal("0.7000"),
            confidence=Decimal("0.9000"),
            analyzed_at=self.now - timedelta(minutes=2),
        )
        self.newer_unqualified = IgConversationAnalysisSnapshot.objects.create(
            client=self.client,
            commercial_episode=self.episode,
            last_analyzed_message=self.source,
            dedupe_key="mat-legacy-select:newer-unqualified",
            score_band=IgConversationAnalysisSnapshot.Band.COLD,
            interaction_type=(
                IgConversationAnalysisSnapshot.InteractionType.WHOLESALE_B2B
            ),
            purchase_probability=Decimal("0.1000"),
            confidence=Decimal("0.1000"),
            analyzed_at=self.now - timedelta(minutes=1),
        )

    def _hesitation(self):
        from management.services.ig_follow_cta import _latest_hesitation_analysis

        return _latest_hesitation_analysis(
            client=self.client,
            episode=self.episode,
            source_message=self.source,
            now=self.now,
        )

    @override_settings(
        IG_ANALYSIS_MATERIALITY_MODE="off",
        IG_ANALYSIS_CURRENT_SELECTOR_MODE="enforce",
    )
    def test_off_mode_preserves_exact_legacy_cta_even_if_read_gate_is_stale(self):
        self.assertEqual(self._hesitation().pk, self.qualifying.pk)
        self.assertEqual(
            materiality.current_analysis_snapshot(self.client).pk,
            self.newer_unqualified.pk,
        )

    @override_settings(
        IG_ANALYSIS_MATERIALITY_MODE="shadow",
        IG_ANALYSIS_CURRENT_SELECTOR_MODE="legacy",
    )
    def test_shadow_mode_does_not_enforce_freshness_on_operational_consumers(self):
        from management.services.bot_followups import _suppressed_interaction

        self.job.materiality_digest = "a" * 64
        self.job.analyzed_materiality_digest = "b" * 64
        self.job.materiality_event_highwater = 2
        self.job.analyzed_materiality_event_highwater = 1
        self.job.save()

        self.assertEqual(self._hesitation().pk, self.qualifying.pk)
        self.assertEqual(_suppressed_interaction(self.client), "wholesale_b2b")
        self.assertEqual(
            materiality.current_analysis_snapshot(self.client).pk,
            self.newer_unqualified.pk,
        )


@override_settings(IG_ANALYSIS_MATERIALITY_MODE="shadow")
class MaterialityCadenceTests(TestCase):
    def setUp(self):
        self.client = IgClient.objects.create(igsid="mat-cadence")
        self.job = _job(self.client)
        self.source = _message(self.client, "material event")

    def _record(self, suffix, at, **kwargs):
        return materiality.record_materiality_event(
            client_id=self.client.pk,
            event_kind=IgAnalysisMaterialityEvent.Kind.CUSTOMER_TURN,
            event_digest=_event_digest(f"event-{suffix}"),
            source_role=IgAnalysisMaterialityEvent.SourceRole.USER,
            source_message_id=self.source.pk,
            relevant_at=at,
            **kwargs,
        )

    def test_quiet_window_has_a_continuous_ten_minute_ceiling(self):
        start = timezone.now().replace(microsecond=0)
        behavior_before = (
            self.job.due_at,
            self.job.status,
            self.job.revision,
            self.job.watermark_message_id,
        )

        self._record("one", start)
        self.job.refresh_from_db()
        self.assertEqual(
            self.job.materiality_due_at,
            start + timedelta(seconds=90),
        )
        self._record("two", start + timedelta(minutes=5))
        self.job.refresh_from_db()
        self.assertEqual(
            self.job.materiality_due_at,
            start + timedelta(minutes=6, seconds=30),
        )
        self._record("three", start + timedelta(minutes=9, seconds=30))
        self.job.refresh_from_db()
        self.assertEqual(
            self.job.materiality_due_at,
            start + timedelta(minutes=10),
        )
        self.assertEqual(
            (
                self.job.due_at,
                self.job.status,
                self.job.revision,
                self.job.watermark_message_id,
            ),
            behavior_before,
        )

    def test_duplicate_digest_does_not_append_or_bump_job(self):
        now = timezone.now()
        first = self._record("same", now)
        self.job.refresh_from_db()
        highwater = self.job.materiality_event_highwater
        digest = self.job.materiality_digest

        duplicate = self._record("same", now + timedelta(minutes=1))

        self.assertIsNotNone(first)
        self.assertIsNone(duplicate)
        self.assertEqual(IgAnalysisMaterialityEvent.objects.count(), 1)
        self.job.refresh_from_db()
        self.assertEqual(self.job.materiality_event_highwater, highwater)
        self.assertEqual(self.job.materiality_digest, digest)

    def test_authority_event_is_immediate_and_same_truth_is_not_polled(self):
        self.job.required_state_fingerprint = "a" * 64
        self.job.revision = 10
        self.job.save(update_fields=["required_state_fingerprint", "revision"])
        now = timezone.now().replace(microsecond=0)

        first = materiality.record_authority_materiality(
            client=self.client,
            job=self.job,
            trigger="payment_truth",
            source_message_id=self.source.pk,
            now=now,
        )
        duplicate = materiality.record_authority_materiality(
            client=self.client,
            job=self.job,
            trigger="payment_truth",
            source_message_id=self.source.pk,
            now=now + timedelta(hours=12),
        )

        self.assertIsNotNone(first)
        self.assertIsNone(duplicate)
        self.job.refresh_from_db()
        self.assertEqual(self.job.materiality_due_at, now)
        self.assertEqual(self.job.authority_digest, first.authority_digest)
        self.assertNotEqual(self.job.authority_digest, "a" * 64)
        materiality_payload = json.dumps({
            "event_digest": first.event_digest,
            "authority_digest": first.authority_digest,
            "job_authority_digest": self.job.authority_digest,
            "job_materiality_digest": self.job.materiality_digest,
        })
        self.assertNotIn("a" * 64, materiality_payload)
        self.assertEqual(IgAnalysisMaterialityEvent.objects.count(), 1)

    def test_authority_a_to_b_to_a_appends_each_transition_but_dedupes_retry(self):
        now = timezone.now().replace(microsecond=0)
        identities = []
        for offset, (revision, fingerprint) in enumerate((
            (10, "a" * 64),
            (11, "b" * 64),
            (12, "a" * 64),
        )):
            self.job.revision = revision
            self.job.required_state_fingerprint = fingerprint
            self.job.save(update_fields=["revision", "required_state_fingerprint"])
            event = materiality.record_authority_materiality(
                client=self.client,
                job=self.job,
                trigger="payment_truth",
                source_message_id=self.source.pk,
                now=now + timedelta(minutes=offset),
            )
            self.assertIsNotNone(event)
            identities.append(event.authority_digest)
            retry = materiality.record_authority_materiality(
                client=self.client,
                job=self.job,
                trigger="payment_truth",
                source_message_id=self.source.pk,
                now=now + timedelta(minutes=offset, seconds=30),
            )
            self.assertIsNone(retry)

        self.assertEqual(IgAnalysisMaterialityEvent.objects.count(), 3)
        self.assertEqual(len(set(identities)), 3)
        self.assertNotEqual(identities[0], identities[2])
        self.job.refresh_from_db()
        self.assertEqual(self.job.authority_digest, identities[2])
        self.assertEqual(self.job.required_state_fingerprint, "a" * 64)

        self.job.status = IgConversationAnalysisJob.Status.DONE
        self.job.analyzed_watermark_message_id = self.source.pk
        self.job.analyzed_materiality_event_highwater = (
            self.job.materiality_event_highwater
        )
        self.job.analyzed_materiality_digest = self.job.materiality_digest
        self.job.save()
        snapshot = IgConversationAnalysisSnapshot.objects.create(
            client=self.client,
            last_analyzed_message=self.source,
            dedupe_key="authority-a-b-a-current",
            score_band=IgConversationAnalysisSnapshot.Band.QUALIFIED,
            interaction_type=(
                IgConversationAnalysisSnapshot.InteractionType.PRODUCT_INTEREST
            ),
            purchase_probability=Decimal("0.7000"),
            confidence=Decimal("0.9000"),
            evidence=[{
                "message_id": self.source.pk,
                "source_role": InstagramBotMessage.Role.USER,
                "quote": self.source.text,
            }],
            required_state_fingerprint="a" * 64,
        )
        with override_settings(IG_ANALYSIS_CURRENT_SELECTOR_MODE="enforce"):
            self.assertEqual(
                materiality.current_analysis_snapshot(self.client).pk,
                snapshot.pk,
            )

    @patch("management.services.bot_conversation_analysis.gemini_generate_json")
    def test_existing_payment_truth_adapter_records_without_provider_polling(
        self,
        generate,
    ):
        from management.services.bot_conversation_analysis import (
            schedule_client_truth_analysis,
        )

        message = _message(self.client, "Чекаю оплату")
        first = schedule_client_truth_analysis(
            self.client,
            trigger="payment_truth",
            now=timezone.now(),
        )
        second = schedule_client_truth_analysis(
            self.client,
            trigger="payment_truth",
            now=timezone.now() + timedelta(minutes=1),
        )

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(IgAnalysisMaterialityEvent.objects.count(), 1)
        self.assertEqual(
            IgAnalysisMaterialityEvent.objects.get().source_message_id,
            message.pk,
        )
        generate.assert_not_called()

    @patch(
        "management.services.ig_analysis_materiality.record_authority_materiality",
        side_effect=RuntimeError("shadow unavailable"),
    )
    def test_shadow_authority_failure_keeps_existing_job_schedule(self, _record):
        from management.services.bot_conversation_analysis import (
            schedule_client_truth_analysis,
        )

        _message(self.client, "Оплата")
        job = schedule_client_truth_analysis(
            self.client,
            trigger="payment_truth",
            now=timezone.now(),
        )

        self.assertIsNotNone(job)
        self.assertTrue(IgConversationAnalysisJob.objects.filter(pk=job.pk).exists())

    def test_new_event_schedule_uses_three_application_queries(self):
        with CaptureQueriesContext(connection) as queries:
            event = self._record("budget", timezone.now())

        application_queries = [
            row["sql"] for row in queries
            if row["sql"].lstrip().upper().startswith(
                ("SELECT", "INSERT", "UPDATE")
            )
        ]
        self.assertIsNotNone(event)
        self.assertLessEqual(len(application_queries), 3, application_queries)

    def test_atomic_claim_copies_all_materiality_cursor_dimensions(self):
        from management.services import bot_conversation_analysis as analysis

        authority_identity = _event_digest("claim-authority")
        artifact_identity = _event_digest("claim-artifact")
        event = materiality.record_materiality_event(
            client_id=self.client.pk,
            event_kind=IgAnalysisMaterialityEvent.Kind.CUSTOMER_TURN,
            event_digest=_event_digest("claim-cursor"),
            source_role=IgAnalysisMaterialityEvent.SourceRole.USER,
            source_message_id=self.source.pk,
            authority_digest=authority_identity,
            artifact_revision=3,
            artifact_digest=artifact_identity,
            relevant_at=timezone.now(),
        )

        claimed, _watermark, _revision, token = analysis._claim_due(
            timezone.now() + timedelta(seconds=1)
        )

        self.assertEqual(claimed.claimed_materiality_event_highwater, event.pk)
        self.assertEqual(
            claimed.claimed_materiality_digest,
            claimed.materiality_digest,
        )
        self.assertEqual(claimed.claimed_authority_digest, authority_identity)
        self.assertEqual(claimed.claimed_artifact_digest, artifact_identity)
        self.assertTrue(
            analysis._defer_claim_for_customer_reply(
                claimed.pk,
                token,
                now=timezone.now(),
            )
        )
        claimed.refresh_from_db()
        self.assertEqual(claimed.claimed_materiality_event_highwater, 0)
        self.assertEqual(claimed.claimed_materiality_digest, "")
        self.assertEqual(claimed.claimed_authority_digest, "")
        self.assertEqual(claimed.claimed_artifact_digest, "")

    def test_episode_line_and_event_highwater_are_typed_on_job(self):
        episode = IgCommercialEpisode.objects.create(
            client=self.client,
            sequence=1,
            open_slot=1,
            materialization_key="mat-cadence:episode:1",
        )

        event = self._record(
            "episode-line",
            timezone.now(),
            episode_id=episode.pk,
            line_id="line:0",
        )

        self.job.refresh_from_db()
        self.assertEqual(event.episode_id, episode.pk)
        self.assertEqual(event.line_id, "line:0")
        self.assertEqual(self.job.materiality_episode_id, episode.pk)
        self.assertEqual(self.job.materiality_line_id, "line:0")
        self.assertEqual(self.job.materiality_event_highwater, event.pk)

    def test_out_of_order_event_backdates_first_unanalysed_at(self):
        now = timezone.now().replace(microsecond=0)
        self._record("later", now)
        earlier = now - timedelta(minutes=4)
        self._record("earlier", earlier)

        self.job.refresh_from_db()
        self.assertEqual(self.job.first_unanalysed_at, earlier)

    def test_manager_only_message_cannot_masquerade_as_customer_turn(self):
        manager = _message(
            self.client,
            "manager-only evidence",
            role=InstagramBotMessage.Role.MANAGER,
        )
        before = self.job.materiality_event_highwater

        digest = _event_digest("manager-masquerade")
        event = materiality.record_materiality_event(
            client_id=self.client.pk,
            event_kind=IgAnalysisMaterialityEvent.Kind.CUSTOMER_TURN,
            event_digest=digest,
            source_role=IgAnalysisMaterialityEvent.SourceRole.USER,
            source_message_id=manager.pk,
        )

        self.assertIsNone(event)
        self.assertFalse(IgAnalysisMaterialityEvent.objects.filter(
            event_digest=digest,
        ).exists())
        self.job.refresh_from_db()
        self.assertEqual(self.job.materiality_event_highwater, before)

    def test_user_evidence_from_another_client_cannot_cross_the_guard(self):
        other = IgClient.objects.create(igsid="mat-other-client")
        foreign_source = _message(other, "foreign customer evidence")

        event = materiality.record_materiality_event(
            client_id=self.client.pk,
            event_kind=IgAnalysisMaterialityEvent.Kind.CUSTOMER_TURN,
            event_digest=_event_digest("foreign-customer-evidence"),
            source_role=IgAnalysisMaterialityEvent.SourceRole.USER,
            source_message_id=foreign_source.pk,
        )

        self.assertIsNone(event)
        self.assertFalse(IgAnalysisMaterialityEvent.objects.exists())


@override_settings(IG_ANALYSIS_MATERIALITY_MODE="shadow")
class CompletedTurnMaterialityTests(TestCase):
    def setUp(self):
        self.client = IgClient.objects.create(igsid="mat-turn")
        self.job = _job(self.client)

    def test_reaction_and_non_customer_echo_are_noops(self):
        reaction = _message(self.client, "👍")
        reaction_turn = _turn(self.client, reaction)
        from management.services.ig_customer_turns import mark_turn_processed

        mark_turn_processed(reaction_turn.pk)
        manager = _message(
            self.client,
            "manager note",
            role=InstagramBotMessage.Role.MANAGER,
        )
        manager_turn = _turn(self.client, manager)
        mark_turn_processed(manager_turn.pk)

        self.assertFalse(IgAnalysisMaterialityEvent.objects.exists())
        self.job.refresh_from_db()
        self.assertEqual(self.job.materiality_digest, "")

    def test_meaningful_confirmation_records_artifact_identity_without_text(self):
        media_digest = "b" * 64
        message = _message(
            self.client,
            "Оплатив, дякую",
            artifact={"schema_version": 2, "media_digest": media_digest},
        )
        message.attachments = '["https://cdn.example/private-customer-image.jpg"]'
        message.save(update_fields=["attachments"])
        turn = _turn(self.client, message)
        from management.services.ig_customer_turns import mark_turn_processed

        mark_turn_processed(turn.pk)

        event = IgAnalysisMaterialityEvent.objects.get()
        self.assertEqual(event.customer_turn_id, turn.pk)
        self.assertEqual(event.source_message_id, message.pk)
        self.assertEqual(event.source_role, "user")
        self.assertEqual(event.artifact_revision, 2)
        self.assertTrue(event.artifact_digest)
        self.assertNotEqual(event.artifact_digest, media_digest)
        self.assertEqual(
            event.artifact_digest,
            materiality._sha({
                "artifacts": [{
                    "source_message_id": message.pk,
                    "schema_revision": 2,
                }],
            }),
        )
        self.assertNotIn("Оплатив", event.event_key)
        self.assertNotEqual(
            event.event_digest,
            hashlib.sha256(message.text.encode("utf-8")).hexdigest(),
        )
        self.assertNotEqual(
            event.event_digest,
            materiality._sha({"value": message.text.casefold()}),
        )
        ledger_payload = json.dumps({
            "event_digest": event.event_digest,
            "artifact_digest": event.artifact_digest,
            "materiality_digest": (
                IgConversationAnalysisJob.objects.get(pk=self.job.pk)
                .materiality_digest
            ),
        })
        self.assertNotIn(media_digest, ledger_payload)
        self.assertNotIn(
            hashlib.sha256(message.text.encode("utf-8")).hexdigest(),
            ledger_payload,
        )

    def test_raw_text_like_digest_is_rejected_before_ledger_write(self):
        message = _message(self.client, "customer content")

        with self.assertRaisesRegex(ValueError, "64-character hexadecimal"):
            materiality.record_materiality_event(
                client_id=self.client.pk,
                source_message_id=message.pk,
                source_role=IgAnalysisMaterialityEvent.SourceRole.USER,
                event_kind=IgAnalysisMaterialityEvent.Kind.CUSTOMER_TURN,
                event_digest=message.text,
            )

        self.assertFalse(IgAnalysisMaterialityEvent.objects.exists())

    @patch(
        "management.services.ig_analysis_materiality.record_completed_customer_turn",
        side_effect=RuntimeError("shadow unavailable"),
    )
    def test_shadow_failure_cannot_change_turn_completion(self, _record):
        message = _message(self.client, "Хочу худі")
        turn = _turn(self.client, message)
        from management.services.ig_customer_turns import mark_turn_processed

        mark_turn_processed(turn.pk)

        turn.refresh_from_db()
        self.assertEqual(turn.claim_state, IgCustomerTurn.ClaimState.PROCESSED)


@override_settings(
    IG_ANALYSIS_MATERIALITY_MODE="shadow",
    IG_ANALYSIS_CURRENT_SELECTOR_MODE="enforce",
)
class CurrentAnalysisSnapshotTests(TestCase):
    def setUp(self):
        self.client = IgClient.objects.create(igsid="mat-selector")
        self.episode = IgCommercialEpisode.objects.create(
            client=self.client,
            sequence=1,
            open_slot=1,
            materialization_key="mat-selector:episode:1",
            opened_watermark_message_id=1,
        )
        self.client.current_commercial_episode = self.episode
        self.client.save(update_fields=["current_commercial_episode", "updated_at"])
        self.manager_message = _message(
            self.client,
            "manager-only observation",
            role=InstagramBotMessage.Role.MANAGER,
        )
        self.message = _message(self.client, "Я подумаю про худі")
        self.job = _job(self.client, watermark=self.message.pk)
        self.job.analyzed_watermark_message_id = self.message.pk
        self.job.status = IgConversationAnalysisJob.Status.DONE
        self.job.materiality_event_highwater = 7
        self.job.analyzed_materiality_event_highwater = 7
        self.job.materiality_digest = "c" * 64
        self.job.analyzed_materiality_digest = "c" * 64
        self.job.authority_digest = "e" * 64
        self.job.required_state_fingerprint = "d" * 64
        self.job.save()

    def _snapshot(self, *, episode, interaction, probability, evidence=None):
        if evidence is None:
            evidence = [{
                "message_id": self.message.pk,
                "source_role": InstagramBotMessage.Role.USER,
                "quote": self.message.text,
            }]
        return IgConversationAnalysisSnapshot.objects.create(
            client=self.client,
            commercial_episode=episode,
            last_analyzed_message=self.message,
            dedupe_key=f"selector:{interaction}:{probability}:{timezone.now().timestamp()}",
            score_band=IgConversationAnalysisSnapshot.Band.HIGH_INTENT,
            interaction_type=interaction,
            purchase_probability=Decimal(str(probability)),
            confidence=Decimal("0.9000"),
            evidence=evidence,
            required_state_fingerprint="d" * 64,
        )

    def test_selector_ignores_newer_manager_and_stale_episode_numeric_intent(self):
        current = self._snapshot(
            episode=self.episode,
            interaction=IgConversationAnalysisSnapshot.InteractionType.HIGH_INTENT,
            probability="0.8000",
        )
        old_episode = IgCommercialEpisode.objects.create(
            client=self.client,
            sequence=2,
            open_slot=None,
            materialization_key="mat-selector:episode:old",
        )
        self._snapshot(
            episode=old_episode,
            interaction=IgConversationAnalysisSnapshot.InteractionType.HIGH_INTENT,
            probability="0.9900",
        )
        manager = self._snapshot(
            episode=self.episode,
            interaction=(
                IgConversationAnalysisSnapshot.InteractionType.MANAGER_OBSERVATION
            ),
            probability="1.0000",
        )

        selected = materiality.current_analysis_snapshot(self.client)
        selected_with_manager = materiality.current_analysis_snapshot(
            self.client,
            include_manager=True,
        )

        self.assertEqual(selected.pk, current.pk)
        self.assertEqual(selected_with_manager.pk, manager.pk)

    def test_new_unanalysed_digest_hides_stale_probability(self):
        self._snapshot(
            episode=self.episode,
            interaction=IgConversationAnalysisSnapshot.InteractionType.HIGH_INTENT,
            probability="0.9500",
        )
        self.job.materiality_digest = "e" * 64
        self.job.save(update_fields=["materiality_digest"])

        self.assertIsNone(materiality.current_analysis_snapshot(self.client))

    def test_followup_selector_uses_only_canonical_current_snapshot(self):
        from management.services.bot_followups import _suppressed_interaction

        self._snapshot(
            episode=self.episode,
            interaction=(
                IgConversationAnalysisSnapshot.InteractionType.WHOLESALE_B2B
            ),
            probability="0.7000",
        )
        self.assertEqual(_suppressed_interaction(self.client), "wholesale_b2b")

        self.job.materiality_digest = "f" * 64
        self.job.save(update_fields=["materiality_digest"])
        self.assertEqual(_suppressed_interaction(self.client), "")

    def test_ui_projection_drops_stale_numeric_probability(self):
        from management.bot_views import _client_potential_payload

        snapshot = self._snapshot(
            episode=self.episode,
            interaction=IgConversationAnalysisSnapshot.InteractionType.HIGH_INTENT,
            probability="0.9100",
        )
        current = materiality.current_analysis_snapshot(self.client)
        current_payload = _client_potential_payload(
            self.client,
            current,
            latest_message_id=self.message.pk,
        )
        self.assertEqual(current.pk, snapshot.pk)
        self.assertIsNotNone(current_payload["probability"])

        self.job.materiality_digest = "1" * 64
        self.job.save(update_fields=["materiality_digest"])
        stale_payload = _client_potential_payload(
            self.client,
            materiality.current_analysis_snapshot(self.client),
            latest_message_id=self.message.pk,
        )
        self.assertIsNone(stale_payload["probability"])

    def test_manager_only_evidence_cannot_project_customer_intent_or_cta(self):
        from management.bot_views import _client_potential_payload
        from management.services.ig_follow_cta import _latest_hesitation_analysis

        snapshot = self._snapshot(
            episode=self.episode,
            interaction=IgConversationAnalysisSnapshot.InteractionType.HIGH_INTENT,
            probability="0.9900",
            evidence=[{
                "message_id": self.manager_message.pk,
                "source_role": InstagramBotMessage.Role.MANAGER,
                "quote": self.manager_message.text,
            }],
        )

        selected = materiality.current_analysis_snapshot(self.client)
        potential = _client_potential_payload(
            self.client,
            selected,
            latest_message_id=self.message.pk,
        )
        cta_analysis = _latest_hesitation_analysis(
            client=self.client,
            episode=self.episode,
            source_message=self.message,
            now=timezone.now(),
        )

        self.assertIsNone(selected)
        self.assertIsNone(potential["probability"])
        self.assertIsNone(cta_analysis)
        self.assertTrue(IgConversationAnalysisSnapshot.objects.filter(
            pk=snapshot.pk,
        ).exists())

    def test_manager_only_evidence_cannot_suppress_followup_as_customer_b2b(self):
        from management.services.bot_followups import _suppressed_interaction

        self._snapshot(
            episode=self.episode,
            interaction=(
                IgConversationAnalysisSnapshot.InteractionType.WHOLESALE_B2B
            ),
            probability="0.9000",
            evidence=[{
                "message_id": self.manager_message.pk,
                "source_role": InstagramBotMessage.Role.MANAGER,
                "quote": self.manager_message.text,
            }],
        )

        self.assertEqual(_suppressed_interaction(self.client), "")


@override_settings(
    IG_ANALYSIS_MATERIALITY_MODE="shadow",
    IG_ANALYSIS_CURRENT_SELECTOR_MODE="enforce",
)
class ShadowAnalysisCompletionTests(TestCase):
    @patch("management.services.bot_conversation_analysis.gemini_generate_json")
    def test_existing_analysis_completion_advances_shadow_cursor(self, generate):
        from management.services import bot_conversation_analysis as analysis

        client = IgClient.objects.create(igsid="mat-completion")
        episode = IgCommercialEpisode.objects.create(
            client=client,
            sequence=1,
            open_slot=1,
            materialization_key="mat-completion:episode:1",
        )
        client.current_commercial_episode = episode
        client.save(update_fields=["current_commercial_episode", "updated_at"])
        message = _message(client, "Хочу чорне худі")
        now = timezone.now()
        job = analysis.schedule_analysis(
            client,
            message,
            now=now,
            delay_seconds=0,
        )
        materiality.record_materiality_event(
            client_id=client.pk,
            episode_id=episode.pk,
            source_message_id=message.pk,
            source_role=IgAnalysisMaterialityEvent.SourceRole.USER,
            event_kind=IgAnalysisMaterialityEvent.Kind.CUSTOMER_TURN,
            event_digest=_event_digest("completion-event"),
            relevant_at=now,
        )
        generate.return_value = {
            "parsed": {
                "interaction_type": "product_interest",
                "score_band": "qualified",
                "purchase_probability": 0.7,
                "confidence": 0.9,
                "evidence": [{
                    "message_id": message.pk,
                    "quote": "Хочу чорне худі",
                    "claim": "product interest",
                }],
                "uncertainties": [],
                "repeat_intent": {},
            },
            "model": "gemini-3.6-flash",
            "meta": {},
        }

        result = analysis.process_due_analysis(limit=1, now=now)

        self.assertEqual(result["done"], 1)
        job.refresh_from_db()
        self.assertEqual(job.status, IgConversationAnalysisJob.Status.DONE)
        self.assertEqual(job.analyzed_materiality_digest, job.materiality_digest)
        self.assertEqual(
            job.analyzed_materiality_event_highwater,
            job.materiality_event_highwater,
        )
        snapshot = materiality.current_analysis_snapshot(client)
        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot.last_analyzed_message_id, message.pk)

    @patch("management.services.bot_conversation_analysis.gemini_generate_json")
    def test_event_after_claim_does_not_advance_past_captured_cursor(self, generate):
        from management.services import bot_conversation_analysis as analysis

        client = IgClient.objects.create(igsid="mat-after-claim")
        episode = IgCommercialEpisode.objects.create(
            client=client,
            sequence=1,
            open_slot=1,
            materialization_key="mat-after-claim:episode:1",
        )
        client.current_commercial_episode = episode
        client.save(update_fields=["current_commercial_episode", "updated_at"])
        message = _message(client, "Хочу чорне худі")
        now = timezone.now().replace(microsecond=0)
        job = analysis.schedule_analysis(
            client,
            message,
            now=now,
            delay_seconds=0,
        )
        captured = materiality.record_materiality_event(
            client_id=client.pk,
            episode_id=episode.pk,
            source_message_id=message.pk,
            source_role=IgAnalysisMaterialityEvent.SourceRole.USER,
            event_kind=IgAnalysisMaterialityEvent.Kind.CUSTOMER_TURN,
            event_digest=_event_digest("before-claim"),
            relevant_at=now,
        )

        def append_new_event(*_args, **_kwargs):
            materiality.record_materiality_event(
                client_id=client.pk,
                episode_id=episode.pk,
                source_message_id=message.pk,
                source_role=IgAnalysisMaterialityEvent.SourceRole.USER,
                event_kind=IgAnalysisMaterialityEvent.Kind.CUSTOMER_TURN,
                event_digest=_event_digest("after-claim"),
                relevant_at=now + timedelta(seconds=1),
            )
            return {
                "parsed": {
                    "interaction_type": "product_interest",
                    "score_band": "qualified",
                    "purchase_probability": 0.7,
                    "confidence": 0.9,
                    "evidence": [{
                        "message_id": message.pk,
                        "quote": message.text,
                        "claim": "product interest",
                    }],
                    "uncertainties": [],
                    "repeat_intent": {},
                },
                "model": "gemini-3.6-flash",
                "meta": {},
            }

        generate.side_effect = append_new_event

        result = analysis.process_due_analysis(limit=1, now=now)

        self.assertEqual(result["done"], 1, result)
        job.refresh_from_db()
        latest = IgAnalysisMaterialityEvent.objects.order_by("-id").first()
        self.assertEqual(job.status, IgConversationAnalysisJob.Status.DONE)
        self.assertEqual(job.analyzed_materiality_event_highwater, captured.pk)
        self.assertEqual(
            job.analyzed_materiality_digest,
            materiality._sha({
                "event_id": captured.pk,
                "digest": captured.event_digest,
            }),
        )
        self.assertEqual(job.materiality_event_highwater, latest.pk)
        self.assertNotEqual(job.analyzed_materiality_digest, job.materiality_digest)
        self.assertIsNotNone(job.first_unanalysed_at)
        self.assertEqual(job.claimed_materiality_event_highwater, 0)
        self.assertEqual(job.claimed_materiality_digest, "")
        self.assertEqual(job.claimed_authority_digest, "")
        self.assertEqual(job.claimed_artifact_digest, "")
        self.assertIsNone(materiality.current_analysis_snapshot(client))


@override_settings(IG_ANALYSIS_MATERIALITY_MODE="shadow")
class MaterialityConcurrencyTests(AnalysisPrivacyCleanupMixin, TransactionTestCase):
    reset_sequences = False

    def test_same_digest_concurrency_appends_once_and_bumps_once(self):
        client = IgClient.objects.create(igsid="mat-concurrency")
        _job(client)
        source = _message(client, "concurrent source")
        barrier = threading.Barrier(2)
        results = []
        errors = []

        def worker():
            close_old_connections()
            try:
                barrier.wait(timeout=5)
                result = materiality.record_materiality_event(
                    client_id=client.pk,
                    event_kind=IgAnalysisMaterialityEvent.Kind.CUSTOMER_TURN,
                    event_digest=_event_digest("same-concurrent-event"),
                    source_role=IgAnalysisMaterialityEvent.SourceRole.USER,
                    source_message_id=source.pk,
                    relevant_at=timezone.now(),
                )
                results.append(bool(result))
            except BaseException as exc:
                errors.append(exc)
            finally:
                close_old_connections()

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)

        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(errors, [])
        self.assertEqual(results.count(True), 1)
        self.assertEqual(IgAnalysisMaterialityEvent.objects.count(), 1)
        job = IgConversationAnalysisJob.objects.get(client=client)
        self.assertEqual(
            job.materiality_event_highwater,
            IgAnalysisMaterialityEvent.objects.get().pk,
        )
