"""Request-local limits for validated Instagram provider replies."""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable


_SAFE_REASON_CODE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
MAX_REASON_CODES = 12
_VALIDATION_USAGE_COUNTS = (
    "promptTokenCount",
    "thoughtsTokenCount",
    "candidatesTokenCount",
    "totalTokenCount",
    "_request_inline_count",
    "_request_trimmed_inline",
    "_request_serialized_bytes",
)


@dataclass(frozen=True)
class ValidationDecision:
    valid: bool
    reason_codes: tuple[str, ...] = ()


def normalize_validation_decision(value) -> ValidationDecision:
    """Return one bounded decision without retaining validator error details."""
    valid = bool(getattr(value, "valid", False))
    raw_reasons: Iterable = getattr(
        value,
        "reason_codes",
        getattr(value, "reasons", ()),
    ) or ()
    reasons: list[str] = []
    for raw in raw_reasons:
        reason = str(raw or "").strip().casefold()
        if _SAFE_REASON_CODE.fullmatch(reason) and reason not in reasons:
            reasons.append(reason)
        if len(reasons) >= MAX_REASON_CODES:
            break
    if valid:
        return ValidationDecision(valid=True)
    return ValidationDecision(
        valid=False,
        reason_codes=tuple(reasons) or ("invalid_result",),
    )


def sanitized_validation_usage(usage) -> dict:
    """Expose only bounded runtime counters needed by deterministic validation."""
    source = usage if isinstance(usage, dict) else {}
    sanitized = {}
    for name in _VALIDATION_USAGE_COUNTS:
        try:
            value = int(source.get(name) or 0)
        except (TypeError, ValueError, OverflowError):
            value = 0
        sanitized[name] = max(0, value)
    sanitized["_finish_reason"] = str(
        source.get("_finish_reason") or ""
    )[:32]
    return sanitized


@dataclass
class ProviderDispatchBudget:
    """Count actual HTTP dispatches and permit at most one repair payload."""

    max_dispatches: int = 2
    consumed_dispatches: int = 0
    repair_consumed: bool = False

    def __post_init__(self) -> None:
        value = int(self.max_dispatches)
        if value < 1 or value > 2:
            raise ValueError("validated provider dispatch limit must be 1 or 2")
        self.max_dispatches = value

    @property
    def remaining_dispatches(self) -> int:
        return max(0, self.max_dispatches - self.consumed_dispatches)

    def consume_dispatch(self) -> bool:
        """Consume immediately before HTTP I/O; false means no dispatch."""
        if self.remaining_dispatches <= 0:
            return False
        self.consumed_dispatches += 1
        return True

    def consume_repair(self) -> bool:
        """Reserve the sole repair only while an HTTP attempt remains."""
        if self.repair_consumed or self.remaining_dispatches <= 0:
            return False
        self.repair_consumed = True
        return True
