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
import importlib.machinery
import importlib.util
import json
import logging
from decimal import Decimal, InvalidOperation
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from urllib.parse import urljoin

from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.conf import settings
from django.shortcuts import render
from django.db import transaction
from django.views.decorators.http import require_POST
from django.utils.text import slugify
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
from storefront.services.catalog_helpers import apply_public_product_order
from storefront.services.size_guides import build_public_size_guide_blocks, resolve_product_sizes
from storefront.utils.analytics_helpers import FEED_DEFAULT_COLOR, normalize_feed_color
from storefront.support_content import (
    FOOTER_CONTENT,
    PRO_BRAND_FAQ_ITEMS,
    SUPPORT_PAGE_DEFINITIONS,
)

# Константы для feed
DEFAULT_FEED_SEASON = "Демисезон"
_LEGACY_GOOGLE_MERCHANT_FEED = None
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
        "question": "Як оформити партію для бренду, команди або події?",
        "answer": "Оберіть формат для команди або бренду, вкажіть кількість, розміри та контакт. Після цього ми допоможемо узгодити тираж, принт, дедлайни й умови для партії.",
    },
]

# Вспомогательные функции для feed


def _sanitize_feed_description(raw: str) -> str:
    if not raw:
        return ""
    cleaned = re.sub(r"(?is)<[^>]*?(?:цена|price|грн|uah|₴)[^>]*?>.*?</[^>]+>", "", raw)
    cleaned = re.sub(r"(?i)цена\s*[:\-]?[^\n<]*", "", cleaned)
    cleaned = re.sub(r"\d+[\s.,]*(?:грн|uah|₴)", "", cleaned, flags=re.IGNORECASE)
    lines = re.split(r"\r?\n", cleaned)
    price_line = re.compile(r"(?i)(грн|uah|₴|цена|price)")
    filtered = [line for line in lines if line and not price_line.search(line)]
    collapsed = "\n".join(filtered)
    collapsed = re.sub(r"\n{3,}", "\n\n", collapsed)
    return collapsed.strip()


def _material_for_product(product) -> str:
    lookup_source = " ".join(filter(None, [
        product.category.name if getattr(product, "category", None) else "",
        product.title or "",
        product.slug or ""
    ])).lower()

    if any(token in lookup_source for token in ("худі", "hood", "hudi")):
        return "трехнитка с начесом"
    if "лонг" in lookup_source or "long" in lookup_source:
        return "бамбук"
    return "кулирка"


def _normalize_color_name(raw_color: str | None) -> str:
    return normalize_feed_color(raw_color)


def _absolute_media_url(base_url: str, path: str | None) -> str | None:
    if not path:
        return None
    if path.startswith("http://") or path.startswith("https://"):
        return path
    if not path.startswith("/"):
        path = f"/{path}"
    return urljoin(base_url, path)


# ==================== STATIC PAGES ====================

def robots_txt(request):
    """
    Генерирует robots.txt файл.

    Returns:
        HttpResponse: текстовый файл robots.txt
    """
    lines = [
        "User-agent: *",
        "Allow: /",
        "",
        "# Disallow internal/admin pages",
        "Disallow: /admin/",
        "Disallow: /admin-panel/",
        "Disallow: /accounts/",
        "Disallow: /orders/",
        "Disallow: /cart/",
        "Disallow: /checkout/",
        "Disallow: /api/",
        "Disallow: /debug/",
        "Disallow: /dev/",
        "",
        "# Search results — noindex reinforcement",
        "Disallow: /search/",
        "",
        "# Explicitly allow AI search, citation and model discovery bots",
        "User-agent: OAI-SearchBot",
        "Allow: /",
        "",
        "User-agent: ChatGPT-User",
        "Allow: /",
        "",
        "User-agent: Claude-SearchBot",
        "Allow: /",
        "",
        "User-agent: Claude-User",
        "Allow: /",
        "",
        "User-agent: PerplexityBot",
        "Allow: /",
        "",
        "User-agent: Perplexity-User",
        "Allow: /",
        "",
        "# Gemini grounding is controlled via Google-Extended",
        "User-agent: Google-Extended",
        "Allow: /",
        "",
        "# Allow training and research crawlers because this site wants maximum AI discoverability",
        "User-agent: GPTBot",
        "Allow: /",
        "",
        "User-agent: CCBot",
        "Allow: /",
        "",
        "User-agent: ClaudeBot",
        "Allow: /",
        "",
        "User-agent: anthropic-ai",
        "Allow: /",
        "",
        f"Sitemap: {request.build_absolute_uri('/sitemap.xml')}",
    ]

    return HttpResponse("\n".join(lines), content_type="text/plain")


