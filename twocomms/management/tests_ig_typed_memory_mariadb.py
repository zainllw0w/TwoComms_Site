import hashlib
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless

from django.db import close_old_connections, connection
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
    IG_TYPED_MEMORY_HMAC_ACTIVE_KEY_ID="maria-v1",
    IG_TYPED_MEMORY_HMAC_KEYRING={
        "maria-v1": "maria-typed-memory-test-key-000000000001",
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
