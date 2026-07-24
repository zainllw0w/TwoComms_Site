"""Evidence-bound manual payment review for Instagram conversations."""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
import hashlib
import json

from django.conf import settings
from django.db import transaction
from django.utils import timezone


_PAYMENT_EVIDENCE_RE = re.compile(
    r"(?:\bоплат\w*\b|\bпередоплат\w*\b|\bплатіж\w*\b|\bплатеж\w*\b|"
    r"\bоплач\w*\b|\bсплач\w*\b|\bпереказ\w*\b|\bперевод\w*\b|\bоплатила\b|"
    r"\bоплатив\b|\bчек(?:а|у|ом)?\b|\bквитанц\w*\b|\breceipt\b|\bpaid\b)",
    re.IGNORECASE,
)
_NON_EVIDENCE_RE = re.compile(
    r"(?:посилання|ссылка|лінк|линк|як оплатити|как оплатить|оплата доступна|payment link)",
    re.IGNORECASE,
)
_AFFIRMATION_RE = re.compile(
    r"(?:я\s+(?:вже\s+)?оплат\w*|(?:оплат\w*|сплач\w*|переказ\w*|перевод\w*)\s+"
    r"(?:вже\s+)?(?:зроб\w*|викон\w*|готов\w*)|\bчек(?:а|у|ом)?\b|"
    r"\bквитанц\w*\b|receipt|paid)",
    re.IGNORECASE,
)
_AMOUNT_RE = re.compile(r"(?<!\d)(\d{2,6}(?:[.,]\d{1,2})?)\s*(?:грн|uah|₴)", re.IGNORECASE)
_FIT_RE = re.compile(
    r"(?P<fit>базов\w*|класич\w*|classic|basic|оверсайз\w*|oversize)"
    r"(?:\s+(?:розмір|size))?\s*(?P<size>2xl|xxl|xl|l|m|s|xs|2xs)\b",
    re.IGNORECASE,
)
_QTY_RE = re.compile(r"\b(\d+)\s+(?:футбол\w*|шт\.?|штук\w*)\b", re.IGNORECASE)
_CUSTOMER_ROLES = {"user", "customer", "client"}
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?380|0)\d{9}(?!\d)")
_OFFICE_RE = re.compile(r"(?P<kind>поштомат|відділен\w*|відд\.?|office)\s*№?\s*(?P<number>\d{1,8})", re.IGNORECASE)
_NAME_STOPWORDS = {
    "в різні",
    "по повній передоплаті",
    "по повній оплаті",
    "потрібна оплата",
}

_MEDIA_PRODUCT_RE = re.compile(
    r"\b(товар\w*|футболк\w*|худі|худи|одяг\w*|одежд\w*|модель\w*|"
    r"розмір\w*|размер\w*|колір\w*|цвет\w*|ціна\w*|цена\w*|"
    r"наявн\w*|налич\w*|хочу|беру|давайте|замовл\w*|заказ\w*|куп\w*)\b",
    re.IGNORECASE,
)
_MEDIA_PURCHASE_RE = re.compile(
    r"\b(хочу|беру|забираю|оформл\w*|замовл\w*|заказ\w*|купл\w*|куп\w*|"
    r"давайте|підтверджую|подтверждаю)\b",
    re.IGNORECASE,
)
_MEDIA_CUSTOM_RE = re.compile(
    r"\b(кастом\w*|custom|dtf|дтф|принт\w*|друк\w*|печать\w*)\b",
    re.IGNORECASE,
)
_CUSTOMER_PAYMENT_COMMITMENT_RE = re.compile(
    r"\b(?:по\s+)?повн\w*\s+(?:перед)?оплат\w*\b|"
    r"\b(?:обираю|вибираю|выбираю)\s+(?:повн\w*\s+)?(?:перед)?оплат\w*\b",
    re.IGNORECASE,
)
_PRICE_ACCEPTANCE_RE = re.compile(
    r"\b(так|да|ок|добре|хорошо|домов\w*|погодж\w*|соглас\w*|оформл\w*|"
    r"замовл\w*|заказ\w*|беру|забираю)\b",
    re.IGNORECASE,
)


def _amount_evidence_kind(text: str) -> str:
    low = " ".join(str(text or "").split()).casefold()
    if re.search(
        r"\b(передоплат\w*|аванс\w*|оплатив\w*|оплатила\w*|оплачено\w*|"
        r"сплатив\w*|сплатила\w*|сплачено\w*|чек\w*|квитанц\w*|receipt|paid)\b",
        low,
    ) or re.search(
        r"\b(переказ\w*|перевод\w*)\b.{0,24}\b(зроб\w*|викон\w*|готов\w*)\b",
        low,
    ):
        return "payment_evidence"
    if re.search(r"\b(сума|сумма|разом|итого|всього|всего|total)\b", low):
        return "order_total"
    if re.search(r"\b(ціна|цена|вартість|стоимость)\b", low) or re.search(
        r"\bза\s+\d{2,6}(?:[.,]\d{1,2})?\s*(?:грн|uah|₴)", low
    ):
        return "unit_price"
    return "unknown"

_PRODUCT_MEDIA_TYPES = {"ig_post", "share", "ig_reel", "reel", "story_mention", "story"}


