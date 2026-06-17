"""
Єдиний вхідний вебхук Binotel.

Binotel розрізняє два типи вебхуків, але обидва можна спрямувати на ОДИН URL —
ми розрізняємо їх за полем ``requestType`` у тілі POST:

  • ``apiCallSettings``  — приходить ДО з'єднання (вхідний/вихідний дзвінок).
    Очікує JSON-відповідь з карткою клієнта (customerData) та/або маршрутом
    (routeData). Використовується, щоб показати менеджеру, хто дзвонить, і
    спрямувати дзвінок на закріпленого менеджера.

  • ``apiCallCompleted`` — приходить ПІСЛЯ завершення кожного дзвінка з повною
    структурою callDetails. МАЄ повернути ``{"status":"success"}``, інакше
    Binotel повторить доставку 7 разів (одразу, +20хв, +1г, +2г, +6г, +14г, +38г).

Безпека: підпису немає, тож довіряємо лише whitelist IP Binotel + звіряємо
companyID. На тестовій фазі enforcement IP вимкнено (BINOTEL_WEBHOOK_ENFORCE_IP),
але кожен запит логуємо разом з detected IP, щоб згодом увімкнути блокування.

Endpoint НІКОЛИ не повертає 5xx — будь-яка внутрішня помилка ловиться, подія
логується, а Binotel отримує валідну відповідь.
"""
from __future__ import annotations

import json
import logging

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import BinotelWebhookEvent, CallRecord, Client
from .models import normalize_phone as model_normalize_phone
from .services.binotel import (
    client_ip_from_request,
    is_binotel_ip,
    parse_webhook_call_details,
)

logger = logging.getLogger("binotel")


def _json_body(request) -> dict:
    """Binotel шле raw JSON, але буває і form-urlencoded — підтримуємо обидва."""
    ctype = (request.content_type or "").lower()
    if "application/json" in ctype or not request.POST:
        try:
            body = request.body.decode("utf-8") or "{}"
            data = json.loads(body)
            if isinstance(data, dict):
                return data
        except (ValueError, UnicodeDecodeError):
            pass
    return request.POST.dict()


def _match_client(external_number: str):
    """Шукає Client за нормалізованим номером або останніми 7 цифрами."""
    norm = model_normalize_phone(external_number or "")
    if not norm:
        return None
    qs = Client.objects.filter(phone_normalized=norm).order_by("id")
    client = qs.first()
    if client:
        return client
    last7 = norm[-7:] if len(norm) >= 7 else norm
    if last7:
        return Client.objects.filter(phone_last7=last7).order_by("id").first()
    return None


def _handle_call_settings(payload: dict, event: BinotelWebhookEvent) -> dict:
    """apiCallSettings → картка клієнта для екрана менеджера."""
    external = payload.get("externalNumber") or ""
    client = _match_client(external)
    if not client:
        # Невідомий клієнт — повертаємо порожньо (Binotel це допускає).
        return {}

    customer_data = {"name": (client.shop_name or "")[:43]}
    owner = getattr(client, "owner", None)
    if owner and getattr(owner, "email", ""):
        customer_data["assignedToEmployeeEmail"] = owner.email
    base = getattr(settings, "MANAGEMENT_BASE_URL", "https://management.twocomms.shop").rstrip("/")
    customer_data["linkToCrmUrl"] = f"{base}/?client={client.id}"
    customer_data["linkToCrmTitle"] = "Відкрити в TwoComms"
    if client.id:
        event.handled_ok = True
    return {"customerData": customer_data}


def _handle_call_completed(payload: dict, event: BinotelWebhookEvent) -> dict:
    """apiCallCompleted → зберігаємо/оновлюємо CallRecord. Завжди success."""
    call_details = payload.get("callDetails")
    if not isinstance(call_details, dict):
        # Інколи callDetails може бути обгорнутий або відсутній — фіксуємо як є.
        return {"status": "success"}

    parsed = parse_webhook_call_details(call_details)
    gcid = parsed.get("general_call_id")
    if not gcid:
        return {"status": "success"}

    started_at = None
    if parsed.get("start_time"):
        try:
            started_at = timezone.datetime.fromtimestamp(
                int(parsed["start_time"]), tz=timezone.get_current_timezone()
            )
        except (TypeError, ValueError, OSError):
            started_at = None

    client = _match_client(parsed.get("external_number") or "")

    defaults = {
        "phone": parsed.get("external_number") or "",
        "direction": parsed.get("direction") or CallRecord.Direction.UNKNOWN,
        "duration_seconds": int(parsed.get("bill_seconds") or 0),
        "payload": call_details,
        "matched_client": client,
    }
    if started_at:
        defaults["started_at"] = started_at

    record, _created = CallRecord.objects.update_or_create(
        provider="binotel",
        external_call_id=gcid,
        defaults=defaults,
    )

    # Прив'язка до сесії click-to-call (якщо дзвінок ішов з картки клієнта):
    # переносимо менеджера/клієнта з сесії й позначаємо запис у чергу на ШІ-аналіз.
    _link_call_session_and_enqueue(record, parsed)

    event.handled_ok = True
    return {"status": "success"}


