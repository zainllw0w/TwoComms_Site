"""
Шаблонные теги для SEO оптимизации
"""
import json
from django import template
from django.utils.safestring import mark_safe
from django.urls import reverse
from ..seo_utils import (
    get_product_seo_meta, 
    get_category_seo_meta, 
    get_product_schema, 
    get_breadcrumb_schema,
    SEOContentOptimizer
)

register = template.Library()


@register.inclusion_tag('partials/seo_meta.html', takes_context=True)
def seo_meta_tags(context, product=None, category=None):
    """
    Генерирует SEO мета-теги для товара или категории
    """
    meta_data = {}
    
    if product:
        meta_data = get_product_seo_meta(product)
    elif category:
        meta_data = get_category_seo_meta(category)
    else:
        # Базовые мета-теги для главной страницы
        meta_data = {
            'title': 'TwoComms — Стріт & Мілітарі Одяг',
            'description': 'TwoComms - магазин стріт & мілітарі одягу з ексклюзивним дизайном. Футболки, худі, лонгсліви з характером. Якісний одяг для сучасного стилю.',
            'keywords': 'стріт одяг, мілітарі одяг, футболки, худі, лонгсліви, TwoComms, ексклюзивний дизайн, якісний одяг',
            'og_title': 'TwoComms — Стріт & Мілітарі Одяг',
            'og_description': 'TwoComms - магазин стріт & мілітарі одягу з ексклюзивним дизайном. Футболки, худі, лонгсліви з характером.',
            'og_image': '',
            'twitter_title': 'TwoComms — Стріт & Мілітарі Одяг',
            'twitter_description': 'TwoComms - магазин стріт & мілітарі одягу з ексклюзивним дизайном. Футболки, худі, лонгсліви з характером.',
            'twitter_image': ''
        }
    
    return {
        'meta_data': meta_data,
        'request': context['request']
    }


@register.simple_tag
def product_schema(product):
    """
    Возвращает JSON-LD schema для товара
    """
    if not product:
        return ''
    
    schema = get_product_schema(product)
    return mark_safe(f'<script type="application/ld+json">{schema}</script>')


@register.simple_tag
def breadcrumb_schema(breadcrumbs):
    """
    Возвращает JSON-LD schema для хлебных крошек
    """
    if not breadcrumbs:
        return ''
    
    schema = get_breadcrumb_schema(breadcrumbs)
    return mark_safe(f'<script type="application/ld+json">{schema}</script>')


@register.inclusion_tag('partials/breadcrumbs.html')
def breadcrumbs(request, product=None, category=None):
    """
    Генерирует хлебные крошки
    """
    breadcrumb_list = [
        {
            'name': 'Головна',
            'url': reverse('home')
        }
    ]
    
    if category:
        breadcrumb_list.append({
            'name': category.name,
            'url': reverse('catalog_by_cat', kwargs={'cat_slug': category.slug})
        })
    
    if product:
        if product.category:
            breadcrumb_list.append({
                'name': product.category.name,
                'url': reverse('catalog_by_cat', kwargs={'cat_slug': product.category.slug})
            })
        
        breadcrumb_list.append({
            'name': product.title,
            'url': reverse('product', kwargs={'slug': product.slug})
        })
    
    return {
        'breadcrumbs': breadcrumb_list,
        'request': request
    }


@register.simple_tag
def generate_alt_text(image_name, product_title=None):
    """
    Генерирует alt-текст для изображения
    """
    return SEOContentOptimizer.generate_alt_text_for_image(image_name, product_title)


@register.simple_tag
def seo_suggestions(product):
    """
    Возвращает предложения по улучшению SEO для товара
    """
    if not product:
        return []
    
    return SEOContentOptimizer.suggest_content_improvements(product)


@register.filter
def truncate_meta(text, length=160):
    """
    Обрезает текст для мета-описания
    """
    if not text:
        return ''
    
    if len(text) <= length:
        return text
    
    return text[:length-3] + '...'


@register.simple_tag
def canonical_url(request):
    """
    Возвращает канонический URL для текущей страницы
    """
    return f"{request.scheme}://{request.get_host()}{request.path}"


@register.simple_tag
def og_image_url(request, image_url=None):
    """
    Возвращает полный URL для Open Graph изображения
    """
    if not image_url:
        return f"{request.scheme}://{request.get_host()}/static/img/logo.svg"
    
    if image_url.startswith('http'):
        return image_url
    
    return f"{request.scheme}://{request.get_host()}{image_url}"


@register.inclusion_tag('partials/faq_schema.html')
def faq_schema(faq_items):
    """
    Генерирует FAQ schema
    """
    if not faq_items:
        return {}
    
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
    
    return {
        'faq_schema': schema
    }


@register.simple_tag
def local_business_schema():
    """
    Возвращает LocalBusiness schema для организации
    """
    schema = {
        "@context": "https://schema.org",
        "@type": "LocalBusiness",
        "name": "TwoComms",
        "description": "Магазин стріт & мілітарі одягу з ексклюзивним дизайном",
        "url": "https://twocomms.shop",
        "telephone": "+380XXXXXXXXX",
        "address": {
            "@type": "PostalAddress",
            "addressCountry": "UA",
            "addressLocality": "Україна"
        },
        "openingHours": "Mo-Su 00:00-23:59",
        "priceRange": "$$",
        "paymentAccepted": "Cash, Credit Card",
        "currenciesAccepted": "UAH"
    }
    
    return mark_safe(f'<script type="application/ld+json">{json.dumps(schema, ensure_ascii=False, indent=2)}</script>')


@register.simple_tag
def product_rating_schema(product, rating=None, review_count=None):
    """
    Возвращает Product schema с рейтингом
    """
    if not product:
        return ''
    
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
    
    if rating and review_count:
        schema["aggregateRating"] = {
            "@type": "AggregateRating",
            "ratingValue": str(rating),
            "reviewCount": str(review_count)
        }
    
    return mark_safe(f'<script type="application/ld+json">{json.dumps(schema, ensure_ascii=False, indent=2)}</script>')
