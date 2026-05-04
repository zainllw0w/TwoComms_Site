"""
Static Pages views - Статические страницы и служебные файлы.

Содержит views для:
- robots.txt
- sitemap.xml
- Google Merchant Feed
- Prom.ua Feed  
- Статические файлы верификации
- О компании, Контакты, и т.д.
- Тестовая страница для аналитики
"""

from copy import deepcopy
import json
import logging
from decimal import Decimal, InvalidOperation
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

from django.core.paginator import EmptyPage, PageNotAnInteger
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.conf import settings
from django.shortcuts import render
from django.db import transaction
from django.template.response import TemplateResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.urls import reverse
from storefront.models import Category, CustomPrintLead, CustomPrintModerationStatus, Product, SizeGrid
from storefront.forms import CustomPrintLeadForm
from storefront.custom_print_config import (
    ADDON_LABELS,
    PRODUCT_LABELS,
    SESSION_CUSTOM_CART_KEY,
    TELEGRAM_MANAGER_URL,
    ZONE_LABELS,
    build_custom_print_config,
    build_placement_specs,
    compute_cart_label,
    normalize_custom_print_snapshot,
)
from storefront.custom_print_notifications import (
    notify_custom_print_moderation_request,
    notify_custom_print_safe_exit,
    notify_new_custom_print_lead,
)
from storefront.utm_tracking import record_custom_print_event
from storefront.services.catalog_helpers import apply_public_product_order
from storefront.services.marketplace_feeds import (
    build_buyme_feed_xml,
    build_google_merchant_feed_xml,
    build_kasta_feed_xml,
    build_prom_feed_xml,
    build_rozetka_feed_xml,
    build_uaprom_products_feed_xml,
)
from storefront.services.size_guides import build_public_size_guide_blocks
from storefront.support_content import (
    FOOTER_CONTENT,
    PRO_BRAND_FAQ_ITEMS,
    SUPPORT_PAGE_DEFINITIONS,
)

SITEMAP_STATIC_ROUTE_NAMES = (
    "home",
    "catalog",
    "delivery",
    "about",
    "contacts",
    "cooperation",
    "custom_print",
    "wholesale_page",
    "help_center",
    "faq",
    "size_guide",
    "care_guide",
    "order_tracking",
    "site_map_page",
    "news",
    "returns",
    "privacy_policy",
    "terms_of_service",
)

ROBOTS_INTERNAL_DISALLOW_PATHS = (
    "/admin/",
    "/admin-panel/",
    "/accounts/",
    "/orders/",
    "/cart/",
    "/checkout/",
    "/api/",
    "/debug/",
    "/dev/",
)

SEARCH_ROBOTS_USER_AGENTS = (
    "Googlebot",
    "Googlebot-Image",
    "Googlebot-Video",
    "Googlebot-News",
    "Google-InspectionTool",
    "GoogleOther",
    "GoogleOther-Image",
    "GoogleOther-Video",
    "AdsBot-Google",
    "AdsBot-Google-Mobile",
    "AdsBot-Google-Mobile-Apps",
    "Storebot-Google",
    "Google-CloudVertexBot",
    "bingbot",
    "BingPreview",
    "Applebot",
    "DuckDuckBot",
    "YandexBot",
    "Slurp",
)

AI_ROBOTS_USER_AGENTS = (
    "OAI-SearchBot",
    "ChatGPT-User",
    "Claude-SearchBot",
    "Claude-User",
    "PerplexityBot",
    "Perplexity-User",
    "Google-Extended",
    "GPTBot",
    "CCBot",
    "ClaudeBot",
    "anthropic-ai",
)


def _site_base_url():
    return (getattr(settings, "SITE_BASE_URL", "") or "https://twocomms.shop").rstrip("/")


def _absolute_site_url(path):
    normalized_path = path if path.startswith("/") else f"/{path}"
    return f"{_site_base_url()}{normalized_path}"


def _feed_base_url():
    return (getattr(settings, "FEED_BASE_URL", "").strip() or _site_base_url()).rstrip("/")


CUSTOM_PRINT_FAQ_ITEMS = [
    {
        "question": "Чи можна замовити один кастомний виріб для себе?",
        "answer": "Так. У конфігураторі можна зібрати один худі, футболку або лонгслів для себе, додати принт, контакт і передати заявку менеджеру або в кошик.",
    },
    {
        "question": "Що робити, якщо у мене немає готового файлу для друку?",
        "answer": "Можна завантажити готовий макет або просто описати ідею в брифі. Менеджер підкаже, як підготувати файл, або допоможе допрацювати дизайн під друк.",
    },
    {
        "question": "Чи можна друкувати на своєму одязі?",
        "answer": "Так. Конфігуратор підтримує сценарій зі своїм виробом: додайте опис речі, матеріал, колір і важливі деталі, щоб менеджер міг коректно порахувати замовлення.",
    },
    {
        "question": "Чи можна повернути або обміняти кастомний виріб?",
        "answer": "Кастомний одяг, виготовлений за індивідуальним замовленням, не підлягає поверненню чи обміну, якщо його виконано належним чином і він відповідає погодженим параметрам. Якщо є виробничий брак або відхилення від погодженого макета, зверніться до нас через контакти й ми розглянемо ситуацію окремо.",
    },
    {
        "question": "Як оформити партію для бренду, команди або події?",
        "answer": "Оберіть формат для команди або бренду, вкажіть кількість, розміри та контакт. Після цього ми допоможемо узгодити тираж, принт, дедлайни й умови для партії.",
    },
]

