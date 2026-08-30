"""Authoritative, provider-free integrity boundary for Gemini accounting V2.

This module performs no routing, quota admission, provider I/O or dual-write.
It exists in S3a so every future S3b writer has one tested boundary for
cross-table invariants that MariaDB CHECK constraints cannot express.
"""
from __future__ import annotations

import hashlib
import json

from django.core.exceptions import ValidationError


def canonical_candidate_plan_digest(candidate_plan) -> str:
    """Return a deterministic digest without retaining plan payload elsewhere."""
    try:
        serialized = json.dumps(
            candidate_plan,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise ValidationError({"candidate_plan": "Candidate plan is not canonical JSON."}) from exc
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def validate_request_contract(request) -> None:
    """Validate immutable plan identity and a winner belonging to this graph."""
    errors: dict[str, str] = {}
    plan = request.candidate_plan
    if not isinstance(plan, list):
        errors["candidate_plan"] = "Candidate plan must be a list."
    elif plan:
        expected_digest = canonical_candidate_plan_digest(plan)
        if not request.candidate_plan_digest:
            errors["candidate_plan_digest"] = "Non-empty candidate plan requires a digest."
        elif request.candidate_plan_digest != expected_digest:
            errors["candidate_plan_digest"] = "Candidate plan digest does not match the plan."

    if request.pk is not None:
        persisted = (
            type(request)._base_manager.filter(pk=request.pk)
            .values(
                "request_id",
                "candidate_plan",
                "candidate_plan_digest",
                "winner_attempt_id",
            )
            .first()
        )
        if persisted is not None:
            if request.request_id != persisted["request_id"]:
                errors["request_id"] = "Gemini request id is immutable."
            if (
                request.candidate_plan != persisted["candidate_plan"]
                or request.candidate_plan_digest != persisted["candidate_plan_digest"]
            ):
                errors["candidate_plan"] = "Gemini candidate plan and digest are immutable."
            if (
                persisted["winner_attempt_id"] is not None
                and request.winner_attempt_id != persisted["winner_attempt_id"]
            ):
                errors["winner_attempt"] = "Gemini request winner is immutable once claimed."

    if request.winner_attempt_id is not None:
        if request.pk is None:
            errors["winner_attempt"] = "Winner cannot be attached before request creation."
        else:
            attempt = request.winner_attempt
            if attempt.request_graph_id != request.pk:
                errors["winner_attempt"] = "Winner attempt belongs to another request graph."
            elif attempt.request_id != request.request_id:
                errors["winner_attempt"] = "Winner attempt request id does not match its graph."

    if errors:
        raise ValidationError(errors)


def validate_attempt_contract(attempt) -> None:
    """Validate parent request identity and model/profile compatibility."""
    errors: dict[str, str] = {}
    if attempt.request_graph_id is not None:
        request = attempt.request_graph
        if attempt.request_id != request.request_id:
            errors["request_id"] = "Attempt request id does not match its request graph."
    if attempt.quota_profile_id is not None:
        profile = attempt.quota_profile
        if attempt.model != profile.model:
            errors["quota_profile"] = "Attempt model does not match quota profile model."
    if attempt.pk is not None:
        persisted = (
            type(attempt)._base_manager.filter(pk=attempt.pk)
            .values("request_graph_id", "request_id", "model", "quota_profile_id")
            .first()
        )
        if persisted is not None:
            for field in ("request_graph_id", "request_id", "model", "quota_profile_id"):
                if getattr(attempt, field) != persisted[field]:
                    errors[field] = "Gemini attempt graph/profile identity is immutable."
    if errors:
        raise ValidationError(errors)


def validate_quota_state_contract(state) -> None:
    """Validate the cross-table pair/profile model relation."""
    errors: dict[str, str] = {}
    if (
        state.quota_profile_id is not None
        and state.model != state.quota_profile.model
    ):
        errors["quota_profile"] = "Quota-state model does not match quota profile model."
    if state.pk is not None:
        persisted = (
            type(state)._base_manager.filter(pk=state.pk)
            .values("project_identity", "model", "quota_profile_id")
            .first()
        )
        if persisted is not None:
            for field in ("project_identity", "model", "quota_profile_id"):
                if getattr(state, field) != persisted[field]:
                    errors[field] = "Gemini quota-state identity/profile is immutable."
    if errors:
        raise ValidationError(errors)
