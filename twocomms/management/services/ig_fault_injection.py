"""ЭА.22 — fault-injection harness for reproducible provider glitches.

Why this module exists separately from production code.

All ЭА protections defend against external failures, but can only be verified
during real provider degradation. This is unacceptable: waiting for the next
incident to know whether the protection works means validating on customers.

The harness enables on-demand reproduction of degradation in tests. It mocks
`_gemini_call_once` at the transport level — the same entry point production
calls use — and lets tests inject typed failure sequences.

Design principles:

1. Test-only: never imported by production code, never reads settings/env.
2. Scenario-first: named fixtures cover the failure matrix from section 12 of
   the handoff document rather than low-level primitives.
3. Outcome sequences: one scenario is a list of outcomes indexed by attempt,
   so "503 on first, success on second" is explicit.
4. Typed exceptions: failures raise the same typed exceptions production code
   handles (_GeminiTransient, _Gemini429, _GeminiFatal, _GeminiEmpty).
5. Actual contracts: success responses use the real app schema (`reply_text`,
   `controls`) and usage metadata (`promptTokenCount`, `_finish_reason`).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class InjectedOutcome:
    """One scripted outcome for a single _gemini_call_once invocation.

    Exactly one of `success_response`, `exception`, or `delay_then_outcome`
    must be set. `success_response` is (parsed_dict_or_text, usage_dict).
    """
    success_response: tuple[Any, dict] | None = None
    exception: Exception | None = None
    delay_then_outcome: tuple[float, InjectedOutcome] | None = None

    def __post_init__(self):
        set_count = sum([
            self.success_response is not None,
            self.exception is not None,
            self.delay_then_outcome is not None,
        ])
        if set_count != 1:
            raise ValueError("exactly one outcome field must be set")


@dataclass(frozen=True)
class FaultScenario:
    """Failure scenario: a sequence of outcomes by attempt number.

    `outcomes[i]` is returned on attempt i (zero-indexed). If the scenario
    runs past len(outcomes), it loops the final outcome.
    """
    name: str
    outcomes: tuple[InjectedOutcome, ...]

    def __post_init__(self):
        if not self.outcomes:
            raise ValueError("scenario must have at least one outcome")


def _make_exception(kind: str, *, http_code: int | None = None,
                    provider_reason: str = "", retry_after: int = 0) -> Exception:
    """Build a typed Gemini exception matching production classification."""
    from management.services.call_ai_analysis import (
        _Gemini429, _GeminiEmpty, _GeminiFatal, _GeminiModelUnavailable,
        _GeminiTransient
    )

    if kind == "quota_429":
        exc = _Gemini429(
            f"injected {kind}",
            scope="unknown",
            retry_after_seconds=retry_after,
            provider_reason=provider_reason or "RESOURCE_EXHAUSTED",
            provider_quota_metric="",
            provider_quota_id="",
        )
        exc.http_code = 429
        return exc
    elif kind == "http_503":
        exc = _GeminiTransient(f"injected {kind}")
        exc.http_code = 503
        exc.provider_reason = provider_reason or "UNAVAILABLE"
        return exc
    elif kind == "http_500":
        exc = _GeminiTransient(f"injected {kind}")
        exc.http_code = 500
        exc.provider_reason = provider_reason or "INTERNAL"
        return exc
    elif kind == "timeout":
        exc = _GeminiTransient(f"injected {kind}: timeout")
        exc.http_code = None
        exc.provider_reason = ""
        return exc
    elif kind == "connect":
        exc = _GeminiTransient(f"injected {kind}: transport")
        exc.http_code = None
        exc.provider_reason = ""
        return exc
    elif kind == "invalid_payload":
        exc = _GeminiFatal(f"injected {kind}")
        exc.http_code = 400
        exc.provider_reason = "INVALID_ARGUMENT"
        return exc
    elif kind == "auth":
        exc = _GeminiFatal(f"injected {kind}")
        exc.http_code = 403
        exc.provider_reason = "PERMISSION_DENIED"
        return exc
    elif kind == "not_found":
        exc = _GeminiModelUnavailable(f"injected {kind}")
        exc.http_code = 404
        exc.provider_reason = "NOT_FOUND"
        return exc
    elif kind == "empty":
        exc = _GeminiEmpty(f"injected {kind}")
        return exc
    else:
        raise ValueError(f"unsupported exception kind: {kind}")


def _success(text: str = "injected success", input_tokens: int = 100,
             output_tokens: int = 50, parsed: bool = True) -> InjectedOutcome:
    """Standard success outcome with synthetic usage.

    If `parsed=True`, returns structured response with `reply_text` and
    `controls` matching the actual app schema. If `parsed=False`, returns
    raw text (for non-parsed responses).
    """
    if parsed:
        payload = {"reply_text": text, "controls": []}
    else:
        payload = text
    return InjectedOutcome(
        success_response=(
            payload,
            {
                "promptTokenCount": input_tokens,
                "candidatesTokenCount": output_tokens,
                "_finish_reason": "STOP",
            }
        )
    )


def _failure(kind: str, **kwargs) -> InjectedOutcome:
    """Standard failure outcome wrapping a typed exception."""
    return InjectedOutcome(exception=_make_exception(kind, **kwargs))


# --- Named scenario fixtures covering section 12 matrix ---

def full_429_all_aliases() -> FaultScenario:
    """All candidates return 429, forcing circuit open or fallback."""
    return FaultScenario(
        name="full_429_all_aliases",
        outcomes=(_failure("quota_429", retry_after=60),)
    )


def http_503_first_then_success() -> FaultScenario:
    """503 on first attempt, success on second (alias failover)."""
    return FaultScenario(
        name="http_503_first_then_success",
        outcomes=(
            _failure("http_503"),
            _success("recovered after 503"),
        )
    )


def read_timeout_all_models() -> FaultScenario:
    """ReadTimeout on every attempt (network-level, not HTTP)."""
    return FaultScenario(
        name="read_timeout_all_models",
        outcomes=(_failure("timeout"),)
    )


def invalid_payload_400() -> FaultScenario:
    """400 INVALID_ARGUMENT blocks retry with the same payload."""
    return FaultScenario(
        name="invalid_payload_400",
        outcomes=(_failure("invalid_payload"),)
    )


def slow_success_30_seconds() -> FaultScenario:
    """Success after 30-second delay (tests progress pulse, not timeout)."""
    return FaultScenario(
        name="slow_success_30_seconds",
        outcomes=(
            InjectedOutcome(delay_then_outcome=(30.0, _success("delayed success"))),
        )
    )


def success_between_two_failures() -> FaultScenario:
    """Fail, succeed, fail — checks partial recovery doesn't close incident."""
    return FaultScenario(
        name="success_between_two_failures",
        outcomes=(
            _failure("http_503"),
            _success("transient recovery"),
            _failure("http_503"),
        )
    )


