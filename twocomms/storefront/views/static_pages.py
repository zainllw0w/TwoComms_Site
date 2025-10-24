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


def cooperation(request):
    """
    Сторінка співпраці з брендом TwoComms.
    """
    return render(request, 'pages/cooperation.html')


def custom_sitemap(request):
    """
    Кастомний sitemap view без проблемних заголовків.
    """
    from django.contrib.sitemaps.views import sitemap
    from storefront.sitemaps import StaticViewSitemap, ProductSitemap, CategorySitemap
    
    sitemaps = {
        'static': StaticViewSitemap,
        'products': ProductSitemap,
        'categories': CategorySitemap,
    }
    
    response = sitemap(request, sitemaps)
    
    # Прибираємо проблемні заголовки для sitemap
    if 'x-robots-tag' in response:
        del response['x-robots-tag']
    if 'x-frame-options' in response:
        del response['x-frame-options']
    
    # Додаємо правильні заголовки для sitemap
    response['Content-Type'] = 'application/xml; charset=utf-8'
    response['Cache-Control'] = 'public, max-age=3600'  # Кешуємо на 1 годину
    
    return response


def delivery_view(request):
    """
    Детальна сторінка доставки та оплати з структурованими даними.
    
    Включає:
    - FAQ про доставку
    - Кроки повернення товару
    - Schema.org HowTo structured data
    """
    import json
    
    # FAQ дані для структурованих даних
    faq_items = [
        {
            "question": "Як довго триває доставка по Україні?",
            "answer": "Доставка по Україні зазвичай триває 1-5 робочих днів залежно від регіону. У великих містах доставка може бути швидшою."
        },
        {
            "question": "Чи можна оплатити товар при отриманні?",
            "answer": "Так, ми пропонуємо накладений платіж для доставки по Україні. Варто врахувати, що при цьому способі оплати додається комісія перевізника."
        },
        {
            "question": "Як відстежити замовлення?",
            "answer": "Після відправки замовлення ви отримаєте номер ТТН на email або в Telegram. Ви можете відстежити посилку на сайті перевізника або через наш Telegram бот."
        },
        {
            "question": "Чи можлива доставка за кордон?",
            "answer": "Так, ми здійснюємо міжнародну доставку через Укрпошту та Нову пошту. Термін доставки 7-21 робочий день залежно від країни."
        },
        {
            "question": "Які способи оплати доступні?",
            "answer": "Ми приймаємо оплату на банківську картку, накладений платіж при отриманні, а також бали за купони для зареєстрованих користувачів."
        }
    ]
    
    return_steps = [
        {
            "title": "Зв'яжіться з нами протягом 14 днів",
            "description": "Напишіть у Telegram або на електронну пошту з номером замовлення та причиною повернення, щоб узгодити деталі."
        },
        {
            "title": "Підготуйте товар",
            "description": "Збережіть бірки, пакування та переконайтеся, що річ не була у використанні. Це пришвидшить перевірку."
        },
        {
            "title": "Надішліть посилку",
            "description": "Відправте повернення Новою поштою або Укрпоштою за погодженими реквізитами й надішліть номер ТТН. Доставка сплачується клієнтом."
        },
        {
            "title": "Отримайте кошти",
            "description": "Після перевірки товару ми повернемо оплату протягом 3 робочих днів тим самим способом, яким було здійснено платіж."
        }
    ]

    return_policy_howto = {
        "@context": "https://schema.org",
        "@type": "HowTo",
        "name": "Як оформити повернення товару у TwoComms",
        "description": "Покрокова інструкція для повернення або обміну товару протягом 14 днів",
        "totalTime": "P14D",
        "supply": [
            {
                "@type": "HowToSupply",
                "name": "Товар з бірками та пакуванням"
            },
            {
                "@type": "HowToSupply",
                "name": "Номер замовлення та контактні дані"
            }
        ],
        "tool": [
            {
                "@type": "HowToTool",
                "name": "Telegram або email для зв'язку"
            },
            {
                "@type": "HowToTool",
                "name": "Сервіс доставки (Нова пошта чи Укрпошта)"
            }
        ],
        "step": [
            {
                "@type": "HowToStep",
                "position": 1,
                "name": return_steps[0]["title"],
                "itemListElement": [
                    {
                        "@type": "HowToDirection",
                        "text": return_steps[0]["description"]
                    }
                ]
            },
            {
                "@type": "HowToStep",
                "position": 2,
                "name": return_steps[1]["title"],
                "itemListElement": [
                    {
                        "@type": "HowToDirection",
                        "text": return_steps[1]["description"]
                    }
                ]
            },
            {
                "@type": "HowToStep",
                "position": 3,
                "name": return_steps[2]["title"],
                "itemListElement": [
                    {
                        "@type": "HowToDirection",
                        "text": return_steps[2]["description"]
                    }
                ]
            },
            {
                "@type": "HowToStep",
                "position": 4,
                "name": return_steps[3]["title"],
                "itemListElement": [
                    {
                        "@type": "HowToDirection",
                        "text": return_steps[3]["description"]
                    }
                ]
            }
        ]
    }

    return render(request, 'pages/delivery.html', {
        'faq_items': faq_items,
        'return_steps': return_steps,
        'return_policy_howto': json.dumps(return_policy_howto, ensure_ascii=False, indent=2)
    })
















