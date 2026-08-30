"""Fail-soft Gemini accounting V2 shadow runtime.

This module is deliberately observational.  ``off`` is the default and returns
null objects before any accounting database access.  ``shadow`` records what
the V2 admission policy would have decided, but the legacy gateway remains the
only authority that can allow, deny, order or retry a provider call.

No prompt, customer text, credential, environment alias or provider body is
stored in ``GeminiRequest.candidate_plan``.  Provider attempts keep the legacy
alias field for the existing operational scoreboard, while quota coordination
is keyed only by the stable, non-secret project identity.
"""
from __future__ import annotations

import datetime as dt
import math
import re
import threading
import time
import uuid
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import DatabaseError, IntegrityError, transaction
from django.db.models import Case, Count, F, IntegerField, Min, Sum, When
from django.utils import timezone


PT = ZoneInfo("America/Los_Angeles")
ACCOUNTING_POLICY_VERSION = "gemini-accounting-shadow-v1"
OWNER_PROFILE_VERSION = "owner-observed-2026-08-29.v1"
PROFILED_MODELS = frozenset({
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
})
ATTEMPT_PERMIT_SECONDS = 180
_SAFE_TOKEN = re.compile(r"^[A-Za-z0-9_.:-]{1,120}$")
_SAFE_REASON = re.compile(r"^[a-z0-9_]{0,32}$")
_PLAN_FIELDS = frozenset({
    "candidate_index",
    "project_identity",
    "model",
    "identity_status",
    "initial_skip_reason",
})


def parse_effective_from(value) -> dt.datetime | None:
    """Parse one aware ISO timestamp; invalid/naive values fail closed."""
    if isinstance(value, dt.datetime):
        parsed = value
    else:
        raw = str(value or "").strip()
        if not raw:
            return None
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        try:
            parsed = dt.datetime.fromisoformat(raw)
        except (TypeError, ValueError):
            return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(dt.timezone.utc)


def is_pacific_midnight(value: dt.datetime | None) -> bool:
    if value is None:
        return False
    local = value.astimezone(PT)
    return local.time().replace(tzinfo=None) == dt.time.min


def configured_mode() -> str:
    return str(getattr(settings, "GEMINI_ACCOUNTING_V2_MODE", "off") or "off").strip().casefold()


def shadow_runtime_active(*, now=None) -> bool:
    """Return true only after an explicitly configured Pacific-midnight gate."""
    if configured_mode() != "shadow":
        return False
    effective = parse_effective_from(
        getattr(settings, "GEMINI_ACCOUNTING_V2_EFFECTIVE_FROM", "")
    )
    if not is_pacific_midnight(effective):
        return False
    current = now or timezone.now()
    return current >= effective


def _safe_token(value, *, limit: int) -> str:
    text = str(value or "").strip()[:limit]
    return text if not text or _SAFE_TOKEN.fullmatch(text) else ""


def _safe_reason(value) -> str:
    text = str(value or "").strip().casefold()[:32]
    return text if _SAFE_REASON.fullmatch(text) else ""


def sanitize_candidate_plan(candidate_plan) -> list[dict]:
    """Return the strict, secret-free persisted candidate representation."""
    result: list[dict] = []
    for position, raw in enumerate(candidate_plan or (), start=1):
        if not isinstance(raw, dict):
            continue
        try:
            candidate_index = max(1, int(raw.get("candidate_index") or position))
        except (TypeError, ValueError):
            candidate_index = position
        identity = _safe_token(raw.get("project_identity"), limit=80)
        model = _safe_token(raw.get("model"), limit=80)
        if not model:
            continue
        identity_status = str(raw.get("identity_status") or "").strip().casefold()
        if identity_status not in {"known", "unknown", "unconfigured", "duplicate"}:
            identity_status = "known" if identity else "unknown"
        item = {
            "candidate_index": candidate_index,
            "project_identity": identity,
            "model": model,
            "identity_status": identity_status,
            "initial_skip_reason": _safe_reason(raw.get("skip_reason")),
        }
        # This assertion makes adding a field an explicit privacy decision.
        if set(item) != _PLAN_FIELDS:
            raise AssertionError("Gemini candidate plan allowlist drift")
        result.append(item)
    return result


