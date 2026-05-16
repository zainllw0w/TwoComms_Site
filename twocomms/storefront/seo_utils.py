"""
SEO утилиты для автоматической генерации мета-тегов и ключевых слов
"""
import re
import json
import os
from datetime import timedelta
from decimal import Decimal
from typing import List, Dict, Optional
from urllib.parse import urljoin
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import get_language
from .models import Product, Category
from .services.size_guides import resolve_product_sizes
from .services.policy import (
    APPLICABLE_COUNTRY,
    CURRENCY,
    RETURN_POLICY,
    SHIPPING_TIERS,
    shipping_tiers_as_dicts,
)

SITE_BASE_URL = getattr(settings, 'SITE_BASE_URL', 'https://twocomms.shop')
if not SITE_BASE_URL.endswith('/'):
    SITE_BASE_URL += '/'

DEFAULT_SOCIAL_IMAGE_PATH = "static/img/social-preview.jpg"


def _build_absolute_url(path: str) -> str:
    """Возвращает абсолютный URL, используя SITE_BASE_URL как базу"""
    if not path:
        return SITE_BASE_URL
    if path.startswith(('http://', 'https://')):
        return path
    return urljoin(SITE_BASE_URL, path.lstrip('/'))


def get_default_social_image_url() -> str:
    return _build_absolute_url(DEFAULT_SOCIAL_IMAGE_PATH)


def _clean_text(raw: str | None) -> str:
    if not raw:
        return ""
    cleaned = re.sub(r"<[^>]+>", " ", str(raw))
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _truncate_at_word_boundary(text: str, limit: int) -> str:
    if not text or len(text) <= limit:
        return text

    cut = text[: max(0, limit - 3)].rstrip(" ,.;:-")
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0].rstrip(" ,.;:-")
    return f"{cut}..."


def _ai_enabled(obj) -> bool:
    """Returns True only if the object explicitly opted into AI-driven SEO.

    AI content (ai_keywords / ai_description) is used in fallbacks ONLY when
    the corresponding ai_generation_enabled flag is True. Otherwise we treat
    those fields as if they were empty.
    """
    return bool(getattr(obj, "ai_generation_enabled", False))


def _pick_product_description_source(product: Product) -> str:
    """Cascade through description fields in priority order.

    AI description is consulted only when the product opted into AI generation.
    """
    candidates = ["seo_description", "short_description"]
    if _ai_enabled(product):
        candidates.append("ai_description")
    candidates.extend(["full_description", "description"])
    for attr in candidates:
        value = _clean_text(getattr(product, attr, ""))
        if value:
            return value
    return ""


def _guess_product_material(product: Product) -> str:
    lookup_source = " ".join(
        filter(
            None,
            [
                getattr(product, "title", ""),
                getattr(getattr(product, "category", None), "name", ""),
                getattr(product, "slug", ""),
            ],
        )
    ).lower()

    if any(token in lookup_source for token in ("худі", "hoodie", "світшот", "sweatshirt")):
        return "трьохнитка"
    if "лонг" in lookup_source or "long" in lookup_source:
        return "бавовна"
    return "бавовна"


