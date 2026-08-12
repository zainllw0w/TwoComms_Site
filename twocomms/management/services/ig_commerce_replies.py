"""Safe, deterministic text payloads for the durable commerce outbox."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from management.services.ig_commerce_types import CommerceTurnRequest


_CLARIFICATIONS = {
    "multiple_product_links": (
        "Бачу кілька товарів. Надішліть, будь ласка, одне посилання на потрібний варіант."
    ),
    "which_product": (
        "Уточніть, будь ласка, який саме товар ви маєте на увазі, або надішліть посилання на нього."
    ),
    "print_placement": (
        "Уточніть, будь ласка, де саме має бути без принта: спереду, на спині чи всюди."
    ),
    "new_purchase_or_exchange": (
        "Уточніть, будь ласка, це нове замовлення чи обмін уже отриманого товару."
    ),
}


def _payload(text: str) -> dict:
    return {"text": [text]}


def build_durable_reply_payload(
    request: CommerceTurnRequest,
    *,
    action: str,
    reasons: Sequence[str],
    before: Mapping,
    after: Mapping,
) -> dict:
    """Return a persistable single-chunk reply for a safe commerce outcome.

    This layer must stay independent from mutable catalog, price, availability,
    payment, and staffing data. More expressive candidate and checkout replies
    are delivered by later W9 stages only after their facts are authoritative.
    """
    del before  # The interface deliberately keeps a deterministic state snapshot.
    reason_set = {str(reason) for reason in reasons}
    if action == "candidate_rejected" and "candidate_prompt_mismatch" in reason_set:
        return _payload(
            "Ця добірка вже неактуальна. Виберіть варіант з останнього повідомлення "
            "або надішліть посилання на товар."
        )
    if action == "clarification_requested":
        clarification = str(
            after.get("pending_clarification") or request.pending_clarification or ""
        )
        text = _CLARIFICATIONS.get(clarification)
        if text:
            return _payload(text)
    if action == "product_selected" and request.exact_product_id:
        return _payload(
            "Зафіксувала цей варіант. Підкажіть, будь ласка, розмір, колір і кількість."
        )
    return {}
