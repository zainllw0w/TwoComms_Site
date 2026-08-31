import datetime
import hashlib
import json
from decimal import Decimal
from unittest.mock import patch

from django.db import DatabaseError, connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from management.models import (
    IgClient,
    IgCommercialEpisode,
    IgConversationAnalysisJob,
    IgConversationAnalysisResult,
    IgConversationAnalysisSnapshot,
    IgMemoryFact,
    IgMemoryFactEvidence,
    IgMemoryHead,
    InstagramBotMessage,
    InstagramBotSettings,
)
from management.services import ig_analysis_v2 as analysis_v2
from management.services import ig_typed_memory as memory


SHADOW = {
    "IG_ANALYSIS_MATERIALITY_MODE": "shadow",
    "IG_ANALYSIS_V2_MODE": "shadow",
    "IG_ANALYSIS_V2_EXTENDED_PROMPT": True,
    "IG_TYPED_MEMORY_MODE": "shadow_compare",
}


class TypedMemoryRuntimeTests(TestCase):
    def setUp(self):
        self.client_row = IgClient.objects.create(igsid="typed-memory-client")
        self.episode = IgCommercialEpisode.objects.create(
            client=self.client_row,
            sequence=1,
            open_slot=1,
            materialization_key="typed-memory:episode:1",
            opened_watermark_message_id=1,
        )
        self.client_row.current_commercial_episode = self.episode
        self.client_row.save(update_fields=["current_commercial_episode", "updated_at"])
        self.message = InstagramBotMessage.objects.create(
            client=self.client_row,
            sender_id=self.client_row.igsid,
            role=InstagramBotMessage.Role.USER,
            text="Після зарплати хочу футболку, але ціна важлива",
            status=InstagramBotMessage.Status.DONE,
        )
        self.fingerprint = hashlib.sha256(b"typed-memory-current-state").hexdigest()
        self.job = IgConversationAnalysisJob.objects.create(
            client=self.client_row,
            watermark_message_id=self.message.pk,
            analyzed_watermark_message_id=self.message.pk,
            revision=2,
            analyzed_revision=2,
            status=IgConversationAnalysisJob.Status.DONE,
            due_at=timezone.now(),
            next_attempt_at=timezone.now(),
            materiality_episode=self.episode,
            materiality_line_id="line:primary",
            materiality_event_highwater=7,
            analyzed_materiality_event_highwater=7,
            materiality_digest="a" * 64,
            analyzed_materiality_digest="a" * 64,
            authority_digest="b" * 64,
            artifact_digest="c" * 64,
            required_state_fingerprint=self.fingerprint,
        )
        self.snapshot = IgConversationAnalysisSnapshot.objects.create(
            client=self.client_row,
            last_analyzed_message=self.message,
            dedupe_key="typed-memory:snapshot:1",
            score_band=IgConversationAnalysisSnapshot.Band.QUALIFIED,
            interaction_type=IgConversationAnalysisSnapshot.InteractionType.PRICE_OBJECTION,
            commercial_episode=self.episode,
            required_state_fingerprint=self.fingerprint,
            analyzed_at=timezone.now(),
        )
        self.result = IgConversationAnalysisResult(
            result_key="analysis-v2:" + hashlib.sha256(b"typed-memory-result").hexdigest(),
            legacy_snapshot=self.snapshot,
            client=self.client_row,
            commercial_episode=self.episode,
            line_id="line:primary",
            watermark_message_id=self.message.pk,
            job_revision=2,
            materiality_event_highwater=7,
            materiality_digest="a" * 64,
            authority_digest="b" * 64,
            artifact_digest="c" * 64,
            state_correlation=analysis_v2.state_correlation(self.fingerprint),
            result_schema_version=analysis_v2.RESULT_SCHEMA_VERSION,
            normalizer_version=analysis_v2.NORMALIZER_VERSION,
            interaction_type=self.snapshot.interaction_type,
            score_band=self.snapshot.score_band,
            detected_language="uk",
            language_evidence_message_ids=[self.message.pk],
            evidence_manifest=[{
                "message_id": self.message.pk,
                "source_role": "user",
                "claim_codes": ["interaction", "objection", "deferred_intent"],
            }],
            customer_evidence_count=1,
            active_objection_type="price",
            active_objection_confidence=Decimal("0.8000"),
            deferred_kind=IgConversationAnalysisResult.DeferredKind.PAYDAY,
            deferred_condition_code="payday",
            result_digest="",
            analyzed_at=self.snapshot.analyzed_at,
        )
        self.result.result_digest = analysis_v2.result_digest_for_instance(self.result)
        self.result.save(force_insert=True)

    def test_off_mode_is_absolute_zero_query_and_typed_prompt_is_rejected(self):
        with CaptureQueriesContext(connection) as captured:
            outcome = memory.publish_analysis_memory(self.result.pk)
        self.assertEqual(outcome.status, "off")
        self.assertEqual(len(captured), 0)

        with override_settings(IG_TYPED_MEMORY_MODE="typed_prompt"):
            with CaptureQueriesContext(connection) as captured:
                outcome = memory.publish_analysis_memory(self.result.pk)
            self.assertEqual(outcome.status, "off")
            self.assertEqual(len(captured), 0)

    @override_settings(**SHADOW)
    @patch("management.services.call_ai_analysis.gemini_generate_json")
    def test_one_result_projects_three_closed_facts_without_provider(self, provider):
        outcome = memory.publish_analysis_memory(self.result.pk)

        self.assertEqual(outcome.status, "published")
        self.assertEqual(outcome.created_facts, 3)
        self.assertEqual(IgMemoryFact.objects.count(), 3)
        self.assertEqual(IgMemoryHead.objects.count(), 3)
        self.assertEqual(IgMemoryFactEvidence.objects.count(), 3)
        self.assertEqual(
            set(IgMemoryFact.objects.values_list("fact_key", flat=True)),
            {"observed_language", "objection_observed", "deferred_intent"},
        )
        self.assertTrue(all(
            memory.memory_chain_valid(head)
            for head in IgMemoryHead.objects.select_related("current_fact")
        ))
        one_head = IgMemoryHead.objects.get(fact_key="observed_language")
        with CaptureQueriesContext(connection) as captured:
            self.assertTrue(memory.memory_chain_valid(one_head))
        self.assertLessEqual(len(captured), 2)
        provider.assert_not_called()

        repeated = memory.publish_analysis_memory(self.result.pk)
        self.assertEqual(repeated.status, "published")
        self.assertEqual(repeated.created_facts, 0)
        self.assertEqual(repeated.unchanged_heads, 3)
        self.assertEqual(IgMemoryFact.objects.count(), 3)

    @override_settings(**SHADOW)
    def test_late_result_and_forged_evidence_cannot_advance_heads(self):
        IgConversationAnalysisJob.objects.filter(pk=self.job.pk).update(
            materiality_digest="d" * 64,
            materiality_event_highwater=8,
        )
        outcome = memory.publish_analysis_memory(self.result.pk)
        self.assertEqual(outcome.status, "stale")
        self.assertFalse(IgMemoryHead.objects.exists())

        IgConversationAnalysisJob.objects.filter(pk=self.job.pk).update(
            materiality_digest="a" * 64,
            materiality_event_highwater=7,
        )
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE management_igconversationanalysisresult "
                "SET language_evidence_message_ids=%s WHERE id=%s",
                [json.dumps([999999]), self.result.pk],
            )
        outcome = memory.publish_analysis_memory(self.result.pk)
        self.assertIn(outcome.status, {"stale", "invalid_evidence"})
        self.assertFalse(IgMemoryHead.objects.exists())

    @override_settings(**SHADOW)
    def test_new_current_result_supersedes_exact_slot_and_old_result_cannot_return(self):
        memory.publish_analysis_memory(self.result.pk)
        language_head = IgMemoryHead.objects.get(fact_key="observed_language")
        old_fact_id = language_head.current_fact_id
        message = InstagramBotMessage.objects.create(
            client=self.client_row,
            sender_id=self.client_row.igsid,
            role=InstagramBotMessage.Role.USER,
            text="Пишіть російською",
            status=InstagramBotMessage.Status.DONE,
        )
        IgConversationAnalysisJob.objects.filter(pk=self.job.pk).update(
            watermark_message_id=message.pk,
            analyzed_watermark_message_id=message.pk,
            revision=3,
            analyzed_revision=3,
            materiality_event_highwater=8,
            analyzed_materiality_event_highwater=8,
            materiality_digest="d" * 64,
            analyzed_materiality_digest="d" * 64,
        )
        snapshot = IgConversationAnalysisSnapshot.objects.create(
            client=self.client_row,
            last_analyzed_message=message,
            dedupe_key="typed-memory:snapshot:2",
            score_band=IgConversationAnalysisSnapshot.Band.COLD,
            interaction_type=IgConversationAnalysisSnapshot.InteractionType.INFORMATION_ONLY,
            commercial_episode=self.episode,
            required_state_fingerprint=self.fingerprint,
            analyzed_at=timezone.now(),
        )
        result = IgConversationAnalysisResult(
            result_key="analysis-v2:" + hashlib.sha256(b"typed-memory-result-2").hexdigest(),
            legacy_snapshot=snapshot,
            client=self.client_row,
            commercial_episode=self.episode,
            line_id="line:primary",
            watermark_message_id=message.pk,
            job_revision=3,
            materiality_event_highwater=8,
            materiality_digest="d" * 64,
            authority_digest="b" * 64,
            artifact_digest="c" * 64,
            state_correlation=analysis_v2.state_correlation(self.fingerprint),
            result_schema_version=analysis_v2.RESULT_SCHEMA_VERSION,
            normalizer_version=analysis_v2.NORMALIZER_VERSION,
            interaction_type=snapshot.interaction_type,
            score_band=snapshot.score_band,
            detected_language="ru",
            language_evidence_message_ids=[message.pk],
            evidence_manifest=[{
                "message_id": message.pk,
                "source_role": "user",
                "claim_codes": ["interaction"],
            }],
            customer_evidence_count=1,
            result_digest="",
            analyzed_at=snapshot.analyzed_at,
        )
        result.result_digest = analysis_v2.result_digest_for_instance(result)
        result.save(force_insert=True)

        outcome = memory.publish_analysis_memory(result.pk)
        self.assertEqual(outcome.status, "published")
        language_head.refresh_from_db()
        self.assertEqual(language_head.revision, 2)
        self.assertEqual(language_head.current_fact.typed_value, {"code": "ru"})
        self.assertEqual(language_head.current_fact.supersedes_id, old_fact_id)
        self.assertTrue(memory.memory_chain_valid(language_head))
        with patch.object(
            memory,
            "fact_integrity_valid",
            side_effect=lambda fact: fact.pk != old_fact_id,
        ):
            self.assertFalse(memory.memory_chain_valid(language_head))
            self.assertEqual(memory.parity_report()["bad_hmac"], 1)
        self.assertEqual(memory.publish_analysis_memory(self.result.pk).status, "stale")

    @override_settings(**SHADOW)
    def test_retained_key_rotation_replays_same_result_as_exact_noop(self):
        first = memory.publish_analysis_memory(self.result.pk)
        self.assertEqual(first.created_facts, 3)
        head_revisions = dict(IgMemoryHead.objects.values_list("slot_key", "revision"))
        old_key_ids = set(IgMemoryFact.objects.values_list("integrity_key_id", flat=True))
        self.assertEqual(old_key_ids, {"tmk_test_v1"})

        with override_settings(
            **SHADOW,
            IG_TYPED_MEMORY_HMAC_ACTIVE_KEY_ID="tmk_rotated_v2",
            IG_TYPED_MEMORY_HMAC_KEYRING={
                "tmk_test_v1": "test-typed-memory-hmac-key-00000000000001",
                "tmk_rotated_v2": "rotated-typed-memory-hmac-key-0000000001",
            },
        ):
            replay = memory.publish_analysis_memory(self.result.pk)
            self.assertEqual(replay.status, "published")
            self.assertEqual(replay.created_facts, 0)
            self.assertEqual(replay.advanced_heads, 0)
            self.assertEqual(replay.unchanged_heads, 3)
            self.assertEqual(IgMemoryFact.objects.count(), 3)
            self.assertEqual(
                dict(IgMemoryHead.objects.values_list("slot_key", "revision")),
                head_revisions,
            )
            self.assertTrue(all(
                memory.memory_chain_valid(head)
                for head in IgMemoryHead.objects.select_related("current_fact")
            ))
            language_head = IgMemoryHead.objects.get(fact_key="observed_language")
            tombstone = memory.append_memory_tombstone(
                language_head,
                operation=IgMemoryFact.Operation.INVALIDATE,
                source_event_digest="9" * 64,
                reason_code="reset_boundary",
            )
            self.assertEqual(tombstone.status, "published")
            language_head.refresh_from_db()
            self.assertEqual(language_head.revision, 2)
            self.assertEqual(
                language_head.current_fact.integrity_key_id,
                "tmk_rotated_v2",
            )
            self.assertEqual(
                language_head.current_fact.supersedes.integrity_key_id,
                "tmk_test_v1",
            )
            self.assertTrue(memory.memory_chain_valid(language_head))

    @override_settings(**SHADOW)
    def test_expiry_and_reset_append_tombstones_without_mutating_old_fact(self):
        memory.publish_analysis_memory(self.result.pk)

        deferred = IgMemoryHead.objects.get(fact_key="deferred_intent")
        first_id = deferred.current_fact_id
        invalidated = memory.append_memory_tombstone(
            deferred,
            operation=IgMemoryFact.Operation.INVALIDATE,
            source_event_digest="d" * 64,
            reason_code="reset_boundary",
        )
        self.assertEqual(invalidated.status, "published")
        deferred.refresh_from_db()
        self.assertEqual(deferred.state, IgMemoryHead.State.INVALIDATED)
        self.assertEqual(deferred.current_fact.supersedes_id, first_id)
        self.assertTrue(IgMemoryFact.objects.filter(pk=first_id).exists())

        not_due = memory.append_memory_tombstone(
            IgMemoryHead.objects.get(fact_key="observed_language"),
            operation=IgMemoryFact.Operation.EXPIRE,
            source_event_digest="e" * 64,
            reason_code="valid_until_elapsed",
        )
        self.assertEqual(not_due.status, "not_due")

    @override_settings(**SHADOW)
    def test_tampered_current_fact_is_never_reused_or_projected(self):
        memory.publish_analysis_memory(self.result.pk)
        fact = IgMemoryFact.objects.get(fact_key="observed_language")
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE management_igmemoryfact SET typed_value=%s WHERE id=%s",
                    [json.dumps({"code": "ru"}), fact.pk],
                )
        except DatabaseError:
            # Migration-enabled databases reject the corruption at source.
            return
        outcome = memory.publish_analysis_memory(self.result.pk)
        self.assertEqual(outcome.status, "integrity_error")

    @override_settings(**SHADOW)
    def test_privacy_fence_purges_memory_a2_materiality_without_orphans(self):
        memory.publish_analysis_memory(self.result.pk)
        # The existing job/materiality contract already owns event identity.
        IgClient.objects.filter(pk=self.client_row.pk).update(
            privacy_erasure_started_at=timezone.now()
        )
        outcome = memory.purge_client_analysis_memory([self.client_row.pk])
        self.assertGreaterEqual(outcome["rows"], 6)
        self.assertFalse(IgMemoryFact.objects.filter(client_id=self.client_row.pk).exists())
        self.assertFalse(IgConversationAnalysisResult.objects.filter(client_id=self.client_row.pk).exists())

    def test_privacy_fence_is_also_an_analysis_write_barrier(self):
        from management.services.bot_conversation_analysis import _skip_reason

        self.client_row.privacy_erasure_started_at = timezone.now()
        self.client_row.save(
            update_fields=["privacy_erasure_started_at", "updated_at"]
        )
        self.assertEqual(_skip_reason(self.client_row), "privacy_erasure")

    @override_settings(**SHADOW)
    def test_reconcile_cursor_advances_past_no_claim_results(self):
        settings_row = InstagramBotSettings.load()
        settings_row.typed_memory_reconcile_cursor = 0
        settings_row.save(update_fields=["typed_memory_reconcile_cursor", "updated_at"])
        report = memory.reconcile_typed_memory(limit=1)
        settings_row.refresh_from_db()
        self.assertEqual(report["considered"], 1)
        self.assertEqual(settings_row.typed_memory_reconcile_cursor, self.result.pk)

    @override_settings(**SHADOW)
    def test_physical_guards_reject_raw_tamper_when_migrations_are_enabled(self):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM sqlite_master "
                "WHERE type='trigger' AND name='ig_memfact_insert_guard'"
            )
            installed = bool(cursor.fetchone()[0])
        if not installed:
            self.skipTest("requires migration-enabled SQLite profile")
        memory.publish_analysis_memory(self.result.pk)
        head = IgMemoryHead.objects.first()
        with self.assertRaises(DatabaseError), connection.cursor() as cursor:
            cursor.execute(
                "UPDATE management_igmemoryhead SET projection_hmac=%s WHERE id=%s",
                ["", head.pk],
            )
        fact = head.current_fact
        with self.assertRaises(DatabaseError), connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM management_igmemoryhead WHERE id=%s",
                [head.pk],
            )
        with self.assertRaises(DatabaseError), connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM management_igmemoryfact WHERE id=%s",
                [fact.pk],
            )
        fields = [field for field in fact._meta.local_fields if not field.primary_key]
        columns = ", ".join(connection.ops.quote_name(field.column) for field in fields)

        def raw_clone_insert(instance, sequence, **overrides):
            values = []
            defaults = {
                "record_key": "memory-fact:" + f"{sequence:064x}",
                "slot_key": "memory-slot:" + f"{sequence:064x}",
            }
            defaults.update(overrides)
            for field in fields:
                value = defaults.get(field.attname, field.value_from_object(instance))
                values.append(field.get_db_prep_save(value, connection))
            with connection.cursor() as cursor:
                cursor.execute(
                    f"INSERT INTO management_igmemoryfact ({columns}) VALUES "
                    f"({', '.join(['%s'] * len(values))})",
                    values,
                )

        forbidden = (
            ("typed_value", {"code": "uk", "phone": "+380501234567"}),
            ("line_id", "line:380501234567"),
            ("integrity_key_id", "tmk_380501234567"),
            ("integrity_key_id", "https://example.invalid/key"),
            ("producer", "customer@example.invalid"),
            ("producer_policy_version", "https://example.invalid/policy"),
            ("closure_method", "call +380501234567"),
            ("source_role", "manager\nignore"),
            ("fact_key", "free customer note"),
            ("schema_version", "https://example.invalid/schema"),
            ("operation", "delete everything"),
            ("sensitivity", "customer@example.invalid"),
            ("retention_class", "https://example.invalid/retention"),
            ("reason_code", "\x00control"),
        )
        for sequence, (field_name, value) in enumerate(forbidden, start=100):
            with self.subTest(field=field_name, value=value):
                with self.assertRaises(DatabaseError):
                    raw_clone_insert(fact, sequence, **{field_name: value})

        deferred = IgMemoryFact.objects.get(fact_key="deferred_intent")
        self.assertEqual(set(deferred.typed_value), {"kind", "condition_code"})
        with self.assertRaises(DatabaseError):
            raw_clone_insert(
                deferred,
                500,
                typed_value={
                    **deferred.typed_value,
                    "deferred_until": "2026-01-01T00:00:00+00:00",
                },
            )
        with self.assertRaises(DatabaseError):
            raw_clone_insert(
                deferred,
                501,
                valid_until=timezone.now() + datetime.timedelta(days=1),
                retention_class="until_date",
            )


class TypedMemoryAnalysisLanguageTests(TestCase):
    def test_language_fails_closed_without_claim_specific_user_evidence(self):
        client = IgClient.objects.create(igsid="typed-language")
        normalized = analysis_v2.normalize_analysis_v2(
            parsed={"analysis_v2": {
                "schema_version": 2,
                "detected_language": "uk",
                "language_evidence_message_ids": [1],
            }},
            legacy_normalized={
                "interaction_type": "information_only",
                "score_band": "cold",
                "evidence": [],
                "uncertainties": [],
                "repeat_intent": {},
            },
            by_id={1: {"message_id": 1, "role": "manager", "text": "українська"}},
            client=client,
            truth_state={},
            analyzed_at=timezone.now(),
        )
        self.assertEqual(normalized.result_values["detected_language"], "")
        self.assertEqual(normalized.result_values["language_evidence_message_ids"], [])
