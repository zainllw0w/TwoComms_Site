"""Demand-driven, fail-closed Instagram follow-state observation."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import timedelta

from django.db import transaction
from django.utils import timezone


FOLLOWING_TTL = timedelta(days=7)
NOT_FOLLOWING_TTL = timedelta(hours=24)
REFRESH_LEASE = timedelta(minutes=2)
PERMISSION_CIRCUIT = timedelta(hours=24)
RATE_LIMIT_CIRCUIT = timedelta(minutes=15)
MAX_TRIGGER_HISTORY = 8
_PROJECTION_UNSET = object()


@dataclass(frozen=True)
class FollowStateView:
    state: str
    last_known_state: str
    fresh: bool
    stale: bool
    revision: int
    observed_at: object | None
    first_observed_following_at: object | None
    source: str
    last_result: str
    error_kind: str
    next_retry_at: object | None


@dataclass(frozen=True)
class _LookupResult:
    kind: str
    value: bool | None = None
    http_code: int | None = None
    graph_code: int | None = None
    graph_subcode: int | None = None
    error_kind: str = ""
    error_code: str = ""
    field_present: bool = False
    field_type: str = ""


def configuration_fingerprint(settings_obj) -> str:
    """Fingerprint every capability input without storing the provider token."""
    from management.services import instagram_bot

    token = instagram_bot.resolve_instagram_login_token()
    material = "\x00".join(
        (
            instagram_bot.provider_transport(settings_obj),
            str(instagram_bot.GRAPH_VERSION or ""),
            str(instagram_bot._provider_account_id(settings_obj) or ""),
            hashlib.sha256(str(token or "").encode("utf-8")).hexdigest(),
        )
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def effective_follow_state(
    client,
    *,
    now=None,
    settings_obj=None,
    projection=_PROJECTION_UNSET,
) -> FollowStateView:
    """Return policy-effective state while retaining last-known UI evidence."""
    from management.models import IgFollowState, InstagramBotSettings

    now = now or timezone.now()
    settings_obj = settings_obj or InstagramBotSettings.load()
    if projection is _PROJECTION_UNSET:
        # A queryset using ``select_related('follow_state_projection')`` puts
        # the one-to-one row in Django's field cache. Reuse it for manager
        # lists so follow serialization remains one bounded SQL query.
        projection = client._state.fields_cache.get("follow_state_projection", _PROJECTION_UNSET)
        if projection is _PROJECTION_UNSET:
            projection = IgFollowState.objects.filter(client_id=client.pk).first()
    if projection is None:
        return FollowStateView(
            state=IgFollowState.State.UNKNOWN,
            last_known_state=IgFollowState.State.UNKNOWN,
            fresh=False,
            stale=False,
            revision=0,
            observed_at=None,
            first_observed_following_at=None,
            source="",
            last_result=IgFollowState.CheckResult.NEVER,
            error_kind="",
            next_retry_at=None,
        )
    fingerprint_matches = bool(
        projection.config_fingerprint
        and projection.config_fingerprint == configuration_fingerprint(settings_obj)
    )
    fresh = bool(
        projection.last_result == IgFollowState.CheckResult.KNOWN
        and fingerprint_matches
        and projection.observed_at
        and projection.expires_at
        and projection.expires_at > now
        and projection.state
        in {IgFollowState.State.FOLLOWING, IgFollowState.State.NOT_FOLLOWING}
    )
    return FollowStateView(
        state=(projection.state if fresh else IgFollowState.State.UNKNOWN),
        last_known_state=projection.state,
        fresh=fresh,
        stale=bool(projection.observed_at and not fresh),
        revision=int(projection.revision or 0),
        observed_at=projection.observed_at,
        first_observed_following_at=projection.first_observed_following_at,
        source=projection.source,
        last_result=projection.last_result,
        error_kind=projection.last_error_kind,
        # A retry scheduled under a rotated token/configuration must not
        # suppress a fresh demand under the new capability fingerprint.
        next_retry_at=(projection.next_retry_at if fingerprint_matches else None),
    )


def follow_state_payload(
    client,
    *,
    now=None,
    settings_obj=None,
    projection=_PROJECTION_UNSET,
) -> dict:
    """Serialize policy-effective state for manager UI/API consumers.

    The effective ``state`` is intentionally independent from the retained
    last observation: expired, failed, or configuration-stale evidence is
    always exposed as ``unknown`` so the UI cannot imply a negative follow.
    """
    from management.models import IgFollowState

    now = now or timezone.now()
    view = effective_follow_state(
        client,
        now=now,
        settings_obj=settings_obj,
        projection=projection,
    )
    state_labels = {
        IgFollowState.State.FOLLOWING: "Підписаний",
        IgFollowState.State.NOT_FOLLOWING: "Не підписаний",
        IgFollowState.State.UNKNOWN: "Невідомо",
    }
    last_label = state_labels.get(view.last_known_state, state_labels[IgFollowState.State.UNKNOWN])
    if view.fresh:
        label = state_labels.get(view.state, state_labels[IgFollowState.State.UNKNOWN])
        aria_label = f"{label} на @twocomms"
    elif view.stale:
        aria_label = f"Статус підписки застарів; останнє відоме: {last_label.lower()}"
    else:
        aria_label = "Статус підписки невідомий; перевірка ще не виконувалась"
    if view.source:
        aria_label += f"; джерело: {view.source}"
    if view.error_kind:
        aria_label += f"; остання перевірка: {view.error_kind}"
    if view.next_retry_at:
        aria_label += "; повторна перевірка запланована"
    return {
        "state": view.state,
        "last_known_state": view.last_known_state,
        "fresh": view.fresh,
        "stale": view.stale,
        "revision": view.revision,
        "observed_at": view.observed_at.isoformat() if view.observed_at else "",
        "first_observed_following_at": (
            view.first_observed_following_at.isoformat()
            if view.first_observed_following_at
            else ""
        ),
        "source": view.source,
        "last_result": view.last_result,
        "error_kind": view.error_kind,
        "next_retry_at": view.next_retry_at.isoformat() if view.next_retry_at else "",
        "retry_state": "scheduled" if view.next_retry_at else ("error" if view.error_kind else "idle"),
        "state_label": state_labels.get(view.state, state_labels[IgFollowState.State.UNKNOWN]),
        "last_known_state_label": last_label,
        "aria_label": aria_label,
    }


def _bounded_triggers(existing, trigger: str) -> list[str]:
    values = [str(value)[:32] for value in (existing or []) if str(value).strip()]
    trigger = str(trigger or "unknown").strip()[:32] or "unknown"
    if trigger not in values:
        values.append(trigger)
    return values[-MAX_TRIGGER_HISTORY:]


@transaction.atomic
def request_follow_refresh(client, *, trigger, now=None):
    """Coalesce one new demand signal into the client's refresh job."""
    from management.models import (
        IgFollowRefreshJob,
        IgFollowState,
        InstagramBotSettings,
    )

    now = now or timezone.now()
    settings_obj = InstagramBotSettings.load()
    fingerprint = configuration_fingerprint(settings_obj)
    # Every writer follows job -> state lock order.  This prevents a refresh
    # request from deadlocking against provider-result publication on MariaDB.
    job, created = IgFollowRefreshJob.objects.select_for_update().get_or_create(
        client_id=client.pk,
        defaults={
            "requested_generation": 0,
            "triggers": [],
            "expected_config_fingerprint": fingerprint,
            "due_at": now,
        },
    )
    projection, _created = IgFollowState.objects.select_for_update().get_or_create(
        client_id=client.pk
    )
    projection.refresh_generation += 1
    projection.save(update_fields=["refresh_generation", "updated_at"])
    job.requested_generation = projection.refresh_generation
    job.triggers = _bounded_triggers(job.triggers, trigger)
    job.expected_config_fingerprint = fingerprint
    if not created:
        if job.status != IgFollowRefreshJob.Status.PROCESSING:
            job.status = IgFollowRefreshJob.Status.PENDING
            job.due_at = now
            job.next_attempt_at = None
            job.completed_at = None
    job.save(
        update_fields=[
            "requested_generation",
            "triggers",
            "expected_config_fingerprint",
            "status",
            "due_at",
            "next_attempt_at",
            "completed_at",
            "updated_at",
        ]
    )
    return job