def generic_candidate_plan(*, role: str, models, manual_key: str | None = None) -> list[dict]:
    """Build an observational plan without changing the executable iterator."""
    from management.services import gemini_keys

    rows: list[dict] = []
    candidate_index = 0
    manual_value = str(manual_key or "").strip()
    if manual_value:
        alias = gemini_keys.configured_alias_for_secret(manual_value)
        identity = gemini_keys.project_group(alias) if alias else ""
        for model in models:
            candidate_index += 1
            rows.append({
                "candidate_index": candidate_index,
                "key_name": "(manual)",
                "model": str(model),
                "project_identity": identity,
                "identity_status": "known" if identity else "unknown",
                "skip_reason": "",
            })

    pool = gemini_keys.role_key_pools().get(role, {"own": [], "borrow": []})
    aliases: list[str] = []
    for alias in (*pool.get("own", ()), *pool.get("borrow", ())):
        if alias not in aliases:
            aliases.append(alias)
    seen_values_by_model: dict[str, list[str]] = {}
    seen_projects_by_model: dict[str, set[str]] = {}
    for model in models:
        seen_values = seen_values_by_model.setdefault(str(model), [])
        seen_projects = seen_projects_by_model.setdefault(str(model), set())
        for alias in aliases:
            candidate_index += 1
            value = gemini_keys._key_value(alias)
            identity = gemini_keys.project_group(alias)
            duplicate = bool(
                (value and value in seen_values)
                or (identity and identity in seen_projects)
            )
            rows.append({
                "candidate_index": candidate_index,
                "key_name": alias,
                "model": str(model),
                "project_identity": identity,
                "identity_status": (
                    "unconfigured" if not value else "duplicate" if duplicate else "known"
                ),
                "skip_reason": (
                    "unconfigured" if not value else "duplicate_credential" if duplicate else ""
                ),
            })
            if value and value not in seen_values:
                seen_values.append(value)
            if identity and value:
                seen_projects.add(identity)
    return rows


class NullAttemptBoundary:
    attempt_id = None

    def before_provider(self, **_kwargs) -> None:
        return None

    def succeeded(self, _usage=None) -> None:
        return None

    def failed(self, _error) -> None:
        return None

    def manual_result(self, **_kwargs) -> None:
        return None

    def cancelled_pre_dispatch(self, _error=None) -> None:
        return None


class NullRequestObserver:
    enabled = False
    request_id = ""
    graph_id = None

    def attempt(self, **_kwargs):
        return NullAttemptBoundary()

    def resolve_failure(self, _reason="exhausted") -> None:
        return None

    def candidate_index(self, _key_name: str, _model: str) -> int:
        return 0


NULL_OBSERVER = NullRequestObserver()


def _routing_value(routing_decision, name: str, default=""):
    value = getattr(routing_decision, name, default) if routing_decision is not None else default
    return getattr(value, "value", value)


def begin_request(
    *,
    request_id: str | None,
    role: str,
    reasoning_task: str,
    candidate_plan,
    deadline_seconds: float | None = None,
    routing_decision=None,
    lane: str = "",
) -> "RequestObserver | NullRequestObserver":
    """Create one immutable graph only when the shadow gate is active."""
    if not shadow_runtime_active():
        return NULL_OBSERVER
    try:
        from management.models import GeminiRequest
        from management.services.gemini_accounting_contract import (
            canonical_candidate_plan_digest,
        )
        from management.services.ig_turn_lineage import current_context

        now = timezone.now()
        lineage = current_context()
        safe_plan = sanitize_candidate_plan(candidate_plan)
        resolved_lane = str(
            lane
            or lineage.get("lane")
            or ("followup" if reasoning_task == "follow_cta_copy" else "live" if role == "chat" else "analysis")
        )[:16]
        task_class = str(
            _routing_value(
                routing_decision,
                "task_class",
                "diagnostic" if resolved_lane == "diagnostic" else "durable_analysis" if role != "chat" else "ordinary_live",
            )
        )[:24]
        deadline_ms = max(0, int(float(deadline_seconds or 0) * 1000))
        models = {str(item.get("model") or "") for item in safe_plan}
        graph = GeminiRequest.objects.create(
            request_id=str(request_id or uuid.uuid4().hex)[:40],
            lane=resolved_lane,
            task_class=task_class,
            reasoning_task=str(reasoning_task or "")[:40],
            logical_turn_id=str(lineage.get("logical_turn_id") or "")[:64],
            source_message_id=lineage.get("source_message_id") or None,
            client_id=lineage.get("client_id") or None,
            recovery_job_id=lineage.get("recovery_job_id") or None,
            routing_policy_version=str(_routing_value(routing_decision, "policy_version", ""))[:32],
            accounting_policy_version=ACCOUNTING_POLICY_VERSION,
            quota_profile_version=(OWNER_PROFILE_VERSION if models and models <= PROFILED_MODELS else ""),
            authority_snapshot_version=str(
                _routing_value(routing_decision, "authority_snapshot_version", "")
            )[:32],
            routing_mode=str(_routing_value(routing_decision, "routing_mode", ""))[:12],
            commercial_risk=str(_routing_value(routing_decision, "commercial_risk", ""))[:16],
            requires_media_reasoning=bool(
                _routing_value(routing_decision, "requires_media_reasoning", False)
            ),
            candidate_plan=safe_plan,
            candidate_plan_digest=canonical_candidate_plan_digest(safe_plan),
            deadline_ms=deadline_ms,
            deadline_at=(now + dt.timedelta(milliseconds=deadline_ms) if deadline_ms else None),
            accounting_mode=GeminiRequest.AccountingMode.SHADOW,
        )
        return RequestObserver(graph_id=graph.pk, request_id=graph.request_id, raw_plan=candidate_plan)
    except Exception:
        return NULL_OBSERVER


