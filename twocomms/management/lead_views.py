from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .constants import LEAD_BASE_PROCESSING_PENALTY, POINTS, TARGET_CLIENTS_DAY, TARGET_POINTS_DAY
from .models import Client, ManagementLead, normalize_phone
from .views import _sync_client_followup, get_user_stats, user_is_management


def _source_display(source: str, source_link: str, source_other: str) -> str:
    return {
        "instagram": "Instagram",
        "prom_ua": "Prom.ua",
        "google_maps": "Google Карти",
        "forums": f"Сайти/Форуми: {source_link}" if source_link else "Сайти/Форуми",
        "other": source_other or "Інше",
    }.get(source, source or "")


def _next_call_at_from_request(data) -> datetime | None:
    next_call_type = data.get("next_call_type", "scheduled")
    if next_call_type == "no_follow":
        return None
    next_call_date = (data.get("next_call_date") or "").strip()
    next_call_time = (data.get("next_call_time") or "").strip()
    if not next_call_date or not next_call_time:
        return None
    try:
        naive = datetime.strptime(f"{next_call_date} {next_call_time}", "%Y-%m-%d %H:%M")
        return timezone.make_aware(naive, timezone.get_current_timezone())
    except ValueError:
        return None


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
    return {
        "user_points_today": user_points_today,
        "user_points_total": stats["points_total"],
        "processed_today": processed_today,
        "target_clients": TARGET_CLIENTS_DAY,
        "target_points": TARGET_POINTS_DAY,
        "progress_clients_pct": progress_clients_pct,
        "progress_points_pct": progress_points_pct,
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

    has_duplicate = Client.objects.filter(phone_normalized=phone_normalized).exists() or ManagementLead.objects.filter(
        phone_normalized=phone_normalized
    ).exists()
    if has_duplicate:
        return JsonResponse({"success": False, "error": "Такий номер вже є у базі."}, status=409)

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
    next_call_at = _next_call_at_from_request(data)

    if not shop_name or not phone:
        return JsonResponse({"success": False, "error": "Вкажіть назву магазину та номер телефону."}, status=400)

    role_value = role if role in Client.Role.values else Client.Role.OTHER
    call_value = call_result if call_result in Client.CallResult.values else Client.CallResult.THINKING
    details_parts = []
    if role_value == Client.Role.OTHER and role_custom:
        details_parts.append(f"Роль: {role_custom}")
    if call_value == Client.CallResult.OTHER and call_result_other:
        details_parts.append(f"Інше: {call_result_other}")
    details = "\n".join(details_parts)
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
            call_result_details=details,
            next_call_at=next_call_at,
            owner=request.user,
            points_override=adjusted_points,
        )
        _sync_client_followup(client, None, client.next_call_at, timezone.now())

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
        "client": {
            "id": client.id,
            "shop": client.shop_name,
            "phone": client.phone,
            "website_url": client.website_url,
            "full_name": client.full_name,
            "role": client.role,
            "role_display": client.get_role_display(),
            "source": client.source,
            "call_result": client.call_result,
            "call_result_display": client.get_call_result_display(),
            "call_result_details": client.call_result_details,
            "next_call": timezone.localtime(client.next_call_at).strftime("%d.%m.%Y %H:%M") if client.next_call_at else "–",
        },
        "lead_id": lead_id,
    }
    payload.update(_stats_payload(request.user))
    return JsonResponse(payload)
