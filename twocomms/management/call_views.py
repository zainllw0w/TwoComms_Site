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

# --- Кеш записів у памʼяті процесу --------------------------------------
# Перемотка (seek) у HTML5-плеєрі вимагає HTTP Range; браузер робить кілька
# range-запитів на той самий файл. Щоб не тягнути mp3 з Binotel щоразу,
# тримаємо короткий кеш повних байтів (посилання Binotel живе ~15 хв).
import threading
import time as _time

_RECORD_CACHE: dict[int, tuple[bytes, str, float]] = {}
_RECORD_CACHE_LOCK = threading.Lock()
_RECORD_CACHE_TTL = 12 * 60  # 12 хв (менше за час життя посилання Binotel)
_RECORD_CACHE_MAX_ITEMS = 8
_RECORD_CACHE_MAX_BYTES = 80 * 1024 * 1024  # ~80 МБ сумарно


def _record_cache_get(record_id: int):
    now = _time.time()
    with _RECORD_CACHE_LOCK:
        item = _RECORD_CACHE.get(record_id)
        if not item:
            return None
        data, ctype, ts = item
        if now - ts > _RECORD_CACHE_TTL:
            _RECORD_CACHE.pop(record_id, None)
            return None
        return data, ctype


def _record_cache_put(record_id: int, data: bytes, ctype: str):
    now = _time.time()
    with _RECORD_CACHE_LOCK:
        # прибираємо протерміноване
        for rid in [k for k, (_d, _c, ts) in _RECORD_CACHE.items() if now - ts > _RECORD_CACHE_TTL]:
            _RECORD_CACHE.pop(rid, None)
        _RECORD_CACHE[record_id] = (data, ctype, now)
        # обмеження за кількістю
        while len(_RECORD_CACHE) > _RECORD_CACHE_MAX_ITEMS:
            oldest = min(_RECORD_CACHE.items(), key=lambda kv: kv[1][2])[0]
            _RECORD_CACHE.pop(oldest, None)
        # обмеження за обсягом
        total = sum(len(d) for d, _c, _ts in _RECORD_CACHE.values())
        while total > _RECORD_CACHE_MAX_BYTES and len(_RECORD_CACHE) > 1:
            oldest = min(_RECORD_CACHE.items(), key=lambda kv: kv[1][2])[0]
            total -= len(_RECORD_CACHE[oldest][0])
            _RECORD_CACHE.pop(oldest, None)


def _parse_range(range_header: str, size: int):
    """Парсить заголовок 'Range: bytes=start-end'. Повертає (start, end) або None."""
    if not range_header:
        return None
    rng = range_header.strip()
    if not rng.lower().startswith("bytes="):
        return None
    spec = rng.split("=", 1)[1].split(",")[0].strip()
    if "-" not in spec:
        return None
    start_s, end_s = spec.split("-", 1)
    try:
        if start_s == "":
            # suffix range: останні N байтів
            n = int(end_s)
            if n <= 0:
                return None
            start = max(0, size - n)
            end = size - 1
        else:
            start = int(start_s)
            end = int(end_s) if end_s else size - 1
    except ValueError:
        return None
    if start > end or start >= size:
        return None
    end = min(end, size - 1)
    return start, end


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
        CallRecord.objects.filter(matched_client=client)
        .prefetch_related("ai_analyses")
        .order_by("-started_at", "-created_at")[:50]
    )
    session_record_ids = list(
        CallSession.objects.filter(client=client, call_record__isnull=False)
        .values_list("call_record_id", flat=True)
    )
    if session_record_ids:
        extra = (
            CallRecord.objects.filter(id__in=session_record_ids)
            .exclude(id__in=[r.id for r in records])
            .prefetch_related("ai_analyses")
        )
        records.extend(list(extra))
    records.sort(key=lambda r: (r.started_at or r.created_at), reverse=True)

    def _latest_done(rec):
        # ai_analyses вже prefetch'нуті — фільтруємо в памʼяті (без N+1)
        best = None
        for an in rec.ai_analyses.all():
            if an.status == "done" and (best is None or an.created_at > best.created_at):
                best = an
        return best

    items = []
    for r in records:
        recordable = (r.payload or {}).get("disposition", "").upper() in {"ANSWER", "VM-SUCCESS", "SUCCESS", "TRANSFER"}
        analysis = _latest_done(r) if is_admin else None
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
                "discrepancies": analysis.discrepancies or [],
                "extracted_facts": analysis.extracted_facts or {},
            }
        items.append(item)
    return JsonResponse({"success": True, "calls": items, "is_admin": is_admin})


@login_required(login_url="management_login")
@require_GET
def call_recording(request, record_id):
    """Стрім запису розмови з перевіркою доступу (менеджер — лише свої).

    Підтримує HTTP Range (206 Partial Content), тож HTML5-плеєр уміє
    перемотувати запис. Повні байти кешуються у памʼяті процесу на кілька
    хвилин, щоб серія range-запитів не смикала Binotel щоразу.
    """
    if not user_is_management(request.user):
        return HttpResponse(status=403)
    record = CallRecord.objects.filter(id=record_id).select_related("matched_client").first()
    if not record or not record.external_call_id:
        return HttpResponse("not found", status=404)
    if not _can_access_call_record(request.user, record):
        return HttpResponse(status=403)

    cached = _record_cache_get(record.id)
    if cached is not None:
        data, content_type = cached
    else:
        try:
            binotel = BinotelClient.from_settings()
            data, content_type = binotel.fetch_record_bytes(record.external_call_id)
        except BinotelNotConfigured:
            return HttpResponse("telephony off", status=503)
        except BinotelError as exc:
            return HttpResponse(str(exc), status=404, content_type="text/plain; charset=utf-8")
        if data:
            _record_cache_put(record.id, data, content_type)

    size = len(data)
    is_download = request.GET.get("download") in ("1", "true", "yes")
    disposition = (
        f'attachment; filename="call_{record_id}.mp3"' if is_download else "inline"
    )

    rng = _parse_range(request.META.get("HTTP_RANGE", ""), size) if size else None
    if rng is not None:
        start, end = rng
        chunk = data[start:end + 1]
        resp = HttpResponse(chunk, status=206, content_type=content_type)
        resp["Content-Range"] = f"bytes {start}-{end}/{size}"
        resp["Content-Length"] = str(len(chunk))
    else:
        resp = HttpResponse(data, content_type=content_type)
        resp["Content-Length"] = str(size)

    resp["Accept-Ranges"] = "bytes"
    resp["Cache-Control"] = "private, max-age=600"
    resp["Content-Disposition"] = disposition
    return resp
