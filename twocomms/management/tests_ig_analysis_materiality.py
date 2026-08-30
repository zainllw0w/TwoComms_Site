import hashlib
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
        event = materiality.record_materiality_event(
            client_id=client.pk,
            event_kind=IgAnalysisMaterialityEvent.Kind.CUSTOMER_TURN,
            event_digest="append-only",
            source_role=IgAnalysisMaterialityEvent.SourceRole.USER,
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


@override_settings(IG_ANALYSIS_MATERIALITY_MODE="shadow")
class MaterialityCadenceTests(TestCase):
    def setUp(self):
        self.client = IgClient.objects.create(igsid="mat-cadence")
        self.job = _job(self.client)

    def _record(self, suffix, at, **kwargs):
        return materiality.record_materiality_event(
            client_id=self.client.pk,
            event_kind=IgAnalysisMaterialityEvent.Kind.CUSTOMER_TURN,
            event_digest=f"event-{suffix}",
            source_role=IgAnalysisMaterialityEvent.SourceRole.USER,
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
        self.job.save(update_fields=["required_state_fingerprint"])
        now = timezone.now().replace(microsecond=0)

        first = materiality.record_authority_materiality(
            client=self.client,
            job=self.job,
            trigger="payment_truth",
            now=now,
        )
        duplicate = materiality.record_authority_materiality(
            client=self.client,
            job=self.job,
            trigger="payment_truth",
            now=now + timedelta(hours=12),
        )

        self.assertIsNotNone(first)
        self.assertIsNone(duplicate)
        self.job.refresh_from_db()
        self.assertEqual(self.job.materiality_due_at, now)
        self.assertEqual(self.job.authority_digest, "a" * 64)
        self.assertEqual(IgAnalysisMaterialityEvent.objects.count(), 1)

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
        message = _message(
            self.client,
            "Оплатив, дякую",
            artifact={"schema_version": 2, "media_digest": "b" * 64},
        )
        turn = _turn(self.client, message)
        from management.services.ig_customer_turns import mark_turn_processed

        mark_turn_processed(turn.pk)

        event = IgAnalysisMaterialityEvent.objects.get()
        self.assertEqual(event.customer_turn_id, turn.pk)
        self.assertEqual(event.source_message_id, message.pk)
        self.assertEqual(event.source_role, "user")
        self.assertEqual(event.artifact_revision, 2)
        self.assertTrue(event.artifact_digest)
        self.assertNotIn("Оплатив", event.event_key)

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


@override_settings(IG_ANALYSIS_MATERIALITY_MODE="shadow")
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
        self.message = _message(self.client, "Хочу худі")
        self.job = _job(self.client, watermark=self.message.pk)
        self.job.analyzed_watermark_message_id = self.message.pk
        self.job.status = IgConversationAnalysisJob.Status.DONE
        self.job.materiality_event_highwater = 7
        self.job.analyzed_materiality_event_highwater = 7
        self.job.materiality_digest = "c" * 64
        self.job.analyzed_materiality_digest = "c" * 64
        self.job.authority_digest = "d" * 64
        self.job.save()

    def _snapshot(self, *, episode, interaction, probability):
        return IgConversationAnalysisSnapshot.objects.create(
            client=self.client,
            commercial_episode=episode,
            last_analyzed_message=self.message,
            dedupe_key=f"selector:{interaction}:{probability}:{timezone.now().timestamp()}",
            score_band=IgConversationAnalysisSnapshot.Band.HIGH_INTENT,
            interaction_type=interaction,
            purchase_probability=Decimal(str(probability)),
            confidence=Decimal("0.9000"),
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


@override_settings(IG_ANALYSIS_MATERIALITY_MODE="shadow")
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
            event_digest="completion-event",
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


@override_settings(IG_ANALYSIS_MATERIALITY_MODE="shadow")
class MaterialityConcurrencyTests(TransactionTestCase):
    reset_sequences = False

    def test_same_digest_concurrency_appends_once_and_bumps_once(self):
        client = IgClient.objects.create(igsid="mat-concurrency")
        _job(client)
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
                    event_digest="same-concurrent-event",
                    source_role=IgAnalysisMaterialityEvent.SourceRole.USER,
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
