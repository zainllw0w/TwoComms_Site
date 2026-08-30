from decimal import Decimal
import hashlib

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
            "result_key": "analysis-v2:" + hashlib.sha256(b"schema-result").hexdigest(),
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
            "evidence_manifest": [{
                "message_id": 1,
                "source_role": "user",
                "claim_codes": ["purchase_intent"],
            }],
            "customer_evidence_count": 1,
            "result_digest": "e" * 64,
            "analyzed_at": timezone.now(),
        }
        defaults.update(overrides)
        return IgConversationAnalysisResult.objects.create(**defaults)

    def _proposal(self, result, **overrides):
        defaults = {
            "proposal_key": "analysis-proposal:" + hashlib.sha256(b"schema-proposal").hexdigest(),
            "analysis_result": result,
            "ordinal": 1,
            "client": self.client_row,
            "proposal_type": IgAnalysisProposal.ProposalType.UPDATE_PROBABILITY,
            "target_scope": IgAnalysisProposal.TargetScope.CLIENT,
            "typed_value": {
                "probability": "0.5000",
                "basis": "customer_evidence",
            },
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
                proposal_key="analysis-proposal:" + hashlib.sha256(b"raw-proposal").hexdigest(),
                typed_value={"free_text": "call this customer tomorrow"},
            )

    def test_exact_enums_refs_and_finite_numbers_reject_pii_like_codes(self):
        with self.assertRaises(ValidationError):
            self._result(active_objection_type="customername")
        with self.assertRaises(ValidationError):
            self._result(project_slot="gslot_customername")
        with self.assertRaises(ValidationError):
            self._result(gemini_request_ref="internal-request-id")
        result = self._result()
        with self.assertRaises(ValidationError):
            self._proposal(
                result,
                proposal_key="analysis-proposal:" + hashlib.sha256(b"pii-kind").hexdigest(),
                proposal_type=IgAnalysisProposal.ProposalType.RECORD_DEFERRED_INTENT,
                typed_value={
                    "kind": "customername",
                    "condition_code": "payday",
                    "deferred_until": "",
                },
            )
        with self.assertRaises(ValidationError):
            self._proposal(
                result,
                proposal_key="analysis-proposal:" + hashlib.sha256(b"nan").hexdigest(),
                typed_value={
                    "probability": float("nan"),
                    "basis": "customer_evidence",
                },
            )
        proposal = self._proposal(
            result,
            proposal_key="analysis-proposal:" + hashlib.sha256(b"mutable").hexdigest(),
        )
        with self.assertRaises(ValidationError):
            IgAnalysisProposal.objects.filter(pk=proposal.pk).update(
                decision_code="customername"
            )

    def test_manifest_counts_and_probability_basis_are_recomputed(self):
        with self.assertRaises(ValidationError):
            self._result(customer_evidence_count=0)
        with self.assertRaises(ValidationError):
            self._result(
                evidence_manifest=[{
                    "message_id": 1,
                    "source_role": "user",
                    "claim_codes": ["interaction"],
                }],
            )
        with self.assertRaises(ValidationError):
            self._result(
                probability_basis=(
                    IgConversationAnalysisResult.ProbabilityBasis.DETERMINISTIC_OPT_OUT
                ),
                purchase_probability=Decimal("0.0000"),
                purchase_confidence=Decimal("1.0000"),
            )

    def test_version_tokens_are_forward_safe_but_not_free_text(self):
        result = self._result(
            result_key="analysis-v2:" + hashlib.sha256(b"future-version").hexdigest(),
            analysis_model="gemini-4.1-flash-pro-preview",
            prompt_version="2030-01-01.crm.analysis-v9",
            routing_policy_version="gemini-routing-v9.2",
            reasoning_policy_version="reasoning-v4.3",
        )
        self.assertEqual(result.prompt_version, "2030-01-01.crm.analysis-v9")
        with self.assertRaises(ValidationError):
            self._result(prompt_version="customername")

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

    def test_protected_base_managers_reject_raw_pii_bulk_create(self):
        bad_result = IgConversationAnalysisResult(
            result_key="analysis-v2:" + hashlib.sha256(b"base-manager-result").hexdigest(),
            legacy_snapshot=self.snapshot,
            client=self.client_row,
            watermark_message_id=10,
            job_revision=2,
            materiality_event_highwater=4,
            materiality_digest="a" * 64,
            authority_digest="b" * 64,
            artifact_digest="c" * 64,
            state_correlation="d" * 64,
            result_schema_version="analysis-v2.1",
            normalizer_version="analysis-v2-normalizer.1",
            interaction_type=self.snapshot.interaction_type,
            score_band=self.snapshot.score_band,
            purchase_probability=Decimal("0.5000"),
            purchase_confidence=Decimal("0.8000"),
            probability_basis=(
                IgConversationAnalysisResult.ProbabilityBasis.CUSTOMER_EVIDENCE
            ),
            evidence_manifest=[{
                "message_id": 1,
                "source_role": "user",
                "claim_codes": ["purchase_intent"],
                "quote": "Call +380501234567 or customer@example.com",
            }],
            customer_evidence_count=1,
            result_digest="e" * 64,
            analyzed_at=timezone.now(),
        )
        with self.assertRaises(ValidationError):
            IgConversationAnalysisResult._base_manager.bulk_create([bad_result])

        result = self._result()
        bad_proposal = IgAnalysisProposal(
            proposal_key=(
                "analysis-proposal:"
                + hashlib.sha256(b"base-manager-proposal").hexdigest()
            ),
            analysis_result=result,
            ordinal=1,
            client=self.client_row,
            proposal_type=IgAnalysisProposal.ProposalType.UPDATE_PROBABILITY,
            target_scope=IgAnalysisProposal.TargetScope.CLIENT,
            typed_value={
                "probability": "0.5000",
                "basis": "customer_evidence",
                "phone": "+380501234567",
            },
            evidence_message_ids=[10],
            confidence=Decimal("0.8000"),
            source_result_digest=result.result_digest,
            expected_materiality_digest=result.materiality_digest,
            expected_authority_digest=result.authority_digest,
            expected_state_correlation=result.state_correlation,
        )
        with self.assertRaises(ValidationError):
            IgAnalysisProposal._base_manager.bulk_create([bad_proposal])

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
