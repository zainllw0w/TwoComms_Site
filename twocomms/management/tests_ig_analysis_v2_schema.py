from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from django.core.exceptions import ValidationError

from management.models import (
    IgAnalysisProposal,
    IgClient,
    IgConversationAnalysisResult,
    IgConversationAnalysisSnapshot,
)


class AnalysisV2SchemaTests(TestCase):
    def setUp(self):
        self.client_row = IgClient.objects.create(igsid="analysis-v2-schema")
        self.snapshot = IgConversationAnalysisSnapshot.objects.create(
            client=self.client_row,
            dedupe_key="analysis-v2-schema:snapshot",
            score_band=IgConversationAnalysisSnapshot.Band.EXPLORING,
            interaction_type=IgConversationAnalysisSnapshot.InteractionType.PRODUCT_INTEREST,
            purchase_probability=Decimal("0.5000"),
            confidence=Decimal("0.8000"),
        )

    def _result(self, **overrides):
        defaults = {
            "result_key": "analysis-v2-schema:result",
            "legacy_snapshot": self.snapshot,
            "client": self.client_row,
            "watermark_message_id": 10,
            "job_revision": 2,
            "materiality_event_highwater": 4,
            "materiality_digest": "a" * 64,
            "authority_digest": "b" * 64,
            "artifact_digest": "c" * 64,
            "state_correlation": "d" * 64,
            "result_schema_version": "analysis-v2.1",
            "normalizer_version": "analysis-v2-normalizer.1",
            "interaction_type": self.snapshot.interaction_type,
            "score_band": self.snapshot.score_band,
            "purchase_probability": Decimal("0.5000"),
            "purchase_confidence": Decimal("0.8000"),
            "probability_basis": IgConversationAnalysisResult.ProbabilityBasis.CUSTOMER_EVIDENCE,
            "result_digest": "e" * 64,
            "analyzed_at": timezone.now(),
        }
        defaults.update(overrides)
        return IgConversationAnalysisResult.objects.create(**defaults)

    def _proposal(self, result, **overrides):
        defaults = {
            "proposal_key": "analysis-v2-schema:proposal",
            "analysis_result": result,
            "ordinal": 1,
            "client": self.client_row,
            "proposal_type": IgAnalysisProposal.ProposalType.UPDATE_PROBABILITY,
            "target_scope": IgAnalysisProposal.TargetScope.CLIENT,
            "typed_value": {"probability": "0.5000"},
            "evidence_message_ids": [10],
            "confidence": Decimal("0.8000"),
            "source_result_digest": result.result_digest,
            "expected_materiality_digest": result.materiality_digest,
            "expected_authority_digest": result.authority_digest,
            "expected_state_correlation": result.state_correlation,
        }
        defaults.update(overrides)
        return IgAnalysisProposal.objects.create(**defaults)

    def test_result_schema_has_no_customer_text_quote_or_raw_provider_body(self):
        field_names = {
            field.name for field in IgConversationAnalysisResult._meta.get_fields()
        }
        self.assertFalse(field_names & {
            "text", "quote", "summary", "raw_body", "provider_body", "key_alias",
        })
        self.assertTrue({
            "materiality_digest", "authority_digest", "artifact_digest",
            "evidence_manifest", "purchase_probability", "probability_basis",
            "injection_risk", "conflict_codes", "deferred_kind", "ltv_signal",
            "state_correlation", "usage_status", "prompt_tokens",
            "thoughts_tokens", "candidates_tokens", "total_tokens",
            "analysis_latency_ms",
        }.issubset(field_names))
        self.assertNotIn("required_state_fingerprint", field_names)

    def test_model_boundaries_reject_raw_text_in_result_or_proposal_json(self):
        with self.assertRaises(ValidationError):
            self._result(evidence_manifest=[{
                "message_id": 1,
                "source_role": "user",
                "claim_codes": ["interaction"],
                "quote": "raw customer quote",
            }])
        result = self._result()
        with self.assertRaises(ValidationError):
            self._proposal(
                result,
                proposal_key="analysis-v2-schema:raw-proposal",
                typed_value={"free_text": "call this customer tomorrow"},
            )

    def test_result_is_append_only_at_every_orm_boundary(self):
        result = self._result()
        result.score_band = IgConversationAnalysisSnapshot.Band.QUALIFIED
        with self.assertRaisesRegex(ValueError, "append-only"):
            result.save()
        with self.assertRaisesRegex(ValueError, "append-only"):
            IgConversationAnalysisResult.objects.filter(pk=result.pk).update(
                score_band=IgConversationAnalysisSnapshot.Band.QUALIFIED
            )
        with self.assertRaisesRegex(ValueError, "append-only"):
            IgConversationAnalysisResult.objects.bulk_update(
                [result], ["score_band"]
            )
        with self.assertRaisesRegex(ValueError, "append-only"):
            result.delete()

    def test_proposal_allows_status_only_mutation_and_rejects_identity_changes(self):
        result = self._result()
        proposal = self._proposal(result)

        proposal.status = IgAnalysisProposal.Status.SHADOW_VALIDATED
        proposal.decision_code = "shadow_valid"
        proposal.save(update_fields=["status", "decision_code", "updated_at"])
        proposal.refresh_from_db()
        self.assertEqual(
            proposal.status,
            IgAnalysisProposal.Status.SHADOW_VALIDATED,
        )

        proposal.typed_value = {"probability": "0.9000"}
        with self.assertRaisesRegex(ValueError, "identity is immutable"):
            proposal.save()
        with self.assertRaisesRegex(ValueError, "identity is immutable"):
            IgAnalysisProposal.objects.filter(pk=proposal.pk).update(
                typed_value={"probability": "0.9000"}
            )
        with self.assertRaisesRegex(ValueError, "cannot be deleted"):
            proposal.delete()

    def test_model_constraints_and_indexes_are_declared(self):
        result_constraints = {
            item.name for item in IgConversationAnalysisResult._meta.constraints
        }
        proposal_constraints = {
            item.name for item in IgAnalysisProposal._meta.constraints
        }
        self.assertTrue({
            "ig_anres_cursor_version_uniq",
            "ig_anres_probability_range",
            "ig_anres_confidence_range",
            "ig_anres_materiality_positive",
        }.issubset(result_constraints))
        self.assertTrue({
            "ig_anprop_result_ordinal_uniq",
            "ig_anprop_confidence_range",
            "ig_anprop_status_valid",
        }.issubset(proposal_constraints))
        self.assertEqual(
            {item.name for item in IgConversationAnalysisResult._meta.indexes},
            {
                "ig_anres_client_created", "ig_anres_episode_line",
                "ig_anres_materiality", "ig_anres_probability",
            },
        )

    def test_engine_inventory_registers_both_analysis_v2_tables(self):
        from management.services.ig_engine_health import IG_RUNTIME_TABLES

        self.assertIn("management_igconversationanalysisresult", IG_RUNTIME_TABLES)
        self.assertIn("management_iganalysisproposal", IG_RUNTIME_TABLES)
