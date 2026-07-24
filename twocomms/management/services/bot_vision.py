"""
Візуальні відбитки товарів і матчинг присланого фото/поста з каталогом.

Проблема, яку розв'язуємо: коли клієнт пересилає пост/фото товару, текстовий
каталог не дає чим зіставити візуал. Тут ми один раз (командою/кроном) проганяємо
фото кожного варіанту товару через Gemini-vision і зберігаємо стислий структурний
опис (принт, тема, кольори, напис) у ProductColorVariant.metadata['bot_vision'].
Далі матчинг (Task 8) дає моделі цей опис як кандидатів.

Vision-виклики йдуть через роль 'management' (розумніша модель, не критична до
латентності), окремо від швидкого діалогу ('chat').
"""
from __future__ import annotations

import base64
import json

from django.utils import timezone

from management.services.call_ai_analysis import gemini_generate_text

FINGERPRINT_INSTRUCTION = (
    "Ти аналізуєш фото товару (одяг бренду TwoComms: футболки, худі, лонгсліви). "
    "Опиши СТИСЛО українською у форматі JSON без пояснень і без markdown: "
    '{"print_subject":"що зображено на принті (об\'єкт/персонаж/символ/тварина)",'
    '"theme":"тема одним словом: military/streetwear/patriotic/anime/generic тощо",'
    '"dominant_colors":["основні кольори одягу"],'
    '"text_on_item":"текст/напис на одязі, якщо є",'
    '"summary":"одне коротке речення-опис для пошуку"}. '
    "Якщо чогось немає — порожній рядок або []."
)

MAX_FP_IMAGES = 2
MAX_MEDIA_ROLE_IMAGES = 8
MEDIA_ROLE_INSTRUCTION = (
    "Класифікуй кожне зображення лише за його видимим вмістом для внутрішньої CRM. "
    "Допустимі ролі: receipt (банківський чек, квитанція або екран успішного переказу), "
    "product (товар, картка товару, пост або одяг), custom_reference (референс бажаного "
    "кастомного принта), other (усе інше або недостатньо даних). Не роби висновок paid. "
    "Поверни тільки JSON: "
    '{"items":[{"source_image_index":0,"role":"receipt|product|custom_reference|other",'
    '"confidence":0.0,"reason":"коротка видима ознака"}]}. '
    "Один елемент на кожне вхідне зображення, індекси від 0."
)


def build_fingerprint_payload(images: list[tuple[str, bytes]]) -> dict:
    """Будує payload Gemini для опису фото товару (JSON-вихід)."""
    parts: list[dict] = [{"text": FINGERPRINT_INSTRUCTION}]
    for mime, raw in images[:MAX_FP_IMAGES]:
        try:
            parts.append(
                {"inline_data": {"mime_type": mime, "data": base64.b64encode(raw).decode()}}
            )
        except Exception:
            continue
    return {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 4096,
            "responseMimeType": "application/json",
        },
    }


def _parse_fingerprint(raw: str) -> dict:
    """Парсить JSON-відповідь моделі, знімаючи ```json fences та зайвий текст."""
    text = (raw or "").strip()
    if not text:
        return {}
    if text.startswith("```"):
        # прибираємо ```json ... ```
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    # межі першого { ... останнього }
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]
    try:
        data = json.loads(text)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def describe_images(images: list[tuple[str, bytes]] | None) -> dict | None:
    """Викликає Gemini-vision (роль management) і повертає розпарсений відбиток."""
    if not images:
        return None
    payload = build_fingerprint_payload(images)
    try:
        out = gemini_generate_text(
            payload, role="management", reasoning_task="media_analysis"
        )
    except Exception:
        return None
    return _parse_fingerprint(out.get("parsed") or "")


def classify_media_roles(images: list[tuple[str, bytes]] | None) -> list[dict]:
    """Classify visual evidence without inferring provider payment truth."""
    if not images:
        return []
    parts: list[dict] = [{"text": MEDIA_ROLE_INSTRUCTION}]
    usable_count = 0
    for mime, raw in images[:MAX_MEDIA_ROLE_IMAGES]:
        try:
            encoded = base64.b64encode(raw).decode()
        except Exception:
            continue
        parts.append({"inline_data": {"mime_type": str(mime or "image/jpeg"), "data": encoded}})
        usable_count += 1
    if not usable_count:
        return []
    payload = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 4096,
            "responseMimeType": "application/json",
        },
    }
    try:
        out = gemini_generate_text(payload, role="management", reasoning_task="media_analysis")
    except Exception:
        return []
    data = _parse_fingerprint(out.get("parsed") or "")
    raw_items = data.get("items") if isinstance(data.get("items"), list) else []
    allowed_roles = {"receipt", "product", "custom_reference", "other"}
    result = []
    seen_indexes = set()
    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            continue
        try:
            image_index = int(raw_item.get("source_image_index"))
            confidence = float(raw_item.get("confidence") or 0)
        except (TypeError, ValueError):
            continue
        role = str(raw_item.get("role") or "").strip().casefold()
        if (
            image_index < 0
            or image_index >= usable_count
            or image_index in seen_indexes
            or role not in allowed_roles
            or confidence < 0
            or confidence > 1
        ):
            continue
        seen_indexes.add(image_index)
        result.append({
            "source_image_index": image_index,
            "role": role,
            "confidence": confidence,
            "reason": str(raw_item.get("reason") or "")[:300],
        })
    return sorted(result, key=lambda item: item["source_image_index"])


