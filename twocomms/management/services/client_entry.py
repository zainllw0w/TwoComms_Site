from __future__ import annotations

from typing import Any

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from management.models import (
    Client,
    ClientCPLink,
    ClientInteractionAttempt,
    CommercialOfferEmailLog,
    DuplicateReview,
    Shop,
)
from management.services.analytics_v7 import record_interaction_analytics


MESSENGER_TYPE_LABELS = {
    "telegram": "Telegram",
    "whatsapp": "WhatsApp",
    "viber": "Viber",
    "other": "Інший",
}

MESSENGER_TARGET_MODE_LABELS = {
    "phone": "За номером телефону",
    "manual": "Окремий логін або номер",
}

XML_PLATFORM_LABELS = {
    "prom": "Prom",
    "other": "Інший ресурс",
}

NEGATIVE_RESULTS_REQUIRING_NOTE = frozenset(
    {
        Client.CallResult.NOT_INTERESTED,
        Client.CallResult.EXPENSIVE,
        Client.CallResult.INVALID_NUMBER,
        Client.CallResult.OTHER,
    }
)


def _user_display(user) -> str:
    if not user:
        return "—"
    full_name = (user.get_full_name() or "").strip()
    return full_name or getattr(user, "username", "—")


def _serialize_cp_log(log: CommercialOfferEmailLog) -> dict[str, Any]:
    return {
        "id": log.id,
        "label": f"{log.recipient_email} · {timezone.localtime(log.created_at).strftime('%d.%m.%Y %H:%M')}",
        "recipient_email": log.recipient_email,
        "recipient_name": log.recipient_name or "",
        "created_at": timezone.localtime(log.created_at).strftime("%d.%m.%Y %H:%M"),
    }


def _serialize_shop(shop: Shop) -> dict[str, Any]:
    latest_shipment = shop.shipments.select_related("wholesale_invoice").order_by("-shipped_at", "-created_at").first()
    latest_ttn = latest_shipment.ttn_number if latest_shipment else ""
    latest_total = ""
    if latest_shipment and latest_shipment.invoice_total_amount is not None:
        latest_total = str(latest_shipment.invoice_total_amount)
    return {
        "id": shop.id,
        "label": shop.name,
        "shop_type": shop.shop_type,
        "shop_type_display": shop.get_shop_type_display(),
        "latest_ttn": latest_ttn,
        "latest_invoice_total_amount": latest_total,
        "website_url": shop.website_url or "",
        "instagram_url": shop.instagram_url or "",
        "prom_url": shop.prom_url or "",
    }


def build_client_entry_form_payload(user) -> dict[str, Any]:
    cp_logs = CommercialOfferEmailLog.objects.filter(
        owner=user,
        status=CommercialOfferEmailLog.Status.SENT,
    ).order_by("-created_at")[:120]
    shops = (
        Shop.objects.filter(Q(created_by=user) | Q(managed_by=user))
        .distinct()
        .prefetch_related("shipments")
        .order_by("-created_at")[:160]
    )
    full_shops = [shop for shop in shops if shop.shop_type == Shop.ShopType.FULL]
    test_shops = [shop for shop in shops if shop.shop_type == Shop.ShopType.TEST]
    return {
        "cp_logs": [_serialize_cp_log(log) for log in cp_logs],
        "full_shops": [_serialize_shop(shop) for shop in full_shops],
        "test_shops": [_serialize_shop(shop) for shop in test_shops],
        "messenger_types": [
            {"value": value, "label": label}
            for value, label in MESSENGER_TYPE_LABELS.items()
        ],
        "xml_platforms": [
            {"value": value, "label": label}
            for value, label in XML_PLATFORM_LABELS.items()
        ],
    }


