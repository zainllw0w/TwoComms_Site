"""
Менеджерські endpoint'и click-to-call (доступні всім management-користувачам,
не лише адмінам — на відміну від binotel_views, що є адмін-пісочницею).
"""
from __future__ import annotations

import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .models import CallSession, Client, ManagementLead
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