@dataclass
class AttemptBoundary:
    observer: "RequestObserver"
    key_name: str
    model: str
    candidate_index: int
    attempt_index: int
    attempt_id: int | None = None
    state_id: int | None = None
    started_monotonic: float | None = None

    def before_provider(self, *, serialized_bytes: int, inline_count: int = 0) -> None:
        try:
            self.observer._before_provider(
                self,
                serialized_bytes=max(0, int(serialized_bytes or 0)),
                inline_count=max(0, int(inline_count or 0)),
            )
        except Exception:
            # Shadow accounting never changes a real provider call.
            self.attempt_id = None
            self.state_id = None

    def succeeded(self, usage=None) -> None:
        try:
            self.observer._finish(self, succeeded=True, usage=usage or {})
        except Exception:
            return None

    def failed(self, error) -> None:
        try:
            self.observer._finish(self, succeeded=False, error=error)
        except Exception:
            return None

    def manual_result(
        self,
        *,
        succeeded: bool,
        http_code: int | None = None,
        failure_kind: str = "",
        usage=None,
    ) -> None:
        error = None if succeeded else ManualProviderFailure(
            failure_kind=failure_kind,
            http_code=http_code,
        )
        try:
            self.observer._finish(
                self,
                succeeded=succeeded,
                error=error,
                usage=usage or {},
                http_code=http_code,
                failure_kind=failure_kind,
            )
        except Exception:
            return None

    def cancelled_pre_dispatch(self, error=None) -> None:
        try:
            self.observer._cancel_pre_dispatch(self, error=error)
        except Exception:
            return None


@dataclass(frozen=True)
class ManualProviderFailure(Exception):
    failure_kind: str
    http_code: int | None = None

    def __str__(self):
        return self.failure_kind or "provider_error"


