"""
SEO оптимизированные alt-теги для TwoComms
"""

from django import template
from django.utils.safestring import mark_safe
from django.utils.text import slugify
import re

register = template.Library()


class SEOAltTextGenerator:
    """Генератор SEO-оптимизированных alt-текстов"""
    
    # SEO ключевые слова
    SEO_KEYWORDS = {
        'product_types': {
            'футболка': ['футболка', 'базова футболка', 'принтована футболка', 'чоловіча футболка', 'жіноча футболка'],
            'худі': ['худі', 'базове худі', 'принтоване худі', 'чоловіче худі', 'жіноче худі'],
            'лонгслів': ['лонгслів', 'базовий лонгслів', 'принтований лонгслів', 'чоловічий лонгслів', 'жіночий лонгслів'],
            'світшот': ['світшот', 'толстовка', 'базовий світшот', 'принтований світшот']
        },
        'colors': {
            'чорний': ['чорна', 'чорне', 'чорний'],
            'білий': ['біла', 'біле', 'білий'],
            'сірий': ['сіра', 'сіре', 'сірий'],
            'зелений': ['зелена', 'зелене', 'зелений'],
            'синій': ['синя', 'синє', 'синій'],
            'червоний': ['червона', 'червоне', 'червоний'],
            'коричневий': ['коричнева', 'коричневе', 'коричневий'],
            'бежевий': ['бежева', 'бежеве', 'бежевий']
        },
        'styles': [
            'стріт стиль', 'мілітарі стиль', 'ексклюзивний дизайн',
            'модний одяг', 'трендовий одяг', 'якісний одяг',
            'одяг з характером', 'український бренд'
        ]
    }
    
    @classmethod
    def generate_product_alt_text(cls, product, image_type='main', color_name=None, photo_number=None):
        """Генерирует alt-текст для товара"""
        
        # Базовые компоненты
        product_title = product.title if hasattr(product, 'title') else str(product)
        category_name = product.category.name if hasattr(product, 'category') and product.category else ''
        
        # Определяем тип товара
        product_type = cls._detect_product_type(product_title, category_name)
        
        # Определяем цвет
        color = cls._detect_color(product_title, color_name)
        
        # Генерируем alt-текст в зависимости от типа изображения
        if image_type == 'main':
            alt_text = f"{product_title} - {color} {product_type} TwoComms"
        elif image_type == 'gallery':
            photo_num = f" {photo_number}" if photo_number else ""
            alt_text = f"{product_title} - {color} {product_type} - фото{photo_num} TwoComms"
        elif image_type == 'thumbnail':
            alt_text = f"{product_title} - {color} {product_type} - мініатюра TwoComms"
        else:
            alt_text = f"{product_title} - {color} {product_type} TwoComms"
        
        # Ограничиваем длину
        return cls._limit_length(alt_text, 125)
    
    @classmethod
    def generate_category_alt_text(cls, category, image_type='icon'):
        """Генерирует alt-текст для категории"""
        category_name = category.name if hasattr(category, 'name') else str(category)
        
        if image_type == 'icon':
            alt_text = f"{category_name} іконка - TwoComms"
        elif image_type == 'cover':
            alt_text = f"{category_name} категорія - TwoComms магазин"
        else:
            alt_text = f"{category_name} - TwoComms"
        
        return cls._limit_length(alt_text, 125)
    
    @classmethod
    def generate_logo_alt_text(cls, logo_type='main'):
        """Генерирует alt-текст для логотипа"""
        if logo_type == 'main':
            return "TwoComms логотип - стріт & мілітарі одяг"
        elif logo_type == 'small':
            return "TwoComms логотип"
        elif logo_type == 'floating':
            return "TwoComms логотип - декоративний"
        else:
            return "TwoComms логотип - стріт & мілітарі одяг"
    
    @classmethod
    def generate_avatar_alt_text(cls, username=None):
        """Генерирует alt-текст для аватара"""
        if username:
            return f"Аватар користувача {username} - TwoComms"
        else:
            return "Аватар користувача - TwoComms"
    
    @classmethod
    def generate_social_alt_text(cls, social_network):
        """Генерирует alt-текст для социальной сети"""
        return f"Вхід через {social_network} - TwoComms"
    
    @classmethod
    def _detect_product_type(cls, title, category):
        """Определяет тип товара"""
        title_lower = title.lower()
        category_lower = category.lower() if category else ''
        
        # Проверяем в названии товара
        for product_type, keywords in cls.SEO_KEYWORDS['product_types'].items():
            for keyword in keywords:
                if keyword in title_lower:
                    return product_type
        
        # Проверяем в категории
        for product_type, keywords in cls.SEO_KEYWORDS['product_types'].items():
            for keyword in keywords:
                if keyword in category_lower:
                    return product_type
        
        # По умолчанию
        return 'одяг'
    
    @classmethod
    def _detect_color(cls, title, color_name=None):
        """Определяет цвет товара"""
        if color_name:
            color_lower = color_name.lower()
            for color, variations in cls.SEO_KEYWORDS['colors'].items():
                if any(var in color_lower for var in variations):
                    return variations[0]  # Возвращаем первую вариацию
        
        # Ищем цвет в названии
        title_lower = title.lower()
        for color, variations in cls.SEO_KEYWORDS['colors'].items():
            for variation in variations:
                if variation in title_lower:
                    return variation
        
        # По умолчанию
        return 'різнокольоровий'
    
    @classmethod
    def _limit_length(cls, text, max_length):
        """Ограничивает длину текста"""
        if len(text) <= max_length:
            return text
        
        # Обрезаем до последнего пробела
        truncated = text[:max_length-3]
        last_space = truncated.rfind(' ')
        if last_space > max_length * 0.8:  # Если пробел не слишком далеко
            return truncated[:last_space] + '...'
        
        return truncated + '...'