def validate_client_entry_evidence(
    *,
    data,
    owner,
    phone_normalized: str,
    call_result: str,
    result_capture: dict[str, Any],
) -> dict[str, Any]:
    errors: list[str] = []
    context_updates: dict[str, Any] = {}
    detail_fragments: list[str] = []

    cp_log = None
    linked_shop = None
    cp_log_id = (data.get("cp_log_id") or "").strip()
    linked_shop_id = (data.get("linked_shop_id") or "").strip()
    messenger_type = (data.get("messenger_type") or "").strip().lower()
    messenger_target_mode = (data.get("messenger_target_mode") or "").strip().lower()
    messenger_target_value = (data.get("messenger_target_value") or "").strip()
    messenger_use_phone = str(data.get("messenger_use_phone") or "").strip().lower() in {"1", "true", "on", "yes"}
    xml_platform = (data.get("xml_platform") or "").strip().lower()
    xml_resource_url = (data.get("xml_resource_url") or "").strip()
    duplicate_override_reason = (data.get("duplicate_override_reason") or "").strip()

    if messenger_use_phone:
        messenger_target_mode = "phone"

    if call_result in NEGATIVE_RESULTS_REQUIRING_NOTE and len((result_capture.get("reason_note") or "").strip()) < 6:
        errors.append("Для неконверсійного результату додайте коротке обґрунтування в коментарі.")

    if call_result == Client.CallResult.SENT_EMAIL:
        if not cp_log_id:
            errors.append("Для КП на e-mail оберіть відправлений лист зі списку.")
        else:
            cp_log = CommercialOfferEmailLog.objects.filter(
                id=cp_log_id,
                owner=owner,
                status=CommercialOfferEmailLog.Status.SENT,
            ).first()
            if not cp_log:
                errors.append("Обраний лист КП не знайдено серед відправлених.")
            else:
                context_updates["cp_log_id"] = cp_log.id
                context_updates["cp_recipient_email"] = cp_log.recipient_email
                detail_fragments.append(f"КП: {cp_log.recipient_email}")

    if call_result == Client.CallResult.SENT_MESSENGER:
        if messenger_type not in MESSENGER_TYPE_LABELS:
            errors.append("Оберіть месенджер, через який відправили КП.")
        else:
            if messenger_target_mode not in MESSENGER_TARGET_MODE_LABELS:
                messenger_target_mode = "phone" if messenger_use_phone else "manual"
            if messenger_target_mode == "phone":
                messenger_target_value = phone_normalized
            if not messenger_target_value:
                errors.append("Вкажіть логін або номер для месенджера.")
            else:
                context_updates["messenger_type"] = messenger_type
                context_updates["messenger_target_mode"] = messenger_target_mode
                context_updates["messenger_target_value"] = messenger_target_value
                detail_fragments.append(
                    f"Месенджер: {MESSENGER_TYPE_LABELS[messenger_type]} · {messenger_target_value}"
                )

    if call_result == Client.CallResult.XML_CONNECTED:
        if xml_platform not in XML_PLATFORM_LABELS or not xml_resource_url:
            errors.append("Для XML оберіть платформу та вкажіть посилання на підключений ресурс.")
        else:
            context_updates["xml_platform"] = xml_platform
            context_updates["xml_resource_url"] = xml_resource_url
            detail_fragments.append(f"XML: {XML_PLATFORM_LABELS[xml_platform]} · {xml_resource_url}")

    if call_result in {Client.CallResult.ORDER, Client.CallResult.TEST_BATCH}:
        expected_type = Shop.ShopType.FULL if call_result == Client.CallResult.ORDER else Shop.ShopType.TEST
        if not linked_shop_id:
            errors.append(
                "Для цього результату потрібно обрати магазин менеджера."
                if call_result == Client.CallResult.ORDER
                else "Для тестової партії потрібно обрати тестовий магазин менеджера."
            )
        else:
            linked_shop = (
                Shop.objects.filter(id=linked_shop_id, shop_type=expected_type)
                .filter(Q(created_by=owner) | Q(managed_by=owner))
                .first()
            )
            if not linked_shop:
                errors.append("Обраний магазин недоступний для цього результату.")
            else:
                context_updates["linked_shop_id"] = linked_shop.id
                context_updates["linked_shop_type"] = linked_shop.shop_type
                context_updates["linked_shop_name"] = linked_shop.name
                detail_fragments.append(f"Магазин: {linked_shop.name}")

    verification_level = ClientInteractionAttempt.VerificationLevel.SELF_REPORTED
    if duplicate_override_reason:
        verification_level = ClientInteractionAttempt.VerificationLevel.OVERRIDE
    elif cp_log or linked_shop or xml_resource_url:
        verification_level = ClientInteractionAttempt.VerificationLevel.LINKED_EVIDENCE

    return {
        "errors": errors,
        "cp_log": cp_log,
        "linked_shop": linked_shop,
        "context_updates": context_updates,
        "detail_fragments": detail_fragments,
        "messenger_type": context_updates.get("messenger_type", ""),
        "messenger_target_mode": context_updates.get("messenger_target_mode", ""),
        "messenger_target_value": context_updates.get("messenger_target_value", ""),
        "xml_platform": context_updates.get("xml_platform", ""),
        "xml_resource_url": context_updates.get("xml_resource_url", ""),
        "duplicate_override_reason": duplicate_override_reason,
        "verification_level": verification_level,
    }


