from django.contrib.auth.decorators import login_required
from django.db import models, transaction
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .constants import TARGET_CLIENTS_DAY, TARGET_POINTS_DAY
from .models import Client, LeadParsingJob, LeadParsingResult, ManagementLead, normalize_phone
from .parser_service import (
    ParsingServiceError,
    create_parsing_job,
    parser_global_counters,
    parser_run_step,
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
    results_qs = LeadParsingResult.objects.filter(job=job).order_by("-created_at")[:80]
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
            "created_at": timezone.localtime(item.created_at).strftime("%H:%M:%S"),
        }
        for item in results_qs
    ]
    return {
        "id": job.id,
        "status": job.status,
        "status_display": job.get_status_display(),
        "keywords": job.keywords,
        "cities": job.cities,
        "request_limit": job.request_limit,
        "request_count": job.request_count,
        "current_keyword_index": job.current_keyword_index,
        "current_city_index": job.current_city_index,
        "current_query": job.current_query,
        "next_page_token": job.next_page_token,
        "total_found": job.total_found,
        "no_phone_skipped": job.no_phone_skipped,
        "duplicate_skipped": job.duplicate_skipped,
        "already_rejected_skipped": job.already_rejected_skipped,
        "added_to_moderation": job.added_to_moderation,
        "moved_to_bad": job.moved_to_bad,
        "last_error": job.last_error,
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
    active_job = LeadParsingJob.objects.filter(status__in=[LeadParsingJob.Status.RUNNING, LeadParsingJob.Status.PAUSED]).order_by(
        "-started_at"
    ).first()
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
    try:
        job = create_parsing_job(
            user=request.user,
            keywords_raw=(request.POST.get("keywords") or "").strip(),
            cities_raw=(request.POST.get("cities") or "").strip(),
            request_limit=request_limit,
        )
    except ParsingServiceError as exc:
        return JsonResponse({"success": False, "error": str(exc)}, status=400)

    moderation, rejected = _lead_queue_payload()
    return JsonResponse(
        {
            "success": True,
            "job": _job_payload(job),
            "counters": _counters_payload(),
            "moderation": moderation,
            "rejected": rejected,
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

    with transaction.atomic():
        try:
            job = LeadParsingJob.objects.select_for_update().get(id=job_id)
        except LeadParsingJob.DoesNotExist:
            return JsonResponse({"success": False, "error": "Сесію парсингу не знайдено."}, status=404)
        parser_run_step(job)

    moderation, rejected = _lead_queue_payload()
    return JsonResponse(
        {
            "success": True,
            "job": _job_payload(LeadParsingJob.objects.get(id=job_id)),
            "counters": _counters_payload(),
            "moderation": moderation,
            "rejected": rejected,
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
        job = LeadParsingJob.objects.get(id=job_id)
    except LeadParsingJob.DoesNotExist:
        return JsonResponse({"success": False, "error": "Сесію не знайдено."}, status=404)
    if job.status == LeadParsingJob.Status.RUNNING:
        job.status = LeadParsingJob.Status.PAUSED
        job.save(update_fields=["status", "updated_at"])
    return JsonResponse({"success": True, "job": _job_payload(job)})


@login_required(login_url="management_login")
@require_POST
def parser_resume_api(request):
    blocked = _require_admin_json(request)
    if blocked:
        return blocked
    job_id = request.POST.get("job_id")
    try:
        job = LeadParsingJob.objects.get(id=job_id)
    except LeadParsingJob.DoesNotExist:
        return JsonResponse({"success": False, "error": "Сесію не знайдено."}, status=404)
    if job.status in {LeadParsingJob.Status.PAUSED, LeadParsingJob.Status.FAILED}:
        job.status = LeadParsingJob.Status.RUNNING
        job.last_error = ""
        job.save(update_fields=["status", "last_error", "updated_at"])
    return JsonResponse({"success": True, "job": _job_payload(job)})


@login_required(login_url="management_login")
@require_POST
def parser_stop_api(request):
    blocked = _require_admin_json(request)
    if blocked:
        return blocked
    job_id = request.POST.get("job_id")
    try:
        job = LeadParsingJob.objects.get(id=job_id)
    except LeadParsingJob.DoesNotExist:
        return JsonResponse({"success": False, "error": "Сесію не знайдено."}, status=404)
    if job.status in {LeadParsingJob.Status.RUNNING, LeadParsingJob.Status.PAUSED}:
        job.status = LeadParsingJob.Status.STOPPED
        job.finished_at = timezone.now()
        job.save(update_fields=["status", "finished_at", "updated_at"])
    return JsonResponse({"success": True, "job": _job_payload(job)})


@login_required(login_url="management_login")
@require_GET
def parser_status_api(request):
    blocked = _require_admin_json(request)
    if blocked:
        return blocked
    job_id = request.GET.get("job_id")
    if job_id:
        job = LeadParsingJob.objects.filter(id=job_id).first()
    else:
        job = LeadParsingJob.objects.filter(status__in=[LeadParsingJob.Status.RUNNING, LeadParsingJob.Status.PAUSED]).order_by(
            "-started_at"
        ).first()
    moderation, rejected = _lead_queue_payload()
    return JsonResponse(
        {
            "success": True,
            "job": _job_payload(job),
            "counters": _counters_payload(),
            "moderation": moderation,
            "rejected": rejected,
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

        raw_phone = (request.POST.get("phone") or lead.phone).strip()
        phone_normalized = normalize_phone(raw_phone)
        if not phone_normalized:
            return JsonResponse({"success": False, "error": "Некоректний номер телефону."}, status=400)
        lead.phone = phone_normalized

        duplicate_decision = evaluate_duplicate_zone(
            shop_name=lead.shop_name,
            phone=phone_normalized,
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
