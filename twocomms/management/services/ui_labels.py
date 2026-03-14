from __future__ import annotations


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
