from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any

from django.utils import timezone

from management.models import Client


CONTACT_CHANNEL_LABELS = {
    "phone": "Телефон",
    "messenger": "Месенджер",
    "email": "E-mail",
}

OUTCOME_REASON_SCHEMA: dict[str, dict[str, Any]] = {
    Client.CallResult.NOT_INTERESTED: {
        "label": "Чому клієнту не цікаво",
        "hint": "Заповнена причина допомагає чесніше рахувати якість бази та рейтинг менеджера.",
        "options": [
            {"code": "current_supplier", "label": "Працюють з іншим постачальником"},
            {"code": "no_demand", "label": "Немає попиту"},
            {"code": "wrong_assortment", "label": "Не підходить асортимент"},
            {"code": "season_not_now", "label": "Не сезон / не на часі"},
            {"code": "not_wholesale", "label": "Не працюють по гурту"},
            {"code": "policy_block", "label": "Внутрішня політика / заборона"},
            {"code": "other", "label": "Інша причина"},
        ],
        "note_label": "Що саме сказав клієнт",
        "note_placeholder": "Коротко зафіксуйте аргумент клієнта або важливий контекст",
        "note_required_for": {"other"},
    },
    Client.CallResult.EXPENSIVE: {
        "label": "Що саме дорого",
        "hint": "Це дає адмінці зрозуміти, де проблема: ціна, MOQ, логістика чи умови.",
        "options": [
            {"code": "price_high", "label": "Зависока ціна"},
            {"code": "min_order", "label": "Не підходить мінімальне замовлення"},
            {"code": "payment_terms", "label": "Не підходять умови оплати"},
            {"code": "logistics", "label": "Дорога логістика"},
            {"code": "no_budget", "label": "Немає бюджету"},
            {"code": "supplier_cheaper", "label": "У поточного постачальника дешевше"},
            {"code": "other", "label": "Інша причина"},
        ],
        "note_label": "Деталізація заперечення",
        "note_placeholder": "Наприклад: просили нижчу MOQ, довший відтермін, дешевшу доставку",
        "note_required_for": {"other"},
    },
    Client.CallResult.NO_ANSWER: {
        "label": "Який саме сценарій",
        "hint": "Для недозвону обов'язково фіксуємо, скільки було спроб і через який канал.",
        "options": [
            {"code": "busy", "label": "Зайнято"},
            {"code": "no_reply", "label": "Не взяли слухавку"},
            {"code": "voicemail", "label": "Голосова пошта"},
            {"code": "secretary", "label": "Секретар / ресепшн"},
            {"code": "promised_callback", "label": "Пообіцяли передзвонити"},
            {"code": "other", "label": "Інший сценарій"},
        ],
        "note_label": "Уточнення по контакту",
        "note_placeholder": "Наприклад: відповіли в месенджері, але без рішення",
        "note_required_for": {"other"},
        "requires_attempts": True,
        "requires_channel": True,
    },
    Client.CallResult.INVALID_NUMBER: {
        "label": "Що саме з номером",
        "hint": "Це допомагає чистити базу без помилкових штрафів для менеджера.",
        "options": [
            {"code": "wrong_number", "label": "Невірний номер"},
            {"code": "disconnected", "label": "Номер відключено"},
            {"code": "not_serviced", "label": "Номер не обслуговується"},
            {"code": "blocked", "label": "Номер блокує дзвінки"},
            {"code": "other", "label": "Інша причина"},
        ],
        "note_label": "Коментар по номеру",
        "note_placeholder": "Коротко вкажіть, як це підтвердили",
        "note_required_for": {"other"},
    },
    Client.CallResult.OTHER: {
        "label": "Уточніть нетиповий результат",
        "hint": "Без пояснення нетиповий результат знижує якість даних.",
        "options": [
            {"code": "freeform", "label": "Нетиповий сценарій"},
        ],
        "note_label": "Що саме сталося",
        "note_placeholder": "Опишіть результат своїми словами",
        "note_required_for": {"freeform"},
    },
}

RESULTS_REQUIRING_REASON = frozenset(OUTCOME_REASON_SCHEMA.keys())


def get_outcome_reason_schema() -> dict[str, dict[str, Any]]:
    schema = deepcopy(OUTCOME_REASON_SCHEMA)
    for config in schema.values():
        if isinstance(config.get("note_required_for"), set):
            config["note_required_for"] = sorted(config["note_required_for"])
    return schema


def format_source_display(source: str, source_link: str, source_other: str) -> str:
    return {
        "instagram": "Instagram",
        "prom_ua": "Prom.ua",
        "google_maps": "Google Карти",
        "forums": f"Сайти/Форуми: {source_link}" if source_link else "Сайти/Форуми",
        "other": source_other or "Інше",
    }.get(source, source or "")


def next_call_at_from_request(data) -> datetime | None:
    next_call_type = data.get("next_call_type", "scheduled")
    if next_call_type == "no_follow":
        return None
    next_call_date = (data.get("next_call_date") or "").strip()
    next_call_time = (data.get("next_call_time") or "").strip()
    if not next_call_date or not next_call_time:
        return None
    try:
        naive = datetime.strptime(f"{next_call_date} {next_call_time}", "%Y-%m-%d %H:%M")
        return timezone.make_aware(naive, timezone.get_current_timezone())
    except ValueError:
        return None


def reason_label_for(call_result: str, reason_code: str) -> str:
    config = OUTCOME_REASON_SCHEMA.get(call_result) or {}
    for option in config.get("options", []):
        if option["code"] == reason_code:
            return option["label"]
    return reason_code or ""


