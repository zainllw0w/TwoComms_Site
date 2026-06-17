"""
Вкладка «Тест» (тільки для адміністраторів) — пісочниця для інтеграції Binotel.

Дозволяє вручну перевіряти всі основні методи Binotel REST API 4.0:
ініціювати дзвінки, опитувати статус, отримувати посилання на записи розмов,
дивитися онлайн-дзвінки, статистику за період, список співробітників тощо.

Усі ендпоінти доступні лише staff/superuser. Реальні дзвінки виконуються
через ключі з ENV (BINOTEL_API_KEY / BINOTEL_API_SECRET).
"""
from __future__ import annotations

import json
import time

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, StreamingHttpResponse, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from .services.binotel import (
    BINOTEL_ERROR_MESSAGES,
    DISPOSITION_META,
    BinotelClient,
    BinotelError,
    BinotelNotConfigured,
)

# Дозволені для generic-консолі ендпоінти (whitelist, щоб не дати викликати
# деструктивні методи на кшталт customers/delete з тестової сторінки).
ALLOWED_RAW_ENDPOINTS = {
    "settings/list-of-employees",
    "settings/list-of-voice-files",
    "settings/list-of-routes",
    "calls/internal-number-to-external-number",
    "calls/external-number-to-external-number",
    "calls/hangup-call",
    "calls/attended-call-transfer",
    "calls/call-with-announcement",
    "stats/online-calls",
    "stats/call-details",
    "stats/call-record",
    "stats/list-of-calls-for-period",
    "stats/list-of-calls-per-day",
    "stats/list-of-calls-by-internal-number-for-period",
    "stats/recent-calls-by-internal-number",
    "stats/list-of-lost-calls-for-today",
    "stats/history-by-external-number",
    "customers/search",
    "customers/list",
}


def _is_admin(user) -> bool:
    return bool(user.is_authenticated and (user.is_staff or user.is_superuser))


def _require_admin_json(request):
    if not _is_admin(request.user):
        return JsonResponse(
            {"success": False, "error": "Доступ лише для адміністраторів."}, status=403
        )
    return None


def _client_or_error():
    """Повертає (client, None) або (None, JsonResponse) якщо ключі не задані."""
    try:
        return BinotelClient.from_settings(), None
    except BinotelNotConfigured as exc:
        return None, JsonResponse(
            {
                "success": False,
                "configured": False,
                "error": str(exc),
            },
            status=400,
        )


def _error_response(exc: BinotelError):
    return JsonResponse(
        {
            "success": False,
            "error": str(exc),
            "code": exc.code,
            "hint": exc.hint,
            "raw": exc.raw,
        },
        status=200,  # 200 — щоб фронт показав текст помилки Binotel, а не generic 500
    )


def _annotate_dispositions(call_details):
    """Додає людські лейбли disposition до кожного дзвінка (для UI)."""
    if not isinstance(call_details, dict):
        return call_details
    for call in call_details.values():
        if isinstance(call, dict):
            disp = call.get("disposition") or ""
            meta = DISPOSITION_META.get(disp)
            if meta:
                call["_dispositionLabel"] = meta["label_uk"]
                call["_dispositionGroup"] = meta["group"]
                call["_dispositionFinal"] = meta["final"]
    return call_details


def _post_json(request) -> dict:
    """Підтримує і form-urlencoded, і application/json тіло."""
    ctype = (request.content_type or "").lower()
    if "application/json" in ctype:
        try:
            return json.loads(request.body.decode("utf-8") or "{}")
        except (ValueError, UnicodeDecodeError):
            return {}
    return request.POST.dict()


# --- сторінка ----------------------------------------------------------


