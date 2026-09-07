"""ЭА.20 — контракт structured-output і HTTP 400 INVALID_ARGUMENT.

Що саме сталось у production. Два відкази 3.7 з HTTP 400 `INVALID_ARGUMENT`
(08:51:01Z і 08:52:50Z) на живому payload, який просить
`responseMimeType=application/json` плюс `responseJsonSchema` з `anyOf`,
`minLength`/`maxLength` і `enum`. Офіційна документація описує ОБМЕЖЕНЕ
підмножину JSON Schema, і точне поле лишалось недоказаним, бо тіло помилки
свідомо не зберігалось. Тобто дефект був наш, а не провайдера, і при цьому він
виглядав як «технічна затримка» для клієнта.

Три речі, які цей модуль робить, і одна, якої він НЕ робить.

1. Preflight: недопустимий запит не має доходити до провайдера. Схема
   приводиться до документованого підмножини ДО серіалізації тіла. Це дешевше й
   надійніше, ніж дізнаватись про дефект з 400 після витраченого ходу.
2. Обмежена атрибуція 400: `error.code`, `error.status` і шлях/ім'я поля з
   `details[].fieldViolations[].field` (або з повідомлення, але лише якщо токен
   схожий на поле НАШОГО запиту). Тіло цілком не зберігається ніколи.
3. Circuit конкретного ВАРІАНТА payload: один 400 — це доказ для цього тіла,
   тому те саме тіло не повторюється ніколи. Дозволений один ретрай заздалегідь
   визначеним спрощеним варіантом. Circuit провайдера при цьому не відкривається
   (ЭА.10): провайдер справний.

Чого модуль НЕ робить: він не послаблює валідацію відповіді. Звуження схеми
провайдера не переносить роботу на валідатор — межі, які ми знімаємо з
`responseJsonSchema`, вже перевіряються застосунком (`ig_response_control`), і
тест етапу це фіксує.
"""
from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from dataclasses import dataclass
from datetime import timedelta

from django.utils import timezone

from management.services.ig_failure_classes import flag

# --- Документоване підмножина -------------------------------------------------
# Джерело: guide «Structured output» (ai.google.dev/gemini-api/docs/structured-output),
# розділ про підтримувані поля схеми плюс його ж «Limitations»: «Schema subset:
# Not all JSON Schema features are supported» і «Schema complexity: Very large or
# deeply nested schemas may be rejected».
#
# Ключові слова, які guide перелічує як підтримувані: типи, `title`,
# `description`, `properties`, `required`, `additionalProperties`, `enum`,
# `format`, `minimum`, `maximum`, `items`, `prefixItems`, `minItems`, `maxItems`;
# приклади додатково демонструють `anyOf` і рекурсію через `$ref`.
#
# `minLength`, `maxLength`, `pattern` і `propertyOrdering` у переліку відсутні —
# саме вони й стоять у живій схемі (`reply_text`, `follow_cta.text`). Це головний
# кандидат на причину 400, і поки провайдер не назве поле сам, ми не маємо права
# лишати недокументовані ключові слова в тілі.
DOCUMENTED_KEYWORDS = frozenset({
    "type",
    "title",
    "description",
    "nullable",
    "enum",
    "format",
    "minimum",
    "maximum",
    "items",
    "prefixItems",
    "minItems",
    "maxItems",
    "properties",
    "required",
    "additionalProperties",
    "anyOf",
    "oneOf",
    "$ref",
    "$defs",
    "$anchor",
    "$id",
})

# Ключові слова, які ми знімаємо явно (а не «все, чого немає в переліку»), щоб
# у звіті було видно КОНКРЕТНУ причину зняття, а не «не в списку».
UNSUPPORTED_KEYWORDS = frozenset({
    "minLength",
    "maxLength",
    "pattern",
    "propertyOrdering",
    "$schema",
    "default",
    "examples",
    "multipleOf",
    "uniqueItems",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "additionalItems",
    "patternProperties",
    "dependentRequired",
    "dependentSchemas",
    "allOf",
    "not",
    "if",
    "then",
    "else",
    "const",
})

# Вузли, значення яких — це самі схеми, а не прості ключові слова. Без цього
# розділення ім'я властивості `pattern` у нашій схемі виглядало б як
# недокументоване ключове слово.
_SCHEMA_MAP_KEYS = ("properties", "$defs", "patternProperties", "dependentSchemas")
_SCHEMA_NODE_KEYS = ("items", "additionalProperties", "propertyNames", "not", "if", "then", "else")
_SCHEMA_LIST_KEYS = ("anyOf", "oneOf", "allOf", "prefixItems")

LIVE_VARIANT = "live"
DOCUMENTED_VARIANT = "documented"
JSON_MODE_VARIANT = "json_mode"