def _link_call_session_and_enqueue(record, parsed: dict) -> None:
    """Зв'язує CallRecord із CallSession за generalCallID і ставить у чергу
    авто-аналізу значущі відповіді (duration >= поріг, запис доступний)."""
    from .models import CallSession

    disposition = (parsed.get("disposition") or "").upper()
    duration = int(parsed.get("bill_seconds") or 0)
    recordable = disposition in {"ANSWER", "VM-SUCCESS", "SUCCESS", "TRANSFER"}
    meaningful = duration >= 30

    update_fields = []
    session = (
        CallSession.objects.filter(general_call_id=record.external_call_id)
        .order_by("-started_at")
        .first()
    )
    if session:
        if not session.call_record_id:
            session.call_record = record
        session.status = CallSession.Status.ENDED
        if not session.ended_at:
            session.ended_at = timezone.now()
        session.disposition = disposition
        session.duration_seconds = duration or session.duration_seconds
        session.save(update_fields=["call_record", "status", "ended_at", "disposition", "duration_seconds", "updated_at"])
        # перенести менеджера/клієнта з сесії на запис (надійніше за матч по номеру)
        if session.manager_id and not record.manager_id:
            record.manager_id = session.manager_id
            update_fields.append("manager")
        if session.client_id and not record.matched_client_id:
            record.matched_client_id = session.client_id
            update_fields.append("matched_client")

    if recordable and meaningful and record.ai_status == CallRecord.AiStatus.NONE:
        record.ai_status = CallRecord.AiStatus.PENDING
        update_fields.append("ai_status")

    if update_fields:
        update_fields.append("updated_at")
        record.save(update_fields=update_fields)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def binotel_webhook(request, token: str = ""):
    # GET — health-check (зручно перевірити URL у браузері).
    if request.method == "GET":
        return JsonResponse({"status": "ok", "service": "binotel-webhook"})

    expected_token = getattr(settings, "BINOTEL_WEBHOOK_TOKEN", "") or ""
    if expected_token and token != expected_token:
        return HttpResponse(status=404)

    remote_ip = client_ip_from_request(request)
    ip_allowed = is_binotel_ip(remote_ip)

    payload = _json_body(request)
    request_type = str(payload.get("requestType") or "").strip() or "unknown"

    # generalCallID може бути на верхньому рівні або всередині callDetails.
    gcid = str(payload.get("generalCallID") or "")
    if not gcid and isinstance(payload.get("callDetails"), dict):
        gcid = str(payload["callDetails"].get("generalCallID") or "")

    event = BinotelWebhookEvent(
        request_type=request_type
        if request_type in BinotelWebhookEvent.RequestType.values
        else BinotelWebhookEvent.RequestType.UNKNOWN,
        company_id=str(payload.get("companyID") or ""),
        general_call_id=gcid,
        call_type=str(payload.get("callType") or ""),
        external_number=str(payload.get("externalNumber") or ""),
        internal_number=str(payload.get("internalNumber") or ""),
        remote_ip=remote_ip,
        ip_allowed=ip_allowed,
        payload=payload if isinstance(payload, dict) else {"_raw": str(payload)[:4000]},
    )

    # Enforcement IP — лише якщо ввімкнено в ENV (на тестовій фазі вимкнено).
    if getattr(settings, "BINOTEL_WEBHOOK_ENFORCE_IP", False) and not ip_allowed:
        event.error = f"IP {remote_ip} не у whitelist Binotel"
        try:
            event.save()
        except Exception:
            logger.exception("binotel webhook: failed to log rejected event")
        return HttpResponse("forbidden", status=403)

    response_data: dict = {"status": "success"}
    try:
        if request_type == "apiCallSettings":
            response_data = _handle_call_settings(payload, event)
        elif request_type == "apiCallCompleted":
            response_data = _handle_call_completed(payload, event)
        else:
            logger.info("binotel webhook: unknown requestType=%s", request_type)
            response_data = {"status": "success"}
    except Exception as exc:  # ніколи не 5xx — Binotel інакше ретраїтиме
        logger.exception("binotel webhook handler error")
        event.error = str(exc)[:1000]
        response_data = {"status": "success"}

    event.response_payload = response_data if isinstance(response_data, dict) else {}
    try:
        event.save()
    except Exception:
        logger.exception("binotel webhook: failed to persist event")

    return JsonResponse(response_data)
