from __future__ import annotations

import re


CONFIDENCE_BAND_LABELS = {
    "HIGH": "Висока",
    "MEDIUM": "Середня",
    "LOW": "Низька",
}

SURFACE_STATE_LABELS = {
    "ACTIVE": "АКТИВНО",
    "SHADOW": "ТІНЬОВИЙ",
    "DORMANT": "СПЛЯЧИЙ",
    "FROZEN": "ЗАМОРОЖЕНО",
    "STALE": "ЗАСТАРІЛО",
    "LOW_CONFIDENCE": "НИЗЬКА ДОВІРА",
    "PARTIAL": "ЧАСТКОВО",
}

TELEPHONY_STATUS_LABELS = {
    "healthy": "Здорово",
    "degraded": "Деградація",
    "outage": "Недоступно",
}

DTF_STATUS_LABELS = {
    "fresh": "Актуально",
    "degraded": "Деградація",
    "stale": "Застаріло",
}

PAYBACK_RISK_LABELS = {
    "high": "високий ризик",
    "watch": "під наглядом",
    "safe": "стабільно",
}

DRIVER_LABELS = {
    "pipeline_aging": "старіння воронки",
    "verified_coverage": "підтверджене покриття",
    "repeat_concentration": "концентрація повторних продажів",
    "recent_conversion_trend": "свіжий тренд конверсії",
    "pipeline_freshness": "свіжість воронки",
    "follow_up_load": "навантаження на передзвони",
}

INCIDENT_KEY_LABELS = {
    "SNAPSHOT_STALE": "Застарілий знімок",
    "DUPLICATE_QUEUE_BACKLOG": "Черга дублів",
    "REMINDER_STORM": "Перевантаження передзвонами",
    "TELEPHONY_OUTAGE": "Збій телефонії",
}

CHURN_BASIS_LABELS = {
    "logistic": "логістична модель",
    "interim": "тимчасовий зріз",
    "weibull": "модель Вейбулла",
}

READINESS_KEY_LABELS = {
    "result": "Результат",
    "source_fairness": "Справедливість джерел",
    "process": "Процес",
    "follow_up": "Передзвони",
    "data_quality": "Якість даних",
    "verified_communication": "Підтверджена комунікація",
}

READINESS_STATE_LABELS = {
    "active": "активно",
    "shadow": "тіньовий режим",
    "dormant": "сплячий режим",
    "frozen": "заморожено",
    "stale": "застаріло",
}

GATE_LEVEL_LABELS = {
    "Paid": "Оплачено",
    "Admin-confirmed": "Підтверджено адміністратором",
    "CRM-timestamped": "Підтверджено CRM-мітками",
    "Self-reported only": "Лише самозвіт",
}


def translate_confidence_band(value: str | None) -> str:
    return CONFIDENCE_BAND_LABELS.get(str(value or "").upper(), str(value or "—"))


def translate_surface_state(value: str | None) -> str:
    return SURFACE_STATE_LABELS.get(str(value or "").upper(), str(value or "—"))


def translate_telephony_status(value: str | None) -> str:
    return TELEPHONY_STATUS_LABELS.get(str(value or "").lower(), str(value or "—"))


def translate_dtf_status(value: str | None) -> str:
    return DTF_STATUS_LABELS.get(str(value or "").lower(), str(value or "—"))


def translate_payback_risk(value: str | None) -> str:
    return PAYBACK_RISK_LABELS.get(str(value or "").lower(), str(value or "—"))


def translate_driver(value: str | None) -> str:
    return DRIVER_LABELS.get(str(value or ""), str(value or "—"))


def translate_readiness_key(value: str | None) -> str:
    return READINESS_KEY_LABELS.get(str(value or ""), str(value or "—"))


def translate_readiness_state(value: str | None) -> str:
    return READINESS_STATE_LABELS.get(str(value or "").lower(), str(value or "—"))


def translate_gate_level(value: str | None) -> str:
    return GATE_LEVEL_LABELS.get(str(value or ""), str(value or "—"))


def translate_incident_key(value: str | None) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "—"
    return INCIDENT_KEY_LABELS.get(raw.upper(), raw.replace("_", " ").title())


def translate_churn_basis(value: str | None) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "—"
    return CHURN_BASIS_LABELS.get(raw.lower(), raw)


def normalize_shadow_urgency(value: str | None) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "—"
    lower = raw.lower()
    if any(token in lower for token in ("дн", "год", "простроч", "без контакту")):
        return raw
    match = re.fullmatch(r"(\d+)\s*h", lower)
    if match:
        return f"{match.group(1)} год"
    match = re.fullmatch(r"(\d+)\s*d(?:\s+overdue)?", lower)
    if match and "overdue" in lower:
        return f"{match.group(1)} дн прострочення"
    match = re.fullmatch(r"(\d+)\s*d(?:\s+stale)?", lower)
    if match and "stale" in lower:
        return f"{match.group(1)} дн без контакту"
    match = re.fullmatch(r"(\d+)\s*d", lower)
    if match:
        return f"{match.group(1)} дн"
    return raw


def normalize_shadow_phrase(value: str | None) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    phrase_map = {
        "fresh follow-ups": "свіжі передзвони",
        "close overdue calls": "закрийте прострочені передзвони",
        "protect rescue queue": "захистіть чергу порятунку",
        "paid orders": "оплачені замовлення",
        "Review rescue top-5 before end of day": "Перегляньте топ-5 на порятунок до завершення дня",
        "Close overdue follow-ups to reduce discipline drag": "Закрийте прострочені передзвони, щоб зменшити дисциплінарне просідання",
        "Recover minimum-vs-pace gap before report cutoff": "Закрийте розрив між мінімумом і темпом до дедлайну звіту",
    }
    return phrase_map.get(raw, raw)
