"""
Static Pages views - Статические страницы и служебные файлы.

Содержит views для:
- robots.txt
- sitemap.xml
- Google Merchant Feed
- Prom.ua Feed  
- Статические файлы верификации
- О компании, Контакты, и т.д.
"""

from django.http import HttpResponse, FileResponse, Http404
from django.conf import settings
from django.shortcuts import render
from pathlib import Path


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
    Prom.ua (UA Prom) Product Feed.
    
    Генерирует XML feed для украинского маркетплейса Prom.ua.
    """
    # TODO: Реализовать генерацию Prom.ua Feed
    # Временно импортируем из старого views.py
    from storefront import views as old_views
    if hasattr(old_views, 'uaprom_products_feed'):
        return old_views.uaprom_products_feed(request)
    
    return HttpResponse(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<shop></shop>',
        content_type='application/xml'
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

