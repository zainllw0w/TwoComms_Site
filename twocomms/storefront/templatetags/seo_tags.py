"""
Шаблонные теги для SEO оптимизации
"""
from importlib import import_module
import json
from django.conf import settings
from django import template
from django.utils.safestring import mark_safe
from django.urls import reverse

register = template.Library()


def _seo_utils():
    return import_module("storefront.seo_utils")


def _get_product_seo_meta(product):
    return _seo_utils().get_product_seo_meta(product)


def _get_category_seo_meta(category):
    return _seo_utils().get_category_seo_meta(category)


def _get_product_schema(product):
    return _seo_utils().get_product_schema(product)


def _get_breadcrumb_schema(breadcrumbs):
    return _seo_utils().get_breadcrumb_schema(breadcrumbs)


def _get_google_merchant_schema(product):
    return _seo_utils().get_google_merchant_schema(product)


def _get_default_social_image_url():
    return _seo_utils().get_default_social_image_url()


def _seo_content_optimizer():
    return _seo_utils().SEOContentOptimizer


def _site_base_url():
    return (getattr(settings, "SITE_BASE_URL", "") or "https://twocomms.shop").rstrip("/")


@register.simple_tag(takes_context=True)
def seo_title(context, product=None, category=None):
    """Возвращает SEO заголовок"""
    if product:
        meta_data = _get_product_seo_meta(product)
        return meta_data.get('title', 'TwoComms — Стріт & Мілітарі Одяг')
    elif category:
        meta_data = _get_category_seo_meta(category)
        return meta_data.get('title', 'TwoComms — Стріт & Мілітарі Одяг')
    return 'TwoComms — Стріт & Мілітарі Одяг'


@register.simple_tag(takes_context=True)
def seo_description(context, product=None, category=None):
    """Возвращает SEO описание"""
    if product:
        meta_data = _get_product_seo_meta(product)
        return meta_data.get('description', 'TwoComms - магазин стріт & мілітарі одягу з ексклюзивним дизайном.')
    elif category:
        meta_data = _get_category_seo_meta(category)
        return meta_data.get('description', 'TwoComms - магазин стріт & мілітарі одягу з ексклюзивним дизайном.')
    return 'TwoComms - магазин стріт & мілітарі одягу з ексклюзивним дизайном.'


@register.simple_tag(takes_context=True)
def seo_keywords(context, product=None, category=None):
    """Возвращает SEO ключевые слова"""
    if product:
        meta_data = _get_product_seo_meta(product)
        return meta_data.get('keywords', 'стріт одяг, мілітарі одяг, TwoComms')
    elif category:
        meta_data = _get_category_seo_meta(category)
        return meta_data.get('keywords', 'стріт одяг, мілітарі одяг, TwoComms')
    return 'стріт одяг, мілітарі одяг, TwoComms'


@register.simple_tag(takes_context=True)
def seo_og_image(context, product=None, category=None, selected_variant=None):
    """Returns the Open Graph / Twitter image URL.

    Phase 21 (PR-2 T7.3) — accepts ``selected_variant`` (a
    ``ProductColorVariant``). On a self-canonical colour PDP the OG
    image leads with the variant's first photo so social embeds and
    rich-result previews show the colour the user is actually
    looking at, matching the Product schema's ``image`` array.
    """
    if product:
        # Variant-aware override — only when caller explicitly passed
        # a selected variant (the view computes this from the URL
        # path; ?color= query never forks canonical and never leads
        # the OG image).
        if selected_variant is not None:
            try:
                first_img = selected_variant.images.all().first()
            except Exception:
                first_img = None
            if first_img and getattr(first_img, "image", None):
                try:
                    url = first_img.image.url
                except (ValueError, AttributeError):
                    url = ""
                if url:
                    base = (
                        getattr(settings, "SITE_BASE_URL", "")
                        or "https://twocomms.shop"
                    ).rstrip("/")
                    return url if url.startswith(("http://", "https://")) else f"{base}{url}"
        meta_data = _get_product_seo_meta(product)
        return meta_data.get('og_image', '')
    elif category:
        meta_data = _get_category_seo_meta(category)
        return meta_data.get('og_image', '')
    return ''


