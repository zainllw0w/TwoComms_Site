#!/usr/bin/env python3
"""
Комплексный SEO аудит для TwoComms
Анализирует все аспекты SEO готовности сайта
"""

import requests
import time
import json
import re
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from datetime import datetime
import ssl
import socket
from typing import Dict, List, Tuple, Optional
import sys

class SEOAuditor:
    def __init__(self, base_url: str = "https://twocomms.shop"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'base_url': base_url,
            'technical_seo': {},
            'content_seo': {},
            'performance': {},
            'security': {},
            'mobile': {},
            'structured_data': {},
            'issues': [],
            'recommendations': [],
            'score': 0
        }
    
    def check_http_status(self, url: str) -> Tuple[int, Dict]:
        """Проверяет HTTP статус и заголовки"""
        try:
            response = self.session.head(url, timeout=10, allow_redirects=True)
            return response.status_code, dict(response.headers)
        except Exception as e:
            return 0, {'error': str(e)}
    
    def get_page_content(self, url: str) -> Optional[BeautifulSoup]:
        """Получает содержимое страницы"""
        try:
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                return BeautifulSoup(response.content, 'html.parser')
        except Exception as e:
            print(f"Ошибка получения {url}: {e}")
        return None
    
    def check_technical_seo(self):
        """Проверяет технические аспекты SEO"""
        print("🔍 Проверка технических аспектов SEO...")
        
        tech_checks = {
            'robots_txt': self.check_robots_txt(),
            'sitemap': self.check_sitemap(),
            'canonical_urls': self.check_canonical_urls(),
            'meta_robots': self.check_meta_robots(),
            'url_structure': self.check_url_structure(),
            'redirects': self.check_redirects(),
            'ssl_certificate': self.check_ssl_certificate(),
            'page_speed': self.check_page_speed(),
            'mobile_friendly': self.check_mobile_friendly(),
            'structured_data': self.check_structured_data()
        }
        
        self.results['technical_seo'] = tech_checks
    
    def check_robots_txt(self) -> Dict:
        """Проверяет robots.txt"""
        url = f"{self.base_url}/robots.txt"
        status, headers = self.check_http_status(url)
        
        if status == 200:
            try:
                response = self.session.get(url)
                content = response.text
                
                # Анализируем содержимое
                has_sitemap = 'sitemap' in content.lower()
                has_disallow = 'disallow' in content.lower()
                has_allow = 'allow' in content.lower()
                
                return {
                    'status': 'ok',
                    'accessible': True,
                    'has_sitemap': has_sitemap,
                    'has_disallow': has_disallow,
                    'has_allow': has_allow,
                    'content_length': len(content),
                    'headers': headers
                }
            except Exception as e:
                return {'status': 'error', 'error': str(e)}
        else:
            return {'status': 'error', 'http_status': status}
    
    def check_sitemap(self) -> Dict:
        """Проверяет sitemap.xml"""
        url = f"{self.base_url}/sitemap.xml"
        status, headers = self.check_http_status(url)
        
        if status == 200:
            try:
                response = self.session.get(url)
                content = response.text
                
                # Парсим XML
                soup = BeautifulSoup(content, 'xml')
                urls = soup.find_all('url')
                
                # Проверяем домен в URL
                correct_domain = self.base_url.replace('https://', '') in content
                
                return {
                    'status': 'ok',
                    'accessible': True,
                    'url_count': len(urls),
                    'correct_domain': correct_domain,
                    'content_type': headers.get('content-type', ''),
                    'content_length': len(content)
                }
            except Exception as e:
                return {'status': 'error', 'error': str(e)}
        else:
            return {'status': 'error', 'http_status': status}
    
    def check_canonical_urls(self) -> Dict:
        """Проверяет canonical URLs на главных страницах"""
        pages = ['/', '/catalog/', '/about/', '/contacts/']
        results = {}
        
        for page in pages:
            url = f"{self.base_url}{page}"
            soup = self.get_page_content(url)
            
            if soup:
                canonical = soup.find('link', rel='canonical')
                if canonical:
                    canonical_url = canonical.get('href', '')
                    is_correct = canonical_url.startswith(self.base_url)
                    results[page] = {
                        'has_canonical': True,
                        'url': canonical_url,
                        'correct': is_correct
                    }
                else:
                    results[page] = {'has_canonical': False}
            else:
                results[page] = {'error': 'Не удалось загрузить страницу'}
        
        return results
    
    def check_meta_robots(self) -> Dict:
        """Проверяет мета-теги robots"""
        pages = ['/', '/catalog/', '/about/']
        results = {}
        
        for page in pages:
            url = f"{self.base_url}{page}"
            soup = self.get_page_content(url)
            
            if soup:
                robots_meta = soup.find('meta', attrs={'name': 'robots'})
                if robots_meta:
                    content = robots_meta.get('content', '')
                    results[page] = {
                        'has_robots_meta': True,
                        'content': content,
                        'allows_indexing': 'noindex' not in content.lower()
                    }
                else:
                    results[page] = {'has_robots_meta': False}
        
        return results
    
    def check_url_structure(self) -> Dict:
        """Проверяет структуру URL"""
        # Проверяем несколько URL
        test_urls = [
            f"{self.base_url}/",
            f"{self.base_url}/catalog/",
            f"{self.base_url}/about/",
            f"{self.base_url}/contacts/"
        ]
        
        results = {}
        for url in test_urls:
            status, headers = self.check_http_status(url)
            results[url] = {
                'status_code': status,
                'accessible': status == 200,
                'content_type': headers.get('content-type', ''),
                'content_length': headers.get('content-length', '0')
            }
        
        return results
    
    def check_redirects(self) -> Dict:
        """Проверяет редиректы"""
        # Проверяем HTTP -> HTTPS редирект
        http_url = self.base_url.replace('https://', 'http://')
        status, headers = self.check_http_status(http_url)
        
        # Проверяем www редирект
        www_url = self.base_url.replace('://', '://www.')
        www_status, www_headers = self.check_http_status(www_url)
        
        return {
            'http_to_https': {
                'status': status,
                'redirects_to_https': status in [301, 302, 307, 308]
            },
            'www_redirect': {
                'status': www_status,
                'accessible': www_status == 200
            }
        }
    
    def check_ssl_certificate(self) -> Dict:
        """Проверяет SSL сертификат"""
        try:
            hostname = urlparse(self.base_url).hostname
            context = ssl.create_default_context()
            
            with socket.create_connection((hostname, 443), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                    cert = ssock.getpeercert()
                    
                    return {
                        'status': 'ok',
                        'has_ssl': True,
                        'subject': dict(x[0] for x in cert['subject']),
                        'issuer': dict(x[0] for x in cert['issuer']),
                        'version': cert['version'],
                        'serial_number': cert['serialNumber']
                    }
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
    
    def check_page_speed(self) -> Dict:
        """Проверяет скорость загрузки страниц"""
        pages = ['/', '/catalog/', '/about/']
        results = {}
        
        for page in pages:
            url = f"{self.base_url}{page}"
            start_time = time.time()
            
            try:
                response = self.session.get(url, timeout=10)
                load_time = time.time() - start_time
                
                results[page] = {
                    'load_time': round(load_time, 2),
                    'status_code': response.status_code,
                    'content_length': len(response.content),
                    'fast_load': load_time < 3.0
                }
            except Exception as e:
                results[page] = {'error': str(e)}
        
        return results
    
    def check_mobile_friendly(self) -> Dict:
        """Проверяет мобильную адаптивность"""
        url = f"{self.base_url}/"
        soup = self.get_page_content(url)
        
        if soup:
            viewport = soup.find('meta', attrs={'name': 'viewport'})
            has_viewport = viewport is not None
            
            # Проверяем наличие мобильных CSS
            css_links = soup.find_all('link', rel='stylesheet')
            mobile_css = any('mobile' in link.get('href', '').lower() for link in css_links)
            
            return {
                'has_viewport_meta': has_viewport,
                'viewport_content': viewport.get('content', '') if viewport else '',
                'has_mobile_css': mobile_css,
                'responsive_design': has_viewport
            }
        
        return {'error': 'Не удалось загрузить страницу'}
    
    def check_structured_data(self) -> Dict:
        """Проверяет структурированные данные"""
        url = f"{self.base_url}/"
        soup = self.get_page_content(url)
        
        if soup:
            # Ищем JSON-LD
            json_ld_scripts = soup.find_all('script', type='application/ld+json')
            json_ld_count = len(json_ld_scripts)
            
            # Ищем микроданные
            microdata_items = soup.find_all(attrs={'itemscope': True})
            microdata_count = len(microdata_items)
            
            # Ищем Open Graph
            og_tags = soup.find_all('meta', property=lambda x: x and x.startswith('og:'))
            og_count = len(og_tags)
            
            # Ищем Twitter Cards
            twitter_tags = soup.find_all('meta', attrs={'name': lambda x: x and x.startswith('twitter:')})
            twitter_count = len(twitter_tags)
            
            return {
                'json_ld_count': json_ld_count,
                'microdata_count': microdata_count,
                'open_graph_count': og_count,
                'twitter_cards_count': twitter_count,
                'has_structured_data': json_ld_count > 0 or microdata_count > 0,
                'has_social_meta': og_count > 0 or twitter_count > 0
            }
        
        return {'error': 'Не удалось загрузить страницу'}
    
    def check_content_seo(self):
        """Проверяет контентные аспекты SEO"""
        print("📝 Проверка контентных аспектов SEO...")
        
        content_checks = {
            'meta_tags': self.check_meta_tags(),
            'headings': self.check_headings(),
            'images': self.check_images(),
            'internal_links': self.check_internal_links(),
            'content_quality': self.check_content_quality()
        }
        
        self.results['content_seo'] = content_checks
    
    def check_meta_tags(self) -> Dict:
        """Проверяет мета-теги"""
        url = f"{self.base_url}/"
        soup = self.get_page_content(url)
        
        if soup:
            title = soup.find('title')
            description = soup.find('meta', attrs={'name': 'description'})
            keywords = soup.find('meta', attrs={'name': 'keywords'})
            
            return {
                'has_title': title is not None,
                'title_text': title.get_text() if title else '',
                'title_length': len(title.get_text()) if title else 0,
                'title_optimal': 30 <= len(title.get_text()) <= 60 if title else False,
                'has_description': description is not None,
                'description_text': description.get('content', '') if description else '',
                'description_length': len(description.get('content', '')) if description else 0,
                'description_optimal': 120 <= len(description.get('content', '')) <= 160 if description else False,
                'has_keywords': keywords is not None,
                'keywords_text': keywords.get('content', '') if keywords else ''
            }
        
        return {'error': 'Не удалось загрузить страницу'}
    
    def check_headings(self) -> Dict:
        """Проверяет структуру заголовков"""
        url = f"{self.base_url}/"
        soup = self.get_page_content(url)
        
        if soup:
            h1_tags = soup.find_all('h1')
            h2_tags = soup.find_all('h2')
            h3_tags = soup.find_all('h3')
            
            return {
                'h1_count': len(h1_tags),
                'h1_texts': [h.get_text().strip() for h in h1_tags],
                'h2_count': len(h2_tags),
                'h3_count': len(h3_tags),
                'has_proper_h1': len(h1_tags) == 1,
                'heading_structure_ok': len(h1_tags) == 1 and len(h1_tags) > 0
            }
        
        return {'error': 'Не удалось загрузить страницу'}
    
    def check_images(self) -> Dict:
        """Проверяет изображения"""
        url = f"{self.base_url}/"
        soup = self.get_page_content(url)
        
        if soup:
            images = soup.find_all('img')
            total_images = len(images)
            images_with_alt = len([img for img in images if img.get('alt')])
            images_without_alt = total_images - images_with_alt
            
            return {
                'total_images': total_images,
                'images_with_alt': images_with_alt,
                'images_without_alt': images_without_alt,
                'alt_coverage': round((images_with_alt / total_images * 100), 2) if total_images > 0 else 0,
                'all_images_have_alt': images_without_alt == 0
            }
        
        return {'error': 'Не удалось загрузить страницу'}
    
    def check_internal_links(self) -> Dict:
        """Проверяет внутренние ссылки"""
        url = f"{self.base_url}/"
        soup = self.get_page_content(url)
        
        if soup:
            links = soup.find_all('a', href=True)
            internal_links = []
            external_links = []
            
            for link in links:
                href = link.get('href')
                if href.startswith('/') or self.base_url in href:
                    internal_links.append(href)
                elif href.startswith('http'):
                    external_links.append(href)
            
            return {
                'total_links': len(links),
                'internal_links': len(internal_links),
                'external_links': len(external_links),
                'internal_link_ratio': round((len(internal_links) / len(links) * 100), 2) if links else 0
            }
        
        return {'error': 'Не удалось загрузить страницу'}
    
    def check_content_quality(self) -> Dict:
        """Проверяет качество контента"""
        url = f"{self.base_url}/"
        soup = self.get_page_content(url)
        
        if soup:
            # Убираем скрипты и стили
            for script in soup(["script", "style"]):
                script.decompose()
            
            text = soup.get_text()
            word_count = len(text.split())
            
            # Проверяем уникальность контента
            paragraphs = soup.find_all('p')
            paragraph_count = len(paragraphs)
            
            return {
                'word_count': word_count,
                'paragraph_count': paragraph_count,
                'has_substantial_content': word_count > 300,
                'content_density_ok': word_count > 100
            }
        
        return {'error': 'Не удалось загрузить страницу'}
    
    def calculate_seo_score(self):
        """Вычисляет общий SEO балл"""
        score = 0
        max_score = 100
        
        # Технические аспекты (40 баллов)
        tech_score = 0
        tech_max = 40
        
        if self.results['technical_seo'].get('robots_txt', {}).get('accessible'):
            tech_score += 5
        if self.results['technical_seo'].get('sitemap', {}).get('accessible'):
            tech_score += 5
        if self.results['technical_seo'].get('ssl_certificate', {}).get('has_ssl'):
            tech_score += 5
        if self.results['technical_seo'].get('mobile_friendly', {}).get('responsive_design'):
            tech_score += 5
        if self.results['technical_seo'].get('structured_data', {}).get('has_structured_data'):
            tech_score += 5
        if self.results['technical_seo'].get('canonical_urls', {}).get('/', {}).get('has_canonical'):
            tech_score += 5
        if self.results['technical_seo'].get('meta_robots', {}).get('/', {}).get('allows_indexing'):
            tech_score += 5
        if self.results['technical_seo'].get('page_speed', {}).get('/', {}).get('fast_load'):
            tech_score += 5
        
        # Контентные аспекты (35 баллов)
        content_score = 0
        content_max = 35
        
        meta_tags = self.results['content_seo'].get('meta_tags', {})
        if meta_tags.get('has_title') and meta_tags.get('title_optimal'):
            content_score += 8
        if meta_tags.get('has_description') and meta_tags.get('description_optimal'):
            content_score += 8
        if self.results['content_seo'].get('headings', {}).get('has_proper_h1'):
            content_score += 5
        if self.results['content_seo'].get('images', {}).get('all_images_have_alt'):
            content_score += 7
        if self.results['content_seo'].get('content_quality', {}).get('has_substantial_content'):
            content_score += 7
        
        # Производительность (25 баллов)
        perf_score = 0
        perf_max = 25
        
        page_speed = self.results['technical_seo'].get('page_speed', {})
        for page in ['/', '/catalog/', '/about/']:
            if page_speed.get(page, {}).get('fast_load'):
                perf_score += 8
        
        total_score = tech_score + content_score + perf_score
        self.results['score'] = round((total_score / (tech_max + content_max + perf_max)) * 100, 1)
        
        # Определяем уровень
        if self.results['score'] >= 90:
            level = "Отлично"
        elif self.results['score'] >= 80:
            level = "Хорошо"
        elif self.results['score'] >= 70:
            level = "Удовлетворительно"
        elif self.results['score'] >= 60:
            level = "Требует улучшения"
        else:
            level = "Критично"
        
        self.results['level'] = level
    
    def generate_recommendations(self):
        """Генерирует рекомендации по улучшению"""
        recommendations = []
        
        # Проверяем robots.txt
        if not self.results['technical_seo'].get('robots_txt', {}).get('accessible'):
            recommendations.append("🔧 Создайте файл robots.txt в корне сайта")
        
        # Проверяем sitemap
        sitemap = self.results['technical_seo'].get('sitemap', {})
        if not sitemap.get('accessible'):
            recommendations.append("🗺️ Создайте sitemap.xml для лучшей индексации")
        elif not sitemap.get('correct_domain'):
            recommendations.append("🌐 Исправьте домен в sitemap.xml (сейчас example.com)")
        
        # Проверяем мета-теги
        meta_tags = self.results['content_seo'].get('meta_tags', {})
        if not meta_tags.get('has_title'):
            recommendations.append("📝 Добавьте тег <title> на главную страницу")
        elif not meta_tags.get('title_optimal'):
            recommendations.append("📏 Оптимизируйте длину title (30-60 символов)")
        
        if not meta_tags.get('has_description'):
            recommendations.append("📄 Добавьте мета-описание на главную страницу")
        elif not meta_tags.get('description_optimal'):
            recommendations.append("📏 Оптимизируйте длину description (120-160 символов)")
        
        # Проверяем изображения
        images = self.results['content_seo'].get('images', {})
        if not images.get('all_images_have_alt'):
            recommendations.append("🖼️ Добавьте alt-атрибуты ко всем изображениям")
        
        # Проверяем заголовки
        headings = self.results['content_seo'].get('headings', {})
        if not headings.get('has_proper_h1'):
            recommendations.append("📋 Добавьте один тег H1 на главную страницу")
        
        # Проверяем мобильную адаптивность
        if not self.results['technical_seo'].get('mobile_friendly', {}).get('responsive_design'):
            recommendations.append("📱 Добавьте viewport meta-тег для мобильной адаптивности")
        
        # Проверяем скорость
        page_speed = self.results['technical_seo'].get('page_speed', {})
        slow_pages = [page for page, data in page_speed.items() if not data.get('fast_load', True)]
        if slow_pages:
            recommendations.append(f"⚡ Оптимизируйте скорость загрузки страниц: {', '.join(slow_pages)}")
        
        self.results['recommendations'] = recommendations
    
    def run_full_audit(self):
        """Запускает полный SEO аудит"""
        print("🚀 Запуск комплексного SEO аудита для TwoComms...")
        print("=" * 60)
        
        # Технические проверки
        self.check_technical_seo()
        
        # Контентные проверки
        self.check_content_seo()
        
        # Вычисляем балл
        self.calculate_seo_score()
        
        # Генерируем рекомендации
        self.generate_recommendations()
        
        print("✅ Аудит завершен!")
        return self.results
    
    def save_report(self, filename: str = None):
        """Сохраняет отчет в файл"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"seo_audit_report_{timestamp}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)
        
        print(f"📊 Отчет сохранен в файл: {filename}")
        return filename
    
    def print_summary(self):
        """Выводит краткую сводку"""
        print("\n" + "=" * 60)
        print("📊 СВОДКА SEO АУДИТА")
        print("=" * 60)
        print(f"🌐 Сайт: {self.results['base_url']}")
        print(f"📅 Дата: {self.results['timestamp']}")
        print(f"🎯 Общий балл: {self.results['score']}/100 ({self.results['level']})")
        
        print(f"\n🔧 Технические аспекты:")
        tech = self.results['technical_seo']
        print(f"  • Robots.txt: {'✅' if tech.get('robots_txt', {}).get('accessible') else '❌'}")
        print(f"  • Sitemap: {'✅' if tech.get('sitemap', {}).get('accessible') else '❌'}")
        print(f"  • SSL: {'✅' if tech.get('ssl_certificate', {}).get('has_ssl') else '❌'}")
        print(f"  • Мобильная версия: {'✅' if tech.get('mobile_friendly', {}).get('responsive_design') else '❌'}")
        print(f"  • Структурированные данные: {'✅' if tech.get('structured_data', {}).get('has_structured_data') else '❌'}")
        
        print(f"\n📝 Контентные аспекты:")
        content = self.results['content_seo']
        print(f"  • Title: {'✅' if content.get('meta_tags', {}).get('has_title') else '❌'}")
        print(f"  • Description: {'✅' if content.get('meta_tags', {}).get('has_description') else '❌'}")
        print(f"  • H1 заголовок: {'✅' if content.get('headings', {}).get('has_proper_h1') else '❌'}")
        print(f"  • Alt-атрибуты: {'✅' if content.get('images', {}).get('all_images_have_alt') else '❌'}")
        
        if self.results['recommendations']:
            print(f"\n💡 Рекомендации ({len(self.results['recommendations'])}):")
            for i, rec in enumerate(self.results['recommendations'], 1):
                print(f"  {i}. {rec}")


def main():
    """Главная функция"""
    print("🔍 Комплексный SEO аудит TwoComms")
    print("=" * 60)
    
    auditor = SEOAuditor()
    results = auditor.run_full_audit()
    
    # Выводим сводку
    auditor.print_summary()
    
    # Сохраняем отчет
    report_file = auditor.save_report()
    
    print(f"\n🎉 Аудит завершен! Отчет сохранен в {report_file}")
    
    return results


if __name__ == "__main__":
    main()