def _raw_media_by_mid(client) -> dict[str, list[dict]]:
    """Recover media that Meta kept only in the raw webhook event.

    Instagram sometimes sends an ``ig_post`` in a separate event with the same
    message id while the normalized message row has an empty ``attachments``
    field. Raw events are the source evidence; this helper only reads them.
    """
    if not client or not getattr(client, "igsid", ""):
        return {}
    try:
        from management.models import InstagramBotRawEvent
        from management.services.instagram_bot import _iter_events
    except Exception:
        return {}
    recovered: dict[str, list[dict]] = {}
    rows = InstagramBotRawEvent.objects.filter(sender_id=client.igsid).order_by("-id")[:240]
    for event in rows:
        try:
            payload = json.loads(event.payload or "{}")
        except (TypeError, ValueError):
            continue
        try:
            events = _iter_events(payload)
            for sender_id, _recipient_id, message, _referral in events:
                if sender_id != client.igsid:
                    continue
                mid = str(message.get("mid") or "").strip()
                if not mid:
                    continue
                for attachment in message.get("attachments") or []:
                    if not isinstance(attachment, dict):
                        continue
                    payload_data = attachment.get("payload")
                    if not isinstance(payload_data, dict):
                        continue
                    url = str(payload_data.get("url") or "").strip()
                    if not url or not url.startswith(("https://", "http://")):
                        continue
                    item = {
                        "url": url[:1200],
                        "type": str(attachment.get("type") or "image")[:32],
                        "title": str(payload_data.get("title") or "")[:700],
                        "ig_post_media_id": str(payload_data.get("ig_post_media_id") or "")[:80],
                        "raw_event_id": event.pk,
                    }
                    event_at = message.get("_event_created_at")
                    if event_at is not None:
                        item["event_at"] = event_at.isoformat() if hasattr(event_at, "isoformat") else str(event_at)
                    existing = recovered.setdefault(mid, [])
                    if not any(row.get("url") == item["url"] for row in existing):
                        existing.append(item)
        except Exception:
            continue
    # Keep media whose provider mid has no normalized row available for the
    # timestamp-based fallback in _augment_messages_with_raw_media.
    known_mids = set()
    try:
        from management.models import InstagramBotMessage
        known_mids = set(
            InstagramBotMessage.objects.filter(client=client).exclude(mid__isnull=True).values_list("mid", flat=True)
        )
    except Exception:
        pass
    unmatched = []
    for mid, items in list(recovered.items()):
        if mid not in known_mids:
            unmatched.extend(items)
    if unmatched:
        recovered["__unmatched__"] = unmatched
    return recovered


def _existing_media(raw_attachments: str) -> list[dict]:
    try:
        urls = json.loads(raw_attachments or "[]")
    except (TypeError, ValueError):
        urls = []
    if not isinstance(urls, list):
        urls = []
        for candidate in re.findall(r"https?://[^\s\"'\]]+", raw_attachments or ""):
            urls.append(candidate)
    return [
        {"url": str(url)[:1200], "type": "image", "title": "", "raw_event_id": None}
        for url in urls
        if isinstance(url, str) and url.startswith(("https://", "http://"))
    ]


def _media_intent(text: str, *, payment_context: bool, explicit_claim: bool) -> str:
    low = " ".join(str(text or "").split()).casefold()
    if explicit_claim:
        return "payment_evidence"
    if _MEDIA_CUSTOM_RE.search(low) and (
        re.search(
            r"(можн\w*|можете|можна|зроб\w*|сдел\w*|виготов\w*|нанес\w*|надрук\w*)",
            low,
        )
        or _MEDIA_PURCHASE_RE.search(low)
    ):
        return "custom_print_request"
    if _MEDIA_PURCHASE_RE.search(low):
        return "purchase_candidate"
    if _MEDIA_PRODUCT_RE.search(low):
        return "question" if re.search(
            r"(який|яка|яке|какой|какая|скільки|сколько|чи є|есть ли|можна|можно|розмір|размер|ціна|цена)",
            low,
        ) else "interest"
    if payment_context:
        return "payment_evidence"
    return "unknown"


def classify_media_items(
    text: str,
    media: list[dict] | None,
    *,
    payment_context: bool = False,
    explicit_claim: bool | None = None,
) -> list[dict]:
    """Attach conservative role/intent semantics to current-turn media.

    This is deliberately deterministic. Gemini may enrich a product match, but
    receipts are never sent to catalog matching and unknown images remain
    reviewable instead of becoming invented products.
    """
    normalized_text = " ".join(str(text or "").split())
    if explicit_claim is None:
        explicit_claim = bool(_AFFIRMATION_RE.search(normalized_text)) and not _NON_EVIDENCE_RE.search(normalized_text)
    intent = _media_intent(
        normalized_text,
        payment_context=payment_context,
        explicit_claim=bool(explicit_claim),
    )
    result = []
    for raw in media or []:
        if not isinstance(raw, dict) or not raw.get("url"):
            continue
        item = dict(raw)
        media_type = str(item.get("type") or "image").casefold()
        if media_type in _PRODUCT_MEDIA_TYPES:
            # Meta's explicit post/share type is stronger than surrounding
            # payment text: a product post accompanying a receipt is still a
            # product reference, while the generic image is the receipt.
            role = "product"
            item_intent = "purchase_candidate" if intent == "purchase_candidate" else "interest"
        elif intent == "payment_evidence":
            role = "receipt" if explicit_claim else "payment_candidate"
            item_intent = intent
        elif intent == "custom_print_request":
            role = "custom_reference"
            item_intent = intent
        elif intent in {"question", "interest", "purchase_candidate"}:
            role = "product"
            item_intent = intent
        else:
            role = "other"
            item_intent = intent
        item.update({
            "role": role,
            "intent": item_intent,
            "actionable": item_intent == "purchase_candidate" and role == "product",
            "payment_evidence": role in {"receipt", "payment_candidate"},
            "catalog_match_allowed": role == "product",
            "uncertain": role in {"other", "custom_reference", "payment_candidate"} or item_intent in {"unknown", "question", "interest"},
        })
        result.append(item)
    return result


def _role_for_media(
    item: dict,
    *,
    payment_context: bool,
    explicit_claim: bool,
    text: str = "",
) -> str:
    """Return the durable media role used by the payment-review audit."""
    classified = classify_media_items(
        text,
        [item],
        payment_context=payment_context,
        explicit_claim=explicit_claim,
    )
    return classified[0]["role"] if classified else "other"


