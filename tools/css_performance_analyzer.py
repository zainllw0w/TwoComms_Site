#!/usr/bin/env python3
"""
CSS Performance Analyzer
Анализирует CSS файлы на предмет производительности
"""

import os
import re
import json
import gzip
from pathlib import Path
from typing import Dict, List, Any
import time

class CSSPerformanceAnalyzer:
    def __init__(self, css_file_path: str):
        self.css_file_path = css_file_path
        self.analysis_results = {}
        
    def analyze_file_size(self) -> Dict[str, Any]:
        """Анализ размера файла"""
        file_path = Path(self.css_file_path)
        if not file_path.exists():
            return {"error": "File not found"}
            
        size_bytes = file_path.stat().st_size
        size_kb = size_bytes / 1024
        size_mb = size_kb / 1024
        
        # Проверяем возможность сжатия
        with open(file_path, 'rb') as f:
            original_data = f.read()
            compressed_data = gzip.compress(original_data)
            compression_ratio = len(compressed_data) / len(original_data)
            
        return {
            "size_bytes": size_bytes,
            "size_kb": round(size_kb, 2),
            "size_mb": round(size_mb, 2),
            "compressed_size_bytes": len(compressed_data),
            "compressed_size_kb": round(len(compressed_data) / 1024, 2),
            "compression_ratio": round(compression_ratio, 3),
            "compression_savings_percent": round((1 - compression_ratio) * 100, 1)
        }
    
    def analyze_selectors(self) -> Dict[str, Any]:
        """Анализ селекторов CSS"""
        with open(self.css_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Подсчет различных типов селекторов
        selector_patterns = {
            'universal': r'\*',
            'element': r'^[a-zA-Z][a-zA-Z0-9]*\s*\{',
            'class': r'\.[a-zA-Z][a-zA-Z0-9_-]*',
            'id': r'#[a-zA-Z][a-zA-Z0-9_-]*',
            'attribute': r'\[[^\]]+\]',
            'pseudo_class': r':[a-zA-Z][a-zA-Z0-9_-]*',
            'pseudo_element': r'::[a-zA-Z][a-zA-Z0-9_-]*',
            'descendant': r'\s+',
            'child': r'>',
            'adjacent_sibling': r'\+',
            'general_sibling': r'~'
        }
        
        selector_stats = {}
        for selector_type, pattern in selector_patterns.items():
            matches = re.findall(pattern, content, re.MULTILINE)
            selector_stats[selector_type] = len(matches)
            
        # Анализ сложности селекторов
        complex_selectors = re.findall(r'[^{]+\{[^}]*\}', content)
        complex_count = 0
        for selector in complex_selectors:
            if len(selector.split()) > 3:  # Более 3 частей в селекторе
                complex_count += 1
                
        return {
            "selector_stats": selector_stats,
            "complex_selectors_count": complex_count,
            "total_rules": len(re.findall(r'[^{]+\{[^}]*\}', content)),
            "average_selector_complexity": round(complex_count / len(complex_selectors) * 100, 2) if complex_selectors else 0
        }
    
    def analyze_properties(self) -> Dict[str, Any]:
        """Анализ CSS свойств"""
        with open(self.css_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Поиск проблемных свойств для производительности
        performance_heavy_properties = {
            'box_shadow': r'box-shadow\s*:',
            'border_radius': r'border-radius\s*:',
            'transform': r'transform\s*:',
            'filter': r'filter\s*:',
            'backdrop_filter': r'backdrop-filter\s*:',
            'gradient': r'gradient\s*\(',
            'animation': r'animation\s*:',
            'transition': r'transition\s*:',
            'will_change': r'will-change\s*:',
            'contain': r'contain\s*:'
        }
        
        property_stats = {}
        for prop_name, pattern in performance_heavy_properties.items():
            matches = re.findall(pattern, content, re.IGNORECASE)
            property_stats[prop_name] = len(matches)
            
        # Анализ дублирующихся свойств
        all_properties = re.findall(r'([a-zA-Z-]+)\s*:', content)
        property_frequency = {}
        for prop in all_properties:
            prop = prop.strip()
            property_frequency[prop] = property_frequency.get(prop, 0) + 1
            
        # Топ дублирующихся свойств
        top_duplicates = sorted(property_frequency.items(), key=lambda x: x[1], reverse=True)[:10]
        
        return {
            "performance_heavy_properties": property_stats,
            "total_properties": len(all_properties),
            "unique_properties": len(property_frequency),
            "top_duplicate_properties": top_duplicates,
            "duplication_ratio": round((len(all_properties) - len(property_frequency)) / len(all_properties) * 100, 2) if all_properties else 0
        }
    
    def analyze_media_queries(self) -> Dict[str, Any]:
        """Анализ медиа-запросов"""
        with open(self.css_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        media_queries = re.findall(r'@media\s+([^{]+)\s*\{', content)
        media_stats = {}
        
        for query in media_queries:
            query = query.strip()
            if 'min-width' in query:
                media_stats['min_width'] = media_stats.get('min_width', 0) + 1
            if 'max-width' in query:
                media_stats['max_width'] = media_stats.get('max_width', 0) + 1
            if 'orientation' in query:
                media_stats['orientation'] = media_stats.get('orientation', 0) + 1
            if 'prefers-reduced-motion' in query:
                media_stats['reduced_motion'] = media_stats.get('reduced_motion', 0) + 1
                
        return {
            "total_media_queries": len(media_queries),
            "media_query_types": media_stats,
            "media_queries_list": media_queries[:10]  # Первые 10 для примера
        }
    
    def analyze_unused_css(self, html_files: List[str]) -> Dict[str, Any]:
        """Анализ неиспользуемого CSS"""
        with open(self.css_file_path, 'r', encoding='utf-8') as f:
            css_content = f.read()
            
        # Извлекаем все селекторы из CSS
        css_selectors = set()
        selector_pattern = r'([^{}]+)\s*\{'
        matches = re.findall(selector_pattern, css_content)
        
        for match in matches:
            selectors = [s.strip() for s in match.split(',')]
            for selector in selectors:
                # Очищаем селектор от псевдо-классов и псевдо-элементов
                clean_selector = re.sub(r'[:\[]\S*', '', selector).strip()
                if clean_selector and not clean_selector.startswith('@'):
                    css_selectors.add(clean_selector)
        
        # Проверяем использование в HTML файлах
        used_selectors = set()
        for html_file in html_files:
            if os.path.exists(html_file):
                with open(html_file, 'r', encoding='utf-8') as f:
                    html_content = f.read()
                    
                for selector in css_selectors:
                    if self._is_selector_used(selector, html_content):
                        used_selectors.add(selector)
        
        unused_selectors = css_selectors - used_selectors
        
        return {
            "total_selectors": len(css_selectors),
            "used_selectors": len(used_selectors),
            "unused_selectors": len(unused_selectors),
            "usage_percentage": round(len(used_selectors) / len(css_selectors) * 100, 2) if css_selectors else 0,
            "unused_selectors_list": list(unused_selectors)[:20]  # Первые 20 для примера
        }
    
    def _is_selector_used(self, selector: str, html_content: str) -> bool:
        """Проверяет, используется ли селектор в HTML"""
        # Упрощенная проверка использования селектора
        if selector.startswith('.'):
            class_name = selector[1:]
            return f'class="{class_name}"' in html_content or f"class='{class_name}'" in html_content
        elif selector.startswith('#'):
            id_name = selector[1:]
            return f'id="{id_name}"' in html_content or f"id='{id_name}'" in html_content
        else:
            return f'<{selector}' in html_content
    
    def analyze_critical_css(self) -> Dict[str, Any]:
        """Анализ критического CSS"""
        with open(self.css_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Определяем критические селекторы (above-the-fold)
        critical_selectors = [
            'body', 'html', 'header', 'nav', 'main', 'h1', 'h2', 'h3',
            'p', 'a', 'img', 'button', 'input', 'form', 'div', 'span'
        ]
        
        critical_css = []
        non_critical_css = []
        
        rules = re.findall(r'([^{}]+)\s*\{([^{}]+)\}', content)
        for selector, properties in rules:
            selector_clean = re.sub(r'[:\[]\S*', '', selector).strip()
            if any(critical in selector_clean for critical in critical_selectors):
                critical_css.append(f"{selector} {{{properties}}}")
            else:
                non_critical_css.append(f"{selector} {{{properties}}}")
        
        return {
            "critical_rules_count": len(critical_css),
            "non_critical_rules_count": len(non_critical_css),
            "critical_percentage": round(len(critical_css) / (len(critical_css) + len(non_critical_css)) * 100, 2) if (critical_css or non_critical_css) else 0
        }
    
    def run_full_analysis(self, html_files: List[str] = None) -> Dict[str, Any]:
        """Запуск полного анализа"""
        start_time = time.time()
        
        self.analysis_results = {
            "file_info": self.analyze_file_size(),
            "selectors": self.analyze_selectors(),
            "properties": self.analyze_properties(),
            "media_queries": self.analyze_media_queries(),
            "critical_css": self.analyze_critical_css(),
            "analysis_time": time.time() - start_time
        }
        
        if html_files:
            self.analysis_results["unused_css"] = self.analyze_unused_css(html_files)
        
        return self.analysis_results
    
    def generate_recommendations(self) -> List[str]:
        """Генерация рекомендаций по оптимизации"""
        recommendations = []
        
        # Рекомендации по размеру файла
        if self.analysis_results.get("file_info", {}).get("size_kb", 0) > 100:
            recommendations.append("CSS файл слишком большой (>100KB). Рекомендуется минификация и разделение на модули.")
        
        # Рекомендации по селекторам
        selector_stats = self.analysis_results.get("selectors", {})
        if selector_stats.get("complex_selectors_count", 0) > 50:
            recommendations.append("Слишком много сложных селекторов. Упростите селекторы для лучшей производительности.")
        
        # Рекомендации по свойствам
        properties = self.analysis_results.get("properties", {})
        if properties.get("duplication_ratio", 0) > 30:
            recommendations.append("Высокий процент дублирования свойств. Используйте CSS переменные и миксины.")
        
        # Рекомендации по неиспользуемому CSS
        if "unused_css" in self.analysis_results:
            unused = self.analysis_results["unused_css"]
            if unused.get("usage_percentage", 100) < 70:
                recommendations.append(f"Только {unused['usage_percentage']}% CSS используется. Удалите неиспользуемые стили.")
        
        return recommendations

def main():
    """Основная функция для запуска анализа"""
    css_file = "/Users/zainllw0w/PycharmProjects/TwoComms/twocomms/twocomms_django_theme/static/css/styles.css"
    
    # Поиск HTML файлов для анализа использования
    html_files = []
    templates_dir = "/Users/zainllw0w/PycharmProjects/TwoComms/twocomms/twocomms_django_theme/templates"
    if os.path.exists(templates_dir):
        for root, dirs, files in os.walk(templates_dir):
            for file in files:
                if file.endswith('.html'):
                    html_files.append(os.path.join(root, file))
    
    analyzer = CSSPerformanceAnalyzer(css_file)
    results = analyzer.run_full_analysis(html_files)
    recommendations = analyzer.generate_recommendations()
    
    # Сохранение результатов
    output_file = "/Users/zainllw0w/PycharmProjects/TwoComms/css_performance_analysis.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            "analysis_results": results,
            "recommendations": recommendations,
            "timestamp": time.time()
        }, f, indent=2, ensure_ascii=False)
    
    print("CSS Performance Analysis completed!")
    print(f"Results saved to: {output_file}")
    print(f"Recommendations: {len(recommendations)}")
    for i, rec in enumerate(recommendations, 1):
        print(f"{i}. {rec}")

if __name__ == "__main__":
    main()