def contact_channel_label(code: str) -> str:
    return CONTACT_CHANNEL_LABELS.get(code, code or "")


def reason_required_for(call_result: str) -> bool:
    return call_result in RESULTS_REQUIRING_REASON


def normalize_result_capture(
    *,
    call_result: str,
    role: str,
    role_custom: str,
    call_result_other: str,
    reason_code: str,
    reason_note: str,
    contact_attempts: str,
    contact_channel: str,
) -> dict[str, Any]:
    config = OUTCOME_REASON_SCHEMA.get(call_result) or {}
    valid_codes = {item["code"] for item in config.get("options", [])}
    normalized_reason_code = (reason_code or "").strip()
    normalized_reason_note = (reason_note or "").strip()
    normalized_other = (call_result_other or "").strip()
    normalized_role_custom = (role_custom or "").strip()
    normalized_contact_channel = (contact_channel or "").strip()
    errors: list[str] = []
    context: dict[str, Any] = {}

    if call_result == Client.CallResult.OTHER and not normalized_reason_note:
        normalized_reason_note = normalized_other

    if reason_required_for(call_result):
        if not normalized_reason_code and len(valid_codes) == 1:
            normalized_reason_code = next(iter(valid_codes))
        if normalized_reason_code not in valid_codes:
            errors.append("Оберіть причину результату.")

    if normalized_reason_code and normalized_reason_code in (config.get("note_required_for") or set()) and not normalized_reason_note:
        errors.append("Додайте уточнення до вибраної причини.")

    if call_result == Client.CallResult.NO_ANSWER:
        try:
            attempts_value = int((contact_attempts or "").strip() or 0)
        except ValueError:
            attempts_value = 0
        if attempts_value <= 0:
            errors.append("Для недозвону вкажіть кількість спроб.")
        else:
            context["attempts"] = attempts_value
        if normalized_contact_channel not in CONTACT_CHANNEL_LABELS:
            errors.append("Оберіть канал контакту для недозвону.")
        else:
            context["contact_channel"] = normalized_contact_channel

    if normalized_reason_note:
        context["note"] = normalized_reason_note

    details_parts: list[str] = []
    if role == Client.Role.OTHER and normalized_role_custom:
        details_parts.append(f"Роль: {normalized_role_custom}")
    if normalized_reason_code:
        label = reason_label_for(call_result, normalized_reason_code)
        if label:
            details_parts.append(f"Причина: {label}")
    if normalized_reason_note:
        details_parts.append(f"Уточнення: {normalized_reason_note}")
    if context.get("attempts"):
        details_parts.append(f"Спроб: {context['attempts']}")
    if context.get("contact_channel"):
        details_parts.append(f"Канал: {contact_channel_label(context['contact_channel'])}")
    if call_result == Client.CallResult.OTHER and normalized_other and normalized_other != normalized_reason_note:
        details_parts.append(f"Інше: {normalized_other}")

    return {
        "errors": errors,
        "reason_code": normalized_reason_code if normalized_reason_code in valid_codes else "",
        "reason_note": normalized_reason_note,
        "context": context,
        "details": "\n".join(details_parts),
    }


def summarize_reason_quality(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total_required = 0
    missing_reason = 0
    missing_detail = 0
    breakdown: dict[str, dict[str, int]] = {}
    issue_examples: list[dict[str, str]] = []

    for row in rows:
        call_result = str(row.get("call_result") or "")
        if not reason_required_for(call_result):
            continue
        total_required += 1
        reason_code = str(row.get("call_result_reason_code") or "").strip()
        reason_note = str(row.get("call_result_reason_note") or "").strip()
        context = row.get("call_result_context") or {}
        label = reason_label_for(call_result, reason_code)

        is_missing_reason = not reason_code
        is_missing_detail = False
        if call_result == Client.CallResult.NO_ANSWER and not context.get("attempts"):
            is_missing_detail = True
        config = OUTCOME_REASON_SCHEMA.get(call_result) or {}
        if reason_code and reason_code in (config.get("note_required_for") or set()) and not reason_note:
            is_missing_detail = True

        if is_missing_reason:
            missing_reason += 1
            if len(issue_examples) < 8:
                issue_examples.append({"call_result": call_result, "issue": "missing_reason"})
            continue
        if is_missing_detail:
            missing_detail += 1
            if len(issue_examples) < 8:
                issue_examples.append({"call_result": call_result, "issue": "missing_detail", "reason_code": reason_code})

        bucket = breakdown.setdefault(call_result, {})
        bucket[label or reason_code] = bucket.get(label or reason_code, 0) + 1

    if total_required == 0:
        reason_quality = 1.0
    else:
        confidence = min(1.0, total_required / 3.0)
        penalty = ((missing_reason / total_required) + 0.5 * (missing_detail / total_required)) * confidence
        reason_quality = max(0.0, 1.0 - min(1.0, penalty))

    structured_breakdown: list[dict[str, Any]] = []
    for call_result, labels in breakdown.items():
        structured_breakdown.append(
            {
                "call_result": call_result,
                "items": [
                    {"label": label, "count": count}
                    for label, count in sorted(labels.items(), key=lambda item: (-item[1], item[0]))
                ],
            }
        )

    return {
        "required_total": total_required,
        "missing_reason": missing_reason,
        "missing_detail": missing_detail,
        "reason_quality": round(reason_quality, 4),
        "breakdown": structured_breakdown,
        "issue_examples": issue_examples,
    }
