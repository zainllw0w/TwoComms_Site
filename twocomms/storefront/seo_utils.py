"""
SEO утилиты для автоматической генерации мета-тегов и ключевых слов
"""
import re
import json
import os
from datetime import timedelta
from decimal import Decimal
from typing import List, Dict
from urllib.parse import urljoin
from django.conf import settings
from django.utils import timezone
from .models import Product, Category
from .services.size_guides import resolve_product_sizes

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


def _pick_product_description_source(product: Product) -> str:
    for attr in ("seo_description", "short_description", "ai_description", "full_description", "description"):
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
        except ImportError:
            pass

        # Добавляем сохраненные AI-ключевые слова, если они есть
        if hasattr(product, 'ai_keywords') and product.ai_keywords:
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

        # Добавляем сохраненные AI-ключевые слова, если они есть
        if hasattr(category, 'ai_keywords') and category.ai_keywords:
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
        stored_description = _clean_text(getattr(product, "seo_description", "")) or _clean_text(getattr(product, "ai_description", ""))
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
        if product.display_image:
            image_url = _build_absolute_url(product.display_image.url)

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

        # Используем сохраненное AI-описание, если оно есть
        if hasattr(category, 'ai_description') and category.ai_description:
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

    SHIPPING_OPTIONS = [
        {"rate": "85", "max_weight": 2.0},
        {"rate": "180", "min_weight": 2.01, "max_weight": 5.0},
        {"rate": "220", "min_weight": 5.01}
    ]

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
            "currency": "UAH"
        }

    @staticmethod
    def _get_dynamic_price_valid_until() -> str:
        """Returns a priceValidUntil date 90 days from today in ISO format."""
        return (timezone.now().date() + timedelta(days=90)).isoformat()

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
                    "currency": "UAH"
                },
                "shippingDestination": {
                    "@type": "DefinedRegion",
                    "addressCountry": "UA"
                },
                "deliveryTime": StructuredDataGenerator._build_shipping_delivery_time(),
                "shippingWeight": weight_spec
            })

        return shipping_details

    @staticmethod
    def generate_product_schema(product: Product) -> Dict:
        """Генерирует Product schema для товара (совместимо с Google Merchant Center)"""
        # Базовые изображения
        images = []
        if product.display_image:
            images.append(_build_absolute_url(product.display_image.url))

        # Добавляем дополнительные изображения
        try:
            for img in product.images.all()[:4]:  # Максимум 4 дополнительных изображения
                images.append(_build_absolute_url(img.image.url))
        except Exception:
            pass

        # Добавляем изображения из цветовых вариантов
        try:
            from productcolors.models import ProductColorVariant
            color_variants = ProductColorVariant.objects.filter(product=product).prefetch_related('images')
            for variant in color_variants[:2]:  # Максимум 2 цветовых варианта
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

        schema = {
            "@context": "https://schema.org",
            "@type": "Product",
            "name": product.title,
            "description": description,
            "sku": f"TC-{product.id}",
            "mpn": f"TC-{product.id}",  # Manufacturer Part Number
            "url": _build_absolute_url(f"product/{product.slug}/"),
            "image": images[0] if len(images) == 1 else images,
            "material": material,
            "countryOfOrigin": {
                "@type": "Country",
                "name": "Україна"
            },
            "additionalProperty": [
                {
                    "@type": "PropertyValue",
                    "name": "Матеріал",
                    "value": material
                },
                {
                    "@type": "PropertyValue",
                    "name": "Країна виробництва",
                    "value": "Україна"
                },
                {
                    "@type": "PropertyValue",
                    "name": "Стиль",
                    "value": "Стріт & Мілітарі"
                }
            ],
            "brand": {
                "@type": "Brand",
                "name": "TwoComms",
                "url": _build_absolute_url("")
            },
            "manufacturer": {
                "@type": "Organization",
                "name": "TwoComms",
                "url": _build_absolute_url("")
            },
            "offers": {
                "@type": "Offer",
                "price": str(product.final_price),
                "priceCurrency": "UAH",
                "availability": "https://schema.org/InStock",
                "itemCondition": "https://schema.org/NewCondition",
                "url": _build_absolute_url(f"product/{product.slug}/"),
                "priceValidUntil": StructuredDataGenerator._get_dynamic_price_valid_until(),
                "hasMerchantReturnPolicy": {
                    "@type": "MerchantReturnPolicy",
                    "returnPolicyCategory": "https://schema.org/MerchantReturnFiniteReturnWindow",
                    "merchantReturnDays": 14,
                    "returnMethod": "https://schema.org/ReturnByMail",
                    "returnFees": "https://schema.org/ReturnShippingFees",
                    "returnShippingFeesAmount": StructuredDataGenerator._get_return_shipping_amount(),
                    "applicableCountry": "UA"
                },
                "seller": {
                    "@type": "Organization",
                    "name": "TwoComms",
                    "url": _build_absolute_url(""),
                    "address": {
                        "@type": "PostalAddress",
                        "addressCountry": "UA",
                        "addressLocality": "Україна"
                    }
                },
                "shippingDetails": StructuredDataGenerator._get_weight_based_shipping_details()
            },
        }

        # Merchant-level properties (age_group, gender, google_product_category)
        age_group = "adult"
        gender = "unisex"
        if product.category:
            category_name = product.category.name.lower()
            if any(word in category_name for word in ['чоловіч', 'мужск', 'men']):
                gender = "male"
            elif any(word in category_name for word in ['жіноч', 'женск', 'women']):
                gender = "female"

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
            color_names = []
            color_variants = ProductColorVariant.objects.filter(product=product).select_related('color')
            for variant in color_variants:
                if variant.color and variant.color.name:
                    color_names.append(variant.color.name)
            if color_names:
                unique_colors = list(dict.fromkeys(color_names))[:5]
                schema["color"] = ", ".join(unique_colors)
                schema["additionalProperty"].append({
                    "@type": "PropertyValue",
                    "name": "Колір",
                    "value": ", ".join(unique_colors)
                })
            else:
                schema["additionalProperty"].append({
                    "@type": "PropertyValue",
                    "name": "Колір",
                    "value": "Різні кольори"
                })
        except Exception:
            schema["additionalProperty"].append({
                "@type": "PropertyValue",
                "name": "Колір",
                "value": "Різні кольори"
            })

        # Добавляем размеры
        resolved_sizes = resolve_product_sizes(product)
        if resolved_sizes:
            schema["size"] = resolved_sizes if len(resolved_sizes) > 1 else resolved_sizes[0]
            schema["additionalProperty"].append({
                "@type": "PropertyValue",
                "name": "Розміри",
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
        """Генерирует BreadcrumbList schema"""
        schema = {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": []
        }

        for i, breadcrumb in enumerate(breadcrumbs):
            item_url = _build_absolute_url(breadcrumb.get("url", ""))
            schema["itemListElement"].append({
                "@type": "ListItem",
                "@id": item_url,
                "position": i + 1,
                "name": breadcrumb.get("name", ""),
                "item": item_url
            })

        return schema

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


def get_product_schema(product: Product) -> str:
    """Возвращает JSON-LD schema для товара"""
    try:
        schema = StructuredDataGenerator.generate_product_schema(product)
        return json.dumps(schema, ensure_ascii=False, indent=2)
    except Exception as e:
        # Возвращаем пустую строку в случае ошибки
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
