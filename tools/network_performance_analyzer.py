#!/usr/bin/env python3
"""
Network Performance Analyzer
Анализирует сетевые запросы, API и внешние зависимости
"""

import os
import re
import json
import time
import requests
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Set
from urllib.parse import urlparse
import ssl
import socket

class NetworkPerformanceAnalyzer:
    def __init__(self, project_root: str):
        self.project_root = project_root
        self.analysis_results = {}
        
    def analyze_external_dependencies(self) -> Dict[str, Any]:
        """Анализ внешних зависимостей"""
        dependencies = {
            "cdn_resources": [],
            "external_apis": [],
            "third_party_scripts": [],
            "fonts": [],
            "total_external_requests": 0,
            "blocking_resources": [],
            "optimization_opportunities": []
        }
        
        # Поиск внешних ресурсов в HTML файлах
        templates_dir = os.path.join(self.project_root, "twocomms_django_theme", "templates")
        if os.path.exists(templates_dir):
            for root, dirs, files in os.walk(templates_dir):
                for file in files:
                    if file.endswith('.html'):
                        file_path = os.path.join(root, file)
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        # Поиск CDN ресурсов
                        cdn_patterns = [
                            r'https?://cdn\.jsdelivr\.net[^"\']*',
                            r'https?://cdnjs\.cloudflare\.com[^"\']*',
                            r'https?://unpkg\.com[^"\']*',
                            r'https?://ajax\.googleapis\.com[^"\']*',
                            r'https?://fonts\.googleapis\.com[^"\']*',
                            r'https?://fonts\.gstatic\.com[^"\']*'
                        ]
                        
                        for pattern in cdn_patterns:
                            matches = re.findall(pattern, content)
                            for match in matches:
                                dependencies["cdn_resources"].append({
                                    "url": match,
                                    "file": file_path,
                                    "type": self._get_resource_type(match)
                                })
                        
                        # Поиск внешних API
                        api_patterns = [
                            r'https?://[^"\']*api[^"\']*',
                            r'https?://[^"\']*\.json[^"\']*',
                            r'fetch\s*\(\s*["\']([^"\']+)["\']',
                            r'axios\.[^(]*\(\s*["\']([^"\']+)["\']'
                        ]
                        
                        for pattern in api_patterns:
                            matches = re.findall(pattern, content)
                            for match in matches:
                                if match.startswith('http'):
                                    dependencies["external_apis"].append({
                                        "url": match,
                                        "file": file_path,
                                        "method": "GET"  # По умолчанию
                                    })
                        
                        # Поиск шрифтов
                        font_patterns = [
                            r'@import\s+url\s*\(\s*["\']([^"\']+)["\']',
                            r'<link[^>]*href\s*=\s*["\']([^"\']*font[^"\']*)["\']'
                        ]
                        
                        for pattern in font_patterns:
                            matches = re.findall(pattern, content)
                            for match in matches:
                                if match.startswith('http'):
                                    dependencies["fonts"].append({
                                        "url": match,
                                        "file": file_path
                                    })
        
        # Поиск в JavaScript файлах
        js_files = []
        for root, dirs, files in os.walk(self.project_root):
            for file in files:
                if file.endswith('.js'):
                    js_files.append(os.path.join(root, file))
        
        for js_file in js_files:
            with open(js_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Поиск fetch/axios запросов
            fetch_patterns = [
                r'fetch\s*\(\s*["\']([^"\']+)["\']',
                r'axios\.[^(]*\(\s*["\']([^"\']+)["\']',
                r'XMLHttpRequest.*open\s*\(\s*["\']([^"\']+)["\']'
            ]
            
            for pattern in fetch_patterns:
                matches = re.findall(pattern, content)
                for match in matches:
                    if match.startswith('http'):
                        dependencies["external_apis"].append({
                            "url": match,
                            "file": js_file,
                            "method": "GET"
                        })
        
        # Анализ блокирующих ресурсов
        for resource in dependencies["cdn_resources"]:
            if resource["type"] in ["script", "stylesheet"]:
                dependencies["blocking_resources"].append(resource)
        
        dependencies["total_external_requests"] = (
            len(dependencies["cdn_resources"]) + 
            len(dependencies["external_apis"]) + 
            len(dependencies["fonts"])
        )
        
        return dependencies
    
    def _get_resource_type(self, url: str) -> str:
        """Определение типа ресурса по URL"""
        if '.js' in url:
            return 'script'
        elif '.css' in url:
            return 'stylesheet'
        elif any(ext in url for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
            return 'image'
        elif '.woff' in url or '.ttf' in url or 'font' in url:
            return 'font'
        else:
            return 'other'
    
    def analyze_api_performance(self, base_url: str = "http://localhost:8000") -> Dict[str, Any]:
        """Анализ производительности API"""
        api_stats = {
            "endpoints": [],
            "response_times": {},
            "status_codes": {},
            "performance_issues": [],
            "optimization_recommendations": []
        }
        
        # Список основных эндпоинтов для тестирования
        test_endpoints = [
            "/",
            "/products/",
            "/categories/",
            "/api/products/",
            "/api/categories/",
            "/admin/",
            "/accounts/login/",
            "/accounts/register/"
        ]
        
        for endpoint in test_endpoints:
            try:
                url = base_url + endpoint
                start_time = time.time()
                
                response = requests.get(url, timeout=10, allow_redirects=True)
                
                response_time = time.time() - start_time
                
                endpoint_stats = {
                    "url": url,
                    "status_code": response.status_code,
                    "response_time": round(response_time, 3),
                    "content_length": len(response.content),
                    "headers": dict(response.headers)
                }
                
                api_stats["endpoints"].append(endpoint_stats)
                
                # Анализ производительности
                if response_time > 2.0:
                    api_stats["performance_issues"].append({
                        "endpoint": endpoint,
                        "issue": "slow_response",
                        "response_time": response_time
                    })
                
                if response.status_code >= 400:
                    api_stats["performance_issues"].append({
                        "endpoint": endpoint,
                        "issue": "error_status",
                        "status_code": response.status_code
                    })
                
                # Статистика по кодам ответов
                status_code = str(response.status_code)
                api_stats["status_codes"][status_code] = api_stats["status_codes"].get(status_code, 0) + 1
                
            except requests.exceptions.RequestException as e:
                api_stats["performance_issues"].append({
                    "endpoint": endpoint,
                    "issue": "connection_error",
                    "error": str(e)
                })
        
        # Рекомендации по оптимизации
        slow_endpoints = [ep for ep in api_stats["endpoints"] if ep["response_time"] > 1.0]
        if slow_endpoints:
            api_stats["optimization_recommendations"].append(
                f"Найдено {len(slow_endpoints)} медленных эндпоинтов - требуется оптимизация"
            )
        
        return api_stats
    
    def analyze_ssl_security(self, domain: str = "localhost") -> Dict[str, Any]:
        """Анализ SSL безопасности"""
        ssl_stats = {
            "ssl_enabled": False,
            "certificate_info": {},
            "security_issues": [],
            "recommendations": []
        }
        
        try:
            # Проверка SSL сертификата
            context = ssl.create_default_context()
            with socket.create_connection((domain, 443), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=domain) as ssock:
                    ssl_stats["ssl_enabled"] = True
                    cert = ssock.getpeercert()
                    
                    ssl_stats["certificate_info"] = {
                        "subject": dict(x[0] for x in cert['subject']),
                        "issuer": dict(x[0] for x in cert['issuer']),
                        "version": cert['version'],
                        "serial_number": cert['serialNumber'],
                        "not_before": cert['notBefore'],
                        "not_after": cert['notAfter']
                    }
                    
                    # Проверка срока действия
                    from datetime import datetime
                    not_after = datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y %Z')
                    days_until_expiry = (not_after - datetime.now()).days
                    
                    if days_until_expiry < 30:
                        ssl_stats["security_issues"].append({
                            "issue": "certificate_expiring_soon",
                            "days_until_expiry": days_until_expiry
                        })
                    
                    # Проверка версии SSL
                    ssl_version = ssock.version()
                    if ssl_version in ['TLSv1', 'TLSv1.1']:
                        ssl_stats["security_issues"].append({
                            "issue": "outdated_ssl_version",
                            "version": ssl_version
                        })
        
        except Exception as e:
            ssl_stats["security_issues"].append({
                "issue": "ssl_connection_failed",
                "error": str(e)
            })
        
        return ssl_stats
    
    def analyze_caching_headers(self, base_url: str = "http://localhost:8000") -> Dict[str, Any]:
        """Анализ заголовков кэширования"""
        caching_stats = {
            "endpoints": [],
            "caching_issues": [],
            "recommendations": []
        }
        
        test_endpoints = [
            "/",
            "/static/css/styles.css",
            "/static/js/main.js",
            "/media/products/",
            "/api/products/"
        ]
        
        for endpoint in test_endpoints:
            try:
                url = base_url + endpoint
                response = requests.head(url, timeout=5)
                
                headers = dict(response.headers)
                caching_info = {
                    "url": url,
                    "cache_control": headers.get('Cache-Control', 'Not set'),
                    "etag": headers.get('ETag', 'Not set'),
                    "last_modified": headers.get('Last-Modified', 'Not set'),
                    "expires": headers.get('Expires', 'Not set')
                }
                
                caching_stats["endpoints"].append(caching_info)
                
                # Анализ проблем с кэшированием
                if 'Cache-Control' not in headers:
                    caching_stats["caching_issues"].append({
                        "endpoint": endpoint,
                        "issue": "no_cache_control"
                    })
                
                if endpoint.startswith('/static/') and 'no-cache' in headers.get('Cache-Control', ''):
                    caching_stats["caching_issues"].append({
                        "endpoint": endpoint,
                        "issue": "static_files_not_cached"
                    })
                
                if endpoint.startswith('/api/') and 'no-cache' not in headers.get('Cache-Control', ''):
                    caching_stats["caching_issues"].append({
                        "endpoint": endpoint,
                        "issue": "api_endpoints_cached"
                    })
        
            except requests.exceptions.RequestException as e:
                caching_stats["caching_issues"].append({
                    "endpoint": endpoint,
                    "issue": "caching_test_failed",
                    "error": str(e)
                })
        
        return caching_stats
    
    def analyze_compression(self, base_url: str = "http://localhost:8000") -> Dict[str, Any]:
        """Анализ сжатия"""
        compression_stats = {
            "endpoints": [],
            "compression_issues": [],
            "recommendations": []
        }
        
        test_endpoints = [
            "/",
            "/static/css/styles.css",
            "/static/js/main.js",
            "/api/products/"
        ]
        
        for endpoint in test_endpoints:
            try:
                url = base_url + endpoint
                
                # Запрос без сжатия
                response_normal = requests.get(url, timeout=5)
                normal_size = len(response_normal.content)
                
                # Запрос с gzip
                headers = {'Accept-Encoding': 'gzip, deflate'}
                response_compressed = requests.get(url, headers=headers, timeout=5)
                compressed_size = len(response_compressed.content)
                
                compression_ratio = (normal_size - compressed_size) / normal_size if normal_size > 0 else 0
                
                compression_info = {
                    "url": url,
                    "normal_size": normal_size,
                    "compressed_size": compressed_size,
                    "compression_ratio": round(compression_ratio, 3),
                    "compression_savings_percent": round(compression_ratio * 100, 1)
                }
                
                compression_stats["endpoints"].append(compression_info)
                
                # Анализ проблем со сжатием
                if compression_ratio < 0.1 and normal_size > 1024:  # < 10% сжатия для файлов > 1KB
                    compression_stats["compression_issues"].append({
                        "endpoint": endpoint,
                        "issue": "poor_compression",
                        "ratio": compression_ratio
                    })
                
            except requests.exceptions.RequestException as e:
                compression_stats["compression_issues"].append({
                    "endpoint": endpoint,
                    "issue": "compression_test_failed",
                    "error": str(e)
                })
        
        return compression_stats
    
    def run_full_analysis(self, base_url: str = "http://localhost:8000") -> Dict[str, Any]:
        """Запуск полного анализа"""
        start_time = time.time()
        
        self.analysis_results = {
            "external_dependencies": self.analyze_external_dependencies(),
            "api_performance": self.analyze_api_performance(base_url),
            "ssl_security": self.analyze_ssl_security(),
            "caching_headers": self.analyze_caching_headers(base_url),
            "compression": self.analyze_compression(base_url),
            "analysis_time": time.time() - start_time
        }
        
        return self.analysis_results
    
    def generate_recommendations(self) -> List[str]:
        """Генерация рекомендаций по оптимизации"""
        recommendations = []
        
        # Рекомендации по внешним зависимостям
        deps = self.analysis_results.get("external_dependencies", {})
        if deps.get("total_external_requests", 0) > 10:
            recommendations.append(f"Слишком много внешних запросов ({deps['total_external_requests']}) - рассмотрите объединение ресурсов")
        
        blocking_resources = len(deps.get("blocking_resources", []))
        if blocking_resources > 5:
            recommendations.append(f"Слишком много блокирующих ресурсов ({blocking_resources}) - используйте async/defer")
        
        # Рекомендации по API
        api = self.analysis_results.get("api_performance", {})
        performance_issues = len(api.get("performance_issues", []))
        if performance_issues > 0:
            recommendations.append(f"Найдено {performance_issues} проблем с производительностью API")
        
        # Рекомендации по SSL
        ssl = self.analysis_results.get("ssl_security", {})
        if not ssl.get("ssl_enabled", False):
            recommendations.append("SSL не настроен - обязательно для продакшена")
        
        ssl_issues = len(ssl.get("security_issues", []))
        if ssl_issues > 0:
            recommendations.append(f"Найдено {ssl_issues} проблем с SSL безопасностью")
        
        # Рекомендации по кэшированию
        caching = self.analysis_results.get("caching_headers", {})
        caching_issues = len(caching.get("caching_issues", []))
        if caching_issues > 0:
            recommendations.append(f"Найдено {caching_issues} проблем с кэшированием")
        
        # Рекомендации по сжатию
        compression = self.analysis_results.get("compression", {})
        compression_issues = len(compression.get("compression_issues", []))
        if compression_issues > 0:
            recommendations.append(f"Найдено {compression_issues} проблем со сжатием")
        
        return recommendations

def main():
    """Основная функция для запуска анализа"""
    project_root = "/home/qlknpodo/TWC/TwoComms_Site/twocomms"
    base_url = "http://localhost:8000"  # Измените на ваш URL
    
    analyzer = NetworkPerformanceAnalyzer(project_root)
    results = analyzer.run_full_analysis(base_url)
    recommendations = analyzer.generate_recommendations()
    
    # Сохранение результатов
    output_file = "/home/qlknpodo/TWC/TwoComms_Site/twocomms/network_performance_analysis.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            "analysis_results": results,
            "recommendations": recommendations,
            "timestamp": time.time()
        }, f, indent=2, ensure_ascii=False)
    
    print("Network Performance Analysis completed!")
    print(f"Results saved to: {output_file}")
    print(f"Recommendations: {len(recommendations)}")
    for i, rec in enumerate(recommendations, 1):
        print(f"{i}. {rec}")

if __name__ == "__main__":
    main()