def _messaging_consent_exists(client_id: int) -> bool:
    from management.models import InstagramBotMessage

    return InstagramBotMessage.objects.filter(
        client_id=client_id,
        role=InstagramBotMessage.Role.USER,
    ).exists()


def _capability_for_update(*, fingerprint: str, settings_obj, now):
    from management.models import IgFollowCapabilityState
    from management.services import instagram_bot

    capability, _created = (
        IgFollowCapabilityState.objects.select_for_update().get_or_create(
            singleton_key=1
        )
    )
    if capability.config_fingerprint != fingerprint:
        capability.transport = instagram_bot.provider_transport(settings_obj)
        capability.graph_version = instagram_bot.GRAPH_VERSION
        capability.ig_user_id = instagram_bot._provider_account_id(settings_obj)
        capability.config_fingerprint = fingerprint
        capability.status = IgFollowCapabilityState.Status.UNKNOWN
        capability.checked_at = None
        capability.next_probe_at = None
        capability.blocked_until = None
        capability.consecutive_failures = 0
        capability.last_error_kind = ""
        capability.last_error_code = ""
        capability.save()
    return capability


@transaction.atomic
def _claim_job(job_id: int, *, now):
    from management.models import IgFollowRefreshJob, InstagramBotSettings

    settings_obj = InstagramBotSettings.load()
    fingerprint = configuration_fingerprint(settings_obj)
    job = (
        IgFollowRefreshJob.objects.select_for_update()
        .select_related("client")
        .filter(pk=job_id)
        .first()
    )
    if job is None:
        return None, settings_obj, "missing"
    due_at = job.next_attempt_at or job.due_at
    if due_at and due_at > now:
        return None, settings_obj, "not_due"
    if (
        job.status == IgFollowRefreshJob.Status.DONE
        and job.claimed_generation >= job.requested_generation
    ):
        return None, settings_obj, "done"
    if (
        job.status == IgFollowRefreshJob.Status.PROCESSING
        and job.lease_expires_at
        and job.lease_expires_at > now
    ):
        return None, settings_obj, "leased"
    capability = _capability_for_update(
        fingerprint=fingerprint,
        settings_obj=settings_obj,
        now=now,
    )
    if capability.is_probe_blocked(now=now):
        _publish_without_io(
            job,
            result="skipped",
            error_kind="circuit_open",
            error_code=capability.last_error_code,
            now=now,
            due_at=capability.blocked_until or capability.next_probe_at,
        )
        return None, settings_obj, "circuit_open"
    token = uuid.uuid4().hex
    job.status = IgFollowRefreshJob.Status.PROCESSING
    job.claimed_generation = job.requested_generation
    job.expected_config_fingerprint = fingerprint
    job.attempts += 1
    job.lease_token = token
    job.lease_expires_at = now + REFRESH_LEASE
    job.last_error_kind = ""
    job.last_error_code = ""
    job.save(
        update_fields=[
            "status",
            "claimed_generation",
            "expected_config_fingerprint",
            "attempts",
            "lease_token",
            "lease_expires_at",
            "last_error_kind",
            "last_error_code",
            "updated_at",
        ]
    )
    return job, settings_obj, token


