#!/usr/bin/env python
"""
Скрипт для автоматического измерения метрик производительности.

Использование:
    python measure_performance_metrics.py [--page PAGE] [--output OUTPUT]

Примеры:
    python measure_performance_metrics.py --page /catalog/
    python measure_performance_metrics.py --output metrics.json
"""

import os
import sys
import django
import json
import time
from datetime import datetime
from decimal import Decimal

# Настройка Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'twocomms.settings')
django.setup()

from django.db import connection
from django.test import Client
from django.urls import reverse
from storefront.performance import DatabaseOptimizer, PerformanceMonitor
from storefront.models import Product, Category


def measure_page_performance(url_path, client):
    """
    Измеряет производительность страницы.
    
    Args:
        url_path (str): Путь к странице (например, '/catalog/')
        client: Django test client
        
    Returns:
        dict: Метрики производительности
    """
    # Сброс счетчика запросов
    connection.queries_log.clear()
    
    monitor = PerformanceMonitor()
    
    # Запрос страницы
    start_time = time.time()
    response = client.get(url_path)
    end_time = time.time()
    
    # Получение метрик
    metrics = monitor.get_metrics()
    query_performance = DatabaseOptimizer.analyze_query_performance()
    
    return {
        'url': url_path,
        'status_code': response.status_code,
        'execution_time': end_time - start_time,
        'queries_count': metrics['queries_count'],
        'queries_total_time': query_performance['total_time'],
        'queries_average_time': query_performance['average_time'],
        'slow_queries': query_performance['slow_queries'],
        'response_size': len(response.content),
        'timestamp': datetime.now().isoformat(),
    }


def measure_catalog_performance(client):
    """Измеряет производительность каталога."""
    return measure_page_performance('/catalog/', client)


def measure_cart_performance(client):
    """Измеряет производительность корзины."""
    return measure_page_performance('/cart/', client)


def measure_home_performance(client):
    """Измеряет производительность главной страницы."""
    return measure_page_performance('/', client)


def measure_product_detail_performance(client, product_slug=None):
    """
    Измеряет производительность страницы товара.
    
    Args:
        client: Django test client
        product_slug (str, optional): Slug товара. Если не указан, берется первый товар.
    """
    if not product_slug:
        product = Product.objects.filter(status='published').first()
        if not product:
            return None
        product_slug = product.slug
    
    return measure_page_performance(f'/product/{product_slug}/', client)


def analyze_n_plus_one_queries(metrics_list):
    """
    Анализирует N+1 запросы в метриках.
    
    Args:
        metrics_list (list): Список метрик
        
    Returns:
        dict: Анализ N+1 запросов
    """
    analysis = {
        'total_pages': len(metrics_list),
        'total_queries': sum(m['queries_count'] for m in metrics_list),
        'average_queries_per_page': sum(m['queries_count'] for m in metrics_list) / len(metrics_list) if metrics_list else 0,
        'pages_with_many_queries': [m for m in metrics_list if m['queries_count'] > 20],
        'slow_pages': [m for m in metrics_list if m['execution_time'] > 1.0],
    }
    
    return analysis


def generate_report(metrics_list, output_file=None):
    """
    Генерирует отчет о производительности.
    
    Args:
        metrics_list (list): Список метрик
        output_file (str, optional): Путь к файлу для сохранения отчета
    """
    report = {
        'timestamp': datetime.now().isoformat(),
        'summary': {
            'total_pages_tested': len(metrics_list),
            'average_execution_time': sum(m['execution_time'] for m in metrics_list) / len(metrics_list) if metrics_list else 0,
            'average_queries_per_page': sum(m['queries_count'] for m in metrics_list) / len(metrics_list) if metrics_list else 0,
            'total_queries': sum(m['queries_count'] for m in metrics_list),
            'total_slow_queries': sum(len(m['slow_queries']) for m in metrics_list),
        },
        'pages': metrics_list,
        'n_plus_one_analysis': analyze_n_plus_one_queries(metrics_list),
    }
    
    # Вывод в консоль
    print("\n" + "="*80)
    print("ОТЧЕТ О ПРОИЗВОДИТЕЛЬНОСТИ")
    print("="*80)
    print(f"\nВремя создания: {report['timestamp']}")
    print(f"\nСводка:")
    print(f"  - Протестировано страниц: {report['summary']['total_pages_tested']}")
    print(f"  - Среднее время выполнения: {report['summary']['average_execution_time']:.3f}s")
    print(f"  - Среднее количество запросов на страницу: {report['summary']['average_queries_per_page']:.1f}")
    print(f"  - Всего запросов: {report['summary']['total_queries']}")
    print(f"  - Медленных запросов: {report['summary']['total_slow_queries']}")
    
    print(f"\nДетали по страницам:")
    for page in metrics_list:
        print(f"\n  {page['url']}:")
        print(f"    - Время выполнения: {page['execution_time']:.3f}s")
        print(f"    - Запросов к БД: {page['queries_count']}")
        print(f"    - Общее время запросов: {page['queries_total_time']:.3f}s")
        print(f"    - Среднее время запроса: {page['queries_average_time']:.3f}s")
        if page['slow_queries']:
            print(f"    - Медленных запросов: {len(page['slow_queries'])}")
    
    n_plus_one = report['n_plus_one_analysis']
    print(f"\nАнализ N+1 запросов:")
    print(f"  - Страниц с >20 запросами: {len(n_plus_one['pages_with_many_queries'])}")
    print(f"  - Медленных страниц (>1s): {len(n_plus_one['slow_pages'])}")
    
    if n_plus_one['pages_with_many_queries']:
        print(f"\n  Страницы с большим количеством запросов:")
        for page in n_plus_one['pages_with_many_queries']:
            print(f"    - {page['url']}: {page['queries_count']} запросов")
    
    if n_plus_one['slow_pages']:
        print(f"\n  Медленные страницы:")
        for page in n_plus_one['slow_pages']:
            print(f"    - {page['url']}: {page['execution_time']:.3f}s")
    
    print("\n" + "="*80)
    
    # Сохранение в файл
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)
        print(f"\nОтчет сохранен в: {output_file}")
    
    return report


def main():
    """Главная функция."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Измерение метрик производительности')
    parser.add_argument('--page', type=str, help='Путь к странице для тестирования (например, /catalog/)')
    parser.add_argument('--output', type=str, help='Путь к файлу для сохранения отчета (JSON)')
    parser.add_argument('--all', action='store_true', help='Протестировать все основные страницы')
    
    args = parser.parse_args()
    
    client = Client()
    metrics_list = []
    
    if args.page:
        # Тестирование одной страницы
        metrics = measure_page_performance(args.page, client)
        metrics_list.append(metrics)
    elif args.all:
        # Тестирование всех основных страниц
        print("Тестирование всех основных страниц...")
        metrics_list.append(measure_home_performance(client))
        metrics_list.append(measure_catalog_performance(client))
        metrics_list.append(measure_cart_performance(client))
        product_metrics = measure_product_detail_performance(client)
        if product_metrics:
            metrics_list.append(product_metrics)
    else:
        # По умолчанию тестируем главную страницу
        print("Тестирование главной страницы...")
        metrics_list.append(measure_home_performance(client))
    
    # Генерация отчета
    output_file = args.output or 'performance_metrics_report.json'
    generate_report(metrics_list, output_file)


if __name__ == '__main__':
    main()

