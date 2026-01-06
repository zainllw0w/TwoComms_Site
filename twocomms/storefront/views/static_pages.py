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

from django.http import HttpResponse, FileResponse, Http404
from django.conf import settings
from django.shortcuts import render
from pathlib import Path
from django.utils.text import slugify
from django.utils import timezone
from urllib.parse import urljoin
from storefront.models import Product, Category
from storefront.utils.analytics_helpers import FEED_DEFAULT_COLOR, normalize_feed_color
import re
import xml.etree.ElementTree as ET
import logging

# Константы для feed
FEED_SIZE_OPTIONS = ["S", "M", "L", "XL"]
DEFAULT_FEED_SEASON = "Демисезон"

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
    
    if any(token in lookup_source for token in ("худі", "hood", "hudi", "hoodie")):
        return '90% бавовна, 10% поліестер'
    if any(token in lookup_source for token in ("лонг", "long", "longsleeve", "лонгслів")):
        return '95% бамбук, 5% еластан'
    if any(token in lookup_source for token in ("футболк", "tshirt", "t-shirt", "tee")):
        return '95% бавовна, 5% еластан'
        
    return '95% бавовна, 5% еластан'


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
        f"Sitemap: {request.build_absolute_uri('/sitemap.xml')}",
        "",
        "# Disallow admin and internal pages",
        "Disallow: /admin/",
        "Disallow: /accounts/",
        "Disallow: /orders/",
        "Disallow: /cart/",
        "Disallow: /checkout/",
    ]
    
    return HttpResponse("\n".join(lines), content_type="text/plain")


def static_sitemap(request):
    """
    Sitemap.xml endpoint.
    
    Генерирует XML карту сайта для поисковых систем.
    Импортирует реальную функцию из старого views.py.
    """
    # TODO: Реализовать генерацию sitemap
    # Временно редиректим на старую реализацию
    from storefront import views as old_views
    if hasattr(old_views, 'static_sitemap'):
        return old_views.static_sitemap(request)
    
    return HttpResponse(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f'  <url><loc>{request.build_absolute_uri("/")}</loc></url>\n'
        '</urlset>',
        content_type='application/xml'
    )


def google_merchant_feed(request):
    """
    Google Merchant Center Product Feed.
    
    Генерирует XML feed для Google Shopping.
    """
    # TODO: Реализовать генерацию Google Merchant Feed
    # Временно импортируем из старого views.py
    from storefront import views as old_views
    if hasattr(old_views, 'google_merchant_feed'):
        return old_views.google_merchant_feed(request)
    
    return HttpResponse(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<feed xmlns="http://www.w3.org/2005/Atom"></feed>',
        content_type='application/xml'
    )


def uaprom_products_feed(request):
    """
    Генерирует XML feed для Prom.ua / UAPROM.
    Формат: YML (Yandex Market Language)
    
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
            Product.objects
            .filter(status='published')  # Только опубликованные товары
            .select_related("category")
            .prefetch_related(
                "images",
                "color_variants__images",
                "color_variants__color"
            )
            .order_by("-priority", "-id")  # Сначала по приоритету, потом по ID (новые первыми)
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

                    for size in FEED_SIZE_OPTIONS:
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


def about(request):
    """
    Страница "О нас".
    """
    return render(request, 'pages/about.html', {
        'page_title': 'Про нас'
    })


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
    return render(request, 'pages/delivery.html', {
        'page_title': 'Доставка та оплата'
    })


def returns(request):
    """
    Страница "Возврат и обмен".
    """
    return render(request, 'pages/returns.html', {
        'page_title': 'Повернення та обмін'
    })


def privacy_policy(request):
    """
    Страница "Политика конфиденциальности".
    """
    return render(request, 'pages/privacy_policy.html', {
        'page_title': 'Політика конфіденційності'
    })


def terms_of_service(request):
    """
    Страница "Условия использования".
    """
    return render(request, 'pages/terms_of_service.html', {
        'page_title': 'Умови використання'
    })


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
