@register.inclusion_tag('partials/seo_meta.html', takes_context=True)
def seo_meta_tags(context, product=None, category=None):
    """
    Генерирует SEO мета-теги для товара или категории
    """
    meta_data = {}

    if product:
        meta_data = _get_product_seo_meta(product)
    elif category:
        meta_data = _get_category_seo_meta(category)
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
def product_schema(product, canonical_path=None, selected_variant=None, review_summary=None):
    """
    Возвращает JSON-LD schema для товара.

    Phase 21 (2026-05-10) — accepts ``canonical_path`` (the page's
    actual ``<link rel=canonical>`` target), ``selected_variant``
    (a ``ProductColorVariant`` instance) and ``review_summary``
    (a ``reviews.services.aggregate.ProductReviewSummary``) so the
    schema's ``url``, ``image`` and ``aggregateRating`` mirror what
    the user is looking at. All optional — when omitted the schema
    falls back to base URL, default image set, and no rating block.
    """
    if not product:
        return ''

    schema = _seo_utils().get_product_schema(
        product,
        canonical_path=canonical_path,
        selected_variant=selected_variant,
        review_summary=review_summary,
    )
    return mark_safe(f'<script type="application/ld+json">{schema}</script>')


@register.simple_tag
def google_merchant_schema(product):
    """
    Возвращает JSON-LD schema для Google Merchant Center
    """
    if not product:
        return ''

    schema = _get_google_merchant_schema(product)
    return mark_safe(f'<script type="application/ld+json">{schema}</script>')


@register.simple_tag
def breadcrumb_schema(breadcrumbs):
    """
    Возвращает JSON-LD schema для хлебных крошек
    """
    if not breadcrumbs:
        return ''

    schema = _get_breadcrumb_schema(breadcrumbs)
    return mark_safe(f'<script type="application/ld+json">{schema}</script>')


@register.simple_tag
def product_graph(product, breadcrumbs=None, canonical_path=None,
                  selected_variant=None, review_summary=None):
    """Phase 21 (PR-6 T15.1) — emit Product + BreadcrumbList together
    inside a single ``@graph`` JSON-LD block.

    This is what Google's structured-data guidance recommends for
    pages that carry multiple inter-related entities: Search Console
    parses one script, joins to the global Organization / WebSite
    nodes (still emitted from base.html with stable ``@id`` so the
    @graph references resolve), and reports a single rich-result
    candidate instead of two disjoint schemas.
    """
    if not product:
        return ''

    product_node = _seo_utils().StructuredDataGenerator.generate_product_schema(
        product,
        canonical_path=canonical_path,
        selected_variant=selected_variant,
        review_summary=review_summary,
    )
    # Drop the stand-alone @context — it lives on the wrapper graph.
    product_node.pop("@context", None)

    nodes = [product_node]
    if breadcrumbs:
        breadcrumb_node = (
            _seo_utils().StructuredDataGenerator.generate_breadcrumb_schema(breadcrumbs)
        )
        breadcrumb_node.pop("@context", None)
        nodes.append(breadcrumb_node)

    graph = {
        "@context": "https://schema.org",
        "@graph": nodes,
    }
    return mark_safe(
        f'<script type="application/ld+json">'
        f'{json.dumps(graph, ensure_ascii=False, indent=2)}'
        f'</script>'
    )


@register.inclusion_tag('partials/breadcrumbs.html')
def breadcrumbs(request, product=None, category=None, current_name=None):
    """
    Генерирует хлебные крошки
    """
    breadcrumb_list = [
        {
            'name': 'Головна',
            'url': reverse('home')
        }
    ]

    if current_name and not category and not product:
        breadcrumb_list.append({
            'name': current_name,
            'url': request.path,
        })
        return {
            'breadcrumbs': breadcrumb_list,
            'request': request
        }

    if category or product:
        breadcrumb_list.append({
            'name': 'Каталог',
            'url': reverse('catalog')
        })

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
    return _seo_content_optimizer().generate_alt_text_for_image(image_name, product_title)


@register.simple_tag
def seo_suggestions(product):
    """
    Возвращает предложения по улучшению SEO для товара
    """
    if not product:
        return []

    return _seo_content_optimizer().suggest_content_improvements(product)


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
    return f"{_site_base_url()}{request.path}"


