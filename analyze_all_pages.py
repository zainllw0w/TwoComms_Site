#!/usr/bin/env python3
"""
Детальный анализ всех найденных страниц
"""
import json
from pathlib import Path
from collections import defaultdict

def analyze_pages():
    # Загрузить результаты краулинга
    with open('artifacts/audit_2025-10-21/crawl-results.json') as f:
        data = json.load(f)
    
    pages = data['pages']
    total = data['total_pages']
    
    print(f"╔══════════════════════════════════════════════════════════════════════╗")
    print(f"║        АНАЛИЗ ВСЕХ СТРАНИЦ TWOCOMMS ({total} страниц)                ║")
    print(f"╚══════════════════════════════════════════════════════════════════════╝\n")
    
    # Статистика по статус-кодам
    by_status = defaultdict(list)
    for page in pages:
        by_status[page.get('status', 'unknown')].append(page['url'])
    
    print("📊 СТАТУС-КОДЫ:")
    for status, urls in sorted(by_status.items()):
        print(f"  {status}: {len(urls)} страниц")
        if status != 200 and len(urls) <= 10:
            for url in urls:
                print(f"    - {url}")
    
    # Статистика по размерам
    print("\n📦 РАЗМЕРЫ СТРАНИЦ:")
    sizes = [p.get('size', 0) for p in pages if 'size' in p]
    if sizes:
        avg_size = sum(sizes) / len(sizes)
        max_size = max(sizes)
        min_size = min(sizes)
        total_size = sum(sizes)
        
        print(f"  Средний размер: {avg_size/1024:.1f} KB")
        print(f"  Минимальный: {min_size/1024:.1f} KB")
        print(f"  Максимальный: {max_size/1024:.1f} KB")
        print(f"  Общий размер: {total_size/1024/1024:.1f} MB")
        
        # Самые большие страницы
        pages_with_size = [(p['url'], p['size']) for p in pages if 'size' in p]
        pages_with_size.sort(key=lambda x: x[1], reverse=True)
        
        print("\n  📊 Топ-10 самых больших страниц:")
        for i, (url, size) in enumerate(pages_with_size[:10], 1):
            print(f"    {i}. {size/1024:.1f} KB - {url}")
    
    # Группировка по типам страниц
    print("\n📂 ТИПЫ СТРАНИЦ:")
    page_types = defaultdict(list)
    
    for page in pages:
        url = page['url']
        if '/product/' in url:
            page_types['Страницы товаров'].append(url)
        elif '/catalog/' in url:
            page_types['Каталог'].append(url)
        elif '/admin' in url or '/login' in url or '/register' in url:
            page_types['Авторизация'].append(url)
        elif '?page=' in url or '/?page=' in url:
            page_types['Пагинация'].append(url)
        elif '/dropshipper/' in url or '/wholesale/' in url:
            page_types['Бизнес (дропшип/опт)'].append(url)
        elif url.endswith('/') and url.count('/') <= 4:
            page_types['Основные страницы'].append(url)
        else:
            page_types['Прочее'].append(url)
    
    for ptype, urls in sorted(page_types.items(), key=lambda x: len(x[1]), reverse=True):
        print(f"  {ptype}: {len(urls)}")
        if len(urls) <= 5:
            for url in urls:
                print(f"    - {url}")
    
    # Headers анализ
    print("\n🔐 АНАЛИЗ SECURITY HEADERS:")
    security_issues = []
    
    for page in pages:
        if page.get('status') == 200 and 'headers' in page:
            headers = page['headers']
            url = page['url']
            
            if 'Strict-Transport-Security' not in headers:
                security_issues.append(f"❌ HSTS отсутствует: {url}")
            if 'X-Content-Type-Options' not in headers:
                security_issues.append(f"❌ X-Content-Type-Options отсутствует: {url}")
            if 'X-Frame-Options' not in headers:
                security_issues.append(f"❌ X-Frame-Options отсутствует: {url}")
    
    if security_issues:
        print(f"  Найдено {len(security_issues)} проблем")
        for issue in security_issues[:10]:
            print(f"  {issue}")
        if len(security_issues) > 10:
            print(f"  ... и ещё {len(security_issues) - 10}")
    else:
        print("  ✅ Все страницы имеют базовые security headers")
    
    # Проблемные страницы
    print("\n⚠️ ПРОБЛЕМНЫЕ СТРАНИЦЫ:")
    errors = [p for p in pages if p.get('status', 200) >= 400 or 'error' in p]
    if errors:
        print(f"  Найдено {len(errors)} проблемных страниц:")
        for page in errors[:20]:
            if 'error' in page:
                print(f"  ❌ {page['url']}: {page['error']}")
            else:
                print(f"  ❌ {page['url']}: HTTP {page['status']}")
    else:
        print("  ✅ Проблемных страниц не найдено")
    
    # Рекомендации
    print("\n💡 РЕКОМЕНДАЦИИ:")
    
    product_pages = len(page_types.get('Страницы товаров', []))
    if product_pages > 50:
        print(f"  ⚠️ {product_pages} страниц товаров - рассмотреть пагинацию/кэширование")
    
    if len(pages_with_size) > 0:
        big_pages = [p for p in pages_with_size if p[1] > 500*1024]
        if big_pages:
            print(f"  ⚠️ {len(big_pages)} страниц >500KB - оптимизировать")
    
    if security_issues:
        print(f"  🔴 {len(security_issues)} проблем безопасности - исправить headers")
    
    print("\n✅ Анализ завершён!")
    
    # Сохранить детальный отчёт
    report = {
        'total_pages': total,
        'by_status': {str(k): len(v) for k, v in by_status.items()},
        'by_type': {k: len(v) for k, v in page_types.items()},
        'avg_size_kb': avg_size/1024 if sizes else 0,
        'total_size_mb': total_size/1024/1024 if sizes else 0,
        'security_issues_count': len(security_issues),
        'errors_count': len(errors)
    }
    
    with open('artifacts/audit_2025-10-21/pages-analysis.json', 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\n📄 Отчёт сохранён: artifacts/audit_2025-10-21/pages-analysis.json")
    
    return report

if __name__ == '__main__':
    analyze_pages()

