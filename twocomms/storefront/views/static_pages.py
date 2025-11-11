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
    Загружает функцию напрямую из views.py файла.
    """
    import os
    import importlib.util
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        # Получаем путь к views.py (на уровень выше от views/ директории)
        current_dir = os.path.dirname(__file__)  # storefront/views/
        parent_dir = os.path.dirname(current_dir)  # storefront/
        views_py_path = os.path.join(parent_dir, 'views.py')
        
        if not os.path.exists(views_py_path):
            logger.error(f"views.py not found at {views_py_path}")
            raise FileNotFoundError(f"views.py not found at {views_py_path}")
        
        # Динамически загружаем модуль views.py
        spec = importlib.util.spec_from_file_location("storefront.views_legacy_feed", views_py_path)
        if spec is None or spec.loader is None:
            raise ValueError("Could not create spec for views.py")
        
        legacy_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(legacy_module)
        
        if hasattr(legacy_module, 'uaprom_products_feed'):
            return legacy_module.uaprom_products_feed(request)
        else:
            logger.error("uaprom_products_feed function not found in views.py")
            raise AttributeError("uaprom_products_feed function not found in views.py")
            
    except Exception as e:
        logger.error(f"Error loading uaprom_products_feed from views.py: {e}", exc_info=True)
        return HttpResponse(
            f'<?xml version="1.0" encoding="UTF-8"?>\n<error>Feed generation failed: {str(e)}</error>',
            content_type='application/xml',
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
