def _retry_delay(failures: int) -> timedelta:
    minutes = min(360, 5 * (2 ** max(0, min(int(failures or 1) - 1, 7))))
    return timedelta(minutes=minutes)


def _publish_without_io(
    job,
    *,
    result: str,
    error_kind: str,
    error_code: str,
    now,
    due_at=None,
    revalidate_claim=False,
):
    """Publish a pre-provider skip while the caller already owns row locks."""
    from management.models import (
        IgFollowObservation,
        IgFollowRefreshJob,
        IgFollowState,
        InstagramBotSettings,
    )

    if revalidate_claim:
        current_fingerprint = configuration_fingerprint(InstagramBotSettings.load())
        if (
            job.claimed_generation != job.requested_generation
            or job.expected_config_fingerprint != current_fingerprint
            or not job.lease_expires_at
            or job.lease_expires_at <= now
        ):
            job.status = IgFollowRefreshJob.Status.PENDING
            job.lease_token = ""
            job.lease_expires_at = None
            job.due_at = now
            job.next_attempt_at = None
            job.completed_at = None
            job.save(
                update_fields=[
                    "status",
                    "lease_token",
                    "lease_expires_at",
                    "due_at",
                    "next_attempt_at",
                    "completed_at",
                    "updated_at",
                ]
            )
            return False

    projection = IgFollowState.objects.select_for_update().get(client_id=job.client_id)
    projection.last_check_at = now
    projection.last_result = (
        IgFollowState.CheckResult.SKIPPED
        if result == "skipped"
        else IgFollowState.CheckResult.ERROR
    )
    projection.last_error_kind = error_kind[:32]
    projection.last_error_code = error_code[:64]
    if result == "error":
        projection.consecutive_failures += 1
        projection.next_retry_at = due_at or now + _retry_delay(
            projection.consecutive_failures
        )
    else:
        projection.next_retry_at = due_at
    projection.save(
        update_fields=[
            "last_check_at",
            "last_result",
            "last_error_kind",
            "last_error_code",
            "consecutive_failures",
            "next_retry_at",
            "updated_at",
        ]
    )
    IgFollowObservation.objects.create(
        client_id=job.client_id,
        revision=projection.revision,
        trigger=str((job.triggers or ["unknown"])[-1])[:32],
        result=(
            IgFollowObservation.Result.SKIPPED
            if result == "skipped"
            else IgFollowObservation.Result.ERROR
        ),
        config_fingerprint=job.expected_config_fingerprint,
        error_kind=error_kind[:32],
        error_code=error_code[:64],
    )
    job.status = (
        IgFollowRefreshJob.Status.DONE
        if result == "skipped"
        else IgFollowRefreshJob.Status.FAILED
    )
    job.lease_token = ""
    job.lease_expires_at = None
    job.last_error_kind = error_kind[:32]
    job.last_error_code = error_code[:64]
    job.next_attempt_at = due_at
    job.completed_at = now if result == "skipped" else None
    job.save(
        update_fields=[
            "status",
            "lease_token",
            "lease_expires_at",
            "last_error_kind",
            "last_error_code",
            "next_attempt_at",
            "completed_at",
            "updated_at",
        ]
    )
    return True


