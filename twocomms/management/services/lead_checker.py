"""AI-чекер спарсенных аккаунтов: скоринг одного ManagementLead через Gemini
с Google Search grounding. Архитектура и паттерн вызова — как в
services/call_ai_analysis.py (прямой REST, цепочка моделей, ретраи)."""
from __future__ import annotations

import logging
import re

import requests
from django.utils import timezone

from management.models import LeadAICheck, ManagementLead
from management.services.call_ai_analysis import CallAIAnalysisError, gemini_generate_grounded

logger = logging.getLogger("management.checker")


class CheckerKeysExhausted(Exception):
    """Усі ключі checker-пулу тимчасово недоступні (квота/перевантаження).
    Лід НЕ позначається перевіреним — його треба повторити, коли квота відновиться."""

# 10 критериев (ключ, человекочитаемый заголовок). Каждый оценивается 0..10.
CRITERIA: list[tuple[str, str]] = [
    ("product_relevance", "Релевантність товару"),
    ("style_aesthetic", "Стиль та естетика"),
    ("audience_match", "Збіг цільової аудиторії"),
    ("military_tactical", "Мілітарі / тактика"),
    ("custom_print_potential", "Потенціал кастом-друку (white-label)"),
    ("wholesale_potential", "Потенціал опту готового"),
    ("collab_potential", "Потенціал колаборації"),
    ("online_presence", "Онлайн-присутність та охоплення"),
    ("business_profile", "Бізнес-профіль і масштаб"),
    ("approachability", "Реалістичність заходу"),
]

PARTNERSHIP_CHANNELS = ["wholesale", "custom_print", "collab", "dropship", "test_batch", "shelf"]
VERDICT_CATEGORIES = [
    "physical_store", "retail_chain", "dropshipper", "brand",
    "voentorg", "marketplace_seller", "wholesale_supplier", "irrelevant", "other",
]

FIT_THRESHOLD = 70
MAYBE_THRESHOLD = 40

WEBSITE_TIMEOUT = (5, 6)        # (connect, read) сек
WEBSITE_TEXT_LIMIT = 6000       # символов текста сайта
_TAG_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)
_ANY_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def band_for_score(score: int) -> str:
    if score >= FIT_THRESHOLD:
        return "fit"
    if score >= MAYBE_THRESHOLD:
        return "maybe"
    return "unfit"


def niche_for_band(band: str) -> str:
    if band == "fit":
        return ManagementLead.NicheStatus.NICHE
    if band == "maybe":
        return ManagementLead.NicheStatus.MAYBE
    return ManagementLead.NicheStatus.NON_NICHE


def build_lead_context(lead: ManagementLead) -> str:
    extra = lead.extra_data if isinstance(lead.extra_data, dict) else {}
    types = extra.get("types") or []
    address = extra.get("formattedAddress") or ""
    parts = [
        f"Назва: {lead.shop_name}",
        f"Місто: {lead.city}" if lead.city else "",
        f"Сайт: {lead.website_url}" if lead.website_url else "Сайт: невідомо",
        f"Google Maps: {lead.google_maps_url}" if lead.google_maps_url else "",
        f"Google-категорії: {', '.join(types)}" if types else "",
        f"Адреса: {address}" if address else "",
        f"Деталі парсера: {lead.details}" if lead.details else "",
    ]
    return "\n".join(p for p in parts if p)


def fetch_website_text(url: str) -> tuple[str, bool]:
    url = (url or "").strip()
    if not url:
        return "", False
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        resp = requests.get(
            url, timeout=WEBSITE_TIMEOUT,
            headers={"User-Agent": "Mozilla/5.0 TwoCommsChecker/1.0"},
        )
    except Exception:
        return "", False
    if resp.status_code != 200 or "html" not in (resp.headers.get("content-type", "")):
        return "", False
    html = resp.text or ""
    html = _TAG_RE.sub(" ", html)
    text = _ANY_TAG_RE.sub(" ", html)
    text = _WS_RE.sub(" ", text).strip()
    return text[:WEBSITE_TEXT_LIMIT], bool(text)


