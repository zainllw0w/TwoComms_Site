#!/usr/bin/env python
"""
Ежедневный мониторинг производительности
Запускать через cron: 0 9 * * * /path/to/python /path/to/monitor_performance_daily.py
"""

import os
import sys
import django
import json
from datetime import datetime
from pathlib import Path

# Настройка Django
sys.path.append(str(Path(__file__).parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'twocomms.settings')
django.setup()

from django.test import Client
from django.db import connection
from django.core.cache import cache
import requests

def measure_page_performance(url):
    """Измеряет производительность страницы"""
    client = Client()
    
    # Сброс счетчика запросов
    initial_queries = len(connection.queries)
    
    # Запрос страницы
    start_time = datetime.now()
    response = client.get(url)
    end_time = datetime.now()
    
    # Подсчет запросов
    query_count = len(connection.queries) - initial_queries
    query_time = sum(float(q['time']) for q in connection.queries[-query_count:])
    
    response_time = (end_time - start_time).total_seconds() * 1000
    
    return {
        'url': url,
        'status_code': response.status_code,
        'response_time_ms': response_time,
        'query_count': query_count,
        'query_time_ms': query_time * 1000,
        'response_size_kb': len(response.content) / 1024,
    }

def check_core_web_vitals():
    """Проверяет Core Web Vitals через PageSpeed Insights API"""
    # Требуется API ключ от Google
    api_key = os.environ.get('PAGESPEED_API_KEY')
    if not api_key:
        return None
    
    url = 'https://twocomms.com.ua'
    api_url = f'https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url={url}&key={api_key}'
    
    try:
        response = requests.get(api_url, timeout=30)
        data = response.json()
        
        lighthouse = data.get('lighthouseResult', {})
        metrics = lighthouse.get('audits', {}).get('metrics', {}).get('details', {}).get('items', [{}])[0]
        
        return {
            'fcp': metrics.get('firstContentfulPaint', 0) / 1000,
            'lcp': metrics.get('largestContentfulPaint', 0) / 1000,
            'tti': metrics.get('interactive', 0) / 1000,
            'cls': metrics.get('cumulativeLayoutShift', 0),
            'fid': metrics.get('maxPotentialFID', 0) / 1000,
            'score': lighthouse.get('categories', {}).get('performance', {}).get('score', 0) * 100,
        }
    except Exception as e:
        print(f"Ошибка при проверке Core Web Vitals: {e}")
        return None

def main():
    """Основная функция"""
    pages = [
        '/',
        '/catalog/',
        '/cart/',
    ]
    
    results = {
        'timestamp': datetime.now().isoformat(),
        'pages': [],
        'core_web_vitals': None,
    }
    
    # Измерение производительности страниц
    for page in pages:
        try:
            metrics = measure_page_performance(page)
            results['pages'].append(metrics)
            print(f"✅ {page}: {metrics['response_time_ms']:.0f}ms, {metrics['query_count']} запросов")
        except Exception as e:
            print(f"❌ Ошибка при измерении {page}: {e}")
            results['pages'].append({'url': page, 'error': str(e)})
    
    # Проверка Core Web Vitals
    cwv = check_core_web_vitals()
    if cwv:
        results['core_web_vitals'] = cwv
        print(f"✅ Core Web Vitals: FCP={cwv['fcp']:.2f}s, LCP={cwv['lcp']:.2f}s, Score={cwv['score']:.0f}")
    
    # Сохранение результатов
    output_dir = Path('performance_monitoring')
    output_dir.mkdir(exist_ok=True)
    
    date_str = datetime.now().strftime('%Y%m%d')
    output_file = output_dir / f'performance_{date_str}.json'
    
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n📊 Результаты сохранены: {output_file}")
    
    # Проверка на критические проблемы
    critical_issues = []
    
    for page in results['pages']:
        if 'error' in page:
            continue
        
        if page['response_time_ms'] > 2000:
            critical_issues.append(f"{page['url']}: медленный ответ ({page['response_time_ms']:.0f}ms)")
        
        if page['query_count'] > 20:
            critical_issues.append(f"{page['url']}: слишком много запросов ({page['query_count']})")
    
    if cwv:
        if cwv['fcp'] > 3.0:
            critical_issues.append(f"FCP критически медленный: {cwv['fcp']:.2f}s")
        if cwv['lcp'] > 4.0:
            critical_issues.append(f"LCP критически медленный: {cwv['lcp']:.2f}s")
        if cwv['cls'] > 0.25:
            critical_issues.append(f"CLS критически высокий: {cwv['cls']:.2f}")
    
    if critical_issues:
        print("\n⚠️  КРИТИЧЕСКИЕ ПРОБЛЕМЫ:")
        for issue in critical_issues:
            print(f"  - {issue}")
        
        # Отправить уведомление (email, Telegram, Slack и т.д.)
        # TODO: Реализовать отправку уведомлений
    
    return 0 if not critical_issues else 1

if __name__ == '__main__':
    sys.exit(main())

