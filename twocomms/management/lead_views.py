from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .constants import LEAD_BASE_PROCESSING_PENALTY, POINTS, TARGET_CLIENTS_DAY, TARGET_POINTS_DAY
from .models import Client, ManagementLead, normalize_phone
from .context_processors import build_management_shell_metrics
from .services.client_entry import merge_result_capture_with_evidence, record_client_interaction, validate_client_entry_evidence
from .services.dedupe import (
    DedupeZone,
    build_duplicate_conflict_payload,
    evaluate_duplicate_zone,
    resolve_duplicate_review_override,
)
from .services.outcomes import format_source_display, next_call_at_from_request, normalize_result_capture, parse_next_call_request
from .views import _serialize_client_for_home, _sync_client_followup, get_user_stats, user_is_management


def _source_display(source: str, source_link: str, source_other: str) -> str:
    return format_source_display(source, source_link, source_other)


def _next_call_at_from_request(data) -> datetime | None:
    return next_call_at_from_request(data)


def _lead_payload(lead: ManagementLead) -> dict:
    return {
        "id": lead.id,
        "shop_name": lead.shop_name,
        "phone": lead.phone,
        "full_name": lead.full_name,
        "role": lead.role,
        "role_display": lead.get_role_display(),
        "source": lead.source,
        "website_url": lead.website_url,
        "city": lead.city,
        "comments": lead.comments,
        "details": lead.details,
        "added_by": lead.added_by_display,
        "status": lead.status,
        "status_display": lead.get_status_display(),
    }


def _stats_payload(user) -> dict:
    stats = get_user_stats(user)
    processed_today = stats["processed_today"]
    user_points_today = stats["points_today"]
    progress_clients_pct = min(100, int(processed_today / TARGET_CLIENTS_DAY * 100)) if TARGET_CLIENTS_DAY else 0
    progress_points_pct = min(100, int(user_points_today / TARGET_POINTS_DAY * 100)) if TARGET_POINTS_DAY else 0
    shell_metrics = build_management_shell_metrics(user, getattr(user, "userprofile", None))
    return {
        "user_points_today": user_points_today,
        "user_points_total": stats["points_total"],
        "processed_today": processed_today,
        "target_clients": TARGET_CLIENTS_DAY,
        "target_points": TARGET_POINTS_DAY,
        "progress_clients_pct": progress_clients_pct,
        "progress_points_pct": progress_points_pct,
        "shell_secondary_counts": shell_metrics["management_shell_secondary_counts"],
    }


@login_required(login_url="management_login")
@require_POST
def lead_create_api(request):
    if not user_is_management(request.user):
        return JsonResponse({"success": False, "error": "Доступ заборонено."}, status=403)

    data = request.POST
    shop_name = (data.get("shop_name") or "").strip()
    phone = (data.get("phone") or "").strip()
    full_name = (data.get("full_name") or "").strip()
    role = (data.get("role") or Client.Role.OTHER).strip()
    source = (data.get("source") or "").strip()
    source_link = (data.get("source_link") or "").strip()
    source_other = (data.get("source_other") or "").strip()
    website_url = (data.get("website_url") or "").strip()
    city = (data.get("city") or "").strip()
    comments = (data.get("comments") or "").strip()
    details = (data.get("details") or "").strip()

    if not shop_name or not phone:
        return JsonResponse({"success": False, "error": "Вкажіть назву магазину та номер телефону."}, status=400)

    phone_normalized = normalize_phone(phone)
    if not phone_normalized:
        return JsonResponse({"success": False, "error": "Не вдалося розпізнати номер телефону."}, status=400)

    duplicate_decision = evaluate_duplicate_zone(
        shop_name=shop_name,
        phone=phone_normalized,
        website_url=website_url,
        owner=request.user,
    )
    if duplicate_decision.zone in {DedupeZone.AUTO_BLOCK, DedupeZone.REVIEW}:
        return JsonResponse(
            build_duplicate_conflict_payload(
                owner=request.user,
                decision=duplicate_decision,
                shop_name=shop_name,
                phone=phone_normalized,
                payload={
                    "shop_name": shop_name,
                    "full_name": full_name,
                    "website_url": website_url,
                    "city": city,
                },
                auto_block_error="Такий номер вже є у базі.",
                review_error="Потрібна перевірка на дубль.",
            ),
            status=409,
        )

    lead = ManagementLead.objects.create(
        shop_name=shop_name,
        phone=phone_normalized,
        full_name=full_name,
        role=role if role in Client.Role.values else Client.Role.OTHER,
        source=_source_display(source, source_link, source_other),
        website_url=website_url,
        city=city,
        comments=comments,
        details=details,
        status=ManagementLead.Status.BASE,
        lead_source=ManagementLead.LeadSource.MANUAL,
        added_by=request.user,
        approved_to_base_at=timezone.now(),
    )
    payload = {"success": True, "lead": _lead_payload(lead)}
    payload.update(_stats_payload(request.user))
    return JsonResponse(payload)


