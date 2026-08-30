from decimal import Decimal
import inspect
import hashlib

from django.test import TestCase, override_settings
from django.utils import timezone

from management.models import (
    IgAnalysisProposal,
    IgClient,
    IgCommercialEpisode,
    IgConversationAnalysisJob,
    IgConversationAnalysisResult,
    IgConversationAnalysisSnapshot,
    InstagramBotMessage,
)
from management.services import ig_analysis_v2 as v2
from management.services.ig_analysis_v2_projector import validate_proposal


@override_settings(
    IG_ANALYSIS_V2_MODE="shadow",
    IG_ANALYSIS_MATERIALITY_MODE="shadow",
)
class AnalysisV2ProjectorTests(TestCase):
    def setUp(self):
        self.client_row = IgClient.objects.create(igsid="analysis-v2-projector")
        self.episode = IgCommercialEpisode.objects.create(
            client=self.client_row,
            sequence=1,
            open_slot=1,
            materialization_key="analysis-v2-projector:episode",
        )
        self.client_row.current_commercial_episode = self.episode
        self.client_row.save(
            update_fields=["current_commercial_episode", "updated_at"]
        )
        self.manager_message = InstagramBotMessage.objects.create(
            client=self.client_row,
            sender_id=self.client_row.igsid,
            role=InstagramBotMessage.Role.MANAGER,
            text="manager note",
            status=InstagramBotMessage.Status.DONE,
        )
        self.message = InstagramBotMessage.objects.create(
            client=self.client_row,
            sender_id=self.client_row.igsid,
            role=InstagramBotMessage.Role.USER,
            text="хочу футболку",
            status=InstagramBotMessage.Status.DONE,
        )
        self.raw_fingerprint = "f" * 64
        self.job = IgConversationAnalysisJob.objects.create(
            client=self.client_row,
            watermark_message_id=self.message.pk,
            revision=2,
            status=IgConversationAnalysisJob.Status.DONE,
            due_at=timezone.now(),
            next_attempt_at=timezone.now(),
            materiality_episode=self.episode,
            materiality_line_id="line:primary",
            materiality_event_highwater=7,
            materiality_digest="a" * 64,
            authority_digest="b" * 64,
            required_state_fingerprint=self.raw_fingerprint,
        )
        self.snapshot = IgConversationAnalysisSnapshot.objects.create(
            client=self.client_row,
            last_analyzed_message=self.message,
            dedupe_key="analysis-v2-projector:snapshot",
            score_band=IgConversationAnalysisSnapshot.Band.EXPLORING,
            interaction_type=IgConversationAnalysisSnapshot.InteractionType.PRODUCT_INTEREST,
            commercial_episode=self.episode,
            required_state_fingerprint=self.raw_fingerprint,
        )
        self.result = IgConversationAnalysisResult(
            result_key="analysis-v2:" + hashlib.sha256(b"projector-result").hexdigest(),
            legacy_snapshot=self.snapshot,
            client=self.client_row,
            commercial_episode=self.episode,
            line_id="line:primary",
            watermark_message_id=self.message.pk,
            job_revision=2,
            materiality_event_highwater=7,
            materiality_digest="a" * 64,
            authority_digest="b" * 64,
            state_correlation=v2.state_correlation(self.raw_fingerprint),
            result_schema_version=v2.RESULT_SCHEMA_VERSION,
            normalizer_version=v2.NORMALIZER_VERSION,
            interaction_type=self.snapshot.interaction_type,
            score_band=self.snapshot.score_band,
            result_digest="",
            analyzed_at=timezone.now(),
        )
        self.result.result_digest = v2.result_digest_for_instance(self.result)
        self.result.save()

    def _proposal(self, proposal_type, typed_value, **overrides):
        defaults = {
            "proposal_key": f"analysis-v2-projector:{proposal_type}",
            "analysis_result": self.result,
            "ordinal": IgAnalysisProposal.objects.count() + 1,
            "client": self.client_row,
            "commercial_episode": self.episode,
            "line_id": "line:primary",
            "proposal_type": proposal_type,
            "target_scope": IgAnalysisProposal.TargetScope.CLIENT,
            "typed_value": typed_value,
            "evidence_message_ids": [self.message.pk],
            "confidence": Decimal("0.9000"),
            "source_result_digest": self.result.result_digest,
            "expected_materiality_digest": self.result.materiality_digest,
            "expected_authority_digest": self.result.authority_digest,
            "expected_state_correlation": self.result.state_correlation,
        }
        defaults.update(overrides)
        defaults.pop("proposal_key", None)
        proposal = IgAnalysisProposal(proposal_key="", **defaults)
        proposal.proposal_key = v2.proposal_key_for_instance(proposal)
        proposal.save()
        return proposal

    def test_probability_is_shadow_validated_without_business_mutation(self):
        before = {
            "stage": self.client_row.stage,
            "sales_context": self.client_row.sales_context,
            "readiness": self.client_row.buying_readiness,
        }
        proposal = self._proposal(
            IgAnalysisProposal.ProposalType.UPDATE_PROBABILITY,
            {"probability": "0.7000", "basis": "customer_evidence"},
        )

        decision = validate_proposal(proposal)

        self.assertEqual(decision.status, IgAnalysisProposal.Status.SHADOW_VALIDATED)
        self.client_row.refresh_from_db()
        self.assertEqual(before, {
            "stage": self.client_row.stage,
            "sales_context": self.client_row.sales_context,
            "readiness": self.client_row.buying_readiness,
        })

    def test_funnel_and_repeat_actions_are_blocked_by_owned_dependencies(self):
        funnel = self._proposal(
            IgAnalysisProposal.ProposalType.CLOSE_NODE,
            {},
            target_scope=IgAnalysisProposal.TargetScope.FUNNEL_NODE,
            target_key="checkout.size",
        )
        repeat = self._proposal(
            IgAnalysisProposal.ProposalType.START_REPEAT_EPISODE,
            {"repeat_kind": "reorder"},
            proposal_key="analysis-v2-projector:repeat",
        )

        self.assertEqual(
            validate_proposal(funnel).status,
            IgAnalysisProposal.Status.BLOCKED_DEPENDENCY,
        )
        self.assertEqual(
            validate_proposal(repeat).status,
            IgAnalysisProposal.Status.BLOCKED_LEGACY_OWNER,
        )

    def test_manager_evidence_opt_out_takeover_and_stale_cursor_reject(self):
        manager_proposal = self._proposal(
            IgAnalysisProposal.ProposalType.UPDATE_PROBABILITY,
            {"probability": "0.8000", "basis": "customer_evidence"},
            evidence_message_ids=[self.manager_message.pk],
        )
        self.assertEqual(
            validate_proposal(manager_proposal).code,
            "evidence_not_customer_owned",
        )

        self.client_row.manager_takeover = True
        self.client_row.save(update_fields=["manager_takeover", "updated_at"])
        takeover = self._proposal(
            IgAnalysisProposal.ProposalType.RECORD_OBJECTION,
            {"objection_type": "price"},
            proposal_key="analysis-v2-projector:takeover",
        )
        self.assertEqual(validate_proposal(takeover).code, "manager_takeover")

        self.client_row.manager_takeover = False
        self.client_row.save(update_fields=["manager_takeover", "updated_at"])
        self.job.materiality_digest = "e" * 64
        self.job.save(update_fields=["materiality_digest", "updated_at"])
        stale = self._proposal(
            IgAnalysisProposal.ProposalType.RECORD_OBJECTION,
            {"objection_type": "price"},
            proposal_key="analysis-v2-projector:stale",
        )
        self.assertEqual(validate_proposal(stale).code, "analysis_state_superseded")

    def test_forged_result_digest_and_proposal_key_are_rejected(self):
        valid = self._proposal(
            IgAnalysisProposal.ProposalType.UPDATE_PROBABILITY,
            {"probability": "0.7000", "basis": "customer_evidence"},
        )
        IgConversationAnalysisResult._base_manager.filter(pk=self.result.pk).update(
            result_digest="0" * 64
        )
        self.result.refresh_from_db()
        valid.refresh_from_db()
        self.assertEqual(validate_proposal(valid).code, "result_digest_invalid")

        IgConversationAnalysisResult._base_manager.filter(pk=self.result.pk).update(
            result_digest=v2.result_digest_for_instance(self.result)
        )
        self.result.refresh_from_db()
        forged = self._proposal(
            IgAnalysisProposal.ProposalType.RECORD_OBJECTION,
            {"objection_type": "price"},
        )
        IgAnalysisProposal._base_manager.filter(pk=forged.pk).update(
            proposal_key="forged-proposal-key"
        )
        forged.refresh_from_db()
        self.assertEqual(validate_proposal(forged).code, "proposal_key_invalid")

    def test_artifact_digest_mismatch_is_rejected(self):
        proposal = self._proposal(
            IgAnalysisProposal.ProposalType.RECORD_OBJECTION,
            {"objection_type": "price"},
        )
        self.job.artifact_digest = "9" * 64
        self.job.save(update_fields=["artifact_digest", "updated_at"])
        self.assertEqual(
            validate_proposal(proposal).code,
            "analysis_state_superseded",
        )

    def test_projector_has_no_business_mutation_service_imports(self):
        from management.services import ig_analysis_v2_projector as projector

        source = inspect.getsource(projector)
        for forbidden in (
            "start_repeat_episode",
            "client.set_stage",
            "create_order",
            "create_invoice",
            "bot_followups",
            "bot_memory",
            "send_text",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)