def store_fingerprint(variant, fp: dict) -> None:
    """Зберігає відбиток у variant.metadata['bot_vision'] з міткою часу."""
    meta = dict(variant.metadata or {})
    data = dict(fp or {})
    data["updated_at"] = timezone.now().isoformat()
    meta["bot_vision"] = data
    variant.metadata = meta
    variant.save(update_fields=["metadata"])


def _variant_images(variant, limit: int = MAX_FP_IMAGES) -> list[tuple[str, bytes]]:
    """Читає байти зображень варіанту (фото кольору, фолбек — головне фото товару)."""
    images: list[tuple[str, bytes]] = []
    try:
        for img in variant.images.all()[:limit]:
            f = getattr(img, "image", None)
            if not f:
                continue
            try:
                f.open("rb")
                raw = f.read()
            finally:
                try:
                    f.close()
                except Exception:
                    pass
            if raw:
                images.append(("image/jpeg", raw))
    except Exception:
        pass
    if not images:
        try:
            main = getattr(variant.product, "main_image", None)
            if main:
                main.open("rb")
                raw = main.read()
                main.close()
                if raw:
                    images.append(("image/jpeg", raw))
        except Exception:
            pass
    return images[:limit]


def fingerprint_variant(variant) -> bool:
    """Генерує і зберігає відбиток для одного варіанту. False, якщо немає фото
    або модель не дала відповіді."""
    images = _variant_images(variant)
    if not images:
        return False
    fp = describe_images(images)
    if not fp:
        return False
    store_fingerprint(variant, fp)
    return True


def fingerprint_product(product, force: bool = False) -> int:
    """Прогоняє всі варіанти товару. Повертає к-сть оброблених.
    Якщо force=False — пропускає варіанти, що вже мають відбиток."""
    done = 0
    try:
        variants = list(product.color_variants.all())
    except Exception:
        variants = []
    for v in variants:
        if not force and (v.metadata or {}).get("bot_vision"):
            continue
        try:
            if fingerprint_variant(v):
                done += 1
        except Exception:
            continue
    return done


# ---------------------------------------------------------------------------
# Матчинг присланого фото/поста з каталогом (Task 8)
# ---------------------------------------------------------------------------
MATCH_THRESHOLD = 0.6  # поріг впевненості для автоматичної відповіді з ціною
MATCH_CANDIDATES_LIMIT = 60
MAX_MATCH_IMAGES = 8

MATCH_INSTRUCTION = (
    "Клієнт прислав фото або переслав пост товару. Обери з КАНДИДАТІВ той товар, "
    "що НАЙБІЛЬШЕ відповідає зображенню (за принтом, темою, кольором, написом). "
    "Поверни лише JSON без markdown: "
    '{"product_id": <id з кандидатів або null>, "confidence": <число 0..1>, '
    '"reason": "коротко чому"}. Якщо впевненого збігу немає — product_id:null, '
    "confidence:0. НЕ вигадуй товар, якого немає у списку кандидатів."
)

MATCH_MANY_INSTRUCTION = (
    "На фото може бути один або кілька різних товарів TwoComms. Знайди ВСІ "
    "впевнені збіги з КАНДИДАТАМИ, не об'єднуй різні принти в один SKU. "
    "Поверни лише JSON без markdown: "
    '{"matches":[{"product_id":<id>,"confidence":<0..1>,'
    '"source_image_indexes":[<індекси фото від 0>],"reason":"коротко"}]}. '
    "Один скриншот може містити два товари, тоді поверни два елементи з тим самим "
    "індексом фото. Якщо збігу немає, поверни {\"matches\":[]}. Не вигадуй ID."
)


