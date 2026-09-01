"""Э3.4 — устаревший snapshot не выглядит текущим (`NEW-ANALYSIS-001`)."""

from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from management.models import (
    IgClient,
    IgCommercialEpisode,
    IgConversationAnalysisJob,
    IgConversationAnalysisSnapshot,
    InstagramBotMessage,
)
from management.services.ig_analysis_materiality import (
    current_analysis_snapshot,
    selector_enforced,
)


def _message(client, text, *, role=InstagramBotMessage.Role.USER):
    return InstagramBotMessage.objects.create(
        client=client,
        sender_id=client.igsid,
        role=role,
        text=text,
        status=InstagramBotMessage.Status.DONE,
    )


_TYPES = IgConversationAnalysisSnapshot.InteractionType
_BANDS = IgConversationAnalysisSnapshot.Band


class AnalysisFreshnessTests(TestCase):
    def setUp(self):
        self.client_row = IgClient.objects.create(igsid="freshness-test")
        self.episode = IgCommercialEpisode.objects.create(
            client=self.client_row,
            sequence=1,
            open_slot=1,
            materialization_key="freshness:episode:1",
        )
        self.client_row.current_commercial_episode = self.episode
        self.client_row.save(update_fields=["current_commercial_episode", "updated_at"])
        self.user_message_1 = _message(self.client_row, "Скільки коштує худі?")
        self.user_message_2 = _message(self.client_row, "Готовий замовити")
        self.job = IgConversationAnalysisJob.objects.create(
            client=self.client_row,
            watermark_message_id=self.user_message_2.pk,
            analyzed_watermark_message_id=self.user_message_1.pk,
            revision=2,
            analyzed_revision=1,
            status=IgConversationAnalysisJob.Status.PENDING,
            due_at=timezone.now(),
            materiality_digest="a" * 64,
            analyzed_materiality_digest="a" * 64,
            materiality_event_highwater=5,
            analyzed_materiality_event_highwater=5,
            authority_digest="b" * 64,
            artifact_digest="c" * 64,
            required_state_fingerprint="state1",
            materiality_episode=self.episode,
            materiality_line_id="line:primary",
        )
        self.stale_snapshot = IgConversationAnalysisSnapshot.objects.create(
            client=self.client_row,
            last_analyzed_message=self.user_message_1,
            dedupe_key="stale-snapshot",
            score_band=_BANDS.QUALIFIED,
            interaction_type=_TYPES.PRODUCT_INTEREST,
            purchase_probability=Decimal("0.6000"),
            confidence=Decimal("0.8000"),
            commercial_episode=self.episode,
            required_state_fingerprint="state1",
            analysis_model="gemini-3.6-flash",
            evidence=[{
                "message_id": self.user_message_1.pk,
                "source_role": "user",
                "quote": "Скільки коштує худі?",
                "claim": "price question",
            }],
            analyzed_at=timezone.now(),
        )

    # --- RED: pending job → current selector returns None ---------------

    @override_settings(
        IG_ANALYSIS_FRESHNESS_SELECTOR=True,
        IG_ANALYSIS_MATERIALITY_MODE="shadow",
    )
    def test_pending_analysis_job_makes_snapshot_stale_even_when_recent(self):
        """Контроль: стара поведінка повертала останній snapshot незалежно від job."""
        self.assertTrue(selector_enforced())
        current = current_analysis_snapshot(self.client_row)
        self.assertIsNone(current)

    @override_settings(
        IG_ANALYSIS_FRESHNESS_SELECTOR=False,
        IG_ANALYSIS_MATERIALITY_MODE="shadow",
    )
    def test_control_flag_off_returns_stale_snapshot_as_current(self):
        """Без флага дефектна поведінка: pending job не блокує snapshot."""
        self.assertFalse(selector_enforced())
        current = current_analysis_snapshot(self.client_row)
        self.assertIsNotNone(current)
        self.assertEqual(current.pk, self.stale_snapshot.pk)

    @override_settings(
        IG_ANALYSIS_FRESHNESS_SELECTOR=True,
        IG_ANALYSIS_MATERIALITY_MODE="shadow",
    )
    def test_done_job_with_mismatched_watermark_returns_none(self):
        self.job.status = IgConversationAnalysisJob.Status.DONE
        self.job.analyzed_watermark_message_id = self.user_message_2.pk
        self.job.save(update_fields=["status", "analyzed_watermark_message_id"])

        current = current_analysis_snapshot(self.client_row)

        self.assertIsNone(current)

    @override_settings(
        IG_ANALYSIS_FRESHNESS_SELECTOR=True,
        IG_ANALYSIS_MATERIALITY_MODE="shadow",
    )
    def test_done_job_with_matched_watermark_returns_snapshot(self):
        self.job.status = IgConversationAnalysisJob.Status.DONE
        self.job.analyzed_watermark_message_id = self.user_message_1.pk
        self.job.save(update_fields=["status", "analyzed_watermark_message_id"])

        current = current_analysis_snapshot(self.client_row)

        self.assertIsNotNone(current)
        self.assertEqual(current.pk, self.stale_snapshot.pk)

    @override_settings(
        IG_ANALYSIS_FRESHNESS_SELECTOR=True,
        IG_ANALYSIS_MATERIALITY_MODE="shadow",
    )
    def test_episode_mismatch_excludes_snapshot_from_current(self):
        self.episode.open_slot = None
        self.episode.save(update_fields=["open_slot"])
        new_episode = IgCommercialEpisode.objects.create(
            client=self.client_row,
            sequence=2,
            open_slot=1,
            materialization_key="freshness:episode:2",
        )
        self.client_row.current_commercial_episode = new_episode
        self.client_row.save(update_fields=["current_commercial_episode", "updated_at"])
        self.job.status = IgConversationAnalysisJob.Status.DONE
        self.job.analyzed_watermark_message_id = self.user_message_1.pk
        self.job.save(update_fields=["status", "analyzed_watermark_message_id"])

        current = current_analysis_snapshot(self.client_row)

        self.assertIsNone(current)

    @override_settings(
        IG_ANALYSIS_FRESHNESS_SELECTOR=True,
        IG_ANALYSIS_MATERIALITY_MODE="shadow",
    )
    def test_state_fingerprint_mismatch_excludes_snapshot_from_current(self):
        self.job.status = IgConversationAnalysisJob.Status.DONE
        self.job.analyzed_watermark_message_id = self.user_message_1.pk
        self.job.required_state_fingerprint = "state2"
        self.job.save(update_fields=[
            "status",
            "analyzed_watermark_message_id",
            "required_state_fingerprint",
        ])

        current = current_analysis_snapshot(self.client_row)

        self.assertIsNone(current)

    @override_settings(
        IG_ANALYSIS_FRESHNESS_SELECTOR=True,
        IG_ANALYSIS_MATERIALITY_MODE="shadow",
    )
    def test_materiality_digest_mismatch_excludes_snapshot(self):
        self.job.status = IgConversationAnalysisJob.Status.DONE
        self.job.analyzed_watermark_message_id = self.user_message_1.pk
        self.job.materiality_digest = "d" * 64
        self.job.save(update_fields=[
            "status",
            "analyzed_watermark_message_id",
            "materiality_digest",
        ])

        current = current_analysis_snapshot(self.client_row)

        self.assertIsNone(current)

    @override_settings(
        IG_ANALYSIS_FRESHNESS_SELECTOR=True,
        IG_ANALYSIS_MATERIALITY_MODE="shadow",
    )
    def test_event_highwater_mismatch_excludes_snapshot(self):
        self.job.status = IgConversationAnalysisJob.Status.DONE
        self.job.analyzed_watermark_message_id = self.user_message_1.pk
        self.job.materiality_event_highwater = 10
        self.job.save(update_fields=[
            "status",
            "analyzed_watermark_message_id",
            "materiality_event_highwater",
        ])

        current = current_analysis_snapshot(self.client_row)

        self.assertIsNone(current)