@login_required(login_url="management_login")
def binotel_test(request):
    if not _is_admin(request.user):
        return redirect("management_home")
    base = (getattr(settings, "MANAGEMENT_BASE_URL", "") or "https://management.twocomms.shop").rstrip("/")
    token = getattr(settings, "BINOTEL_WEBHOOK_TOKEN", "") or ""
    webhook_path = f"/binotel/webhook/{token}/" if token else "/binotel/webhook/"
    context = {
        "binotel_configured": BinotelClient.is_configured(),
        "binotel_company_id": getattr(settings, "BINOTEL_COMPANY_ID", "") or "",
        "binotel_api_base": getattr(settings, "BINOTEL_API_BASE", ""),
        "binotel_api_version": getattr(settings, "BINOTEL_API_VERSION", ""),
        "binotel_error_codes": BINOTEL_ERROR_MESSAGES,
        "allowed_raw_endpoints": sorted(ALLOWED_RAW_ENDPOINTS),
        "binotel_webhook_url": f"{base}{webhook_path}",
        "binotel_webhook_enforce_ip": bool(getattr(settings, "BINOTEL_WEBHOOK_ENFORCE_IP", False)),
        "binotel_recording_base": "/binotel/recording/",
    }
    return render(request, "management/binotel_test.html", context)


# --- AJAX --------------------------------------------------------------


@login_required(login_url="management_login")
@require_GET
def binotel_status(request):
    """Перевірка конфігурації + ping (list-of-employees)."""
    blocked = _require_admin_json(request)
    if blocked:
        return blocked
    if not BinotelClient.is_configured():
        return JsonResponse(
            {
                "success": True,
                "configured": False,
                "reachable": False,
                "key_present": bool(getattr(settings, "BINOTEL_API_KEY", "")),
                "secret_present": bool(getattr(settings, "BINOTEL_API_SECRET", "")),
                "company_present": bool(getattr(settings, "BINOTEL_COMPANY_ID", "")),
                "message": "Ключі Binotel не задані в ENV "
                "(BINOTEL_API_KEY / BINOTEL_API_SECRET).",
            }
        )
    client, err = _client_or_error()
    if err:
        return err
    try:
        data = client.list_of_employees()
    except BinotelError as exc:
        return JsonResponse(
            {
                "success": True,
                "configured": True,
                "reachable": True,
                "auth_ok": False,
                "error": str(exc),
                "code": exc.code,
            }
        )
    employees = data.get("listOfEmployees") or {}
    return JsonResponse(
        {
            "success": True,
            "configured": True,
            "reachable": True,
            "auth_ok": True,
            "employees_count": len(employees),
        }
    )


@login_required(login_url="management_login")
@require_GET
def binotel_employees(request):
    blocked = _require_admin_json(request)
    if blocked:
        return blocked
    client, err = _client_or_error()
    if err:
        return err
    try:
        data = client.list_of_employees()
    except BinotelError as exc:
        return _error_response(exc)

    employees = []
    for email, emp in (data.get("listOfEmployees") or {}).items():
        endpoint = emp.get("endpointData") or {}
        employees.append(
            {
                "employeeID": emp.get("employeeID"),
                "email": emp.get("email") or email,
                "name": emp.get("name"),
                "department": emp.get("department"),
                "presenceState": emp.get("presenceState"),
                "internalNumber": endpoint.get("internalNumber"),
                "lineStatus": endpoint.get("status"),
            }
        )
    employees.sort(key=lambda e: (e.get("internalNumber") or ""))
    return JsonResponse({"success": True, "employees": employees, "raw": data})


@login_required(login_url="management_login")
@require_GET
def binotel_voice_files(request):
    blocked = _require_admin_json(request)
    if blocked:
        return blocked
    client, err = _client_or_error()
    if err:
        return err
    try:
        data = client.list_of_voice_files()
    except BinotelError as exc:
        return _error_response(exc)
    return JsonResponse({"success": True, "raw": data})


