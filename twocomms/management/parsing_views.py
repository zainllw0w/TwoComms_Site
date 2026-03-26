from django.contrib.auth.decorators import login_required
from django.db import models, transaction
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .constants import TARGET_CLIENTS_DAY, TARGET_POINTS_DAY
from .models import Client, LeadParsingJob, LeadParsingResult, ManagementLead, normalize_phone
from .parser_usage import parser_usage_snapshot
from .parser_service import (
    ParsingServiceError,
    PLACES_INCLUDED_TYPE_CHOICES,
    STEP_LOCK_STALE_AFTER,
    create_parsing_job,
    effective_added_lead_count,
    parser_current_query_state_payload,
    parser_selected_included_types,
    parser_dashboard_job,
    parser_global_counters,
    parser_pause_job,
    parser_resume_job,
    parser_run_step,
    parser_stop_job,
    places_included_type_label,
    sanitize_history_lookback_days,
    sanitize_requests_per_minute,
    sanitize_target_leads_limit,
)
from .services.dedupe import DedupeZone, build_duplicate_conflict_payload, evaluate_duplicate_zone
from .views import get_manager_bot_username, get_reminders, get_user_stats


def _require_admin_json(request):
    if request.user.is_staff:
        return None
    return JsonResponse({"success": False, "error": "Доступ лише для адміністраторів."}, status=403)


def _lead_queue_payload(limit=150):
    moderation = [
        {
            "id": lead.id,
            "shop_name": lead.shop_name,
            "phone": lead.phone,
            "full_name": lead.full_name,
            "role": lead.role,
            "role_display": lead.get_role_display(),
            "source": lead.source,
            "website_url": lead.website_url,
            "city": lead.city,
            "keyword": lead.parser_keyword,
            "query": lead.parser_query,
            "details": lead.details,
            "comments": lead.comments,
            "niche_status": lead.niche_status,
            "niche_status_display": lead.get_niche_status_display(),
            "lead_source": lead.lead_source,
            "lead_source_display": lead.get_lead_source_display(),
            "requires_phone_completion": lead.requires_phone_completion,
            "created_at": timezone.localtime(lead.created_at).strftime("%d.%m.%Y %H:%M"),
        }
        for lead in ManagementLead.objects.filter(status=ManagementLead.Status.MODERATION)
        .select_related("added_by", "moderated_by")
        .order_by("-created_at")[:limit]
    ]
    rejected = [
        {
            "id": lead.id,
            "shop_name": lead.shop_name,
            "phone": lead.phone,
            "city": lead.city,
            "keyword": lead.parser_keyword,
            "source": lead.source,
            "website_url": lead.website_url,
            "reason": lead.rejection_reason,
            "niche_status": lead.niche_status,
            "created_at": timezone.localtime(lead.created_at).strftime("%d.%m.%Y %H:%M"),
            "updated_at": timezone.localtime(lead.updated_at).strftime("%d.%m.%Y %H:%M"),
        }
        for lead in ManagementLead.objects.filter(status=ManagementLead.Status.REJECTED).order_by("-updated_at")[:limit]
    ]
    return moderation, rejected


