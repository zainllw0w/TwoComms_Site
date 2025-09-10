#!/usr/bin/env python3
"""
Report Generator
Генерирует детальные отчеты по анализу производительности
"""

import os
import json
import time
from datetime import datetime
from typing import Dict, List, Any
from pathlib import Path

class PerformanceReportGenerator:
    def __init__(self, output_dir: str = "/Users/zainllw0w/PycharmProjects/TwoComms"):
        self.output_dir = output_dir
        self.reports = {}
        
    def load_analysis_data(self) -> Dict[str, Any]:
        """Загрузка всех данных анализа"""
        analysis_files = {
            "css": "css_performance_analysis.json",
            "javascript": "js_performance_analysis.json",
            "django": "django_performance_analysis.json",
            "media": "media_performance_analysis.json",
            "network": "network_performance_analysis.json",
            "ai": "ai_performance_analysis.json"
        }
        
        analysis_data = {}
        for analysis_type, filename in analysis_files.items():
            file_path = os.path.join(self.output_dir, filename)
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    analysis_data[analysis_type] = json.load(f)
            else:
                print(f"Предупреждение: Файл {filename} не найден")
        
        return analysis_data
    
    def generate_executive_summary(self, analysis_data: Dict[str, Any]) -> str:
        """Генерация исполнительного резюме"""
        summary = []
        summary.append("# Исполнительное резюме анализа производительности")
        summary.append("")
        summary.append(f"**Дата анализа:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        summary.append("")
        
        # Общая статистика
        total_issues = 0
        critical_issues = 0
        optimization_potential = []
        
        for analysis_type, data in analysis_data.items():
            if "recommendations" in data:
                total_issues += len(data["recommendations"])
                
                # Подсчет критических проблем
                analysis_results = data.get("analysis_results", {})
                if analysis_type == "css":
                    problematic_images = analysis_results.get("problematic_images", [])
                    critical_issues += len(problematic_images)
                elif analysis_type == "javascript":
                    performance_issues = analysis_results.get("performance_patterns", {}).get("performance_issues", {})
                    critical_issues += performance_issues.get("eval_usage", 0)
                elif analysis_type == "django":
                    problematic_models = analysis_results.get("models", {}).get("problematic_models", [])
                    critical_issues += len(problematic_models)
        
        summary.append(f"**Общее количество проблем:** {total_issues}")
        summary.append(f"**Критические проблемы:** {critical_issues}")
        summary.append("")
        
        # Топ проблемы
        summary.append("## Топ-5 критических проблем:")
        summary.append("")
        
        top_issues = []
        for analysis_type, data in analysis_data.items():
            if "recommendations" in data:
                for rec in data["recommendations"][:2]:  # Берем первые 2 из каждого типа
                    top_issues.append(f"- **{analysis_type.upper()}:** {rec}")
        
        summary.extend(top_issues[:5])
        summary.append("")
        
        # Потенциал оптимизации
        summary.append("## Потенциал оптимизации:")
        summary.append("")
        
        if "media" in analysis_data:
            media_data = analysis_data["media"]["analysis_results"]
            if "images" in media_data:
                webp_savings = media_data["images"].get("optimization_potential", {}).get("webp_savings_mb", 0)
                if webp_savings > 0:
                    summary.append(f"- **Экономия от WebP:** {webp_savings} MB")
        
        if "css" in analysis_data:
            css_data = analysis_data["css"]["analysis_results"]
            if "file_info" in css_data:
                size_kb = css_data["file_info"].get("size_kb", 0)
                if size_kb > 100:
                    summary.append(f"- **CSS минификация:** экономия ~{size_kb * 0.3:.1f} KB")
        
        summary.append("")
        summary.append("## Рекомендации по приоритету:")
        summary.append("")
        summary.append("1. **Критический уровень:** Исправить проблемы безопасности и критические ошибки")
        summary.append("2. **Высокий уровень:** Оптимизировать изображения и CSS")
        summary.append("3. **Средний уровень:** Улучшить JavaScript производительность")
        summary.append("4. **Низкий уровень:** Настроить кэширование и мониторинг")
        
        return "\n".join(summary)
    
    def generate_css_report(self, css_data: Dict[str, Any]) -> str:
        """Генерация отчета по CSS"""
        report = []
        report.append("# Анализ производительности CSS")
        report.append("")
        
        analysis_results = css_data.get("analysis_results", {})
        
        # Информация о файле
        file_info = analysis_results.get("file_info", {})
        if file_info:
            report.append("## Информация о файле")
            report.append("")
            report.append(f"- **Размер файла:** {file_info.get('size_kb', 0):.1f} KB")
            report.append(f"- **Сжатый размер:** {file_info.get('compressed_size_kb', 0):.1f} KB")
            report.append(f"- **Коэффициент сжатия:** {file_info.get('compression_ratio', 0):.3f}")
            report.append(f"- **Экономия от сжатия:** {file_info.get('compression_savings_percent', 0):.1f}%")
            report.append("")
        
        # Анализ селекторов
        selectors = analysis_results.get("selectors", {})
        if selectors:
            report.append("## Анализ селекторов")
            report.append("")
            report.append(f"- **Всего правил:** {selectors.get('total_rules', 0)}")
            report.append(f"- **Сложных селекторов:** {selectors.get('complex_selectors_count', 0)}")
            report.append(f"- **Средняя сложность:** {selectors.get('average_selector_complexity', 0):.1f}%")
            report.append("")
            
            selector_stats = selectors.get("selector_stats", {})
            if selector_stats:
                report.append("### Статистика селекторов:")
                for selector_type, count in selector_stats.items():
                    report.append(f"- **{selector_type}:** {count}")
                report.append("")
        
        # Анализ свойств
        properties = analysis_results.get("properties", {})
        if properties:
            report.append("## Анализ CSS свойств")
            report.append("")
            report.append(f"- **Всего свойств:** {properties.get('total_properties', 0)}")
            report.append(f"- **Уникальных свойств:** {properties.get('unique_properties', 0)}")
            report.append(f"- **Процент дублирования:** {properties.get('duplication_ratio', 0):.1f}%")
            report.append("")
            
            perf_props = properties.get("performance_heavy_properties", {})
            if perf_props:
                report.append("### Проблемные свойства для производительности:")
                for prop, count in perf_props.items():
                    if count > 0:
                        report.append(f"- **{prop}:** {count} использований")
                report.append("")
        
        # Неиспользуемый CSS
        unused_css = analysis_results.get("unused_css", {})
        if unused_css:
            report.append("## Анализ неиспользуемого CSS")
            report.append("")
            report.append(f"- **Всего селекторов:** {unused_css.get('total_selectors', 0)}")
            report.append(f"- **Используемых селекторов:** {unused_css.get('used_selectors', 0)}")
            report.append(f"- **Неиспользуемых селекторов:** {unused_css.get('unused_selectors', 0)}")
            report.append(f"- **Процент использования:** {unused_css.get('usage_percentage', 0):.1f}%")
            report.append("")
        
        # Рекомендации
        recommendations = css_data.get("recommendations", [])
        if recommendations:
            report.append("## Рекомендации по оптимизации")
            report.append("")
            for i, rec in enumerate(recommendations, 1):
                report.append(f"{i}. {rec}")
            report.append("")
        
        return "\n".join(report)
    
    def generate_javascript_report(self, js_data: Dict[str, Any]) -> str:
        """Генерация отчета по JavaScript"""
        report = []
        report.append("# Анализ производительности JavaScript")
        report.append("")
        
        analysis_results = js_data.get("analysis_results", {})
        
        # Информация о файле
        file_info = analysis_results.get("file_info", {})
        if file_info:
            report.append("## Информация о файле")
            report.append("")
            report.append(f"- **Размер файла:** {file_info.get('size_kb', 0):.1f} KB")
            report.append(f"- **Сжатый размер:** {file_info.get('compressed_size_kb', 0):.1f} KB")
            report.append(f"- **Экономия от сжатия:** {file_info.get('compression_savings_percent', 0):.1f}%")
            report.append("")
        
        # DOM операции
        dom_ops = analysis_results.get("dom_operations", {})
        if dom_ops:
            report.append("## Анализ DOM операций")
            report.append("")
            report.append(f"- **Всего DOM операций:** {dom_ops.get('total_dom_operations', 0)}")
            report.append(f"- **Проблемных паттернов:** {dom_ops.get('total_problematic_patterns', 0)}")
            report.append("")
            
            dom_operations = dom_ops.get("dom_operations", {})
            if dom_operations:
                report.append("### Статистика DOM операций:")
                for op, count in dom_operations.items():
                    if count > 0:
                        report.append(f"- **{op}:** {count}")
                report.append("")
            
            problematic = dom_ops.get("problematic_patterns", {})
            if problematic:
                report.append("### Проблемные паттерны:")
                for pattern, count in problematic.items():
                    if count > 0:
                        report.append(f"- **{pattern}:** {count}")
                report.append("")
        
        # Функции
        functions = analysis_results.get("functions", {})
        if functions:
            report.append("## Анализ функций")
            report.append("")
            report.append(f"- **Всего функций:** {functions.get('total_functions', 0)}")
            report.append(f"- **Сложных функций:** {functions.get('complex_functions', 0)}")
            report.append(f"- **Длинных функций:** {functions.get('long_functions', 0)}")
            report.append(f"- **Средняя длина функции:** {functions.get('average_function_length', 0):.1f} символов")
            report.append("")
        
        # Производительность
        performance = analysis_results.get("performance_patterns", {})
        if performance:
            report.append("## Анализ производительности")
            report.append("")
            
            issues = performance.get("performance_issues", {})
            if issues:
                report.append("### Проблемы производительности:")
                for issue, count in issues.items():
                    if count > 0:
                        report.append(f"- **{issue}:** {count}")
                report.append("")
            
            optimizations = performance.get("optimizations", {})
            if optimizations:
                report.append("### Используемые оптимизации:")
                for opt, count in optimizations.items():
                    if count > 0:
                        report.append(f"- **{opt}:** {count}")
                report.append("")
        
        # Память
        memory = analysis_results.get("memory_usage", {})
        if memory:
            report.append("## Анализ использования памяти")
            report.append("")
            report.append(f"- **Всего проблем с памятью:** {memory.get('total_memory_issues', 0)}")
            report.append("")
            
            memory_issues = memory.get("memory_issues", {})
            if memory_issues:
                report.append("### Проблемы с памятью:")
                for issue, count in memory_issues.items():
                    if count > 0:
                        report.append(f"- **{issue}:** {count}")
                report.append("")
        
        # Рекомендации
        recommendations = js_data.get("recommendations", [])
        if recommendations:
            report.append("## Рекомендации по оптимизации")
            report.append("")
            for i, rec in enumerate(recommendations, 1):
                report.append(f"{i}. {rec}")
            report.append("")
        
        return "\n".join(report)
    
    def generate_django_report(self, django_data: Dict[str, Any]) -> str:
        """Генерация отчета по Django"""
        report = []
        report.append("# Анализ производительности Django")
        report.append("")
        
        analysis_results = django_data.get("analysis_results", {})
        
        # Модели
        models = analysis_results.get("models", {})
        if models:
            report.append("## Анализ моделей")
            report.append("")
            report.append(f"- **Всего моделей:** {models.get('total_models', 0)}")
            report.append(f"- **Всего полей:** {models.get('total_fields', 0)}")
            report.append(f"- **Среднее количество полей на модель:** {models.get('average_fields_per_model', 0):.1f}")
            report.append(f"- **Проблемных моделей:** {len(models.get('problematic_models', []))}")
            report.append("")
            
            if models.get('problematic_models'):
                report.append("### Проблемные модели:")
                for model in models['problematic_models']:
                    report.append(f"- {model}")
                report.append("")
        
        # Views
        views = analysis_results.get("views", {})
        if views:
            report.append("## Анализ Views")
            report.append("")
            report.append(f"- **Всего views:** {views.get('total_views', 0)}")
            report.append(f"- **Проблемных views:** {len(views.get('problematic_views', []))}")
            report.append("")
            
            if views.get('problematic_views'):
                report.append("### Проблемные views:")
                for view in views['problematic_views']:
                    report.append(f"- {view}")
                report.append("")
        
        # Запросы к БД
        queries = analysis_results.get("queries", {})
        if queries:
            report.append("## Анализ запросов к БД")
            report.append("")
            
            query_patterns = queries.get("query_patterns", {})
            if query_patterns:
                report.append("### Используемые паттерны оптимизации:")
                for pattern, count in query_patterns.items():
                    if count > 0:
                        report.append(f"- **{pattern}:** {count}")
                report.append("")
            
            recommendations = queries.get("recommendations", [])
            if recommendations:
                report.append("### Рекомендации по БД:")
                for rec in recommendations:
                    report.append(f"- {rec}")
                report.append("")
        
        # Middleware
        middleware = analysis_results.get("middleware", {})
        if middleware:
            report.append("## Анализ Middleware")
            report.append("")
            report.append(f"- **Всего middleware:** {middleware.get('total_middleware', 0)}")
            report.append("")
            
            recommendations = middleware.get("recommendations", [])
            if recommendations:
                report.append("### Рекомендации по middleware:")
                for rec in recommendations:
                    report.append(f"- {rec}")
                report.append("")
        
        # Настройки
        settings = analysis_results.get("settings", {})
        if settings:
            report.append("## Анализ настроек")
            report.append("")
            report.append(f"- **Режим отладки:** {settings.get('debug_mode', 'Неизвестно')}")
            report.append(f"- **Движок БД:** {settings.get('database_engine', 'Неизвестно')}")
            report.append(f"- **Кэш:** {settings.get('cache_backend', 'Не настроен')}")
            report.append("")
            
            recommendations = settings.get("recommendations", [])
            if recommendations:
                report.append("### Рекомендации по настройкам:")
                for rec in recommendations:
                    report.append(f"- {rec}")
                report.append("")
        
        # Рекомендации
        recommendations = django_data.get("recommendations", [])
        if recommendations:
            report.append("## Общие рекомендации по оптимизации")
            report.append("")
            for i, rec in enumerate(recommendations, 1):
                report.append(f"{i}. {rec}")
            report.append("")
        
        return "\n".join(report)
    
    def generate_media_report(self, media_data: Dict[str, Any]) -> str:
        """Генерация отчета по медиа файлам"""
        report = []
        report.append("# Анализ производительности медиа файлов")
        report.append("")
        
        analysis_results = media_data.get("analysis_results", {})
        
        # Изображения
        images = analysis_results.get("images", {})
        if images:
            report.append("## Анализ изображений")
            report.append("")
            report.append(f"- **Всего изображений:** {images.get('total_images', 0)}")
            report.append(f"- **Общий размер:** {images.get('total_size_bytes', 0) / (1024*1024):.1f} MB")
            report.append("")
            
            formats = images.get("formats", {})
            if formats:
                report.append("### Форматы изображений:")
                for format_ext, data in formats.items():
                    count = data.get("count", 0)
                    size_mb = data.get("total_size", 0) / (1024*1024)
                    report.append(f"- **{format_ext}:** {count} файлов, {size_mb:.1f} MB")
                report.append("")
            
            sizes = images.get("sizes", {})
            if sizes:
                report.append("### Размеры изображений:")
                for size_category, data in sizes.items():
                    count = data.get("count", 0)
                    size_mb = data.get("total_size", 0) / (1024*1024)
                    report.append(f"- **{size_category}:** {count} файлов, {size_mb:.1f} MB")
                report.append("")
            
            optimization = images.get("optimization_potential", {})
            if optimization:
                report.append("### Потенциал оптимизации:")
                report.append(f"- **Общий размер:** {optimization.get('total_size_mb', 0):.1f} MB")
                report.append(f"- **Экономия от WebP:** {optimization.get('webp_savings_mb', 0):.1f} MB ({optimization.get('webp_savings_percent', 0):.1f}%)")
                report.append(f"- **Экономия от сжатия:** {optimization.get('compression_savings_mb', 0):.1f} MB")
                report.append("")
            
            problematic = images.get("problematic_images", [])
            if problematic:
                report.append(f"### Проблемных изображений: {len(problematic)}")
                for img in problematic[:5]:  # Показываем первые 5
                    report.append(f"- **{img.get('file', 'Unknown')}:** {img.get('file_size_kb', 0):.1f} KB")
                    for issue in img.get('issues', []):
                        report.append(f"  - {issue}")
                report.append("")
        
        # Другие медиа файлы
        other_media = analysis_results.get("other_media", {})
        if other_media:
            report.append("## Анализ других медиа файлов")
            report.append("")
            report.append(f"- **Всего файлов:** {other_media.get('total_files', 0)}")
            report.append(f"- **Общий размер:** {other_media.get('total_size_bytes', 0) / (1024*1024):.1f} MB")
            report.append("")
            
            file_types = other_media.get("file_types", {})
            if file_types:
                report.append("### Типы файлов:")
                for file_type, data in file_types.items():
                    count = data.get("count", 0)
                    size_mb = data.get("total_size", 0) / (1024*1024)
                    report.append(f"- **{file_type}:** {count} файлов, {size_mb:.1f} MB")
                report.append("")
            
            large_files = other_media.get("large_files", [])
            if large_files:
                report.append(f"### Больших файлов (>10MB): {len(large_files)}")
                for file_info in large_files:
                    report.append(f"- **{file_info.get('file', 'Unknown')}:** {file_info.get('size_mb', 0):.1f} MB")
                report.append("")
        
        # Использование
        usage = analysis_results.get("usage", {})
        if usage:
            report.append("## Анализ использования")
            report.append("")
            report.append(f"- **Используемых файлов:** {len(usage.get('referenced_files', []))}")
            report.append(f"- **Неиспользуемых файлов:** {len(usage.get('unreferenced_files', []))}")
            report.append("")
            
            usage_patterns = usage.get("usage_patterns", {})
            if usage_patterns:
                report.append("### Паттерны использования:")
                for pattern, count in usage_patterns.items():
                    report.append(f"- **{pattern}:** {count}")
                report.append("")
        
        # Рекомендации
        recommendations = media_data.get("recommendations", [])
        if recommendations:
            report.append("## Рекомендации по оптимизации")
            report.append("")
            for i, rec in enumerate(recommendations, 1):
                report.append(f"{i}. {rec}")
            report.append("")
        
        return "\n".join(report)
    
    def generate_network_report(self, network_data: Dict[str, Any]) -> str:
        """Генерация отчета по сетевой производительности"""
        report = []
        report.append("# Анализ сетевой производительности")
        report.append("")
        
        analysis_results = network_data.get("analysis_results", {})
        
        # Внешние зависимости
        dependencies = analysis_results.get("external_dependencies", {})
        if dependencies:
            report.append("## Внешние зависимости")
            report.append("")
            report.append(f"- **Всего внешних запросов:** {dependencies.get('total_external_requests', 0)}")
            report.append(f"- **CDN ресурсов:** {len(dependencies.get('cdn_resources', []))}")
            report.append(f"- **Внешних API:** {len(dependencies.get('external_apis', []))}")
            report.append(f"- **Шрифтов:** {len(dependencies.get('fonts', []))}")
            report.append(f"- **Блокирующих ресурсов:** {len(dependencies.get('blocking_resources', []))}")
            report.append("")
        
        # API производительность
        api_performance = analysis_results.get("api_performance", {})
        if api_performance:
            report.append("## Производительность API")
            report.append("")
            
            endpoints = api_performance.get("endpoints", [])
            if endpoints:
                report.append(f"- **Протестированных эндпоинтов:** {len(endpoints)}")
                
                # Статистика по времени ответа
                response_times = [ep.get("response_time", 0) for ep in endpoints]
                if response_times:
                    avg_time = sum(response_times) / len(response_times)
                    max_time = max(response_times)
                    report.append(f"- **Среднее время ответа:** {avg_time:.3f} сек")
                    report.append(f"- **Максимальное время ответа:** {max_time:.3f} сек")
                report.append("")
                
                # Статистика по кодам ответов
                status_codes = api_performance.get("status_codes", {})
                if status_codes:
                    report.append("### Коды ответов:")
                    for code, count in status_codes.items():
                        report.append(f"- **{code}:** {count}")
                    report.append("")
            
            performance_issues = api_performance.get("performance_issues", [])
            if performance_issues:
                report.append(f"### Проблем производительности: {len(performance_issues)}")
                for issue in performance_issues:
                    report.append(f"- **{issue.get('endpoint', 'Unknown')}:** {issue.get('issue', 'Unknown')}")
                report.append("")
        
        # SSL безопасность
        ssl_security = analysis_results.get("ssl_security", {})
        if ssl_security:
            report.append("## SSL безопасность")
            report.append("")
            report.append(f"- **SSL включен:** {ssl_security.get('ssl_enabled', False)}")
            
            security_issues = ssl_security.get("security_issues", [])
            if security_issues:
                report.append(f"- **Проблем безопасности:** {len(security_issues)}")
                for issue in security_issues:
                    report.append(f"- {issue.get('issue', 'Unknown')}")
            report.append("")
        
        # Кэширование
        caching = analysis_results.get("caching_headers", {})
        if caching:
            report.append("## Анализ кэширования")
            report.append("")
            
            caching_issues = caching.get("caching_issues", [])
            if caching_issues:
                report.append(f"- **Проблем с кэшированием:** {len(caching_issues)}")
                for issue in caching_issues:
                    report.append(f"- **{issue.get('endpoint', 'Unknown')}:** {issue.get('issue', 'Unknown')}")
            report.append("")
        
        # Сжатие
        compression = analysis_results.get("compression", {})
        if compression:
            report.append("## Анализ сжатия")
            report.append("")
            
            compression_issues = compression.get("compression_issues", [])
            if compression_issues:
                report.append(f"- **Проблем со сжатием:** {len(compression_issues)}")
                for issue in compression_issues:
                    report.append(f"- **{issue.get('endpoint', 'Unknown')}:** {issue.get('issue', 'Unknown')}")
            report.append("")
        
        # Рекомендации
        recommendations = network_data.get("recommendations", [])
        if recommendations:
            report.append("## Рекомендации по оптимизации")
            report.append("")
            for i, rec in enumerate(recommendations, 1):
                report.append(f"{i}. {rec}")
            report.append("")
        
        return "\n".join(report)
    
    def generate_ai_report(self, ai_data: Dict[str, Any]) -> str:
        """Генерация отчета по AI анализу"""
        report = []
        report.append("# AI анализ производительности")
        report.append("")
        
        analysis_results = ai_data.get("analysis_results", {})
        ai_analysis = analysis_results.get("ai_analysis", {})
        
        # CSS анализ
        css_analysis = ai_analysis.get("css", {})
        if css_analysis and "error" not in css_analysis:
            report.append("## AI анализ CSS")
            report.append("")
            
            css_issues = css_analysis.get("css_issues", [])
            if css_issues:
                report.append(f"### Найдено проблем: {len(css_issues)}")
                for issue in css_issues[:5]:  # Показываем первые 5
                    report.append(f"- **{issue.get('type', 'Unknown')}:** {issue.get('description', 'No description')}")
                    report.append(f"  - Серьезность: {issue.get('severity', 'Unknown')}")
                    report.append(f"  - Исправление: {issue.get('fix', 'No fix provided')}")
                report.append("")
            
            performance_score = css_analysis.get("performance_score")
            if performance_score:
                report.append(f"### Оценка производительности CSS: {performance_score}/10")
                report.append("")
        
        # JavaScript анализ
        js_analysis = ai_analysis.get("javascript", {})
        if js_analysis and "error" not in js_analysis:
            report.append("## AI анализ JavaScript")
            report.append("")
            
            js_issues = js_analysis.get("js_issues", [])
            if js_issues:
                report.append(f"### Найдено проблем: {len(js_issues)}")
                for issue in js_issues[:5]:  # Показываем первые 5
                    report.append(f"- **{issue.get('type', 'Unknown')}:** {issue.get('description', 'No description')}")
                    report.append(f"  - Серьезность: {issue.get('severity', 'Unknown')}")
                report.append("")
            
            performance_score = js_analysis.get("performance_score")
            if performance_score:
                report.append(f"### Оценка производительности JS: {performance_score}/10")
                report.append("")
        
        # Django анализ
        django_analysis = ai_analysis.get("django_views", {})
        if django_analysis and "error" not in django_analysis:
            report.append("## AI анализ Django")
            report.append("")
            
            django_issues = django_analysis.get("django_issues", [])
            if django_issues:
                report.append(f"### Найдено проблем: {len(django_issues)}")
                for issue in django_issues[:5]:  # Показываем первые 5
                    report.append(f"- **{issue.get('type', 'Unknown')}:** {issue.get('description', 'No description')}")
                    report.append(f"  - Серьезность: {issue.get('severity', 'Unknown')}")
                report.append("")
            
            performance_score = django_analysis.get("performance_score")
            if performance_score:
                report.append(f"### Оценка производительности Django: {performance_score}/10")
                report.append("")
        
        # Комплексные рекомендации
        comprehensive = ai_analysis.get("comprehensive_recommendations", {})
        if comprehensive and "error" not in comprehensive:
            report.append("## Комплексные рекомендации AI")
            report.append("")
            
            priority_issues = comprehensive.get("priority_issues", [])
            if priority_issues:
                report.append("### Приоритетные проблемы:")
                for issue in priority_issues:
                    report.append(f"- **{issue.get('issue', 'Unknown')}** (Приоритет: {issue.get('priority', 'Unknown')})")
                    report.append(f"  - Влияние: {issue.get('impact', 'Unknown')}")
                    report.append(f"  - Решение: {issue.get('solution', 'No solution provided')}")
                report.append("")
            
            optimization_roadmap = comprehensive.get("optimization_roadmap", [])
            if optimization_roadmap:
                report.append("### План оптимизации:")
                for phase in optimization_roadmap:
                    report.append(f"- **{phase.get('phase', 'Unknown')}:**")
                    report.append(f"  - Ожидаемое улучшение: {phase.get('expected_improvement', 'Unknown')}")
                    report.append(f"  - Время: {phase.get('time_estimate', 'Unknown')}")
                report.append("")
            
            performance_metrics = comprehensive.get("performance_metrics", {})
            if performance_metrics:
                report.append("### Метрики производительности:")
                report.append(f"- **Текущая оценка:** {performance_metrics.get('current_score', 'Unknown')}/10")
                report.append(f"- **Потенциальная оценка:** {performance_metrics.get('potential_score', 'Unknown')}/10")
                
                quick_wins = performance_metrics.get("quick_wins", [])
                if quick_wins:
                    report.append("- **Быстрые победы:**")
                    for win in quick_wins:
                        report.append(f"  - {win}")
                report.append("")
        
        return "\n".join(report)
    
    def generate_comprehensive_report(self) -> str:
        """Генерация комплексного отчета"""
        print("Загружаю данные анализа...")
        analysis_data = self.load_analysis_data()
        
        if not analysis_data:
            return "# Ошибка\n\nДанные анализа не найдены. Запустите сначала анализ производительности."
        
        print("Генерирую отчеты...")
        
        # Собираем все отчеты
        reports = []
        
        # Исполнительное резюме
        reports.append(self.generate_executive_summary(analysis_data))
        reports.append("\n---\n")
        
        # Детальные отчеты по каждому компоненту
        if "css" in analysis_data:
            reports.append(self.generate_css_report(analysis_data["css"]))
            reports.append("\n---\n")
        
        if "javascript" in analysis_data:
            reports.append(self.generate_javascript_report(analysis_data["javascript"]))
            reports.append("\n---\n")
        
        if "django" in analysis_data:
            reports.append(self.generate_django_report(analysis_data["django"]))
            reports.append("\n---\n")
        
        if "media" in analysis_data:
            reports.append(self.generate_media_report(analysis_data["media"]))
            reports.append("\n---\n")
        
        if "network" in analysis_data:
            reports.append(self.generate_network_report(analysis_data["network"]))
            reports.append("\n---\n")
        
        if "ai" in analysis_data:
            reports.append(self.generate_ai_report(analysis_data["ai"]))
            reports.append("\n---\n")
        
        # Заключение
        reports.append("# Заключение")
        reports.append("")
        reports.append("Данный отчет содержит детальный анализ производительности веб-сайта TwoComms.")
        reports.append("Рекомендуется приоритизировать исправление критических проблем и постепенно")
        reports.append("внедрять оптимизации согласно предложенному плану.")
        reports.append("")
        reports.append(f"**Дата генерации отчета:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        return "\n".join(reports)
    
    def save_report(self, report_content: str, filename: str = None) -> str:
        """Сохранение отчета в файл"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"performance_analysis_report_{timestamp}.md"
        
        file_path = os.path.join(self.output_dir, filename)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        return file_path

def main():
    """Основная функция для генерации отчета"""
    generator = PerformanceReportGenerator()
    
    print("Генерирую комплексный отчет по производительности...")
    report_content = generator.generate_comprehensive_report()
    
    print("Сохраняю отчет...")
    report_file = generator.save_report(report_content)
    
    print(f"Отчет сохранен: {report_file}")
    print(f"Размер отчета: {len(report_content)} символов")

if __name__ == "__main__":
    main()
