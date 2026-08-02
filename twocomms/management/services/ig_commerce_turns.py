"""Bounded multilingual turn parsing for the commerce state reducer."""

from __future__ import annotations

import re

from .ig_commerce_types import CommerceTurnRequest, ReferenceSource
from .ig_product_references import resolve_product_reference


_COLOR_WORDS = {
    "black": "black", "черн": "black", "чорн": "black",
    "white": "white", "бел": "white", "бі"
    "лий": "white", "син": "blue", "blue": "blue",
    "pink": "pink", "розов": "pink", "рожев": "pink",
    "grey": "grey", "gray": "grey", "сер": "grey", "сір": "grey",
    "green": "green", "зелен": "green", "зелен": "green",
}
_FIT_WORDS = {
    "classic": "classic", "классик": "classic", "класик": "classic",
    "класич": "classic", "standard": "classic", "стандарт": "classic",
    "regular": "classic", "oversize": "oversize", "oversized": "oversize",
    "оверсайз": "oversize", "оверсайз": "oversize",
}
_SIZE_RE = re.compile(r"\b(?:xxxs|xxl|xxxl|2xl|3xl|4xl|5xl|xs|s|m|l|xl)\b", re.I)


def _find_prefix_value(text: str, words: dict[str, str]) -> str:
    lowered = text.casefold()
    for needle, value in words.items():
        if needle in lowered:
            return value
    return ""


def _is_negated_url(text: str, url: str) -> bool:
    before = text[: text.find(url)].casefold()
    return bool(re.search(r"(?:не|не хочу|не нужен|not|don't want)\s*$", before[-32:]))


def _parse_model_payload(payload) -> dict:
    if not isinstance(payload, dict):
        return {}
    allowed = {"color", "fit", "size", "garment_type", "checkout_requested"}
    result = {}
    for key in allowed:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            result[key] = value.strip()
        elif key == "checkout_requested" and isinstance(value, bool):
            result[key] = value
    return result


def parse_turn(text: str | None, *, media_evidence=None) -> CommerceTurnRequest:
    raw = str(text or "").strip()
    lowered = raw.casefold()
    urls = re.findall(r"https?://[^\s<>]+", raw)
    rejected_ids: list[int] = []
    exact_urls = []
    for url in urls:
        if _is_negated_url(raw, url):
            reference = resolve_product_reference(url, media_evidence=media_evidence)
            if reference.product_id:
                rejected_ids.append(reference.product_id)
        else:
            exact_urls.append(url)

    reference = resolve_product_reference(" ".join(exact_urls), media_evidence=media_evidence) if exact_urls else None
    pending = ""
    exact_product_id = None
    if len(exact_urls) > 1:
        exact_product_ids = {
            item.product_id
            for item in (
                resolve_product_reference(url, media_evidence=media_evidence)
                for url in exact_urls
            )
            if item.is_exact and item.product_id
        }
        if len(exact_product_ids) > 1:
            pending = "multiple_product_links"
    elif reference and reference.is_exact:
        exact_product_id = reference.product_id

    field_updates: dict[str, str] = {}
    color = _find_prefix_value(raw, _COLOR_WORDS)
    fit = _find_prefix_value(raw, _FIT_WORDS)
    size_match = _SIZE_RE.search(raw)
    if color:
        field_updates["color"] = color
    if fit:
        field_updates["fit"] = fit
    if size_match and not re.search(r"(?:розмірн\w*|размерн\w*|size\s+guide)", lowered):
        field_updates["size"] = size_match.group(0).upper()

    hard: dict[str, str] = {}
    if re.search(r"логотип\s+(?:спереди|спереду|на\s+груд|front)|logo\s+front", lowered):
        hard["front_decoration"] = "logo"
    if re.search(r"(?:без|without|no)\s+(?:принта|print)\s+(?:сзади|сзаду|на\s+спин|back)", lowered):
        hard["back_decoration"] = "none"
    if re.search(r"(?:без|without|no)\s+(?:принта|print)\b", lowered) and not hard:
        pending = pending or "print_placement"

    info_topics: list[str] = []
    if re.search(r"(?:размерн\w*\s+сетк|сітк\w*\s+розмір|size\s+guide|size\s+chart)", lowered):
        guide_fit = fit or ("oversize" if "оверсайз" in lowered or "oversize" in lowered else "")
        info_topics.append(f"size_guide:{guide_fit}" if guide_fit else "size_guide")
        field_updates.pop("fit", None)

    checkout_requested = bool(re.search(
        r"(?:оплатить|оплатить|оформить|оформлюємо|оформити|pay|checkout|payment)",
        lowered,
    ))
    reset_requested = bool(re.search(
        r"(?:друг(?:ой|ую|ую)|інш(?:ий|у)|another|different|сменить|заміни|replace)",
        lowered,
    ))
    new_purchase_requested = bool(re.search(r"(?:еще\s+одну|ще\s+одну|another\s+one|new\s+order)", lowered))
    exchange_requested = bool(re.search(r"(?:поменять|обмен|обмін|exchange|change\s+size)", lowered))
    if reset_requested and not new_purchase_requested and not exchange_requested and not exact_product_id:
        pending = pending or "new_purchase_or_exchange"

    return CommerceTurnRequest(
        exact_product_id=exact_product_id,
        exact_unique_alias=False,
        field_updates=field_updates,
        hard=hard,
        semantic_constraints=hard,
        exact_reference=reference,
        rejected_product_ids=tuple(sorted(set(rejected_ids))),
        pending_clarification=pending,
        info_topics=tuple(info_topics),
        checkout_requested=checkout_requested,
        reset_requested=reset_requested,
        support_requested=bool(re.search(r"(?:помог|вопрос|support|help)", lowered)),
        new_purchase_requested=new_purchase_requested,
        exchange_requested=exchange_requested,
    )


def understand_turn(text: str | None, *, model_payload=None, media_evidence=None) -> CommerceTurnRequest:
    """Use model fields only as bounded hints; never accept model product IDs."""
    deterministic = parse_turn(text, media_evidence=media_evidence)
    model = _parse_model_payload(model_payload)
    if model_payload is not None and not model:
        return CommerceTurnRequest(pending_clarification="which_product")
    updates = dict(deterministic.field_updates)
    for key in ("color", "fit", "size", "garment_type"):
        if key not in updates and key in model:
            updates[key] = model[key]
    return CommerceTurnRequest(
        **{
            **deterministic.__dict__,
            "field_updates": updates,
            "checkout_requested": deterministic.checkout_requested or bool(model.get("checkout_requested")),
        }
    )