def _safe_product_display_image(product) -> object | None:
    main_image = getattr(product, "main_image", None)
    if main_image:
        return main_image

    try:
        return getattr(product, "display_image", None)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Homepage commerce signals (US-16 — eliminate Google price-snippet
# hallucination "200 200 грн" by providing explicit priceRange and
# AggregateOffer derived from real Product data).
# ---------------------------------------------------------------------------


def _homepage_price_aggregate() -> Dict[str, object]:
    """Compute live low/high price + offer count across the catalogue.

    Used both inside ``Organization.priceRange`` (text form) and as the
    standalone ``AggregateOffer`` node on the homepage. Errors during
    aggregation are non-fatal — Google handles a missing AggregateOffer
    gracefully, but we never want a 500 on the home view because of a
    schema helper. Returns an empty dict on any DB failure.
    """
    try:
        active_qs = Product.objects.filter(price__isnull=False).only(
            "price", "discount_percent"
        )
        prices: List[int] = []
        for product in active_qs:
            base_price = int(product.price or 0)
            if base_price <= 0:
                continue
            if product.discount_percent and product.discount_percent > 0:
                final_price = int(base_price * (100 - product.discount_percent) / 100)
            else:
                final_price = base_price
            if final_price > 0:
                prices.append(final_price)
        if not prices:
            return {}
        return {
            "lowPrice": min(prices),
            "highPrice": max(prices),
            "offerCount": len(prices),
        }
    except Exception:
        return {}


def _homepage_price_range_text() -> str:
    """Render ``priceRange`` as a single string ("880-2550 UAH")."""
    aggregate = _homepage_price_aggregate()
    if not aggregate:
        # Fall back to the published catalogue range from the brand brief
        # (BrandDNA / SEO/napolke-veteran-brands-2026.md) so the property
        # is never empty even when the DB is unavailable.
        return "880-2550 UAH"
    return f"{aggregate['lowPrice']}-{aggregate['highPrice']} UAH"


def _organization_same_as() -> List[str]:
    """Curated ``sameAs`` list for Organization / OnlineStore.

    Composes confirmed social profiles in a stable order so the
    Knowledge Graph can deduplicate the entity. Owner-confirmed
    handles only — placeholder/empty values from settings are
    silently dropped, never emitted as fake links.

    Configurable additions go through environment variables:

    * ``BRAND_FACEBOOK_URL``
    * ``BRAND_TIKTOK_URL``
    * ``BRAND_YOUTUBE_URL``
    * ``BRAND_PINTEREST_URL``
    * ``BRAND_TWITTER_URL``
    * ``BRAND_WIKIDATA_URL`` (full https://www.wikidata.org/wiki/Q… URL)

    The Instagram + Telegram base entries stay hard-coded because
    they're already public on the site footer and verified by the
    owner.
    """
    extras = []
    for env_key in (
        "BRAND_FACEBOOK_URL",
        "BRAND_TIKTOK_URL",
        "BRAND_YOUTUBE_URL",
        "BRAND_PINTEREST_URL",
        "BRAND_TWITTER_URL",
        "BRAND_WIKIDATA_URL",
    ):
        value = (getattr(settings, env_key, "") or os.environ.get(env_key, "") or "").strip()
        if value and value.startswith(("http://", "https://")):
            extras.append(value)
    base = [
        "https://instagram.com/twocomms",
        "https://t.me/twocomms",
    ]
    # Preserve order, drop dupes
    seen = set()
    out: List[str] = []
    for url in base + extras:
        if url not in seen:
            seen.add(url)
            out.append(url)
    return out


class SEOKeywordGenerator:
    """Генератор ключевых слов на основе анализа контента"""

    # Базовые ключевые слова для магазина одежды
    BASE_KEYWORDS = [
        'стріт одяг', 'мілітарі одяг', 'футболки', 'худі', 'лонгсліви',
        'ексклюзивний дизайн', 'якісний одяг', 'одяг з характером',
        'стріт стиль', 'мілітарі стиль', 'TwoComms', 'купити одяг онлайн',
        'модний одяг', 'трендовий одяг', 'український бренд'
    ]

    # Ключевые слова по категориям
    CATEGORY_KEYWORDS = {
        'футболки': ['чоловічі футболки', 'жіночі футболки', 'базові футболки', 'принтовані футболки'],
        'худі': ['чоловічі худі', 'жіночі худі', 'базові худі', 'принтовані худі'],
        'лонгсліви': ['чоловічі лонгсліви', 'жіночі лонгсліви', 'базові лонгсліви', 'принтовані лонгсліви']
    }

    # Ключевые слова по цветам
    COLOR_KEYWORDS = {
        'чорний': ['чорна футболка', 'чорне худі', 'чорний лонгслів'],
        'білий': ['біла футболка', 'біле худі', 'білий лонгслів'],
        'сірий': ['сіра футболка', 'сіре худі', 'сірий лонгслів'],
        'зелений': ['зелена футболка', 'зелене худі', 'зелений лонгслів'],
        'синій': ['синя футболка', 'синє худі', 'синій лонгслів']
    }

    @classmethod
    def extract_keywords_from_text(cls, text: str) -> List[str]:
        """Извлекает ключевые слова из текста"""
        if not text:
            return []

        # Очищаем текст от HTML тегов
        clean_text = re.sub(r'<[^>]+>', '', text)

        # Разбиваем на слова и фильтруем
        words = re.findall(r'\b[а-яіїєґ]{3,}\b', clean_text.lower())

        # Убираем стоп-слова
        stop_words = {
            'для', 'від', 'до', 'на', 'у', 'з', 'по', 'про', 'та', 'або', 'але',
            'як', 'що', 'де', 'коли', 'чому', 'який', 'яка', 'яке', 'які',
            'можна', 'потрібно', 'варто', 'краще', 'добре', 'гарний', 'якісний'
        }

        keywords = [word for word in words if word not in stop_words and len(word) > 2]

        # Подсчитываем частоту
        word_freq = {}
        for word in keywords:
            word_freq[word] = word_freq.get(word, 0) + 1

        # Сортируем по частоте и возвращаем топ-10
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        return [word for word, freq in sorted_words[:10]]

    @classmethod
    def generate_product_keywords(cls, product: Product) -> List[str]:
        """Генерирует ключевые слова для товара"""
        keywords = []

        # Базовые ключевые слова
        keywords.extend(cls.BASE_KEYWORDS)

        # Ключевые слова категории
        if product.category:
            category_name = product.category.name.lower()
            if category_name in cls.CATEGORY_KEYWORDS:
                keywords.extend(cls.CATEGORY_KEYWORDS[category_name])

        # Ключевые слова из названия товара
        title_keywords = cls.extract_keywords_from_text(product.title)
        keywords.extend(title_keywords)

        # Ключевые слова из описания
        if product.description:
            desc_keywords = cls.extract_keywords_from_text(product.description)
            keywords.extend(desc_keywords)

        # Ключевые слова по цветам (если есть цветовые варианты)
        try:
            from productcolors.models import ProductColorVariant
            color_variants = ProductColorVariant.objects.filter(product=product).select_related('color')
            for variant in color_variants:
                if variant.color and variant.color.name:
                    color_name = variant.color.name.lower()
                    if color_name in cls.COLOR_KEYWORDS:
                        keywords.extend(cls.COLOR_KEYWORDS[color_name])
        except Exception:
            pass

        # Добавляем сохраненные AI-ключевые слова ТОЛЬКО если AI явно включен
        if _ai_enabled(product) and getattr(product, 'ai_keywords', None):
            ai_keywords = [kw.strip() for kw in product.ai_keywords.split(',') if kw.strip()]
            for kw in ai_keywords:
                if kw and kw not in keywords:
                    keywords.append(kw)

        return list(dict.fromkeys(keywords))[:20]  # Максимум 20 ключевых слов

    @classmethod
    def generate_product_keywords_ai(cls, product: Product) -> List[str]:
        """Генерирует ключевые слова для товара с помощью OpenAI (если доступно)"""
        model = getattr(settings, 'OPENAI_MODEL', 'gpt-4o')
        api_key = getattr(settings, 'OPENAI_API_KEY', None) or os.environ.get('OPENAI_API_KEY')
        if not api_key:
            return []
        try:
            import openai
            client = openai.OpenAI(api_key=api_key)
        except Exception:
            return []

        color_names = []
        try:
            from productcolors.models import ProductColorVariant
            for variant in ProductColorVariant.objects.filter(product=product):
                if variant.color and getattr(variant.color, 'name', None):
                    color_names.append(variant.color.name)
        except Exception:
            color_names = []

        prompt = (
            f"Створіть до 20 SEO ключових слів для товару. Назва: {product.title}. "
            f"Категорія: {product.category.name if product.category else 'N/A'}. "
            f"Опис: {product.description or ''}. "
            f"Кольори: {', '.join(color_names) if color_names else 'N/A'}. "
            "Виведіть ключові слова через кому."
        )
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "Ви - генератор SEO ключових слів."},
                    {"role": "user", "content": prompt},
                ],
            )
            text = response.choices[0].message.get('content', '') if hasattr(response, 'choices') else ''
        except Exception:
            return []
        if not text:
            return []
        raw = [t.strip() for t in text.replace('\n', ',').split(',') if t.strip()]
        seen = set()
        keywords = []
        for w in raw:
            lw = w.lower()
            if lw not in seen:
                seen.add(lw)
                keywords.append(w)
            if len(keywords) >= 20:
                break
        return keywords

    @classmethod
    def generate_category_keywords(cls, category: Category) -> List[str]:
        """Генерирует ключевые слова для категории"""
        keywords = []

        # Базовые ключевые слова
        keywords.extend(cls.BASE_KEYWORDS)

        # Ключевые слова категории
        category_name = category.name.lower()
        if category_name in cls.CATEGORY_KEYWORDS:
            keywords.extend(cls.CATEGORY_KEYWORDS[category_name])

        # Ключевые слова из описания категории
        if category.description:
            desc_keywords = cls.extract_keywords_from_text(category.description)
            keywords.extend(desc_keywords)

        # Добавляем сохраненные AI-ключевые слова ТОЛЬКО если AI явно включен
        if _ai_enabled(category) and getattr(category, 'ai_keywords', None):
            ai_keywords = [kw.strip() for kw in category.ai_keywords.split(',') if kw.strip()]
            for kw in ai_keywords:
                if kw and kw not in keywords:
                    keywords.append(kw)

        return list(dict.fromkeys(keywords))[:15]

    @classmethod
    def generate_category_keywords_ai(cls, category: Category) -> List[str]:
        """Генерирует ключевые слова для категории с помощью OpenAI (если доступно)"""
        model = getattr(settings, 'OPENAI_MODEL', 'gpt-4o')
        api_key = getattr(settings, 'OPENAI_API_KEY', None) or os.environ.get('OPENAI_API_KEY')
        if not api_key:
            return []
        try:
            import openai
            client = openai.OpenAI(api_key=api_key)
        except Exception:
            return []
        prompt = (
            f"Створіть до 20 SEO ключових слів для категорії '{category.name}'. "
            f"Опис: {category.description or ''}."
        )
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "Ви - генератор SEO ключових слів."},
                    {"role": "user", "content": prompt},
                ],
            )
            text = resp.choices[0].message.get('content', '') if hasattr(resp, 'choices') else ''
        except Exception:
            return []
        if not text:
            return []
        raw = [t.strip() for t in text.replace('\n', ',').split(',') if t.strip()]
        seen = set()
        keywords = []
        for w in raw:
            lw = w.lower()
            if lw not in seen:
                seen.add(lw)
                keywords.append(w)
            if len(keywords) >= 20:
                break
        return keywords

    @classmethod
    def generate_meta_description(cls, product: Product) -> str:
        """Генерирует мета-описание для товара"""
        stored_description = _clean_text(getattr(product, "seo_description", ""))
        if not stored_description and _ai_enabled(product):
            stored_description = _clean_text(getattr(product, "ai_description", ""))
        if stored_description:
            return _truncate_at_word_boundary(stored_description, 160)

        category_label = product.category.name.lower() if product.category else "одяг"
        source_description = _pick_product_description_source(product)
        teaser = _truncate_at_word_boundary(source_description, 84) if source_description else f"Якісний {category_label} з характером і швидким відвантаженням."
        parts = [
            product.title,
            teaser,
            f"Ціна від {product.final_price} грн.",
            "Доставка по Україні.",
        ]
        return _truncate_at_word_boundary(" ".join(part for part in parts if part), 160)

    @classmethod
    def generate_meta_title(cls, product: Product) -> str:
        """Генерирует мета-заголовок для товара"""
        stored_title = _clean_text(getattr(product, "seo_title", ""))
        if stored_title:
            return _truncate_at_word_boundary(stored_title, 60)

        title = f"{product.title} - TwoComms"

        if product.category:
            title = f"{product.title} ({product.category.name}) - TwoComms"

        return _truncate_at_word_boundary(title, 60)