def _augment_messages_with_raw_media(client, messages) -> list[dict]:
    raw_by_mid = _raw_media_by_mid(client)
    result = []
    for raw in list(messages or ()):
        if not isinstance(raw, dict):
            continue
        item = dict(raw)
        media = list(item.get("media") or []) if isinstance(item.get("media"), list) else []
        media.extend(_existing_media(str(item.get("attachments") or "")))
        mid = str(item.get("mid") or "").strip()
        for attachment in raw_by_mid.get(mid, []):
            if not any(row.get("url") == attachment.get("url") for row in media):
                media.append(attachment)
        # Keep the old attachments contract intact for callers that only know
        # how to consume a JSON list of URLs, while exposing structured media
        # evidence to the review UI and catalog matcher.
        item["media"] = media[:8]
        if media and not item.get("attachments"):
            item["attachments"] = json.dumps(
                [row["url"] for row in media if row.get("url")], ensure_ascii=False
            )
        result.append(item)
    unmatched = list(raw_by_mid.get("__unmatched__") or [])
    if unmatched and result:
        # Meta may emit the attachment as a follow-up event with a different
        # mid. Prefer an explicit "Принт …" message; otherwise use the first
        # normalized user message created after the provider event timestamp.
        for attachment in unmatched:
            target = next(
                (
                    row for row in result
                    if str(row.get("role") or "").casefold() in {"user", "customer", "client"}
                    and "принт" in str(row.get("text") or "").casefold()
                ),
                None,
            )
            event_at = str(attachment.get("event_at") or "")
            if target is None and event_at:
                target = next(
                    (
                        row for row in result
                        if str(row.get("role") or "").casefold() in {"user", "customer", "client"}
                        and str(row.get("created_at") or "") >= event_at
                    ),
                    None,
                )
            if target is None:
                target = next((row for row in result if row.get("role") == "user"), None)
            if target is not None:
                target.setdefault("media", [])
                if not any(row.get("url") == attachment.get("url") for row in target["media"]):
                    target["media"].append(attachment)
                target["media"] = target["media"][:8]
                if not target.get("attachments"):
                    target["attachments"] = json.dumps(
                        [row["url"] for row in target["media"] if row.get("url")], ensure_ascii=False
                    )
    return result


def _persist_review_media(media: list[dict]) -> list[dict]:
    """Download bounded image evidence to our media storage for durable review.

    Signed Meta URLs can expire; ``local_url`` is best effort and the original
    URL remains in evidence for audit. Non-image or failed downloads are never
    sent into catalog matching.
    """
    try:
        from django.core.files.base import ContentFile
        from django.core.files.storage import default_storage
        from management.services.instagram_bot import download_image
    except Exception:
        return media
    enriched = []
    for item in media[:8]:
        row = dict(item)
        url = str(row.get("url") or "")
        if not url:
            enriched.append(row)
            continue
        try:
            downloaded = download_image(url)
            if downloaded:
                mime, raw = downloaded
                suffix = ".jpg" if mime == "image/jpeg" else ".bin"
                digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
                path = f"ig_payment_reviews/{digest}{suffix}"
                if not default_storage.exists(path):
                    default_storage.save(path, ContentFile(raw))
                row["local_url"] = default_storage.url(path)
                row["mime"] = mime[:64]
                row["bytes"] = len(raw)
        except Exception:
            pass
        enriched.append(row)
    return enriched


def _resolve_payment_media_candidates(media: list[dict]) -> list[dict]:
    """Use bounded vision only for images whose receipt role is contextual."""
    result = [dict(item) for item in (media or []) if isinstance(item, dict)]
    candidate_indexes = [
        index for index, item in enumerate(result)
        if item.get("role") == "payment_candidate" and item.get("url")
    ]
    if not candidate_indexes:
        return result
    try:
        from management.services.instagram_bot import download_image
        from management.services import bot_vision

        images = []
        source_indexes = []
        for source_index in candidate_indexes[:8]:
            image = download_image(str(result[source_index].get("url") or ""))
            if image:
                images.append(image)
                source_indexes.append(source_index)
        matches = bot_vision.classify_media_roles(images) if images else []
    except Exception:
        return result
    for match in matches:
        try:
            image_index = int(match.get("source_image_index"))
            confidence = float(match.get("confidence") or 0)
            source_index = source_indexes[image_index]
        except (IndexError, TypeError, ValueError):
            continue
        if confidence < 0.75:
            result[source_index]["uncertain"] = True
            continue
        role = str(match.get("role") or "other")
        semantics = {
            "receipt": ("payment_evidence", True, False, False),
            "product": ("interest", False, False, True),
            "custom_reference": ("custom_print_request", False, False, True),
            "other": ("unknown", False, False, True),
        }.get(role)
        if semantics is None:
            continue
        intent, payment_evidence, catalog_match_allowed, uncertain = semantics
        result[source_index].update({
            "role": role,
            "intent": intent,
            "actionable": False,
            "payment_evidence": payment_evidence,
            "catalog_match_allowed": catalog_match_allowed,
            "uncertain": uncertain,
            "vision_role": role,
            "vision_confidence": confidence,
            "vision_reason": str(match.get("reason") or "")[:300],
        })
    return result


def _reconcile_payment_evidence_after_media_resolution(extracted: dict, media: list[dict]) -> dict:
    """Rebuild payment evidence after vision has resolved provisional images.

    A contextual ``payment_candidate`` is not proof by itself. Once vision says
    that the image is a product/custom/reference/other image, it must leave the
    financial workflow unless the same customer message contains an explicit
    payment statement.
    """
    if not isinstance(extracted, dict):
        return extracted
    resolved = [item for item in (media or []) if isinstance(item, dict)]
    roles_by_message: dict[int, set[str]] = {}
    for item in resolved:
        try:
            message_id = int(item.get("message_id") or 0)
        except (TypeError, ValueError):
            message_id = 0
        if message_id:
            roles_by_message.setdefault(message_id, set()).add(str(item.get("role") or "other"))
    kept = []
    for entry in extracted.get("evidence") or []:
        if not isinstance(entry, dict):
            continue
        try:
            message_id = int(entry.get("message_id") or 0)
        except (TypeError, ValueError):
            message_id = 0
        quote = str(entry.get("quote") or "")
        explicit_statement = bool(_AFFIRMATION_RE.search(quote) and not _NON_EVIDENCE_RE.search(quote))
        payment_role = bool(roles_by_message.get(message_id, set()).intersection({"receipt", "payment_candidate"}))
        if explicit_statement or payment_role:
            kept.append(entry)
    extracted["evidence"] = kept[-20:]
    extracted["message_ids"] = [entry.get("message_id") for entry in kept if entry.get("message_id")]
    extracted["needs_review"] = bool(kept)
    return extracted