def _job_payload(job: LeadParsingJob | None) -> dict | None:
    if not job:
        return None
    now = timezone.now()
    next_step_eta_seconds = 0
    if job.next_step_not_before:
        next_step_eta_seconds = max(0, int((job.next_step_not_before - now).total_seconds()))
    elapsed_seconds = max(1.0, (now - job.started_at).total_seconds())
    current_rpm = round((job.request_count * 60) / elapsed_seconds, 1)
    results_qs = list(LeadParsingResult.objects.filter(job=job).order_by("-created_at")[:80])
    results = [
        {
            "id": item.id,
            "status": item.status,
            "status_display": item.get_status_display(),
            "keyword": item.keyword,
            "city": item.city,
            "place_name": item.place_name,
            "phone": item.phone,
            "website_url": item.website_url,
            "reason": item.reason,
            "reason_code": item.reason_code,
            "created_at": timezone.localtime(item.created_at).strftime("%H:%M:%S"),
        }
        for item in results_qs
    ]
    last_notice = ""
    for item in results_qs:
        if item.status == LeadParsingResult.ResultStatus.NOTICE or item.reason_code.startswith("query_"):
            last_notice = item.reason
            break
    return {
        "id": job.id,
        "status": job.status,
        "status_display": job.get_status_display(),
        "keywords": job.keywords,
        "cities": job.cities,
        "request_limit": job.request_limit,
        "target_leads_limit": job.target_leads_limit,
        "request_count": job.request_count,
        "requests_per_minute": job.requests_per_minute,
        "history_lookback_days": job.history_lookback_days,
        "save_no_phone_leads": job.save_no_phone_leads,
        "included_type": job.included_type,
        "included_types": parser_selected_included_types(job),
        "current_type_index": job.current_type_index,
        "current_type_label": places_included_type_label(job.included_type),
        "strict_type_filtering": job.strict_type_filtering,
        "effective_added_count": effective_added_lead_count(job),
        "request_success_count": job.request_success_count,
        "request_error_count": job.request_error_count,
        "current_keyword_index": job.current_keyword_index,
        "current_city_index": job.current_city_index,
        "current_query": job.current_query,
        "current_request_spec": job.current_request_spec or {},
        "current_query_state": parser_current_query_state_payload(job),
        "next_page_token": job.next_page_token,
        "next_step_not_before": timezone.localtime(job.next_step_not_before).isoformat() if job.next_step_not_before else "",
        "next_step_eta_seconds": next_step_eta_seconds,
        "next_step_eta_ms": next_step_eta_seconds * 1000,
        "current_rpm": current_rpm,
        "is_step_in_progress": job.is_step_in_progress,
        "heartbeat_at": timezone.localtime(job.heartbeat_at).strftime("%d.%m.%Y %H:%M:%S") if job.heartbeat_at else "",
        "last_step_started_at": timezone.localtime(job.last_step_started_at).strftime("%H:%M:%S") if job.last_step_started_at else "",
        "last_step_finished_at": timezone.localtime(job.last_step_finished_at).strftime("%H:%M:%S") if job.last_step_finished_at else "",
        "last_step_duration_ms": job.last_step_duration_ms,
        "retry_state": job.retry_state or {},
        "total_found": job.total_found,
        "no_phone_skipped": job.no_phone_skipped,
        "duplicate_skipped": job.duplicate_skipped,
        "duplicate_same_job_phone_skipped": job.duplicate_same_job_phone_skipped,
        "duplicate_same_job_place_skipped": job.duplicate_same_job_place_skipped,
        "duplicate_existing_client_skipped": job.duplicate_existing_client_skipped,
        "duplicate_existing_lead_skipped": job.duplicate_existing_lead_skipped,
        "recent_history_phone_skipped": job.recent_history_phone_skipped,
        "recent_history_place_skipped": job.recent_history_place_skipped,
        "saved_no_phone_to_moderation": job.saved_no_phone_to_moderation,
        "already_rejected_skipped": job.already_rejected_skipped,
        "added_to_moderation": job.added_to_moderation,
        "queries_exhausted_normal": job.queries_exhausted_normal,
        "queries_exhausted_anomaly": job.queries_exhausted_anomaly,
        "moved_to_bad": job.moved_to_bad,
        "last_error": job.last_error,
        "last_notice": last_notice,
        "stop_reason_code": job.stop_reason_code,
        "started_at": timezone.localtime(job.started_at).strftime("%d.%m.%Y %H:%M:%S"),
        "finished_at": timezone.localtime(job.finished_at).strftime("%d.%m.%Y %H:%M:%S") if job.finished_at else "",
        "results": results,
    }


def _counters_payload():
    counters = parser_global_counters()
    return {
        "moderation": counters.moderation,
        "base": counters.base,
        "converted": counters.converted,
        "rejected": counters.rejected,
        "unprocessed": counters.unprocessed,
    }