# ==================== STATIC PAGES ====================

def robots_txt(request):
    """
    Генерирует robots.txt файл.

    Returns:
        HttpResponse: текстовый файл robots.txt
    """
    def append_public_rules(payload):
        payload.append("Allow: /")
        for path in ROBOTS_INTERNAL_DISALLOW_PATHS:
            payload.append(f"Disallow: {path}")

    lines = [
        "User-agent: *",
    ]
    append_public_rules(lines)
    lines.extend(
        [
            "",
            "# Explicitly allow major search, ads and commerce crawlers",
        ]
    )

    for user_agent in SEARCH_ROBOTS_USER_AGENTS:
        lines.append(f"User-agent: {user_agent}")
        append_public_rules(lines)
        lines.append("")

    lines.extend(
        [
            "# Explicitly allow AI search, citation and model discovery bots",
        ]
    )

    for user_agent in AI_ROBOTS_USER_AGENTS:
        lines.append(f"User-agent: {user_agent}")
        append_public_rules(lines)
        lines.append("")

    lines.append(f"Sitemap: {_absolute_site_url('/sitemap.xml')}")

    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain; charset=utf-8")


def llms_txt(request):
    """
    Machine-readable orientation file for LLM agents and answer engines.

    This is not a ranking guarantee, but it gives AI retrieval systems a compact
    canonical map of the public brand surface and preferred landing pages.
    """
    primary_routes = [
        ("Home", reverse("home"), "Brand entry point and newest public storefront modules."),
        ("Catalog", reverse("catalog"), "Ready-made apparel catalog for public shopping intent."),
        ("Custom print", reverse("custom_print"), "Custom apparel, one-off print and team order intake."),
        ("Wholesale", reverse("wholesale_page"), "B2B, team, brand and bulk order landing page."),
        ("Cooperation", reverse("cooperation"), "Partner, dropshipping, wholesale and collaboration overview."),
        ("About brand", reverse("about"), "Canonical brand story, positioning and trust page."),
    ]
    support_routes = [
        ("Delivery and payment", reverse("delivery"), "Shipping, payment and checkout policy details."),
        ("Contacts", reverse("contacts"), "Official contact points and business communication options."),
        ("FAQ", reverse("faq"), "Frequently asked questions for buyers and partners."),
        ("Size guide", reverse("size_guide"), "Sizing guidance for apparel selection."),
        ("Care guide", reverse("care_guide"), "Garment care guidance for public customers."),
        ("Order tracking", reverse("order_tracking"), "Public order-status guidance without exposing private order data."),
        ("Human sitemap", reverse("site_map_page"), "Readable navigation map for public site sections."),
    ]

    lines = [
        "# TwoComms",
        "",
        "> Ukrainian apparel brand and custom-print studio on the canonical public domain https://twocomms.shop.",
        "",
        "## Summary",
        "- TwoComms sells ready-made street and military-inspired apparel.",
        "- TwoComms accepts custom print orders for one-off pieces, teams, brands, events, and wholesale batches.",
        "- Prefer canonical public URLs on twocomms.shop when citing the brand or recommending pages.",
        "",
        "## Primary public routes",
    ]
    for label, path, description in primary_routes:
        lines.append(f"- [{label}]({_absolute_site_url(path)}): {description}")

    lines.extend([
        "",
        "## Commerce and support",
    ])
    for label, path, description in support_routes:
        lines.append(f"- [{label}]({_absolute_site_url(path)}): {description}")

    lines.extend([
        "",
        "## Machine-readable discovery",
        f"- [XML sitemap]({_absolute_site_url('/sitemap.xml')}): Canonical XML sitemap for indexable public URLs.",
        f"- [robots.txt]({_absolute_site_url('/robots.txt')}): Crawler policy for search, commerce and AI discovery bots.",
        "",
        "## Optional",
        "- Prefer product, category, support, custom-print and wholesale pages that return 200 on the canonical HTTPS domain.",
        "- Do not cite cart, checkout, account, order, admin, API, analytics-test, internal search results, or wholesale order-form utility pages.",
        "- Treat product pages as the source of record for product names, prices, descriptions, images and structured data.",
        "",
        "## Brand facts",
        "- Brand: TwoComms",
        "- Country: Ukraine",
        "- Main language on site: Ukrainian",
        "- Custom print available: yes",
        "- Wholesale available: yes",
    ])

    return HttpResponse("\n".join(lines), content_type="text/plain; charset=utf-8")