@login_required(login_url="management_login")
@require_POST
def binotel_call(request):
    """Ініціює дзвінок internal → external. Повертає generalCallID."""
    blocked = _require_admin_json(request)
    if blocked:
        return blocked
    payload = _post_json(request)
    internal_number = (payload.get("internalNumber") or "").strip()
    external_number = (payload.get("externalNumber") or "").strip()
    if not internal_number or not external_number:
        return JsonResponse(
            {"success": False, "error": "Потрібні internalNumber та externalNumber."},
            status=400,
        )
    extra = {}
    for key in ("pbxNumber", "limitCallTime", "callTimeToExt", "callerIdForEmployee"):
        val = (payload.get(key) or "").strip() if isinstance(payload.get(key), str) else payload.get(key)
        if val:
            extra[key] = val
    # playbackWaiting=FALSE прибирає голосове "очікуйте, з'єднання з оператором".
    pw = payload.get("playbackWaiting")
    if isinstance(pw, str):
        pw = pw.strip().lower()
        if pw in ("false", "0", "no"):
            extra["playbackWaiting"] = "FALSE"
        elif pw in ("true", "1", "yes"):
            extra["playbackWaiting"] = "TRUE"
    elif pw is False:
        extra["playbackWaiting"] = "FALSE"
    client, err = _client_or_error()
    if err:
        return err
    try:
        data = client.internal_to_external(internal_number, external_number, **extra)
    except BinotelError as exc:
        return _error_response(exc)
    return JsonResponse(
        {
            "success": True,
            "generalCallID": data.get("generalCallID"),
            "raw": data,
        }
    )


@login_required(login_url="management_login")
@require_POST
def binotel_hangup(request):
    blocked = _require_admin_json(request)
    if blocked:
        return blocked
    payload = _post_json(request)
    general_call_id = (str(payload.get("generalCallID") or "")).strip()
    if not general_call_id:
        return JsonResponse({"success": False, "error": "Потрібен generalCallID."}, status=400)
    client, err = _client_or_error()
    if err:
        return err
    try:
        data = client.hangup_call(general_call_id)
    except BinotelError as exc:
        return _error_response(exc)
    return JsonResponse({"success": True, "raw": data})


@login_required(login_url="management_login")
@require_POST
def binotel_call_details(request):
    blocked = _require_admin_json(request)
    if blocked:
        return blocked
    payload = _post_json(request)
    raw_ids = payload.get("generalCallID") or payload.get("generalCallIDs") or ""
    if isinstance(raw_ids, str):
        ids = [i.strip() for i in raw_ids.replace(";", ",").split(",") if i.strip()]
    elif isinstance(raw_ids, (list, tuple)):
        ids = [str(i).strip() for i in raw_ids if str(i).strip()]
    else:
        ids = [str(raw_ids)]
    if not ids:
        return JsonResponse({"success": False, "error": "Потрібен generalCallID."}, status=400)
    client, err = _client_or_error()
    if err:
        return err
    try:
        data = client.call_details(ids)
    except BinotelError as exc:
        return _error_response(exc)
    return JsonResponse({"success": True, "callDetails": _annotate_dispositions(data.get("callDetails")), "raw": data})


@login_required(login_url="management_login")
@require_POST
def binotel_call_record(request):
    """Посилання на запис розмови (час життя — 15 хв)."""
    blocked = _require_admin_json(request)
    if blocked:
        return blocked
    payload = _post_json(request)
    general_call_id = (str(payload.get("generalCallID") or "")).strip()
    if not general_call_id:
        return JsonResponse({"success": False, "error": "Потрібен generalCallID."}, status=400)
    client, err = _client_or_error()
    if err:
        return err
    try:
        data = client.call_record(general_call_id)
    except BinotelError as exc:
        return _error_response(exc)
    # Binotel може повернути посилання у полі url або всередині callDetails.
    url = data.get("url")
    if not url:
        details = data.get("callDetails")
        if isinstance(details, dict):
            url = details.get("url")
        elif isinstance(details, str):
            url = details
    return JsonResponse({"success": True, "url": url, "raw": data})


@login_required(login_url="management_login")
@require_GET
def binotel_online_calls(request):
    blocked = _require_admin_json(request)
    if blocked:
        return blocked
    client, err = _client_or_error()
    if err:
        return err
    try:
        data = client.online_calls()
    except BinotelError as exc:
        return _error_response(exc)
    return JsonResponse({"success": True, "callDetails": _annotate_dispositions(data.get("callDetails")), "raw": data})