def _usage_payload():
    usage = parser_usage_snapshot()
    return {
        "provider_status": usage.provider_status,
        "sku": usage.sku,
        "field_mask_version": usage.field_mask_version,
        "free_monthly_calls": usage.free_monthly_calls,
        "local_30d_usage": usage.local_30d_usage,
        "current_billing_month_usage": usage.current_billing_month_usage,
        "google_project_usage": usage.google_project_usage,
    }


@login_required(login_url="management_login")
def parsing_dashboard(request):
    if not request.user.is_staff:
        return redirect("management_home")

    stats = get_user_stats(request.user)
    processed_today = stats["processed_today"]
    user_points_today = stats["points_today"]
    progress_clients_pct = min(100, int(processed_today / TARGET_CLIENTS_DAY * 100)) if TARGET_CLIENTS_DAY else 0
    progress_points_pct = min(100, int(user_points_today / TARGET_POINTS_DAY * 100)) if TARGET_POINTS_DAY else 0
    reminders = get_reminders(
        request.user,
        stats={
            "points_today": user_points_today,
            "processed_today": processed_today,
        },
        report_sent=False,
    )
    active_job = parser_dashboard_job()
    moderation, rejected = _lead_queue_payload()
    return render(
        request,
        "management/parsing.html",
        {
            "user_points_today": user_points_today,
            "user_points_total": stats["points_total"],
            "processed_today": processed_today,
            "target_clients": TARGET_CLIENTS_DAY,
            "target_points": TARGET_POINTS_DAY,
            "progress_clients_pct": progress_clients_pct,
            "progress_points_pct": progress_points_pct,
            "reminders": reminders,
            "manager_bot_username": get_manager_bot_username(),
            "active_job": active_job,
            "active_job_json": _job_payload(active_job),
            "moderation_leads": moderation,
            "rejected_leads": rejected,
            "parser_counters": _counters_payload(),
            "parser_usage": _usage_payload(),
            "places_included_type_choices": [item for item in PLACES_INCLUDED_TYPE_CHOICES if item[0]],
        },
    )


@login_required(login_url="management_login")
@require_POST
def parser_start_api(request):
    blocked = _require_admin_json(request)
    if blocked:
        return blocked
    try:
        request_limit = int((request.POST.get("request_limit") or "0").strip())
    except ValueError:
        request_limit = 0
    target_leads_limit = sanitize_target_leads_limit(request.POST.get("target_leads_limit"))
    requests_per_minute = sanitize_requests_per_minute(request.POST.get("requests_per_minute"))
    history_lookback_days = sanitize_history_lookback_days(request.POST.get("history_lookback_days"))
    try:
        job = create_parsing_job(
            user=request.user,
            keywords_raw=(request.POST.get("keywords") or "").strip(),
            cities_raw=(request.POST.get("cities") or "").strip(),
            request_limit=request_limit,
            target_leads_limit=target_leads_limit,
            requests_per_minute=requests_per_minute,
            history_lookback_days=history_lookback_days,
            save_no_phone_leads=request.POST.get("save_no_phone_leads"),
            included_types=request.POST.getlist("included_types"),
            included_type=request.POST.get("included_type"),
            strict_type_filtering=request.POST.get("strict_type_filtering"),
        )
    except ParsingServiceError as exc:
        current_job = parser_dashboard_job()
        status_code = 409 if current_job and current_job.status in {LeadParsingJob.Status.RUNNING, LeadParsingJob.Status.PAUSED} else 400
        return JsonResponse(
            {
                "success": False,
                "error": str(exc),
                "job": _job_payload(current_job),
                "usage": _usage_payload(),
            },
            status=status_code,
        )

    moderation, rejected = _lead_queue_payload()
    return JsonResponse(
        {
            "success": True,
            "job": _job_payload(job),
            "counters": _counters_payload(),
            "moderation": moderation,
            "rejected": rejected,
            "usage": _usage_payload(),
        }
    )