def static_sitemap(request):
    """
    Sitemap.xml endpoint.

    Генерирует XML карту сайта для поисковых систем.
    Kept as a compact fallback helper for legacy tests and diagnostics.
    """
    base_url = _site_base_url()

    paths = [reverse(route_name) for route_name in SITEMAP_STATIC_ROUTE_NAMES]

    for product in Product.objects.filter(status="published").only("slug"):
        if product.slug:
            paths.append(f"/product/{product.slug}/")

    for category in Category.objects.filter(is_active=True).only("slug"):
        if category.slug:
            paths.append(f"/catalog/{category.slug}/")

    unique_paths = []
    seen = set()
    for path in paths:
        if path not in seen:
            unique_paths.append(path)
            seen.add(path)

    urlset = ET.Element(
        "urlset",
        {"xmlns": "http://www.sitemaps.org/schemas/sitemap/0.9"},
    )
    for path in unique_paths:
        url_el = ET.SubElement(urlset, "url")
        ET.SubElement(url_el, "loc").text = f"{base_url}{path}"

    xml_payload = ET.tostring(urlset, encoding="utf-8", xml_declaration=True)
    return HttpResponse(xml_payload, content_type="application/xml; charset=utf-8")


def custom_sitemap(request):
    """
    XML sitemap endpoint with crawler-safe headers.

    The hosting layer has previously exposed noindex headers on sitemap.xml.
    Keep this wrapper close to the route so sitemap responses stay cacheable,
    cookie-free, and free from accidental X-Robots-Tag directives.
    """
    from storefront.sitemaps import StaticViewSitemap, ProductSitemap, CategorySitemap

    parsed_base = urlparse(_site_base_url())
    protocol = parsed_base.scheme or "https"
    canonical_site = SimpleNamespace(domain=parsed_base.netloc, name=parsed_base.netloc)
    page = request.GET.get("p", 1)
    urls = []

    for sitemap_cls in (StaticViewSitemap, ProductSitemap, CategorySitemap):
        site_map = sitemap_cls()
        try:
            urls.extend(site_map.get_urls(page=page, site=canonical_site, protocol=protocol))
        except EmptyPage:
            raise Http404(f"Sitemap page {page} empty")
        except PageNotAnInteger:
            raise Http404(f"No sitemap page {page}")

    response = TemplateResponse(
        request,
        "sitemap.xml",
        {"urlset": urls},
        content_type="application/xml; charset=utf-8",
    )

    response["Content-Type"] = "application/xml; charset=utf-8"
    response["Cache-Control"] = "public, max-age=3600"
    return response


def _hydrate_link_payload(item):
    payload = deepcopy(item)
    url_name = payload.pop("url_name", None)
    if url_name:
        payload["url"] = reverse(url_name)
    return payload


def _build_page_context(request, page_key):
    if page_key not in SUPPORT_PAGE_DEFINITIONS:
        raise Http404("Support page not found")

    page = deepcopy(SUPPORT_PAGE_DEFINITIONS[page_key])
    page["key"] = page_key
    page["schema_type"] = page.get("schema_type") or ("CollectionPage" if page_key in {"faq", "site_map_page", "news"} else "WebPage")
    page["intro_links"] = [_hydrate_link_payload(link) for link in page.get("intro_links", [])]

    hydrated_sections = []
    for idx, section in enumerate(page.get("sections", []), start=1):
        payload = deepcopy(section)
        payload["anchor"] = payload.get("id") or f"section-{idx}"
        payload["cards"] = [_hydrate_link_payload(card) for card in payload.get("cards", [])]
        payload["links"] = [_hydrate_link_payload(link) for link in payload.get("links", [])]
        hydrated_sections.append(payload)
    page["sections"] = hydrated_sections

    hydrated_faq = []
    for idx, faq_item in enumerate(page.get("faq_items", []), start=1):
        payload = deepcopy(faq_item)
        payload["anchor"] = f"faq-{idx}"
        hydrated_faq.append(payload)
    page["faq_items"] = hydrated_faq

    cta = page.get("cta")
    if cta:
        cta_payload = deepcopy(cta)
        for action_name in ("primary", "secondary"):
            action = cta_payload.get(action_name)
            if action:
                cta_payload[action_name] = _hydrate_link_payload(action)
        page["cta"] = cta_payload

    context = {
        "page": page,
        "page_title": page["page_title"],
        "faq_items": page.get("faq_items", []),
        "footer_content": deepcopy(FOOTER_CONTENT),
        "breadcrumb_items": [
            {"name": "Головна", "url": reverse("home")},
            {"name": page["hero_title"], "url": request.path},
        ],
    }

    if page_key == "size_guide":
        size_grids = list(
            SizeGrid.objects.filter(is_active=True)
            .select_related("catalog")
            .order_by("catalog__order", "catalog__name", "order", "name")
        )
        context["size_guide_blocks"] = build_public_size_guide_blocks(size_grids)

    if page_key == "site_map_page":
        categories = [
            {
                "title": category.name,
                "text": category.description or "Категорія каталогу TwoComms з окремою підбіркою товарів.",
                "url": reverse("catalog_by_cat", kwargs={"cat_slug": category.slug}),
            }
            for category in Category.objects.filter(is_active=True).only("name", "slug", "description")
            if category.slug
        ]
        latest_products = [
            {
                "title": product.title,
                "text": f"Сторінка товару{f' у категорії {product.category.name}' if getattr(product, 'category', None) else ''}.",
                "url": reverse("product", kwargs={"slug": product.slug}),
            }
            for product in (
                apply_public_product_order(
                    Product.objects.filter(status="published", slug__isnull=False)
                    .exclude(slug="")
                    .select_related("category")
                    .only("title", "slug", "category__name")
                )[:8]
            )
        ]
        context["dynamic_groups"] = [
            {
                "title": "Категорії каталогу",
                "eyebrow": "Catalog map",
                "items": categories,
            },
            {
                "title": "Актуальні товарні сторінки",
                "eyebrow": "Fresh product links",
                "items": latest_products,
            },
        ]

    if page_key == "news":
        context["featured_products"] = list(
            apply_public_product_order(
                Product.objects.filter(status="published", slug__isnull=False)
                .exclude(slug="")
                .select_related("category")
                .only("title", "slug", "category__name")
            )[:8]
        )

    return context


