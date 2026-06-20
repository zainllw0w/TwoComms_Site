from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from .models import LeadAICheck, LeadCheckerSettings, ManagementLead
from .parsing_views import _require_admin_json
from .services import lead_check_job as ljob
from .services import lead_checker

RESULTS_PAGE_SIZE_OPTIONS = (10, 25, 50, 100)
DEFAULT_RESULTS_PAGE_SIZE = 25


def serialize_lead_check(lead: ManagementLead) -> dict:
    check = lead.ai_checks.order_by("-created_at").first()
    base = {
        "lead_id": lead.id,
        "shop_name": lead.shop_name,
        "city": lead.city,
        "website_url": lead.website_url,
        "google_maps_url": lead.google_maps_url,
        "phone": lead.phone,
        "ai_score": lead.ai_score,
        "ai_verdict": lead.ai_verdict or "",
        "niche_status": lead.niche_status,
        "status": lead.status,
    }
    if check is None:
        base.update({
            "check_status": "", "verdict_category": "", "partnership_fit": [],
            "confidence": "", "brand_summary": "", "audience_guess": "",
            "instagram_url": "", "comment": "", "recommendation": "",
            "criteria": [], "sources": [], "error": "", "model_used": "",
            "verdict_band": "", "collaboration_evidence": "", "signals": {},
            "checked_at": None,
        })
        return base
    base.update({
        "check_status": check.status,
        "verdict_category": check.verdict_category,
        "partnership_fit": check.partnership_fit or [],
        "confidence": check.confidence,
        "verdict_band": check.verdict_band,
        "collaboration_evidence": check.collaboration_evidence,
        "signals": check.signals or {},
        "brand_summary": check.brand_summary,
        "audience_guess": check.audience_guess,
        "instagram_url": check.instagram_url,
        "comment": check.comment,
        "recommendation": check.recommendation,
        "criteria": check.criteria or [],
        "sources": check.sources or [],
        "error": check.error,
        "model_used": check.model_used,
        "checked_at": check.created_at.isoformat() if check.created_at else None,
    })
    return base


@login_required(login_url="management_login")
@require_POST
def checker_start_api(request):
    denied = _require_admin_json(request)
    if denied:
        return denied
    try:
        job = ljob.create_check_job(
            user=request.user,
            scope=request.POST.get("scope", "unchecked"),
            city=request.POST.get("city", ""),
            band=request.POST.get("band", ""),
            target_limit=request.POST.get("target_limit", 0),
            requests_per_minute=request.POST.get("requests_per_minute", 8),
        )
    except ljob.CheckerServiceError as exc:
        return JsonResponse({"success": False, "error": str(exc)}, status=409)
    return JsonResponse({"success": True, "job": ljob.job_status_payload(job)})


@login_required(login_url="management_login")
@require_POST
def checker_step_api(request):
    denied = _require_admin_json(request)
    if denied:
        return denied
    job = ljob.dashboard_job(request.POST.get("job_id"))
    if job is None:
        return JsonResponse({"success": False, "error": "Сесію не знайдено."}, status=404)
    job = ljob.run_step(job)
    return JsonResponse({"success": True, "job": ljob.job_status_payload(job)})


def _simple_job_action(request, action):
    denied = _require_admin_json(request)
    if denied:
        return denied
    job_id = request.POST.get("job_id")
    if not job_id:
        return JsonResponse({"success": False, "error": "job_id обовʼязковий."}, status=400)
    try:
        job = action(job_id)
    except ljob.CheckerServiceError as exc:
        return JsonResponse({"success": False, "error": str(exc)}, status=409)
    except ljob.LeadCheckJob.DoesNotExist:
        return JsonResponse({"success": False, "error": "Сесію не знайдено."}, status=404)
    return JsonResponse({"success": True, "job": ljob.job_status_payload(job)})


@login_required(login_url="management_login")
@require_POST
def checker_pause_api(request):
    return _simple_job_action(request, ljob.pause_job)


@login_required(login_url="management_login")
@require_POST
def checker_resume_api(request):
    return _simple_job_action(request, ljob.resume_job)


@login_required(login_url="management_login")
@require_POST
def checker_stop_api(request):
    return _simple_job_action(request, ljob.stop_job)


@login_required(login_url="management_login")
@require_GET
def checker_status_api(request):
    denied = _require_admin_json(request)
    if denied:
        return denied
    job = ljob.dashboard_job(request.GET.get("job_id"))
    return JsonResponse({"success": True, "job": ljob.job_status_payload(job)})


def _results_queryset(band, city):
    qs = ManagementLead.objects.filter(lead_source=ManagementLead.LeadSource.PARSER,
                                       ai_checked_at__isnull=False)
    if band and band != "all":
        qs = qs.filter(ai_verdict=band)
    if city:
        qs = qs.filter(city__iexact=city.strip())
    return qs.order_by("-ai_score", "-ai_checked_at")


