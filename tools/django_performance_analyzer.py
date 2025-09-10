#!/usr/bin/env python3
"""
Django Performance Analyzer
Анализирует Django views, модели и запросы к БД на предмет производительности
"""

import os
import re
import json
import ast
import time
from pathlib import Path
from typing import Dict, List, Any, Set
import django
from django.conf import settings
from django.db import connection
from django.test.utils import override_settings

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'twocomms.settings')
django.setup()

class DjangoPerformanceAnalyzer:
    def __init__(self, project_root: str):
        self.project_root = project_root
        self.analysis_results = {}
        
    def analyze_models(self) -> Dict[str, Any]:
        """Анализ моделей Django"""
        from django.apps import apps
        
        models_analysis = {}
        total_models = 0
        total_fields = 0
        problematic_models = []
        
        for app_config in apps.get_app_configs():
            app_name = app_config.name
            models_analysis[app_name] = {}
            
            for model in app_config.get_models():
                total_models += 1
                model_name = model.__name__
                
                # Анализ полей модели
                fields = model._meta.get_fields()
                field_count = len(fields)
                total_fields += field_count
                
                # Поиск проблемных полей
                problematic_fields = []
                for field in fields:
                    if hasattr(field, 'db_index') and not field.db_index:
                        if isinstance(field, (models.CharField, models.TextField)):
                            problematic_fields.append(f"{field.name} (CharField/TextField без индекса)")
                    
                    if hasattr(field, 'max_length') and field.max_length and field.max_length > 255:
                        problematic_fields.append(f"{field.name} (длинное поле: {field.max_length})")
                
                # Анализ связей
                foreign_keys = [f for f in fields if hasattr(f, 'related_model') and f.related_model]
                many_to_many = [f for f in fields if hasattr(f, 'many_to_many') and f.many_to_many]
                
                # Поиск N+1 проблем
                n_plus_one_risks = []
                for fk in foreign_keys:
                    if not hasattr(fk, 'related_name') or not fk.related_name:
                        n_plus_one_risks.append(f"{fk.name} (нет related_name)")
                
                model_analysis = {
                    "field_count": field_count,
                    "foreign_keys": len(foreign_keys),
                    "many_to_many": len(many_to_many),
                    "problematic_fields": problematic_fields,
                    "n_plus_one_risks": n_plus_one_risks,
                    "has_meta_ordering": bool(model._meta.ordering),
                    "has_meta_indexes": bool(model._meta.indexes)
                }
                
                models_analysis[app_name][model_name] = model_analysis
                
                # Отмечаем проблемные модели
                if (len(problematic_fields) > 2 or 
                    len(n_plus_one_risks) > 1 or 
                    field_count > 20):
                    problematic_models.append(f"{app_name}.{model_name}")
        
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
                    views_file = os.path.join(root, file)
                    app_name = os.path.basename(os.path.dirname(views_file))
                    
                    with open(views_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Парсинг AST для анализа функций
                    try:
                        tree = ast.parse(content)
                        views_analysis[app_name] = {}
                        
                        for node in ast.walk(tree):
                            if isinstance(node, ast.FunctionDef):
                                total_views += 1
                                view_name = node.name
                                
                                # Анализ декораторов
                                decorators = [d.id if hasattr(d, 'id') else str(d) for d in node.decorator_list]
                                
                                # Анализ сложности функции
                                lines_of_code = len(node.body)
                                complexity_score = self._calculate_complexity(node)
                                
                                # Поиск проблемных паттернов
                                issues = []
                                view_content = ast.get_source_segment(content, node)
                                
                                if view_content:
                                    if 'objects.all()' in view_content:
                                        issues.append("Использует objects.all() без фильтрации")
                                    if 'objects.get(' in view_content and 'try:' not in view_content:
                                        issues.append("Использует objects.get() без обработки исключений")
                                    if 'for ' in view_content and 'objects.' in view_content:
                                        issues.append("Возможная N+1 проблема в цикле")
                                    if 'render(' in view_content and 'context' not in view_content:
                                        issues.append("Рендеринг без контекста")
                                    if 'HttpResponse' in view_content and 'json' not in view_content:
                                        issues.append("Возвращает HttpResponse вместо JsonResponse")
                                
                                view_analysis = {
                                    "decorators": decorators,
                                    "lines_of_code": lines_of_code,
                                    "complexity_score": complexity_score,
                                    "issues": issues,
                                    "has_caching": any('cache' in d.lower() for d in decorators),
                                    "has_permissions": any('permission' in d.lower() for d in decorators),
                                    "is_class_based": any('View' in d for d in decorators)
                                }
                                
                                views_analysis[app_name][view_name] = view_analysis
                                
                                # Отмечаем проблемные views
                                if (complexity_score > 10 or 
                                    len(issues) > 2 or 
                                    lines_of_code > 50):
                                    problematic_views.append(f"{app_name}.{view_name}")
                    
                    except SyntaxError:
                        continue
        
        return {
            "total_views": total_views,
            "views_by_app": views_analysis,
            "problematic_views": problematic_views
        }
    
    def _calculate_complexity(self, node: ast.AST) -> int:
        """Вычисление цикломатической сложности"""
        complexity = 1
        
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For, ast.AsyncFor)):
                complexity += 1
            elif isinstance(child, ast.ExceptHandler):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
        
        return complexity
    
    def analyze_queries(self) -> Dict[str, Any]:
        """Анализ SQL запросов"""
        from django.db import connection
        from django.test.utils import override_settings
        
        # Включаем логирование запросов
        with override_settings(DEBUG=True):
            connection.queries_log.clear()
            
            # Здесь можно добавить тестовые запросы или использовать существующие
            # Для демонстрации создадим базовый анализ
            
            query_analysis = {
                "total_queries": 0,
                "duplicate_queries": 0,
                "slow_queries": 0,
                "n_plus_one_queries": 0,
                "query_patterns": {},
                "recommendations": []
            }
            
            # Анализ паттернов в коде
            query_patterns = {
                'select_related': 0,
                'prefetch_related': 0,
                'only': 0,
                'defer': 0,
                'values': 0,
                'values_list': 0,
                'exists': 0,
                'count': 0,
                'aggregate': 0,
                'annotate': 0
            }
            
            # Поиск в коде
            for root, dirs, files in os.walk(self.project_root):
                for file in files:
                    if file.endswith('.py'):
                        file_path = os.path.join(root, file)
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            
                        for pattern, count in query_patterns.items():
                            matches = len(re.findall(f'\.{pattern}\s*\(', content))
                            query_patterns[pattern] += matches
            
            query_analysis["query_patterns"] = query_patterns
            
            # Рекомендации
            if query_patterns['select_related'] < 5:
                query_analysis["recommendations"].append("Мало select_related() - возможны N+1 проблемы")
            if query_patterns['prefetch_related'] < 3:
                query_analysis["recommendations"].append("Мало prefetch_related() - возможны проблемы с M2M")
            if query_patterns['only'] < 2:
                query_analysis["recommendations"].append("Мало only() - загружаются лишние поля")
            
            return query_analysis
    
    def analyze_middleware(self) -> Dict[str, Any]:
        """Анализ middleware"""
        middleware_analysis = {
            "total_middleware": len(settings.MIDDLEWARE),
            "middleware_list": settings.MIDDLEWARE,
            "performance_impact": {},
            "recommendations": []
        }
        
        # Анализ влияния на производительность
        performance_heavy = [
            'django.middleware.security.SecurityMiddleware',
            'django.middleware.csrf.CsrfViewMiddleware',
            'django.contrib.sessions.middleware.SessionMiddleware',
            'django.contrib.auth.middleware.AuthenticationMiddleware',
            'django.contrib.messages.middleware.MessageMiddleware'
        ]
        
        for middleware in settings.MIDDLEWARE:
            if middleware in performance_heavy:
                middleware_analysis["performance_impact"][middleware] = "high"
            else:
                middleware_analysis["performance_impact"][middleware] = "medium"
        
        # Рекомендации
        if len(settings.MIDDLEWARE) > 10:
            middleware_analysis["recommendations"].append("Слишком много middleware - проверьте необходимость каждого")
        
        if 'django.middleware.cache.CacheMiddleware' not in settings.MIDDLEWARE:
            middleware_analysis["recommendations"].append("Отсутствует кэширование - добавьте CacheMiddleware")
        
        return middleware_analysis
    
    def analyze_settings(self) -> Dict[str, Any]:
        """Анализ настроек Django"""
        settings_analysis = {
            "debug_mode": settings.DEBUG,
            "database_engine": settings.DATABASES['default']['ENGINE'],
            "cache_backend": getattr(settings, 'CACHES', {}).get('default', {}).get('BACKEND', 'None'),
            "static_files_serving": getattr(settings, 'STATICFILES_DIRS', []),
            "media_files_serving": bool(getattr(settings, 'MEDIA_URL', None)),
            "security_settings": {},
            "performance_settings": {},
            "recommendations": []
        }
        
        # Анализ настроек безопасности
        security_settings = [
            'SECURE_SSL_REDIRECT',
            'SECURE_HSTS_SECONDS',
            'SECURE_HSTS_INCLUDE_SUBDOMAINS',
            'SECURE_HSTS_PRELOAD',
            'SECURE_CONTENT_TYPE_NOSNIFF',
            'SECURE_BROWSER_XSS_FILTER',
            'X_FRAME_OPTIONS',
            'SECURE_REFERRER_POLICY'
        ]
        
        for setting in security_settings:
            settings_analysis["security_settings"][setting] = getattr(settings, setting, None)
        
        # Анализ настроек производительности
        performance_settings = [
            'USE_TZ',
            'USE_I18N',
            'USE_L10N',
            'LOGGING',
            'EMAIL_BACKEND',
            'SESSION_ENGINE',
            'SESSION_CACHE_ALIAS'
        ]
        
        for setting in performance_settings:
            settings_analysis["performance_settings"][setting] = getattr(settings, setting, None)
        
        # Рекомендации
        if settings.DEBUG:
            settings_analysis["recommendations"].append("DEBUG=True в продакшене - отключите для производительности")
        
        if not settings_analysis["cache_backend"] or settings_analysis["cache_backend"] == 'None':
            settings_analysis["recommendations"].append("Кэширование не настроено - настройте Redis или Memcached")
        
        if settings_analysis["database_engine"] == 'django.db.backends.sqlite3':
            settings_analysis["recommendations"].append("SQLite в продакшене - перейдите на PostgreSQL или MySQL")
        
        return settings_analysis
    
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
                    urls_file = os.path.join(root, file)
                    app_name = os.path.basename(os.path.dirname(urls_file))
                    
                    with open(urls_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Подсчет URL паттернов
                    url_patterns = re.findall(r'path\s*\(|url\s*\(', content)
                    urls_analysis["urls_by_app"][app_name] = len(url_patterns)
                    urls_analysis["total_urls"] += len(url_patterns)
                    
                    # Поиск проблемных паттернов
                    if 'include(' in content and 'namespace=' not in content:
                        urls_analysis["problematic_urls"].append(f"{app_name}: отсутствует namespace")
                    
                    if 're_path(' in content:
                        urls_analysis["problematic_urls"].append(f"{app_name}: использует регулярные выражения")
        
        # Рекомендации
        if urls_analysis["total_urls"] > 100:
            urls_analysis["recommendations"].append("Слишком много URL - рассмотрите группировку по приложениям")
        
        return urls_analysis
    
    def run_full_analysis(self) -> Dict[str, Any]:
        """Запуск полного анализа"""
        start_time = time.time()
        
        self.analysis_results = {
            "models": self.analyze_models(),
            "views": self.analyze_views(),
            "queries": self.analyze_queries(),
            "middleware": self.analyze_middleware(),
            "settings": self.analyze_settings(),
            "urls": self.analyze_urls(),
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
        
        # Рекомендации по запросам
        queries = self.analysis_results.get("queries", {})
        if queries.get("recommendations"):
            recommendations.extend(queries["recommendations"])
        
        # Рекомендации по middleware
        middleware = self.analysis_results.get("middleware", {})
        if middleware.get("recommendations"):
            recommendations.extend(middleware["recommendations"])
        
        # Рекомендации по настройкам
        settings = self.analysis_results.get("settings", {})
        if settings.get("recommendations"):
            recommendations.extend(settings["recommendations"])
        
        return recommendations

def main():
    """Основная функция для запуска анализа"""
    project_root = "/Users/zainllw0w/PycharmProjects/TwoComms/twocomms"
    
    analyzer = DjangoPerformanceAnalyzer(project_root)
    results = analyzer.run_full_analysis()
    recommendations = analyzer.generate_recommendations()
    
    # Сохранение результатов
    output_file = "/Users/zainllw0w/PycharmProjects/TwoComms/django_performance_analysis.json"
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
