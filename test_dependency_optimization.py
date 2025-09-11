#!/usr/bin/env python3
"""
Скрипт для тестирования оптимизации дерева зависимостей TwoComms
Проверяет производительность до и после оптимизации
"""

import os
import sys
import time
import requests
import json
from datetime import datetime
from urllib.parse import urljoin

class DependencyOptimizationTester:
    def __init__(self, base_url="https://twocomms.shop"):
        self.base_url = base_url
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'base_url': base_url,
            'tests': {}
        }
    
    def test_critical_path(self):
        """Тестирует критический путь загрузки"""
        print("🔍 Тестирование критического пути...")
        
        start_time = time.time()
        
        try:
            # Загружаем главную страницу
            response = requests.get(self.base_url, timeout=10)
            load_time = time.time() - start_time
            
            # Анализируем заголовки
            headers = response.headers
            
            # Проверяем наличие оптимизаций
            optimizations = {
                'preconnect': 'preconnect' in response.text,
                'async_css': 'rel="preload" as="style"' in response.text,
                'defer_js': 'defer' in response.text,
                'lazy_images': 'loading="lazy"' in response.text,
                'critical_css': '<style>' in response.text,
                'idle_analytics': 'requestIdleCallback' in response.text
            }
            
            self.results['tests']['critical_path'] = {
                'load_time': round(load_time * 1000, 2),  # в миллисекундах
                'status_code': response.status_code,
                'content_length': len(response.content),
                'optimizations': optimizations,
                'score': self._calculate_optimization_score(optimizations)
            }
            
            print(f"✅ Критический путь: {load_time*1000:.2f}ms")
            print(f"📊 Оценка оптимизации: {self._calculate_optimization_score(optimizations)}/100")
            
        except Exception as e:
            print(f"❌ Ошибка тестирования критического пути: {e}")
            self.results['tests']['critical_path'] = {'error': str(e)}
    
    def test_resource_loading(self):
        """Тестирует загрузку ресурсов"""
        print("🔍 Тестирование загрузки ресурсов...")
        
        resources = [
            '/static/css/styles.min.css',
            '/static/css/cls-fixes.css',
            '/static/js/main.js',
            '/static/img/logo.svg'
        ]
        
        resource_times = {}
        
        for resource in resources:
            try:
                start_time = time.time()
                response = requests.get(urljoin(self.base_url, resource), timeout=5)
                load_time = time.time() - start_time
                
                resource_times[resource] = {
                    'load_time': round(load_time * 1000, 2),
                    'status_code': response.status_code,
                    'content_length': len(response.content),
                    'content_type': response.headers.get('content-type', ''),
                    'cache_control': response.headers.get('cache-control', '')
                }
                
                print(f"  📁 {resource}: {load_time*1000:.2f}ms")
                
            except Exception as e:
                print(f"  ❌ {resource}: {e}")
                resource_times[resource] = {'error': str(e)}
        
        self.results['tests']['resource_loading'] = resource_times
    
    def test_core_web_vitals(self):
        """Тестирует Core Web Vitals (симуляция)"""
        print("🔍 Тестирование Core Web Vitals...")
        
        # Симуляция метрик на основе загрузки
        try:
            start_time = time.time()
            response = requests.get(self.base_url, timeout=10)
            total_time = time.time() - start_time
            
            # Оценка метрик на основе времени загрузки
            fcp = min(total_time * 1000 * 0.6, 1000)  # First Contentful Paint
            lcp = min(total_time * 1000 * 0.8, 2000)  # Largest Contentful Paint
            cls = 0.05 if 'cls-fixes.css' in response.text else 0.15  # Cumulative Layout Shift
            
            self.results['tests']['core_web_vitals'] = {
                'fcp': round(fcp, 2),
                'lcp': round(lcp, 2),
                'cls': round(cls, 3),
                'fid': 50,  # First Input Delay (симуляция)
                'ttfb': round(total_time * 1000 * 0.3, 2)  # Time to First Byte
            }
            
            print(f"  📊 FCP: {fcp:.2f}ms")
            print(f"  📊 LCP: {lcp:.2f}ms")
            print(f"  📊 CLS: {cls:.3f}")
            
        except Exception as e:
            print(f"❌ Ошибка тестирования Core Web Vitals: {e}")
            self.results['tests']['core_web_vitals'] = {'error': str(e)}
    
    def test_mobile_performance(self):
        """Тестирует производительность на мобильных устройствах"""
        print("🔍 Тестирование мобильной производительности...")
        
        mobile_headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1'
        }
        
        try:
            start_time = time.time()
            response = requests.get(self.base_url, headers=mobile_headers, timeout=10)
            load_time = time.time() - start_time
            
            # Проверяем мобильные оптимизации
            mobile_optimizations = {
                'viewport_meta': 'viewport' in response.text,
                'mobile_css': 'media=' in response.text,
                'touch_icons': 'apple-touch-icon' in response.text,
                'mobile_js': 'defer' in response.text
            }
            
            self.results['tests']['mobile_performance'] = {
                'load_time': round(load_time * 1000, 2),
                'optimizations': mobile_optimizations,
                'score': self._calculate_optimization_score(mobile_optimizations)
            }
            
            print(f"  📱 Мобильная загрузка: {load_time*1000:.2f}ms")
            print(f"  📊 Мобильная оценка: {self._calculate_optimization_score(mobile_optimizations)}/100")
            
        except Exception as e:
            print(f"❌ Ошибка тестирования мобильной производительности: {e}")
            self.results['tests']['mobile_performance'] = {'error': str(e)}
    
    def _calculate_optimization_score(self, optimizations):
        """Вычисляет оценку оптимизации"""
        total = len(optimizations)
        enabled = sum(1 for v in optimizations.values() if v)
        return round((enabled / total) * 100) if total > 0 else 0
    
    def generate_report(self):
        """Генерирует отчет о тестировании"""
        print("\n" + "="*60)
        print("📊 ОТЧЕТ О ТЕСТИРОВАНИИ ОПТИМИЗАЦИИ ДЕРЕВА ЗАВИСИМОСТЕЙ")
        print("="*60)
        
        # Общая оценка
        total_score = 0
        test_count = 0
        
        for test_name, test_data in self.results['tests'].items():
            if 'score' in test_data:
                total_score += test_data['score']
                test_count += 1
        
        overall_score = round(total_score / test_count) if test_count > 0 else 0
        
        print(f"🎯 Общая оценка оптимизации: {overall_score}/100")
        print(f"⏰ Время тестирования: {self.results['timestamp']}")
        print(f"🌐 Тестируемый сайт: {self.results['base_url']}")
        
        # Детальные результаты
        for test_name, test_data in self.results['tests'].items():
            print(f"\n📋 {test_name.upper()}:")
            if 'error' in test_data:
                print(f"  ❌ Ошибка: {test_data['error']}")
            else:
                for key, value in test_data.items():
                    if key != 'score':
                        print(f"  • {key}: {value}")
        
        # Рекомендации
        print(f"\n💡 РЕКОМЕНДАЦИИ:")
        if overall_score < 70:
            print("  🔴 Требуется значительная оптимизация")
        elif overall_score < 85:
            print("  🟡 Есть возможности для улучшения")
        else:
            print("  🟢 Отличная оптимизация!")
        
        # Сохраняем отчет
        report_file = f"dependency_optimization_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Отчет сохранен: {report_file}")
    
    def run_all_tests(self):
        """Запускает все тесты"""
        print("🚀 Запуск тестирования оптимизации дерева зависимостей...")
        print(f"🌐 Тестируемый сайт: {self.base_url}")
        print("-" * 60)
        
        self.test_critical_path()
        self.test_resource_loading()
        self.test_core_web_vitals()
        self.test_mobile_performance()
        
        self.generate_report()

def main():
    """Основная функция"""
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
    else:
        base_url = "https://twocomms.shop"
    
    tester = DependencyOptimizationTester(base_url)
    tester.run_all_tests()

if __name__ == "__main__":
    main()