@login_required(login_url="management_login")
@require_GET
def checker_results_api(request):
    denied = _require_admin_json(request)
    if denied:
        return denied
    band = request.GET.get("band", "all")
    city = request.GET.get("city", "")
    try:
        page = max(1, int(request.GET.get("page", 1)))
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = int(request.GET.get("page_size", DEFAULT_RESULTS_PAGE_SIZE))
    except (TypeError, ValueError):
        page_size = DEFAULT_RESULTS_PAGE_SIZE
    if page_size not in RESULTS_PAGE_SIZE_OPTIONS:
        page_size = DEFAULT_RESULTS_PAGE_SIZE

    qs = _results_queryset(band, city).prefetch_related("ai_checks")
    paginator = Paginator(qs, page_size)
    page_obj = paginator.get_page(page)
    rows = [serialize_lead_check(lead) for lead in page_obj.object_list]
    return JsonResponse({"success": True, "results": {
        "rows": rows,
        "page": page_obj.number,
        "num_pages": paginator.num_pages,
        "total": paginator.count,
        "page_size": page_size,
        "band": band,
        "city": city,
    }})


@login_required(login_url="management_login")
@require_POST
def checker_recheck_api(request, lead_id):
    denied = _require_admin_json(request)
    if denied:
        return denied
    lead = ManagementLead.objects.filter(id=lead_id).first()
    if lead is None:
        return JsonResponse({"success": False, "error": "Лід не знайдено."}, status=404)
    api_key = ljob.resolve_checker_api_key() or None
    lead_checker.score_lead(lead, api_key=api_key, checked_by=request.user)
    lead.refresh_from_db()
    return JsonResponse({"success": True, "row": serialize_lead_check(lead)})


@login_required(login_url="management_login")
@require_POST
def checker_settings_api(request):
    denied = _require_admin_json(request)
    if denied:
        return denied
    s = LeadCheckerSettings.load()
    if "gemini_api_key" in request.POST:
        s.gemini_api_key = request.POST.get("gemini_api_key", "").strip()
    if request.POST.get("model_chain") is not None:
        s.model_chain = request.POST.get("model_chain", "").strip()
    try:
        s.requests_per_minute = max(1, min(20, int(request.POST.get("requests_per_minute", s.requests_per_minute))))
    except (TypeError, ValueError):
        pass
    if "auto_recheck" in request.POST:
        s.auto_recheck = request.POST.get("auto_recheck") in ("1", "true", "on", "True")
    try:
        if request.POST.get("auto_recheck_batch") is not None:
            s.auto_recheck_batch = max(1, min(500, int(request.POST.get("auto_recheck_batch", s.auto_recheck_batch))))
    except (TypeError, ValueError):
        pass
    s.save()
    return JsonResponse({"success": True, "settings": {
        "has_key": bool(s.gemini_api_key),
        "requests_per_minute": s.requests_per_minute,
        "model_chain": s.model_chain,
        "auto_recheck": s.auto_recheck,
        "auto_recheck_batch": s.auto_recheck_batch,
    }})


@login_required(login_url="management_login")
@require_GET
def checker_keys_status_api(request):
    denied = _require_admin_json(request)
    if denied:
        return denied
    from .services import gemini_keys
    return JsonResponse({"success": True, "keys": gemini_keys.pool_status()})


def checker_context(request) -> dict:
    """Контекст AI-чекера для вбудовування у сторінку «Лідоген»."""
    job = ljob.dashboard_job()
    settings_obj = LeadCheckerSettings.load()
    cities = list(
        ManagementLead.objects.filter(lead_source=ManagementLead.LeadSource.PARSER)
        .exclude(city="").values_list("city", flat=True).distinct().order_by("city")[:300]
    )
    counters = {
        "checked": ManagementLead.objects.filter(lead_source=ManagementLead.LeadSource.PARSER, ai_checked_at__isnull=False).count(),
        "unchecked": ManagementLead.objects.filter(lead_source=ManagementLead.LeadSource.PARSER, ai_checked_at__isnull=True).count(),
        "fit": ManagementLead.objects.filter(ai_verdict="fit").count(),
        "maybe": ManagementLead.objects.filter(ai_verdict="maybe").count(),
        "unfit": ManagementLead.objects.filter(ai_verdict="unfit").count(),
        "errors": ManagementLead.objects.filter(ai_verdict="error").count(),
    }
    return {
        "checker_active_job_json": ljob.job_status_payload(job),
        "checker_counters": counters,
        "checker_cities": cities,
        "checker_settings": {
            "has_key": bool(settings_obj.gemini_api_key),
            "requests_per_minute": settings_obj.requests_per_minute,
            "model_chain": settings_obj.model_chain,
            "auto_recheck": settings_obj.auto_recheck,
            "auto_recheck_batch": settings_obj.auto_recheck_batch,
        },
    }


@login_required(login_url="management_login")
def checker_dashboard(request):
    # Чекер злитий зі сторінкою «Лідоген» (Парсинг). Єдина вкладка.
    return redirect("management_parsing")