class SEOMetaGenerator:
    """Генератор SEO мета-тегов"""

    @staticmethod
    def generate_product_meta(product: Product) -> Dict[str, str]:
        """Генерирует все мета-теги для товара"""
        keywords = _clean_text(getattr(product, "seo_keywords", "")) or ", ".join(SEOKeywordGenerator.generate_product_keywords(product))
        description = SEOKeywordGenerator.generate_meta_description(product)
        title = SEOKeywordGenerator.generate_meta_title(product)

        image_url = get_default_social_image_url()
        display_image = _safe_product_display_image(product)
        if display_image:
            image_url = _build_absolute_url(display_image.url)

        return {
            'title': title,
            'description': description,
            'keywords': keywords,
            'og_title': title,
            'og_description': description,
            'og_image': image_url,
            'twitter_title': title,
            'twitter_description': description,
            'twitter_image': image_url,
        }

    @staticmethod
    def generate_category_meta(category: Category) -> Dict[str, str]:
        """Генерирует мета-теги для категории"""
        keywords = SEOKeywordGenerator.generate_category_keywords(category)

        title = f"{category.name} - TwoComms"

        # Используем сохраненное AI-описание ТОЛЬКО если AI явно включен для категории
        if _ai_enabled(category) and getattr(category, 'ai_description', None):
            description = category.ai_description[:160]
        else:
            description = f"Купити {category.name.lower()} в TwoComms. Якісний одяг з ексклюзивним дизайном. Швидка доставка по Україні."

            if category.description:
                description = _truncate_at_word_boundary(_clean_text(category.description), 160)

        cover_url = get_default_social_image_url()
        if category.cover:
            cover_url = _build_absolute_url(category.cover.url)

        return {
            'title': title,
            'description': _truncate_at_word_boundary(_clean_text(description), 160),
            'keywords': ', '.join(keywords),
            'og_title': title,
            'og_description': _truncate_at_word_boundary(_clean_text(description), 160),
            'og_image': cover_url,
            'twitter_title': title,
            'twitter_description': _truncate_at_word_boundary(_clean_text(description), 160),
            'twitter_image': cover_url,
        }


