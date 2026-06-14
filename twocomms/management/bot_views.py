"""
Вкладка «Бот» (тільки для адміністраторів).

UI зі станом агента (запущено/зупинено, очікує повідомлення), кнопками
Start/Stop, вибором джерела ключів і онлайн-консоллю подій.
"""
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from .models import InstagramBotLog, InstagramBotSettings
from .services import instagram_bot as bot


def _is_admin(user) -> bool:
    return bool(user.is_authenticated and (user.is_staff or user.is_superuser))


def _require_admin_json(request):
    if not _is_admin(request.user):
        return JsonResponse({"success": False, "error": "Доступ лише для адміністраторів."}, status=403)
    return None


def _log_items(limit: int = 80):
    rows = InstagramBotLog.objects.all()[:limit]
    return [
        {
            "id": r.id,
            "level": r.level,
            "event": r.event,
            "detail": r.detail,
            "time": r.created_at.strftime("%H:%M:%S"),
            "date": r.created_at.strftime("%d.%m.%Y"),
        }
        for r in rows
    ]


@login_required(login_url="management_login")
def bot_dashboard(request):
    if not _is_admin(request.user):
        return redirect("management_home")
    settings_obj = InstagramBotSettings.load()
    return render(
        request,
        "management/bot.html",
        {
            "settings": settings_obj,
            "status": bot.status_snapshot(),
            "log_items": _log_items(),
            "cred_env": InstagramBotSettings.CredSource.ENV,
            "cred_custom": InstagramBotSettings.CredSource.CUSTOM,
        },
    )


@login_required(login_url="management_login")
@require_POST
def bot_start_api(request):
    blocked = _require_admin_json(request)
    if blocked:
        return blocked
    bot.start_bot()
    return JsonResponse({"success": True, "status": bot.status_snapshot()})


@login_required(login_url="management_login")
@require_POST
def bot_stop_api(request):
    blocked = _require_admin_json(request)
    if blocked:
        return blocked
    bot.stop_bot()
    return JsonResponse({"success": True, "status": bot.status_snapshot()})


@login_required(login_url="management_login")
@require_GET
def bot_status_api(request):
    blocked = _require_admin_json(request)
    if blocked:
        return blocked
    try:
        after_id = int(request.GET.get("after_id") or 0)
    except (TypeError, ValueError):
        after_id = 0

    rows = InstagramBotLog.objects.all()
    if after_id:
        rows = rows.filter(id__gt=after_id)
    rows = list(rows[:120])
    rows.reverse()  # від старіших до новіших для дозапису в консоль
    items = [
        {
            "id": r.id,
            "level": r.level,
            "event": r.event,
            "detail": r.detail,
            "time": r.created_at.strftime("%H:%M:%S"),
        }
        for r in rows
    ]
    return JsonResponse({"success": True, "status": bot.status_snapshot(), "log": items})


@login_required(login_url="management_login")
@require_POST
def bot_settings_save_api(request):
    blocked = _require_admin_json(request)
    if blocked:
        return blocked
    s = InstagramBotSettings.load()

    direct_source = (request.POST.get("direct_source") or "").strip()
    if direct_source in InstagramBotSettings.CredSource.values:
        s.direct_source = direct_source
    gemini_source = (request.POST.get("gemini_source") or "").strip()
    if gemini_source in InstagramBotSettings.CredSource.values:
        s.gemini_source = gemini_source

    if "custom_direct_token" in request.POST:
        s.custom_direct_token = (request.POST.get("custom_direct_token") or "").strip()
    if "custom_gemini_key" in request.POST:
        s.custom_gemini_key = (request.POST.get("custom_gemini_key") or "").strip()

    trigger = (request.POST.get("trigger_text") or "").strip()
    if trigger:
        s.trigger_text = trigger[:255]
    reply = (request.POST.get("reply_text") or "").strip()
    if reply:
        s.reply_text = reply[:1000]

    # AI-режим / модель / правило / білий список.
    s.ai_enabled = (request.POST.get("ai_enabled") or "").strip() in {"1", "true", "on", "yes"}
    s.receive_via_poll = (request.POST.get("receive_via_poll") or "").strip() in {"1", "true", "on", "yes"}
    model = (request.POST.get("gemini_model") or "").strip()
    if model:
        s.gemini_model = model[:80]
    if "system_prompt" in request.POST:
        s.system_prompt = (request.POST.get("system_prompt") or "").strip()
    if "knowledge_base" in request.POST:
        s.knowledge_base = (request.POST.get("knowledge_base") or "").strip()
    if "allowed_senders" in request.POST:
        s.allowed_senders = (request.POST.get("allowed_senders") or "").strip()

    try:
        interval = int(request.POST.get("poll_interval_seconds") or s.poll_interval_seconds)
        s.poll_interval_seconds = max(2, min(60, interval))
    except (TypeError, ValueError):
        pass

    s.save()
    # Скинути кеш токена/кулдаун, щоб новий токен підхопився одразу.
    try:
        from django.core.cache import cache
        cache.delete("ig_bot_page_token")
        cache.delete("ig_bot_pt_cooldown")
        cache.delete("ig_bot_ll_user_token")
        cache.delete("ig_bot_pt_errsig")
    except Exception:
        pass
    bot.log(
        "info",
        "settings_saved",
        f"ai={s.ai_enabled}, model={s.gemini_model}, direct={s.direct_source}, gemini={s.gemini_source}",
    )
    return JsonResponse({"success": True, "status": bot.status_snapshot()})