@login_required(login_url="management_login")
@require_POST
def parser_step_api(request):
    blocked = _require_admin_json(request)
    if blocked:
        return blocked
    job_id = request.POST.get("job_id")
    if not job_id:
        return JsonResponse({"success": False, "error": "job_id обов'язковий."}, status=400)

    try:
        job = LeadParsingJob.objects.get(id=job_id)
    except LeadParsingJob.DoesNotExist:
        return JsonResponse({"success": False, "error": "Сесію парсингу не знайдено."}, status=404)
    if job.status == LeadParsingJob.Status.RUNNING:
        now = timezone.now()
        if job.is_step_in_progress:
            step_started_at = job.last_step_started_at or job.heartbeat_at
            step_is_stale = bool(step_started_at and step_started_at <= now - STEP_LOCK_STALE_AFTER)
            if not step_is_stale:
                moderation, rejected = _lead_queue_payload()
                return JsonResponse(
                    {
                        "success": True,
                        "job": _job_payload(parser_dashboard_job(job_id=job_id)),
                        "counters": _counters_payload(),
                        "moderation": moderation,
                        "rejected": rejected,
                        "usage": _usage_payload(),
                    }
                )
        if job.next_step_not_before and now < job.next_step_not_before:
            moderation, rejected = _lead_queue_payload()
            return JsonResponse(
                {
                    "success": True,
                    "job": _job_payload(parser_dashboard_job(job_id=job_id)),
                    "counters": _counters_payload(),
                    "moderation": moderation,
                    "rejected": rejected,
                    "usage": _usage_payload(),
                }
            )
    parser_run_step(job)

    moderation, rejected = _lead_queue_payload()
    return JsonResponse(
        {
            "success": True,
            "job": _job_payload(parser_dashboard_job(job_id=job_id)),
            "counters": _counters_payload(),
            "moderation": moderation,
            "rejected": rejected,
            "usage": _usage_payload(),
        }
    )


@login_required(login_url="management_login")
@require_POST
def parser_pause_api(request):
    blocked = _require_admin_json(request)
    if blocked:
        return blocked
    job_id = request.POST.get("job_id")
    try:
        job = parser_pause_job(job_id)
    except LeadParsingJob.DoesNotExist:
        return JsonResponse({"success": False, "error": "Сесію не знайдено."}, status=404)
    except ParsingServiceError as exc:
        return JsonResponse({"success": False, "error": str(exc), "job": _job_payload(parser_dashboard_job(job_id=job_id))}, status=409)
    return JsonResponse({"success": True, "job": _job_payload(job), "usage": _usage_payload()})


@login_required(login_url="management_login")
@require_POST
def parser_resume_api(request):
    blocked = _require_admin_json(request)
    if blocked:
        return blocked
    job_id = request.POST.get("job_id")
    try:
        job = parser_resume_job(job_id)
    except LeadParsingJob.DoesNotExist:
        return JsonResponse({"success": False, "error": "Сесію не знайдено."}, status=404)
    except ParsingServiceError as exc:
        return JsonResponse({"success": False, "error": str(exc), "job": _job_payload(parser_dashboard_job(job_id=job_id))}, status=409)
    return JsonResponse({"success": True, "job": _job_payload(job), "usage": _usage_payload()})


@login_required(login_url="management_login")
@require_POST
def parser_stop_api(request):
    blocked = _require_admin_json(request)
    if blocked:
        return blocked
    job_id = request.POST.get("job_id")
    reason_code = (request.POST.get("reason_code") or "user_stop").strip() or "user_stop"
    try:
        job = parser_stop_job(job_id, reason_code=reason_code)
    except LeadParsingJob.DoesNotExist:
        return JsonResponse({"success": False, "error": "Сесію не знайдено."}, status=404)
    return JsonResponse({"success": True, "job": _job_payload(job), "usage": _usage_payload()})


@login_required(login_url="management_login")
@require_GET
def parser_status_api(request):
    blocked = _require_admin_json(request)
    if blocked:
        return blocked
    job_id = request.GET.get("job_id")
    job = parser_dashboard_job(job_id=job_id)
    moderation, rejected = _lead_queue_payload()
    return JsonResponse(
        {
            "success": True,
            "job": _job_payload(job),
            "counters": _counters_payload(),
            "moderation": moderation,
            "rejected": rejected,
            "usage": _usage_payload(),
        }
    )