class RequestObserver:
    enabled = True

    def __init__(self, *, graph_id: int, request_id: str, raw_plan):
        self.graph_id = int(graph_id)
        self.request_id = str(request_id)
        self._counter = 0
        self._lock = threading.Lock()
        self._candidate_indexes: dict[tuple[str, str], int] = {}
        self._candidate_identities: dict[tuple[str, str], str] = {}
        for position, raw in enumerate(raw_plan or (), start=1):
            if not isinstance(raw, dict):
                continue
            key = (str(raw.get("key_name") or ""), str(raw.get("model") or ""))
            try:
                index = max(1, int(raw.get("candidate_index") or position))
            except (TypeError, ValueError):
                index = position
            self._candidate_indexes.setdefault(key, index)
            self._candidate_identities.setdefault(
                key, _safe_token(raw.get("project_identity"), limit=80)
            )

    def candidate_index(self, key_name: str, model: str) -> int:
        return int(self._candidate_indexes.get((str(key_name), str(model)), 0) or 0)

    def attempt(self, *, key_name: str, model: str, candidate_index: int = 0):
        with self._lock:
            self._counter += 1
            attempt_index = self._counter
        return AttemptBoundary(
            observer=self,
            key_name=str(key_name or "")[:40],
            model=str(model or "")[:80],
            candidate_index=max(
                0,
                int(candidate_index or self.candidate_index(key_name, model) or 0),
            ),
            attempt_index=attempt_index,
        )

    def _identity_for(self, boundary: AttemptBoundary) -> str:
        identity = self._candidate_identities.get(
            (boundary.key_name, boundary.model), ""
        )
        if identity:
            return identity
        if boundary.key_name.startswith("GEMINI_API"):
            from management.services import gemini_keys

            return _safe_token(gemini_keys.project_group(boundary.key_name), limit=80)
        return ""

    def _active_profile(self, model: str, now):
        from management.models import GeminiQuotaProfile

        return (
            GeminiQuotaProfile.objects.filter(
                model=model,
                effective_from__lte=now,
            )
            .filter(
                models_Q_effective(now)
            )
            .order_by("-effective_from", "-id")
            .first()
        )

    def _before_provider(
        self,
        boundary: AttemptBoundary,
        *,
        serialized_bytes: int,
        inline_count: int,
    ) -> None:
        from management.models import (
            GeminiQuotaState,
            GeminiRequest,
            GeminiRequestAttempt,
        )
        from management.services.gemini_quota import pacific_day

        now = timezone.now()
        identity = self._identity_for(boundary)
        estimated = max(1, int(math.ceil(serialized_bytes / 4)))
        profile = self._active_profile(boundary.model, now) if identity else None
        expiry = now + dt.timedelta(seconds=ATTEMPT_PERMIT_SECONDS)

        with transaction.atomic():
            state = None
            shadow_decision = GeminiRequestAttempt.ShadowDecision.UNKNOWN
            deny_reason = "unknown_project" if not identity else "missing_profile" if profile is None else ""
            if identity and profile is not None:
                state, _created = (
                    GeminiQuotaState.objects.select_for_update()
                    .select_related("quota_profile")
                    .get_or_create(
                    project_identity=identity,
                    model=boundary.model,
                    defaults={
                        "quota_profile": profile,
                        "pacific_day": pacific_day(now),
                    },
                    )
                )
                profile = state.quota_profile
                self._reconcile_expired_locked(state, now=now)
                if state.pacific_day != pacific_day(now):
                    state.pacific_day = pacific_day(now)
                    state.rpd_reserved = 0
                    state.rpd_dispatched = 0
                    state.rpd_uncertain = 0

                rolling = GeminiRequestAttempt.objects.filter(
                    project_identity=identity,
                    model=boundary.model,
                    provider_started_at__gte=now - dt.timedelta(seconds=60),
                    provider_started_at__lte=now,
                ).aggregate(
                    requests=Count("id"),
                    prompt_tokens=Sum(
                        Case(
                            When(prompt_tokens__gt=0, then=F("prompt_tokens")),
                            default=F("reserved_prompt_tokens"),
                            output_field=IntegerField(),
                        )
                    ),
                )
                requests_60 = int(rolling.get("requests") or 0)
                prompt_60 = int(rolling.get("prompt_tokens") or 0)
                active_block = self._active_provider_block(state.provider_blocks, now)
                if active_block:
                    shadow_decision = GeminiRequestAttempt.ShadowDecision.DENY
                    deny_reason = "provider_block"
                elif int(state.rpd_dispatched or 0) >= int(profile.rpd_limit):
                    shadow_decision = GeminiRequestAttempt.ShadowDecision.DENY
                    deny_reason = "rpd_exhausted"
                elif requests_60 >= int(profile.rpm_limit):
                    shadow_decision = GeminiRequestAttempt.ShadowDecision.DENY
                    deny_reason = "rpm_exhausted"
                elif int(state.in_flight_count or 0) >= int(profile.permit_limit):
                    shadow_decision = GeminiRequestAttempt.ShadowDecision.DENY
                    deny_reason = "permit_exhausted"
                elif not inline_count and prompt_60 + estimated > int(profile.input_tpm_limit):
                    shadow_decision = GeminiRequestAttempt.ShadowDecision.DENY
                    deny_reason = "tpm_exhausted"
                elif inline_count or profile.estimator_version == "shadow-calibration-required":
                    shadow_decision = GeminiRequestAttempt.ShadowDecision.UNKNOWN
                    deny_reason = "estimator_uncalibrated"
                else:
                    shadow_decision = GeminiRequestAttempt.ShadowDecision.ALLOW

            graph = GeminiRequest.objects.select_for_update().get(pk=self.graph_id)
            attempt = GeminiRequestAttempt.objects.create(
                request_id=self.request_id,
                request_graph=graph,
                role=self._role_for_graph(graph),
                key_name=boundary.key_name,
                project_group=identity,
                project_identity=identity,
                model=boundary.model,
                outcome="provider_started",
                fsm_state=GeminiRequestAttempt.FsmState.PROVIDER_STARTED,
                quota_profile=profile,
                accounting_mode="shadow",
                shadow_decision=shadow_decision,
                shadow_deny_reason=deny_reason[:32],
                logical_turn_id=graph.logical_turn_id,
                source_message_id=graph.source_message_id,
                client_id=graph.client_id,
                lane=graph.lane,
                attempt_index=boundary.attempt_index,
                candidate_index=boundary.candidate_index,
                recovery_job_id=graph.recovery_job_id,
                estimated_prompt_tokens=estimated,
                reserved_prompt_tokens=estimated,
                reserved_at=now,
                reservation_expires_at=expiry,
                provider_started_at=now,
                dispatch_pacific_day=pacific_day(now),
                permit_expires_at=expiry,
            )
            boundary.attempt_id = attempt.pk
            boundary.state_id = state.pk if state is not None else None
            boundary.started_monotonic = time.monotonic()

            if state is not None:
                next_expiry = (
                    min(state.next_permit_expiry_at, expiry)
                    if state.next_permit_expiry_at
                    else expiry
                )
                GeminiQuotaState.objects.filter(pk=state.pk).update(
                    pacific_day=state.pacific_day,
                    rpd_reserved=state.rpd_reserved,
                    rpd_dispatched=int(state.rpd_dispatched or 0) + 1,
                    rpd_uncertain=state.rpd_uncertain,
                    in_flight_count=int(state.in_flight_count or 0) + 1,
                    next_permit_expiry_at=next_expiry,
                    accounting_status=GeminiQuotaState.AccountingStatus.AVAILABLE,
                    revision=F("revision") + 1,
                    updated_at=now,
                )

            if graph.provider_phase_started_at is None:
                GeminiRequest.objects.filter(
                    pk=graph.pk,
                    provider_phase_started_at__isnull=True,
                ).update(provider_phase_started_at=now, updated_at=now)

    def _cancel_pre_dispatch(self, boundary: AttemptBoundary, *, error=None) -> None:
        """Persist a local final-payload failure without any quota state spend."""
        if boundary.attempt_id:
            return
        from management.models import GeminiRequest, GeminiRequestAttempt

        now = timezone.now()
        identity = self._identity_for(boundary)
        classified = classify_failure(error, failure_kind="invalid_payload")
        with transaction.atomic():
            graph = GeminiRequest.objects.select_for_update().get(pk=self.graph_id)
            attempt = GeminiRequestAttempt.objects.create(
                request_id=self.request_id,
                request_graph=graph,
                role=self._role_for_graph(graph),
                key_name=boundary.key_name,
                project_group=identity,
                project_identity=identity,
                model=boundary.model,
                outcome="cancelled_pre_dispatch",
                fsm_state=GeminiRequestAttempt.FsmState.CANCELLED_PRE_DISPATCH,
                accounting_mode="shadow",
                shadow_decision=GeminiRequestAttempt.ShadowDecision.UNKNOWN,
                shadow_deny_reason="local_payload",
                failure_kind=classified["failure_kind"],
                http_code=classified["http_code"],
                provider_reason=classified["provider_reason"],
                decision="stop_payload",
                logical_turn_id=graph.logical_turn_id,
                source_message_id=graph.source_message_id,
                client_id=graph.client_id,
                lane=graph.lane,
                attempt_index=boundary.attempt_index,
                candidate_index=boundary.candidate_index,
                recovery_job_id=graph.recovery_job_id,
                finished_at=now,
                settled_at=now,
                reservation_released_at=now,
                permit_released_at=now,
            )
            boundary.attempt_id = attempt.pk
            outcomes = dict(graph.candidate_outcomes or {})
            outcomes[str(boundary.candidate_index or boundary.attempt_index)] = {
                "attempt_index": boundary.attempt_index,
                "outcome": "cancelled_pre_dispatch",
                "failure_kind": classified["failure_kind"],
            }
            GeminiRequest.objects.filter(pk=graph.pk).update(
                candidate_outcomes=outcomes,
                updated_at=now,
            )

    @staticmethod
    def _role_for_graph(graph) -> str:
        if graph.lane in {"live", "recovery", "holding"}:
            return "chat"
        if graph.lane == "diagnostic":
            return "diagnostic"
        return "management" if graph.reasoning_task != "conversion_analysis" else "checker"

    @staticmethod
    def _active_provider_block(blocks, now) -> bool:
        for value in (blocks or {}).values():
            if not isinstance(value, dict):
                continue
            until = parse_effective_from(value.get("until"))
            if until and until > now:
                return True
        return False

    def _reconcile_expired_locked(self, state, *, now) -> None:
        from management.models import GeminiRequestAttempt

        stale = list(
            GeminiRequestAttempt.objects.select_for_update().filter(
                project_identity=state.project_identity,
                model=state.model,
                fsm_state__in=(
                    GeminiRequestAttempt.FsmState.RESERVED,
                    GeminiRequestAttempt.FsmState.PROVIDER_STARTED,
                ),
                permit_expires_at__lte=now,
            )[:50]
        )
        if not stale:
            return
        uncertain = 0
        for row in stale:
            if row.fsm_state == GeminiRequestAttempt.FsmState.PROVIDER_STARTED:
                row.fsm_state = GeminiRequestAttempt.FsmState.TIMEOUT_AMBIGUOUS
                row.outcome = "timeout_ambiguous"
                row.failure_kind = "stale_provider_boundary"
                uncertain += 1
            else:
                row.fsm_state = GeminiRequestAttempt.FsmState.CANCELLED_PRE_DISPATCH
                row.outcome = "cancelled_pre_dispatch"
                row.reservation_released_at = now
            row.finished_at = now
            row.settled_at = now
            row.permit_released_at = now
            row.save(update_fields=[
                "fsm_state", "outcome", "failure_kind", "finished_at",
                "settled_at", "reservation_released_at", "permit_released_at",
            ])
        if uncertain:
            state.rpd_uncertain = int(state.rpd_uncertain or 0) + uncertain
        active = GeminiRequestAttempt.objects.filter(
            project_identity=state.project_identity,
            model=state.model,
            fsm_state__in=(
                GeminiRequestAttempt.FsmState.RESERVED,
                GeminiRequestAttempt.FsmState.PROVIDER_STARTED,
            ),
        ).aggregate(count=Count("id"), next_expiry=Min("permit_expires_at"))
        state.in_flight_count = int(active.get("count") or 0)
        state.next_permit_expiry_at = active.get("next_expiry")

    def _finish(
        self,
        boundary: AttemptBoundary,
        *,
        succeeded: bool,
        error=None,
        usage=None,
        http_code: int | None = None,
        failure_kind: str = "",
    ) -> None:
        if not boundary.attempt_id:
            return
        from management.models import GeminiQuotaState, GeminiRequest, GeminiRequestAttempt

        now = timezone.now()
        usage = usage if isinstance(usage, dict) else {}
        latency_ms = max(
            0,
            int((time.monotonic() - boundary.started_monotonic) * 1000)
            if boundary.started_monotonic is not None
            else 0,
        )
        classified = classify_failure(error, http_code=http_code, failure_kind=failure_kind)
        with transaction.atomic():
            attempt = GeminiRequestAttempt.objects.select_for_update().get(
                pk=boundary.attempt_id
            )
            late_success = bool(
                succeeded
                and attempt.fsm_state == GeminiRequestAttempt.FsmState.TIMEOUT_AMBIGUOUS
            )
            if attempt.fsm_state in {
                GeminiRequestAttempt.FsmState.SUCCEEDED,
                GeminiRequestAttempt.FsmState.SUCCEEDED_LATE,
                GeminiRequestAttempt.FsmState.FAILED,
                GeminiRequestAttempt.FsmState.TIMEOUT_AMBIGUOUS,
                GeminiRequestAttempt.FsmState.CANCELLED_PRE_DISPATCH,
            } and not late_success:
                return

            if succeeded:
                attempt.fsm_state = (
                    GeminiRequestAttempt.FsmState.SUCCEEDED_LATE
                    if late_success
                    else GeminiRequestAttempt.FsmState.SUCCEEDED
                )
                attempt.outcome = "succeeded"
                attempt.failure_kind = ""
                attempt.http_code = 200
                attempt.provider_reason = ""
            else:
                attempt.fsm_state = (
                    GeminiRequestAttempt.FsmState.TIMEOUT_AMBIGUOUS
                    if classified["timeout_ambiguous"]
                    else GeminiRequestAttempt.FsmState.FAILED
                )
                attempt.outcome = (
                    "timeout_ambiguous" if classified["timeout_ambiguous"] else "failed"
                )
                attempt.failure_kind = classified["failure_kind"]
                attempt.http_code = classified["http_code"]
                attempt.provider_reason = classified["provider_reason"]
                attempt.provider_quota_metric = classified["quota_metric"]
                attempt.provider_quota_id = classified["quota_id"]
                attempt.provider_quota_dimensions = classified["quota_dimensions"]
                attempt.provider_retry_after_seconds = classified["retry_after_seconds"]
                attempt.provider_block_until = classified["block_until"]
            attempt.prompt_tokens = _usage_int(usage, "promptTokenCount", "prompt_token_count")
            attempt.thoughts_tokens = _usage_int(usage, "thoughtsTokenCount", "thoughts_token_count")
            attempt.candidates_tokens = _usage_int(usage, "candidatesTokenCount", "candidates_token_count")
            attempt.total_tokens = _usage_int(usage, "totalTokenCount", "total_token_count")
            attempt.latency_ms = latency_ms
            attempt.finished_at = now
            attempt.settled_at = now
            attempt.permit_released_at = now
            attempt.save(update_fields=[
                "fsm_state", "outcome", "failure_kind", "http_code",
                "provider_reason", "provider_quota_metric", "provider_quota_id",
                "provider_quota_dimensions", "provider_retry_after_seconds",
                "provider_block_until", "prompt_tokens", "thoughts_tokens",
                "candidates_tokens", "total_tokens", "latency_ms", "finished_at",
                "settled_at", "permit_released_at",
            ])

            state = None
            if boundary.state_id:
                state = GeminiQuotaState.objects.select_for_update().get(
                    pk=boundary.state_id
                )
                state.in_flight_count = max(0, int(state.in_flight_count or 0) - 1)
                if succeeded:
                    state.last_success_at = now
                    state.last_latency_ms = latency_ms
                    state.latency_ewma_ms = (
                        latency_ms
                        if not state.latency_ewma_ms
                        else int(state.latency_ewma_ms * 0.7 + latency_ms * 0.3)
                    )
                    if late_success and state.rpd_uncertain:
                        state.rpd_uncertain = max(0, int(state.rpd_uncertain) - 1)
                else:
                    state.last_failure_at = now
                    state.last_failure_kind = classified["failure_kind"]
                    state.last_http_code = classified["http_code"]
                    state.last_latency_ms = latency_ms
                    if classified["timeout_ambiguous"]:
                        state.rpd_uncertain = int(state.rpd_uncertain or 0) + 1
                    if classified["http_code"] == 429:
                        metric_key = classified["quota_metric"] or "unknown"
                        blocks = dict(state.provider_blocks or {})
                        blocks[metric_key] = {
                            "quota_id": classified["quota_id"],
                            "dimensions": classified["quota_dimensions"],
                            "retry_after_seconds": classified["retry_after_seconds"],
                            "until": (
                                classified["block_until"].isoformat()
                                if classified["block_until"]
                                else ""
                            ),
                        }
                        state.provider_blocks = blocks
                        state.external_usage_suspected = True
                        state.accounting_status = GeminiQuotaState.AccountingStatus.BLOCKED
                    elif not succeeded:
                        state.accounting_status = GeminiQuotaState.AccountingStatus.DEGRADED
                active = GeminiRequestAttempt.objects.filter(
                    project_identity=state.project_identity,
                    model=state.model,
                    fsm_state__in=(
                        GeminiRequestAttempt.FsmState.RESERVED,
                        GeminiRequestAttempt.FsmState.PROVIDER_STARTED,
                    ),
                ).aggregate(next_expiry=Min("permit_expires_at"))
                state.next_permit_expiry_at = active.get("next_expiry")
                state.revision = F("revision") + 1
                state.save()

            graph = GeminiRequest.objects.select_for_update().get(pk=self.graph_id)
            outcomes = dict(graph.candidate_outcomes or {})
            outcome_key = str(boundary.candidate_index or boundary.attempt_index)
            outcomes[outcome_key] = {
                "attempt_index": boundary.attempt_index,
                "outcome": attempt.outcome,
                "failure_kind": attempt.failure_kind,
            }
            graph.candidate_outcomes = outcomes
            if succeeded and graph.winner_attempt_id is None:
                graph.winner_attempt = attempt
                graph.terminal_resolution = "succeeded"
                graph.terminal_reason = "provider_success"
                graph.resolved_at = now
                attempt.winner_claimed = True
                attempt.save(update_fields=["winner_claimed"])
            graph.save(update_fields=[
                "candidate_outcomes", "winner_attempt", "terminal_resolution",
                "terminal_reason", "resolved_at", "updated_at",
            ])

    def resolve_failure(self, reason="exhausted") -> None:
        try:
            from management.models import GeminiRequest

            now = timezone.now()
            GeminiRequest.objects.filter(
                pk=self.graph_id,
                terminal_resolution="",
            ).update(
                terminal_resolution="failed",
                terminal_reason=_safe_reason(reason)[:48] or "exhausted",
                resolved_at=now,
                updated_at=now,
            )
        except Exception:
            return None