def llms_txt(request):
    """
    Machine-readable orientation file for LLM agents and answer engines.

    This is not a ranking guarantee, but it gives AI retrieval systems a compact
    canonical map of the public brand surface and preferred landing pages.
    """
    entries = [
        ("Home", reverse("home")),
        ("Catalog", reverse("catalog")),
        ("Custom print", reverse("custom_print")),
        ("Wholesale", reverse("wholesale_page")),
        ("Cooperation", reverse("cooperation")),
        ("Delivery and payment", reverse("delivery")),
        ("Contacts", reverse("contacts")),
        ("About brand", reverse("about")),
        ("FAQ", reverse("faq")),
        ("Size guide", reverse("size_guide")),
        ("Care guide", reverse("care_guide")),
        ("Order tracking", reverse("order_tracking")),
        ("Human sitemap", reverse("site_map_page")),
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
    for label, path in entries:
        lines.append(f"- {label}: {request.build_absolute_uri(path)}")

    lines.extend([
        "",
        "## Best starting points by intent",
        f"- Ready-made apparel shopping: {request.build_absolute_uri(reverse('catalog'))}",
        f"- Custom apparel or your own print: {request.build_absolute_uri(reverse('custom_print'))}",
        f"- Wholesale, team, or B2B orders: {request.build_absolute_uri(reverse('wholesale_page'))}",
        f"- Brand overview and trust signals: {request.build_absolute_uri(reverse('about'))}",
        "",
        "## Crawl and citation guidance",
        "- Prefer product, category, support, and service pages that return 200 on the main domain.",
        "- Avoid citing internal search, cart, checkout, admin, API, analytics-test, and wholesale order-form utilities.",
        f"- XML sitemap: {request.build_absolute_uri('/sitemap.xml')}",
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
    Импортирует реальную функцию из старого views.py.
    """
    scheme = request.scheme or "https"
    host = request.get_host().split(":")[0]
    base_url = f"{scheme}://{host}"

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
    global _LEGACY_GOOGLE_MERCHANT_FEED

    if _LEGACY_GOOGLE_MERCHANT_FEED is None:
        legacy_path = Path(__file__).resolve().parent.parent / "views.py.backup"
        if legacy_path.exists():
            loader = importlib.machinery.SourceFileLoader(
                "storefront.legacy_views_for_google_feed",
                str(legacy_path),
            )
            spec = importlib.util.spec_from_loader(loader.name, loader)
            if spec and spec.loader:
                legacy_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(legacy_module)
                _LEGACY_GOOGLE_MERCHANT_FEED = getattr(legacy_module, "google_merchant_feed", False)
            else:
                _LEGACY_GOOGLE_MERCHANT_FEED = False
        else:
            _LEGACY_GOOGLE_MERCHANT_FEED = False

    if callable(_LEGACY_GOOGLE_MERCHANT_FEED):
        try:
            return _LEGACY_GOOGLE_MERCHANT_FEED(request)
        except Exception:
            logging.getLogger(__name__).exception(
                "Legacy google_merchant_feed failed, using minimal fallback."
            )

    return HttpResponse(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<feed xmlns="http://www.w3.org/2005/Atom"></feed>',
        content_type='application/xml; charset=utf-8'
    )


def uaprom_products_feed(request):
    """
    Генерирует XML feed для Prom.ua / UAPROM.
    Формат: legacy YML feed для marketplace-импорта.

    Обновленная версия:
    - Включает только опубликованные товары
    - Правильно обрабатывает все изображения (main_image + images + color variants)
    - Корректно отображает цены (oldprice = price, price = final_price)
    - Использует full_description если доступно
    """
    logger = logging.getLogger(__name__)

    try:
        base_url = getattr(settings, "FEED_BASE_URL", "").strip() or request.build_absolute_uri("/").rstrip("/")

        # Фильтруем только опубликованные товары
        products_qs = (
            apply_public_product_order(
                Product.objects
                .filter(status='published')  # Только опубликованные товары
                .select_related("category", "catalog")
                .prefetch_related(
                    "catalog__options__values",
                    "images",
                    "color_variants__images",
                    "color_variants__color"
                )
            )
        )
        products = list(products_qs)

        logger.info(f"Generating feed for {len(products)} published products")
    except Exception as e:
        logger.error(f"Error in uaprom_products_feed: {e}", exc_info=True)
        return HttpResponse(
            f'<?xml version="1.0" encoding="UTF-8"?>\n<error>Failed to generate feed: {str(e)}</error>',
            content_type="application/xml; charset=utf-8",
            status=500
        )

    categories_ids = {p.category_id for p in products if p.category_id}
    categories_map = {
        cat.id: cat for cat in Category.objects.select_related().filter(id__in=categories_ids)
    }

    catalog = ET.Element("yml_catalog", {"date": timezone.now().strftime("%Y-%m-%d %H:%M")})
    shop = ET.SubElement(catalog, "shop")
    ET.SubElement(shop, "name").text = "TwoComms"
    ET.SubElement(shop, "company").text = "TWOCOMMS"
    ET.SubElement(shop, "url").text = base_url

    currencies = ET.SubElement(shop, "currencies")
    ET.SubElement(currencies, "currency", {"id": "UAH", "rate": "1"})

    categories_el = ET.SubElement(shop, "categories")
    for cat_id in sorted(categories_ids):
        category = categories_map.get(cat_id)
        if not category:
            continue
        category_el = ET.SubElement(categories_el, "category", {"id": str(category.id)})
        category_el.text = category.name

    offers_el = ET.SubElement(shop, "offers")

    for product in products:
        try:
            material_value = _material_for_product(product)

            # Собираем все изображения товара
            base_image_paths = []

            # Главное изображение
            if product.main_image:
                try:
                    main_img_url = product.main_image.url
                    if main_img_url:
                        base_image_paths.append(main_img_url)
                except Exception as e:
                    logger.debug(f"Error getting main_image for product {product.id}: {e}")

            # Дополнительные изображения товара
            try:
                for img in product.images.all():
                    try:
                        if hasattr(img, "image") and img.image:
                            img_url = img.image.url
                            if img_url and img_url not in base_image_paths:
                                base_image_paths.append(img_url)
                    except Exception as e:
                        logger.debug(f"Error getting image {img.id} for product {product.id}: {e}")
                        continue
            except Exception as e:
                logger.warning(f"Error processing product images for product {product.id}: {e}")

            # Убираем дубликаты, сохраняя порядок
            base_image_paths = list(dict.fromkeys(base_image_paths))

            try:
                color_variants = list(product.color_variants.all())
                if color_variants:
                    variant_payloads = []
                    for variant in color_variants:
                        try:
                            color_label = _normalize_color_name(variant.color.name if variant.color else None)
                            variant_images = []

                            # Собираем все изображения варианта
                            for img in variant.images.all():
                                try:
                                    if hasattr(img, "image") and img.image:
                                        img_url = img.image.url
                                        if img_url and img_url not in variant_images:
                                            variant_images.append(img_url)
                                except Exception as e:
                                    logger.debug(f"Error getting variant image {img.id}: {e}")
                                    continue

                            variant_payloads.append((color_label, variant_images, variant.id))
                        except Exception as e:
                            logger.warning(f"Error processing variant {variant.id} for product {product.id}: {e}")
                            continue
                else:
                    variant_payloads = [(FEED_DEFAULT_COLOR, base_image_paths, None)]
            except Exception as e:
                logger.warning(f"Error processing color variants for product {product.id}: {e}")
                variant_payloads = [(FEED_DEFAULT_COLOR, base_image_paths, None)]

            for color_name, variant_images, variant_id in variant_payloads:
                try:
                    # Объединяем изображения варианта с базовыми (вариант имеет приоритет)
                    # Если у варианта есть изображения, используем их + базовые как дополнение
                    if variant_images:
                        # Начинаем с изображений варианта, затем добавляем базовые, которых нет в варианте
                        images_to_use = list(variant_images)
                        for base_img in base_image_paths:
                            if base_img not in images_to_use:
                                images_to_use.append(base_img)
                    else:
                        # Если у варианта нет изображений, используем базовые
                        images_to_use = base_image_paths

                    # Преобразуем в абсолютные URL
                    image_urls = []
                    for path in images_to_use:
                        try:
                            abs_url = _absolute_media_url(base_url, path)
                            if abs_url and abs_url not in image_urls:
                                image_urls.append(abs_url)
                        except Exception as e:
                            logger.debug(f"Error converting image URL {path}: {e}")
                            continue

                    # Убираем дубликаты, сохраняя порядок
                    image_urls = list(dict.fromkeys(image_urls))

                    # Fallback: если нет изображений, пытаемся использовать первое базовое
                    if not image_urls and base_image_paths:
                        fallback = _absolute_media_url(base_url, base_image_paths[0])
                        if fallback:
                            image_urls = [fallback]

                    group_id = f"TC-GROUP-{product.id}"

                    # Используем full_description если доступно, иначе description
                    raw_description = getattr(product, "full_description", None) or product.description or ""
                    sanitized_description = _sanitize_feed_description(raw_description)
                    if not sanitized_description:
                        # Используем short_description как fallback
                        short_desc = getattr(product, "short_description", None) or ""
                        if short_desc:
                            sanitized_description = short_desc
                        else:
                            sanitized_description = f"TwoComms {product.title} — демисезонная вещь собственного производства."

                    # Украинское описание
                    ua_source = getattr(product, "ai_description", None) or raw_description
                    sanitized_description_ua = _sanitize_feed_description(ua_source)
                    if not sanitized_description_ua:
                        sanitized_description_ua = sanitized_description

                    for size in resolve_product_sizes(product):
                        try:
                            offer_id = product.get_offer_id(variant_id, size)
                            offer_el = ET.SubElement(
                                offers_el,
                                "offer",
                                {"id": offer_id, "available": "true", "group_id": group_id},
                            )

                            product_slug = getattr(product, "slug", f"product-{product.id}") or f"product-{product.id}"
                            product_path = f"/product/{product_slug}/"
                            query = f"?size={size}&color={slugify(color_name, allow_unicode=True)}"
                            ET.SubElement(offer_el, "url").text = f"{urljoin(base_url, product_path)}{query}"

                            # Правильная обработка цен
                            final_price = product.final_price if hasattr(product, 'final_price') else product.price
                            base_price = product.price

                            # Если есть скидка, oldprice = старая цена, price = цена со скидкой
                            if product.has_discount and final_price < base_price:
                                ET.SubElement(offer_el, "oldprice").text = str(base_price)
                                ET.SubElement(offer_el, "price").text = str(final_price)
                            else:
                                # Если нет скидки, только price
                                ET.SubElement(offer_el, "price").text = str(base_price)

                            ET.SubElement(offer_el, "currencyId").text = "UAH"

                            if product.category_id:
                                ET.SubElement(offer_el, "categoryId").text = str(product.category_id)

                            # Добавляем все изображения (до 10 изображений на оффер)
                            for image_url in image_urls[:10]:  # Ограничение Prom.ua - максимум 10 изображений
                                if image_url:  # Проверяем, что URL не пустой
                                    ET.SubElement(offer_el, "picture").text = image_url

                            ET.SubElement(offer_el, "pickup").text = "true"
                            ET.SubElement(offer_el, "delivery").text = "true"

                            product_title = getattr(product, "title", "Товар") or "Товар"
                            display_name = f"TwoComms {product_title} {color_name} {size}"
                            display_name_clean = display_name.strip()
                            ET.SubElement(offer_el, "name").text = display_name_clean
                            ET.SubElement(offer_el, "name_ua").text = display_name_clean
                            ET.SubElement(offer_el, "vendor").text = "TWOCOMMS"
                            ET.SubElement(offer_el, "vendorCode").text = offer_id
                            ET.SubElement(offer_el, "country_of_origin").text = "Украина"

                            description_el = ET.SubElement(offer_el, "description")
                            description_el.text = sanitized_description

                            description_ua_el = ET.SubElement(offer_el, "description_ua")
                            description_ua_el.text = sanitized_description_ua

                            param_size = ET.SubElement(offer_el, "param", {"name": "Размер", "unit": ""})
                            param_size.text = size

                            param_color = ET.SubElement(offer_el, "param", {"name": "Цвет", "unit": ""})
                            param_color.text = color_name

                            param_material = ET.SubElement(offer_el, "param", {"name": "Материал", "unit": ""})
                            param_material.text = material_value

                            param_season = ET.SubElement(offer_el, "param", {"name": "Сезон", "unit": ""})
                            param_season.text = DEFAULT_FEED_SEASON
                        except Exception as e:
                            logger.warning(f"Error creating offer for product {product.id}, variant {variant_id}, size {size}: {e}")
                            continue
                except Exception as e:
                    logger.warning(f"Error processing color variant for product {product.id}: {e}")
                    continue
        except Exception as e:
            logger.error(f"Error processing product {product.id}: {e}", exc_info=True)
            continue

    try:
        ET.indent(catalog, space="  ", level=0)
        xml_payload = ET.tostring(catalog, encoding="utf-8", xml_declaration=True)

        response = HttpResponse(xml_payload, content_type="application/xml; charset=utf-8")
        response["Content-Disposition"] = 'inline; filename="products_feed.xml"'
        return response
    except Exception as e:
        logger.error(f"Error generating XML feed: {e}", exc_info=True)
        return HttpResponse(
            f'<?xml version="1.0" encoding="UTF-8"?>\n<error>Failed to generate feed: {str(e)}</error>',
            content_type="application/xml; charset=utf-8",
            status=500
        )


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
    brand_page_url = request.build_absolute_uri(reverse("about"))
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
    )
    breadcrumb_items = [
        {"name": "Головна", "url": reverse("home")},
        {"name": "Кастомний принт", "url": reverse("custom_print")},
    ]
    return render(request, 'pages/custom_print.html', {
        'page_title': 'Кастомний принт',
        'custom_print_config': config,
        'breadcrumb_items': breadcrumb_items,
        'faq_items': CUSTOM_PRINT_FAQ_ITEMS,
    })


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
        lead.moderation_status = CustomPrintModerationStatus.APPROVED
        lead.reviewed_at = timezone.now()
        lead.save(update_fields=["moderation_status", "reviewed_at"])
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


# ==================== NEW PROM.UA DYNAMIC FEED (v2) ====================

def _material_for_prom_new(product) -> str:
    """
    Improved material logic for Prom.ua feed.
    """
    lookup_source = " ".join(filter(None, [
        product.category.name if getattr(product, "category", None) else "",
        product.title or "",
        product.slug or ""
    ])).lower()

    if any(token in lookup_source for token in ("худі", "hood", "hudi", "hoodie")):
        return '90% бавовна, 10% поліестер'
    if any(token in lookup_source for token in ("лонг", "long", "longsleeve", "лонгслів")):
        return '95% бамбук, 5% еластан'
    if any(token in lookup_source for token in ("футболк", "tshirt", "t-shirt", "tee")):
        return '95% бавовна, 5% еластан'

    return '95% бавовна, 5% еластан'


# Helper for manual CDATA handling
def _format_description_for_prom(raw_desc: str) -> str:
    """
    Formats description for Prom.ua:
    1. Keeps structure (newlines -> <br>)
    2. Wraps in <p>
    3. Wraps in CDATA markers for post-processing
    """
    if not raw_desc:
        return ""

    # Basic cleaning (strip prices if needed, but keep structure)
    # Removing aggressive whitespace collapsing to preserve user formatting
    cleaned = re.sub(r"(?is)<[^>]*?(?:цена|price|грн|uah|₴)[^>]*?>.*?</[^>]+>", "", raw_desc)
    cleaned = re.sub(r"(?i)цена\s*[:\-]?[^\n<]*", "", cleaned)
    cleaned = re.sub(r"\d+[\s.,]*(?:грн|uah|₴)", "", cleaned, flags=re.IGNORECASE)

    # Convert newlines to HTML
    # Logic: Double newline = new paragraph. Single newline = br.
    paragraphs = re.split(r'\n\s*\n', cleaned.strip())
    html_parts = []

    for p in paragraphs:
        if not p.strip():
            continue
        # Convert internal single newlines to <br>
        p_html = p.replace('\n', '<br>')
        html_parts.append(f"<p>{p_html}</p>")

    final_html = "".join(html_parts)

    # Add signature/styling if needed, e.g. <b> header?
    # User asked for <b> but didn't specify logic.
    # We'll assume the user uses <b> tags in the text or we leave it for now.
    # We won't auto-bold random things to avoid breaking it.

    # CDATA MARKERS for post-processing
    # We use a unique marker that survives XML escaping (mostly)
    # and then replace it in the byte string.
    return f"___CDATA_START___{final_html}___CDATA_END___"


def prom_feed_xml(request):
    """
    Dynamic generation of Prom.ua feed (replacing the static file cron job).
    URL: /prom-feed.xml
    """
    logger = logging.getLogger(__name__)

    try:
        base_url = "https://twocomms.shop"

        products_qs = (
            apply_public_product_order(
                Product.objects
                .filter(status='published', is_dropship_available=True)
                .select_related("category")
                .prefetch_related(
                    "images",
                    "color_variants__images",
                    "color_variants__color"
                )
            )
        )
        products = list(products_qs)

        # Collect relevant categories
        categories_ids = {p.category_id for p in products if p.category_id}
        categories_map = {
            cat.id: cat for cat in Category.objects.filter(id__in=categories_ids)
        }

    except Exception as e:
        logger.error(f"Error fetching products for Prom feed: {e}", exc_info=True)
        return HttpResponse(f"<error>{str(e)}</error>", status=500, content_type="text/xml")

    # XML Structure
    catalog = ET.Element("yml_catalog", {"date": timezone.now().strftime("%Y-%m-%d %H:%M")})
    shop = ET.SubElement(catalog, "shop")
    ET.SubElement(shop, "name").text = "TwoComms"
    ET.SubElement(shop, "company").text = "TwoComms"
    ET.SubElement(shop, "url").text = base_url

    currencies = ET.SubElement(shop, "currencies")
    ET.SubElement(currencies, "currency", {"id": "UAH", "rate": "1"})

    categories_el = ET.SubElement(shop, "categories")
    for cat_id in sorted(categories_ids):
        cat = categories_map.get(cat_id)
        if cat:
            ET.SubElement(categories_el, "category", {"id": str(cat_id)}).text = cat.name

    offers_el = ET.SubElement(shop, "offers")

    # Offer Generation Loop
    for product in products:
        try:
            # Logic to mirror Command.handle
            cat_id = str(product.category.id) if product.category else ""
            group_id = str(product.id)
            material_value = _material_for_prom_new(product)

            # Prepare variants
            color_variants = list(product.color_variants.all())

            final_variants = []

            # --- Variant Preparation Logic ---
            if not color_variants:
                # Fallback for no variants
                # Check is_dropship_available logic from Command
                stock_val = 100 if product.is_dropship_available else 0
                fake_variant = {
                    'color_name': '',
                    'images': [],
                    'variant_id': None,
                    'stock': stock_val
                }
                if product.main_image:
                    fake_variant['images'].append(product.main_image.url)

                for size in resolve_product_sizes(product):
                    final_variants.append({
                        'color_var': fake_variant,
                        'size': size
                    })
            else:
                for cv in color_variants:
                    c_name = cv.color.name if cv.color and cv.color.name else normalize_feed_color(getattr(cv.color, 'primary_hex', ''))

                    cv_images = [img.image.url for img in cv.images.all() if img.image]
                    var_data = {
                        'color_name': c_name,
                        'images': cv_images,
                        'variant_id': cv.id,
                        'stock': cv.stock
                    }
                    for size in resolve_product_sizes(product):
                        final_variants.append({
                            'color_var': var_data,
                            'size': size
                        })

            # --- Write Offers ---
            for item in final_variants:
                var = item['color_var']
                size = item['size']

                offer_id_suffix = f"-{var['variant_id']}" if var['variant_id'] else "-0"
                offer_id = f"{product.id}{offer_id_suffix}-{size}"

                # FORCE AVAILABLE = TRUE as per user request (IDs 100, 101 issue)
                is_available = "true"

                offer_el = ET.SubElement(offers_el, "offer", {
                    "id": offer_id,
                    "available": is_available
                })

                # URL
                product_path = f"/product/{product.slug}/" if product.slug else f"/product/{product.id}/"
                ET.SubElement(offer_el, "url").text = urljoin(base_url, product_path)

                # Price Logic
                selling_price = getattr(product, 'final_price', product.price)
                old_price = product.price

                ET.SubElement(offer_el, "price").text = str(selling_price)
                if selling_price < old_price:
                    ET.SubElement(offer_el, "oldprice").text = str(old_price)

                ET.SubElement(offer_el, "currencyId").text = "UAH"
                ET.SubElement(offer_el, "categoryId").text = cat_id

                # Pictures
                imgs = var['images'][:]
                # Add main image if missing
                if product.main_image and product.main_image.url not in imgs:
                    imgs.append(product.main_image.url)
                # Add other product images
                for p_img in product.images.all():
                    if p_img.image and p_img.image.url not in imgs:
                        imgs.append(p_img.image.url)

                for img_url in imgs[:10]:
                    full_img_url = urljoin(base_url, img_url)
                    ET.SubElement(offer_el, "picture").text = full_img_url

                ET.SubElement(offer_el, "name").text = product.title
                ET.SubElement(offer_el, "vendor").text = "TwoComms"
                ET.SubElement(offer_el, "group_id").text = group_id

                # Description with HTML and CDATA placeholders
                desc = getattr(product, 'full_description', None) or product.description or ""
                if not desc:
                    cat_for_desc = product.category.name.lower() if product.category else 'одяг'
                    desc = f"Якісний {cat_for_desc} з ексклюзивним дизайном від TwoComms"

                formatted_desc = _format_description_for_prom(desc)
                ET.SubElement(offer_el, "description").text = formatted_desc

                # Params
                ET.SubElement(offer_el, "param", {"name": "Розмір"}).text = size
                if var['color_name']:
                    ET.SubElement(offer_el, "param", {"name": "Колір"}).text = var['color_name']
                ET.SubElement(offer_el, "param", {"name": "Матеріал"}).text = material_value

        except Exception as e:
            logger.warning(f"Skipping product {product.id} in prom feed: {e}")
            continue

    try:
        ET.indent(catalog, space="  ", level=0)
        xml_payload = ET.tostring(catalog, encoding="utf-8", xml_declaration=True)

        # POST-PROCESSING FOR CDATA
        # 1. Unescape HTML inside the CDATA block (ET escaped < to &lt;)
        # 2. Replace markers with real CDATA tags

        # Helper to unescape ONLY inside markers
        def unescape_cdata_content(match):
            content = match.group(1)
            # Unescape basic XML entities that ET escaped
            content = content.replace(b"&lt;", b"<").replace(b"&gt;", b">").replace(b"&amp;", b"&")
            return b"<![CDATA[" + content + b"]]>"

        # Using regex on bytes
        cdata_pattern = re.compile(b"___CDATA_START___(.*?)___CDATA_END___", re.DOTALL)
        xml_payload_final = cdata_pattern.sub(unescape_cdata_content, xml_payload)

        return HttpResponse(xml_payload_final, content_type="application/xml; charset=utf-8")
    except Exception as e:
        return HttpResponse(f"<error>{str(e)}</error>", status=500)
