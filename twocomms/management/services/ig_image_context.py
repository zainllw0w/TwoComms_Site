"""Provider-safe contextual image instructions for the existing live request."""
from __future__ import annotations

import json
from collections.abc import Mapping, Sequence

from management.services.ig_media_manifest import IMAGE_TYPE_CODES


_PROVISIONAL_ROLES = frozenset({
    "receipt", "payment_candidate", "product", "custom_reference", "other",
    "manager_reference",
})
_PROVISIONAL_INTENTS = frozenset({
    "payment_evidence", "purchase_candidate", "custom_print_request", "question",
    "interest", "unknown", "manager_reference",
})


def _bounded_index(value, fallback: int) -> int:
    if isinstance(value, bool):
        return fallback
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return parsed if 0 <= parsed <= 10_000 else fallback


def _safe_code(value: object, allowed: frozenset[str], default: str) -> str:
    code = str(value or "").strip().casefold()
    return code if code in allowed else default


def _hint_for_part(
    part: Mapping[str, object],
    hints: Sequence[Mapping[str, object]],
    position: int,
) -> Mapping[str, object]:
    source_part_id = str(part.get("source_part_id") or "")
    if source_part_id:
        matches = [
            hint for hint in hints
            if str(hint.get("source_part_id") or "") == source_part_id
        ]
        if len(matches) == 1:
            return matches[0]
    original_index = _bounded_index(part.get("original_index"), position)
    matches = [
        hint for hint in hints
        if _bounded_index(hint.get("original_index"), -1) == original_index
    ]
    return matches[0] if len(matches) == 1 else {}


def build_contextual_image_note(
    submitted_parts: Sequence[Mapping[str, object]] | None,
    provisional_media: Sequence[Mapping[str, object]] | None = None,
) -> str:
    """Describe submitted image indexes without exposing local identities or hashes."""
    hints = [item for item in (provisional_media or ()) if isinstance(item, Mapping)]
    rows = []
    for inline_index, part in enumerate(submitted_parts or ()):
        if not isinstance(part, Mapping):
            continue
        mime = str(part.get("mime") or "").strip().casefold()
        if not mime.startswith("image/"):
            continue
        hint = _hint_for_part(part, hints, inline_index)
        rows.append({
            "source_image_index": inline_index,
            "original_index": _bounded_index(part.get("original_index"), inline_index),
            "provisional_role": _safe_code(
                hint.get("role"), _PROVISIONAL_ROLES, "other"
            ),
            "provisional_intent": _safe_code(
                hint.get("intent"), _PROVISIONAL_INTENTS, "unknown"
            ),
        })
    if not rows:
        return ""
    return (
        "[CONTEXTUAL IMAGE UNDERSTANDING]\n"
        + json.dumps({"submitted_images": rows}, ensure_ascii=True, separators=(",", ":"))
        + "\nInspect every submitted image together with the current caption and conversation. "
        "Provisional role and intent are hints only; visible content may correct them. "
        "Return exactly one image_observations item for each listed source_image_index, "
        "using a finite type_code from: "
        + ",".join(sorted(IMAGE_TYPE_CODES))
        + ". Respond to the customer's purpose for each understood image. Do not claim "
        "that omitted or unavailable parts were inspected. Read only the visible detail "
        "needed for the customer's question; do not reproduce full payment details, "
        "document numbers, or QR contents. A receipt or payment screenshot is evidence, "
        "not verified payment. A certificate is visible content, not verified entitlement. "
        "Escalate only for an actual unreadable part, unresolved ambiguity, or a separate "
        "business-authority decision."
    )


__all__ = ["build_contextual_image_note"]