# Один 400 доказує несумісність цього тіла на весь час життя контракту. TTL
# потрібен лише щоб зміна схеми (новий fingerprint і так новий) або зміна на
# стороні провайдера не блокувала варіант назавжди.
CONTRACT_CIRCUIT_TTL = timedelta(hours=6)

AUDIT_ACTION = "gemini_invalid_payload_contract"
AUDIT_ENTITY = "gemini_payload_contract"

# Корені шляхів полів НАШОГО запиту. Токен, який не починається з жодного з них,
# не вважається шляхом поля — так у телеметрію не потрапить ані ключ, ані текст
# клієнта, ані вільний текст провайдера.
_FIELD_ROOTS = frozenset({
    "generation_config",
    "generationConfig",
    "response_json_schema",
    "responseJsonSchema",
    "response_schema",
    "responseSchema",
    "response_mime_type",
    "responseMimeType",
    "thinking_config",
    "thinkingConfig",
    "contents",
    "system_instruction",
    "systemInstruction",
    "safety_settings",
    "safetySettings",
    "tools",
    "tool_config",
    "toolConfig",
    "cached_content",
    "cachedContent",
    "model",
})
_FIELD_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+|\[[0-9]+\])*")
_STATUS_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,39}$")


def _field_root(token: str) -> str:
    root = re.split(r"[.\[]", str(token or ""), maxsplit=1)[0]
    return root


def bounded_field_path(value) -> str:
    """Шлях поля, обрізаний і перевірений, або "" — жодного вільного тексту."""
    token = str(value or "").strip()
    if not token or len(token) > 160:
        token = token[:160]
    if not token:
        return ""
    match = _FIELD_TOKEN_RE.fullmatch(token)
    if match and _field_root(token) in _FIELD_ROOTS:
        return token[:120]
    # Поле могло приїхати всередині речення. Беремо перший токен, який виглядає
    # як шлях НАШОГО запиту, і нічого більше.
    for candidate in _FIELD_TOKEN_RE.findall(str(value or "")[:600]):
        if _field_root(candidate) in _FIELD_ROOTS and ("." in candidate or "[" in candidate):
            return candidate[:120]
    return ""


def bounded_error_facts(error: object) -> dict:
    """`error.code`, `error.status` і шлях поля — і нічого крім них.

    Тіло помилки провайдера може містити довільний текст (у тому числі те, що ми
    самі туди відправили). Тому зберігаються ЛИШЕ три обмежені поля, кожне
    перевірене окремо.
    """
    facts = {"code": 0, "status": "", "field": ""}
    if not isinstance(error, dict):
        return facts
    try:
        facts["code"] = int(error.get("code") or 0)
    except (TypeError, ValueError):
        facts["code"] = 0
    status = str(error.get("status") or "").strip()[:40]
    facts["status"] = status if _STATUS_RE.fullmatch(status) else ""
    for detail in error.get("details") or []:
        if not isinstance(detail, dict):
            continue
        for violation in detail.get("fieldViolations") or []:
            if not isinstance(violation, dict):
                continue
            field = bounded_field_path(violation.get("field"))
            if field:
                facts["field"] = field
                return facts
    facts["field"] = bounded_field_path(error.get("message"))
    return facts


# --- Огляд і спрощення схеми --------------------------------------------------
def _walk(node, path: str, found: list) -> None:
    if isinstance(node, list):
        for index, item in enumerate(node):
            _walk(item, f"{path}[{index}]", found)
        return
    if not isinstance(node, dict):
        return
    for key, value in node.items():
        child_path = f"{path}.{key}" if path else str(key)
        if key in _SCHEMA_MAP_KEYS and isinstance(value, dict):
            for name, sub in value.items():
                _walk(sub, f"{child_path}.{name}", found)
            continue
        if key in _SCHEMA_NODE_KEYS:
            _walk(value, child_path, found)
            continue
        if key in _SCHEMA_LIST_KEYS:
            _walk(value, child_path, found)
            if key in UNSUPPORTED_KEYWORDS:
                found.append((child_path, key))
            continue
        if key in UNSUPPORTED_KEYWORDS or key not in DOCUMENTED_KEYWORDS:
            found.append((child_path, key))


def unsupported_keywords(schema) -> tuple:
    """Усі ключові слова схеми поза документованим підмножиною, зі шляхами."""
    found: list = []
    _walk(schema, "", found)
    return tuple(found)


def _prune(node):
    if isinstance(node, list):
        return [_prune(item) for item in node]
    if not isinstance(node, dict):
        return node
    result = {}
    for key, value in node.items():
        if key in _SCHEMA_MAP_KEYS and isinstance(value, dict):
            result[key] = {name: _prune(sub) for name, sub in value.items()}
            continue
        if key in _SCHEMA_NODE_KEYS:
            result[key] = _prune(value)
            continue
        if key in _SCHEMA_LIST_KEYS:
            if key in UNSUPPORTED_KEYWORDS:
                continue
            result[key] = _prune(value)
            continue
        if key in UNSUPPORTED_KEYWORDS or key not in DOCUMENTED_KEYWORDS:
            continue
        result[key] = value
    return result


