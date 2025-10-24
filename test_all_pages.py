#!/usr/bin/env python
"""
Тестирование всех страниц сайта на наличие ошибок.
Проверяет каждый endpoint и собирает статистику.
"""
import requests
import json
from urllib.parse import urljoin
from datetime import datetime

# Базовый URL сайта
BASE_URL = "https://twocomms.opillia.store"

# Список всех endpoints для проверки
ENDPOINTS = {
    # Критические страницы
    "Главная": "/",
    "Каталог": "/catalog/",
    "Корзина": "/cart/",
    "Оформление заказа": "/checkout/",
    "Поиск": "/search/",
    
    # Статические страницы
    "О нас": "/about/",
    "Контакты": "/contacts/",
    "Доставка": "/delivery/",
    "Сотрудничество": "/cooperation/",
    "Оптовые цены": "/wholesale/",
    "Прайс-лист": "/pricelist/",
    
    # Авторизация
    "Вход": "/login/",
    "Регистрация": "/register/",
    
    # Админ панель (без авторизации ожидаем редирект)
    "Админ панель": "/admin-panel/",
    
    # API endpoints (AJAX)
    "Cart Summary API": "/cart/summary/",
    "Cart Mini API": "/cart/mini/",
    "Favorites Count API": "/favorites/count/",
    
    # Feeds
    "Robots.txt": "/robots.txt",
    "Sitemap": "/sitemap.xml",
    "Google Merchant Feed": "/google_merchant_feed.xml",
    "Products Feed": "/products_feed.xml",
    
    # Избранное
    "Избранное": "/favorites/",
    
    # Wholesale
    "Wholesale Order Form": "/wholesale/order-form/",
}

def test_endpoint(name, path):
    """
    Тестирует один endpoint.
    
    Args:
        name: Название страницы
        path: Путь к странице
        
    Returns:
        dict: Результат проверки
    """
    url = urljoin(BASE_URL, path)
    result = {
        "name": name,
        "url": url,
        "status": None,
        "error": None,
        "response_time": None,
    }
    
    try:
        start_time = datetime.now()
        response = requests.get(
            url,
            timeout=15,
            allow_redirects=True,
            headers={
                'User-Agent': 'Mozilla/5.0 (compatible; SiteChecker/1.0)',
            }
        )
        end_time = datetime.now()
        
        result["status"] = response.status_code
        result["response_time"] = (end_time - start_time).total_seconds()
        
        # Проверяем на internal server error
        if response.status_code == 500:
            result["error"] = "Internal Server Error (500)"
            # Пытаемся получить текст ошибки
            if "text/html" in response.headers.get("content-type", ""):
                if "Traceback" in response.text or "Exception" in response.text:
                    result["error"] += " - Contains Python exception"
        elif response.status_code == 404:
            result["error"] = "Page Not Found (404)"
        elif response.status_code >= 400:
            result["error"] = f"HTTP Error {response.status_code}"
            
    except requests.Timeout:
        result["error"] = "Timeout (>15s)"
    except requests.ConnectionError as e:
        result["error"] = f"Connection Error: {str(e)[:100]}"
    except Exception as e:
        result["error"] = f"Exception: {str(e)[:100]}"
    
    return result

def main():
    """Основная функция тестирования."""
    print("=" * 80)
    print(f"ПРОВЕРКА ВСЕХ СТРАНИЦ САЙТА: {BASE_URL}")
    print(f"Время начала: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    print()
    
    results = []
    errors = []
    
    for name, path in ENDPOINTS.items():
        print(f"Проверяю: {name:<30} {path:<40}", end=" ... ")
        result = test_endpoint(name, path)
        results.append(result)
        
        if result["error"]:
            print(f"❌ {result['error']}")
            errors.append(result)
        elif result["status"] == 200:
            print(f"✅ OK ({result['response_time']:.2f}s)")
        elif result["status"] in [301, 302, 303, 307, 308]:
            print(f"↪️  Redirect {result['status']} ({result['response_time']:.2f}s)")
        else:
            print(f"⚠️  Status {result['status']} ({result['response_time']:.2f}s)")
    
    print()
    print("=" * 80)
    print("СВОДКА")
    print("=" * 80)
    
    total = len(results)
    ok = len([r for r in results if r["status"] == 200 and not r["error"]])
    redirects = len([r for r in results if r["status"] in [301, 302, 303, 307, 308]])
    errors_count = len(errors)
    
    print(f"Всего проверено: {total}")
    print(f"✅ Успешно (200): {ok}")
    print(f"↪️  Редиректы: {redirects}")
    print(f"❌ Ошибки: {errors_count}")
    print()
    
    if errors:
        print("=" * 80)
        print("НАЙДЕННЫЕ ОШИБКИ")
        print("=" * 80)
        for error in errors:
            print(f"❌ {error['name']}")
            print(f"   URL: {error['url']}")
            print(f"   Ошибка: {error['error']}")
            print()
    
    # Сохраняем результаты в JSON
    output_file = "page_check_results.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "base_url": BASE_URL,
            "total": total,
            "ok": ok,
            "redirects": redirects,
            "errors_count": errors_count,
            "results": results,
        }, f, ensure_ascii=False, indent=2)
    
    print(f"Результаты сохранены в: {output_file}")
    print()
    
    return errors_count == 0

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)

