"""
ШІ-аналіз записів розмов (Binotel + Gemini).

Потік (синхронний — щоб на тестовій фазі бачити реальну швидкість):

  1. Апсерт CallRecord за generalCallID (авторитетні дані з stats/call-details,
     не довіряємо фронту). Матч клієнта за номером, менеджера — за internalNumber.
  2. Якщо вже є готовий аналіз і не force — повертаємо кеш.
  3. Тягнемо mp3 server-side через BinotelClient.fetch_record_stream (обхід
     15-хв посилання та mixed-content), читаємо в памʼять, перевіряємо розмір.
  4. Шлемо аудіо inline у Gemini generateContent з рубрикою оцінки у стилі
     Mosaic (адаптованою під один дзвінок) + опційний B2B-контекст менеджера.
     Просимо строгий JSON (responseMimeType=application/json).
  5. Парсимо, зберігаємо CallAIAnalysis (done) з метриками прогону.

Аудіо локально НЕ зберігається — лише структурований розбор та метрики.
Ключ Gemini — з ENV GEMINI_API (той самий, що використовує Instagram-бот),
модель за замовчуванням gemini-3.5-flash. Бібліотека google.generativeai НЕ
потрібна — прямий REST-виклик (як у services/instagram_bot.py).
"""
from __future__ import annotations

import base64
import json
import logging
import os
import time
from decimal import Decimal, InvalidOperation

import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone

from management.models import CallAIAnalysis, CallRecord, Client
from management.models import normalize_phone as model_normalize_phone
from management.services.binotel import (
    BinotelClient,
    BinotelError,
    BinotelNotConfigured,
    parse_webhook_call_details,
)

logger = logging.getLogger("binotel")

GENAI_BASE = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_MODEL = "gemini-3.5-flash"

# Inline-ліміт Gemini — 20 МБ на весь запит. Лишаємо запас на JSON/base64-оверхед
# (base64 додає ~33%), тож кап на сирий mp3 ставимо консервативно.
MAX_AUDIO_BYTES = 14 * 1024 * 1024

GEMINI_TIMEOUT = (10, 120)  # (connect, read) — аудіо-аналіз може йти десятки секунд


class CallAIAnalysisError(Exception):
    """Помилка рівня ШІ-аналізу (конфіг/аудіо/Gemini)."""


# ---------------------------------------------------------------------------
# Рубрика оцінки (system_instruction)
# ---------------------------------------------------------------------------
# Осі — дух Mosaic, перекладений на один дзвінок. Кожна 0..100, ваги в сумі = 1.0.
RUBRIC_AXES = [
    {"key": "rapport", "title": "Встановлення контакту", "weight": 0.15},
    {"key": "needs_discovery", "title": "Виявлення потреб", "weight": 0.25},
    {"key": "value_presentation", "title": "Презентація рішення та цінності", "weight": 0.20},
    {"key": "objection_handling", "title": "Робота із запереченнями", "weight": 0.15},
    {"key": "closing_next_step", "title": "Закриття / наступний крок", "weight": 0.15},
    {"key": "communication_quality", "title": "Якість комунікації", "weight": 0.10},
]


def _build_system_instruction() -> str:
    axes_lines = "\n".join(
        f"  - {a['key']} ({a['title']}, вага {a['weight']})" for a in RUBRIC_AXES
    )
    return (
        "Ти — досвідчений керівник відділу продажів та QA-аналітик дзвінків бренду "
        "TwoComms (B2B-продаж одягу мілітарі/стрітстайл оптовим клієнтам та магазинам). "
        "Тобі дають АУДІОЗАПИС реальної телефонної розмови менеджера з клієнтом. "
        "Повністю прослухай розмову від початку до кінця, зроби транскрипт із розміткою "
        "ролей (Менеджер / Клієнт), зрозумій, про якого клієнта йдеться і чого він хоче.\n\n"
        "Оціни роботу МЕНЕДЖЕРА за такими осями (кожна 0..100):\n"
        f"{axes_lines}\n\n"
        "Загальний бал overall_score (0..100) — зважена сума осей за вказаними вагами.\n"
        "verdict: 'pass' (>=75 і немає грубих провалів), 'coaching' (50..74 або є що "
        "підтягнути), 'fail' (<50 або критичні помилки).\n\n"
        "Будь конкретним і спирайся на фрази з розмови. Якщо аудіо нерозбірливе або "
        "розмови фактично немає (автовідповідач, тиша, гудки) — постав низькі бали, "
        "познач це у summary і поверни verdict 'fail'.\n\n"
        "Відповідай СУВОРО валідним JSON (без markdown, без ```), українською, за схемою:\n"
        "{\n"
        '  "client_identification": "хто клієнт і що йому треба (1-3 речення)",\n'
        '  "summary": "стисле резюме розмови (3-6 речень)",\n'
        '  "transcript": "повний транскрипт з ролями Менеджер:/Клієнт:",\n'
        '  "overall_score": <number 0..100>,\n'
        '  "verdict": "pass|coaching|fail",\n'
        '  "axes": [ {"key": "<ключ осі>", "title": "<назва>", "score": <0..100>, '
        '"comment": "обґрунтування з прикладами"} ],\n'
        '  "discussed_well": ["що менеджер зробив добре", "..."],\n'
        '  "missed_topics": ["важливі речі/потреби, які НЕ обговорили", "..."],\n'
        '  "recommendations": ["конкретна порада менеджеру", "..."]\n'
        "}"
    )