def simplify_schema(schema):
    """Заздалегідь визначений спрощений варіант: тільки документовані слова.

    Спрощення знімає ЛИШЕ валідаційні обмеження. Структура контракту —
    `type`, `properties`, `required`, `enum`, `items`, `anyOf` — лишається
    незмінною: інакше ми втратили б сам сенс structured-output і почали б
    отримувати відповіді іншої форми.
    """
    return _prune(deepcopy(schema))


def _response_config(payload) -> tuple:
    """Return response config and schema key; empty key means MIME-only JSON."""
    if not isinstance(payload, dict):
        return None, ""
    generation = payload.get("generationConfig")
    if not isinstance(generation, dict):
        return None, ""
    for key in ("responseJsonSchema", "responseSchema"):
        if isinstance(generation.get(key), (dict, list)):
            return generation, key
    if generation.get("responseMimeType") == "application/json":
        return generation, ""
    return None, ""


def contract_fingerprint(payload) -> str:
    """Стабільний відпечаток ВАРІАНТА контракту (mime + схема).

    У відпечаток входить лише конфігурація відповіді, а не `contents`: контракт
    один для всіх клієнтів, і circuit має відкриватись на ньому, а не на
    конкретному діалозі.
    """
    generation, schema_key = _response_config(payload)
    if generation is None:
        return ""
    material = {
        "mime": str(generation.get("responseMimeType") or ""),
        "schema_key": schema_key,
        "schema": generation.get(schema_key),
    }
    try:
        serialized = json.dumps(material, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    except (TypeError, ValueError):
        return ""
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class ContractReport:
    """Результат preflight: що саме поїде до провайдера і чому."""

    fingerprint: str = ""
    variant: str = ""
    live_fingerprint: str = ""
    unsupported: tuple = ()
    simplified: bool = False
    blocked: bool = False
    reason: str = ""

    @property
    def has_contract(self) -> bool:
        return bool(self.live_fingerprint)


def _with_schema(payload, schema_key: str, schema) -> dict:
    updated = deepcopy(payload)
    updated["generationConfig"][schema_key] = schema
    return updated


def guard_payload(payload, *, model: str = "", now=None) -> tuple:
    """Preflight контракту: повернути тіло, яке дозволено відправити.

    Порядок рішень:

    * контракту немає — нічого не робимо (аудіо-аналіз, проби);
    * є недокументовані ключові слова і preflight увімкнений — їдемо спрощеним
      варіантом; недопустиме тіло взагалі не доходить до провайдера;
    * варіант уже отримав 400 (circuit цього тіла відкритий) — той самий payload
      не повторюється: пробуємо спрощений;
    * спрощений теж отримав 400 — `blocked`. Далі не гадаємо, а віддаємо хід
      людині: третій варіант «на удачу» — це і є той самий сліпий ретрай.
    """
    generation, schema_key = _response_config(payload)
    if generation is None:
        return payload, ContractReport(reason="no_contract")
    now = now or timezone.now()
    if not schema_key:
        fingerprint = contract_fingerprint(payload)
        blocked = bool(
            flag("GEMINI_PAYLOAD_CONTRACT_CIRCUIT")
            and contract_circuit_open(fingerprint, now=now)
        )
        return payload, ContractReport(
            fingerprint=fingerprint,
            variant=JSON_MODE_VARIANT,
            live_fingerprint=fingerprint,
            blocked=blocked,
            reason="json_mode_rejected" if blocked else "json_mode",
        )
    live_schema = generation.get(schema_key)
    live_fingerprint = contract_fingerprint(payload)
    unsupported = unsupported_keywords(live_schema)
    simplified_schema = simplify_schema(live_schema)
    simplified_payload = _with_schema(payload, schema_key, simplified_schema)
    simplified_fingerprint = contract_fingerprint(simplified_payload)
    identical = simplified_fingerprint == live_fingerprint

    circuit_enabled = flag("GEMINI_PAYLOAD_CONTRACT_CIRCUIT")
    live_blocked = circuit_enabled and contract_circuit_open(live_fingerprint, now=now)
    simplified_blocked = circuit_enabled and (
        live_blocked if identical else contract_circuit_open(simplified_fingerprint, now=now)
    )

    use_simplified = bool(
        not identical
        and (
            (unsupported and flag("GEMINI_PAYLOAD_CONTRACT_PREFLIGHT"))
            or live_blocked
        )
    )
    if use_simplified and simplified_blocked:
        return simplified_payload, ContractReport(
            fingerprint=simplified_fingerprint,
            variant=DOCUMENTED_VARIANT,
            live_fingerprint=live_fingerprint,
            unsupported=unsupported,
            simplified=True,
            blocked=True,
            reason="all_variants_rejected",
        )
    if use_simplified:
        return simplified_payload, ContractReport(
            fingerprint=simplified_fingerprint,
            variant=DOCUMENTED_VARIANT,
            live_fingerprint=live_fingerprint,
            unsupported=unsupported,
            simplified=True,
            reason="preflight_simplified" if unsupported else "live_variant_rejected",
        )
    if live_blocked:
        # Спрощення нічого не змінює (або збігається з живим варіантом), а живий
        # варіант уже доказано недопустимий. Повторювати його заборонено.
        return payload, ContractReport(
            fingerprint=live_fingerprint,
            variant=LIVE_VARIANT,
            live_fingerprint=live_fingerprint,
            unsupported=unsupported,
            blocked=True,
            reason="live_variant_rejected",
        )
    return payload, ContractReport(
        fingerprint=live_fingerprint,
        variant=LIVE_VARIANT,
        live_fingerprint=live_fingerprint,
        unsupported=unsupported,
        reason="contract_within_subset" if not unsupported else "preflight_disabled",
    )


def retry_variant_available(payload, *, now=None) -> bool:
    """Чи лишився заздалегідь визначений варіант, яким дозволено ретрай.

    Викликається ПІСЛЯ 400: живий варіант уже в circuit, тому питання одне —
    чи існує спрощений варіант, який ще не доказано недопустимим.
    """
    if not flag("GEMINI_PAYLOAD_CONTRACT_CIRCUIT"):
        return False
    _guarded, report = guard_payload(payload, now=now)
    return bool(report.has_contract and not report.blocked and report.simplified)


# --- Durable evidence і circuit варіанта --------------------------------------
def record_invalid_payload(
    *,
    fingerprint: str,
    variant: str = "",
    model: str = "",
    role: str = "",
    facts: dict | None = None,
    unsupported: tuple = (),
) -> bool:
    """Зберегти ОБМЕЖЕНІ факти 400 і тим самим відкрити circuit цього варіанта.

    Стан circuit не тримається в окремій мутабельній колонці: подія в audit-логу
    Й Є станом. Причини дві. Перша — нової колонки цей етап не додає. Друга —
    похідний стан не можна розсинхронити між процесами демона, а «скільки 400 за
    добу» (метрика ЭА.20) читається тим самим запитом, що й circuit.
    """
    safe_fingerprint = str(fingerprint or "")[:32]
    if not safe_fingerprint:
        return False
    facts = facts if isinstance(facts, dict) else {}
    try:
        from management.models import AdminAuditLog

        AdminAuditLog.objects.create(
            action=AUDIT_ACTION,
            entity_type=AUDIT_ENTITY,
            entity_id=safe_fingerprint,
            after={
                "code": int(facts.get("code") or 0),
                "status": str(facts.get("status") or "")[:40],
                "field": str(facts.get("field") or "")[:120],
                "variant": str(variant or "")[:24],
                "model": str(model or "")[:80],
                "role": str(role or "")[:20],
                # Шляхи недокументованих ключових слів — це наша власна схема,
                # а не текст провайдера, тому їх безпечно зберігати.
                "unsupported": [
                    f"{path}:{keyword}"[:120] for path, keyword in list(unsupported)[:12]
                ],
            },
            reason="ЭА.20 bounded INVALID_ARGUMENT evidence",
        )
        return True
    except Exception:  # pragma: no cover - телеметрія не ламає хід
        import logging

        logging.getLogger(__name__).debug(
            "invalid payload evidence unavailable", exc_info=True
        )
        return False


def contract_circuit_open(fingerprint: str, *, now=None) -> bool:
    """Чи доказано, що це конкретне тіло недопустиме."""
    safe_fingerprint = str(fingerprint or "")[:32]
    if not safe_fingerprint:
        return False
    now = now or timezone.now()
    try:
        from management.models import AdminAuditLog

        return AdminAuditLog.objects.filter(
            action=AUDIT_ACTION,
            entity_type=AUDIT_ENTITY,
            entity_id=safe_fingerprint,
            created_at__gte=now - CONTRACT_CIRCUIT_TTL,
        ).exists()
    except Exception:  # pragma: no cover
        return False


def invalid_payload_count(*, since=None, now=None) -> int:
    """Метрика ЭА.20: число `invalid_payload` за вікно (baseline ЭА.0 — 2 за добу)."""
    now = now or timezone.now()
    since = since or (now - timedelta(days=1))
    from management.models import AdminAuditLog

    return AdminAuditLog.objects.filter(
        action=AUDIT_ACTION, entity_type=AUDIT_ENTITY, created_at__gte=since
    ).count()
