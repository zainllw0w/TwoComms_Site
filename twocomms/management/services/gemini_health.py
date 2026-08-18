"""Bounded, redacted Gemini API health evidence for the management UI."""

from __future__ import annotations

import datetime as dt
from collections import defaultdict
from typing import Any

from django.utils import timezone

from management.models import GeminiRequestAttempt
from management.services import gemini_keys


SCHEMA_VERSION = 1
WINDOW_HOURS = 24
BUCKET_COUNT = 24
ATTEMPT_QUERY_CAP = 2000
DISPLAY_MODELS = ("gemini-3.7-flash", "gemini-3.6-flash")
MODELS = DISPLAY_MODELS
KEY_ALIASES = (
    "GEMINI_API",
    "GEMINI_API2",
    "GEMINI_API3",
    "GEMINI_API4",
    "GEMINI_API5",
    "GEMINI_API6",
)
DISPLAY_ALIASES = {
    key_name: f"API key {index}"
    for index, key_name in enumerate(KEY_ALIASES, start=1)
}

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
    if not rows:
        return "no_observation"

    ordered = sorted(rows, key=_attempt_sort_key)
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
) -> list[dict[str, str]]:
    """Build bucket statuses while retaining recovery evidence across buckets."""
    ordered = sorted(rows, key=_attempt_sort_key)
    by_bucket: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in ordered:
        by_bucket[_bucket_index(row["created_at"], window_start)].append(row)

    recovered_failures, recovered_successes = _ordered_recovery_row_ids(ordered)
    history: list[dict[str, str]] = []
    for index in range(BUCKET_COUNT):
        bucket_rows = by_bucket.get(index, [])
        status = _status_for_attempts(bucket_rows, window_start=window_start)
        if bucket_rows:
            latest = max(bucket_rows, key=_attempt_sort_key)
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

    success_count = sum(1 for row in rows if _attempt_succeeded(row))
    failure_count = len(rows) - success_count
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
        "recovered": recovered_count,
        "last_observation_at": _iso(last["created_at"]),
        "last_latency_ms": max(0, int(last.get("latency_ms") or 0)),
        "history": history,
    })
    return snapshot


def _group_by_request(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if str(row.get("key_name") or "") not in KEY_ALIASES:
            continue
        request_id = str(row.get("request_id") or "").strip()
        if not request_id:
            continue
        grouped[request_id].append(row)
    for request_rows in grouped.values():
        request_rows.sort(
            key=lambda row: (
                _as_utc(row["created_at"]),
                int(row.get("id") or 0),
            )
        )
    return grouped


def _latest_fallback(rows: list[dict[str, Any]]) -> dict[str, str | None] | None:
    latest: tuple[tuple[dt.datetime, int], dict[str, str | None]] | None = None
    for request_rows in _group_by_request(rows).values():
        for index, row in enumerate(request_rows):
            if row.get("model") != "gemini-3.7-flash" or _attempt_succeeded(row):
                continue
            for next_row in request_rows[index + 1:]:
                if next_row.get("model") != "gemini-3.6-flash":
                    continue
                if not _attempt_succeeded(next_row):
                    continue
                failure_kind = str(row.get("failure_kind") or "").strip().lower()
                fallback = {
                    "from_model": "gemini-3.7-flash",
                    "to_model": "gemini-3.6-flash",
                    "reason": _FAILURE_REASON_LABELS.get(failure_kind, "3.7 request failed"),
                    "observed_at": _iso(next_row["created_at"]),
                }
                observed_at = _attempt_sort_key(next_row)
                if latest is None or observed_at > latest[0]:
                    latest = (observed_at, fallback)
                break
    return latest[1] if latest else None


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
                "last_observation_at": None,
            }
            continue
        successes = sum(1 for row in model_rows if _attempt_succeeded(row))
        models[model] = {
            "status": _status_for_attempts(model_rows, window_start=window_start),
            "observations": len(model_rows),
            "successes": successes,
            "failures": len(model_rows) - successes,
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
    attempt_rows = list(
        GeminiRequestAttempt.objects.filter(
            created_at__gte=window_start,
            created_at__lte=generated_at,
            key_name__in=KEY_ALIASES,
            model__in=DISPLAY_MODELS,
        )
        .order_by("-created_at", "-id")
        .values(
            "id",
            "request_id",
            "key_name",
            "model",
            "outcome",
            "failure_kind",
            "latency_ms",
            "created_at",
        )[:ATTEMPT_QUERY_CAP]
    )
    # Newest rows are selected under the cap, then restored to chronological
    # order so fallback and retry classification are deterministic.
    attempt_rows.sort(key=lambda row: (_as_utc(row["created_at"]), int(row.get("id") or 0)))

    pool_rows = list(gemini_keys.pool_status(now=generated_at))
    pool_by_key = _pool_row_by_key(pool_rows)
    keys = []
    for key_name in KEY_ALIASES:
        pool_row = pool_by_key.get(key_name, {})
        row_attempts = [row for row in attempt_rows if row.get("key_name") == key_name]
        keys.append({
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
            "models": {
                model: _model_snapshot(
                    [row for row in row_attempts if row.get("model") == model],
                    window_start,
                )
                for model in DISPLAY_MODELS
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
        "summary": _summary(pool_rows, attempt_rows, window_start=window_start),
        "fallback": _latest_fallback(attempt_rows),
        "keys": keys,
    }