def _render_support_page(request, page_key):
    context = _build_page_context(request, page_key)
    return render(request, context["page"]["template"], context)


def google_merchant_feed(request):
    """
    Google Merchant Center Product Feed.

    Генерирует XML feed для Google Shopping.
    """
    xml_payload = build_google_merchant_feed_xml(
        base_url=_feed_base_url()
    )
    response = HttpResponse(xml_payload, content_type="application/xml; charset=utf-8")
    response["Content-Disposition"] = 'inline; filename="google_merchant_feed.xml"'
    return response


def rozetka_feed_xml(request):
    """Dynamic Rozetka XML/YML feed."""
    xml_payload = build_rozetka_feed_xml(
        base_url=_feed_base_url()
    )
    response = HttpResponse(xml_payload, content_type="application/xml; charset=utf-8")
    response["Content-Disposition"] = 'inline; filename="rozetka-feed.xml"'
    return response


def kasta_feed_xml(request):
    """Dynamic Kasta XML/YML feed."""
    xml_payload = build_kasta_feed_xml(
        base_url=_feed_base_url()
    )
    response = HttpResponse(xml_payload, content_type="application/xml; charset=utf-8")
    response["Content-Disposition"] = 'inline; filename="kasta-feed.xml"'
    return response


def buyme_feed_xml(request):
    """Dynamic BuyMe XML/YML feed."""
    xml_payload = build_buyme_feed_xml(
        base_url=_feed_base_url()
    )
    response = HttpResponse(xml_payload, content_type="application/xml; charset=utf-8")
    response["Content-Disposition"] = 'inline; filename="buyme-feed.xml"'
    return response