def build_system_prompt() -> str:
    criteria_lines = "\n".join(f"  - {key} ({title}, 0..10)" for key, title in CRITERIA)
    return (
        "Ти — B2B-аналітик розвитку партнерств бренду TwoComms. Твоє завдання — "
        "оцінити, наскільки знайдений магазин/бренд підходить TwoComms для співпраці.\n\n"
        "ПРО TwoComms:\n"
        "Український streetwear-бренд із Харкова з military-adjacent ДНК і патріотикою. "
        "Асортимент: футболки, худі, лонгсліви, мерч і КАСТОМНИЙ DTF-друк (можемо надрукувати "
        "будь-який принт під бренд клієнта). Унісекс, сегмент «доступний streetwear-преміум». "
        "Орієнтир-конкуренти: українські streetwear-бренди, що живуть в Instagram, з drop-культурою "
        "і авторськими принтами.\n\n"
        "ХТО КУПУЄ TwoComms: ~40% військові; ~20% волонтери / навколовоєнні / українська військова "
        "спільнота; ~40% цивільні, яким близька urban / streetwear / military-adjacent естетика. "
        "Купують і чоловіки, і жінки. ЕСТЕТИКА ВАЖЛИВІША ЗА СТАТЬ — жіночий streetwear-магазин теж "
        "підходить, якщо збігається стиль.\n\n"
        "КАНАЛИ СПІВПРАЦІ (partnership_fit, обери всі релевантні):\n"
        "  - wholesale: опт готового асортименту TwoComms\n"
        "  - custom_print: кастом-друк під їхній бренд (white-label; друкуємо будь-який принт)\n"
        "  - collab: спільний дроп\n"
        "  - dropship: дропшипінг\n"
        "  - test_batch: тестова партія\n"
        "  - shelf: фізмагазин/військторг ставить наш товар на полицю\n\n"
        "КРИТЕРІЇ (кожен 0..10):\n"
        f"{criteria_lines}\n\n"
        "Тобі дають дані магазину (назва, місто, сайт, Google-категорії, адреса) і, якщо вдалося, "
        "текст головної сторінки сайту. Використай Google Search, щоб дослідити бренд: знайти "
        "Instagram/соцмережі, історію, чи продають своє чи перепродають, чи були колаборації, "
        "чи це військторг, маркетплейс-продавець, мережа тощо.\n\n"
        "ВАЖЛИВО: не вигадуй. Якщо даних недостатньо — постав confidence='low' і чесно пиши "
        "'недостатньо даних'. Усі твердження про бренд підкріплюй джерелами (sources).\n\n"
        "overall_score (0..100) — холістична оцінка придатності (НЕ проста сума критеріїв, "
        "а зважений висновок з урахуванням усіх сигналів).\n\n"
        "Відповідай СУВОРО валідним JSON (без markdown, без ```), українською, за схемою:\n"
        "{\n"
        '  "overall_score": <0..100>,\n'
        '  "verdict_category": "physical_store|retail_chain|dropshipper|brand|voentorg|marketplace_seller|irrelevant",\n'
        '  "partnership_fit": ["wholesale", "custom_print", ...],\n'
        '  "confidence": "low|medium|high",\n'
        '  "brand_summary": "що це за магазин/бренд (2-4 речення)",\n'
        '  "audience_guess": "хто їхня аудиторія",\n'
        '  "instagram_url": "https://instagram.com/... або порожньо",\n'
        '  "criteria": [ {"key": "product_relevance", "score": <0..10>, "comment": "обґрунтування"}, ... усі 10 ],\n'
        '  "comment": "загальний висновок для модератора",\n'
        '  "recommendation": "що менеджеру пропонувати цьому магазину (який канал і питч)",\n'
        '  "sources": [ {"title": "...", "url": "https://..."} ]\n'
        "}\n"
    )


def _coerce_int(value, lo: int, hi: int, default: int) -> int:
    try:
        n = int(round(float(value)))
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, n))


