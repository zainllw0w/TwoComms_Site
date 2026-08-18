"""Token-free Gemini model-resource readiness checks."""
from __future__ import annotations

import datetime as dt
import json
import socket
import time
import uuid
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.utils import timezone

from management.services import gemini_keys

MODELS = ("gemini-3.7-flash", "gemini-3.6-flash")
ROLE = "health_metadata"
BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
TIMEOUT_SECONDS = 5
CHECK_DEADLINE_SECONDS = 70
MAX_METADATA_BYTES = 16 * 1024

def _status_for_http(code: int) -> str:
    known = {
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        408: "http_408",
        429: "rate_limited",
    }
    if code in known:
        return known[code]
    if 500 <= code <= 599:
        return "http_5xx"
    return "http_error"

def _supports_generate_content(response) -> bool:
    try:
        raw = response.read(MAX_METADATA_BYTES + 1)
        if not isinstance(raw, bytes) or len(raw) > MAX_METADATA_BYTES:
            return False
        payload = json.loads(raw.decode("utf-8"))
    except (AttributeError, UnicodeDecodeError, json.JSONDecodeError, OSError):
        return False
    methods = payload.get("supportedGenerationMethods") if isinstance(payload, dict) else None
    return isinstance(methods, list) and "generateContent" in methods

def _record(
    *,
    request_id: str,
    alias: str,
    model: str,
    status: str,
    latency_ms: int = 0,
    http_code: int | None = None,
) -> None:
    succeeded = status == "metadata_ok"
    skipped = status == "not_needed"
    gemini_keys.record_attempt(
        request_id=request_id,
        role=ROLE,
        key_name=alias,
        model=model,
        outcome="succeeded" if succeeded else ("skipped" if skipped else "failed"),
        failure_kind="" if succeeded else status,
        http_code=http_code,
        decision="skipped_primary_ok" if skipped else "metadata_only",
        latency_ms=latency_ms,
    )

def _check_model(
    alias: str,
    api_key: str,
    model: str,
    request_id: str,
    *,
    deadline: float | None = None,
) -> dict:
    started = time.monotonic()
    if deadline is not None and time.monotonic() >= deadline:
        return {
            "model": model,
            "status": "deadline_skipped",
            "http_code": None,
            "latency_ms": 0,
            "evidence_kind": "metadata_only",
            "generation_quota_proven": False,
        }
    request = Request(f"{BASE_URL}/models/{model}", headers={"X-goog-api-key": api_key, "User-Agent": "TwoComms-Gemini-Health/1.0"}, method="GET")
    code = None
    timeout = TIMEOUT_SECONDS
    if deadline is not None:
        timeout = min(timeout, max(0.1, deadline - time.monotonic()))
    try:
        with urlopen(request, timeout=timeout) as response:
            code = int(getattr(response, "status", 200) or 200)
            supports_generation = code == 200 and _supports_generate_content(response)
        status = "metadata_ok" if supports_generation else (
            "unsupported_generation" if code == 200 else _status_for_http(code)
        )
    except HTTPError as exc:
        code = int(exc.code or 0) or None
        status = _status_for_http(code or 0)
    except (TimeoutError, socket.timeout):
        status = "timeout"
    except URLError as exc:
        status = (
            "timeout"
            if isinstance(getattr(exc, "reason", None), (TimeoutError, socket.timeout))
            else "transport_error"
        )
    except OSError:
        status = "transport_error"
    latency_ms = max(0, round((time.monotonic() - started) * 1000))
    _record(
        request_id=request_id,
        alias=alias,
        model=model,
        status=status,
        latency_ms=latency_ms,
        http_code=code,
    )
    return {"model": model, "status": status, "http_code": code, "latency_ms": latency_ms, "evidence_kind": "metadata_only", "generation_quota_proven": False}

def check_alias(
    alias: str,
    *,
    now: dt.datetime | None = None,
    request_id: str | None = None,
    deadline: float | None = None,
) -> list[dict]:
    now = now or timezone.now()
    request_id = request_id or f"meta-{now:%Y%m%d%H}-{uuid.uuid4().hex[:8]}"
    api_key = gemini_keys._key_value(alias)
    if not api_key:
        return [{"model": model, "status": "unconfigured", "evidence_kind": "metadata_only", "generation_quota_proven": False} for model in MODELS]
    primary = _check_model(alias, api_key, MODELS[0], request_id, deadline=deadline)
    if primary["status"] == "metadata_ok":
        secondary = {"model": MODELS[1], "status": "not_needed", "evidence_kind": "metadata_only", "generation_quota_proven": False}
        _record(request_id=request_id, alias=alias, model=MODELS[1], status="not_needed")
    else:
        secondary = _check_model(alias, api_key, MODELS[1], request_id, deadline=deadline)
    return [primary, secondary]

def run_hour(*, now: dt.datetime | None = None) -> dict:
    now = now or timezone.now()
    batch_id = f"meta-{now:%Y%m%d%H}-{uuid.uuid4().hex[:8]}"
    deadline = time.monotonic() + CHECK_DEADLINE_SECONDS
    alias_results: list[list[dict]] = []
    for alias in gemini_keys.ALL_KEYS:
        alias_id = f"{batch_id}-{alias[-1]}"
        alias_results.append(
            check_alias(alias, now=now, request_id=alias_id, deadline=deadline)
        )
    statuses = [
        str(model_result.get("status") or "")
        for result in alias_results
        for model_result in result
    ]
    no_provider_statuses = {"deadline_skipped", "not_needed", "unconfigured"}
    return {
        "request_id": batch_id,
        "checked_aliases": len(alias_results),
        "configured_aliases": sum(
            1
            for result in alias_results
            if any(row.get("status") != "unconfigured" for row in result)
        ),
        "provider_requests": sum(
            1 for status in statuses if status not in no_provider_statuses
        ),
        "deadline_skipped_models": statuses.count("deadline_skipped"),
    }
