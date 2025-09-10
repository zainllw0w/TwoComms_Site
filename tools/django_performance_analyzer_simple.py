#!/usr/bin/env python3
"""
Django Performance Analyzer (Simple Version)
Анализирует Django код без импорта Django
"""

import os
import re
import json
import ast
import time
from pathlib import Path
from typing import Dict, List, Any, Set

class DjangoPerformanceAnalyzerSimple:
    def __init__(self, project_root: str):
        self.project_root = project_root
        self.analysis_results = {}
        
    def analyze_models(self) -> Dict[str, Any]:
        """Анализ моделей Django"""
        models_analysis = {}
        total_models = 0
        total_fields = 0
        problematic_models = []
        
        # Поиск файлов models.py
        for root, dirs, files in os.walk(self.project_root):
            for file in files:
                if file == 'models.py':
                    app_name = os.path.basename(os.path.dirname(os.path.join(root, file)))
                    models_file = os.path.join(root, file)
                    
                    with open(models_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Подсчет моделей
                    model_matches = re.findall(r'class\s+(\w+)\s*\([^)]*Model[^)]*\):', content)
                    total_models += len(model_matches)
                    
                    # Анализ полей
                    field_patterns = [
                        r'CharField\s*\(',
                        r'TextField\s*\(',
                        r'IntegerField\s*\(',
                        r'ForeignKey\s*\(',
                        r'ManyToManyField\s*\(',
                        r'DateTimeField\s*\(',
                        r'BooleanField\s*\(',
                        r'DecimalField\s*\(',
                        r'EmailField\s*\(',
                        r'URLField\s*\('
                    ]
                    
                    field_count = 0
                    for pattern in field_patterns:
                        field_count += len(re.findall(pattern, content))
                    
                    total_fields += field_count
                    
                    # Поиск проблемных паттернов
                    issues = []
                    
                    # Отсутствие индексов
                    if 'db_index=True' not in content:
                        issues.append("Отсутствуют индексы")
                    
                    # Длинные CharField без max_length
                    long_charfields = re.findall(r'CharField\s*\(\s*(?!.*max_length)', content)
                    if long_charfields:
                        issues.append(f"CharField без max_length: {len(long_charfields)}")
                    
                    # Отсутствие related_name
                    foreign_keys = re.findall(r'ForeignKey\s*\([^)]*\)', content)
                    for fk in foreign_keys:
                        if 'related_name' not in fk:
                            issues.append("ForeignKey без related_name")
                    
                    if issues:
                        problematic_models.append(f"{app_name}: {', '.join(issues)}")
                    
                    models_analysis[app_name] = {
                        "models_count": len(model_matches),
                        "fields_count": field_count,
                        "issues": issues
                    }
        
        return {
            "total_models": total_models,
            "total_fields": total_fields,
            "models_by_app": models_analysis,
            "problematic_models": problematic_models,
            "average_fields_per_model": round(total_fields / total_models, 2) if total_models > 0 else 0
        }
    
    def analyze_views(self) -> Dict[str, Any]:
        """Анализ Django views"""
        views_analysis = {}
        total_views = 0
        problematic_views = []
        
        # Анализ views.py файлов
        for root, dirs, files in os.walk(self.project_root):
            for file in files:
                if file == 'views.py':
                    app_name = os.path.basename(os.path.dirname(os.path.join(root, file)))
                    views_file = os.path.join(root, file)
                    
                    with open(views_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Подсчет функций и классов
                    function_views = len(re.findall(r'def\s+(\w+)\s*\([^)]*request[^)]*\):', content))
                    class_views = len(re.findall(r'class\s+(\w+)\s*\([^)]*View[^)]*\):', content))
                    total_views += function_views + class_views
                    
                    # Поиск проблемных паттернов
                    issues = []
                    
                    # objects.all() без фильтрации
                    all_usage = len(re.findall(r'\.objects\.all\(\)', content))
                    if all_usage > 0:
                        issues.append(f"objects.all() без фильтрации: {all_usage}")
                    
                    # Отсутствие select_related/prefetch_related
                    if 'select_related' not in content and 'prefetch_related' not in content:
                        if 'objects.' in content:
                            issues.append("Отсутствует select_related/prefetch_related")
                    
                    # Отсутствие кэширования
                    if 'cache' not in content.lower() and 'Cache' not in content:
                        issues.append("Отсутствует кэширование")
                    
                    # Синхронные запросы
                    if 'requests.get' in content or 'requests.post' in content:
                        issues.append("Синхронные HTTP запросы")
                    
                    # Отсутствие обработки исключений
                    if 'objects.get(' in content and 'try:' not in content:
                        issues.append("objects.get() без обработки исключений")
                    
                    if issues:
                        problematic_views.append(f"{app_name}: {', '.join(issues)}")
                    
                    views_analysis[app_name] = {
                        "function_views": function_views,
                        "class_views": class_views,
                        "total_views": function_views + class_views,
                        "issues": issues
                    }
        
        return {
            "total_views": total_views,
            "views_by_app": views_analysis,
            "problematic_views": problematic_views
        }
    
    def analyze_urls(self) -> Dict[str, Any]:
        """Анализ URL конфигурации"""
        urls_analysis = {
            "total_urls": 0,
            "urls_by_app": {},
            "problematic_urls": [],
            "recommendations": []
        }
        
        # Анализ urls.py файлов
        for root, dirs, files in os.walk(self.project_root):
            for file in files:
                if file == 'urls.py':
                    app_name = os.path.basename(os.path.dirname(os.path.join(root, file)))
                    urls_file = os.path.join(root, file)
                    
                    with open(urls_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Подсчет URL паттернов
                    url_patterns = len(re.findall(r'path\s*\(|url\s*\(', content))
                    urls_analysis["urls_by_app"][app_name] = url_patterns
                    urls_analysis["total_urls"] += url_patterns
                    
                    # Поиск проблемных паттернов
                    if 'include(' in content and 'namespace=' not in content:
                        urls_analysis["problematic_urls"].append(f"{app_name}: отсутствует namespace")
                    
                    if 're_path(' in content:
                        urls_analysis["problematic_urls"].append(f"{app_name}: использует регулярные выражения")
        
        # Рекомендации
        if urls_analysis["total_urls"] > 100:
            urls_analysis["recommendations"].append("Слишком много URL - рассмотрите группировку по приложениям")
        
        return urls_analysis
    
    def analyze_settings(self) -> Dict[str, Any]:
        """Анализ настроек Django"""
        settings_analysis = {
            "debug_mode": None,
            "database_engine": None,
            "cache_backend": None,
            "security_settings": {},
            "performance_settings": {},
            "recommendations": []
        }
        
        settings_file = os.path.join(self.project_root, "twocomms", "settings.py")
        if os.path.exists(settings_file):
            with open(settings_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Поиск настроек
            debug_match = re.search(r'DEBUG\s*=\s*(True|False)', content)
            if debug_match:
                settings_analysis["debug_mode"] = debug_match.group(1) == 'True'
            
            db_match = re.search(r'ENGINE\s*:\s*[\'"]([^\'"]+)[\'"]', content)
            if db_match:
                settings_analysis["database_engine"] = db_match.group(1)
            
            cache_match = re.search(r'CACHES\s*=\s*{[^}]*BACKEND\s*:\s*[\'"]([^\'"]+)[\'"]', content)
            if cache_match:
                settings_analysis["cache_backend"] = cache_match.group(1)
            
            # Рекомендации
            if settings_analysis["debug_mode"]:
                settings_analysis["recommendations"].append("DEBUG=True в продакшене - отключите для производительности")
            
            if not settings_analysis["cache_backend"]:
                settings_analysis["recommendations"].append("Кэширование не настроено - настройте Redis или Memcached")
            
            if settings_analysis["database_engine"] and 'sqlite' in settings_analysis["database_engine"]:
                settings_analysis["recommendations"].append("SQLite в продакшене - перейдите на PostgreSQL или MySQL")
        
        return settings_analysis
    
    def analyze_requirements(self) -> Dict[str, Any]:
        """Анализ зависимостей"""
        requirements_analysis = {
            "total_packages": 0,
            "performance_packages": [],
            "security_packages": [],
            "missing_packages": [],
            "recommendations": []
        }
        
        requirements_file = os.path.join(self.project_root, "requirements.txt")
        if os.path.exists(requirements_file):
            with open(requirements_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            packages = [line.strip() for line in content.split('\n') if line.strip() and not line.startswith('#')]
            requirements_analysis["total_packages"] = len(packages)
            
            # Проверка производительности пакетов
            performance_packages = ['redis', 'celery', 'gunicorn', 'psycopg2', 'django-redis']
            for pkg in performance_packages:
                if any(pkg in package.lower() for package in packages):
                    requirements_analysis["performance_packages"].append(pkg)
                else:
                    requirements_analysis["missing_packages"].append(pkg)
            
            # Рекомендации
            if 'redis' not in [pkg.lower() for pkg in packages]:
                requirements_analysis["recommendations"].append("Добавьте Redis для кэширования")
            
            if 'gunicorn' not in [pkg.lower() for pkg in packages]:
                requirements_analysis["recommendations"].append("Добавьте Gunicorn для продакшена")
        
        return requirements_analysis
    
    def run_full_analysis(self) -> Dict[str, Any]:
        """Запуск полного анализа"""
        start_time = time.time()
        
        self.analysis_results = {
            "models": self.analyze_models(),
            "views": self.analyze_views(),
            "urls": self.analyze_urls(),
            "settings": self.analyze_settings(),
            "requirements": self.analyze_requirements(),
            "analysis_time": time.time() - start_time
        }
        
        return self.analysis_results
    
    def generate_recommendations(self) -> List[str]:
        """Генерация рекомендаций по оптимизации"""
        recommendations = []
        
        # Рекомендации по моделям
        models = self.analysis_results.get("models", {})
        if models.get("problematic_models"):
            recommendations.append(f"Найдено {len(models['problematic_models'])} проблемных моделей - добавьте индексы и оптимизируйте связи")
        
        # Рекомендации по views
        views = self.analysis_results.get("views", {})
        if views.get("problematic_views"):
            recommendations.append(f"Найдено {len(views['problematic_views'])} проблемных views - упростите логику и добавьте кэширование")
        
        # Рекомендации по настройкам
        settings = self.analysis_results.get("settings", {})
        if settings.get("recommendations"):
            recommendations.extend(settings["recommendations"])
        
        # Рекомендации по зависимостям
        requirements = self.analysis_results.get("requirements", {})
        if requirements.get("recommendations"):
            recommendations.extend(requirements["recommendations"])
        
        return recommendations

def main():
    """Основная функция для запуска анализа"""
    project_root = "/home/qlknpodo/TWC/TwoComms_Site/twocomms"
    
    analyzer = DjangoPerformanceAnalyzerSimple(project_root)
    results = analyzer.run_full_analysis()
    recommendations = analyzer.generate_recommendations()
    
    # Сохранение результатов
    output_file = "/home/qlknpodo/TWC/TwoComms_Site/twocomms/django_performance_analysis.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            "analysis_results": results,
            "recommendations": recommendations,
            "timestamp": time.time()
        }, f, indent=2, ensure_ascii=False)
    
    print("Django Performance Analysis completed!")
    print(f"Results saved to: {output_file}")
    print(f"Recommendations: {len(recommendations)}")
    for i, rec in enumerate(recommendations, 1):
        print(f"{i}. {rec}")

if __name__ == "__main__":
    main()