def _is_review_deal_compatible(deal, product_ids: set[int] | None = None) -> bool:
    """Allow only the current unpaid/open deal for the matched product set."""
    if not deal:
        return False
    if getattr(deal, "order_id", None):
        return False
    if str(getattr(deal, "status", "") or "") not in {"draft", "quoted", "awaiting_payment"}:
        return False
    if str(getattr(deal, "payment_truth", "") or "") not in {"", "unverified", "pending"}:
        return False
    if str(getattr(deal, "payment_status", "") or "") in {"paid", "prepaid", "confirmed"}:
        return False
    wanted = {int(value) for value in (product_ids or set()) if str(value).isdigit()}
    if not wanted:
        return False
    known = getattr(deal, "product_ids", None)
    if known is None:
        try:
            known = set(deal.items.values_list("product_id", flat=True))
        except Exception:
            known = set()
    return bool(known) and set(known) == wanted


def _select_review_deal(client, catalog_matches: list[dict]):
    """Select a same-product open deal; never fall back to latest historical deal."""
    product_ids = {
        int(match.get("product_id"))
        for match in (catalog_matches or [])
        if isinstance(match, dict) and str(match.get("product_id") or "").isdigit()
    }
    if not client or not product_ids:
        return None
    try:
        candidates = client.deals.order_by("-id")[:20]
        for deal in candidates:
            if _is_review_deal_compatible(deal, product_ids):
                return deal
    except Exception:
        return None
    return None


def _apply_validated_conversation_price_to_draft(draft: dict, messages, catalog_matches: list[dict]) -> dict:
    """Apply only a human-authorized, product-bound price to a review draft."""
    if not isinstance(draft, dict):
        return draft
    items = draft.get("items") if isinstance(draft.get("items"), list) else []
    matches = [match for match in (catalog_matches or []) if isinstance(match, dict) and match.get("status") == "matched"]
    product = None
    if len(matches) == 1:
        product = type("ReviewProduct", (), {
            "pk": matches[0].get("product_id"),
            "title": matches[0].get("title") or "",
            "slug": matches[0].get("slug") or "",
        })()
    from management.services.bot_orders import _conversation_price_evidence, _message_role

    decision = _conversation_price_evidence(list(messages or ()), qty=int(items[0].get("qty") or 1) if len(items) == 1 else 1, product=product)
    if decision.get("status") == "accepted" and decision.get("price") is not None and len(items) == 1 and product:
        price = Decimal(str(decision["price"])).quantize(Decimal("0.01"))
        items[0]["unit_price"] = str(price)
        draft["quoted_total"] = str(price * Decimal(str(items[0].get("qty") or 1))).rstrip("0").rstrip(".")
        draft["amount_source_message_id"] = decision.get("source_message_id")
        return draft
    commercial_amount_seen = False
    manager_amount_accepted = False
    rows = list(messages or ())
    for index, message in enumerate(rows):
        text = message.get("text") if isinstance(message, dict) else getattr(message, "text", "")
        role = _message_role(message)
        if _AMOUNT_RE.search(str(text or "")) and _amount_evidence_kind(str(text or "")) in {"order_total", "unit_price"}:
            commercial_amount_seen = True
            next_message = rows[index + 1] if index + 1 < len(rows) else None
            next_role = _message_role(next_message) if next_message is not None else ""
            next_text = next_message.get("text") if isinstance(next_message, dict) else getattr(next_message, "text", "") if next_message is not None else ""
            if role == "manager" and next_role in {"user", "customer", "client"} and _PRICE_ACCEPTANCE_RE.search(str(next_text or "")):
                manager_amount_accepted = True
    if commercial_amount_seen and not (manager_amount_accepted and len(items) > 1):
        draft["quoted_total"] = ""
        for item in items:
            item["unit_price"] = None
        reasons = list(draft.get("uncertainty_reasons") or [])
        if "conversation_price_not_authorized" not in reasons:
            reasons.append("conversation_price_not_authorized")
        draft["uncertainty_reasons"] = reasons
    return draft


def _hydrate_catalog_match(match: dict, source_rows: list[dict], source_indexes: list[int]) -> dict:
    product_id = match.get("product_id")
    selected_rows = [source_rows[index] for index in source_indexes if 0 <= index < len(source_rows)]
    result = {
        "status": "matched" if product_id else "unresolved",
        "product_id": product_id,
        "confidence": match.get("confidence", 0),
        "reason": match.get("reason", ""),
        "source_media_indexes": source_indexes,
        "source_message_ids": sorted({
            int(row.get("message_id"))
            for row in selected_rows
            if str(row.get("message_id") or "").isdigit()
        }),
    }
    if not product_id:
        return result
    try:
        from storefront.models import Product
        from productcolors.models import ProductColorVariant

        product = Product.objects.filter(pk=product_id).first()
        if not product:
            result.update({"status": "unresolved", "product_id": None, "reason": "catalog_product_missing"})
            return result
        result.update({
            "title": product.title,
            "slug": product.slug,
            "catalog_price": str(getattr(product, "final_price", None) or product.price),
            "url": f"https://twocomms.shop/product/{product.slug}/",
        })
        variants = []
        for variant in ProductColorVariant.objects.filter(product=product).select_related("color")[:20]:
            variants.append({
                "id": variant.pk,
                "color": getattr(variant.color, "name", "") or "",
                "sku": variant.sku or "",
            })
        result["variant_candidates"] = variants
        if len(variants) == 1:
            result["color_variant_id"] = variants[0]["id"]
    except Exception:
        result.update({"status": "error", "reason": "catalog_hydration_failed"})
    return result


def _catalog_order_media(media: list[dict]) -> list[dict]:
    """Return only images carrying an explicit purchase commitment."""
    return [
        row for row in (media or [])
        if isinstance(row, dict)
        and row.get("url")
        and row.get("role") == "product"
        and row.get("intent") == "purchase_candidate"
        and row.get("actionable") is True
        and row.get("catalog_match_allowed") is True
    ]


