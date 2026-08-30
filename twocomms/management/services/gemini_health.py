"""Bounded, redacted Gemini API health evidence for the management UI."""

from __future__ import annotations

import datetime as dt
import re
from collections import defaultdict
from typing import Any

from django.utils import timezone

from management.models import GeminiRequestAttempt
from management.services import gemini_keys


SCHEMA_VERSION = 4
WINDOW_HOURS = 24
BUCKET_COUNT = 24
ATTEMPT_QUERY_CAP = 2000
METADATA_ATTEMPT_QUERY_CAP = 512
FRESH_EVIDENCE_SECONDS = 7500
DISPLAY_MODELS = (
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
)
MODELS = DISPLAY_MODELS
OTHER_GENERATION_MODELS = ("gemini-3.5-flash", "gemini-3.5-flash-lite")
GENERATION_MODELS = tuple(dict.fromkeys(DISPLAY_MODELS + OTHER_GENERATION_MODELS))
METADATA_ROLES = frozenset(("health_metadata", "health_probe"))
KEY_ALIASES = (
    "GEMINI_API",
    "GEMINI_API2",
    "GEMINI_API3",
    "GEMINI_API4",
    "GEMINI_API5",
    "GEMINI_API6",
)
SLOT_IDS = (
    "gslot_7f3a", "gslot_c921", "gslot_18de",
    "gslot_a604", "gslot_52bb", "gslot_e17c",
)
SLOT_BY_ALIAS = dict(zip(KEY_ALIASES, SLOT_IDS, strict=True))
ALIAS_BY_SLOT = dict(zip(SLOT_IDS, KEY_ALIASES, strict=True))
DISPLAY_ALIASES = {
    key_name: f"API key {index}"
    for index, key_name in enumerate(KEY_ALIASES, start=1)
}
_METADATA_BATCH_RE = re.compile(r"^(meta-\d{10}-[0-9a-f]{8})-(?:I|[2-6])$")

_SUCCESS_OUTCOMES = frozenset(("success", "succeeded", "ok"))
_FAILURE_REASON_LABELS = {
    "read_timeout": "3.7 timed out",
    "timeout": "3.7 timed out",
    "http_408": "3.7 timed out",
    "http_5xx": "provider overload",
    "transport": "network transport failure",
    "overload": "provider overload",
    "provider_overload": "provider overload",
    "quota_429": "quota cooldown",
    "model_not_found": "model unavailable",
    "permission_denied": "model unavailable",
    "invalid_key": "invalid key",
    "invalid_payload": "invalid response",
    "empty": "invalid response",
    "lease_busy": "key busy/quarantined",
    "quarantined": "key busy/quarantined",
}


def _as_utc(value: dt.datetime) -> dt.datetime:
    if timezone.is_naive(value):
        return timezone.make_aware(value, dt.timezone.utc)
    return value.astimezone(dt.timezone.utc)


def _iso(value: dt.datetime | None) -> str | None:
    return _as_utc(value).isoformat() if value else None


def _attempt_succeeded(row: dict[str, Any]) -> bool:
    return str(row.get("outcome") or "").strip().lower() in _SUCCESS_OUTCOMES


def _attempt_not_needed(row: dict[str, Any]) -> bool:
    return (
        str(row.get("outcome") or "").strip().lower()
        in {"skipped", "not_needed", "not_attempted"}
        or str(row.get("failure_kind") or "").strip().lower() == "not_needed"
    )