@login_required(login_url="management_login")
@require_POST
def binotel_calls_period(request):
    """Дзвінки за період. start/stop — unix timestamp (сек)."""
    blocked = _require_admin_json(request)
    if blocked:
        return blocked
    payload = _post_json(request)
    internal_number = (str(payload.get("internalNumber") or "")).strip()
    try:
        start_time = int(payload.get("startTime"))
        stop_time = int(payload.get("stopTime"))
    except (TypeError, ValueError):
        return JsonResponse(
            {"success": False, "error": "Потрібні startTime та stopTime (unix timestamp)."},
            status=400,
        )
    client, err = _client_or_error()
    if err:
        return err
    try:
        if internal_number:
            data = client.list_of_calls_by_internal_number_for_period(
                internal_number, start_time, stop_time
            )
        else:
            data = client.list_of_calls_for_period(start_time, stop_time)
    except BinotelError as exc:
        return _error_response(exc)
    return JsonResponse({"success": True, "callDetails": _annotate_dispositions(data.get("callDetails")), "raw": data})


@login_required(login_url="management_login")
@require_POST
def binotel_customers_search(request):
    blocked = _require_admin_json(request)
    if blocked:
        return blocked
    payload = _post_json(request)
    subject = (str(payload.get("subject") or "")).strip()
    if not subject:
        return JsonResponse({"success": False, "error": "Потрібен subject (ім'я або номер)."}, status=400)
    client, err = _client_or_error()
    if err:
        return err
    try:
        data = client.customers_search(subject)
    except BinotelError as exc:
        return _error_response(exc)
    return JsonResponse({"success": True, "customerData": data.get("customerData"), "raw": data})


@login_required(login_url="management_login")
@require_POST
def binotel_raw(request):
    """Generic-консоль: довільний (whitelisted) метод + JSON-параметри."""
    blocked = _require_admin_json(request)
    if blocked:
        return blocked
    payload = _post_json(request)
    endpoint = (str(payload.get("endpoint") or "")).strip().strip("/")
    if endpoint not in ALLOWED_RAW_ENDPOINTS:
        return JsonResponse(
            {"success": False, "error": f"Метод '{endpoint}' не дозволений у тестовій консолі."},
            status=400,
        )
    params = payload.get("params") or {}
    if isinstance(params, str):
        try:
            params = json.loads(params or "{}")
        except ValueError:
            return JsonResponse({"success": False, "error": "params не є валідним JSON."}, status=400)
    if not isinstance(params, dict):
        return JsonResponse({"success": False, "error": "params має бути об'єктом JSON."}, status=400)
    client, err = _client_or_error()
    if err:
        return err
    started = time.monotonic()
    try:
        data = client.send_request(endpoint, params)
    except BinotelError as exc:
        return _error_response(exc)
    elapsed_ms = int((time.monotonic() - started) * 1000)
    return JsonResponse({"success": True, "raw": data, "elapsed_ms": elapsed_ms})


