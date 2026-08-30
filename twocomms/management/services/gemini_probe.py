"""Redacted, non-customer Gemini connectivity probes."""
from __future__ import annotations

import json
import time
import uuid

import requests

from management.services.call_ai_analysis import GENAI_BASE, _payload_for_model

PROBE_TIMEOUT = (5, 20)
PROBE_OUTPUT_TOKENS = 128


def build_probe_payload(model: str) -> dict:
    payload = {
        "contents": [{"role": "user", "parts": [{"text": "Reply exactly OK."}]}],
        "generationConfig": {
            "temperature": 0,
            "maxOutputTokens": PROBE_OUTPUT_TOKENS,
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }
    return _payload_for_model(model, payload, reasoning_task="health_probe")


def _usage_value(usage: dict, *names: str) -> int:
    for name in names:
        value = usage.get(name)
        if isinstance(value, int):
            return value
    return 0


def classify_probe_response(http_code: int, body: str) -> dict:
    """Return bounded status data; never include provider text or credentials."""
    if http_code != 200:
        status = {
            403: "forbidden",
            404: "model_unavailable",
            429: "quota",
        }.get(http_code, "provider_error" if http_code >= 500 else "request_error")
        return {"status": status, "http_code": http_code, "finish_reason": "", "thoughts_tokens": 0,
                "candidates_tokens": 0}
    try:
        data = json.loads(body or "{}")
    except (TypeError, ValueError):
        return {"status": "malformed_response", "http_code": http_code, "finish_reason": "",
                "thoughts_tokens": 0, "candidates_tokens": 0}
    if not isinstance(data, dict):
        return {"status": "malformed_response", "http_code": http_code, "finish_reason": "",
                "thoughts_tokens": 0, "candidates_tokens": 0}
    malformed = False
    candidates = data.get("candidates", [])
    if candidates is None:
        candidates = []
    elif not isinstance(candidates, list):
        malformed = True
        candidates = []
    candidate = candidates[0] if candidates and isinstance(candidates[0], dict) else {}
    reason = str(candidate.get("finishReason") or "")[:32]
    content = candidate.get("content", {})
    if content is None:
        content = {}
    elif not isinstance(content, dict):
        malformed = True
        content = {}
    parts = content.get("parts", [])
    if parts is None:
        parts = []
    elif not isinstance(parts, list):
        malformed = True
        parts = []
    text = "".join(
        str(part.get("text") or "")
        for part in parts
        if isinstance(part, dict) and not part.get("thought")
    ).strip()
    usage = data.get("usageMetadata", {})
    if usage is None:
        usage = {}
    elif not isinstance(usage, dict):
        malformed = True
        usage = {}
    result = {
        "status": "malformed_response" if malformed else ("ok" if text else "reachable_empty"),
        "http_code": http_code,
        "finish_reason": reason,
        "thoughts_tokens": _usage_value(usage, "thoughtsTokenCount", "thoughts_token_count"),
        "candidates_tokens": _usage_value(usage, "candidatesTokenCount", "candidates_token_count"),
    }
    if reason == "SAFETY" or (isinstance(data.get("promptFeedback"), dict) and (data.get("promptFeedback") or {}).get("blockReason")):
        result["status"] = "blocked"
    elif reason == "MAX_TOKENS":
        result["status"] = "reachable_degraded"
    return result


def probe_key(model: str, key: str, timeout: tuple | None = None) -> dict:
    started = time.monotonic()
    body = json.dumps(build_probe_payload(model))
    boundary = None
    try:
        from management.services import gemini_accounting_runtime, gemini_keys

        alias = gemini_keys.configured_alias_for_secret(key)
        identity = gemini_keys.project_group(alias) if alias else ""
        observer = gemini_accounting_runtime.begin_request(
            request_id=f"diag-{uuid.uuid4().hex[:32]}",
            role="diagnostic",
            reasoning_task="health_probe",
            candidate_plan=[{
                "candidate_index": 1,
                "key_name": alias or "(manual)",
                "project_identity": identity,
                "identity_status": "known" if identity else "unknown",
                "model": model,
                "skip_reason": "",
            }],
            lane="diagnostic",
        )
        boundary = observer.attempt(
            key_name=alias or "(manual)", model=model, candidate_index=1
        )
        boundary.before_provider(
            serialized_bytes=len(body.encode("utf-8")),
            inline_count=0,
        )
    except Exception:
        boundary = None
    try:
        response = requests.post(
            f"{GENAI_BASE}/models/{model}:generateContent",
            data=body,
            headers={"Content-Type": "application/json", "x-goog-api-key": key},
            timeout=timeout or PROBE_TIMEOUT,
        )
        result = classify_probe_response(response.status_code, response.text)
        usage = {}
        if response.status_code == 200:
            try:
                payload = response.json()
                usage = payload.get("usageMetadata") if isinstance(payload, dict) else {}
            except (TypeError, ValueError):
                usage = {}
        if boundary is not None:
            boundary.manual_result(
                succeeded=response.status_code == 200,
                http_code=response.status_code,
                failure_kind="" if response.status_code == 200 else str(result.get("status") or "provider_error"),
                usage=usage,
            )
    except requests.Timeout:
        result = {"status": "timeout", "http_code": 0, "finish_reason": "", "thoughts_tokens": 0,
                  "candidates_tokens": 0}
        if boundary is not None:
            boundary.manual_result(succeeded=False, failure_kind="read_timeout")
    except requests.RequestException:
        result = {"status": "transport_error", "http_code": 0, "finish_reason": "", "thoughts_tokens": 0,
                  "candidates_tokens": 0}
        if boundary is not None:
            boundary.manual_result(succeeded=False, failure_kind="transport")
    result["latency_ms"] = max(0, int((time.monotonic() - started) * 1000))
    result["model"] = model
    return result


def probe_key_metadata(model: str, key: str, timeout: tuple | None = None) -> dict:
    """Проверка доступности пары БЕЗ расхода генерационной квоты (ЭБ.4).

    `probe_key()` выше отправляет настоящий `generateContent`. При лимите free-tier
    20 запросов в сутки на пару (проект, модель) одна такая проверка стоит 5%
    дневного бюджета, а шесть ключей на двух моделях — 10% всего дня. Ради строки
    «работает» в админке это неприемлемо: именно эти перепроверки и съедали
    квоту, из-за которой клиент затем получал техническое извинение.

    Здесь — `GET /models/{model}`: он подтверждает, что ключ валиден, модель
    существует и поддерживает `generateContent`, и НЕ тратит запросов генерации.
    Чего он не доказывает — что квота генерации ещё не исчерпана; это видно из
    локального учёта (`gemini_quota`) и из реальных отказов, а не из проверки.
    """
    started = time.monotonic()
    read_timeout = float((timeout or PROBE_TIMEOUT)[1])
    status = "transport_error"
    http_code = 0
    try:
        response = requests.get(
            f"{GENAI_BASE}/models/{model}",
            headers={"x-goog-api-key": key},
            timeout=timeout or PROBE_TIMEOUT,
        )
        http_code = int(response.status_code or 0)
        if http_code == 200:
            try:
                methods = (response.json() or {}).get("supportedGenerationMethods")
            except (TypeError, ValueError):
                methods = None
            supports = isinstance(methods, list) and "generateContent" in methods
            status = "metadata_ok" if supports else "unsupported_generation"
        else:
            status = {
                403: "forbidden",
                404: "model_unavailable",
                429: "quota",
            }.get(http_code, "provider_error" if http_code >= 500 else "request_error")
    except requests.Timeout:
        status = "timeout"
    except requests.RequestException:
        status = "transport_error"
    return {
        "status": status,
        "http_code": http_code,
        "finish_reason": "",
        "thoughts_tokens": 0,
        "candidates_tokens": 0,
        "latency_ms": max(0, int((time.monotonic() - started) * 1000)),
        "model": model,
        "evidence_kind": "metadata_only",
        "read_timeout": read_timeout,
    }
