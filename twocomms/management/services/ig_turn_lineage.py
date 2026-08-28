"""Контекст ходу клієнта для телеметрії провайдера (ЭА.1).

`GeminiRequestAttempt` зберігав `request_id`, ключ, модель і клас відказу, але
не зберігав, до якого клієнта, ходу, holding-а чи recovery це відноситься. Через
це ланцюг «вхідне → спроби → holding → recovery → receipt» не будувався
запитом, а значить жодну правку спаму технічних вибачень не можна було довести.

Контекст задає ВИКЛИКАЮЧИЙ шар (він єдиний знає, що це за хід), а точка запису
попытки лише читає його. Значення не вгадуються по стеку.

Чому ContextVar, а не додаткові параметри: між шаром, що знає хід
(`_process_one_inside_reply_boundary`), і точкою запису
(`gemini_keys.record_attempt`) чотири рівні викликів
(`gemini_generate` → `gemini_generate_text` → `_run_chat_with_pool` → `_audit`),
частина з яких — спільний код для ролей, що не мають ходу клієнта взагалі.
ContextVar залишає підпис спільного коду незмінним і безпечний у потоках
демона: новий потік починає з порожнього контексту.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar


class Lane:
    LIVE = "live"
    HOLDING = "holding"
    RECOVERY = "recovery"
    ANALYSIS = "analysis"
    METADATA_PROBE = "metadata_probe"
    FOLLOWUP = "followup"


_EMPTY: dict = {}

_turn_context: ContextVar[dict] = ContextVar("ig_turn_lineage", default=_EMPTY)


def logical_turn_key(client_id, source_message_id) -> str:
    """Стабільний ключ логічного ходу клієнта.

    Тимчасове мінімальне визначення: хід — це найраніше вхідне без відповіді.
    Усі вхідні, що прийшли поки бот ще не відповів, належать одному ходу, тому
    сума вибачень у ході рахується коректно навіть при burst-і повідомлень.
    Коли з'явиться `CustomerTurn` (Э0.6), цей ключ треба замінити на його id —
    саме тому він ізольований в одній функції.
    """
    try:
        client_id = int(client_id or 0)
        source_message_id = int(source_message_id or 0)
    except (TypeError, ValueError):
        return ""
    if not client_id or not source_message_id:
        return ""
    return f"t{client_id}:{source_message_id}"


def resolve_logical_turn_key(row) -> str:
    """Ключ ходу для вхідного рядка: найраніше вхідне без відповіді бота."""
    client_id = getattr(row, "client_id", None)
    row_id = getattr(row, "pk", None)
    if not client_id or not row_id:
        return ""
    from management.models import InstagramBotMessage

    last_outgoing = (
        InstagramBotMessage.objects.filter(
            client_id=client_id,
            role__in=(
                InstagramBotMessage.Role.MODEL,
                InstagramBotMessage.Role.MANAGER,
            ),
            id__lt=row_id,
        )
        .order_by("-id")
        .values_list("id", flat=True)
        .first()
    ) or 0
    turn_anchor = (
        InstagramBotMessage.objects.filter(
            client_id=client_id,
            role=InstagramBotMessage.Role.USER,
            id__gt=last_outgoing,
            id__lte=row_id,
        )
        .order_by("id")
        .values_list("id", flat=True)
        .first()
    ) or row_id
    return logical_turn_key(client_id, turn_anchor)


def current_context() -> dict:
    return dict(_turn_context.get() or _EMPTY)


@contextmanager
def turn_lineage(
    *,
    lane: str,
    client_id=None,
    source_message_id=None,
    logical_turn_id: str = "",
    incident_id=None,
    recovery_job_id=None,
):
    """Позначити провайдерські виклики цього блоку контекстом ходу."""
    payload = {
        "lane": str(lane or "")[:16],
        "client_id": int(client_id) if client_id else None,
        "source_message_id": int(source_message_id) if source_message_id else None,
        "logical_turn_id": str(logical_turn_id or "")[:64],
        "incident_id": int(incident_id) if incident_id else None,
        "recovery_job_id": int(recovery_job_id) if recovery_job_id else None,
    }
    token = _turn_context.set(payload)
    try:
        yield payload
    finally:
        _turn_context.reset(token)


def bind_request_id(request_id: str) -> None:
    """Запам'ятати `request_id` поточного провайдерського запиту для ходу."""
    context = _turn_context.get()
    if context is _EMPTY or not isinstance(context, dict):
        return
    context["request_id"] = str(request_id or "")[:40]


def current_request_id() -> str:
    context = _turn_context.get()
    if not isinstance(context, dict):
        return ""
    return str(context.get("request_id") or "")
