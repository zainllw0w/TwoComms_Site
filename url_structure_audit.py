#!/usr/bin/env python3
"""
Аудит структуры URL и редиректов для TwoComms
"""

import requests
import time
from urllib.parse import urljoin, urlparse
from datetime import datetime
import json

class URLStructureAuditor:
    def __init__(self, base_url: str = "https://twocomms.shop"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'base_url': base_url,
            'url_tests': {},
            'redirect_tests': {},
            'issues': [],
            'recommendations': []
        }
    
    def check_url(self, url: str, expected_status: int = 200) -> dict:
        """Проверяет URL и возвращает детальную информацию"""
        try:
            start_time = time.time()
            response = self.session.head(url, timeout=10, allow_redirects=True)
            load_time = time.time() - start_time
            
            return {
                'url': url,
                'status_code': response.status_code,
                'expected_status': expected_status,
                'is_ok': response.status_code == expected_status,
                'load_time': round(load_time, 3),
                'final_url': response.url,
                'redirected': response.url != url,
                'headers': dict(response.headers),
                'content_type': response.headers.get('content-type', ''),
                'content_length': response.headers.get('content-length', '0')
            }
        except Exception as e:
            return {
                'url': url,
                'status_code': 0,
                'expected_status': expected_status,
                'is_ok': False,
                'error': str(e),
                'load_time': 0
            }
    
    def test_main_pages(self):
        """Тестирует основные страницы"""
        print("🔍 Тестирование основных страниц...")
        
        main_pages = [
            '/',
            '/catalog/',
            '/about/',
            '/contacts/',
            '/cooperation/',
            '/delivery/',
            '/cart/',
            '/login/',
            '/register/',
            '/admin/',
            '/robots.txt',
            '/sitemap.xml',
            '/favicon.ico'
        ]
        
        results = {}
        for page in main_pages:
            url = f"{self.base_url}{page}"
            expected_status = 200 if page not in ['/admin/'] else 302  # admin должен редиректить
            results[page] = self.check_url(url, expected_status)
        
        self.results['url_tests']['main_pages'] = results
    
    def test_redirects(self):
        """Тестирует редиректы"""
        print("🔄 Тестирование редиректов...")
        
        redirect_tests = {
            'http_to_https': {
                'from': self.base_url.replace('https://', 'http://'),
                'expected_status': [200, 301, 302, 307, 308]
            },
            'www_redirect': {
                'from': self.base_url.replace('://', '://www.'),
                'expected_status': [200, 301, 302, 307, 308]
            },
            'trailing_slash': {
                'from': f"{self.base_url}/catalog",  # без слеша
                'expected_status': [200, 301, 302, 307, 308]
            }
        }
        
        results = {}
        for test_name, test_data in redirect_tests.items():
            result = self.check_url(test_data['from'])
            result['expected_statuses'] = test_data['expected_status']
            result['is_expected'] = result['status_code'] in test_data['expected_status']
            results[test_name] = result
        
        self.results['redirect_tests'] = results
    
    def test_product_pages(self):
        """Тестирует страницы товаров"""
        print("🛍️ Тестирование страниц товаров...")
        
        # Получаем список товаров из sitemap
        try:
            sitemap_url = f"{self.base_url}/sitemap.xml"
            response = self.session.get(sitemap_url)
            if response.status_code == 200:
                content = response.text
                # Извлекаем URL товаров
                import re
                product_urls = re.findall(r'<loc>([^<]*product/[^<]*)</loc>', content)
                
                # Тестируем первые 5 товаров
                test_urls = product_urls[:5]
                results = {}
                
                for url in test_urls:
                    if url.startswith('http'):
                        result = self.check_url(url)
                        results[url] = result
                
                self.results['url_tests']['product_pages'] = results
        except Exception as e:
            self.results['url_tests']['product_pages'] = {'error': str(e)}
    
    def test_category_pages(self):
        """Тестирует страницы категорий"""
        print("📂 Тестирование страниц категорий...")
        
        # Получаем список категорий из sitemap
        try:
            sitemap_url = f"{self.base_url}/sitemap.xml"
            response = self.session.get(sitemap_url)
            if response.status_code == 200:
                content = response.text
                # Извлекаем URL категорий
                import re
                category_urls = re.findall(r'<loc>([^<]*catalog/[^<]*)</loc>', content)
                
                # Тестируем все категории
                results = {}
                
                for url in category_urls:
                    if url.startswith('http'):
                        result = self.check_url(url)
                        results[url] = result
                
                self.results['url_tests']['category_pages'] = results
        except Exception as e:
            self.results['url_tests']['category_pages'] = {'error': str(e)}
    
    def analyze_results(self):
        """Анализирует результаты и генерирует рекомендации"""
        print("📊 Анализ результатов...")
        
        issues = []
        recommendations = []
        
        # Анализируем основные страницы
        main_pages = self.results['url_tests'].get('main_pages', {})
        for page, result in main_pages.items():
            if not result.get('is_ok', False):
                issues.append(f"❌ {page}: статус {result.get('status_code', 'error')}")
        
        # Анализируем редиректы
        redirects = self.results['redirect_tests']
        for test_name, result in redirects.items():
            if not result.get('is_expected', False):
                issues.append(f"🔄 {test_name}: неожиданный статус {result.get('status_code', 'error')}")
        
        # Анализируем скорость
        slow_pages = []
        for page, result in main_pages.items():
            if result.get('load_time', 0) > 2.0:
                slow_pages.append(f"{page} ({result.get('load_time', 0)}s)")
        
        if slow_pages:
            issues.append(f"⚡ Медленные страницы: {', '.join(slow_pages)}")
        
        # Генерируем рекомендации
        if any(not result.get('is_ok', False) for result in main_pages.values()):
            recommendations.append("🔧 Исправить недоступные страницы")
        
        if not redirects.get('http_to_https', {}).get('redirected', False):
            recommendations.append("🔄 Настроить принудительный редирект HTTP → HTTPS")
        
        if slow_pages:
            recommendations.append("⚡ Оптимизировать скорость загрузки медленных страниц")
        
        self.results['issues'] = issues
        self.results['recommendations'] = recommendations
    
    def run_audit(self):
        """Запускает полный аудит структуры URL"""
        print("🚀 Запуск аудита структуры URL...")
        print("=" * 60)
        
        self.test_main_pages()
        self.test_redirects()
        self.test_product_pages()
        self.test_category_pages()
        self.analyze_results()
        
        print("✅ Аудит завершен!")
        return self.results
    
    def save_report(self, filename: str = None):
        """Сохраняет отчет в файл"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"url_audit_report_{timestamp}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)
        
        print(f"📊 Отчет сохранен в файл: {filename}")
        return filename
    
    def print_summary(self):
        """Выводит краткую сводку"""
        print("\n" + "=" * 60)
        print("📊 СВОДКА АУДИТА СТРУКТУРЫ URL")
        print("=" * 60)
        
        # Основные страницы
        main_pages = self.results['url_tests'].get('main_pages', {})
        ok_pages = sum(1 for result in main_pages.values() if result.get('is_ok', False))
        total_pages = len(main_pages)
        
        print(f"📄 Основные страницы: {ok_pages}/{total_pages} работают")
        
        # Редиректы
        redirects = self.results['redirect_tests']
        ok_redirects = sum(1 for result in redirects.values() if result.get('is_expected', False))
        total_redirects = len(redirects)
        
        print(f"🔄 Редиректы: {ok_redirects}/{total_redirects} работают правильно")
        
        # Товары
        products = self.results['url_tests'].get('product_pages', {})
        if 'error' not in products:
            ok_products = sum(1 for result in products.values() if result.get('is_ok', False))
            total_products = len(products)
            print(f"🛍️ Товары: {ok_products}/{total_products} доступны")
        
        # Категории
        categories = self.results['url_tests'].get('category_pages', {})
        if 'error' not in categories:
            ok_categories = sum(1 for result in categories.values() if result.get('is_ok', False))
            total_categories = len(categories)
            print(f"📂 Категории: {ok_categories}/{total_categories} доступны")
        
        # Проблемы
        if self.results['issues']:
            print(f"\n⚠️ Проблемы ({len(self.results['issues'])}):")
            for issue in self.results['issues']:
                print(f"  • {issue}")
        
        # Рекомендации
        if self.results['recommendations']:
            print(f"\n💡 Рекомендации ({len(self.results['recommendations'])}):")
            for rec in self.results['recommendations']:
                print(f"  • {rec}")


def main():
    """Главная функция"""
    print("🔍 Аудит структуры URL TwoComms")
    print("=" * 60)
    
    auditor = URLStructureAuditor()
    results = auditor.run_audit()
    
    # Выводим сводку
    auditor.print_summary()
    
    # Сохраняем отчет
    report_file = auditor.save_report()
    
    print(f"\n🎉 Аудит завершен! Отчет сохранен в {report_file}")
    
    return results


if __name__ == "__main__":
    main()