class StructuredDataGenerator:
    """Генератор структурированных данных (Schema.org)"""

    # Phase 5: SHIPPING_OPTIONS is now backed by the canonical
    # SHIPPING_TIERS dataclasses in ``services/policy.py``. Leaving
    # this attribute as a list-of-dicts for backwards compatibility
    # with any external code that imported it.
    SHIPPING_OPTIONS = shipping_tiers_as_dicts()

    @staticmethod
    def _format_decimal(value: Decimal) -> str:
        formatted = format(value, 'f')
        return formatted.rstrip('0').rstrip('.') if '.' in formatted else formatted

    @staticmethod
    def _get_return_shipping_amount() -> Dict:
        rates: List[Decimal] = []
        for option in StructuredDataGenerator.SHIPPING_OPTIONS:
            rate = option.get("rate")
            if rate is None:
                continue
            try:
                rates.append(Decimal(str(rate)))
            except Exception:
                continue

        if not rates:
            value = "0"
        else:
            min_rate = min(rates)
            value = StructuredDataGenerator._format_decimal(min_rate)

        return {
            "@type": "MonetaryAmount",
            "value": value,
            "currency": CURRENCY,
        }

    @staticmethod
    def _get_dynamic_price_valid_until() -> str:
        """Returns a priceValidUntil date 90 days from today in ISO format."""
        return (timezone.now().date() + timedelta(days=90)).isoformat()

    @staticmethod
    def _get_product_availability(product: Product) -> str:
        """Return the canonical Schema.org availability URI for a product.

        SEO v1.0 Phase 11 (2026-05-12) — finding (QQ). Live prod observation
        showed *every* PDP returning ``OutOfStock`` because the per-colour
        ``ProductColorVariant.stock`` row defaults to 0 in the admin and the
        old logic only flipped to ``InStock`` when at least one variant had
        an explicit positive stock count. TwoComms produces every garment
        on demand via DTF print after the order is placed, so the legacy
        boolean «do we hold a finished SKU on the shelf?» is the wrong
        question — and emitting OutOfStock blocks the catalogue from
        Google Shopping, Facebook Catalog, Pinterest Rich Pins and
        Perplexity / SGE shopping answers.

        New rules (in priority order):

        1. ``is_dropship_available=False`` → admin explicitly disabled
           sale of the product → OutOfStock (true negative).
        2. Any colour variant with ``stock > 0`` → InStock (kept for the
           rare cases when admins do track finished pieces).
        3. Variants exist but all stock=0 → ``MadeToOrder`` — the
           Schema.org-blessed value for on-demand items. Google's rich
           result spec accepts MadeToOrder as a valid availability state
           and surfaces the product without the «out of stock» badge.
        4. No variants at all → InStock (legacy fallback for products
           authored before the colour matrix was introduced).
        """
        if not getattr(product, "is_dropship_available", True):
            return "https://schema.org/OutOfStock"

        try:
            from productcolors.models import ProductColorVariant

            variants = ProductColorVariant.objects.filter(product=product).only("stock")
            if variants.exists():
                has_stock = any(int(getattr(variant, "stock", 0) or 0) > 0 for variant in variants)
                if has_stock:
                    return "https://schema.org/InStock"
                # All variants report stock=0 → DTF on-demand. Use the
                # Schema.org MadeToOrder URI so Google still considers
                # the product purchasable.
                return "https://schema.org/MadeToOrder"
        except Exception:
            pass

        return "https://schema.org/InStock"

    @staticmethod
    def _build_shipping_delivery_time() -> Dict:
        return {
            "@type": "ShippingDeliveryTime",
            "businessDays": {
                "@type": "OpeningHoursSpecification",
                "dayOfWeek": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
            },
            "cutoffTime": "14:00",
            "handlingTime": {
                "@type": "QuantitativeValue",
                "minValue": 1,
                "maxValue": 2,
                "unitCode": "DAY"
            },
            "transitTime": {
                "@type": "QuantitativeValue",
                "minValue": 1,
                "maxValue": 5,
                "unitCode": "DAY"
            }
        }

    @staticmethod
    def _get_weight_based_shipping_details() -> List[Dict]:
        shipping_details: List[Dict] = []
        for option in StructuredDataGenerator.SHIPPING_OPTIONS:
            weight_spec: Dict[str, object] = {"@type": "QuantitativeValue", "unitCode": "KGM"}
            if "min_weight" in option:
                weight_spec["minValue"] = option["min_weight"]
            if "max_weight" in option:
                weight_spec["maxValue"] = option["max_weight"]

            shipping_details.append({
                "@type": "OfferShippingDetails",
                "shippingRate": {
                    "@type": "MonetaryAmount",
                    "value": option["rate"],
                    "currency": CURRENCY,
                },
                "shippingDestination": {
                    "@type": "DefinedRegion",
                    "addressCountry": APPLICABLE_COUNTRY,
                },
                "deliveryTime": StructuredDataGenerator._build_shipping_delivery_time(),
                "shippingWeight": weight_spec,
            })

        return shipping_details

    @staticmethod
    def generate_product_schema(
        product: Product,
        canonical_path: Optional[str] = None,
        selected_variant=None,
        review_summary=None,
    ) -> Dict:
        """Генерирует Product schema для товара (совместимо с Google Merchant Center).

        Phase 21 (2026-05-10) — accepts ``canonical_path`` and
        ``selected_variant`` so schema ``url`` and ``image`` track the
        page's canonical strategy:
          * On a self-canonical colour/fit page, ``url`` is the variant
            URL (matches ``<link rel=canonical>``).
          * On a size-only page (canonical → base) or the base page,
            ``url`` is the base product URL.
          * If ``selected_variant`` (a ``ProductColorVariant``) is
            provided, its images are surfaced first so OG/Twitter and
            schema ``image`` reflect the visual on the page.
        """
        # Базовые изображения
        images: list[str] = []

        # Phase 21 — variant images first when a variant is selected
        # so the ``image[0]`` slot (used for OG/Twitter) matches the
        # rendered hero image on a colour-variant PDP.
        if selected_variant is not None:
            try:
                for img in selected_variant.images.all()[:3]:
                    candidate = _build_absolute_url(img.image.url)
                    if candidate not in images:
                        images.append(candidate)
            except Exception:
                pass

        display_image = _safe_product_display_image(product)
        if display_image:
            candidate = _build_absolute_url(display_image.url)
            if candidate not in images:
                images.append(candidate)

        # Добавляем дополнительные изображения
        try:
            for img in product.images.all()[:4]:  # Максимум 4 дополнительных изображения
                candidate = _build_absolute_url(img.image.url)
                if candidate not in images:
                    images.append(candidate)
        except Exception:
            pass

        # Добавляем изображения из цветовых вариантов (для остальных вариантов)
        try:
            from productcolors.models import ProductColorVariant
            color_variants = ProductColorVariant.objects.filter(product=product).prefetch_related('images')
            for variant in color_variants[:2]:  # Максимум 2 цветовых варианта
                if selected_variant is not None and getattr(variant, 'pk', None) == getattr(selected_variant, 'pk', None):
                    continue
                for img in variant.images.all()[:2]:
                    candidate = _build_absolute_url(img.image.url)
                    if candidate not in images:
                        images.append(candidate)
        except Exception:
            pass

        if not images:
            images.append(get_default_social_image_url())

        description = _truncate_at_word_boundary(
            _pick_product_description_source(product)
            or f"Якісний {product.category.name.lower() if product.category else 'одяг'} з ексклюзивним дизайном від TwoComms",
            320,
        )
        material = _guess_product_material(product)

        # Phase 21 — schema URL must mirror the page's canonical strategy.
        # ``canonical_path`` (if provided by the view) already reflects
        # whether the variant page is self-canonical or collapses to the
        # base product. Falls back to base for callers that don't yet
        # pass it (e.g. Merchant feed, sitemap-images).
        if canonical_path:
            cp = canonical_path.lstrip("/")
            product_canonical_url = _build_absolute_url(cp)
        else:
            product_canonical_url = _build_absolute_url(f"product/{product.slug}/")

        schema = {
            "@context": "https://schema.org",
            "@type": "Product",
            # SEO molecular-upgrade US-8 (2026-05-16) — stable @id so AI
            # knowledge graphs can deduplicate Product entities across
            # variant URLs and sitemap rebuilds. Anchored to canonical
            # URL so colour/fit variants (whose canonical_path includes
            # the variant slug) get their own ID; size-only facets
            # collapse to the base.
            "@id": f"{product_canonical_url}#product",
            # SEO v1.1 (2026-05-16) — Phase 17v. Derive inLanguage from
            # the active locale so /ru/ and /en/ Product schemas declare
            # the correct language. Previously hardcoded uk-UA, which
            # caused Google Search Console to flag /ru/ and /en/ as
            # "schema language doesn't match page language".
            "inLanguage": StructuredDataGenerator._resolve_inlanguage_code(),
            "name": product.title,
            "description": description,
            "sku": f"TC-{product.id}",
            "mpn": f"TC-{product.id}",  # Manufacturer Part Number
            "url": product_canonical_url,
            "image": images[0] if len(images) == 1 else images,
            "material": StructuredDataGenerator._localized_attr(
                product, "material", fallback=str(material or "")
            ),
            "countryOfOrigin": {
                "@type": "Country",
                "name": _("Україна"),
            },
            "additionalProperty": [
                {
                    "@type": "PropertyValue",
                    "name": _("Матеріал"),
                    "value": StructuredDataGenerator._localized_attr(
                        product, "material", fallback=str(material or "")
                    ),
                },
                {
                    "@type": "PropertyValue",
                    "name": _("Країна виробництва"),
                    "value": _("Україна"),
                },
                {
                    "@type": "PropertyValue",
                    "name": _("Стиль"),
                    "value": _("Стріт & Мілітарі"),
                },
            ],
            "brand": {
                "@id": f"{_build_absolute_url('')}#brand"
            },
            "manufacturer": {
                "@id": f"{_build_absolute_url('')}#organization"
            },
            "offers": {
                "@type": "Offer",
                "price": str(product.final_price),
                "priceCurrency": "UAH",
                "availability": StructuredDataGenerator._get_product_availability(product),
                "itemCondition": "https://schema.org/NewCondition",
                "url": product_canonical_url,
                "priceValidUntil": StructuredDataGenerator._get_dynamic_price_valid_until(),
                "hasMerchantReturnPolicy": {
                    "@type": "MerchantReturnPolicy",
                    "returnPolicyCategory": RETURN_POLICY["category"],
                    "merchantReturnDays": RETURN_POLICY["days"],
                    "returnMethod": RETURN_POLICY["method"],
                    "returnFees": RETURN_POLICY["fees_type"],
                    "returnShippingFeesAmount": StructuredDataGenerator._get_return_shipping_amount(),
                    "applicableCountry": APPLICABLE_COUNTRY,
                },
                "seller": {
                    "@id": f"{_build_absolute_url('')}#organization"
                },
                "shippingDetails": StructuredDataGenerator._get_weight_based_shipping_details()
            },
        }

        # SEO 2026-05-16 (P1-9) — emit ``releaseDate`` and ``dateModified``
        # so AI search engines (Perplexity, ChatGPT Search, Google AI
        # Overviews) can score freshness per product. Mirrors what we
        # already do on Article schema for the DTF blog. Skip silently
        # if the underlying datetimes are missing (e.g. fixtures-only
        # rows during tests) — the rest of the schema stays valid.
        try:
            created_at = getattr(product, "created_at", None)
            updated_at = getattr(product, "updated_at", None)
            if created_at is not None:
                if hasattr(created_at, "isoformat"):
                    schema["releaseDate"] = created_at.isoformat() if getattr(
                        created_at, "tzinfo", None
                    ) else created_at.date().isoformat()
                else:
                    schema["releaseDate"] = str(created_at)
            if updated_at is not None:
                if hasattr(updated_at, "isoformat"):
                    schema["dateModified"] = updated_at.isoformat() if getattr(
                        updated_at, "tzinfo", None
                    ) else updated_at.date().isoformat()
                else:
                    schema["dateModified"] = str(updated_at)
        except Exception:
            # Defensive: never break the whole schema over a
            # date-formatting hiccup.
            pass

        # Phase 21 (2026-05-10) — embed AggregateRating only when the
        # caller passes a ``review_summary`` whose ``show_rating`` is
        # True. SEO v1.0 Phase 12 (2026-05-13) — finding (M) lowered
        # the underlying ``MIN_APPROVED_REVIEWS_FOR_RATING`` from 3
        # to 1, so this branch now activates the moment a single
        # approved review exists on the product. Mirrors the rule in
        # ``reviews.services.aggregate.MIN_APPROVED_REVIEWS_FOR_RATING``
        # so we never emit fake or thin rating signals to Google.
        if review_summary is not None and getattr(review_summary, "show_rating", False):
            avg = getattr(review_summary, "avg", None)
            count = int(getattr(review_summary, "count", 0) or 0)
            if avg is not None and count >= 1:
                schema["aggregateRating"] = {
                    "@type": "AggregateRating",
                    "ratingValue": f"{float(avg):.1f}",
                    "reviewCount": str(count),
                    "bestRating": "5",
                    "worstRating": "1",
                }

                # Nested top-5 Review JSON-LD. Live-queried here so the
                # schema mirrors what's currently on the page; the same
                # threshold (``MIN_APPROVED_REVIEWS_FOR_RATING``, lowered
                # from 3 to 1 in SEO v1.0 Phase 12 — finding (M)) gates
                # surfacing, so once a single approved review exists the
                # nested ``Review`` blocks ride along with
                # ``aggregateRating`` and feed the rich-result snippet.
                try:
                    from reviews.models import Review as _Review, ReviewStatus as _RS
                    top_reviews = list(
                        _Review.objects
                        .filter(product=product, status=_RS.APPROVED)
                        .order_by("-helpful_count", "-created_at")[:5]
                    )
                except Exception:
                    top_reviews = []
                review_blocks = []
                for r in top_reviews:
                    block = {
                        "@type": "Review",
                        "reviewRating": {
                            "@type": "Rating",
                            "ratingValue": str(int(r.rating)),
                            "bestRating": "5",
                            "worstRating": "1",
                        },
                        "author": {"@type": "Person", "name": r.author_name or "TwoComms клієнт"},
                        "datePublished": r.created_at.date().isoformat() if r.created_at else "",
                    }
                    if r.title:
                        block["name"] = r.title
                    if r.body:
                        # Cap to 600 chars — Google ignores giant review
                        # bodies and we don't want to bloat per-page schema.
                        block["reviewBody"] = (r.body[:600] + "…") if len(r.body) > 600 else r.body
                    review_blocks.append(block)
                if review_blocks:
                    schema["review"] = review_blocks

        # Merchant-level properties (age_group, gender, google_product_category)
        age_group = "adult"
        gender = "unisex"
        if product.category:
            category_name = product.category.name.lower()
            if any(word in category_name for word in ['чоловіч', 'мужск', 'men']):
                gender = "male"
            elif any(word in category_name for word in ['жіноч', 'женск', 'women']):
                gender = "female"

        # SEO molecular-upgrade US-8 (2026-05-16) — explicit
        # PeopleAudience so Google Shopping / AI Search can resolve
        # gender targeting without parsing additionalProperty. Maps the
        # already-derived ``gender`` to schema.org audienceType vocab.
        audience_type_map = {
            "male": "Men",
            "female": "Women",
            "unisex": "Adults",
        }
        suggested_gender_map = {
            "male": "https://schema.org/Male",
            "female": "https://schema.org/Female",
            "unisex": "https://schema.org/Unisex",
        }
        schema["audience"] = {
            "@type": "PeopleAudience",
            "audienceType": audience_type_map.get(gender, "Adults"),
            "suggestedGender": suggested_gender_map.get(gender, "https://schema.org/Unisex"),
            "suggestedMinAge": 16,
        }

        schema["additionalProperty"].extend([
            {"@type": "PropertyValue", "name": "age_group", "value": age_group},
            {"@type": "PropertyValue", "name": "gender", "value": gender},
            {"@type": "PropertyValue", "name": "size_type", "value": "regular"},
            {"@type": "PropertyValue", "name": "size_system", "value": "UA"},
        ])

        # Добавляем категорию
        if product.category:
            schema["category"] = product.category.name
            schema["additionalProperty"].append({
                "@type": "PropertyValue",
                "name": "google_product_category",
                "value": "1604"  # Apparel & Accessories > Clothing
            })

        # Добавляем все изображения
        # Добавляем реальные цвета из вариантов
        try:
            from productcolors.models import ProductColorVariant
            from storefront.services.color_filter import _translate_color_label
            color_names = []
            color_variants = ProductColorVariant.objects.filter(product=product).select_related('color')
            for variant in color_variants:
                if variant.color and variant.color.name:
                    color_names.append(str(_translate_color_label(variant.color.name)))
            if color_names:
                unique_colors = list(dict.fromkeys(color_names))[:5]
                schema["color"] = ", ".join(unique_colors)
                schema["additionalProperty"].append({
                    "@type": "PropertyValue",
                    "name": _("Колір"),
                    "value": ", ".join(unique_colors)
                })
            else:
                schema["additionalProperty"].append({
                    "@type": "PropertyValue",
                    "name": _("Колір"),
                    "value": _("Різні кольори"),
                })
        except Exception:
            schema["additionalProperty"].append({
                "@type": "PropertyValue",
                "name": _("Колір"),
                "value": _("Різні кольори"),
            })

        # Добавляем размеры
        resolved_sizes = resolve_product_sizes(product)
        if resolved_sizes:
            schema["size"] = ", ".join(resolved_sizes)
            schema["additionalProperty"].append({
                "@type": "PropertyValue",
                "name": _("Розміри"),
                "value": ", ".join(resolved_sizes)
            })

        # Добавляем скидку если есть
        if product.has_discount:
            schema["offers"]["priceSpecification"] = {
                "@type": "CompoundPriceSpecification",
                "price": str(product.final_price),
                "priceCurrency": "UAH",
                "referenceQuantity": {
                    "@type": "QuantitativeValue",
                    "value": 1,
                    "unitCode": "C62"
                }
            }

        # Respect product.seo_schema as JSON override (merge with generated)
        if product.seo_schema and isinstance(product.seo_schema, dict):
            for key, value in product.seo_schema.items():
                if key not in ('@context', '@type'):
                    schema[key] = value

        return schema

    @staticmethod
    def generate_google_merchant_schema(product: Product) -> Dict:
        """
        DEPRECATED: Use generate_product_schema() instead.
        Now returns the same unified product schema to avoid duplicate JSON-LD blocks.
        """
        return StructuredDataGenerator.generate_product_schema(product)

    @staticmethod
    def generate_breadcrumb_schema(breadcrumbs: List[Dict]) -> Dict:
        """Generate BreadcrumbList schema.

        SEO v1.0 Phase 4 (2026-05-12) — finding (B24). The previous
        payload only annotated the leaf ListItem nodes with ``@id``; the
        parent ``BreadcrumbList`` had none, so when the same trail was
        emitted on multiple pages (PDP + variant + parent category)
        Google could not deduplicate them via the @graph reference
        pattern. Derive a deterministic ``@id`` from the trail itself —
        a hash over the ordered URL list — so identical breadcrumb
        chains share a single node in the Knowledge Graph.
        """
        schema = {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": []
        }

        item_urls: List[str] = []
        for i, breadcrumb in enumerate(breadcrumbs):
            item_url = _build_absolute_url(breadcrumb.get("url", ""))
            item_urls.append(item_url)
            schema["itemListElement"].append({
                "@type": "ListItem",
                "@id": item_url,
                "position": i + 1,
                # Force-resolve gettext_lazy proxies so json.dumps does
                # not blow up with "Object of type __proxy__ is not
                # JSON serializable" when callers pass localized labels.
                "name": str(breadcrumb.get("name", "")),
                "item": item_url
            })

        # Stable @id — last item's URL with a #breadcrumbs anchor lets
        # Google merge identical trails across PDP / variant pages while
        # still being human-meaningful when inspected in Search Console.
        if item_urls:
            schema["@id"] = f"{item_urls[-1].rstrip('/')}/#breadcrumbs"

        return schema

    @staticmethod
    def _resolve_inlanguage_code() -> str:
        """Map the active Django locale to a Google-friendly inLanguage code.

        SEO v1.1 (2026-05-16) — Phase 17v. Previously hardcoded ``uk-UA``
        on every locale, which made Google flag /ru/ and /en/ pages as
        schema-language mismatch. Now derived from ``get_language()``:
            uk → uk-UA   ru → ru-UA   en → en-US
        Defaults to uk-UA if no locale is active (e.g. background tasks).
        """
        lang = (get_language() or "uk").split("-", 1)[0].lower()
        return {
            "uk": "uk-UA",
            "ru": "ru-UA",
            "en": "en-US",
        }.get(lang, "uk-UA")

    @staticmethod
    def _localized_attr(obj, attr: str, fallback: str = "") -> str:
        """Pick a locale-specific model attribute with a UA fallback.

        Used by Product schema to surface ``material_ru`` / ``material_en``
        when modeltranslation has populated them, otherwise falls back to
        the canonical Ukrainian field. ``fallback`` is the literal value
        to return if both the localized and base attributes are empty.
        """
        lang = (get_language() or "uk").split("-", 1)[0].lower()
        if lang and lang != "uk":
            localized = getattr(obj, f"{attr}_{lang}", None)
            if localized:
                return localized
        base = getattr(obj, attr, None) or getattr(obj, f"{attr}_uk", None)
        return base or fallback

    @staticmethod
    def generate_organization_schema() -> Dict:
        """Generates the canonical Organization schema for TwoComms.

        Phase 5 — single source of truth. This is the same payload that
        ``pages/pro_brand.html`` previously hard-coded inline. The
        ``@id`` is stable across pages so Google can deduplicate
        instances of this Organization in the Knowledge Graph.

        SEO 2026-05-16 (P1-5/P1-7) — added ``founder`` reference,
        ``foundingDate``, ``foundingLocation`` and an ``address`` block
        with the canonical Kharkiv NAP signals so AI knowledge graphs
        and Google's Knowledge Panel can resolve TwoComms as a
        Kharkiv-rooted brand instead of inferring "Ukraine, location
        unknown" from the contact channels alone.

        SEO molecular-upgrade US-13 / homepage commerce signals —
        ``image`` (1200x630 social preview) so Knowledge Panel has a
        non-SVG visual fallback, ``slogan`` for AI-cite snippet,
        explicit ``knowsLanguage`` triple and Brand-typed alias.
        ``sameAs`` left at minimum verified set (Instagram + Telegram);
        adding more requires owner-confirmed handles.
        """
        base_url = _build_absolute_url("")
        logo_url = _build_absolute_url("static/img/logo.svg")
        social_image = _build_absolute_url(DEFAULT_SOCIAL_IMAGE_PATH)
        return {
            "@context": "https://schema.org",
            "@type": ["Organization", "OnlineStore"],
            "@id": f"{base_url}#organization",
            "name": "TwoComms",
            "alternateName": "TwoComms / TWOCOMMS",
            "url": base_url,
            "logo": {
                "@type": "ImageObject",
                "url": logo_url,
                "contentUrl": logo_url,
                "caption": "TwoComms logo",
            },
            "image": social_image,
            "slogan": _(
                "Не крапка, а продовження. Український streetwear із Харкова."
            ),
            "description": _(
                "TwoComms — український streetwear / military-adjacent бренд "
                "одягу з Харкова, створений навколо ідеї продовження після "
                "критичної точки: не крапка, а продовження."
            ),
            "foundingDate": "2022",
            "foundingLocation": {
                "@type": "Place",
                "name": _("Харків, Україна"),
                "address": {
                    "@type": "PostalAddress",
                    "addressCountry": "UA",
                    "addressRegion": "UA-63",
                    "addressLocality": _("Харків"),
                },
            },
            "address": {
                "@type": "PostalAddress",
                "addressCountry": "UA",
                "addressRegion": "UA-63",
                "addressLocality": _("Харків"),
            },
            "areaServed": {
                "@type": "Country",
                "name": "Ukraine",
                "identifier": "UA",
            },
            "knowsLanguage": ["uk", "ru", "en"],
            "currenciesAccepted": "UAH",
            "paymentAccepted": "Cash, Credit Card, Apple Pay, Google Pay",
            "priceRange": _homepage_price_range_text(),
            "founder": {"@id": f"{base_url}#founder"},
            "sameAs": _organization_same_as(),
            "contactPoint": {
                "@type": "ContactPoint",
                "telephone": "+380966543212",
                "contactType": "customer support",
                "availableLanguage": ["uk", "ru", "en"],
                "areaServed": "UA",
            },
            "brand": {
                "@type": "Brand",
                "@id": f"{base_url}#brand",
                "name": "TwoComms",
                "logo": logo_url,
            },
        }

    @staticmethod
    def generate_website_schema() -> Dict:
        """Generates the WebSite schema with a SearchAction.

        Phase 5 — single source of truth. The ``target`` URL points at
        the real ``/search/`` route registered in ``storefront/urls.py``.
        """
        base_url = _build_absolute_url("")
        return {
            "@context": "https://schema.org",
            "@type": "WebSite",
            "@id": f"{base_url}#website",
            "name": "TwoComms",
            "url": base_url,
            "description": _("Магазин стріт & мілітарі одягу з ексклюзивним дизайном"),
            "potentialAction": {
                "@type": "SearchAction",
                "target": {
                    "@type": "EntryPoint",
                    "urlTemplate": f"{base_url}search/?q={{search_term_string}}",
                },
                "query-input": "required name=search_term_string",
            },
        }

    @staticmethod
    def generate_homepage_storefront_schema() -> Dict:
        """Storefront commerce node for the homepage (US-16).

        Why this exists
        ---------------
        The homepage previously emitted only ``WebPage`` + ``ItemList``
        (categories), without any explicit price signal. Google's SERP
        renderer therefore fell back to heuristic price extraction,
        which scraped the survey banner ("ВИГРАЙ 200 ГРН" + "-200 грн")
        and rendered ``200 200,00 грн`` underneath the ru-UA homepage
        snippet — actively misleading prospective customers.

        Mitigation strategy: emit an ``OnlineStore`` node anchored to
        ``#storefront`` with explicit ``priceRange`` derived from live
        catalogue prices, plus a ``makesOffer`` AggregateOffer that
        resolves Google's price-snippet attribution to the real
        catalogue range. Combined with the survey-banner numeric
        decoupling fix in ``index.html``, this removes the hallucinated
        ``200 200 грн`` price entirely.

        The node references the canonical Organization ``@id`` so the
        Knowledge Graph stays deduplicated.
        """
        base_url = _build_absolute_url("")
        social_image = _build_absolute_url(DEFAULT_SOCIAL_IMAGE_PATH)
        aggregate = _homepage_price_aggregate()

        node: Dict[str, object] = {
            "@context": "https://schema.org",
            "@type": "OnlineStore",
            "@id": f"{base_url}#storefront",
            "name": "TwoComms",
            "url": base_url,
            "image": social_image,
            "logo": _build_absolute_url("static/img/logo.svg"),
            "description": _(
                "Український онлайн-магазин стріт- та мілітарі-одягу TwoComms: "
                "футболки, худі, лонгсліви та кастомний DTF-друк."
            ),
            "telephone": "+380966543212",
            "currenciesAccepted": "UAH",
            "paymentAccepted": "Cash, Credit Card, Apple Pay, Google Pay",
            "priceRange": _homepage_price_range_text(),
            "areaServed": {"@type": "Country", "name": "Ukraine", "identifier": "UA"},
            "parentOrganization": {"@id": f"{base_url}#organization"},
            "sameAs": _organization_same_as(),
            "contactPoint": {
                "@type": "ContactPoint",
                "telephone": "+380966543212",
                "contactType": "customer support",
                "availableLanguage": ["uk", "ru", "en"],
                "areaServed": "UA",
            },
        }

        if aggregate:
            node["makesOffer"] = {
                "@type": "AggregateOffer",
                "priceCurrency": "UAH",
                "lowPrice": aggregate["lowPrice"],
                "highPrice": aggregate["highPrice"],
                "offerCount": aggregate["offerCount"],
                "availability": "https://schema.org/InStock",
                "seller": {"@id": f"{base_url}#organization"},
            }

        return node

    @staticmethod
    def generate_faq_schema(faq_items: List[Dict]) -> Dict:
        """Генерирует FAQ schema"""
        schema = {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": []
        }

        for faq in faq_items:
            schema["mainEntity"].append({
                "@type": "Question",
                "name": faq["question"],
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": faq["answer"]
                }
            })

        return schema


