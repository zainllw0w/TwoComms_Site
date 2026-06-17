"""
Сервіс вихідних дзвінків менеджера (click-to-call через Binotel).

Потік:
  1. Менеджер тисне «Подзвонити» у формі обробки клієнта/ліда.
  2. start_outbound_call(): бере лінію менеджера (UserProfile.binotel_internal_number),
     викликає Binotel internal_to_external (Binotel дзвонить на софтфон менеджера,
     потім з'єднує з клієнтом), створює CallSession з generalCallID.
  3. poll_call_status(): опитує stats/call-details за generalCallID, оновлює статус.
  4. hangup_call(): завершує дзвінок.
  5. Пізніше webhook apiCallCompleted прив'яже CallRecord до CallSession за generalCallID.

Маппінг менеджер→лінія Binotel зберігається в UserProfile.binotel_internal_number
(задає адмін). Без лінії дзвінок неможливий — повертаємо зрозумілу помилку.
"""
from __future__ import annotations

import logging

from django.utils import timezone

from management.models import CallSession, Client, ManagementLead
from management.models import normalize_phone as model_normalize_phone
from management.services.binotel import BinotelClient, BinotelError, BinotelNotConfigured

logger = logging.getLogger("binotel")

# Disposition'и, що означають завершення дзвінка.
_FINAL_DISPOSITIONS = {
    "ANSWER", "BUSY", "NOANSWER", "CANCEL", "CONGESTION",
    "CHANUNAVAIL", "VM", "VM-SUCCESS", "FAILED", "SUCCESS",
}
_TALKING_DISPOSITIONS = {"ONLINE"}


class CallStartError(Exception):
    """Не вдалося ініціювати дзвінок (немає лінії / Binotel / лінія офлайн)."""


def get_manager_internal_number(user) -> str:
    profile = getattr(user, "userprofile", None)
    return (getattr(profile, "binotel_internal_number", "") or "").strip()


def manager_can_call(user) -> bool:
    return bool(get_manager_internal_number(user)) and BinotelClient.is_configured()


def start_outbound_call(
    user,
    phone: str,
    *,
    client: Client | None = None,
    lead: ManagementLead | None = None,
    no_playback: bool = True,
) -> CallSession:
    """Ініціює дзвінок менеджер→клієнт. Повертає CallSession або кидає CallStartError."""
    internal_number = get_manager_internal_number(user)
    if not internal_number:
        raise CallStartError(
            "Вам не призначено лінію Binotel. Зверніться до адміністратора, "
            "щоб він вказав ваш внутрішній номер у профілі."
        )
    phone = (phone or "").strip()
    phone_normalized = model_normalize_phone(phone)
    if not phone_normalized:
        raise CallStartError("Невірний номер телефону клієнта.")

    # Не дозволяємо паралельні активні дзвінки в одного менеджера.
    active = (
        CallSession.objects.filter(
            manager=user,
            status__in=[CallSession.Status.DIALING, CallSession.Status.RINGING, CallSession.Status.TALKING],
        )
        .order_by("-started_at")
        .first()
    )
    if active and (timezone.now() - active.started_at).total_seconds() < 600:
        raise CallStartError("У вас вже є активний дзвінок. Завершіть його перед новим.")

    try:
        binotel = BinotelClient.from_settings()
    except BinotelNotConfigured as exc:
        raise CallStartError("IP-телефонію не налаштовано на сервері.") from exc

    extra = {}
    if no_playback:
        extra["playbackWaiting"] = "FALSE"

    try:
        data = binotel.internal_to_external(internal_number, phone_normalized, **extra)
    except BinotelError as exc:
        hint = f" — {exc.hint}" if getattr(exc, "hint", "") else ""
        raise CallStartError(f"Binotel: {exc}{hint}") from exc

    general_call_id = str(data.get("generalCallID") or "").strip()
    session = CallSession.objects.create(
        manager=user,
        client=client,
        lead=lead,
        provider="binotel",
        internal_number=internal_number,
        phone=phone_normalized,
        phone_normalized=phone_normalized,
        general_call_id=general_call_id,
        status=CallSession.Status.DIALING,
        meta={"raw_start": data},
    )
    return session


def poll_call_status(session: CallSession) -> CallSession:
    """Опитує статус дзвінка в Binotel і оновлює CallSession."""
    if not session.general_call_id:
        return session
    if session.status in (CallSession.Status.ENDED, CallSession.Status.FAILED):
        return session
    try:
        binotel = BinotelClient.from_settings()
        data = binotel.call_details(session.general_call_id)
    except (BinotelError, BinotelNotConfigured):
        return session

    details = data.get("callDetails")
    entry = None
    if isinstance(details, dict):
        entry = details.get(session.general_call_id) or details.get(str(session.general_call_id))
    if not isinstance(entry, dict):
        return session

    disposition = str(entry.get("disposition") or "").strip()
    billsec = int(entry.get("billsec") or 0)
    changed = []
    if disposition and disposition != session.disposition:
        session.disposition = disposition
        changed.append("disposition")
    if billsec and billsec != session.duration_seconds:
        session.duration_seconds = billsec
        changed.append("duration_seconds")

    if disposition in _TALKING_DISPOSITIONS and session.status != CallSession.Status.TALKING:
        session.status = CallSession.Status.TALKING
        if not session.answered_at:
            session.answered_at = timezone.now()
            changed.append("answered_at")
        changed.append("status")
    elif disposition in _FINAL_DISPOSITIONS and session.status != CallSession.Status.ENDED:
        session.status = CallSession.Status.ENDED
        session.ended_at = timezone.now()
        changed.extend(["status", "ended_at"])

    if changed:
        session.save(update_fields=list(set(changed)) + ["updated_at"])
    return session


def hangup_call(session: CallSession) -> CallSession:
    if session.general_call_id:
        try:
            binotel = BinotelClient.from_settings()
            binotel.hangup_call(session.general_call_id)
        except (BinotelError, BinotelNotConfigured):
            pass
    if session.status not in (CallSession.Status.ENDED, CallSession.Status.FAILED):
        session.status = CallSession.Status.ENDED
        session.ended_at = timezone.now()
        session.save(update_fields=["status", "ended_at", "updated_at"])
    return session


def attach_session_to_client(*, manager, session_id, client: Client) -> CallSession | None:
    """Прив'язує сесію дзвінка до збереженого клієнта (викликається при сабміті форми)."""
    if not session_id:
        return None
    try:
        session = CallSession.objects.get(id=session_id, manager=manager)
    except (CallSession.DoesNotExist, ValueError, TypeError):
        return None
    session.client = client
    session.save(update_fields=["client", "updated_at"])
    return session


def serialize_session(session: CallSession) -> dict:
    return {
        "session_id": session.id,
        "general_call_id": session.general_call_id,
        "status": session.status,
        "status_display": session.get_status_display(),
        "disposition": session.disposition,
        "duration_seconds": session.duration_seconds,
        "phone": session.phone,
        "client_id": session.client_id,
        "lead_id": session.lead_id,
        "is_active": session.status in (
            CallSession.Status.DIALING, CallSession.Status.RINGING, CallSession.Status.TALKING
        ),
    }