def failure_then_recovery_after_2_minutes() -> FaultScenario:
    """Fail initially, then succeed — simulates provider recovery."""
    return FaultScenario(
        name="failure_then_recovery_after_2_minutes",
        outcomes=(
            _failure("http_503"),
            _success("provider recovered"),
        )
    )


def flapping_success_and_failure() -> FaultScenario:
    """Alternating success and failure — incident must not close prematurely."""
    return FaultScenario(
        name="flapping_success_and_failure",
        outcomes=(
            _failure("http_503"),
            _success("flap up"),
            _failure("http_503"),
            _success("flap up again"),
            _failure("http_503"),
        )
    )


def partial_degradation_model_37_unavailable_36_works() -> FaultScenario:
    """Model 3.7 fails, 3.6 succeeds — tests L2 ladder."""
    return FaultScenario(
        name="partial_degradation_model_37_unavailable_36_works",
        outcomes=(
            _failure("http_503"),
            _success("fallback to 3.6"),
        )
    )


def valid_http_200_invalid_application_schema() -> FaultScenario:
    """HTTP 200 with response that fails application validation.

    This is a "model glitch" not covered by provider failure classes: the
    provider returns 200, but the payload doesn't match the expected schema.
    Production must not send this to the customer as-is.
    """
    return FaultScenario(
        name="valid_http_200_invalid_application_schema",
        outcomes=(
            InjectedOutcome(
                success_response=(
                    {"unexpected_field": "not a valid reply structure"},
                    {"promptTokenCount": 100, "candidatesTokenCount": 20, "_finish_reason": "STOP"}
                )
            ),
        )
    )