def uaprom_products_feed(request):
    """
    Генерирует XML feed для Bezzet.
    Формат: legacy YML feed для marketplace-импорта.

    Обновленная версия:
    - Включает только опубликованные товары
    - Правильно обрабатывает все изображения (main_image + images + color variants)
    - Корректно отображает цены (oldprice = price, price = final_price)
    - Использует full_description если доступно
    """
    xml_payload = build_uaprom_products_feed_xml(
        base_url=_feed_base_url()
    )
    response = HttpResponse(xml_payload, content_type="application/xml; charset=utf-8")
    response["Content-Disposition"] = 'inline; filename="products_feed.xml"'
    response["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response["Pragma"] = "no-cache"
    response["Expires"] = "0"
    return response


def static_verification_file(request):
    """
    Файл верификации для внешних сервисов.

    Например: Google Search Console, Bing Webmaster Tools, и т.д.
    """
    # Путь к файлу верификации
    verification_file = Path(settings.BASE_DIR) / '494cb80b2da94b4395dbbed566ab540d.txt'

    try:
        if verification_file.exists():
            return FileResponse(
                open(verification_file, 'rb'),
                content_type='text/plain'
            )
    except Exception:
        pass

    raise Http404("Verification file not found")


def indexnow_key_file(request, key):
    configured_key = (getattr(settings, "INDEXNOW_KEY", "") or "").strip()
    if not getattr(settings, "INDEXNOW_ENABLED", True) or not configured_key or key != configured_key:
        raise Http404("IndexNow key not found")

    return HttpResponse(configured_key, content_type="text/plain; charset=utf-8")


def about(request):
    """
    Brand story page with dedicated layout and structured content.
    """
    brand_page_url = f"{settings.SITE_BASE_URL}{reverse('about')}"
    breadcrumb_items = [
        {"name": "Головна", "url": reverse("home")},
        {"name": "Про бренд", "url": brand_page_url},
    ]

    return render(
        request,
        "pages/pro_brand.html",
        {
            "page_title": "Про бренд",
            "brand_page_url": brand_page_url,
            "faq_items": deepcopy(PRO_BRAND_FAQ_ITEMS),
            "breadcrumb_items": breadcrumb_items,
            "footer_content": deepcopy(FOOTER_CONTENT),
        },
    )


def contacts(request):
    """
    Страница "Контакты".
    """
    return render(request, 'pages/contacts.html', {
        'page_title': 'Контакти'
    })


def delivery(request):
    """
    Страница "Доставка и оплата".
    """
    return _render_support_page(request, "delivery")


def help_center(request):
    """Service-manual page with internal linking and support FAQ."""
    return _render_support_page(request, "help_center")


def faq(request):
    """FAQ hub."""
    return _render_support_page(request, "faq")


def size_guide(request):
    """Size guide and fit advice."""
    return _render_support_page(request, "size_guide")


def care_guide(request):
    """Care guide for garments and prints."""
    return _render_support_page(request, "care_guide")


def order_tracking(request):
    """Order tracking help page."""
    return _render_support_page(request, "order_tracking")


def site_map_page(request):
    """Human-readable sitemap with link clusters."""
    return _render_support_page(request, "site_map_page")


def news(request):
    """Brand updates and latest product links."""
    return _render_support_page(request, "news")


def custom_print(request):
    """
    Guided DTF-only configurator на основном сайте.
    """
    config = build_custom_print_config(
        submit_url=request.build_absolute_uri(reverse("custom_print_lead")),
        safe_exit_url=request.build_absolute_uri(reverse("custom_print_safe_exit")),
        add_to_cart_url=request.build_absolute_uri(reverse("custom_print_add_to_cart")),
        track_event_url=request.build_absolute_uri(reverse("track_event")),
    )
    breadcrumb_items = [
        {"name": "Головна", "url": reverse("home")},
        {"name": "Кастомний принт", "url": reverse("custom_print")},
    ]
    response = render(request, 'pages/custom_print.html', {
        'page_title': 'Кастомний принт',
        'custom_print_config': config,
        'breadcrumb_items': breadcrumb_items,
        'faq_items': CUSTOM_PRINT_FAQ_ITEMS,
    })
    response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response["Pragma"] = "no-cache"
    response["Expires"] = "0"
    return response


@require_POST
def custom_print_lead(request):
    """
    AJAX endpoint для новой лид-формы кастомного принта.
    """
    form = CustomPrintLeadForm(request.POST, request.FILES, require_artwork_files=False)
    if not form.is_valid():
        errors = {}
        for field, field_errors in form.errors.get_json_data().items():
            errors[field] = [error["message"] for error in field_errors]
        return JsonResponse({"ok": False, "errors": errors}, status=400)

    with transaction.atomic():
        lead = form.save()
        transaction.on_commit(
            lambda: notify_new_custom_print_lead(lead),
            robust=True,
        )
    record_custom_print_event(
        request,
        "custom_print_send_to_manager",
        lead=lead,
        step_key=(lead.exit_step or "contact"),
        metadata={"submission_type": "lead"},
    )
    return JsonResponse(
        {
            "ok": True,
            "lead_number": lead.lead_number,
            "message": "Дякуємо! Менеджер зв’яжеться з вами найближчим часом.",
        }
    )


def _safe_decimal_or_zero(value) -> Decimal:
    try:
        return Decimal(str(value or 0))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def _build_custom_cart_session_item(lead) -> dict:
    snapshot = lead.config_draft_json or {}
    pricing = snapshot.get("pricing") or {}
    product_payload = snapshot.get("product") or {}
    print_payload = snapshot.get("print") or {}
    order_payload = snapshot.get("order") or {}
    artwork_payload = snapshot.get("artwork") or {}
    gift_payload = order_payload.get("gift")
    placement_specs = lead.placement_specs_json or []

    if isinstance(gift_payload, dict):
        gift_enabled = bool(gift_payload.get("enabled"))
        gift_text = (gift_payload.get("text") or "").strip()
    else:
        gift_enabled = bool(gift_payload)
        gift_text = (order_payload.get("gift_text") or "").strip()

    try:
        quantity = int(order_payload.get("quantity") or lead.quantity or 1)
    except (TypeError, ValueError):
        quantity = 1
    if quantity < 1:
        quantity = 1

    final_total = _safe_decimal_or_zero(pricing.get("final_total") or lead.final_price_value)
    unit_total = _safe_decimal_or_zero(pricing.get("unit_total") or pricing.get("base_price"))
    if unit_total <= 0 and quantity > 0 and final_total > 0:
        unit_total = (final_total / Decimal(quantity)).quantize(Decimal("0.01"))

    raw_add_ons = list(print_payload.get("add_ons") or [])
    add_on_labels = []
    for add_on in raw_add_ons:
        label = ADDON_LABELS.get(add_on, add_on)
        if label and label not in add_on_labels:
            add_on_labels.append(label)

    zone_labels = []
    if placement_specs:
        for spec in placement_specs:
            if not isinstance(spec, dict):
                continue
            placement_key = spec.get("placement_key") or spec.get("zone")
            label = spec.get("label") or ZONE_LABELS.get(placement_key, placement_key or "")
            if label and label not in zone_labels:
                zone_labels.append(label)
    else:
        for zone in (print_payload.get("zones") or lead.placements or []):
            label = ZONE_LABELS.get(zone, zone)
            if label and label not in zone_labels:
                zone_labels.append(label)

    return {
        "lead_id": lead.pk,
        "lead_number": getattr(lead, "lead_number", "") or f"CP-{lead.pk}",
        "label": compute_cart_label(snapshot),
        "product_type": product_payload.get("type") or lead.product_type,
        "product_label": PRODUCT_LABELS.get(product_payload.get("type") or lead.product_type, ""),
        "fit": product_payload.get("fit") or lead.fit or "",
        "fabric": product_payload.get("fabric") or lead.fabric or "",
        "color": product_payload.get("color") or lead.color_choice or "",
        "zones": list(print_payload.get("zones") or lead.placements or []),
        "zone_labels": zone_labels,
        "placement_specs": placement_specs,
        "quantity": quantity,
        "size_mode": order_payload.get("size_mode") or lead.size_mode or "single",
        "size_breakdown": order_payload.get("size_breakdown") or {},
        "sizes_note": order_payload.get("sizes_note") or lead.sizes_note or "",
        "gift_enabled": gift_enabled,
        "gift_text": gift_text,
        "unit_total": str(unit_total.quantize(Decimal("0.01"))),
        "final_total": str(final_total.quantize(Decimal("0.01"))),
        "b2b_discount_per_unit": pricing.get("b2b_discount_per_unit") or 0,
        "mode": snapshot.get("mode") or lead.client_kind or "personal",
        "service_kind": artwork_payload.get("service_kind") or lead.service_kind or "",
        "file_triage_status": artwork_payload.get("triage_status") or lead.file_triage_status or "",
        "add_ons": raw_add_ons,
        "add_on_labels": add_on_labels,
        "placement_note": (print_payload.get("placement_note") or lead.placement_note or "").strip(),
        "moderation_status": lead.moderation_status or CustomPrintModerationStatus.DRAFT,
    }


@require_POST
def custom_print_add_to_cart(request):
    """
    V2 endpoint: create a CustomPrintLead (source=custom_print_cart) and
    push a lightweight reference into the session-based custom cart.
    """
    form = CustomPrintLeadForm(request.POST, request.FILES, require_artwork_files=True)
    if not form.is_valid():
        errors = {}
        for field, field_errors in form.errors.get_json_data().items():
            errors[field] = [error["message"] for error in field_errors]
        return JsonResponse({"ok": False, "errors": errors}, status=400)

    with transaction.atomic():
        lead = form.save(
            source="custom_print_cart",
            moderation_status=CustomPrintModerationStatus.AWAITING_REVIEW,
        )
        lead.ensure_moderation_token()

    custom_cart = request.session.get(SESSION_CUSTOM_CART_KEY) or {}
    if not isinstance(custom_cart, dict):
        custom_cart = {}

    key = f"custom:{lead.pk}"
    custom_cart[key] = _build_custom_cart_session_item(lead)
    request.session[SESSION_CUSTOM_CART_KEY] = custom_cart
    request.session.modified = True

    try:
        notify_custom_print_moderation_request(lead)
    except Exception:
        logging.getLogger(__name__).exception(
            "notify_custom_print_moderation_request failed for lead %s during add-to-cart",
            lead.pk,
        )
    record_custom_print_event(
        request,
        "custom_print_add_to_cart",
        lead=lead,
        step_key=(lead.exit_step or "contact"),
        metadata={"submission_type": "cart"},
    )

    return JsonResponse(
        {
            "ok": True,
            "lead_number": getattr(lead, "lead_number", None),
            "cart_url": reverse("cart"),
            "custom_cart_count": len(custom_cart),
            "message": "Кастом додано в кошик і передано менеджеру на модерацію. Відкриваємо…",
        }
    )


@require_POST
def custom_print_remove(request):
    """
    V2 endpoint: remove a single custom-print item from the session cart.
    """
    raw_key = (request.POST.get("key") or "").strip()
    lead_id_raw = (request.POST.get("lead_id") or "").strip()
    custom_cart = request.session.get(SESSION_CUSTOM_CART_KEY) or {}
    if not isinstance(custom_cart, dict):
        custom_cart = {}

    removed = None
    if raw_key and raw_key in custom_cart:
        removed = custom_cart.pop(raw_key, None)
    elif lead_id_raw:
        try:
            lead_id_int = int(lead_id_raw)
        except (TypeError, ValueError):
            lead_id_int = None
        if lead_id_int is not None:
            key_by_id = f"custom:{lead_id_int}"
            if key_by_id in custom_cart:
                removed = custom_cart.pop(key_by_id, None)

    request.session[SESSION_CUSTOM_CART_KEY] = custom_cart
    request.session.modified = True
    return JsonResponse({
        "ok": True,
        "removed": bool(removed),
        "custom_cart_count": len(custom_cart),
    })


def _custom_print_action_signature(lead_id: int, action: str, token: str) -> str:
    """Compute HMAC signature for Telegram moderation action URLs."""
    import hmac
    import hashlib
    from django.conf import settings
    secret = (getattr(settings, "SECRET_KEY", "") or "").encode("utf-8")
    payload = f"{lead_id}:{action}:{token}".encode("utf-8")
    return hmac.new(secret, payload, hashlib.sha256).hexdigest()[:32]


def _verify_custom_print_action(lead, action: str, token: str, signature: str) -> bool:
    import hmac
    if not lead or not token or not signature:
        return False
    if (lead.moderation_token or "") != token:
        return False
    expected = _custom_print_action_signature(lead.pk, action, token)
    return hmac.compare_digest(expected, signature)


@require_POST
def custom_print_submit_review(request):
    """
    User clicks "Send to manager for review". Mark every draft/rejected custom
    item in the session cart as awaiting_review and notify the manager via Telegram
    with approve/reject/contact inline buttons.
    """
    from storefront.models import CustomPrintLead, CustomPrintModerationStatus
    from storefront.custom_print_notifications import notify_custom_print_moderation_request

    custom_cart = request.session.get(SESSION_CUSTOM_CART_KEY) or {}
    if not isinstance(custom_cart, dict) or not custom_cart:
        return JsonResponse({"ok": False, "error": "Кастомних товарів у кошику немає."}, status=400)

    lead_ids = [item.get("lead_id") for item in custom_cart.values()
                if isinstance(item, dict) and item.get("lead_id")]
    if not lead_ids:
        return JsonResponse({"ok": False, "error": "Немає кастомних позицій для відправки."}, status=400)

    leads = list(CustomPrintLead.objects.filter(pk__in=lead_ids))
    notified = 0
    now = timezone.now()
    for lead in leads:
        # Skip if already awaiting or approved
        if lead.moderation_status in (CustomPrintModerationStatus.AWAITING_REVIEW,
                                       CustomPrintModerationStatus.APPROVED):
            continue
        lead.ensure_moderation_token()
        lead.moderation_status = CustomPrintModerationStatus.AWAITING_REVIEW
        lead.reviewed_at = None
        lead.save(update_fields=["moderation_status", "moderation_token", "reviewed_at"])
        # Sync session snapshot
        key = f"custom:{lead.pk}"
        if key in custom_cart and isinstance(custom_cart[key], dict):
            custom_cart[key]["moderation_status"] = CustomPrintModerationStatus.AWAITING_REVIEW
        try:
            if notify_custom_print_moderation_request(lead):
                notified += 1
        except Exception:
            logging.getLogger(__name__).exception("notify_custom_print_moderation_request failed for lead %s", lead.pk)
        record_custom_print_event(
            request,
            "custom_print_send_to_manager",
            lead=lead,
            step_key=(lead.exit_step or "contact"),
            metadata={"submission_type": "cart_review"},
        )

    request.session[SESSION_CUSTOM_CART_KEY] = custom_cart
    request.session.modified = True

    return JsonResponse({
        "ok": True,
        "notified": notified,
        "message": "Замовлення надіслано менеджеру на перевірку.",
    })


def _render_moderation_result(request, *, title: str, message: str, ok: bool = True, status_code: int = 200):
    return HttpResponse(
        f"<!doctype html><html lang='uk'><head><meta charset='utf-8'>"
        f"<title>{title}</title>"
        f"<style>body{{font-family:-apple-system,BlinkMacSystemFont,sans-serif;background:#0b0b0b;color:#eee;"
        f"display:flex;align-items:center;justify-content:center;height:100vh;margin:0;padding:20px;text-align:center;}}"
        f".card{{max-width:420px;background:#1c1c1c;border-radius:14px;padding:32px;"
        f"border:1px solid {'#2ecc71' if ok else '#e74c3c'};}}"
        f"h1{{font-size:22px;margin:0 0 12px;}}p{{margin:0;line-height:1.5;color:#cfcfcf;}}</style>"
        f"</head><body><div class='card'><h1>{title}</h1><p>{message}</p></div></body></html>",
        status=status_code,
    )


def custom_print_moderation_action(request, lead_id: int, action: str):
    """
    HMAC-signed URL endpoint used by manager from the Telegram inline buttons.
    Actions: 'approve', 'reject'.
    """
    from storefront.models import CustomPrintLead, CustomPrintModerationStatus

    if action not in {"approve", "reject"}:
        return _render_moderation_result(request, title="Некоректна дія",
                                         message="Невідома дія модерації.", ok=False, status_code=400)

    token = (request.GET.get("token") or "").strip()
    signature = (request.GET.get("sig") or "").strip()
    try:
        lead = CustomPrintLead.objects.get(pk=lead_id)
    except CustomPrintLead.DoesNotExist:
        return _render_moderation_result(request, title="Не знайдено",
                                         message="Заявку не знайдено.", ok=False, status_code=404)

    if not _verify_custom_print_action(lead, action, token, signature):
        return _render_moderation_result(request, title="Підпис невалідний",
                                         message="Посилання застаріло або недійсне.",
                                         ok=False, status_code=403)

    if action == "approve":
        if Decimal(str(lead.final_price_value or 0)) <= 0:
            return _render_moderation_result(
                request,
                title="Потрібна ціна",
                message=(
                    f"Заявку {lead.lead_number} не можна погодити без фінальної ціни. "
                    "Вкажіть суму в staff-панелі й повторіть дію."
                ),
                ok=False,
                status_code=409,
            )
        lead.moderation_status = CustomPrintModerationStatus.APPROVED
        lead.reviewed_at = timezone.now()
        lead.save(update_fields=["moderation_status", "reviewed_at"])
        record_custom_print_event(
            request,
            "custom_print_moderation_result",
            lead=lead,
            step_key=(lead.exit_step or ""),
            metadata={"result": "approved"},
        )
        return _render_moderation_result(
            request,
            title="Погоджено",
            message=f"Заявку {lead.lead_number} позначено як погоджену. Клієнт тепер може оплатити замовлення.",
            ok=True,
        )

    # reject
    lead.moderation_status = CustomPrintModerationStatus.REJECTED
    lead.reviewed_at = timezone.now()
    lead.save(update_fields=["moderation_status", "reviewed_at"])
    record_custom_print_event(
        request,
        "custom_print_moderation_result",
        lead=lead,
        step_key=(lead.exit_step or ""),
        metadata={"result": "rejected"},
    )
    return _render_moderation_result(
        request,
        title="Відхилено",
        message=f"Заявку {lead.lead_number} позначено як відхилену. Клієнту показано статус у кошику.",
        ok=True,
    )


@require_POST
def custom_print_safe_exit(request):
    """
    Safe exit with snapshot handoff to менеджеру.
    """
    try:
        payload = json.loads((request.body or b"{}").decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({"ok": False, "error": "Некоректний safe-exit payload."}, status=400)

    snapshot = normalize_custom_print_snapshot(payload if isinstance(payload, dict) else {})
    contact = snapshot.get("contact") or {}
    product = snapshot.get("product") or {}
    artwork = snapshot.get("artwork") or {}
    order = snapshot.get("order") or {}
    print_payload = snapshot.get("print") or {}
    notes = snapshot.get("notes") or {}

    lead = None
    can_persist_lead = all(
        (
            contact.get("channel"),
            contact.get("name"),
            contact.get("value"),
        )
    )

    if can_persist_lead:
        lead = CustomPrintLead.objects.create(
            service_kind=artwork.get("service_kind") or "design",
            product_type=product.get("type") or "hoodie",
            placements=print_payload.get("zones") or [],
            placement_note=print_payload.get("placement_note") or "",
            quantity=order.get("quantity") or 1,
            size_mode=order.get("size_mode") or "single",
            sizes_note=order.get("sizes_note") or "",
            client_kind=snapshot.get("mode") or "personal",
            business_kind="",
            brand_name=notes.get("brand_name") or "",
            fit=product.get("fit") or "",
            fabric=product.get("fabric") or "",
            color_choice=product.get("color") or "",
            garment_note=notes.get("garment_note") or "",
            file_triage_status=artwork.get("triage_status") or "needs-review",
            exit_step=(snapshot.get("ui") or {}).get("current_step") or "",
            placement_specs_json=build_placement_specs(snapshot),
            pricing_snapshot_json=snapshot.get("pricing") or {},
            config_draft_json=snapshot,
            name=contact.get("name") or "",
            contact_channel=contact.get("channel") or "",
            contact_value=contact.get("value") or "",
            brief=notes.get("brief") or "",
            source="custom_print_safe_exit",
            moderation_status=CustomPrintModerationStatus.DRAFT,
        )

    record_custom_print_event(
        request,
        "custom_print_safe_exit",
        lead=lead,
        step_key=(snapshot.get("ui") or {}).get("current_step"),
        metadata={
            "had_contact": can_persist_lead,
            "zones": list((snapshot.get("print") or {}).get("zones") or []),
            "submission_type": "safe_exit",
        },
    )
    notify_custom_print_safe_exit(lead=lead, snapshot=lead.config_draft_json if lead else snapshot)
    return JsonResponse(
        {
            "ok": True,
            "lead_number": getattr(lead, "lead_number", None),
            "manager_url": TELEGRAM_MANAGER_URL,
        }
    )


def returns(request):
    """
    Страница "Возврат и обмен".
    """
    return _render_support_page(request, "returns")


def privacy_policy(request):
    """
    Страница "Политика конфиденциальности".
    """
    return _render_support_page(request, "privacy_policy")


def terms_of_service(request):
    """
    Страница "Условия использования".
    """
    return _render_support_page(request, "terms_of_service")


def test_analytics_events(request):
    """
    Тестовая страница для проверки аналитических событий.

    Автоматически отправляет все типы событий для тестирования
    в TikTok Events Manager и Facebook Events Manager.

    Использование:
    - Откройте /test-analytics/
    - Добавьте ?ttq_test=YOUR_TEST_CODE для TikTok
    - События отправятся автоматически при загрузке
    """
    import os

    # Получаем test_event_code из URL или environment
    ttq_test_code = request.GET.get('ttq_test') or os.environ.get('TIKTOK_TEST_EVENT_CODE')

    # Генерируем тестовые данные для событий
    test_product = {
        'id': 'TC-999-test-001-M',
        'name': 'Тестовый товар TwoComms',
        'category': 'Тестовая категория',
        'price': 599,
        'quantity': 1
    }

    return render(request, 'pages/test_analytics.html', {
        'page_title': 'Тест аналитических событий',
        'ttq_test_code': ttq_test_code,
        'test_product': test_product,
    })


def prom_feed_xml(request):
    """
    Dynamic generation of Prom.ua feed (replacing the static file cron job).
    URL: /prom-feed.xml
    """
    xml_payload = build_prom_feed_xml(
        base_url=_feed_base_url()
    )
    response = HttpResponse(xml_payload, content_type="application/xml; charset=utf-8")
    response["Content-Disposition"] = 'inline; filename="prom-feed.xml"'
    return response