class SEOContentOptimizer:
    """Оптимизатор контента для SEO"""

    @staticmethod
    def suggest_content_improvements(product: Product) -> List[str]:
        """Предлагает улучшения контента для товара"""
        suggestions = []

        # Проверяем длину описания
        if not product.description or len(product.description) < 100:
            suggestions.append("Додайте детальний опис товару (мінімум 100 символів)")

        # Проверяем наличие изображений
        if not product.display_image:
            suggestions.append("Додайте головне зображення товару")

        # Проверяем наличие цветовых вариантов
        try:
            from productcolors.models import ProductColorVariant
            color_count = ProductColorVariant.objects.filter(product=product).count()
            if color_count == 0:
                suggestions.append("Додайте кольорові варіанти товару")
        except ImportError:
            pass

        # Проверяем длину названия
        if len(product.title) < 10:
            suggestions.append("Збільште назву товару для кращого SEO")

        return suggestions

    @staticmethod
    def generate_alt_text_for_image(image_name: str, product_title: str = "") -> str:
        """Генерирует alt-текст для изображения"""
        if product_title:
            return f"Зображення товару {product_title}"

        # Извлекаем ключевые слова из имени файла
        clean_name = re.sub(r'[^a-zA-Zа-яіїєґ0-9\s]', ' ', image_name.lower())
        words = clean_name.split()

        if words:
            return f"Зображення {' '.join(words[:3])}"

        return "Зображення товару TwoComms"

    @staticmethod
    def generate_ai_category_description(category: Category) -> str:
        """Генерирует AI-описание категории для SEO (если доступно)"""
        try:
            from django.conf import settings
            if not getattr(settings, 'USE_AI_DESCRIPTIONS', False):
                return ''
            api_key = getattr(settings, 'OPENAI_API_KEY', None) or __import__('os').environ.get('OPENAI_API_KEY')
            if not api_key:
                return ''
            import openai
            client = openai.OpenAI(api_key=api_key)
            model = getattr(settings, 'OPENAI_MODEL', 'gpt-4o')
            prompt = (
                f"Напишіть стислий SEO-дружній опис категорії '{category.name}'. "
            )
            if category.description:
                prompt += f" Опис: {category.description}."
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "Ви - SEO-копірайтер."},
                    {"role": "user", "content": prompt},
                ],
            )
            text = resp.choices[0].message.get('content', '') if hasattr(resp, 'choices') and resp.choices else ''
            return text.strip() if text else ''
        except Exception:
            return ''

    @staticmethod
    def generate_ai_product_description(product: Product) -> str:
        """Генерирует AI-описание товара для SEO (если доступно)"""
        try:
            from django.conf import settings
            use_descriptions = getattr(settings, 'USE_AI_DESCRIPTIONS', False)
            if isinstance(use_descriptions, str):
                use_descriptions = use_descriptions.lower() in ('1', 'true', 'yes')
            if not use_descriptions:
                return ''
            api_key = getattr(settings, 'OPENAI_API_KEY', None) or os.environ.get('OPENAI_API_KEY')
            if not api_key:
                return ''
            import openai
            client = openai.OpenAI(api_key=api_key)
            model = getattr(settings, 'OPENAI_MODEL', 'gpt-4o')
            prompt = (
                f"Напишіть стислий SEO-дружній опис товару '{product.title}'. "
                f"Категорія: {product.category.name if product.category else 'N/A'}. "
                f"Ціна: {product.final_price}."
            )
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "Ви - SEO-копірайтер."},
                    {"role": "user", "content": prompt},
                ],
            )
            text = ''
            if hasattr(resp, 'choices') and resp.choices:
                text = resp.choices[0].message.get('content', '') if isinstance(resp.choices[0].message, dict) else ''
            return text.strip() if text else ''
        except Exception:
            return ''