@register.simple_tag
def og_image_url(request, image_url=None):
    """
    Возвращает полный URL для Open Graph изображения
    """
    if not image_url:
        return _get_default_social_image_url()

    if image_url.startswith('http'):
        return image_url

    normalized_path = image_url if image_url.startswith("/") else f"/{image_url}"
    return f"{_site_base_url()}{normalized_path}"


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
        'faq_schema': json.dumps(schema, ensure_ascii=False, indent=2)
    }


@register.simple_tag
def organization_schema():
    """JSON-LD <script> with the canonical Organization schema (Phase 5).

    Single source of truth lives in ``StructuredDataGenerator``. Use this
    tag on every page where you want Knowledge Graph eligibility — the
    stable ``@id`` lets Google deduplicate instances.
    """
    schema = _seo_utils().StructuredDataGenerator.generate_organization_schema()
    return mark_safe(
        f'<script type="application/ld+json">{json.dumps(schema, ensure_ascii=False, indent=2)}</script>'
    )


@register.simple_tag
def website_schema():
    """JSON-LD <script> with the WebSite + SearchAction schema (Phase 5)."""
    schema = _seo_utils().StructuredDataGenerator.generate_website_schema()
    return mark_safe(
        f'<script type="application/ld+json">{json.dumps(schema, ensure_ascii=False, indent=2)}</script>'
    )


@register.simple_tag
def online_store_schema():
    """OnlineStore JSON-LD with verified phone and Ukraine-wide service area.

    Phase 21 (2026-05-10) — replaces the previous ``local_business_schema``
    helper. TwoComms has no physical retail address and no fixed business
    hours, so emitting ``LocalBusiness`` with placeholder data was a
    misleading-claims risk. ``OnlineStore`` accurately models the entity
    (subtype of ``Store`` / ``Organization``), references the canonical
    Organization ``@id`` for graph deduplication, and uses the verified
    business phone ``+380966543212``.
    """
    base_url = "https://twocomms.shop"
    schema = {
        "@context": "https://schema.org",
        "@type": "OnlineStore",
        "@id": f"{base_url}/#online-store",
        "name": "TwoComms",
        "url": base_url,
        "description": (
            "Український онлайн-магазин стріт- та мілітарі-одягу TwoComms: "
            "футболки, худі, лонгсліви та кастомний DTF-друк."
        ),
        "telephone": "+380966543212",
        "currenciesAccepted": "UAH",
        "paymentAccepted": "Cash, Credit Card, Apple Pay, Google Pay",
        "areaServed": {
            "@type": "Country",
            "name": "Ukraine",
        },
        "parentOrganization": {"@id": f"{base_url}/#organization"},
        "contactPoint": {
            "@type": "ContactPoint",
            "telephone": "+380966543212",
            "contactType": "customer support",
            "availableLanguage": ["uk", "ru"],
            "areaServed": "UA",
        },
    }
    return mark_safe(
        f'<script type="application/ld+json">{json.dumps(schema, ensure_ascii=False, indent=2)}</script>'
    )


# Backwards-compat alias — old templates may still import the original
# name. Routes safely to the new helper so a stale include never falls
# back to placeholder ``LocalBusiness`` data.
@register.simple_tag
def local_business_schema():  # pragma: no cover - alias
    return online_store_schema()


@register.simple_tag
def product_rating_schema(product, rating=None, review_count=None):
    """Render Product JSON-LD with optional ``aggregateRating``.

    Phase 21 (2026-05-10) — hardened. Only emits ``aggregateRating``
    when *both* a numeric rating and ``review_count >= 3`` are supplied.
    Defaults to ``None`` so callers must explicitly pass real,
    moderation-approved review aggregates from the upcoming reviews app
    (PR-4). This prevents accidental fake ratings from surfacing.
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

    try:
        review_count_int = int(review_count) if review_count is not None else 0
    except (TypeError, ValueError):
        review_count_int = 0
    if rating and review_count_int >= 3:
        schema["aggregateRating"] = {
            "@type": "AggregateRating",
            "ratingValue": str(rating),
            "reviewCount": str(review_count_int),
            "bestRating": "5",
            "worstRating": "1",
        }

    return mark_safe(f'<script type="application/ld+json">{json.dumps(schema, ensure_ascii=False, indent=2)}</script>')