def _classify_http_error(code: int, body: str) -> _LookupResult:
    from management.services import instagram_bot

    graph_code, graph_subcode = instagram_bot._graph_error_codes(body)
    safe_graph_code = _safe_graph_code(graph_code)
    safe_graph_subcode = _safe_graph_code(graph_subcode)
    if code in {401, 403} or safe_graph_code in {10, 190, 200}:
        kind = "permission"
    elif code == 429 or safe_graph_code in instagram_bot.RATE_LIMIT_CODES:
        kind = "rate_limit"
    elif code == -1:
        kind = "transport"
    elif code >= 500:
        kind = "provider"
    else:
        kind = "http"
    safe_code = str(safe_graph_subcode or safe_graph_code or code or "")[:64]
    return _LookupResult(
        kind="error",
        http_code=code if code >= 0 else None,
        graph_code=safe_graph_code,
        graph_subcode=safe_graph_subcode,
        error_kind=kind,
        error_code=safe_code,
    )


def _safe_graph_code(value):
    """Keep untrusted provider codes within unsigned DB field bounds."""
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        return None
    if normalized < 0 or normalized > 2_147_483_647:
        return None
    return normalized


def _parse_known_response(client_igsid: str, code: int, body: str) -> _LookupResult:
    if code != 200:
        return _classify_http_error(code, body)
    try:
        payload = json.loads(body)
    except Exception:
        return _LookupResult(kind="error", http_code=200, error_kind="malformed_json")
    if not isinstance(payload, dict):
        return _LookupResult(kind="error", http_code=200, error_kind="malformed_json")
    returned_id = payload.get("id")
    if returned_id is not None and str(returned_id) != str(client_igsid):
        return _LookupResult(kind="error", http_code=200, error_kind="identity_mismatch")
    present = "is_user_follow_business" in payload
    value = payload.get("is_user_follow_business")
    field_type = type(value).__name__ if present else "missing"
    if not present:
        return _LookupResult(
            kind="error",
            http_code=200,
            error_kind="missing_field",
            field_present=False,
            field_type=field_type,
        )
    if type(value) is not bool:
        return _LookupResult(
            kind="error",
            http_code=200,
            error_kind="invalid_field_type",
            field_present=True,
            field_type=field_type,
        )
    return _LookupResult(
        kind="known",
        value=value,
        http_code=200,
        field_present=True,
        field_type="bool",
    )