def _bucket_index(created_at: dt.datetime, window_start: dt.datetime) -> int:
    seconds = (_as_utc(created_at) - window_start).total_seconds()
    return min(BUCKET_COUNT - 1, max(0, int(seconds // 3600)))


def _attempt_sort_key(row: dict[str, Any]) -> tuple[dt.datetime, int]:
    return (_as_utc(row["created_at"]), int(row.get("id") or 0))


def _status_for_attempts(
    rows: list[dict[str, Any]],
    *,
    window_start: dt.datetime | None = None,
) -> str:
    meaningful_rows = [row for row in rows if not _attempt_not_needed(row)]
    if not meaningful_rows:
        return "not_needed" if rows else "no_observation"
    if not rows:
        return "no_observation"

    ordered = sorted(meaningful_rows, key=_attempt_sort_key)
    latest = ordered[-1]
    if not _attempt_succeeded(latest):
        return "terminal"
    latest_request = str(latest.get("request_id") or "").strip()
    if window_start is None:
        latest_bucket = _as_utc(latest["created_at"]).replace(
            minute=0,
            second=0,
            microsecond=0,
        )
    else:
        latest_bucket = _bucket_index(latest["created_at"], window_start)
    for previous in ordered[:-1]:
        if _attempt_succeeded(previous):
            continue
        previous_request = str(previous.get("request_id") or "").strip()
        same_request = bool(latest_request) and previous_request == latest_request
        if window_start is None:
            previous_bucket = _as_utc(previous["created_at"]).replace(
                minute=0,
                second=0,
                microsecond=0,
            )
        else:
            previous_bucket = _bucket_index(previous["created_at"], window_start)
        if same_request or previous_bucket == latest_bucket:
            return "recovered"
    return "success"


def _empty_model_snapshot(window_start: dt.datetime) -> dict[str, Any]:
    return {
        "status": "no_observation",
        "observations": 0,
        "successes": 0,
        "failures": 0,
        "skipped": 0,
        "recovered": 0,
        "last_observation_at": None,
        "last_latency_ms": 0,
        "history": [
            {
                "bucket_start": _iso(window_start + dt.timedelta(hours=index)),
                "status": "no_observation",
            }
            for index in range(BUCKET_COUNT)
        ],
    }


def _has_ordered_recovery(rows: list[dict[str, Any]]) -> bool:
    """Return whether a failure is followed by a success in one request."""
    saw_failure = False
    for row in sorted(rows, key=_attempt_sort_key):
        if _attempt_not_needed(row):
            continue
        if _attempt_succeeded(row):
            if saw_failure:
                return True
        else:
            saw_failure = True
    return False


def _ordered_recovery_row_ids(rows: list[dict[str, Any]]) -> tuple[set[int], set[int]]:
    """Return in-memory identities participating in ordered same-request recovery."""
    recovered_failures: set[int] = set()
    recovered_successes: set[int] = set()
    for request_rows in _group_by_request(rows).values():
        pending_failures: list[dict[str, Any]] = []
        for row in request_rows:
            if _attempt_not_needed(row):
                continue
            if _attempt_succeeded(row):
                if pending_failures:
                    recovered_failures.update(id(item) for item in pending_failures)
                    recovered_successes.add(id(row))
                pending_failures = []
            else:
                pending_failures.append(row)
    return recovered_failures, recovered_successes


def _history_statuses(
    rows: list[dict[str, Any]],
    window_start: dt.datetime,
) -> list[dict[str, str | None]]:
    """Build bucket statuses while retaining recovery evidence across buckets."""
    ordered = sorted(rows, key=_attempt_sort_key)
    by_bucket: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in ordered:
        by_bucket[_bucket_index(row["created_at"], window_start)].append(row)

    recovered_failures, recovered_successes = _ordered_recovery_row_ids(ordered)
    history: list[dict[str, str | None]] = []
    for index in range(BUCKET_COUNT):
        bucket_rows = by_bucket.get(index, [])
        status = _status_for_attempts(bucket_rows, window_start=window_start)
        if bucket_rows:
            meaningful_bucket_rows = [
                row for row in bucket_rows if not _attempt_not_needed(row)
            ]
            if not meaningful_bucket_rows:
                history.append({
                    "bucket_start": _iso(window_start + dt.timedelta(hours=index)),
                    "status": "not_needed",
                })
                continue
            latest = max(meaningful_bucket_rows, key=_attempt_sort_key)
            latest_is_unrecovered_failure = (
                not _attempt_succeeded(latest)
                and id(latest) not in recovered_failures
            )
            if not latest_is_unrecovered_failure and any(
                id(row) in recovered_failures or id(row) in recovered_successes
                for row in bucket_rows
            ):
                status = "recovered"
        history.append({
            "bucket_start": _iso(window_start + dt.timedelta(hours=index)),
            "status": status,
        })
    return history


def _model_snapshot(rows: list[dict[str, Any]], window_start: dt.datetime) -> dict[str, Any]:
    snapshot = _empty_model_snapshot(window_start)
    if not rows:
        return snapshot

    rows = sorted(rows, key=_attempt_sort_key)
    history = _history_statuses(rows, window_start)

    meaningful_rows = [row for row in rows if not _attempt_not_needed(row)]
    success_count = sum(1 for row in meaningful_rows if _attempt_succeeded(row))
    failure_count = len(meaningful_rows) - success_count
    skipped_count = len(rows) - len(meaningful_rows)
    recovered_count = sum(
        1
        for request_rows in _group_by_request(rows).values()
        if _has_ordered_recovery(request_rows)
    )
    last = rows[-1]
    snapshot.update({
        "status": _status_for_attempts(rows, window_start=window_start),
        "observations": len(rows),
        "successes": success_count,
        "failures": failure_count,
        "skipped": skipped_count,
        "recovered": recovered_count,
        "last_observation_at": _iso(last["created_at"]),
        "last_latency_ms": max(0, int(last.get("latency_ms") or 0)),
        "history": history,
    })
    return snapshot


def _group_by_request(rows: list[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if str(row.get("key_name") or "") not in KEY_ALIASES:
            continue
        request_id = str(row.get("request_id") or "").strip()
        if not request_id:
            continue
        grouped[(str(row.get("key_name") or ""), request_id)].append(row)
    for request_rows in grouped.values():
        request_rows.sort(
            key=lambda row: (
                _as_utc(row["created_at"]),
                int(row.get("id") or 0),
            )
        )
    return grouped


def _group_global_request(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        request_id = str(row.get("request_id") or "").strip()
        if request_id and str(row.get("key_name") or "") in KEY_ALIASES:
            grouped[request_id].append(row)
    for request_rows in grouped.values():
        request_rows.sort(key=lambda row: (
            int(row.get("candidate_index") or 0) or 65535,
            *_attempt_sort_key(row),
        ))
    return grouped


def _latest_fallback(rows: list[dict[str, Any]]) -> dict[str, str | int | None] | None:
    latest: tuple[tuple[dt.datetime, int], dict[str, str | int | None]] | None = None
    for request_rows in _group_global_request(rows).values():
        for index, row in enumerate(request_rows):
            if _attempt_succeeded(row) or _attempt_not_needed(row):
                continue
            for next_row in request_rows[index + 1:]:
                if not _attempt_succeeded(next_row):
                    continue
                if next_row.get("model") == row.get("model"):
                    continue
                failure_kind = str(row.get("failure_kind") or "").strip().lower()
                fallback = {
                    "from_model": str(row.get("model") or ""),
                    "to_model": str(next_row.get("model") or ""),
                    "reason": _FAILURE_REASON_LABELS.get(failure_kind, "provider request failed"),
                    "http_code": int(row.get("http_code") or 0) or None,
                    "observed_at": _iso(next_row["created_at"]),
                }
                observed_at = _attempt_sort_key(next_row)
                if latest is None or observed_at > latest[0]:
                    latest = (observed_at, fallback)
                break
    return latest[1] if latest else None


def _latest_route(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    groups = _group_global_request(rows)
    if not groups:
        return None
    request_id, request_rows = max(
        groups.items(),
        key=lambda item: _attempt_sort_key(max(item[1], key=_attempt_sort_key)),
    )
    return {
        "request_id": request_id,
        "steps": [
            {
                "slot_id": SLOT_BY_ALIAS[str(row.get("key_name") or "")],
                "model": str(row.get("model") or ""),
                "outcome": str(row.get("outcome") or ""),
                "failure_kind": str(row.get("failure_kind") or ""),
                "not_attempted_reason": str(row.get("not_attempted_reason") or ""),
                "candidate_index": int(row.get("candidate_index") or 0),
            }
            for row in request_rows
        ],
    }


def _latest_request_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return the rows belonging to the most recently observed request."""
    if not rows:
        return []
    latest = max(rows, key=_attempt_sort_key)
    request_id = str(latest.get("request_id") or "").strip()
    if not request_id:
        return [latest]
    return sorted(
        [row for row in rows if str(row.get("request_id") or "").strip() == request_id],
        key=_attempt_sort_key,
    )


def _metadata_batch_key(row: dict[str, Any]) -> str:
    """Group the six alias request IDs emitted by one hourly run."""
    request_id = str(row.get("request_id") or "").strip()
    match = _METADATA_BATCH_RE.fullmatch(request_id)
    return match.group(1) if match else request_id


def _latest_metadata_batch(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Return redacted completeness evidence for the newest metadata batch."""
    if not rows:
        return None
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[_metadata_batch_key(row)].append(row)
    batch_rows = max(
        groups.values(),
        key=lambda batch: _attempt_sort_key(max(batch, key=_attempt_sort_key)),
    )
    aliases = {
        str(row.get("key_name") or "")
        for row in batch_rows
        if str(row.get("key_name") or "") in KEY_ALIASES
    }
    completed_at = max(batch_rows, key=_attempt_sort_key)["created_at"]
    expected_aliases = len(KEY_ALIASES)
    return {
        "checked_aliases": len(aliases),
        "expected_aliases": expected_aliases,
        "complete": len(aliases) == expected_aliases,
        "completed_at": _iso(completed_at),
    }


def _fresh(rows: list[dict[str, Any]], generated_at: dt.datetime) -> bool:
    if not rows:
        return False
    latest = max(rows, key=_attempt_sort_key)
    age = (generated_at - _as_utc(latest["created_at"])).total_seconds()
    return 0 <= age <= FRESH_EVIDENCE_SECONDS


def _runtime_live_state(
    rows: list[dict[str, Any]], generated_at: dt.datetime,
) -> tuple[str, str | None] | None:
    """Classify fresh real generation evidence without metadata inference."""
    request_rows = [row for row in _latest_request_rows(rows) if not _attempt_not_needed(row)]
    if not _fresh(request_rows, generated_at):
        return None
    latest = request_rows[-1]
    if _attempt_succeeded(latest):
        model = str(latest.get("model") or "")
        if model == DISPLAY_MODELS[1]:
            primary_failed = any(
                row.get("model") == DISPLAY_MODELS[0]
                and not _attempt_succeeded(row)
                and not _attempt_not_needed(row)
                for row in request_rows[:-1]
            )
            if primary_failed:
                return "DEGRADED", model
        return "LIVE", model if model in GENERATION_MODELS else None
    return "OFFLINE", None


def _metadata_live_state(
    rows: list[dict[str, Any]], generated_at: dt.datetime,
) -> tuple[str, str | None] | None:
    """Classify one fresh, explicitly requested metadata observation."""
    request_rows = _latest_request_rows(rows)
    if not _fresh(request_rows, generated_at):
        return None
    by_model = {
        str(row.get("model") or ""): row
        for row in request_rows
        if str(row.get("model") or "") in DISPLAY_MODELS
    }
    primary = by_model.get(DISPLAY_MODELS[0])
    secondary = by_model.get(DISPLAY_MODELS[1])
    if primary and _attempt_succeeded(primary):
        return "READY", DISPLAY_MODELS[0]
    if primary and not _attempt_succeeded(primary):
        if secondary and _attempt_succeeded(secondary):
            return "DEGRADED", DISPLAY_MODELS[1]
        if secondary and not _attempt_not_needed(secondary):
            return "OFFLINE", None
        return None
    return None


def _pool_row_by_key(pool_rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("key_name") or ""): row
        for row in pool_rows
        if str(row.get("key_name") or "") in KEY_ALIASES
    }


def _summary(
    pool_rows: list[dict[str, Any]],
    attempts: list[dict[str, Any]],
    *,
    window_start: dt.datetime | None = None,
) -> dict[str, Any]:
    state_counts = {state: 0 for state in ("available", "busy", "cooldown", "unconfigured")}
    for row in pool_rows:
        state = str(
            row.get("health_state")
            or row.get("current_status")
            or row.get("state")
            or "unconfigured"
        )
        if state in state_counts:
            state_counts[state] += 1

    models = {}
    for model in DISPLAY_MODELS:
        model_rows = [row for row in attempts if row.get("model") == model]
        if not model_rows:
            models[model] = {
                "status": "insufficient_observations",
                "observations": 0,
                "successes": 0,
                "failures": 0,
                "skipped": 0,
                "last_observation_at": None,
            }
            continue
        meaningful_rows = [row for row in model_rows if not _attempt_not_needed(row)]
        successes = sum(1 for row in meaningful_rows if _attempt_succeeded(row))
        models[model] = {
            "status": _status_for_attempts(model_rows, window_start=window_start),
            "observations": len(model_rows),
            "successes": successes,
            "failures": len(meaningful_rows) - successes,
            "skipped": len(model_rows) - len(meaningful_rows),
            "last_observation_at": _iso(
                max(model_rows, key=_attempt_sort_key)["created_at"]
            ),
        }

    return {
        **state_counts,
        "configured": sum(1 for row in pool_rows if row.get("present")),
        "observations": len(attempts),
        "models": models,
    }


def build_snapshot(*, now: dt.datetime | None = None) -> dict[str, Any]:
    """Return a deterministic, bounded, JSON-safe API health snapshot.

    The history is derived exclusively from redacted ``GeminiRequestAttempt``
    rows in the last 24 hours. ``pool_status`` supplies the live six-alias
    state; no provider call is made here.
    """
    generated_at = _as_utc(now or timezone.now())
    window_start = generated_at - dt.timedelta(hours=WINDOW_HOURS)
    query = GeminiRequestAttempt.objects.filter(
        created_at__gte=window_start,
        created_at__lte=generated_at,
        key_name__in=KEY_ALIASES,
        model__in=GENERATION_MODELS,
    )
    fields = (
        "id",
        "request_id",
        "key_name",
        "model",
        "outcome",
        "failure_kind",
        "http_code",
        "role",
        "latency_ms",
        "not_attempted_reason",
        "candidate_index",
        "created_at",
    )
    runtime_rows = list(
        query.exclude(role__in=METADATA_ROLES)
        .order_by("-created_at", "-id")
        .values(*fields)[:ATTEMPT_QUERY_CAP]
    )
    metadata_rows = list(
        query.filter(role__in=METADATA_ROLES)
        .order_by("-created_at", "-id")
        .values(*fields)[:METADATA_ATTEMPT_QUERY_CAP]
    )
    attempt_rows = runtime_rows + metadata_rows
    # Newest rows are selected under the cap, then restored to chronological
    # order so fallback and retry classification are deterministic.
    attempt_rows.sort(key=lambda row: (_as_utc(row["created_at"]), int(row.get("id") or 0)))

    pool_rows = list(gemini_keys.pool_status(now=generated_at, read_only=True))
    runtime_attempts = [
        row for row in attempt_rows if row.get("role") not in METADATA_ROLES
    ]
    metadata_attempts = [
        row for row in attempt_rows if row.get("role") in METADATA_ROLES
    ]
    pool_by_key = _pool_row_by_key(pool_rows)
    keys = []
    for key_name in KEY_ALIASES:
        pool_row = pool_by_key.get(key_name, {})
        row_attempts = [row for row in attempt_rows if row.get("key_name") == key_name]
        metadata_rows = [row for row in row_attempts if row.get("role") in METADATA_ROLES]
        runtime_rows = [row for row in row_attempts if row.get("role") not in METADATA_ROLES]
        latest_metadata = max(metadata_rows, key=_attempt_sort_key, default=None)
        latest_runtime = max(runtime_rows, key=_attempt_sort_key, default=None)
        latest_evidence = max(
            [row for row in (latest_metadata, latest_runtime) if row is not None],
            key=_attempt_sort_key,
            default=None,
        )
        evidence_source = "none"
        if not pool_row.get("present"):
            live_state, active_model = "NOT_CONFIGURED", None
        else:
            classified = _runtime_live_state(runtime_rows, generated_at)
            evidence_source = "generation" if classified else ""
            if classified is None:
                classified = _metadata_live_state(metadata_rows, generated_at)
                evidence_source = "manual_metadata" if classified else "none"
            live_state, active_model = classified or ("STALE", None)
        if not pool_row.get("present"):
            evidence_source = "none"
        keys.append({
            "slot_id": SLOT_BY_ALIAS[key_name],
            "display_label": DISPLAY_ALIASES[key_name],
            "alias": DISPLAY_ALIASES[key_name],
            "state": str(
                pool_row.get("health_state")
                or pool_row.get("current_status")
                or pool_row.get("state")
                or "unconfigured"
            ),
            "configured": bool(pool_row.get("present")),
            "available": bool(pool_row.get("available")),
            "role": str(pool_row.get("role") or ""),
            "project_identity_known": bool(pool_row.get("project_identity_known")),
            "live_state": live_state,
            "active_model": active_model,
            "source": evidence_source,
            "evidence_kind": "generation" if evidence_source == "generation" else ("metadata_only" if evidence_source == "manual_metadata" else "none"),
            "checked_at": _iso(latest_evidence["created_at"]) if latest_evidence else None,
            "last_check_at": _iso(latest_metadata["created_at"]) if latest_metadata else None,
            "last_generation_at": _iso(latest_runtime["created_at"]) if latest_runtime else None,
            "freshness": "fresh" if evidence_source != "none" else "stale",
            "generation_quota_proven": (
                evidence_source == "generation"
                and live_state in {"LIVE", "DEGRADED"}
            ),
            "generation_models": {model: _model_snapshot([row for row in runtime_rows if row.get("model") == model], window_start) for model in DISPLAY_MODELS},
            "metadata_models": {model: _model_snapshot([row for row in metadata_rows if row.get("model") == model], window_start) for model in DISPLAY_MODELS},
            "models": {model: _model_snapshot([row for row in runtime_rows if row.get("model") == model], window_start) for model in DISPLAY_MODELS},
            "other_model_usage": {
                model: _model_snapshot(
                    [row for row in runtime_rows if row.get("model") == model],
                    window_start,
                )
                for model in OTHER_GENERATION_MODELS
            },
        })

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _iso(generated_at),
        "window": {
            "start": _iso(window_start),
            "end": _iso(generated_at),
            "hours": WINDOW_HOURS,
            "bucket_count": BUCKET_COUNT,
        },
        "summary": {
            **_summary(pool_rows, runtime_attempts, window_start=window_start),
            "metadata_observations": len(metadata_attempts),
            "other_model_usage": {
                model: _model_snapshot(
                    [row for row in runtime_attempts if row.get("model") == model],
                    window_start,
                )
                for model in OTHER_GENERATION_MODELS
            },
        },
        "latest_metadata_batch": _latest_metadata_batch(metadata_attempts),
        "fallback": _latest_fallback(runtime_attempts),
        "latest_route": _latest_route(runtime_attempts),
        "keys": keys,
    }