def _catalog_matches_for_media(media: list[dict]) -> list[dict]:
    product_media = _catalog_order_media(media)
    if not product_media:
        return []
    try:
        from management.services.instagram_bot import download_image
        from management.services import bot_vision

        images = []
        downloaded_indexes = []
        for index, row in enumerate(product_media[:8]):
            image = download_image(str(row["url"]))
            if image:
                images.append(image)
                downloaded_indexes.append(index)
        raw_matches = bot_vision.match_many(images) if images else []
    except Exception as exc:
        return [{"status": "error", "reason": str(exc)[:180], "source_media_indexes": []}]
    if not raw_matches:
        reason = "image_download_failed" if not images else "catalog_match_unresolved"
        return [_hydrate_catalog_match(
            {"product_id": None, "confidence": 0, "reason": reason},
            product_media,
            list(range(len(product_media[:8]))),
        )]
    results = []
    for match in raw_matches:
        image_indexes = match.get("source_image_indexes") or list(range(len(images)))
        source_indexes = sorted({
            downloaded_indexes[index]
            for index in image_indexes
            if 0 <= index < len(downloaded_indexes)
        })
        result = _hydrate_catalog_match(match, product_media, source_indexes)
        results.append(result)
        if result.get("status") == "matched":
            for source_index in source_indexes:
                product_media[source_index].setdefault("catalog_matches", []).append({
                    key: result.get(key)
                    for key in ("product_id", "title", "url", "confidence")
                    if result.get(key) not in (None, "")
                })
    return results


def _catalog_match_for_media(media: list[dict]) -> dict:
    """Compatibility accessor for callers that only understand one match."""
    matches = _catalog_matches_for_media(media)
    return matches[0] if matches else {}


def _apply_catalog_matches_to_draft(draft: dict, matches: list[dict]) -> None:
    """Bind validated catalog matches to draft lines without collapsing SKUs."""
    if not isinstance(draft, dict):
        return
    items = [item for item in (draft.get("items") or []) if isinstance(item, dict)]
    confirmed = [
        match for match in (matches or [])
        if isinstance(match, dict) and match.get("status") == "matched" and match.get("product_id")
    ]
    if not confirmed:
        return

    def bind(item, match):
        item["product_id"] = match.get("product_id")
        item["color_variant_id"] = match.get("color_variant_id")
        item["catalog"] = {
            key: match.get(key)
            for key in (
                "product_id", "title", "slug", "url", "catalog_price",
                "color_variant_id", "variant_candidates", "confidence",
            )
            if match.get(key) not in (None, "")
        }
        item.setdefault("title", match.get("title") or "Товар з каталогу")
        item.setdefault("qty", 1)
        item.setdefault("size", "")
        item.setdefault("fit", "")
        item.setdefault("unit_price", None)

    if not items:
        for match in confirmed:
            item = {}
            bind(item, match)
            items.append(item)
    else:
        used_product_ids = set()
        for item in items:
            source_message_id = item.get("source_message_id")
            candidates = [
                match for match in confirmed
                if source_message_id
                and source_message_id in (match.get("source_message_ids") or [])
                and match.get("product_id") not in used_product_ids
            ]
            if len(candidates) == 1:
                bind(item, candidates[0])
                used_product_ids.add(candidates[0].get("product_id"))
        unresolved_matches = [
            match for match in confirmed if match.get("product_id") not in used_product_ids
        ]
        if unresolved_matches:
            draft["catalog_candidates"] = unresolved_matches
            reasons = list(draft.get("uncertainty_reasons") or [])
            if "catalog_line_mapping_required" not in reasons:
                reasons.append("catalog_line_mapping_required")
            draft["uncertainty_reasons"] = reasons
    draft["items"] = items
    if items and all(item.get("product_id") for item in items):
        draft["uncertainty_reasons"] = [
            reason for reason in (draft.get("uncertainty_reasons") or [])
            if reason != "catalog_product_not_identified"
        ]


def next_review_status(status: str, action: str) -> str:
    """Apply the monotonic manager decision state machine."""
    if status == "pending" and action == "confirm":
        return "confirmed"
    if status == "confirmed" and action == "cancel":
        return "cancelled"
    if status in {"confirmed", "cancelled"}:
        return status
    if status == "pending" and action == "cancel":
        return "cancelled"
    return status