def _update_capability(*, result: _LookupResult, fingerprint: str, settings_obj, now):
    from management.models import IgFollowCapabilityState

    with transaction.atomic():
        capability = _capability_for_update(
            fingerprint=fingerprint,
            settings_obj=settings_obj,
            now=now,
        )
        capability.checked_at = now
        circuit_open = capability.is_probe_blocked(now=now)
        if result.kind == "known":
            if not circuit_open:
                capability.status = IgFollowCapabilityState.Status.AVAILABLE
                capability.next_probe_at = None
                capability.blocked_until = None
                capability.consecutive_failures = 0
                capability.last_error_kind = ""
                capability.last_error_code = ""
        elif result.error_kind in {
            "permission",
            "missing_account",
            "missing_token",
        }:
            capability.status = IgFollowCapabilityState.Status.BLOCKED
            capability.consecutive_failures += 1
            capability.blocked_until = now + PERMISSION_CIRCUIT
            capability.next_probe_at = capability.blocked_until
            capability.last_error_kind = result.error_kind
            capability.last_error_code = result.error_code
        elif result.error_kind == "rate_limit":
            capability.status = IgFollowCapabilityState.Status.DEGRADED
            capability.consecutive_failures += 1
            capability.next_probe_at = now + RATE_LIMIT_CIRCUIT
            capability.blocked_until = None
            capability.last_error_kind = result.error_kind
            capability.last_error_code = result.error_code
        capability.save()


def _publish_lookup(job_id: int, token: str, result: _LookupResult, *, now) -> str:
    from management.models import (
        IgFollowObservation,
        IgFollowRefreshJob,
        IgFollowState,
        InstagramBotSettings,
    )
    from management.services import instagram_bot

    with transaction.atomic():
        job = (
            IgFollowRefreshJob.objects.select_for_update()
            .select_related("client")
            .filter(pk=job_id)
            .first()
        )
        if job is None or job.lease_token != token:
            return "lease_lost"
        if not job.lease_expires_at or job.lease_expires_at <= now:
            job.status = IgFollowRefreshJob.Status.PENDING
            job.lease_token = ""
            job.lease_expires_at = None
            job.due_at = now
            job.next_attempt_at = None
            job.completed_at = None
            job.save(
                update_fields=[
                    "status",
                    "lease_token",
                    "lease_expires_at",
                    "due_at",
                    "next_attempt_at",
                    "completed_at",
                    "updated_at",
                ]
            )
            return "lease_lost"
        current_fingerprint = configuration_fingerprint(InstagramBotSettings.load())
        if (
            job.claimed_generation != job.requested_generation
            or job.expected_config_fingerprint != current_fingerprint
        ):
            job.status = IgFollowRefreshJob.Status.PENDING
            job.lease_token = ""
            job.lease_expires_at = None
            job.due_at = now
            job.next_attempt_at = None
            job.save(
                update_fields=[
                    "status",
                    "lease_token",
                    "lease_expires_at",
                    "due_at",
                    "next_attempt_at",
                    "updated_at",
                ]
            )
            return "superseded"
        _update_capability(
            result=result,
            fingerprint=current_fingerprint,
            settings_obj=InstagramBotSettings.load(),
            now=now,
        )
        projection = IgFollowState.objects.select_for_update().get(
            client_id=job.client_id
        )
        observation_result = IgFollowObservation.Result.ERROR
        if result.kind == "known":
            projection.revision += 1
            projection.state = (
                IgFollowState.State.FOLLOWING
                if result.value
                else IgFollowState.State.NOT_FOLLOWING
            )
            projection.source = instagram_bot.INSTAGRAM_LOGIN_TRANSPORT
            projection.graph_version = instagram_bot.GRAPH_VERSION
            projection.config_fingerprint = current_fingerprint
            projection.observed_at = now
            projection.expires_at = now + (
                FOLLOWING_TTL if result.value else NOT_FOLLOWING_TTL
            )
            if result.value and projection.first_observed_following_at is None:
                projection.first_observed_following_at = now
            projection.last_result = IgFollowState.CheckResult.KNOWN
            projection.consecutive_failures = 0
            projection.last_error_kind = ""
            projection.last_error_code = ""
            projection.next_retry_at = None
            observation_result = IgFollowObservation.Result.KNOWN
            job.status = IgFollowRefreshJob.Status.DONE
            job.completed_at = now
            return_value = "known"
        else:
            # Bind the retry budget to the configuration that produced the
            # error, while keeping the last state value for manager display.
            projection.config_fingerprint = current_fingerprint
            projection.source = instagram_bot.INSTAGRAM_LOGIN_TRANSPORT
            projection.graph_version = instagram_bot.GRAPH_VERSION
            projection.last_result = IgFollowState.CheckResult.ERROR
            projection.consecutive_failures += 1
            projection.last_error_kind = result.error_kind[:32]
            projection.last_error_code = result.error_code[:64]
            projection.next_retry_at = now + _retry_delay(
                projection.consecutive_failures
            )
            job.status = IgFollowRefreshJob.Status.FAILED
            job.next_attempt_at = projection.next_retry_at
            job.last_error_kind = result.error_kind[:32]
            job.last_error_code = result.error_code[:64]
            return_value = "error"
        projection.last_check_at = now
        projection.refresh_lease_token = ""
        projection.refresh_lease_expires_at = None
        projection.save()
        IgFollowObservation.objects.create(
            client_id=job.client_id,
            revision=projection.revision,
            trigger=str((job.triggers or ["unknown"])[-1])[:32],
            result=observation_result,
            observed_value=result.value if result.kind == "known" else None,
            field_present=result.field_present,
            field_type=result.field_type,
            transport=instagram_bot.provider_transport(InstagramBotSettings.load()),
            graph_version=instagram_bot.GRAPH_VERSION,
            config_fingerprint=current_fingerprint,
            http_code=result.http_code,
            graph_code=result.graph_code,
            graph_subcode=result.graph_subcode,
            error_kind=result.error_kind[:32],
            error_code=result.error_code[:64],
        )
        job.lease_token = ""
        job.lease_expires_at = None
        job.save()
        return return_value