def _resolve_gemini_key() -> str:
    """Ключ Gemini: ENV GEMINI_API (як в Instagram-боті) або settings."""
    key = (os.environ.get("GEMINI_API", "") or "").strip()
    if not key:
        key = (getattr(settings, "GEMINI_API_KEY", "") or "").strip()
    return key


def _resolve_model() -> str:
    return (getattr(settings, "GEMINI_CALL_ANALYSIS_MODEL", "") or DEFAULT_MODEL).strip()


# ---------------------------------------------------------------------------
# CallRecord upsert
# ---------------------------------------------------------------------------
def _match_client(external_number: str):
    norm = model_normalize_phone(external_number or "")
    if not norm:
        return None
    client = Client.objects.filter(phone_normalized=norm).order_by("id").first()
    if client:
        return client
    last7 = norm[-7:] if len(norm) >= 7 else norm
    if last7:
        return Client.objects.filter(phone_last7=last7).order_by("id").first()
    return None


def _resolve_manager(client: BinotelClient, internal_number: str):
    """internalNumber -> email співробітника Binotel -> Django User. Best-effort."""
    internal_number = (str(internal_number or "")).strip()
    if not internal_number:
        return None
    try:
        data = client.list_of_employees()
    except BinotelError:
        return None
    email = ""
    for _key, emp in (data.get("listOfEmployees") or {}).items():
        endpoint = emp.get("endpointData") or {}
        if str(endpoint.get("internalNumber") or "") == internal_number:
            email = (emp.get("email") or "").strip()
            break
    if not email:
        return None
    User = get_user_model()
    return User.objects.filter(email__iexact=email).order_by("id").first()


def upsert_call_record(client: BinotelClient, general_call_id: str) -> CallRecord:
    """Створює/оновлює CallRecord за авторитетними даними stats/call-details."""
    gcid = (str(general_call_id or "")).strip()
    if not gcid:
        raise CallAIAnalysisError("Потрібен generalCallID.")

    parsed = {}
    try:
        data = client.call_details(gcid)
        details = data.get("callDetails")
        if isinstance(details, dict):
            # call-details повертає {generalCallID: {...}}
            entry = details.get(gcid) or details.get(str(gcid))
            if isinstance(entry, dict):
                parsed = parse_webhook_call_details(entry)
    except BinotelError as exc:
        logger.info("call-ai: call-details failed for %s: %s", gcid, exc)

    started_at = None
    if parsed.get("start_time"):
        try:
            started_at = timezone.datetime.fromtimestamp(
                int(parsed["start_time"]), tz=timezone.get_current_timezone()
            )
        except (TypeError, ValueError, OSError):
            started_at = None

    matched_client = _match_client(parsed.get("external_number") or "")
    manager = _resolve_manager(client, parsed.get("internal_number") or "")

    defaults = {
        "phone": parsed.get("external_number") or "",
        "direction": parsed.get("direction") or CallRecord.Direction.UNKNOWN,
        "duration_seconds": int(parsed.get("bill_seconds") or 0),
    }
    if started_at:
        defaults["started_at"] = started_at
    if matched_client:
        defaults["matched_client"] = matched_client
    if manager:
        defaults["manager"] = manager
    if parsed:
        defaults["payload"] = parsed

    record, _created = CallRecord.objects.update_or_create(
        provider="binotel",
        external_call_id=gcid,
        defaults=defaults,
    )
    return record


