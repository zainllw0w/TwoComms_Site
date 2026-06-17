"""
Менеджерські endpoint'и click-to-call (доступні всім management-користувачам,
не лише адмінам — на відміну від binotel_views, що є адмін-пісочницею).
"""
from __future__ import annotations

import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse, StreamingHttpResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .models import CallRecord, CallSession, Client, ManagementLead
from .services.binotel import BinotelClient, BinotelError, BinotelNotConfigured
from .services.telephony_call import (
    CallStartError,
    hangup_call,
    manager_can_call,
    poll_call_status,
    serialize_session,
    start_outbound_call,
)
from .views import user_is_management


def _json_body(request) -> dict:
    ctype = (request.content_type or "").lower()
    if "application/json" in ctype:
        try:
            return json.loads(request.body.decode("utf-8") or "{}")
        except (ValueError, UnicodeDecodeError):
            return {}
    return request.POST.dict()


def _require_manager(request):
    if not user_is_management(request.user):
        return JsonResponse({"success": False, "error": "Доступ лише для менеджерів."}, status=403)
    return None


@login_required(login_url="management_login")
@require_POST
def call_start(request):
    blocked = _require_manager(request)
    if blocked:
        return blocked
    payload = _json_body(request)
    phone = str(payload.get("phone") or "").strip()
    if not phone:
        return JsonResponse({"success": False, "error": "Вкажіть номер телефону."}, status=400)

    client = None
    lead = None
    client_id = payload.get("client_id")
    lead_id = payload.get("lead_id")
    if client_id:
        client = Client.objects.filter(id=client_id).first()
    if lead_id:
        lead = ManagementLead.objects.filter(id=lead_id).first()

    try:
        session = start_outbound_call(request.user, phone, client=client, lead=lead)
    except CallStartError as exc:
        return JsonResponse({"success": False, "error": str(exc)}, status=200)

    return JsonResponse({"success": True, "session": serialize_session(session)})


@login_required(login_url="management_login")
@require_POST
def call_status(request):
    blocked = _require_manager(request)
    if blocked:
        return blocked
    payload = _json_body(request)
    session_id = payload.get("session_id")
    try:
        session = CallSession.objects.get(id=session_id, manager=request.user)
    except (CallSession.DoesNotExist, ValueError, TypeError):
        return JsonResponse({"success": False, "error": "Сесію не знайдено."}, status=404)
    session = poll_call_status(session)
    return JsonResponse({"success": True, "session": serialize_session(session)})


@login_required(login_url="management_login")
@require_POST
def call_hangup(request):
    blocked = _require_manager(request)
    if blocked:
        return blocked
    payload = _json_body(request)
    session_id = payload.get("session_id")
    try:
        session = CallSession.objects.get(id=session_id, manager=request.user)
    except (CallSession.DoesNotExist, ValueError, TypeError):
        return JsonResponse({"success": False, "error": "Сесію не знайдено."}, status=404)
    session = hangup_call(session)
    return JsonResponse({"success": True, "session": serialize_session(session)})


@login_required(login_url="management_login")
def call_can(request):
    """Чи може менеджер дзвонити (чи призначено лінію + чи налаштовано Binotel)."""
    if not user_is_management(request.user):
        return JsonResponse({"success": False, "can_call": False}, status=403)
    return JsonResponse({"success": True, "can_call": manager_can_call(request.user)})


def _can_access_call_record(user, record) -> bool:
    """Доступ до запису: адмін — будь-який; менеджер — лише свої дзвінки
    або дзвінки клієнтів, якими він володіє."""
    if user.is_staff or user.is_superuser:
        return True
    if record.manager_id and record.manager_id == user.id:
        return True
    mc = record.matched_client
    if mc and mc.owner_id == user.id:
        return True
    return False


@login_required(login_url="management_login")
@require_GET
def client_calls(request):
    """Список дзвінків клієнта для картки обробки.

    Менеджеру повертаємо метадані + доступ до прослуховування, але БЕЗ балів
    (приватність оцінок — лише адмін). Адмін бачить бали/вердикт ШІ.
    """
    if not user_is_management(request.user):
        return JsonResponse({"success": False, "error": "Доступ заборонено."}, status=403)
    client_id = request.GET.get("client_id")
    if not client_id:
        return JsonResponse({"success": False, "error": "client_id обовʼязковий."}, status=400)
    client = Client.objects.filter(id=client_id).first()
    if not client:
        return JsonResponse({"success": False, "error": "Клієнта не знайдено."}, status=404)
    is_admin = bool(request.user.is_staff or request.user.is_superuser)
    if not is_admin and client.owner_id != request.user.id:
        return JsonResponse({"success": False, "error": "Це не ваш клієнт."}, status=403)

    # дзвінки за матчем клієнта АБО через сесії click-to-call цього клієнта
    records = list(
        CallRecord.objects.filter(matched_client=client).order_by("-started_at", "-created_at")[:50]
    )
    session_record_ids = list(
        CallSession.objects.filter(client=client, call_record__isnull=False)
        .values_list("call_record_id", flat=True)
    )
    if session_record_ids:
        extra = CallRecord.objects.filter(id__in=session_record_ids).exclude(
            id__in=[r.id for r in records]
        )
        records.extend(list(extra))
    records.sort(key=lambda r: (r.started_at or r.created_at), reverse=True)

    items = []
    for r in records:
        recordable = (r.payload or {}).get("disposition", "").upper() in {"ANSWER", "VM-SUCCESS", "SUCCESS", "TRANSFER"}
        analysis = r.ai_analyses.filter(status="done").order_by("-created_at").first() if is_admin else None
        item = {
            "id": r.id,
            "started_at": timezone.localtime(r.started_at).strftime("%d.%m.%Y %H:%M") if r.started_at else "",
            "duration": r.duration_seconds,
            "direction": r.direction,
            "manager": (r.manager.get_full_name() or r.manager.username) if r.manager_id else "",
            "has_recording": bool(r.external_call_id) and recordable,
            "recording_url": f"/api/call/recording/{r.id}.mp3" if r.external_call_id else "",
            "ai_status": r.ai_status,
        }
        if is_admin and analysis:
            item["ai"] = {
                "overall_score": float(analysis.overall_score),
                "verdict": analysis.verdict,
                "summary": analysis.summary,
            }
        items.append(item)
    return JsonResponse({"success": True, "calls": items, "is_admin": is_admin})


@login_required(login_url="management_login")
@require_GET
def call_recording(request, record_id):
    """Стрім запису розмови з перевіркою доступу (менеджер — лише свої)."""
    if not user_is_management(request.user):
        return HttpResponse(status=403)
    record = CallRecord.objects.filter(id=record_id).select_related("matched_client").first()
    if not record or not record.external_call_id:
        return HttpResponse("not found", status=404)
    if not _can_access_call_record(request.user, record):
        return HttpResponse(status=403)
    try:
        binotel = BinotelClient.from_settings()
        upstream, _url = binotel.fetch_record_stream(record.external_call_id)
    except BinotelNotConfigured:
        return HttpResponse("telephony off", status=503)
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
    resp = StreamingHttpResponse(_stream(), content_type=content_type)
    length = upstream.headers.get("Content-Length")
    if length:
        resp["Content-Length"] = length
    resp["Cache-Control"] = "no-store"
    if request.GET.get("download") in ("1", "true", "yes"):
        resp["Content-Disposition"] = f'attachment; filename="call_{record_id}.mp3"'
    else:
        resp["Content-Disposition"] = "inline"
    return resp