class StalenessCrmProjectionTests(TestCase):
    """Стара probability та intent не потрапляють у CRM і follow-up."""

    @override_settings(
        IG_ANALYSIS_FRESHNESS_SELECTOR=True,
        IG_ANALYSIS_MATERIALITY_MODE="shadow",
    )
    def test_stale_snapshot_does_not_drive_follow_up_projection(self):
        """Pending job після нового inbound робить snapshot stale."""
        from management.services.bot_followups import _suppressed_interaction

        client = IgClient.objects.create(igsid="stale-follow-up")
        episode = IgCommercialEpisode.objects.create(
            client=client,
            sequence=1,
            open_slot=1,
            materialization_key="stale-follow-up:episode:1",
        )
        client.current_commercial_episode = episode
        client.save(update_fields=["current_commercial_episode", "updated_at"])
        message_1 = _message(client, "Хочу худі")
        message_2 = _message(client, "Готовий замовити")

        # Створюємо done job на message_1
        job = IgConversationAnalysisJob.objects.create(
            client=client,
            watermark_message_id=message_1.pk,
            analyzed_watermark_message_id=message_1.pk,
            revision=1,
            analyzed_revision=1,
            status=IgConversationAnalysisJob.Status.DONE,
            due_at=timezone.now(),
            materiality_digest="a" * 64,
            analyzed_materiality_digest="a" * 64,
            materiality_event_highwater=3,
            analyzed_materiality_event_highwater=3,
            authority_digest="b" * 64,
            artifact_digest="c" * 64,
            required_state_fingerprint="state1",
            materiality_episode=episode,
            materiality_line_id="line:primary",
        )
        snapshot = IgConversationAnalysisSnapshot.objects.create(
            client=client,
            last_analyzed_message=message_1,
            dedupe_key="stale-follow-up:snapshot",
            score_band=_BANDS.QUALIFIED,
            interaction_type=_TYPES.PRODUCT_INTEREST,
            purchase_probability=Decimal("0.7000"),
            confidence=Decimal("0.8000"),
            commercial_episode=episode,
            required_state_fingerprint="state1",
            analysis_model="gemini-3.6-flash",
            evidence=[{
                "message_id": message_1.pk,
                "source_role": "user",
                "quote": "Хочу худі",
                "claim": "product interest",
            }],
            analyzed_at=timezone.now(),
        )

        self.assertIsNotNone(current_analysis_snapshot(client))

        # Новий inbound переводить job у pending
        job.watermark_message_id = message_2.pk
        job.status = IgConversationAnalysisJob.Status.PENDING
        job.revision = 2
        job.save(update_fields=["watermark_message_id", "status", "revision"])

        self.assertIsNone(current_analysis_snapshot(client))
        self.assertEqual(_suppressed_interaction(client), "")
