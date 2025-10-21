#!/usr/bin/env python3
"""
Полный краулинг всех страниц TwoComms сайта
"""
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import json
import time
from collections import defaultdict

BASE_URL = "https://twocomms.shop"
MAX_PAGES = 1000
visited = set()
to_visit = [BASE_URL]
pages_data = []

def is_valid_url(url):
    parsed = urlparse(url)
    return parsed.netloc in ['twocomms.shop', 'www.twocomms.shop']

def crawl_page(url):
    try:
        print(f"Краулинг: {url}")
        response = requests.get(url, timeout=10, headers={
            'User-Agent': 'TwoComms-Audit-Bot/1.0'
        })
        
        data = {
            'url': url,
            'status': response.status_code,
            'size': len(response.content),
            'headers': dict(response.headers),
            'links': []
        }
        
        if response.status_code == 200 and 'text/html' in response.headers.get('Content-Type', ''):
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Найти все ссылки
            for link in soup.find_all('a', href=True):
                full_url = urljoin(url, link['href'])
                if is_valid_url(full_url) and full_url not in visited:
                    data['links'].append(full_url)
                    if full_url not in to_visit:
                        to_visit.append(full_url)
        
        return data
    except Exception as e:
        print(f"Ошибка при краулинге {url}: {e}")
        return {'url': url, 'error': str(e)}

print(f"Начинаю краулинг {BASE_URL}")
print(f"Максимум страниц: {MAX_PAGES}\n")

while to_visit and len(visited) < MAX_PAGES:
    url = to_visit.pop(0)
    if url in visited:
        continue
    
    visited.add(url)
    data = crawl_page(url)
    pages_data.append(data)
    
    # Задержка
    time.sleep(0.5)
    
    if len(visited) % 10 == 0:
        print(f"\nПрогресс: {len(visited)}/{MAX_PAGES} страниц")

# Сохранить результаты
with open('artifacts/audit_2025-10-21/crawl-results.json', 'w', encoding='utf-8') as f:
    json.dump({
        'total_pages': len(visited),
        'pages': pages_data
    }, f, ensure_ascii=False, indent=2)

print(f"\n✅ Краулинг завершён!")
print(f"Всего страниц: {len(visited)}")
print(f"Результаты: artifacts/audit_2025-10-21/crawl-results.json")