def merge_result_capture_with_evidence(result_capture: dict[str, Any], evidence: dict[str, Any]) -> tuple[dict[str, Any], str]:
    context = dict(result_capture.get("context") or {})
    context.update(evidence.get("context_updates") or {})
    details_parts = [part for part in str(result_capture.get("details") or "").splitlines() if part.strip()]
    details_parts.extend(fragment for fragment in evidence.get("detail_fragments") or [] if fragment)
    return context, "\n".join(details_parts)


def record_client_interaction(
    *,
    client: Client,
    manager,
    result_capture: dict[str, Any],
    call_result: str,
    next_call_at,
    evidence: dict[str, Any],
    duplicate_review: DuplicateReview | None = None,
) -> ClientInteractionAttempt:
    with transaction.atomic():
        interaction = ClientInteractionAttempt.objects.create(
            client=client,
            manager=manager,
            result=call_result,
            reason_code=result_capture.get("reason_code") or "",
            reason_note=result_capture.get("reason_note") or "",
            context=result_capture.get("context") or {},
            details=result_capture.get("details") or "",
            next_call_at=next_call_at,
            verification_level=evidence.get("verification_level") or ClientInteractionAttempt.VerificationLevel.SELF_REPORTED,
            linked_shop=evidence.get("linked_shop"),
            cp_log=evidence.get("cp_log"),
            duplicate_review=duplicate_review,
            duplicate_override_reason=evidence.get("duplicate_override_reason") or "",
            messenger_type=evidence.get("messenger_type") or "",
            messenger_target_mode=evidence.get("messenger_target_mode") or "",
            messenger_target_value=evidence.get("messenger_target_value") or "",
            xml_platform=evidence.get("xml_platform") or "",
            xml_resource_url=evidence.get("xml_resource_url") or "",
        )
        if evidence.get("cp_log"):
            cp_link, created = ClientCPLink.objects.get_or_create(
                client=client,
                cp_log=evidence["cp_log"],
                defaults={
                    "linked_by": manager,
                    "interaction": interaction,
                },
            )
            if not created and cp_link.interaction_id is None:
                cp_link.interaction = interaction
                cp_link.linked_by = cp_link.linked_by or manager
                cp_link.save(update_fields=["interaction", "linked_by"])
        record_interaction_analytics(interaction)
    return interaction


def duplicate_override_payload_note(reason: str) -> dict[str, Any]:
    return {
        "override_reason": reason,
    }


def candidate_owner_display(owner) -> str:
    return _user_display(owner)
