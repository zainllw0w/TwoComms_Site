#!/usr/bin/env python3
"""
Глубокий CSS Analyzer для TwoComms
Дополнительный анализ для выявления специфических проблем
"""

import re
import json
from collections import defaultdict, Counter
from pathlib import Path

class DeepCSSAnalyzer:
    def __init__(self, css_file_path):
        self.css_file_path = css_file_path
        self.css_content = ""
        self.issues = []
        
    def load_css(self):
        """Загружает CSS файл"""
        with open(self.css_file_path, 'r', encoding='utf-8') as f:
            self.css_content = f.read()
        return True
    
    def find_redundant_properties(self):
        """Находит избыточные CSS свойства"""
        redundant = []
        
        # Поиск дублирующихся свойств в одном селекторе
        rules = re.findall(r'([^{}]+)\s*\{([^{}]*)\}', self.css_content, re.DOTALL)
        
        for selectors, styles in rules:
            properties = {}
            lines = styles.split(';')
            
            for line in lines:
                if ':' in line:
                    prop, value = line.split(':', 1)
                    prop = prop.strip().lower()
                    value = value.strip()
                    
                    if prop in properties:
                        redundant.append({
                            'selector': selectors.strip(),
                            'property': prop,
                            'first_value': properties[prop],
                            'duplicate_value': value
                        })
                    else:
                        properties[prop] = value
        
        return redundant
    
    def find_unused_animations(self):
        """Находит неиспользуемые анимации"""
        # Извлекаем все keyframes
        keyframes = re.findall(r'@keyframes\s+([a-zA-Z0-9_-]+)', self.css_content)
        
        # Ищем использование анимаций
        used_animations = set()
        animation_usage = re.findall(r'animation(?:-name)?\s*:\s*([a-zA-Z0-9_-]+)', self.css_content)
        used_animations.update(animation_usage)
        
        unused = []
        for keyframe in keyframes:
            if keyframe not in used_animations:
                unused.append(keyframe)
        
        return unused
    
    def find_heavy_selectors(self):
        """Находит тяжелые селекторы"""
        heavy = []
        
        # Извлекаем все селекторы
        selectors = re.findall(r'([^{}]+)\s*\{', self.css_content)
        
        for selector in selectors:
            selector = selector.strip()
            
            # Слишком длинные селекторы
            if len(selector) > 150:
                heavy.append({
                    'type': 'too_long',
                    'selector': selector,
                    'length': len(selector)
                })
            
            # Слишком много псевдоклассов
            pseudo_count = selector.count(':')
            if pseudo_count > 4:
                heavy.append({
                    'type': 'too_many_pseudo',
                    'selector': selector,
                    'pseudo_count': pseudo_count
                })
            
            # Слишком глубокая вложенность
            if selector.count(' ') > 5:
                heavy.append({
                    'type': 'too_deep',
                    'selector': selector,
                    'depth': selector.count(' ')
                })
        
        return heavy
    
    def find_media_query_issues(self):
        """Находит проблемы с медиа-запросами"""
        issues = []
        
        # Дублирующиеся медиа-запросы
        media_queries = re.findall(r'@media\s*([^{]+)\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}', self.css_content, re.DOTALL)
        media_groups = defaultdict(list)
        
        for condition, content in media_queries:
            normalized_condition = re.sub(r'\s+', ' ', condition.strip())
            media_groups[normalized_condition].append(content)
        
        for condition, contents in media_groups.items():
            if len(contents) > 1:
                issues.append({
                    'type': 'duplicate_media',
                    'condition': condition,
                    'count': len(contents)
                })
        
        # Неэффективные медиа-запросы
        for condition, content in media_queries:
            if 'min-width' in condition and 'max-width' in condition:
                # Проверяем на пересекающиеся диапазоны
                min_matches = re.findall(r'min-width:\s*(\d+)px', condition)
                max_matches = re.findall(r'max-width:\s*(\d+)px', condition)
                
                if min_matches and max_matches:
                    min_val = int(min_matches[0])
                    max_val = int(max_matches[0])
                    if min_val >= max_val:
                        issues.append({
                            'type': 'invalid_range',
                            'condition': condition,
                            'min': min_val,
                            'max': max_val
                        })
        
        return issues
    
    def find_css_variables_issues(self):
        """Находит проблемы с CSS переменными"""
        issues = []
        
        # Неиспользуемые CSS переменные
        var_definitions = re.findall(r'--([a-zA-Z0-9_-]+)\s*:', self.css_content)
        var_usage = re.findall(r'var\(--([a-zA-Z0-9_-]+)\)', self.css_content)
        
        defined_vars = set(var_definitions)
        used_vars = set(var_usage)
        unused_vars = defined_vars - used_vars
        
        if unused_vars:
            issues.append({
                'type': 'unused_variables',
                'variables': list(unused_vars)
            })
        
        # Переопределенные переменные
        var_redefinitions = Counter(var_definitions)
        redefined = {var: count for var, count in var_redefinitions.items() if count > 1}
        
        if redefined:
            issues.append({
                'type': 'redefined_variables',
                'variables': redefined
            })
        
        return issues
    
    def find_performance_anti_patterns(self):
        """Находит антипаттерны производительности"""
        issues = []
        
        # Избыточные !important
        important_count = self.css_content.count('!important')
        if important_count > 100:
            issues.append({
                'type': 'excessive_important',
                'count': important_count
            })
        
        # Слишком много box-shadow
        shadow_count = self.css_content.count('box-shadow')
        if shadow_count > 50:
            issues.append({
                'type': 'excessive_shadows',
                'count': shadow_count
            })
        
        # Слишком много backdrop-filter
        backdrop_count = self.css_content.count('backdrop-filter')
        if backdrop_count > 30:
            issues.append({
                'type': 'excessive_backdrop',
                'count': backdrop_count
            })
        
        # Слишком много transform
        transform_count = self.css_content.count('transform')
        if transform_count > 100:
            issues.append({
                'type': 'excessive_transforms',
                'count': transform_count
            })
        
        return issues
    
    def find_duplicate_blocks(self):
        """Находит дублирующиеся блоки CSS"""
        # Разбиваем CSS на блоки
        blocks = re.findall(r'([^{}]+)\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}', self.css_content, re.DOTALL)
        
        # Группируем по содержимому
        block_groups = defaultdict(list)
        
        for selector, content in blocks:
            # Нормализуем содержимое
            normalized_content = re.sub(r'\s+', ' ', content.strip().lower())
            if normalized_content:
                block_groups[normalized_content].append(selector.strip())
        
        # Находим дубликаты
        duplicates = []
        for content, selectors in block_groups.items():
            if len(selectors) > 1:
                duplicates.append({
                    'content': content,
                    'selectors': selectors,
                    'count': len(selectors)
                })
        
        return duplicates
    
    def analyze_specificity_issues(self):
        """Анализирует проблемы со специфичностью"""
        issues = []
        
        # Селекторы с очень высокой специфичностью
        selectors = re.findall(r'([^{}]+)\s*\{', self.css_content)
        
        for selector in selectors:
            selector = selector.strip()
            
            # Подсчитываем специфичность (упрощенно)
            id_count = selector.count('#')
            class_count = selector.count('.')
            element_count = len(re.findall(r'\b[a-zA-Z][a-zA-Z0-9]*\b', selector))
            
            specificity = id_count * 100 + class_count * 10 + element_count
            
            if specificity > 200:  # Очень высокая специфичность
                issues.append({
                    'selector': selector,
                    'specificity': specificity,
                    'ids': id_count,
                    'classes': class_count,
                    'elements': element_count
                })
        
        return issues
    
    def run_deep_analysis(self):
        """Запускает глубокий анализ"""
        print("🔍 Запускаем глубокий анализ CSS...")
        
        self.load_css()
        
        analysis = {
            'redundant_properties': self.find_redundant_properties(),
            'unused_animations': self.find_unused_animations(),
            'heavy_selectors': self.find_heavy_selectors(),
            'media_query_issues': self.find_media_query_issues(),
            'css_variables_issues': self.find_css_variables_issues(),
            'performance_anti_patterns': self.find_performance_anti_patterns(),
            'duplicate_blocks': self.find_duplicate_blocks(),
            'specificity_issues': self.analyze_specificity_issues()
        }
        
        # Подсчитываем общую статистику
        total_issues = sum(len(v) if isinstance(v, list) else 1 for v in analysis.values())
        
        print(f"✅ Глубокий анализ завершен! Найдено проблем: {total_issues}")
        
        return analysis

def main():
    analyzer = DeepCSSAnalyzer('twocomms/twocomms_django_theme/static/css/styles.css')
    analysis = analyzer.run_deep_analysis()
    
    with open('css_deep_analysis_report.json', 'w', encoding='utf-8') as f:
        json.dump(analysis, f, ensure_ascii=False, indent=2)
    
    print("📊 Глубокий анализ сохранен в css_deep_analysis_report.json")

if __name__ == "__main__":
    main()

