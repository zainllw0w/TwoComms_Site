#!/usr/bin/env python3
"""
CSS Analyzer для TwoComms
Анализирует CSS файл на предмет:
1. Дублирующихся стилей
2. Неиспользуемых селекторов
3. Избыточного кода
4. Возможностей оптимизации
"""

import re
import os
import json
from collections import defaultdict, Counter
from pathlib import Path
import argparse

class CSSAnalyzer:
    def __init__(self, css_file_path, templates_dir):
        self.css_file_path = css_file_path
        self.templates_dir = templates_dir
        self.css_content = ""
        self.selectors = []
        self.used_classes = set()
        self.used_ids = set()
        self.duplicate_styles = []
        self.unused_selectors = []
        self.performance_issues = []
        
    def load_css(self):
        """Загружает CSS файл"""
        try:
            with open(self.css_file_path, 'r', encoding='utf-8') as f:
                self.css_content = f.read()
            print(f"✅ CSS файл загружен: {len(self.css_content)} символов")
        except Exception as e:
            print(f"❌ Ошибка загрузки CSS: {e}")
            return False
        return True
    
    def extract_selectors(self):
        """Извлекает все селекторы из CSS"""
        # Убираем комментарии
        css_no_comments = re.sub(r'/\*.*?\*/', '', self.css_content, flags=re.DOTALL)
        
        # Находим все правила CSS
        css_rules = re.findall(r'([^{}]+)\s*\{[^{}]*\}', css_no_comments, re.DOTALL)
        
        for rule in css_rules:
            # Разбиваем селекторы (могут быть через запятую)
            selectors = [s.strip() for s in rule.split(',')]
            for selector in selectors:
                if selector.strip():
                    self.selectors.append(selector.strip())
        
        print(f"✅ Найдено селекторов: {len(self.selectors)}")
        return self.selectors
    
    def extract_classes_and_ids_from_css(self):
        """Извлекает классы и ID из CSS селекторов"""
        classes = set()
        ids = set()
        
        for selector in self.selectors:
            # Находим классы (.class-name)
            class_matches = re.findall(r'\.([a-zA-Z0-9_-]+)', selector)
            classes.update(class_matches)
            
            # Находим ID (#id-name)
            id_matches = re.findall(r'#([a-zA-Z0-9_-]+)', selector)
            ids.update(id_matches)
        
        return classes, ids
    
    def scan_templates(self):
        """Сканирует HTML шаблоны для поиска используемых классов и ID"""
        template_files = []
        
        # Рекурсивно находим все HTML файлы
        for root, dirs, files in os.walk(self.templates_dir):
            for file in files:
                if file.endswith('.html'):
                    template_files.append(os.path.join(root, file))
        
        print(f"✅ Найдено HTML шаблонов: {len(template_files)}")
        
        for template_file in template_files:
            try:
                with open(template_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Находим классы в HTML
                class_matches = re.findall(r'class=["\']([^"\']*)["\']', content)
                for class_string in class_matches:
                    classes = class_string.split()
                    self.used_classes.update(classes)
                
                # Находим ID в HTML
                id_matches = re.findall(r'id=["\']([^"\']*)["\']', content)
                self.used_ids.update(id_matches)
                
                # Находим классы в Django тегах
                django_class_matches = re.findall(r'class=["\']([^"\']*)["\']', content)
                for class_string in django_class_matches:
                    classes = class_string.split()
                    self.used_classes.update(classes)
                    
            except Exception as e:
                print(f"⚠️ Ошибка чтения {template_file}: {e}")
        
        print(f"✅ Найдено используемых классов: {len(self.used_classes)}")
        print(f"✅ Найдено используемых ID: {len(self.used_ids)}")
    
    def find_duplicate_styles(self):
        """Находит дублирующиеся стили"""
        # Группируем селекторы по их стилям
        style_groups = defaultdict(list)
        
        # Извлекаем правила с их стилями
        css_rules = re.findall(r'([^{}]+)\s*\{([^{}]*)\}', self.css_content, re.DOTALL)
        
        for selectors, styles in css_rules:
            # Нормализуем стили (убираем пробелы, приводим к нижнему регистру)
            normalized_styles = re.sub(r'\s+', ' ', styles.strip().lower())
            if normalized_styles:
                style_groups[normalized_styles].append(selectors.strip())
        
        # Находим дубликаты
        for styles, selectors_list in style_groups.items():
            if len(selectors_list) > 1:
                self.duplicate_styles.append({
                    'styles': styles,
                    'selectors': selectors_list,
                    'count': len(selectors_list)
                })
        
        print(f"✅ Найдено групп дублирующихся стилей: {len(self.duplicate_styles)}")
    
    def find_unused_selectors(self):
        """Находит неиспользуемые селекторы"""
        css_classes, css_ids = self.extract_classes_and_ids_from_css()
        
        # Находим неиспользуемые классы
        unused_classes = css_classes - self.used_classes
        
        # Находим неиспользуемые ID
        unused_ids = css_ids - self.used_ids
        
        # Собираем неиспользуемые селекторы
        for selector in self.selectors:
            selector_classes = set(re.findall(r'\.([a-zA-Z0-9_-]+)', selector))
            selector_ids = set(re.findall(r'#([a-zA-Z0-9_-]+)', selector))
            
            # Проверяем, используются ли все классы и ID в селекторе
            if (selector_classes.issubset(unused_classes) and 
                selector_ids.issubset(unused_ids) and
                not any(tag in selector for tag in ['html', 'body', 'head', 'script', 'style'])):
                self.unused_selectors.append(selector)
        
        print(f"✅ Найдено неиспользуемых селекторов: {len(self.unused_selectors)}")
    
    def find_performance_issues(self):
        """Находит проблемы с производительностью"""
        issues = []
        
        # Поиск тяжелых селекторов
        heavy_selectors = []
        for selector in self.selectors:
            # Слишком длинные селекторы
            if len(selector) > 100:
                heavy_selectors.append(selector)
            
            # Сложные селекторы с множественными псевдоклассами
            if selector.count(':') > 3:
                heavy_selectors.append(selector)
        
        if heavy_selectors:
            issues.append({
                'type': 'heavy_selectors',
                'description': 'Тяжелые селекторы',
                'items': heavy_selectors
            })
        
        # Поиск избыточных !important
        important_count = self.css_content.count('!important')
        if important_count > 50:
            issues.append({
                'type': 'excessive_important',
                'description': f'Слишком много !important: {important_count}',
                'count': important_count
            })
        
        # Поиск дублирующихся медиа-запросов
        media_queries = re.findall(r'@media[^{]*\{[^{}]*\}', self.css_content, re.DOTALL)
        media_groups = defaultdict(list)
        for media in media_queries:
            media_condition = re.search(r'@media\s*([^{]+)', media)
            if media_condition:
                condition = media_condition.group(1).strip()
                media_groups[condition].append(media)
        
        duplicate_media = {k: v for k, v in media_groups.items() if len(v) > 1}
        if duplicate_media:
            issues.append({
                'type': 'duplicate_media_queries',
                'description': 'Дублирующиеся медиа-запросы',
                'items': duplicate_media
            })
        
        self.performance_issues = issues
        print(f"✅ Найдено проблем производительности: {len(issues)}")
    
    def analyze_css_structure(self):
        """Анализирует структуру CSS"""
        analysis = {
            'total_size': len(self.css_content),
            'total_lines': self.css_content.count('\n'),
            'total_selectors': len(self.selectors),
            'total_rules': len(re.findall(r'[^{}]*\{[^{}]*\}', self.css_content)),
            'media_queries': len(re.findall(r'@media', self.css_content)),
            'keyframes': len(re.findall(r'@keyframes', self.css_content)),
            'imports': len(re.findall(r'@import', self.css_content)),
            'comments': len(re.findall(r'/\*.*?\*/', self.css_content, re.DOTALL)),
        }
        
        return analysis
    
    def generate_report(self):
        """Генерирует отчет анализа"""
        analysis = self.analyze_css_structure()
        
        report = {
            'file_info': {
                'css_file': self.css_file_path,
                'templates_dir': self.templates_dir,
                'analysis_date': str(Path().cwd())
            },
            'css_structure': analysis,
            'duplicate_styles': self.duplicate_styles,
            'unused_selectors': self.unused_selectors,
            'performance_issues': self.performance_issues,
            'usage_stats': {
                'total_css_classes': len(self.extract_classes_and_ids_from_css()[0]),
                'used_classes': len(self.used_classes),
                'unused_classes': len(self.extract_classes_and_ids_from_css()[0]) - len(self.used_classes),
                'total_css_ids': len(self.extract_classes_and_ids_from_css()[1]),
                'used_ids': len(self.used_ids),
                'unused_ids': len(self.extract_classes_and_ids_from_css()[1]) - len(self.used_ids)
            }
        }
        
        return report
    
    def run_analysis(self):
        """Запускает полный анализ"""
        print("🔍 Начинаем анализ CSS файла...")
        
        if not self.load_css():
            return None
        
        self.extract_selectors()
        self.scan_templates()
        self.find_duplicate_styles()
        self.find_unused_selectors()
        self.find_performance_issues()
        
        print("✅ Анализ завершен!")
        return self.generate_report()

def main():
    parser = argparse.ArgumentParser(description='CSS Analyzer для TwoComms')
    parser.add_argument('--css', default='twocomms/twocomms_django_theme/static/css/styles.css',
                       help='Путь к CSS файлу')
    parser.add_argument('--templates', default='twocomms/twocomms_django_theme/templates',
                       help='Путь к директории с шаблонами')
    parser.add_argument('--output', default='css_analysis_report.json',
                       help='Файл для сохранения отчета')
    
    args = parser.parse_args()
    
    analyzer = CSSAnalyzer(args.css, args.templates)
    report = analyzer.run_analysis()
    
    if report:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"📊 Отчет сохранен в {args.output}")

if __name__ == "__main__":
    main()

