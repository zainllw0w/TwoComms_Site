"""
SEO утилиты для автоматической генерации мета-тегов и ключевых слов
"""
import re
import json
import os
from typing import List, Dict, Optional, Tuple
from django.conf import settings
from django.utils.text import slugify
from django.template.loader import render_to_string
from .models import Product, Category


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
            color_variants = ProductColorVariant.objects.filter(product=product)
            for variant in color_variants:
                if variant.color and variant.color.name:
                    color_name = variant.color.name.lower()
                    if color_name in cls.COLOR_KEYWORDS:
                        keywords.extend(cls.COLOR_KEYWORDS[color_name])
        except ImportError:
            pass
        
        # Убираем дубликаты и возвращаем уникальный список
        # При включенной AI-подстановке расширяем словарь ключевых слов
        try:
            use_ai = getattr(settings, 'USE_AI_KEYWORDS', False)
            if isinstance(use_ai, str):
                use_ai = use_ai.lower() in ('1', 'true', 'yes')
        except Exception:
            use_ai = False
        if use_ai:
            ai_keywords = cls.generate_product_keywords_ai(product)
            for kw in ai_keywords:
                if kw and kw not in keywords:
                    keywords.append(kw)
        return list(dict.fromkeys(keywords))[:20]  # Максимум 20 ключевых слов

    @classmethod
    def generate_product_keywords_ai(cls, product: Product) -> List[str]:
        """Генерирует ключевые слова для товара с помощью OpenAI (если доступно)"""
        model = getattr(settings, 'OPENAI_MODEL', 'gpt-5')
        api_key = getattr(settings, 'OPENAI_API_KEY', None) or os.environ.get('OPENAI_API_KEY')
        if not api_key:
            return []
        try:
            import openai
            openai.api_key = api_key
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
            response = openai.ChatCompletion.create(
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
        
        # If AI keywords for category are enabled, extend with AI-generated keywords
        try:
            from django.conf import settings
            if getattr(settings, 'USE_AI_KEYWORDS', False):
                ai_keywords = cls.generate_category_keywords_ai(category)
                for kw in ai_keywords:
                    if kw and kw not in keywords:
                        keywords.append(kw)
        except Exception:
            pass
        return list(dict.fromkeys(keywords))[:15]

    @classmethod
    def generate_category_keywords_ai(cls, category: Category) -> List[str]:
        """Генерирует ключевые слова для категории с помощью OpenAI (если доступно)"""
        model = getattr(settings, 'OPENAI_MODEL', 'gpt-5')
        api_key = getattr(settings, 'OPENAI_API_KEY', None) or os.environ.get('OPENAI_API_KEY')
        if not api_key:
            return []
        try:
            import openai
            openai.api_key = api_key
        except Exception:
            return []
        prompt = (
            f"Створіть до 20 SEO ключових слів для категорії '{category.name}'. "
            f"Опис: {category.description or ''}."
        )
        try:
            resp = openai.ChatCompletion.create(
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
        base_desc = f"Купити {product.title} в TwoComms. "
        
        if product.description:
            # Берем первые 120 символов описания
            clean_desc = re.sub(r'<[^>]+>', '', product.description)
            if len(clean_desc) > 120:
                clean_desc = clean_desc[:117] + "..."
            base_desc += clean_desc
        else:
            base_desc += f"Якісний {product.category.name.lower() if product.category else 'одяг'} з ексклюзивним дизайном."
        
        base_desc += f" Ціна: {product.final_price} грн. Швидка доставка по Україні."
        
        return base_desc[:160]  # Максимум 160 символов
    
    @classmethod
    def generate_meta_title(cls, product: Product) -> str:
        """Генерирует мета-заголовок для товара"""
        title = f"{product.title} - TwoComms"
        
        if product.category:
            title = f"{product.title} ({product.category.name}) - TwoComms"
        
        return title[:60]  # Максимум 60 символов


class SEOMetaGenerator:
    """Генератор SEO мета-тегов"""
    
    @staticmethod
    def generate_product_meta(product: Product) -> Dict[str, str]:
        """Генерирует все мета-теги для товара"""
        keywords = SEOKeywordGenerator.generate_product_keywords(product)
        description = SEOKeywordGenerator.generate_meta_description(product)
        # Пробуем заменить описание AI-генерируемым текстом, если опция включена
        try:
            from django.conf import settings
            if getattr(settings, 'USE_AI_DESCRIPTIONS', False):
                ai_desc = SEOContentOptimizer.generate_ai_product_description(product)
                if ai_desc:
                    description = ai_desc[:160]
        except Exception:
            pass
        
        return {
            'title': SEOKeywordGenerator.generate_meta_title(product),
            'description': description,
            'keywords': ', '.join(keywords),
            'og_title': SEOKeywordGenerator.generate_meta_title(product),
            'og_description': description,
            'og_image': product.display_image.url if product.display_image else '',
            'twitter_title': SEOKeywordGenerator.generate_meta_title(product),
            'twitter_description': description,
            'twitter_image': product.display_image.url if product.display_image else '',
        }
    
    @staticmethod
    def generate_category_meta(category: Category) -> Dict[str, str]:
        """Генерирует мета-теги для категории"""
        keywords = SEOKeywordGenerator.generate_category_keywords(category)
        
        title = f"{category.name} - TwoComms"
        description = f"Купити {category.name.lower()} в TwoComms. Якісний одяг з ексклюзивним дизайном. Швидка доставка по Україні."
        
        if category.description:
            clean_desc = re.sub(r'<[^>]+>', '', category.description)
            if len(clean_desc) > 120:
                clean_desc = clean_desc[:117] + "..."
            description = clean_desc
        
        return {
            'title': title,
            'description': description,
            'keywords': ', '.join(keywords),
            'og_title': title,
            'og_description': description,
            'og_image': category.cover.url if category.cover else '',
            'twitter_title': title,
            'twitter_description': description,
            'twitter_image': category.cover.url if category.cover else '',
        }


class StructuredDataGenerator:
    """Генератор структурированных данных (Schema.org)"""
    
    @staticmethod
    def generate_product_schema(product: Product) -> Dict:
        """Генерирует Product schema для товара (совместимо с Google Merchant Center)"""
        # Базовые изображения
        images = []
        if product.display_image:
            images.append(f"https://twocomms.shop{product.display_image.url}")
        
        # Добавляем дополнительные изображения
        try:
            for img in product.images.all()[:4]:  # Максимум 4 дополнительных изображения
                images.append(f"https://twocomms.shop{img.image.url}")
        except:
            pass
        
        # Добавляем изображения из цветовых вариантов
        try:
            from productcolors.models import ProductColorVariant
            color_variants = ProductColorVariant.objects.filter(product=product)
            for variant in color_variants[:2]:  # Максимум 2 цветовых варианта
                for img in variant.images.all()[:2]:
                    if f"https://twocomms.shop{img.image.url}" not in images:
                        images.append(f"https://twocomms.shop{img.image.url}")
        except:
            pass
        
        schema = {
            "@context": "https://schema.org",
            "@type": "Product",
            "name": product.title,
            "description": product.description or f"Якісний {product.category.name.lower() if product.category else 'одяг'} з ексклюзивним дизайном від TwoComms",
            "sku": f"TC-{product.id}",
            "mpn": f"TC-{product.id}",  # Manufacturer Part Number
            "gtin": f"TC{product.id:08d}",  # Global Trade Item Number
            "url": f"https://twocomms.shop/product/{product.slug}/",
            "image": images[0] if images else "https://twocomms.shop/static/img/placeholder.jpg",
            "additionalProperty": [
                {
                    "@type": "PropertyValue",
                    "name": "Матеріал",
                    "value": "100% бавовна"
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
                "url": "https://twocomms.shop"
            },
            "manufacturer": {
                "@type": "Organization",
                "name": "TwoComms",
                "url": "https://twocomms.shop"
            },
            "offers": {
                "@type": "Offer",
                "price": str(product.final_price),
                "priceCurrency": "UAH",
                "availability": "https://schema.org/InStock",
                "itemCondition": "https://schema.org/NewCondition",
                "url": f"https://twocomms.shop/product/{product.slug}/",
                "priceValidUntil": "2025-12-31",
                "seller": {
                    "@type": "Organization",
                    "name": "TwoComms",
                    "url": "https://twocomms.shop",
                    "address": {
                        "@type": "PostalAddress",
                        "addressCountry": "UA",
                        "addressLocality": "Україна"
                    }
                },
                "shippingDetails": {
                    "@type": "OfferShippingDetails",
                    "shippingRate": {
                        "@type": "MonetaryAmount",
                        "value": "0",
                        "currency": "UAH"
                    },
                    "deliveryTime": {
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
                }
            },
            "aggregateRating": {
                "@type": "AggregateRating",
                "ratingValue": "4.8",
                "reviewCount": "127",
                "bestRating": "5",
                "worstRating": "1"
            }
        }
        
        # Добавляем категорию
        if product.category:
            schema["category"] = product.category.name
            schema["additionalProperty"].append({
                "@type": "PropertyValue",
                "name": "Категорія",
                "value": product.category.name
            })
        
        # Добавляем все изображения
        if len(images) > 1:
            schema["image"] = images
        
        # Добавляем размеры
        schema["additionalProperty"].extend([
            {
                "@type": "PropertyValue",
                "name": "Розміри",
                "value": "S, M, L, XL, XXL"
            },
            {
                "@type": "PropertyValue",
                "name": "Колір",
                "value": "Різні кольори"
            }
        ])
        
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
            schema["offers"]["priceValidUntil"] = "2025-12-31"
        
        return schema
    
    @staticmethod
    def generate_google_merchant_schema(product: Product) -> Dict:
        """Генерирует схему специально для Google Merchant Center"""
        # Получаем все изображения товара
        images = []
        if product.display_image:
            images.append(f"https://twocomms.shop{product.display_image.url}")
        
        # Дополнительные изображения
        try:
            for img in product.images.all()[:10]:  # До 10 изображений для Google
                images.append(f"https://twocomms.shop{img.image.url}")
        except:
            pass
        
        # Изображения цветовых вариантов
        try:
            from productcolors.models import ProductColorVariant
            color_variants = ProductColorVariant.objects.filter(product=product)
            for variant in color_variants:
                for img in variant.images.all():
                    img_url = f"https://twocomms.shop{img.image.url}"
                    if img_url not in images:
                        images.append(img_url)
        except:
            pass
        
        # Определяем возрастную группу и пол
        age_group = "adult"
        gender = "unisex"
        
        if product.category:
            category_name = product.category.name.lower()
            if any(word in category_name for word in ['чоловіч', 'мужск', 'men']):
                gender = "male"
            elif any(word in category_name for word in ['жіноч', 'женск', 'women']):
                gender = "female"
        
        schema = {
            "@context": "https://schema.org",
            "@type": "Product",
            "name": product.title,
            "description": product.description or f"Якісний {product.category.name.lower() if product.category else 'одяг'} з ексклюзивним дизайном від TwoComms. Стріт & мілітарі стиль.",
            "sku": f"TC-{product.id}",
            "mpn": f"TC-{product.id}",
            "gtin": f"TC{product.id:08d}",
            "url": f"https://twocomms.shop/product/{product.slug}/",
            "image": images,
            "brand": {
                "@type": "Brand",
                "name": "TwoComms"
            },
            "manufacturer": {
                "@type": "Organization", 
                "name": "TwoComms"
            },
            "offers": {
                "@type": "Offer",
                "price": str(product.final_price),
                "priceCurrency": "UAH",
                "availability": "https://schema.org/InStock",
                "itemCondition": "https://schema.org/NewCondition",
                "url": f"https://twocomms.shop/product/{product.slug}/",
                "priceValidUntil": "2025-12-31",
                "seller": {
                    "@type": "Organization",
                    "name": "TwoComms",
                    "url": "https://twocomms.shop"
                }
            },
            # Специальные поля для Google Merchant Center
            "additionalProperty": [
                {
                    "@type": "PropertyValue",
                    "name": "age_group",
                    "value": age_group
                },
                {
                    "@type": "PropertyValue",
                    "name": "gender", 
                    "value": gender
                },
                {
                    "@type": "PropertyValue",
                    "name": "material",
                    "value": "100% cotton"
                },
                {
                    "@type": "PropertyValue",
                    "name": "size_type",
                    "value": "regular"
                },
                {
                    "@type": "PropertyValue",
                    "name": "size_system",
                    "value": "UA"
                },
                {
                    "@type": "PropertyValue",
                    "name": "condition",
                    "value": "new"
                },
                {
                    "@type": "PropertyValue",
                    "name": "availability",
                    "value": "in stock"
                }
            ]
        }
        
        # Добавляем категорию
        if product.category:
            schema["category"] = product.category.name
            schema["additionalProperty"].append({
                "@type": "PropertyValue",
                "name": "google_product_category",
                "value": "1604"  # Apparel & Accessories > Clothing
            })
        
        # Добавляем размеры
        schema["additionalProperty"].append({
            "@type": "PropertyValue",
            "name": "size",
            "value": "S,M,L,XL,XXL"
        })
        
        # Добавляем цвета если есть
        try:
            from productcolors.models import ProductColorVariant
            colors = []
            color_variants = ProductColorVariant.objects.filter(product=product)
            for variant in color_variants:
                if variant.color and variant.color.name:
                    colors.append(variant.color.name)
            
            if colors:
                schema["additionalProperty"].append({
                    "@type": "PropertyValue",
                    "name": "color",
                    "value": ",".join(colors[:3])  # Максимум 3 цвета
                })
        except:
            pass
        
        return schema
    
    @staticmethod
    def generate_breadcrumb_schema(breadcrumbs: List[Dict]) -> Dict:
        """Генерирует BreadcrumbList schema"""
        schema = {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": []
        }
        
        for i, breadcrumb in enumerate(breadcrumbs):
            schema["itemListElement"].append({
                "@type": "ListItem",
                "position": i + 1,
                "name": breadcrumb["name"],
                "item": breadcrumb["url"]
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
            openai.api_key = api_key
            model = getattr(settings, 'OPENAI_MODEL', 'gpt-5')
            prompt = (
                f"Напишіть стислий SEO-дружній опис категорії '{category.name}'. "
            )
            if category.description:
                prompt += f" Опис: {category.description}."
            resp = openai.ChatCompletion.create(
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
                use_descriptions = use_descriptions.lower() in ('1','true','yes')
            if not use_descriptions:
                return ''
            api_key = getattr(settings, 'OPENAI_API_KEY', None) or os.environ.get('OPENAI_API_KEY')
            if not api_key:
                return ''
            import openai
            openai.api_key = api_key
            model = getattr(settings, 'OPENAI_MODEL', 'gpt-5')
            prompt = (
                f"Напишіть стислий SEO-дружній опис товару '{product.title}'. "
                f"Категорія: {product.category.name if product.category else 'N/A'}. "
                f"Ціна: {product.final_price}." 
            )
            resp = openai.ChatCompletion.create(
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
    return SEOMetaGenerator.generate_product_meta(product)

def get_category_seo_meta(category: Category) -> Dict[str, str]:
    """Возвращает SEO мета-теги для категории"""
    return SEOMetaGenerator.generate_category_meta(category)

def get_product_schema(product: Product) -> str:
    """Возвращает JSON-LD schema для товара"""
    schema = StructuredDataGenerator.generate_product_schema(product)
    return json.dumps(schema, ensure_ascii=False, indent=2)

def get_breadcrumb_schema(breadcrumbs: List[Dict]) -> str:
    """Возвращает JSON-LD schema для хлебных крошек"""
    schema = StructuredDataGenerator.generate_breadcrumb_schema(breadcrumbs)
    return json.dumps(schema, ensure_ascii=False, indent=2)

def get_google_merchant_schema(product: Product) -> str:
    """Возвращает JSON-LD schema для Google Merchant Center"""
    schema = StructuredDataGenerator.generate_google_merchant_schema(product)
    return json.dumps(schema, ensure_ascii=False, indent=2)