# Глобальные функции для использования в шаблонах
def get_product_seo_meta(product: Product) -> Dict[str, str]:
    """Возвращает SEO мета-теги для товара"""
    try:
        return SEOMetaGenerator.generate_product_meta(product)
    except Exception as e:
        # Возвращаем базовые мета-теги в случае ошибки
        return {
            'title': f"{product.title} - TwoComms",
            'description': f"Купити {product.title} в TwoComms. Якісний одяг з ексклюзивним дизайном.",
            'keywords': 'стріт одяг, мілітарі одяг, TwoComms',
            'og_title': f"{product.title} - TwoComms",
            'og_description': f"Купити {product.title} в TwoComms. Якісний одяг з ексклюзивним дизайном.",
            'og_image': product.main_image.url if product.main_image else '',
            'twitter_title': f"{product.title} - TwoComms",
            'twitter_description': f"Купити {product.title} в TwoComms. Якісний одяг з ексклюзивним дизайном.",
            'twitter_image': product.main_image.url if product.main_image else '',
        }


def get_category_seo_meta(category: Category) -> Dict[str, str]:
    """Возвращает SEO мета-теги для категории"""
    try:
        return SEOMetaGenerator.generate_category_meta(category)
    except Exception as e:
        # Возвращаем базовые мета-теги в случае ошибки
        return {
            'title': f"{category.name} - TwoComms",
            'description': f"Купити {category.name.lower()} в TwoComms. Якісний одяг з ексклюзивним дизайном.",
            'keywords': 'стріт одяг, мілітарі одяг, TwoComms',
            'og_title': f"{category.name} - TwoComms",
            'og_description': f"Купити {category.name.lower()} в TwoComms. Якісний одяг з ексклюзивним дизайном.",
            'og_image': category.cover.url if category.cover else '',
            'twitter_title': f"{category.name} - TwoComms",
            'twitter_description': f"Купити {category.name.lower()} в TwoComms. Якісний одяг з ексклюзивним дизайном.",
            'twitter_image': category.cover.url if category.cover else '',
        }