def models_Q_effective(now):
    """Kept as a helper so profile selection remains easy to unit-test."""
    from django.db.models import Q

    return Q(effective_until__isnull=True) | Q(effective_until__gt=now)


def _usage_int(usage: dict, *names: str) -> int:
    for name in names:
        try:
            value = int(usage.get(name) or 0)
        except (TypeError, ValueError, OverflowError):
            continue
        if value >= 0:
            return value
    return 0


def classify_failure(error, *, http_code=None, failure_kind="") -> dict:
    """Translate typed gateway failures to bounded V2 fields."""
    detail = str(error or "")
    name = type(error).__name__ if error is not None else ""
    code = int(http_code) if http_code else int(getattr(error, "http_code", 0) or 0) or None
    kind = _safe_reason(failure_kind)
    if not kind:
        lowered = detail.casefold()
        if name == "_Gemini429" or code == 429:
            kind, code = "quota_429", 429
        elif name == "_GeminiModelUnavailable":
            kind = "model_not_found" if "404" in detail else "permission_denied"
            code = 404 if kind == "model_not_found" else 403
        elif name == "_GeminiEmpty":
            kind = "empty"
        elif name == "_GeminiFatal":
            kind = "invalid_key" if "API_KEY_INVALID" in detail.upper() or "HTTP 401" in detail.upper() else "invalid_payload"
        elif name == "_GeminiTransient":
            if lowered.startswith("timeout:"):
                kind = "read_timeout"
            elif lowered.startswith("transport:"):
                kind = "transport"
            elif "невалідний json" in lowered or "invalid json" in lowered:
                kind = "invalid_response"
            elif "http 408" in lowered:
                kind, code = "http_408", 408
            else:
                match = re.search(r"HTTP\s+(5\d\d)", detail, re.I)
                kind = "http_5xx" if match else "transport"
                code = int(match.group(1)) if match else code
        else:
            kind = "provider_error"
    timeout_ambiguous = kind in {"read_timeout", "transport", "http_408"}
    provider_reason = _safe_token(getattr(error, "provider_reason", ""), limit=80)
    quota_metric = _safe_token(getattr(error, "provider_quota_metric", ""), limit=16)
    quota_id = _safe_token(getattr(error, "provider_quota_id", ""), limit=120)
    dimensions = getattr(error, "provider_quota_dimensions", {})
    if not isinstance(dimensions, dict):
        dimensions = {}
    safe_dimensions = {
        _safe_token(key, limit=40): _safe_token(value, limit=80)
        for key, value in list(dimensions.items())[:8]
        if _safe_token(key, limit=40) and _safe_token(value, limit=80)
    }
    retry = max(0, int(getattr(error, "retry_after_seconds", 0) or 0))
    block_until = None
    if code == 429:
        now = timezone.now()
        scope = str(getattr(error, "scope", "") or "")
        if scope in {"day", "unknown"}:
            local = now.astimezone(PT)
            tomorrow = local.date() + dt.timedelta(days=1)
            block_until = dt.datetime.combine(tomorrow, dt.time.min, tzinfo=PT).astimezone(dt.timezone.utc)
        elif retry:
            block_until = now + dt.timedelta(seconds=retry)
    return {
        "failure_kind": kind[:32],
        "http_code": code,
        "provider_reason": provider_reason,
        "quota_metric": quota_metric,
        "quota_id": quota_id,
        "quota_dimensions": safe_dimensions,
        "retry_after_seconds": retry,
        "block_until": block_until,
        "timeout_ambiguous": timeout_ambiguous,
    }


def link_reply_if_present(*, request_id: str, reply_message_id: int) -> bool:
    """Attach a committed reply without creating any row in off mode."""
    if not shadow_runtime_active() or not request_id or not reply_message_id:
        return False
    try:
        from management.models import GeminiRequest, GeminiRequestAttempt

        with transaction.atomic():
            graph = GeminiRequest.objects.select_for_update().filter(
                request_id=str(request_id)[:40]
            ).first()
            if graph is None:
                return False
            graph.reply_message_id = int(reply_message_id)
            graph.save(update_fields=["reply_message_id", "updated_at"])
            GeminiRequestAttempt.objects.filter(
                request_graph=graph,
                winner_claimed=True,
            ).update(reply_message_id=int(reply_message_id))
            return True
    except Exception:
        return False
