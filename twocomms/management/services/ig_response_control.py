"""Typed, fail-closed boundary for model replies and operational controls.

The worker can keep consuming the historical ``control`` mapping, but only a
validated immutable response may produce that mapping.  This module deliberately
has no provider or database side effects.
"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any


CONTROL_KINDS = frozenset(
    {
        "manager",
        "spam",
        "stage",
        "paylink",
        "payment",
        "product",
        "item",
        "option",
        "qty",
        "size",
        "fit",
        "color_variant_id",
        "price",
        "price_quoted",
        "order",
        "show_products",
        "catalog_link",
        "objhandle",
    }
)
_KIND_ALIASES = {"opt": "option", "variant": "color_variant_id"}
_REPEATED_KINDS = frozenset({"item", "option"})
_BOOLEAN_KINDS = frozenset({"manager", "spam", "order", "catalog_link"})
_HARD_STAGES = frozenset({"paid", "order_created", "done"})
_STAGES = frozenset(
    {
        "new",
        "qualifying",
        "product_matched",
        "checkout",
        "payment_pending",
        "paid",
        "order_created",
        "done",
        "lead_manager",
        "spam",
        "cold",
    }
)

# These broad, unbounded-by-length matchers are intentional: an ASCII bracket
# token which looks like a command must never reach a customer, even if its
# name is misspelled or a malformed provider response makes it very long.  The
# negated character classes keep both passes linear in the reply length.
_ASCII_CLOSED_CONTROL_TOKEN_RE = re.compile(r"\[[A-Za-z][^\]\r\n]*\]")
_ASCII_CONTROL_SHAPED_RE = re.compile(r"\[[A-Za-z][^\]\r\n]*(?:\]|\r?\n|$)")
_KNOWN_KIND_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
_ID_RE = re.compile(r"^[1-9][0-9]{0,9}$")
_QTY_RE = re.compile(r"^[1-9][0-9]{0,3}$")
_SIZE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _-]{0,15}$")
_FIT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _-]{0,49}$")
_OPTION_RE = re.compile(r"^[a-z][a-z0-9_-]{0,48}=[^=;\[\]\r\n]{1,80}$", re.I)
_OBJHANDLE_RE = re.compile(r"^[a-z][a-z0-9_]{0,47}:[a-z][a-z0-9_]{0,47}$")

# Gemini's structured-output schema is deliberately broader than the
# application validator: ``value`` has different types for different kinds,
# and the validator below remains the authorization boundary.
STRUCTURED_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "reply_text": {
            "type": "string",
            "minLength": 1,
            "maxLength": 4000,
        },
        "controls": {
            "type": "array",
            "maxItems": 32,
            "items": {
                "type": "object",
                "properties": {
                    "kind": {
                        "type": "string",
                        "enum": sorted(CONTROL_KINDS),
                    },
                    "value": {
                        "anyOf": [
                            {"type": "string"},
                            {"type": "boolean"},
                            {"type": "integer"},
                            {"type": "number"},
                            {"type": "array", "items": {"type": "integer"}},
                        ]
                    },
                },
                "required": ["kind", "value"],
            },
        },
    },
    "required": ["reply_text", "controls"],
}


def structured_response_schema() -> dict[str, Any]:
    """Return a caller-owned copy of the provider response schema."""
    return deepcopy(STRUCTURED_RESPONSE_SCHEMA)


@dataclass(frozen=True)
class ResponseControl:
    """One normalized control emitted by the model."""

    kind: str
    value: str | bool


@dataclass(frozen=True)
class ValidatedResponse:
    """Immutable parser result.

    ``control`` is a fresh compatibility projection.  Mutating that projection
    cannot mutate the validated tuple or alter a later projection.
    """

    reply_text: str
    controls: tuple[ResponseControl, ...] = ()
    valid: bool = True
    error: str = ""

    @property
    def control(self) -> dict[str, Any]:
        if not self.valid:
            return {}
        projected: dict[str, Any] = {}
        for entry in self.controls:
            if entry.kind in _REPEATED_KINDS:
                projected.setdefault(f"{entry.kind}s", []).append(entry.value)
            else:
                projected[entry.kind] = entry.value
        return projected

    @property
    def downstream_control(self) -> dict[str, Any]:
        """Explicit name for callers migrating from the legacy tuple parser."""
        return self.control


def _clean_text(text: object) -> str:
    value = str(text or "")
    value = _ASCII_CONTROL_SHAPED_RE.sub("", value)
    value = re.sub(r"[ \t]{2,}", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def _failure(text: object, reason: str) -> ValidatedResponse:
    # Invalid provider text must not be retained in a compatibility result:
    # stringifying an object can expose fields that were never customer text.
    clean = "" if reason == "invalid_reply_text" else _clean_text(text)
    return ValidatedResponse(reply_text=clean, valid=False, error=reason)


def _positive_integer(value: object, *, quantity: bool = False) -> str | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        value = str(value)
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not (re.fullmatch(_QTY_RE, value) if quantity else re.fullmatch(_ID_RE, value)):
        return None
    return value


def _positive_decimal(value: object) -> str | None:
    if isinstance(value, bool) or isinstance(value, (dict, list, tuple)):
        return None
    if isinstance(value, (int, float, Decimal)):
        value = str(value)
    if not isinstance(value, str):
        return None
    raw = value.strip().replace(",", ".")
    if not re.fullmatch(r"[0-9]{1,9}(?:\.[0-9]{1,2})?", raw):
        return None
    try:
        amount = Decimal(raw)
    except (InvalidOperation, ValueError):
        return None
    if amount <= 0:
        return None
    normalized = format(amount, "f")
    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".")
    return normalized or "0"


def _normalize_item(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    raw = value.strip()
    parts = raw.split("|")
    if len(parts) not in (4, 5, 6):
        return None
    product_id = _positive_integer(parts[0])
    qty = _positive_integer(parts[1], quantity=True)
    size = parts[2].strip()
    fit = parts[3].strip()
    if not product_id or not qty or not size or not _SIZE_RE.fullmatch(size):
        return None
    if fit and not _FIT_RE.fullmatch(fit):
        return None
    if len(parts) >= 5 and parts[4].strip() and not _positive_integer(parts[4].strip()):
        return None
    if len(parts) == 6 and parts[5].strip():
        for option in parts[5].split(";"):
            if not _OPTION_RE.fullmatch(option.strip()):
                return None
    return raw


def _normalize_show_products(value: object) -> str | None:
    values = value.split(",") if isinstance(value, str) else value
    if not isinstance(values, (list, tuple)):
        return None
    if not values or len(values) > 12:
        return None
    normalized = [_positive_integer(item) for item in values]
    if any(item is None for item in normalized):
        return None
    return ",".join(normalized)


def _normalize_control(kind: object, value: object, *, legacy: bool, has_value: bool) -> ResponseControl | None:
    if not isinstance(kind, str):
        return None
    normalized_kind = kind.lower()
    canonical = _KIND_ALIASES.get(normalized_kind, normalized_kind) if legacy else normalized_kind
    if canonical not in CONTROL_KINDS:
        return None

    if canonical in _BOOLEAN_KINDS:
        if legacy:
            if has_value:
                return None
            return ResponseControl(canonical, True)
        if value is not True:
            return None
        return ResponseControl(canonical, True)
    if canonical == "stage":
        if not isinstance(value, str):
            return None
        stage = value.strip().lower()
        if stage not in _STAGES or stage in _HARD_STAGES:
            return None
        return ResponseControl(canonical, stage)
    if canonical == "paylink":
        if not isinstance(value, str) or value.strip().lower() not in {"full", "prepay"}:
            return None
        return ResponseControl(canonical, value.strip().lower())
    if canonical in {"product", "color_variant_id"}:
        normalized = _positive_integer(value)
        return ResponseControl(canonical, normalized) if normalized else None
    if canonical == "qty":
        normalized = _positive_integer(value, quantity=True)
        return ResponseControl(canonical, normalized) if normalized else None
    if canonical in {"price", "price_quoted", "payment"}:
        normalized = _positive_decimal(value)
        return ResponseControl(canonical, normalized) if normalized else None
    if canonical == "size":
        if not isinstance(value, str) or not _SIZE_RE.fullmatch(value.strip()):
            return None
        return ResponseControl(canonical, value.strip().upper())
    if canonical == "fit":
        if not isinstance(value, str) or not _FIT_RE.fullmatch(value.strip()):
            return None
        return ResponseControl(canonical, value.strip().lower())
    if canonical == "item":
        normalized = _normalize_item(value)
        return ResponseControl(canonical, normalized) if normalized else None
    if canonical == "option":
        if not isinstance(value, str) or not _OPTION_RE.fullmatch(value.strip()):
            return None
        return ResponseControl(canonical, value.strip())
    if canonical == "show_products":
        normalized = _normalize_show_products(value)
        return ResponseControl(canonical, normalized) if normalized else None
    if canonical == "objhandle":
        if not isinstance(value, str):
            return None
        normalized = value.strip().lower()
        return ResponseControl(canonical, normalized) if _OBJHANDLE_RE.fullmatch(normalized) else None
    return None


def _append_control(controls: list[ResponseControl], entry: ResponseControl) -> bool:
    if entry.kind in _REPEATED_KINDS:
        controls.append(entry)
        return True
    for previous in controls:
        if previous.kind == entry.kind:
            # A singleton is an assertion, not an ordered list.  Repeating it
            # is ambiguous even when the values happen to be equal: duplicate
            # model output must fail closed instead of being silently accepted.
            return False
    controls.append(entry)
    return True


def parse_structured_response(payload: object) -> ValidatedResponse:
    """Validate a structured model response without performing side effects."""
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except (TypeError, ValueError, json.JSONDecodeError):
            return _failure("", "invalid_json")
    if not isinstance(payload, dict) or set(payload) != {"reply_text", "controls"}:
        return _failure(payload.get("reply_text", "") if isinstance(payload, dict) else "", "malformed_payload")
    reply_text = payload.get("reply_text")
    controls_payload = payload.get("controls")
    if not isinstance(reply_text, str):
        return _failure("", "invalid_reply_text")
    if not isinstance(controls_payload, list):
        return _failure(reply_text, "malformed_payload")
    if not reply_text.strip() or len(reply_text) > 4000:
        return _failure(reply_text, "invalid_reply_text")
    if len(controls_payload) > 32:
        return _failure(reply_text, "too_many_controls")
    if _ASCII_CONTROL_SHAPED_RE.search(reply_text):
        return _failure(reply_text, "control_token_in_reply_text")

    controls: list[ResponseControl] = []
    for raw in controls_payload:
        if not isinstance(raw, dict) or set(raw) != {"kind", "value"}:
            return _failure(reply_text, "malformed_control")
        entry = _normalize_control(raw.get("kind"), raw.get("value"), legacy=False, has_value=True)
        if entry is None:
            return _failure(reply_text, "invalid_control")
        if not _append_control(controls, entry):
            return _failure(reply_text, "conflicting_control")
    return ValidatedResponse(reply_text=reply_text.strip(), controls=tuple(controls))


def parse_legacy_response(text: object) -> ValidatedResponse:
    """Parse the historical uppercase bracket protocol with fail-closed output."""
    if not isinstance(text, str):
        return _failure("", "malformed_text")
    shaped_tokens = list(_ASCII_CONTROL_SHAPED_RE.finditer(text))
    tokens = list(_ASCII_CLOSED_CONTROL_TOKEN_RE.finditer(text))
    if any(not match.group(0).endswith("]") for match in shaped_tokens):
        return _failure(text, "malformed_token")
    controls: list[ResponseControl] = []
    invalid_reason = ""
    for token in tokens:
        body = token.group(0)[1:-1]
        kind, separator, raw_value = body.partition(":")
        if not _KNOWN_KIND_RE.fullmatch(kind):
            invalid_reason = "unknown_or_case_control"
            continue
        canonical = _KIND_ALIASES.get(kind.lower(), kind.lower())
        has_value = bool(separator)
        value: object = raw_value.strip() if separator else None
        entry = _normalize_control(canonical, value, legacy=True, has_value=has_value)
        if entry is None:
            invalid_reason = invalid_reason or "invalid_control"
            continue
        if not _append_control(controls, entry):
            invalid_reason = invalid_reason or "conflicting_control"
    clean = _clean_text(text)
    if invalid_reason:
        return ValidatedResponse(reply_text=clean, valid=False, error=invalid_reason)
    return ValidatedResponse(reply_text=clean, controls=tuple(controls))


# Names useful to callers during migration from the old tuple parser.
validate_structured_response = parse_structured_response
parse_model_response = parse_structured_response
parse_legacy_tags = parse_legacy_response


__all__ = [
    "CONTROL_KINDS",
    "ResponseControl",
    "STRUCTURED_RESPONSE_SCHEMA",
    "ValidatedResponse",
    "parse_legacy_response",
    "parse_legacy_tags",
    "parse_model_response",
    "parse_structured_response",
    "structured_response_schema",
    "validate_structured_response",
]