@register.simple_tag
def seo_alt_product(product, image_type='main', color_name=None, photo_number=None):
    """Генерирует SEO alt-текст для товара"""
    return SEOAltTextGenerator.generate_product_alt_text(product, image_type, color_name, photo_number)


@register.simple_tag
def seo_alt_category(category, image_type='icon'):
    """Генерирует SEO alt-текст для категории"""
    return SEOAltTextGenerator.generate_category_alt_text(category, image_type)


@register.simple_tag
def seo_alt_logo(logo_type='main'):
    """Генерирует SEO alt-текст для логотипа"""
    return SEOAltTextGenerator.generate_logo_alt_text(logo_type)


@register.simple_tag
def seo_alt_avatar(username=None):
    """Генерирует SEO alt-текст для аватара"""
    return SEOAltTextGenerator.generate_avatar_alt_text(username)


@register.simple_tag
def seo_alt_social(social_network):
    """Генерирует SEO alt-текст для социальной сети"""
    return SEOAltTextGenerator.generate_social_alt_text(social_network)


@register.simple_tag
def seo_alt_smart(image_context, **kwargs):
    """Умный генератор alt-текстов на основе контекста"""
    
    # Определяем тип изображения по контексту
    if 'product' in kwargs:
        product = kwargs['product']
        image_type = kwargs.get('image_type', 'main')
        color_name = kwargs.get('color_name')
        photo_number = kwargs.get('photo_number')
        return SEOAltTextGenerator.generate_product_alt_text(product, image_type, color_name, photo_number)
    
    elif 'category' in kwargs:
        category = kwargs['category']
        image_type = kwargs.get('image_type', 'icon')
        return SEOAltTextGenerator.generate_category_alt_text(category, image_type)
    
    elif image_context == 'logo':
        logo_type = kwargs.get('logo_type', 'main')
        return SEOAltTextGenerator.generate_logo_alt_text(logo_type)
    
    elif image_context == 'avatar':
        username = kwargs.get('username')
        return SEOAltTextGenerator.generate_avatar_alt_text(username)
    
    elif image_context == 'social':
        social_network = kwargs.get('social_network', 'соціальна мережа')
        return SEOAltTextGenerator.generate_social_alt_text(social_network)
    
    else:
        # Fallback для неизвестных типов
        return kwargs.get('fallback', 'Зображення TwoComms')


@register.filter
def seo_alt_optimize(alt_text):
    """Оптимизирует существующий alt-текст"""
    if not alt_text:
        return "Зображення TwoComms"
    
    # Проверяем, нужно ли улучшать
    alt_lower = alt_text.lower()
    
    # Проблемные тексты
    problematic = ['logo', 'зображення', 'фото', 'картинка', 'аватар', 'плейсхолдер']
    if any(prob in alt_lower for prob in problematic):
        # Пытаемся улучшить
        if 'logo' in alt_lower:
            return SEOAltTextGenerator.generate_logo_alt_text()
        elif 'аватар' in alt_lower:
            return SEOAltTextGenerator.generate_avatar_alt_text()
        else:
            return f"{alt_text} - TwoComms"
    
    # Если уже хороший, просто возвращаем
    return alt_text


@register.inclusion_tag('partials/seo_optimized_image.html')
def seo_optimized_image(image_url, image_context='general', **kwargs):
    """Создает оптимизированное изображение с SEO alt-текстом"""
    
    # Генерируем alt-текст
    alt_text = seo_alt_smart(image_context, **kwargs)
    
    # Дополнительные атрибуты для SEO
    attributes = {
        'src': image_url,
        'alt': alt_text,
        'loading': kwargs.get('loading', 'lazy'),
        'decoding': kwargs.get('decoding', 'async'),
    }
    
    # Добавляем размеры если есть
    if 'width' in kwargs:
        attributes['width'] = kwargs['width']
    if 'height' in kwargs:
        attributes['height'] = kwargs['height']
    
    # Добавляем CSS класс
    if 'class' in kwargs:
        attributes['class'] = kwargs['class']
    
    return {
        'attributes': attributes,
        'alt_text': alt_text
    }