@login_required(login_url="management_login")
@require_GET
def binotel_recording(request, call_id):
    """
    Стрімить запис розмови через наш сервер (проксі).

    Чому проксі, а не пряме посилання Binotel:
    - посилання Binotel живе лише 15 хв і може бути http:// → mixed-content на
      нашій https-сторінці блокує відтворення;
    - проксі дає стабільне відтворення і коректне завантаження (download).

    Доступ лише staff. Програвання (inline) або завантаження (?download=1).
    """
    if not _is_admin(request.user):
        return HttpResponse(status=403)
    call_id = (str(call_id) or "").strip()
    if not call_id:
        return HttpResponse("generalCallID required", status=400)

    try:
        client = BinotelClient.from_settings()
    except BinotelNotConfigured:
        return HttpResponse("Binotel не налаштовано", status=503)

    try:
        upstream, _url = client.fetch_record_stream(call_id)
    except BinotelError as exc:
        return HttpResponse(str(exc), status=404, content_type="text/plain; charset=utf-8")

    def _stream():
        try:
            for chunk in upstream.iter_content(chunk_size=64 * 1024):
                if chunk:
                    yield chunk
        finally:
            upstream.close()

    content_type = upstream.headers.get("Content-Type") or "audio/mpeg"
    if "audio" not in content_type and "mpeg" not in content_type:
        content_type = "audio/mpeg"
    response = StreamingHttpResponse(_stream(), content_type=content_type)
    length = upstream.headers.get("Content-Length")
    if length:
        response["Content-Length"] = length
    response["Cache-Control"] = "no-store"
    response["Accept-Ranges"] = "none"
    if request.GET.get("download") in ("1", "true", "yes"):
        fname = f"binotel_call_{call_id}.mp3"
        response["Content-Disposition"] = f'attachment; filename="{fname}"'
    else:
        response["Content-Disposition"] = "inline"
    return response


@login_required(login_url="management_login")
@require_POST
def binotel_call_ai_analysis(request):
    """ШІ-аналіз запису розмови (Gemini). Тільки адміністратори.

    Body: {generalCallID, b2b_context?, force?}. Синхронно: апсертить
    CallRecord, тягне аудіо, шле в Gemini, зберігає CallAIAnalysis і повертає
    структурований розбор + метрики прогону (швидкість, токени, розмір аудіо).
    """
    blocked = _require_admin_json(request)
    if blocked:
        return blocked

    from .services.call_ai_analysis import (
        CallAIAnalysisError,
        analyze_call,
        serialize_analysis,
    )

    payload = _post_json(request)
    general_call_id = (str(payload.get("generalCallID") or "")).strip()
    if not general_call_id:
        return JsonResponse({"success": False, "error": "Потрібен generalCallID."}, status=400)
    manager_context = str(payload.get("b2b_context") or payload.get("manager_context") or "")
    force = str(payload.get("force") or "").strip().lower() in ("1", "true", "yes")

    try:
        analysis = analyze_call(
            general_call_id,
            manager_context=manager_context,
            force=force,
            created_by=request.user,
        )
    except CallAIAnalysisError as exc:
        return JsonResponse({"success": False, "error": str(exc)}, status=200)

    data = serialize_analysis(analysis)
    if analysis.status != "done":
        return JsonResponse(
            {"success": False, "error": analysis.error or "Аналіз не виконано.", "analysis": data},
            status=200,
        )
    return JsonResponse({"success": True, "analysis": data})


@login_required(login_url="management_login")
@require_GET
def binotel_webhook_events(request):
    """Останні вхідні вебхуки Binotel (для спостереження на тестовій фазі)."""
    blocked = _require_admin_json(request)
    if blocked:
        return blocked
    from .models import BinotelWebhookEvent

    try:
        after_id = int(request.GET.get("after_id") or 0)
    except (TypeError, ValueError):
        after_id = 0

    qs = BinotelWebhookEvent.objects.all()
    if after_id:
        qs = qs.filter(id__gt=after_id)
    rows = list(qs[:60])
    events = [
        {
            "id": r.id,
            "request_type": r.request_type,
            "company_id": r.company_id,
            "general_call_id": r.general_call_id,
            "call_type": r.call_type,
            "external_number": r.external_number,
            "internal_number": r.internal_number,
            "remote_ip": r.remote_ip,
            "ip_allowed": r.ip_allowed,
            "handled_ok": r.handled_ok,
            "error": r.error,
            "response_payload": r.response_payload,
            "payload": r.payload,
            "created_at": r.created_at.strftime("%d.%m.%Y %H:%M:%S"),
        }
        for r in rows
    ]
    return JsonResponse({
        "success": True,
        "events": events,
        "total": BinotelWebhookEvent.objects.count(),
        "enforce_ip": bool(getattr(settings, "BINOTEL_WEBHOOK_ENFORCE_IP", False)),
    })