def get_product_schema(
    product: Product,
    canonical_path: Optional[str] = None,
    selected_variant=None,
    review_summary=None,
) -> str:
    """Возвращает JSON-LD schema для товара.

    Phase 21 — propagates ``canonical_path``, ``selected_variant`` and
    ``review_summary`` to the underlying generator so the rendered
    Product schema's ``url``, ``image`` and ``aggregateRating`` always
    match what the page declares as canonical / approved.
    """
    try:
        schema = StructuredDataGenerator.generate_product_schema(
            product,
            canonical_path=canonical_path,
            selected_variant=selected_variant,
            review_summary=review_summary,
        )
        return json.dumps(schema, ensure_ascii=False, indent=2)
    except Exception:
        return ""


def get_breadcrumb_schema(breadcrumbs: List[Dict]) -> str:
    """Возвращает JSON-LD schema для хлебных крошек"""
    try:
        schema = StructuredDataGenerator.generate_breadcrumb_schema(breadcrumbs)
        return json.dumps(schema, ensure_ascii=False, indent=2)
    except Exception as e:
        # Возвращаем пустую строку в случае ошибки
        return ""


def get_google_merchant_schema(product: Product) -> str:
    """Возвращает JSON-LD schema для Google Merchant Center"""
    try:
        schema = StructuredDataGenerator.generate_google_merchant_schema(product)
        return json.dumps(schema, ensure_ascii=False, indent=2)
    except Exception as e:
        # Возвращаем пустую строку в случае ошибки
        return ""