def model_replies_wrong_language() -> FaultScenario:
    """Model returns English when Ukrainian was requested (validation failure).

    ЭА.22 finding: production has no output language validation. This scenario
    characterizes the current (buggy) behavior — wrong-language output DOES
    reach the customer. Proper coverage would be a test that verifies this bug
    exists, then a separate task to fix it and turn the test green.
    """
    return FaultScenario(
        name="model_replies_wrong_language",
        outcomes=(
            InjectedOutcome(
                success_response=(
                    {"reply_text": "Hello, this is in English", "controls": []},
                    {"promptTokenCount": 100, "candidatesTokenCount": 30, "_finish_reason": "STOP"}
                )
            ),
        )
    )


def model_returns_empty_text() -> FaultScenario:
    """Model returns structurally valid JSON but empty reply text.

    ЭА.22 contract: empty text MUST be rejected before send. This is validated
    by `ig_response_control.parse_structured_response`, which returns an error
    when `reply_text` is empty or whitespace-only.
    """
    return FaultScenario(
        name="model_returns_empty_text",
        outcomes=(
            InjectedOutcome(
                success_response=(
                    {"reply_text": "", "controls": []},
                    {"promptTokenCount": 100, "candidatesTokenCount": 0, "_finish_reason": "STOP"}
                )
            ),
        )
    )


def auth_403_permission_denied() -> FaultScenario:
    """403 PERMISSION_DENIED — configuration error, no retry."""
    return FaultScenario(
        name="auth_403_permission_denied",
        outcomes=(_failure("auth"),)
    )


def not_found_404_unknown_model() -> FaultScenario:
    """404 NOT_FOUND — model or project misconfigured, no retry."""
    return FaultScenario(
        name="not_found_404_unknown_model",
        outcomes=(_failure("not_found"),)
    )


# Registry of all named scenarios for discovery and testing.
ALL_SCENARIOS: tuple[Callable[[], FaultScenario], ...] = (
    full_429_all_aliases,
    http_503_first_then_success,
    read_timeout_all_models,
    invalid_payload_400,
    slow_success_30_seconds,
    success_between_two_failures,
    failure_then_recovery_after_2_minutes,
    flapping_success_and_failure,
    partial_degradation_model_37_unavailable_36_works,
    valid_http_200_invalid_application_schema,
    model_replies_wrong_language,
    model_returns_empty_text,
    auth_403_permission_denied,
    not_found_404_unknown_model,
)


def build_injector(scenario: FaultScenario) -> Callable:
    """Build a mock side_effect for patch.object(ai, "_gemini_call_once").

    The returned callable tracks attempt count and returns outcomes from the
    scenario sequence. If attempts exceed len(outcomes), the final outcome
    repeats.

    Usage:
        scenario = http_503_first_then_success()
        with patch.object(ai, "_gemini_call_once", side_effect=build_injector(scenario)):
            # first call raises _GeminiTransient(503)
            # second call returns success
    """
    attempt_count = 0

    def injector(*args, **kwargs):
        nonlocal attempt_count
        index = min(attempt_count, len(scenario.outcomes) - 1)
        outcome = scenario.outcomes[index]
        attempt_count += 1

        # Handle delayed outcomes (e.g. 30-second success).
        if outcome.delay_then_outcome is not None:
            import time
            delay, delayed = outcome.delay_then_outcome
            time.sleep(delay)
            outcome = delayed

        # Drive attempt_boundary lifecycle if present.
        attempt_boundary = kwargs.get("attempt_boundary")
        if attempt_boundary is not None:
            serialized_bytes = 512  # Synthetic request size
            admitted = attempt_boundary.before_provider(
                serialized_bytes=serialized_bytes,
                inline_count=0,
            )
            if not admitted:
                # Boundary rejected the attempt (stale/non-canonical).
                from management.services.call_ai_analysis import _GeminiAdmissionRejected
                error = _GeminiAdmissionRejected("stale provider boundary")
                attempt_boundary.cancelled_pre_dispatch(error)
                raise error

        # Return or raise based on outcome type.
        if outcome.exception is not None:
            if attempt_boundary is not None:
                attempt_boundary.failed(outcome.exception)
            raise outcome.exception
        elif outcome.success_response is not None:
            if attempt_boundary is not None:
                attempt_boundary.succeeded(outcome.success_response[1])
            return outcome.success_response
        else:
            raise RuntimeError("InjectedOutcome invariant violated")

    return injector
