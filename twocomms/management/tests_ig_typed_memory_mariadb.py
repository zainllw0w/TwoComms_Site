import hashlib
from concurrent.futures import ThreadPoolExecutor
from importlib import import_module
from threading import Barrier
from unittest import skipUnless

from django.apps import apps
from django.db import DatabaseError, close_old_connections, connection
from django.test import TransactionTestCase, override_settings
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
)
from management.services import ig_analysis_v2 as analysis_v2
from management.services import ig_typed_memory as memory


@skipUnless(connection.vendor == "mysql", "Disposable MariaDB-only typed-memory proof")
@override_settings(
    IG_ANALYSIS_MATERIALITY_MODE="shadow",
    IG_ANALYSIS_V2_MODE="shadow",
    IG_ANALYSIS_V2_EXTENDED_PROMPT=True,
    IG_TYPED_MEMORY_MODE="shadow_compare",
    IG_TYPED_MEMORY_HMAC_ACTIVE_KEY_ID="tmk_maria_v1",
    IG_TYPED_MEMORY_HMAC_KEYRING={
        "tmk_maria_v1": "maria-typed-memory-test-key-000000000001",
    },
)
class TypedMemoryMariaConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.client_row = IgClient.objects.create(igsid="typed-memory-maria-race")
        episode = IgCommercialEpisode.objects.create(
            client=self.client_row,
            sequence=1,
            open_slot=1,
            materialization_key="typed-memory:maria:episode",
        )
        self.client_row.current_commercial_episode = episode
        self.client_row.save(update_fields=["current_commercial_episode", "updated_at"])
        message = InstagramBotMessage.objects.create(
            client=self.client_row,
            sender_id=self.client_row.igsid,
            role=InstagramBotMessage.Role.USER,
            text="Привіт",
            status=InstagramBotMessage.Status.DONE,
        )
        fingerprint = hashlib.sha256(b"typed-memory-maria-state").hexdigest()
        IgConversationAnalysisJob.objects.create(
            client=self.client_row,
            watermark_message_id=message.pk,
            analyzed_watermark_message_id=message.pk,
            revision=1,
            analyzed_revision=1,
            status=IgConversationAnalysisJob.Status.DONE,
            due_at=timezone.now(),
            next_attempt_at=timezone.now(),
            materiality_episode=episode,
            materiality_event_highwater=1,
            analyzed_materiality_event_highwater=1,
            materiality_digest="a" * 64,
            analyzed_materiality_digest="a" * 64,
            required_state_fingerprint=fingerprint,
        )
        snapshot = IgConversationAnalysisSnapshot.objects.create(
            client=self.client_row,
            last_analyzed_message=message,
            dedupe_key="typed-memory:maria:snapshot",
            score_band=IgConversationAnalysisSnapshot.Band.COLD,
            interaction_type=IgConversationAnalysisSnapshot.InteractionType.INFORMATION_ONLY,
            commercial_episode=episode,
            required_state_fingerprint=fingerprint,
            analyzed_at=timezone.now(),
        )
        result = IgConversationAnalysisResult(
            result_key="analysis-v2:" + hashlib.sha256(b"typed-memory-maria-result").hexdigest(),
            legacy_snapshot=snapshot,
            client=self.client_row,
            commercial_episode=episode,
            watermark_message_id=message.pk,
            job_revision=1,
            materiality_event_highwater=1,
            materiality_digest="a" * 64,
            state_correlation=analysis_v2.state_correlation(fingerprint),
            result_schema_version=analysis_v2.RESULT_SCHEMA_VERSION,
            normalizer_version=analysis_v2.NORMALIZER_VERSION,
            interaction_type=snapshot.interaction_type,
            score_band=snapshot.score_band,
            detected_language="uk",
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
        self.result_id = result.pk

    def tearDown(self):
        IgClient.objects.filter(pk=self.client_row.pk).update(
            privacy_erasure_started_at=timezone.now()
        )
        memory.purge_client_analysis_memory([self.client_row.pk])
        super().tearDown()

    def test_database_is_explicitly_disposable(self):
        self.assertRegex(
            str(connection.settings_dict.get("NAME") or ""),
            r"^test_twocomms_[A-Za-z0-9_]+$",
        )

    def test_two_publishers_create_one_fact_and_one_head(self):
        start = Barrier(2)

        def worker(_index):
            close_old_connections()
            try:
                start.wait(timeout=10)
                return memory.publish_analysis_memory(self.result_id)
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(worker, (1, 2)))

        self.assertEqual({row.status for row in outcomes}, {"published"})
        self.assertEqual(IgMemoryFact.objects.count(), 1)
        self.assertEqual(IgMemoryFactEvidence.objects.count(), 1)
        self.assertEqual(IgMemoryHead.objects.count(), 1)
        head = IgMemoryHead.objects.select_related("current_fact").get()
        self.assertTrue(memory.memory_chain_valid(head))

    def test_same_name_weak_trigger_and_prefix_unique_fail_closed(self):
        migration = import_module("management.migrations.0185_typed_memory_v2")
        with connection.cursor() as cursor:
            cursor.execute("DROP TRIGGER ig_memfact_no_update")
            cursor.execute(
                "CREATE TRIGGER ig_memfact_no_update BEFORE UPDATE ON "
                "management_igmemoryfact FOR EACH ROW SET @typed_memory_noop=1"
            )
        try:
            with connection.schema_editor() as editor:
                with self.assertRaisesRegex(RuntimeError, "body mismatch"):
                    migration.install_typed_memory_and_privacy_triggers(apps, editor)
        finally:
            with connection.cursor() as cursor:
                cursor.execute("DROP TRIGGER IF EXISTS ig_memfact_no_update")
            with connection.schema_editor() as editor:
                migration.install_typed_memory_and_privacy_triggers(apps, editor)

        with connection.cursor() as cursor:
            cursor.execute("DROP TABLE IF EXISTS tm_mem_unique_good")
            cursor.execute("DROP TABLE IF EXISTS tm_mem_unique_bad")
            cursor.execute(
                "CREATE TABLE tm_mem_unique_good (a VARCHAR(32), b INTEGER, "
                "CONSTRAINT tm_mem_exact UNIQUE (a, b)) ENGINE=InnoDB"
            )
            cursor.execute(
                "CREATE TABLE tm_mem_unique_bad (a VARCHAR(32), b INTEGER, "
                "UNIQUE KEY tm_mem_exact_bad (a(3), b)) ENGINE=InnoDB"
            )
        try:
            with connection.schema_editor() as editor:
                migration._validate_physical_unique(
                    editor, "tm_mem_unique_good", "tm_mem_exact", ("a", "b")
                )
                with self.assertRaisesRegex(RuntimeError, "physical unique"):
                    migration._validate_physical_unique(
                        editor,
                        "tm_mem_unique_bad",
                        "tm_mem_exact_bad",
                        ("a", "b"),
                    )
        finally:
            with connection.cursor() as cursor:
                cursor.execute("DROP TABLE IF EXISTS tm_mem_unique_bad")
                cursor.execute("DROP TABLE IF EXISTS tm_mem_unique_good")

    def test_raw_phone_like_key_id_is_rejected_by_mariadb_guard(self):
        self.assertEqual(memory.publish_analysis_memory(self.result_id).status, "published")
        fact = IgMemoryFact.objects.get()
        fields = [field for field in fact._meta.local_fields if not field.primary_key]
        values = []
        for field in fields:
            value = field.value_from_object(fact)
            if field.attname == "record_key":
                value = "memory-fact:" + "f" * 64
            elif field.attname == "slot_key":
                value = "memory-slot:" + "f" * 64
            elif field.attname == "integrity_key_id":
                value = "tmk_380501234567"
            values.append(field.get_db_prep_save(value, connection))
        columns = ", ".join(
            connection.ops.quote_name(field.column) for field in fields
        )
        with self.assertRaises(DatabaseError), connection.cursor() as cursor:
            cursor.execute(
                f"INSERT INTO management_igmemoryfact ({columns}) VALUES "
                f"({', '.join(['%s'] * len(values))})",
                values,
            )