def _as_str(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _as_list(value) -> list:
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    return [value]


def normalize_result(raw: dict) -> dict:
    raw = raw if isinstance(raw, dict) else {}
    title_by_key = dict(CRITERIA)

    by_key = {}
    for item in _as_list(raw.get("criteria")):
        if isinstance(item, dict) and item.get("key") in title_by_key:
            by_key[item["key"]] = item
    criteria = []
    for key, title in CRITERIA:
        item = by_key.get(key, {})
        criteria.append({
            "key": key,
            "title": title,
            "score": _coerce_int(item.get("score"), 0, 10, 0),
            "comment": _as_str(item.get("comment")),
        })

    if raw.get("overall_score") in (None, ""):
        avg = sum(c["score"] for c in criteria) / len(criteria) if criteria else 0
        overall = _coerce_int(avg * 10, 0, 100, 0)
    else:
        overall = _coerce_int(raw.get("overall_score"), 0, 100, 0)

    category = _as_str(raw.get("verdict_category")) or "other"
    if category not in VERDICT_CATEGORIES:
        category = "other"

    fit = [c for c in _as_list(raw.get("partnership_fit")) if c in PARTNERSHIP_CHANNELS]

    confidence = _as_str(raw.get("confidence")).lower()
    if confidence not in ("low", "medium", "high"):
        confidence = "low"

    sources = []
    for s in _as_list(raw.get("sources")):
        if isinstance(s, dict) and s.get("url"):
            sources.append({"title": _as_str(s.get("title")) or s["url"], "url": _as_str(s["url"])})

    return {
        "overall_score": overall,
        "verdict_category": category,
        "partnership_fit": fit,
        "confidence": confidence,
        "brand_summary": _as_str(raw.get("brand_summary")),
        "audience_guess": _as_str(raw.get("audience_guess")),
        "instagram_url": _as_str(raw.get("instagram_url"))[:300],
        "criteria": criteria,
        "comment": _as_str(raw.get("comment")),
        "recommendation": _as_str(raw.get("recommendation")),
        "sources": sources,
    }


def score_lead(lead: ManagementLead, *, api_key: str | None = None, checked_by=None, job=None) -> LeadAICheck:
    """Оценивает один лид через Gemini grounding. Всегда возвращает LeadAICheck
    (status=done или error). Идемпотентно обновляет кэш-поля лида."""
    check = LeadAICheck.objects.create(
        lead=lead, job=job, status=LeadAICheck.Status.PROCESSING, checked_by=checked_by,
    )
    started = timezone.now()
    try:
        website_text, fetched = fetch_website_text(lead.website_url)
        user_text = build_lead_context(lead)
        if fetched and website_text:
            user_text += "\n\nТЕКСТ ГОЛОВНОЇ СТОРІНКИ САЙТУ (фрагмент):\n" + website_text

        result = gemini_generate_grounded(
            build_system_prompt(), user_text, api_key=api_key,
        )
        norm = normalize_result(result.get("parsed") or {})
        band = band_for_score(norm["overall_score"])

        check.status = LeadAICheck.Status.DONE
        check.overall_score = norm["overall_score"]
        check.criteria = norm["criteria"]
        check.verdict_category = norm["verdict_category"]
        check.partnership_fit = norm["partnership_fit"]
        check.confidence = norm["confidence"]
        check.brand_summary = norm["brand_summary"]
        check.audience_guess = norm["audience_guess"]
        check.instagram_url = norm["instagram_url"]
        check.comment = norm["comment"]
        check.recommendation = norm["recommendation"]
        check.sources = norm["sources"]
        check.website_fetched = fetched
        check.model_used = result.get("model", "")
        check.tokens = result.get("usage") or {}
        check.save()

        lead.ai_score = norm["overall_score"]
        lead.ai_verdict = band
        lead.ai_checked_at = timezone.now()
        lead.niche_status = niche_for_band(band)
        lead.save(update_fields=["ai_score", "ai_verdict", "ai_checked_at", "niche_status", "updated_at"])
    except CallAIAnalysisError as exc:
        msg = str(exc)
        # Вичерпання/недоступність ключів — НЕ позначаємо лід перевіреним,
        # видаляємо processing-чек і сигналізуємо рушію поставити паузу.
        if "недоступні (квота/перевантаження)" in msg:
            check.delete()
            raise CheckerKeysExhausted(msg) from exc
        check.status = LeadAICheck.Status.ERROR
        check.error = msg
        check.model_used = ""
        check.save(update_fields=["status", "error", "model_used"])
        lead.ai_verdict = "error"
        lead.ai_checked_at = timezone.now()
        lead.save(update_fields=["ai_verdict", "ai_checked_at", "updated_at"])
    except Exception as exc:  # noqa: BLE001 — любая иная ошибка не должна ронять движок
        logger.exception("score_lead failed for lead=%s", lead.id)
        check.status = LeadAICheck.Status.ERROR
        check.error = f"{type(exc).__name__}: {exc}"
        check.save(update_fields=["status", "error"])
        lead.ai_verdict = "error"
        lead.ai_checked_at = timezone.now()
        lead.save(update_fields=["ai_verdict", "ai_checked_at", "updated_at"])
    finally:
        check._duration_seconds = (timezone.now() - started).total_seconds()
    return check
