"""
SEO утилиты для автоматической генерации мета-тегов и ключевых слов
"""
import re
import json
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
        return list(dict.fromkeys(keywords))[:20]  # Максимум 20 ключевых слов
    
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
        
        return list(dict.fromkeys(keywords))[:15]
    
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
        
        return {
            'title': SEOKeywordGenerator.generate_meta_title(product),
            'description': SEOKeywordGenerator.generate_meta_description(product),
            'keywords': ', '.join(keywords),
            'og_title': SEOKeywordGenerator.generate_meta_title(product),
            'og_description': SEOKeywordGenerator.generate_meta_description(product),
            'og_image': product.display_image.url if product.display_image else '',
            'twitter_title': SEOKeywordGenerator.generate_meta_title(product),
            'twitter_description': SEOKeywordGenerator.generate_meta_description(product),
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
        """Генерирует Product schema для товара"""
        schema = {
            "@context": "https://schema.org",
            "@type": "Product",
            "name": product.title,
            "description": product.description or f"Якісний {product.category.name.lower() if product.category else 'одяг'} з ексклюзивним дизайном",
            "sku": str(product.id),
            "url": f"https://twocomms.shop/product/{product.slug}/",
            "image": product.display_image.url if product.display_image else "",
            "brand": {
                "@type": "Brand",
                "name": "TwoComms"
            },
            "offers": {
                "@type": "Offer",
                "price": str(product.final_price),
                "priceCurrency": "UAH",
                "availability": "https://schema.org/InStock",
                "seller": {
                    "@type": "Organization",
                    "name": "TwoComms"
                }
            }
        }
        
        if product.category:
            schema["category"] = product.category.name
        
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