@login_required(login_url="management_login")
@require_GET
def lead_detail_api(request, lead_id: int):
    if not user_is_management(request.user):
        return JsonResponse({"success": False, "error": "Доступ заборонено."}, status=403)

    try:
        lead = ManagementLead.objects.get(id=lead_id)
    except ManagementLead.DoesNotExist:
        return JsonResponse({"success": False, "error": "Лід не знайдено."}, status=404)

    return JsonResponse({"success": True, "lead": _lead_payload(lead)})


@login_required(login_url="management_login")
@require_POST
def lead_process_api(request, lead_id: int):
    if not user_is_management(request.user):
        return JsonResponse({"success": False, "error": "Доступ заборонено."}, status=403)

    data = request.POST
    shop_name = (data.get("shop_name") or "").strip()
    phone = (data.get("phone") or "").strip()
    website_url = (data.get("website_url") or "").strip()
    full_name = (data.get("full_name") or "").strip() or "ПІБ не вказано"
    role = (data.get("role") or Client.Role.MANAGER).strip()
    role_custom = (data.get("role_custom") or "").strip()
    source = (data.get("source") or "").strip()
    source_link = (data.get("source_link") or "").strip()
    source_other = (data.get("source_other") or "").strip()
    call_result = (data.get("call_result") or Client.CallResult.THINKING).strip()
    call_result_other = (data.get("call_result_other") or "").strip()
    call_result_reason_code = (data.get("call_result_reason_code") or "").strip()
    call_result_reason_note = (data.get("call_result_reason_note") or "").strip()
    call_result_contact_attempts = (data.get("call_result_contact_attempts") or "").strip()
    call_result_contact_channel = (data.get("call_result_contact_channel") or "").strip()
    manager_note = (data.get("manager_note") or "").strip()
    next_call_type = (data.get("next_call_type") or "scheduled").strip()
    next_call_at, next_call_error = parse_next_call_request(data, now_dt=timezone.now())
    if next_call_error:
        return JsonResponse({"success": False, "error": next_call_error}, status=400)

    if not shop_name or not phone:
        return JsonResponse({"success": False, "error": "Вкажіть назву магазину та номер телефону."}, status=400)

    role_value = role if role in Client.Role.values else Client.Role.OTHER
    call_value = call_result if call_result in Client.CallResult.values else Client.CallResult.THINKING
    result_capture = normalize_result_capture(
        call_result=call_value,
        role=role_value,
        role_custom=role_custom,
        call_result_other=call_result_other,
        reason_code=call_result_reason_code,
        reason_note=call_result_reason_note,
        contact_attempts=call_result_contact_attempts,
        contact_channel=call_result_contact_channel,
    )
    if result_capture["errors"]:
        return JsonResponse({"success": False, "error": result_capture["errors"][0]}, status=400)

    details = result_capture["details"]
    source_display = _source_display(source, source_link, source_other)

    with transaction.atomic():
        try:
            lead = ManagementLead.objects.select_for_update().get(id=lead_id)
        except ManagementLead.DoesNotExist:
            return JsonResponse({"success": False, "error": "Лід не знайдено."}, status=404)

        if lead.status != ManagementLead.Status.BASE:
            return JsonResponse({"success": False, "error": "Лід вже оброблено або недоступний."}, status=409)

        phone_normalized = normalize_phone(phone)
        if not phone_normalized:
            return JsonResponse({"success": False, "error": "Не вдалося розпізнати номер телефону."}, status=400)

        evidence = validate_client_entry_evidence(
            data=data,
            owner=request.user,
            phone_normalized=phone_normalized,
            call_result=call_value,
            result_capture=result_capture,
        )
        if evidence["errors"]:
            return JsonResponse({"success": False, "error": evidence["errors"][0]}, status=400)
        result_context, details = merge_result_capture_with_evidence(result_capture, evidence)
        if next_call_type == "no_follow":
            result_context["followup_mode"] = "no_follow"
        else:
            result_context.pop("followup_mode", None)
        result_capture["context"] = result_context
        result_capture["details"] = details

        duplicate_decision = evaluate_duplicate_zone(
            shop_name=shop_name,
            phone=phone_normalized,
            website_url=website_url,
            owner=request.user,
            exclude_lead_ids=[lead.id],
        )
        duplicate_payload = {
            "lead_id": lead.id,
            "shop_name": shop_name,
            "full_name": full_name,
            "website_url": website_url,
            "role": role_value,
            "source": source_display or lead.source or "База лідів",
            "call_result": call_value,
            "context": result_context,
        }
        duplicate_review = None
        if duplicate_decision.zone in {DedupeZone.AUTO_BLOCK, DedupeZone.REVIEW} and not evidence["duplicate_override_reason"]:
            return JsonResponse(
                build_duplicate_conflict_payload(
                    owner=request.user,
                    decision=duplicate_decision,
                    shop_name=shop_name,
                    phone=phone_normalized,
                    payload=duplicate_payload,
                    auto_block_error="Такий номер вже є у базі.",
                    review_error="Потрібна перевірка на дубль перед конвертацією ліда.",
                ),
                status=409,
            )
        if duplicate_decision.zone in {DedupeZone.AUTO_BLOCK, DedupeZone.REVIEW}:
            duplicate_review = resolve_duplicate_review_override(
                owner=request.user,
                decision=duplicate_decision,
                shop_name=shop_name,
                phone=phone_normalized,
                payload=duplicate_payload,
                override_reason=evidence["duplicate_override_reason"],
            )
            result_context["duplicate_override_reason"] = evidence["duplicate_override_reason"]

        base_points = int(POINTS.get(call_value, 0))
        adjusted_points = max(0, base_points - LEAD_BASE_PROCESSING_PENALTY)
        client = Client.objects.create(
            shop_name=shop_name,
            phone=phone_normalized,
            website_url=website_url,
            full_name=full_name,
            role=role_value,
            source=source_display or lead.source or "База лідів",
            call_result=call_value,
            call_result_reason_code=result_capture["reason_code"],
            call_result_reason_note=result_capture["reason_note"],
            call_result_context=result_context,
            call_result_details=details,
            manager_note=manager_note,
            next_call_at=next_call_at,
            owner=request.user,
            points_override=adjusted_points,
        )
        _sync_client_followup(client, None, client.next_call_at, timezone.now())
        record_client_interaction(
            client=client,
            manager=request.user,
            result_capture=result_capture,
            call_result=call_value,
            next_call_at=next_call_at,
            evidence=evidence,
            duplicate_review=duplicate_review,
        )

        lead.status = ManagementLead.Status.CONVERTED
        lead.processed_by = request.user
        lead.converted_client = client
        lead.shop_name = shop_name
        lead.phone = phone_normalized
        lead.website_url = website_url
        lead.full_name = full_name
        lead.role = role_value
        lead.source = source_display or lead.source
        lead.save()

    payload = {
        "success": True,
        "client": _serialize_client_for_home(client, timezone.localdate()),
        "lead_id": lead_id,
    }
    payload.update(_stats_payload(request.user))
    return JsonResponse(payload)