@login_required(login_url="management_login")
@require_POST
def lead_moderation_action_api(request, lead_id: int):
    blocked = _require_admin_json(request)
    if blocked:
        return blocked

    action = (request.POST.get("action") or "").strip().lower()
    if action not in {"save", "approve", "reject"}:
        return JsonResponse({"success": False, "error": "Невідома дія."}, status=400)

    with transaction.atomic():
        try:
            lead = ManagementLead.objects.select_for_update().get(id=lead_id)
        except ManagementLead.DoesNotExist:
            return JsonResponse({"success": False, "error": "Лід не знайдено."}, status=404)

        lead.shop_name = (request.POST.get("shop_name") or lead.shop_name).strip()
        lead.full_name = (request.POST.get("full_name") or lead.full_name).strip()
        lead.source = (request.POST.get("source") or lead.source).strip()
        lead.website_url = (request.POST.get("website_url") or lead.website_url).strip()
        lead.city = (request.POST.get("city") or lead.city).strip()
        lead.comments = (request.POST.get("comments") or lead.comments).strip()
        lead.details = (request.POST.get("details") or lead.details).strip()
        role_value = (request.POST.get("role") or lead.role).strip()
        if role_value in Client.Role.values:
            lead.role = role_value
        niche_value = (request.POST.get("niche_status") or lead.niche_status).strip()
        if niche_value in ManagementLead.NicheStatus.values:
            lead.niche_status = niche_value

        raw_phone = (request.POST.get("phone") if "phone" in request.POST else lead.phone) or ""
        raw_phone = raw_phone.strip()
        phone_normalized = normalize_phone(raw_phone) if raw_phone else ""
        blank_phone_allowed = lead.requires_phone_completion and action in {"save", "reject"} and not raw_phone
        if phone_normalized:
            lead.phone = phone_normalized
            lead.requires_phone_completion = False
        elif blank_phone_allowed:
            lead.phone = ""
        elif action == "approve" and lead.requires_phone_completion and not raw_phone:
            return JsonResponse(
                {"success": False, "error": "Для підтвердження в базу потрібно вказати коректний номер телефону."},
                status=400,
            )
        else:
            return JsonResponse({"success": False, "error": "Некоректний номер телефону."}, status=400)

        duplicate_decision = evaluate_duplicate_zone(
            shop_name=lead.shop_name,
            phone=lead.phone,
            website_url=lead.website_url,
            owner=lead.added_by or request.user,
            exclude_lead_ids=[lead.id],
        )
        if duplicate_decision.zone in {DedupeZone.AUTO_BLOCK, DedupeZone.REVIEW}:
            return JsonResponse(
                build_duplicate_conflict_payload(
                    owner=request.user,
                    decision=duplicate_decision,
                    shop_name=lead.shop_name,
                    phone=phone_normalized,
                    payload={
                        "lead_id": lead.id,
                        "action": action,
                        "shop_name": lead.shop_name,
                        "full_name": lead.full_name,
                        "website_url": lead.website_url,
                        "phone": lead.phone,
                        "city": lead.city,
                        "source": lead.source,
                    },
                    auto_block_error="Такий лід або клієнт вже є у базі.",
                    review_error="Потрібна перевірка на дубль перед модерацією.",
                ),
                status=409,
            )

        if action == "approve":
            lead.status = ManagementLead.Status.BASE
            lead.moderated_by = request.user
            lead.approved_to_base_at = timezone.now()
            lead.rejection_reason = ""
        elif action == "reject":
            lead.status = ManagementLead.Status.REJECTED
            lead.moderated_by = request.user
            lead.rejection_reason = (request.POST.get("rejection_reason") or "").strip() or "Не відповідає вимогам"
            if lead.parser_job_id:
                LeadParsingJob.objects.filter(id=lead.parser_job_id).update(moved_to_bad=models.F("moved_to_bad") + 1)
        else:
            lead.moderated_by = request.user

        lead.save()

    moderation, rejected = _lead_queue_payload()
    return JsonResponse(
        {
            "success": True,
            "lead_id": lead_id,
            "status": lead.status,
            "moderation": moderation,
            "rejected": rejected,
            "counters": _counters_payload(),
        }
    )
