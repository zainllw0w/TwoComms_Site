#!/usr/bin/env python3
"""
Упрощенный SEO аудит для TwoComms (без внешних зависимостей)
Анализирует основные аспекты SEO готовности сайта
"""

import requests
import time
import json
import re
from urllib.parse import urljoin, urlparse
from datetime import datetime
import ssl
import socket
from typing import Dict, List, Tuple, Optional

class SimpleSEOAuditor:
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
    
    def get_page_content(self, url: str) -> Optional[str]:
        """Получает содержимое страницы"""
        try:
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                return response.text
        except Exception as e:
            print(f"Ошибка получения {url}: {e}")
        return None
    
    def extract_meta_tags(self, html: str) -> Dict:
        """Извлекает мета-теги из HTML"""
        meta_tags = {}
        
        # Title
        title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
        if title_match:
            meta_tags['title'] = title_match.group(1).strip()
        
        # Description
        desc_match = re.search(r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']', html, re.IGNORECASE)
        if desc_match:
            meta_tags['description'] = desc_match.group(1)
        
        # Keywords
        keywords_match = re.search(r'<meta[^>]*name=["\']keywords["\'][^>]*content=["\']([^"\']*)["\']', html, re.IGNORECASE)
        if keywords_match:
            meta_tags['keywords'] = keywords_match.group(1)
        
        # Robots
        robots_match = re.search(r'<meta[^>]*name=["\']robots["\'][^>]*content=["\']([^"\']*)["\']', html, re.IGNORECASE)
        if robots_match:
            meta_tags['robots'] = robots_match.group(1)
        
        # Canonical
        canonical_match = re.search(r'<link[^>]*rel=["\']canonical["\'][^>]*href=["\']([^"\']*)["\']', html, re.IGNORECASE)
        if canonical_match:
            meta_tags['canonical'] = canonical_match.group(1)
        
        # Viewport
        viewport_match = re.search(r'<meta[^>]*name=["\']viewport["\'][^>]*content=["\']([^"\']*)["\']', html, re.IGNORECASE)
        if viewport_match:
            meta_tags['viewport'] = viewport_match.group(1)
        
        return meta_tags
    
    def extract_structured_data(self, html: str) -> Dict:
        """Извлекает структурированные данные"""
        structured_data = {
            'json_ld_count': 0,
            'open_graph_count': 0,
            'twitter_cards_count': 0,
            'microdata_count': 0
        }
        
        # JSON-LD
        json_ld_matches = re.findall(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html, re.IGNORECASE | re.DOTALL)
        structured_data['json_ld_count'] = len(json_ld_matches)
        
        # Open Graph
        og_matches = re.findall(r'<meta[^>]*property=["\']og:[^"\']*["\']', html, re.IGNORECASE)
        structured_data['open_graph_count'] = len(og_matches)
        
        # Twitter Cards
        twitter_matches = re.findall(r'<meta[^>]*name=["\']twitter:[^"\']*["\']', html, re.IGNORECASE)
        structured_data['twitter_cards_count'] = len(twitter_matches)
        
        # Microdata
        microdata_matches = re.findall(r'itemscope', html, re.IGNORECASE)
        structured_data['microdata_count'] = len(microdata_matches)
        
        return structured_data
    
    def check_technical_seo(self):
        """Проверяет технические аспекты SEO"""
        print("🔍 Проверка технических аспектов SEO...")
        
        tech_checks = {
            'robots_txt': self.check_robots_txt(),
            'sitemap': self.check_sitemap(),
            'ssl_certificate': self.check_ssl_certificate(),
            'redirects': self.check_redirects(),
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
                
                # Подсчитываем URL
                url_matches = re.findall(r'<url>', content)
                url_count = len(url_matches)
                
                # Проверяем домен в URL
                correct_domain = self.base_url.replace('https://', '') in content
                
                return {
                    'status': 'ok',
                    'accessible': True,
                    'url_count': url_count,
                    'correct_domain': correct_domain,
                    'content_type': headers.get('content-type', ''),
                    'content_length': len(content)
                }
            except Exception as e:
                return {'status': 'error', 'error': str(e)}
        else:
            return {'status': 'error', 'http_status': status}
    
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
        html = self.get_page_content(url)
        
        if html:
            meta_tags = self.extract_meta_tags(html)
            has_viewport = 'viewport' in meta_tags
            
            return {
                'has_viewport_meta': has_viewport,
                'viewport_content': meta_tags.get('viewport', ''),
                'responsive_design': has_viewport
            }
        
        return {'error': 'Не удалось загрузить страницу'}
    
    def check_structured_data(self) -> Dict:
        """Проверяет структурированные данные"""
        url = f"{self.base_url}/"
        html = self.get_page_content(url)
        
        if html:
            structured_data = self.extract_structured_data(html)
            
            return {
                **structured_data,
                'has_structured_data': structured_data['json_ld_count'] > 0 or structured_data['microdata_count'] > 0,
                'has_social_meta': structured_data['open_graph_count'] > 0 or structured_data['twitter_cards_count'] > 0
            }
        
        return {'error': 'Не удалось загрузить страницу'}
    
    def check_content_seo(self):
        """Проверяет контентные аспекты SEO"""
        print("📝 Проверка контентных аспектов SEO...")
        
        content_checks = {
            'meta_tags': self.check_meta_tags(),
            'headings': self.check_headings(),
            'images': self.check_images(),
            'content_quality': self.check_content_quality()
        }
        
        self.results['content_seo'] = content_checks
    
    def check_meta_tags(self) -> Dict:
        """Проверяет мета-теги"""
        url = f"{self.base_url}/"
        html = self.get_page_content(url)
        
        if html:
            meta_tags = self.extract_meta_tags(html)
            
            return {
                'has_title': 'title' in meta_tags,
                'title_text': meta_tags.get('title', ''),
                'title_length': len(meta_tags.get('title', '')),
                'title_optimal': 30 <= len(meta_tags.get('title', '')) <= 60,
                'has_description': 'description' in meta_tags,
                'description_text': meta_tags.get('description', ''),
                'description_length': len(meta_tags.get('description', '')),
                'description_optimal': 120 <= len(meta_tags.get('description', '')) <= 160,
                'has_keywords': 'keywords' in meta_tags,
                'keywords_text': meta_tags.get('keywords', ''),
                'has_canonical': 'canonical' in meta_tags,
                'canonical_url': meta_tags.get('canonical', ''),
                'has_robots_meta': 'robots' in meta_tags,
                'robots_content': meta_tags.get('robots', ''),
                'allows_indexing': 'noindex' not in meta_tags.get('robots', '').lower()
            }
        
        return {'error': 'Не удалось загрузить страницу'}
    
    def check_headings(self) -> Dict:
        """Проверяет структуру заголовков"""
        url = f"{self.base_url}/"
        html = self.get_page_content(url)
        
        if html:
            h1_matches = re.findall(r'<h1[^>]*>(.*?)</h1>', html, re.IGNORECASE | re.DOTALL)
            h2_matches = re.findall(r'<h2[^>]*>(.*?)</h2>', html, re.IGNORECASE | re.DOTALL)
            h3_matches = re.findall(r'<h3[^>]*>(.*?)</h3>', html, re.IGNORECASE | re.DOTALL)
            
            return {
                'h1_count': len(h1_matches),
                'h1_texts': [h.strip() for h in h1_matches],
                'h2_count': len(h2_matches),
                'h3_count': len(h3_matches),
                'has_proper_h1': len(h1_matches) == 1,
                'heading_structure_ok': len(h1_matches) == 1 and len(h1_matches) > 0
            }
        
        return {'error': 'Не удалось загрузить страницу'}
    
    def check_images(self) -> Dict:
        """Проверяет изображения"""
        url = f"{self.base_url}/"
        html = self.get_page_content(url)
        
        if html:
            # Находим все img теги
            img_matches = re.findall(r'<img[^>]*>', html, re.IGNORECASE)
            total_images = len(img_matches)
            
            # Подсчитываем изображения с alt
            images_with_alt = 0
            for img in img_matches:
                if 'alt=' in img.lower():
                    images_with_alt += 1
            
            images_without_alt = total_images - images_with_alt
            
            return {
                'total_images': total_images,
                'images_with_alt': images_with_alt,
                'images_without_alt': images_without_alt,
                'alt_coverage': round((images_with_alt / total_images * 100), 2) if total_images > 0 else 0,
                'all_images_have_alt': images_without_alt == 0
            }
        
        return {'error': 'Не удалось загрузить страницу'}
    
    def check_content_quality(self) -> Dict:
        """Проверяет качество контента"""
        url = f"{self.base_url}/"
        html = self.get_page_content(url)
        
        if html:
            # Убираем HTML теги для подсчета слов
            text = re.sub(r'<[^>]+>', ' ', html)
            text = re.sub(r'\s+', ' ', text).strip()
            word_count = len(text.split())
            
            # Подсчитываем параграфы
            paragraph_matches = re.findall(r'<p[^>]*>', html, re.IGNORECASE)
            paragraph_count = len(paragraph_matches)
            
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
        if self.results['content_seo'].get('meta_tags', {}).get('has_canonical'):
            tech_score += 5
        if self.results['content_seo'].get('meta_tags', {}).get('allows_indexing'):
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
    
    auditor = SimpleSEOAuditor()
    results = auditor.run_full_audit()
    
    # Выводим сводку
    auditor.print_summary()
    
    # Сохраняем отчет
    report_file = auditor.save_report()
    
    print(f"\n🎉 Аудит завершен! Отчет сохранен в {report_file}")
    
    return results


if __name__ == "__main__":
    main()