def extract_payment_review_evidence(messages) -> dict:
    """Classify customer payment evidence and preserve negotiated order facts.

    Manager payment instructions are context only. They can contribute a quoted
    conversation amount, but never create a payment review by themselves.
    """
    evidence = []
    amount_evidence = []
    order_items = []
    customer_messages = []
    context_messages = []
    raw_messages = list(messages or ())
    customer_order_seen = False
    last_manager_payment_index = None
    last_customer_payment_commitment_index = None
    for message_index, raw in enumerate(raw_messages):
        if not isinstance(raw, dict):
            continue
        role = str(raw.get("role") or "unknown").strip().lower()
        raw_text = str(raw.get("text") or "")
        text = " ".join(raw_text.split())
        attachments = str(raw.get("attachments") or "").strip()
        raw_media = raw.get("media") if isinstance(raw.get("media"), list) else _existing_media(attachments)
        if not text and not attachments and not raw_media:
            continue
        try:
            message_id = int(raw.get("id") or 0)
        except (TypeError, ValueError):
            message_id = 0
        media = [dict(item) for item in raw_media if isinstance(item, dict) and item.get("url")]
        explicit_claim = bool(_AFFIRMATION_RE.search(text)) and not _NON_EVIDENCE_RE.search(text)
        payment_text = bool(text and _PAYMENT_EVIDENCE_RE.search(text) and not _NON_EVIDENCE_RE.search(text))
        payment_context = bool(
            customer_order_seen
            and (
                (
                    last_manager_payment_index is not None
                    and message_index - last_manager_payment_index == 1
                )
                or (
                    last_customer_payment_commitment_index is not None
                    and message_index - last_customer_payment_commitment_index == 1
                )
            )
        )
        media = classify_media_items(
            text,
            media,
            payment_context=payment_context,
            explicit_claim=explicit_claim,
        )
        for media_item in media:
            media_item["message_id"] = message_id
        context_messages.append({
            "message_id": message_id,
            "role": role,
            "quote": raw_text[:500],
            "attachments": attachments[:500],
            "media": media[:8],
        })
        amounts = _AMOUNT_RE.findall(text)
        amount_kind = _amount_evidence_kind(text)
        for amount in amounts:
            try:
                normalized = Decimal(amount.replace(",", ".")).quantize(Decimal("0.01"))
            except (InvalidOperation, ValueError):
                continue
            amount_evidence.append({
                "message_id": message_id,
                "role": role,
                "amount": str(normalized).rstrip("0").rstrip("."),
                "kind": amount_kind,
                "quote": text[:300],
            })
        if role in _CUSTOMER_ROLES:
            customer_messages.append(text)
            for match in _FIT_RE.finditer(text):
                fit_raw = match.group("fit").lower()
                fit = "oversize" if ("оверсайз" in fit_raw or fit_raw == "oversize") else "classic"
                order_items.append({
                    "title": "Оверсайз" if fit == "oversize" else "Базова футболка",
                    "fit": fit,
                    "size": match.group("size").upper(),
                    "qty": 1,
                    "product_id": None,
                    "color_variant_id": None,
                    "unit_price": None,
                    "source_message_id": message_id,
                })
            is_receipt_attachment = bool(attachments) and (
                payment_context
                or explicit_claim
                or (payment_text and not _NON_EVIDENCE_RE.search(text))
            ) and not any(item.get("role") == "product" for item in media)
            is_receipt_attachment = is_receipt_attachment or any(
                item.get("role") in {"receipt", "payment_candidate"} for item in media
            )
            if explicit_claim or is_receipt_attachment:
                evidence.append({
                    "message_id": message_id,
                    "role": role,
                    "quote": text[:300],
                    "attachments": attachments[:500],
                    "media": media[:8],
                })
            if (
                payment_text
                or _MEDIA_PURCHASE_RE.search(text)
                or _FIT_RE.search(text)
                or any(item.get("role") == "product" for item in media)
            ):
                customer_order_seen = True
            if _CUSTOMER_PAYMENT_COMMITMENT_RE.search(text):
                last_customer_payment_commitment_index = message_index
        elif payment_text:
            last_manager_payment_index = message_index

    # A single explicit quantity describes the only extracted line; numbered
    # lines remain independent so classic and oversize are never collapsed.
    if len(order_items) == 1 and customer_messages:
        quantity_match = _QTY_RE.search(" ".join(customer_messages))
        if quantity_match:
            order_items[0]["qty"] = int(quantity_match.group(1))
    uncertainty_reasons = []
    if order_items:
        uncertainty_reasons.append("catalog_product_not_identified")
    commercial_amounts = [
        item for item in amount_evidence if item.get("kind") in {"order_total", "unit_price"}
    ]
    if order_items and not commercial_amounts:
        uncertainty_reasons.append("conversation_price_not_found")
    selected_amount = commercial_amounts[-1] if commercial_amounts else None
    quoted_total = selected_amount["amount"] if selected_amount else ""
    if len(order_items) == 1 and quoted_total:
        try:
            order_items[0]["unit_price"] = str(
                (Decimal(quoted_total) / Decimal(str(order_items[0].get("qty") or 1))).quantize(Decimal("0.01"))
            )
        except (InvalidOperation, ValueError, ZeroDivisionError):
            order_items[0]["unit_price"] = None
    elif len(order_items) > 1 and quoted_total:
        # A total for multiple lines is evidence, but it cannot safely be
        # allocated to each SKU without an explicit per-line price.
        uncertainty_reasons.append("conversation_price_allocation_required")
    manager_package_context = any(
        context["role"] not in _CUSTOMER_ROLES
        and re.search(r"пакет|zip|зіп", context["quote"], re.IGNORECASE)
        for context in context_messages
    )
    packaging_preference = ""
    if manager_package_context:
        customer_packaging_text = " ".join(
            context["quote"] for context in context_messages if context["role"] in _CUSTOMER_ROLES
        ).casefold()
        if "різн" in customer_packaging_text:
            packaging_preference = "Окремі пакети"
        elif "один" in customer_packaging_text:
            packaging_preference = "Один пакет"
    delivery = {"full_name": "", "phone": "", "city": "", "office": ""}
    for context in context_messages:
        if context["role"] not in _CUSTOMER_ROLES:
            continue
        quote = context["quote"]
        phone_match = _PHONE_RE.search(quote.replace(" ", ""))
        if phone_match and not delivery["phone"]:
            delivery["phone"] = phone_match.group(0)
        office_match = _OFFICE_RE.search(quote)
        if office_match and not delivery["office"]:
            delivery["office"] = f"{office_match.group('kind').capitalize()} {office_match.group('number')}"
        if "," in quote and not delivery["city"]:
            candidate = quote.split(",", 1)[0].strip()
            if 2 <= len(candidate) <= 100 and not any(char.isdigit() for char in candidate):
                delivery["city"] = candidate
        # Names are accepted only from the same customer message as a phone
        # number. This prevents short follow-ups such as "В різні" from
        # overwriting an already extracted recipient name. Slash-separated
        # delivery details are common in Instagram messages.
        segments = re.split(r"[/\n]+", quote) if phone_match else []
        for line in segments:
            candidate = " ".join(line.split()).strip(" .,:;()")
            if (
                not delivery["full_name"]
                and len(candidate.split()) in {2, 3}
                and not _PHONE_RE.search(candidate.replace(" ", ""))
                and not _FIT_RE.search(candidate)
                and not _AMOUNT_RE.search(candidate)
                and not _OFFICE_RE.search(candidate)
                and candidate.casefold() not in _NAME_STOPWORDS
                and not any(word in candidate.lower() for word in ("принт", "футбол", "передоплат", "оплат"))
            ):
                delivery["full_name"] = candidate
    media_audit = [
        media_item
        for context in context_messages
        for media_item in context.get("media", [])
    ]
    order_draft = {
        "items": order_items,
        "quoted_total": quoted_total,
        "currency": "UAH",
        "amount_source_message_id": selected_amount["message_id"] if selected_amount else None,
        "uncertainty_reasons": uncertainty_reasons,
        "packaging_preference": packaging_preference,
        "delivery": delivery,
        "context_messages": context_messages[-80:],
        "media": media_audit[:40],
    }
    return {
        "needs_review": bool(evidence),
        "provider_confirmed": False,
        "message_ids": [item["message_id"] for item in evidence if item["message_id"]],
        "evidence": evidence[-20:],
        "amount_evidence": amount_evidence[-20:],
        "order_draft": order_draft,
        "media": media_audit[:40],
    }