# ---------------------------------------------------------------------------
# Gemini
# ---------------------------------------------------------------------------
def _gemini_analyze(audio_bytes: bytes, mime: str, manager_context: str) -> dict:
    """Шле аудіо в Gemini, повертає (parsed_json, raw_response, usage)."""
    key = _resolve_gemini_key()
    if not key:
        raise CallAIAnalysisError("Не задано ключ Gemini (ENV GEMINI_API).")
    model = _resolve_model()

    user_parts = [
        {
            "text": (
                "Проаналізуй цей запис телефонної розмови за наданою рубрикою. "
                + (
                    "Додатковий B2B-контекст від менеджера (підхід до клієнта, його "
                    "потреби, домовленості) — врахуй його при оцінці:\n"
                    + manager_context.strip()
                    if manager_context.strip()
                    else "Додаткового контексту від менеджера немає."
                )
            )
        },
        {"inline_data": {"mime_type": mime, "data": base64.b64encode(audio_bytes).decode()}},
    ]
    payload = {
        "contents": [{"role": "user", "parts": user_parts}],
        "system_instruction": {"parts": [{"text": _build_system_instruction()}]},
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 8192,
            "responseMimeType": "application/json",
        },
        "safetySettings": [
            {"category": c, "threshold": "BLOCK_ONLY_HIGH"}
            for c in (
                "HARM_CATEGORY_HARASSMENT",
                "HARM_CATEGORY_HATE_SPEECH",
                "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "HARM_CATEGORY_DANGEROUS_CONTENT",
            )
        ],
    }

    url = f"{GENAI_BASE}/models/{model}:generateContent"
    try:
        resp = requests.post(
            url,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json", "x-goog-api-key": key},
            timeout=GEMINI_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise CallAIAnalysisError(f"Помилка зʼєднання з Gemini: {exc}") from exc

    if resp.status_code != 200:
        raise CallAIAnalysisError(f"Gemini HTTP {resp.status_code}: {resp.text[:400]}")

    try:
        data = resp.json()
    except ValueError as exc:
        raise CallAIAnalysisError("Gemini повернув невалідний JSON-конверт.") from exc

    cand = (data.get("candidates") or [{}])[0]
    parts = (cand.get("content") or {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts).strip()
    if not text:
        reason = cand.get("finishReason") or "невідомо"
        raise CallAIAnalysisError(f"Gemini не повернув контент (finishReason={reason}).")

    parsed = _parse_model_json(text)
    usage = data.get("usageMetadata") or {}
    return {"parsed": parsed, "raw": parsed, "usage": usage, "model": model}


def _parse_model_json(text: str) -> dict:
    """Парсить JSON від моделі, страхуючись від ```json-фенсів та зайвого тексту."""
    t = text.strip()
    if t.startswith("```"):
        # прибрати ```json ... ```
        t = t.strip("`")
        if t[:4].lower() == "json":
            t = t[4:]
        t = t.strip()
    try:
        return json.loads(t)
    except ValueError:
        # спробувати вирізати від першої { до останньої }
        start, end = t.find("{"), t.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(t[start : end + 1])
            except ValueError:
                pass
    raise CallAIAnalysisError("Не вдалося розпарсити JSON-відповідь моделі.")


# ---------------------------------------------------------------------------
# Нормалізація результату
# ---------------------------------------------------------------------------
def _to_score(value) -> Decimal:
    try:
        d = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0.00")
    if d < 0:
        d = Decimal("0")
    if d > 100:
        d = Decimal("100")
    return d.quantize(Decimal("0.01"))


def _normalize_verdict(value) -> str:
    v = (str(value or "")).strip().lower()
    if v in {"pass", "coaching", "fail"}:
        return v
    return CallAIAnalysis.Verdict.UNKNOWN


def _as_list(value) -> list:
    if isinstance(value, list):
        return [x for x in value if x not in (None, "")]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


# ---------------------------------------------------------------------------
# Публічний вхід
# ---------------------------------------------------------------------------
def analyze_call(
    general_call_id: str,
    *,
    manager_context: str = "",
    force: bool = False,
    created_by=None,
) -> CallAIAnalysis:
    """Аналізує запис розмови та зберігає CallAIAnalysis. Повертає об'єкт."""
    gcid = (str(general_call_id or "")).strip()
    if not gcid:
        raise CallAIAnalysisError("Потрібен generalCallID.")

    try:
        client = BinotelClient.from_settings()
    except BinotelNotConfigured as exc:
        raise CallAIAnalysisError(str(exc)) from exc

    record = upsert_call_record(client, gcid)

    if not force:
        existing = (
            record.ai_analyses.filter(status=CallAIAnalysis.Status.DONE)
            .order_by("-created_at")
            .first()
        )
        if existing:
            return existing

    analysis = CallAIAnalysis.objects.create(
        call_record=record,
        status=CallAIAnalysis.Status.RUNNING,
        manager_context=(manager_context or "").strip(),
        created_by=created_by if getattr(created_by, "is_authenticated", False) else None,
        model=_resolve_model(),
    )

    started = time.monotonic()
    try:
        upstream, _url = client.fetch_record_stream(gcid)
        try:
            audio = upstream.content  # читаємо повністю в памʼять
        finally:
            upstream.close()

        size = len(audio or b"")
        if size <= 0:
            raise CallAIAnalysisError("Порожній аудіофайл запису.")
        if size > MAX_AUDIO_BYTES:
            raise CallAIAnalysisError(
                f"Запис завеликий ({size // (1024*1024)} МБ) для inline-аналізу. "
                "Потрібен Files API (буде додано пізніше)."
            )

        out = _gemini_analyze(audio, "audio/mpeg", analysis.manager_context)
        parsed = out["parsed"]
        usage = out["usage"]

        analysis.status = CallAIAnalysis.Status.DONE
        analysis.model = out["model"]
        analysis.overall_score = _to_score(parsed.get("overall_score"))
        analysis.verdict = _normalize_verdict(parsed.get("verdict"))
        analysis.transcript = str(parsed.get("transcript") or "")
        analysis.summary = str(parsed.get("summary") or "")
        analysis.client_identification = str(parsed.get("client_identification") or "")
        analysis.axes = parsed.get("axes") if isinstance(parsed.get("axes"), list) else []
        analysis.discussed_well = _as_list(parsed.get("discussed_well"))
        analysis.missed_topics = _as_list(parsed.get("missed_topics"))
        analysis.recommendations = _as_list(parsed.get("recommendations"))
        analysis.result = parsed if isinstance(parsed, dict) else {"_raw": parsed}
        analysis.audio_bytes = size
        analysis.prompt_tokens = int(usage.get("promptTokenCount") or 0)
        analysis.output_tokens = int(
            usage.get("candidatesTokenCount") or usage.get("totalTokenCount") or 0
        )
        analysis.elapsed_ms = int((time.monotonic() - started) * 1000)
        analysis.save()
        record.qa_status = CallRecord.QaStatus.REVIEWED
        record.save(update_fields=["qa_status", "updated_at"])
    except (CallAIAnalysisError, BinotelError) as exc:
        analysis.status = CallAIAnalysis.Status.ERROR
        analysis.error = str(exc)[:2000]
        analysis.elapsed_ms = int((time.monotonic() - started) * 1000)
        analysis.save()
        logger.info("call-ai: analysis failed for %s: %s", gcid, exc)
    except Exception as exc:  # будь-яка неочікувана помилка — фіксуємо, не валимо view
        analysis.status = CallAIAnalysis.Status.ERROR
        analysis.error = f"Несподівана помилка: {exc}"[:2000]
        analysis.elapsed_ms = int((time.monotonic() - started) * 1000)
        analysis.save()
        logger.exception("call-ai: unexpected error for %s", gcid)

    return analysis


def serialize_analysis(analysis: CallAIAnalysis) -> dict:
    """Готує словник для JSON-відповіді у тест-вкладку."""
    record = analysis.call_record
    return {
        "id": analysis.id,
        "status": analysis.status,
        "model": analysis.model,
        "overall_score": float(analysis.overall_score),
        "verdict": analysis.verdict,
        "verdict_label": analysis.get_verdict_display(),
        "transcript": analysis.transcript,
        "summary": analysis.summary,
        "client_identification": analysis.client_identification,
        "axes": analysis.axes or [],
        "discussed_well": analysis.discussed_well or [],
        "missed_topics": analysis.missed_topics or [],
        "recommendations": analysis.recommendations or [],
        "manager_context": analysis.manager_context,
        "error": analysis.error,
        "audio_bytes": analysis.audio_bytes,
        "elapsed_ms": analysis.elapsed_ms,
        "prompt_tokens": analysis.prompt_tokens,
        "output_tokens": analysis.output_tokens,
        "created_at": timezone.localtime(analysis.created_at).strftime("%d.%m.%Y %H:%M:%S"),
        "call_record_id": record.id,
        "matched_client_id": record.matched_client_id,
        "manager_name": (
            record.manager.get_full_name() or record.manager.username
            if record.manager_id
            else ""
        ),
    }
