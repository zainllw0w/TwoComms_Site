"""Deterministic shadow projector for Analysis V2 proposals.

This module validates and records decisions only.  It intentionally imports no
order, payment, follow-up, memory or funnel mutation service.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import BigIntegerField, OuterRef, Subquery, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from management.models import (
    IgAnalysisProposal,
    IgConversationAnalysisJob,
    IgConversationAnalysisResult,
    IgFunnelResetAudit,
    IgObjection,
    InstagramBotMessage,
)


PROJECTOR_VERSION = "analysis-v2-projector.1"
_FUNNEL_TYPES = frozenset({
    IgAnalysisProposal.ProposalType.CLOSE_NODE,
    IgAnalysisProposal.ProposalType.INVALIDATE_NODE,
    IgAnalysisProposal.ProposalType.OPEN_SUBFUNNEL,
    IgAnalysisProposal.ProposalType.SWITCH_ACTIVE_LINE,
})
_CLARIFICATION_CODES = frozenset({
    "artifact_conflict",
    "line_conflict",
    "live_agent_inconsistency",
    "manager_customer_conflict",
    "payment_claim_conflict",
    "product_conflict",
    "recipient_conflict",
})


@dataclass(frozen=True, slots=True)
class ProjectionDecision:
    status: str
    code: str


@dataclass(frozen=True, slots=True)
class ProjectionContext:
    job: object
    floor: int
    evidence_roles: dict[tuple[int, int], str]


def _reject(code: str) -> ProjectionDecision:
    return ProjectionDecision(IgAnalysisProposal.Status.REJECTED, code)


def _decimal_01(value):
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not Decimal("0") <= parsed <= Decimal("1"):
        return None
    return parsed.quantize(Decimal("0.0001"))


def validate_proposal(
    proposal: IgAnalysisProposal,
    *,
    now=None,
    context: ProjectionContext | None = None,
) -> ProjectionDecision:
    now = now or timezone.now()
    result = proposal.analysis_result
    client = proposal.client
    if proposal.status != IgAnalysisProposal.Status.PENDING:
        return _reject("not_pending")
    if proposal.analysis_result_id != result.pk:
        return _reject("result_missing")
    legacy_snapshot = result.legacy_snapshot
    if (
        legacy_snapshot.client_id != client.pk
        or legacy_snapshot.commercial_episode_id != result.commercial_episode_id
        or int(legacy_snapshot.last_analyzed_message_id or 0)
        != int(result.watermark_message_id or 0)
    ):
        return _reject("legacy_snapshot_scope_mismatch")
    if proposal.client_id != result.client_id or client.pk != result.client_id:
        return _reject("client_mismatch")
    if proposal.commercial_episode_id != result.commercial_episode_id:
        return _reject("episode_mismatch")
    if proposal.line_id != result.line_id:
        return _reject("line_mismatch")
    from management.services.ig_analysis_v2 import (
        proposal_key_for_instance,
        result_digest_for_instance,
        state_correlation,
    )

    if result.result_digest != result_digest_for_instance(result):
        return _reject("result_digest_invalid")
    if proposal.source_result_digest != result.result_digest:
        return _reject("result_digest_mismatch")
    if proposal.proposal_key != proposal_key_for_instance(proposal):
        return _reject("proposal_key_invalid")
    if proposal.expected_materiality_digest != result.materiality_digest:
        return _reject("materiality_digest_mismatch")
    if proposal.expected_authority_digest != result.authority_digest:
        return _reject("authority_digest_mismatch")
    if proposal.expected_state_correlation != result.state_correlation:
        return _reject("state_correlation_mismatch")
    if client.hidden_at:
        return _reject("client_hidden")
    if client.is_blocked:
        return _reject("client_blocked")
    if client.opted_out_at and (
        not client.opted_in_at or client.opted_in_at < client.opted_out_at
    ):
        return _reject("client_opted_out")
    if client.manager_takeover:
        return _reject("manager_takeover")
    if context is not None:
        job = context.job
    else:
        try:
            job = client.analysis_job
        except IgConversationAnalysisJob.DoesNotExist:
            return _reject("analysis_job_missing")
    if job is None:
        return _reject("analysis_job_missing")
    if (
        int(job.watermark_message_id or 0) != int(result.watermark_message_id or 0)
        or int(job.revision or 0) != int(result.job_revision or 0)
        or int(job.materiality_event_highwater or 0)
        != int(result.materiality_event_highwater or 0)
        or str(job.materiality_digest or "") != result.materiality_digest
        or str(job.authority_digest or "") != result.authority_digest
        or str(job.artifact_digest or "") != result.artifact_digest
        or str(job.materiality_line_id or "") != result.line_id
    ):
        return _reject("analysis_state_superseded")
    if state_correlation(job.required_state_fingerprint) != result.state_correlation:
        return _reject("state_correlation_stale")
    if client.current_commercial_episode_id != result.commercial_episode_id:
        return _reject("current_episode_changed")
    evidence_ids = []
    for value in proposal.evidence_message_ids or []:
        try:
            message_id = int(value)
        except (TypeError, ValueError):
            return _reject("invalid_evidence_id")
        if message_id not in evidence_ids:
            evidence_ids.append(message_id)
    if not evidence_ids:
        return _reject("evidence_missing")
    if context is None:
        from management.services.ig_funnel_reset import current_message_floor

        floor = current_message_floor(client)
        rows = list(
            InstagramBotMessage.objects.filter(
                client_id=client.pk,
                pk__in=evidence_ids,
                pk__gte=floor,
                pk__lte=result.watermark_message_id,
            ).values_list("pk", "role")
        )
    else:
        floor = context.floor
        rows = [
            (message_id, context.evidence_roles.get((client.pk, message_id), ""))
            for message_id in evidence_ids
            if floor <= message_id <= result.watermark_message_id
            and (client.pk, message_id) in context.evidence_roles
        ]
    if sorted(message_id for message_id, _role in rows) != sorted(evidence_ids):
        return _reject("evidence_not_current_or_owned")
    if any(role != InstagramBotMessage.Role.USER for _message_id, role in rows):
        return _reject("evidence_not_customer_owned")

    proposal_type = proposal.proposal_type
    value = proposal.typed_value if isinstance(proposal.typed_value, dict) else {}
    if proposal_type in _FUNNEL_TYPES:
        return ProjectionDecision(
            IgAnalysisProposal.Status.BLOCKED_DEPENDENCY,
            "funnel_registry_missing",
        )
    if proposal_type == IgAnalysisProposal.ProposalType.START_REPEAT_EPISODE:
        return ProjectionDecision(
            IgAnalysisProposal.Status.BLOCKED_LEGACY_OWNER,
            "legacy_repeat_event_owner",
        )
    if proposal_type == IgAnalysisProposal.ProposalType.UPDATE_PROBABILITY:
        if (
            _decimal_01(value.get("probability")) is None
            or value.get("basis")
            != IgConversationAnalysisResult.ProbabilityBasis.CUSTOMER_EVIDENCE
        ):
            return _reject("invalid_probability_value")
    elif proposal_type == IgAnalysisProposal.ProposalType.RECORD_OBJECTION:
        if str(value.get("objection_type") or "") not in IgObjection.Type.values:
            return _reject("invalid_objection_type")
    elif proposal_type == IgAnalysisProposal.ProposalType.RECORD_DEFERRED_INTENT:
        if str(value.get("kind") or "") not in (
            set(IgConversationAnalysisResult.DeferredKind.values) - {"none"}
        ):
            return _reject("invalid_deferred_kind")
    elif proposal_type == IgAnalysisProposal.ProposalType.REQUEST_CLARIFICATION:
        codes = value.get("reason_codes") if isinstance(value.get("reason_codes"), list) else []
        if not codes or any(str(code) not in _CLARIFICATION_CODES for code in codes):
            return _reject("invalid_clarification_codes")
    else:
        return _reject("unsupported_proposal_type")
    del now
    return ProjectionDecision(
        IgAnalysisProposal.Status.SHADOW_VALIDATED,
        "shadow_valid",
    )


def project_shadow_proposals(proposal_ids, *, now=None) -> dict:
    from management.services.ig_analysis_v2 import shadow_enabled

    if not shadow_enabled():
        return {"validated": 0, "blocked": 0, "rejected": 0}
    now = now or timezone.now()
    counts = {"validated": 0, "blocked": 0, "rejected": 0}
    with transaction.atomic():
        reset_floor = (
            IgFunnelResetAudit.objects.filter(client_id=OuterRef("client_id"))
            .order_by("-id")
            .values("reset_after_message_id")[:1]
        )
        proposals = list(
            IgAnalysisProposal.objects.select_for_update()
            .select_related(
                "analysis_result", "analysis_result__legacy_snapshot",
                "client", "client__analysis_job",
                "client__current_commercial_episode",
            )
            .annotate(
                _materiality_reset_after_message_id=Coalesce(
                    Subquery(reset_floor, output_field=BigIntegerField()),
                    Value(0, output_field=BigIntegerField()),
                )
            )
            .filter(
                pk__in=list(proposal_ids or [])[:12],
                status=IgAnalysisProposal.Status.PENDING,
            )
            .order_by("id")
        )
        from management.services.ig_funnel_reset import current_message_floor

        clients_by_id = {}
        for proposal in proposals:
            client = clients_by_id.setdefault(proposal.client_id, proposal.client)
            client.materiality_reset_after_message_id = (
                proposal._materiality_reset_after_message_id
            )
        floor_by_client = {
            client_id: current_message_floor(client)
            for client_id, client in clients_by_id.items()
        }
        all_evidence_ids = {
            int(value)
            for proposal in proposals
            for value in (proposal.evidence_message_ids or [])
            if str(value).isdigit()
        }
        client_ids = {proposal.client_id for proposal in proposals}
        evidence_roles = {
            (client_id, message_id): role
            for client_id, message_id, role in InstagramBotMessage.objects.filter(
                client_id__in=client_ids,
                pk__in=all_evidence_ids,
            ).values_list("client_id", "pk", "role")
        }
        decided = []
        for proposal in proposals:
            try:
                job = proposal.client.analysis_job
            except IgConversationAnalysisJob.DoesNotExist:
                job = None
            decision = validate_proposal(
                proposal,
                now=now,
                context=ProjectionContext(
                    job=job,
                    floor=floor_by_client[proposal.client_id],
                    evidence_roles=evidence_roles,
                ),
            )
            proposal.status = decision.status
            proposal.decision_code = decision.code
            proposal.projector_version = PROJECTOR_VERSION
            proposal.decided_at = now
            proposal.updated_at = now
            decided.append(proposal)
            if decision.status == IgAnalysisProposal.Status.SHADOW_VALIDATED:
                counts["validated"] += 1
            elif decision.status in {
                IgAnalysisProposal.Status.BLOCKED_DEPENDENCY,
                IgAnalysisProposal.Status.BLOCKED_LEGACY_OWNER,
            }:
                counts["blocked"] += 1
            else:
                counts["rejected"] += 1
        if decided:
            # Objects were fully validated above; the base manager avoids the
            # public QuerySet.update boundary seeing Django's internal CASE
            # expressions while still issuing one bounded SQL UPDATE.
            IgAnalysisProposal._base_manager.bulk_update(
                decided,
                [
                    "status", "decision_code", "projector_version",
                    "decided_at", "updated_at",
                ],
            )
    return counts