def _deal_payload(deal) -> dict:
    if not deal:
        return {"deal_id": None, "items": [], "amount": "0", "delivery": {}}
    return {
        "deal_id": deal.pk,
        "amount": str(deal.amount or 0),
        "currency": deal.currency or "UAH",
        "items": [
            {
                "product_id": item.product_id,
                "color_variant_id": item.color_variant_id,
                "title": item.title,
                "size": item.size,
                "qty": item.qty,
                "unit_price": str(item.unit_price or 0),
            }
            for item in deal.items.select_related("product", "color_variant").all()
        ],
        "delivery": {
            "full_name": deal.np_full_name or "",
            "phone": deal.np_phone or "",
            "city": deal.np_city or "",
            "office": deal.np_office or "",
        },
    }


def _alert_text(review, client) -> str:
    evidence = review.evidence if isinstance(review.evidence, dict) else {}
    draft = evidence.get("order_draft") if isinstance(evidence.get("order_draft"), dict) else {}
    items = draft.get("items") or []
    amount = draft.get("quoted_total") or "не вказано"
    lines = [
        "⚠️ Instagram: потрібна перевірка заяви про оплату",
        f"Клієнт: {client.display_name or client.username or client.igsid} (IGSID {client.igsid})",
        f"Review #{review.pk}",
        "Оплата: не підтверджена provider ledger; потрібне ручне рішення.",
        f"Сума з переписки: {amount} грн",
    ]
    if items:
        lines.append("Позиції з переписки:")
        for item in items:
            catalog = item.get("catalog") if isinstance(item.get("catalog"), dict) else {}
            product_label = catalog.get("title") or item.get("title") or item.get("fit") or "Товар"
            variant_label = ""
            variant_id = catalog.get("color_variant_id")
            for variant in catalog.get("variant_candidates") or []:
                if variant.get("id") == variant_id and variant.get("color"):
                    variant_label = f" · {variant['color']}"
                    break
            lines.append(
                f"• {product_label}{variant_label} · "
                f"{item.get('size') or 'розмір не вказано'} · {item.get('qty') or 1} шт."
            )
    else:
        lines.append("Позиції з переписки: не визначені")
    packaging = draft.get("packaging_preference") or ""
    if packaging:
        lines.append(f"Пакування: {packaging}")
    delivery = draft.get("delivery") if isinstance(draft.get("delivery"), dict) else {}
    delivery_text = ", ".join(
        value for value in (delivery.get("full_name"), delivery.get("phone"), delivery.get("city"), delivery.get("office")) if value
    )
    if delivery_text:
        lines.append(f"Доставка: {delivery_text}")
    reasons = draft.get("uncertainty_reasons") or []
    if reasons:
        labels = {
            "catalog_product_not_identified": "товар не зіставлено з каталогом; виберіть його вручну",
            "conversation_price_not_found": "ціну з переписки не знайдено",
            "conversation_price_allocation_required": "загальну суму з переписки потрібно розподілити між позиціями вручну",
            "conversation_price_not_authorized": "ціну не підтверджено менеджером; перевірте вручну",
        }
        lines.append("Потрібно уточнити: " + "; ".join(labels.get(reason, reason) for reason in reasons))
    catalog_matches = evidence.get("catalog_matches") if isinstance(evidence.get("catalog_matches"), list) else []
    if not catalog_matches:
        legacy_match = evidence.get("catalog_match") if isinstance(evidence.get("catalog_match"), dict) else {}
        catalog_matches = [legacy_match] if legacy_match else []
    matched_catalog = [match for match in catalog_matches if match.get("status") == "matched"]
    if matched_catalog:
        lines.append("Зіставлення з каталогом:")
        for match in matched_catalog:
            lines.append(
                f"• {match.get('title') or 'товар'} "
                f"({round(float(match.get('confidence') or 0) * 100)}% впевненості)"
                + (f" — {match['url']}" if match.get("url") else "")
            )
    elif catalog_matches:
        lines.append("Зображення товару: точного збігу з каталогом не знайдено — перевірте вручну.")
    media = evidence.get("media") if isinstance(evidence.get("media"), list) else []
    receipts = [item for item in media if item.get("role") == "receipt"]
    payment_candidates = [item for item in media if item.get("role") == "payment_candidate"]
    products = [item for item in media if item.get("role") == "product"]
    lines.append(
        f"Вкладення: чеків {len(receipts)}, ймовірних чеків для звірки "
        f"{len(payment_candidates)}, зображень товару {len(products)}."
    )
    base = getattr(settings, "MANAGEMENT_BASE_URL", "https://management.twocomms.shop").rstrip("/")
    lines.append(f"Відкрити review: {base}/bot/?payment_review={review.pk}")
    return "\n".join(lines)


def _review_keyboard(review) -> dict:
    base = getattr(settings, "MANAGEMENT_BASE_URL", "https://management.twocomms.shop").rstrip("/")
    rows = [[
        {"text": "Підтвердити оплату", "callback_data": f"igpay:confirm:{review.pk}"},
        {"text": "Відхилити", "callback_data": f"igpay:cancel:{review.pk}"},
    ], [
        {"text": "Відкрити перевірку", "url": f"{base}/bot/?payment_review={review.pk}"},
    ]]
    evidence = review.evidence if isinstance(getattr(review, "evidence", None), dict) else {}
    matches = evidence.get("catalog_matches") if isinstance(evidence.get("catalog_matches"), list) else []
    if not matches:
        legacy_match = evidence.get("catalog_match") if isinstance(evidence.get("catalog_match"), dict) else {}
        matches = [legacy_match] if legacy_match else []
    for match in matches[:4]:
        if not isinstance(match, dict) or match.get("status") != "matched" or not match.get("url"):
            continue
        rows.append([{
            "text": f"Товар: {str(match.get('title') or 'відкрити картку')[:48]}",
            "url": str(match["url"]),
        }])
    return {"inline_keyboard": rows}