def run_follow_refresh_job(job_id: int, *, now=None) -> str:
    """Claim, fetch, and publish one follow-state job without holding DB locks."""
    from management.models import IgFollowRefreshJob
    from management.services import instagram_bot

    supplied_now = now is not None
    now = now or timezone.now()
    job, settings_obj, claim = _claim_job(job_id, now=now)
    if job is None:
        return claim
    if not _messaging_consent_exists(job.client_id):
        with transaction.atomic():
            owned = IgFollowRefreshJob.objects.select_for_update().get(pk=job.pk)
            if owned.lease_token != claim:
                return "lease_lost"
            published = _publish_without_io(
                owned,
                result="skipped",
                error_kind="missing_messaging_consent",
                error_code="",
                now=now if supplied_now else timezone.now(),
                revalidate_claim=True,
            )
            if not published:
                return "superseded"
        return "skipped"
    if instagram_bot.provider_transport(settings_obj) != instagram_bot.INSTAGRAM_LOGIN_TRANSPORT:
        with transaction.atomic():
            owned = IgFollowRefreshJob.objects.select_for_update().get(pk=job.pk)
            if owned.lease_token != claim:
                return "lease_lost"
            published = _publish_without_io(
                owned,
                result="skipped",
                error_kind="unsupported_transport",
                error_code="",
                now=now if supplied_now else timezone.now(),
                revalidate_claim=True,
            )
            if not published:
                return "superseded"
        return "skipped"
    try:
        if not instagram_bot._provider_account_id(settings_obj):
            result = _LookupResult(kind="error", error_kind="missing_account")
        else:
            token = instagram_bot.get_page_token(settings_obj)
            if not token:
                result = _LookupResult(kind="error", error_kind="missing_token")
            else:
                url = instagram_bot._provider_url(
                    settings_obj,
                    f"/{job.client.igsid}",
                    {"fields": "is_user_follow_business"},
                )
                try:
                    code, body = instagram_bot._provider_http(
                        settings_obj,
                        url,
                        token=token,
                        timeout=instagram_bot.HTTP_TIMEOUT,
                    )
                    result = _parse_known_response(job.client.igsid, int(code), str(body))
                except Exception as exc:
                    result = _LookupResult(
                        kind="error",
                        error_kind="transport",
                        error_code=type(exc).__name__[:64],
                    )
    except Exception as exc:
        result = _LookupResult(
            kind="error",
            error_kind="provider_setup",
            error_code=type(exc).__name__[:64],
        )
    return _publish_lookup(
        job.pk,
        claim,
        result,
        now=now if supplied_now else timezone.now(),
    )


def refresh_follow_state_if_due(client, *, trigger, now=None) -> str:
    now = now or timezone.now()
    view = effective_follow_state(client, now=now)
    if view.fresh:
        return "fresh"
    if view.next_retry_at and view.next_retry_at > now:
        return "backoff"
    job = request_follow_refresh(client, trigger=trigger, now=now)
    return run_follow_refresh_job(job.pk, now=now)


__all__ = [
    "FollowStateView",
    "configuration_fingerprint",
    "effective_follow_state",
    "follow_state_payload",
    "request_follow_refresh",
    "run_follow_refresh_job",
    "refresh_follow_state_if_due",
]