def build_match_candidates(limit: int = MATCH_CANDIDATES_LIMIT) -> list[dict]:
    """Список кандидатів (опубліковані товари + їх візуальні відбитки) для матчингу."""
    try:
        from storefront.models import Product, ProductStatus
    except Exception:
        return []
    qs = (
        Product.objects.filter(status=ProductStatus.PUBLISHED)
        .select_related("category")
        .prefetch_related("color_variants")
        .order_by("-featured", "-id")[:limit]
    )
    out: list[dict] = []
    for p in qs:
        fp_parts: list[str] = []
        for v in p.color_variants.all():
            bv = (v.metadata or {}).get("bot_vision") or {}
            seg = (bv.get("summary") or bv.get("print_subject") or "").strip()
            if seg:
                fp_parts.append(seg)
        try:
            price = int(getattr(p, "final_price", None) or p.price)
        except Exception:
            price = int(p.price or 0)
        out.append({
            "id": p.id,
            "title": p.title,
            "price": price,
            "category": getattr(p.category, "name", "") or "",
            "fingerprint": "; ".join(dict.fromkeys(fp_parts))[:300],
            "slug": p.slug,
        })
    return out


def _format_candidates(candidates: list[dict]) -> str:
    lines = []
    for c in candidates:
        fp = f" | візуал: {c['fingerprint']}" if c.get("fingerprint") else ""
        lines.append(
            f"id={c['id']} | {c.get('title','')} | {c.get('category','')} | {c.get('price','')} грн{fp}"
        )
    return "\n".join(lines)


def build_match_payload(images: list[tuple[str, bytes]], candidates: list[dict]) -> dict:
    text = MATCH_INSTRUCTION + "\n\nКАНДИДАТИ:\n" + _format_candidates(candidates)
    parts: list[dict] = [{"text": text}]
    for mime, raw in images[:MAX_MATCH_IMAGES]:
        try:
            parts.append(
                {"inline_data": {"mime_type": mime, "data": base64.b64encode(raw).decode()}}
            )
        except Exception:
            continue
    return {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 4096,
            "responseMimeType": "application/json",
        },
    }


def build_match_many_payload(images: list[tuple[str, bytes]], candidates: list[dict]) -> dict:
    payload = build_match_payload(images, candidates)
    payload["contents"][0]["parts"][0]["text"] = (
        MATCH_MANY_INSTRUCTION + "\n\nКАНДИДАТИ:\n" + _format_candidates(candidates)
    )
    return payload


def match_many(
    images: list[tuple[str, bytes]] | None,
    candidates: list[dict] | None = None,
) -> list[dict]:
    """Return every validated catalog match, including two products in one image."""
    if not images:
        return []
    if candidates is None:
        candidates = build_match_candidates()
    if not candidates:
        return []
    try:
        out = gemini_generate_text(
            build_match_many_payload(images, candidates),
            role="management",
            reasoning_task="catalog_match",
        )
    except Exception:
        return []
    data = _parse_fingerprint(out.get("parsed") or "")
    raw_matches = data.get("matches") if isinstance(data.get("matches"), list) else []
    valid_ids = {int(candidate["id"]) for candidate in candidates if candidate.get("id") is not None}
    result = []
    seen = set()
    for raw in raw_matches[:12]:
        if not isinstance(raw, dict):
            continue
        try:
            product_id = int(raw.get("product_id"))
            confidence = max(0.0, min(1.0, float(raw.get("confidence") or 0)))
        except (TypeError, ValueError):
            continue
        if product_id not in valid_ids or product_id in seen or confidence < MATCH_THRESHOLD:
            continue
        indexes = []
        for index in raw.get("source_image_indexes") or []:
            try:
                index = int(index)
            except (TypeError, ValueError):
                continue
            if 0 <= index < len(images) and index not in indexes:
                indexes.append(index)
        if not indexes:
            continue
        result.append({
            "product_id": product_id,
            "confidence": confidence,
            "source_image_indexes": indexes,
            "reason": str(raw.get("reason") or "")[:300],
        })
        seen.add(product_id)
    return result


def match(images: list[tuple[str, bytes]] | None, candidates: list[dict] | None = None) -> dict:
    """Зіставляє присланий візуал з каталогом. Повертає
    {product_id, confidence, reason}. Анти-галюцинація: product_id мусить бути
    серед кандидатів, інакше скидаємо в None/0."""
    if not images:
        return {"product_id": None, "confidence": 0.0, "reason": "no_image"}
    if candidates is None:
        candidates = build_match_candidates()
    if not candidates:
        return {"product_id": None, "confidence": 0.0, "reason": "no_candidates"}

    payload = build_match_payload(images, candidates)
    try:
        out = gemini_generate_text(
            payload, role="management", reasoning_task="catalog_match"
        )
    except Exception:
        return {"product_id": None, "confidence": 0.0, "reason": "error"}
    data = _parse_fingerprint(out.get("parsed") or "")

    pid = data.get("product_id")
    try:
        pid = int(pid) if pid not in (None, "", "null") else None
    except Exception:
        pid = None
    try:
        conf = float(data.get("confidence") or 0)
    except Exception:
        conf = 0.0

    valid_ids = {c["id"] for c in candidates}
    if pid not in valid_ids:
        pid, conf = None, 0.0

    return {"product_id": pid, "confidence": conf, "reason": (str(data.get("reason") or ""))[:300]}