def create_payment_review(client, *, watermark: int = 0, messages=None):
    """Persist an idempotent review and enqueue its management alert.

    The alert uses the existing notification outbox. No customer message,
    Meta event, provider call, or order is created here.
    """
    if not client or client.hidden_at:
        return None
    from management.ig_bot_models import IgPaymentConfirmationReview
    from management.models import InstagramBotMessage

    if messages is None:
        rows = list(
            InstagramBotMessage.objects.filter(client_id=client.pk)
            .order_by("-id")[:80]
        )
        rows.reverse()
        messages = [
            {
                "id": row.pk,
                "mid": row.mid,
                "role": row.role,
                "text": row.text,
                "attachments": row.attachments,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]
    messages = _augment_messages_with_raw_media(client, messages)
    extracted = extract_payment_review_evidence(messages)
    if not extracted["needs_review"]:
        return None
    resolved_media = _resolve_payment_media_candidates(extracted.get("media") or [])
    enriched_media = _persist_review_media(resolved_media)
    for item in enriched_media:
        item["message_id"] = item.get("message_id") or None
    for container in [
        *(extracted.get("order_draft", {}).get("context_messages", []) or []),
        *(extracted.get("evidence", []) or []),
    ]:
        context_media = container.get("media") or [] if isinstance(container, dict) else []
        for context_item in context_media:
            for item in enriched_media:
                if item.get("url") == context_item.get("url"):
                    context_item.update(item)
    _reconcile_payment_evidence_after_media_resolution(extracted, enriched_media)
    if not extracted["needs_review"]:
        return None
    extracted["media"] = enriched_media
    extracted["order_draft"]["media"] = enriched_media
    catalog_matches = _catalog_matches_for_media(enriched_media)
    for media_item in enriched_media:
        bound_matches = media_item.get("catalog_matches") if isinstance(media_item.get("catalog_matches"), list) else []
        if bound_matches:
            media_item["product_id"] = ",".join(str(match.get("product_id")) for match in bound_matches if match.get("product_id"))
            media_item["product_title"] = " / ".join(str(match.get("title")) for match in bound_matches if match.get("title"))
            media_item["product_url"] = "\n".join(str(match.get("url")) for match in bound_matches if match.get("url"))
            media_item["confidence"] = ",".join(str(match.get("confidence")) for match in bound_matches if match.get("confidence") is not None)
    extracted["catalog_matches"] = catalog_matches
    extracted["catalog_match"] = catalog_matches[0] if catalog_matches else {}
    _apply_catalog_matches_to_draft(extracted["order_draft"], catalog_matches)
    _apply_validated_conversation_price_to_draft(extracted["order_draft"], messages, catalog_matches)
    extracted["media_audit_v3"] = True
    watermark = int(watermark or max(extracted["message_ids"] or [0]))
    deal = _select_review_deal(client, catalog_matches)
    dedupe_key = f"ig-payment-review:{client.pk}:{watermark}"
    with transaction.atomic():
        review, created = IgPaymentConfirmationReview.objects.get_or_create(
            dedupe_key=dedupe_key,
            defaults={
                "client": client,
                "deal": deal,
                "evidence": {
                    "messages": extracted["evidence"],
                    "amount_evidence": extracted["amount_evidence"],
                    "order_draft": extracted["order_draft"],
                    "media": extracted.get("media", []),
                    "catalog_match": extracted.get("catalog_match", {}),
                    "catalog_matches": extracted.get("catalog_matches", []),
                    "media_audit_v3": True,
                    "deal": _deal_payload(deal),
                },
                "watermark_message_id": watermark,
            },
        )
    from management.services.instagram_bot import notify_manager

    if not created and isinstance(review.evidence, dict) and (
        not review.evidence.get("media_audit_v3")
        or (extracted.get("catalog_matches") and not review.evidence.get("catalog_matches"))
        or len(extracted.get("media") or []) > len(review.evidence.get("media") or [])
    ):
        review.evidence = {
            **review.evidence,
            "messages": extracted["evidence"],
            "amount_evidence": extracted["amount_evidence"],
            "order_draft": extracted["order_draft"],
            "media": extracted.get("media", []),
            "catalog_match": extracted.get("catalog_match", {}),
            "catalog_matches": extracted.get("catalog_matches", []),
            "media_audit_v3": True,
        }
        review.save(update_fields=["evidence", "updated_at"])

    notify_manager(
        _alert_text(review, client),
        dedupe_key=review.dedupe_key,
        event_type="payment_review",
        client=client,
        reply_markup=_review_keyboard(review),
        media=enriched_media,
    )
    return review


def confirm_review(review, *, actor, telegram_decision=None):
    from management.ig_bot_models import IgPaymentConfirmationReview

    with transaction.atomic():
        locked = IgPaymentConfirmationReview.objects.select_for_update().get(pk=review.pk)
        locked._transitioned = False
        if locked.status == IgPaymentConfirmationReview.Status.PENDING:
            locked.status = IgPaymentConfirmationReview.Status.CONFIRMED
            locked.confirmed_by = actor
            locked.confirmed_at = timezone.now()
            update_fields = ["status", "confirmed_by", "confirmed_at", "updated_at"]
            if isinstance(telegram_decision, dict):
                evidence = locked.evidence if isinstance(locked.evidence, dict) else {}
                locked.evidence = {**evidence, "telegram_decision": telegram_decision}
                update_fields.append("evidence")
            locked.save(update_fields=update_fields)
            locked._transitioned = True
        return locked


def cancel_review(review, *, actor, reason="", telegram_decision=None):
    from management.ig_bot_models import IgPaymentConfirmationReview

    with transaction.atomic():
        locked = IgPaymentConfirmationReview.objects.select_for_update().get(pk=review.pk)
        locked._transitioned = False
        if locked.status == IgPaymentConfirmationReview.Status.PENDING:
            locked.status = IgPaymentConfirmationReview.Status.CANCELLED
            locked.cancelled_by = actor
            locked.cancelled_at = timezone.now()
            locked.cancellation_reason = (reason or "")[:500]
            update_fields = ["status", "cancelled_by", "cancelled_at", "cancellation_reason", "updated_at"]
            if isinstance(telegram_decision, dict):
                evidence = locked.evidence if isinstance(locked.evidence, dict) else {}
                locked.evidence = {**evidence, "telegram_decision": telegram_decision}
                update_fields.append("evidence")
            locked.save(update_fields=update_fields)
            locked._transitioned = True
        return locked
