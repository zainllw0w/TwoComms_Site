#!/usr/bin/env python3
"""
JavaScript Performance Analyzer
Анализирует JavaScript файлы на предмет производительности
"""

import os
import re
import json
import gzip
from pathlib import Path
from typing import Dict, List, Any, Set
import time
import ast

class JavaScriptPerformanceAnalyzer:
    def __init__(self, js_file_path: str):
        self.js_file_path = js_file_path
        self.analysis_results = {}
        
    def analyze_file_size(self) -> Dict[str, Any]:
        """Анализ размера файла"""
        file_path = Path(self.js_file_path)
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
    
    def analyze_dom_operations(self) -> Dict[str, Any]:
        """Анализ DOM операций"""
        with open(self.js_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Поиск DOM операций
        dom_operations = {
            'getElementById': len(re.findall(r'getElementById\s*\(', content)),
            'getElementsByClassName': len(re.findall(r'getElementsByClassName\s*\(', content)),
            'getElementsByTagName': len(re.findall(r'getElementsByTagName\s*\(', content)),
            'querySelector': len(re.findall(r'querySelector\s*\(', content)),
            'querySelectorAll': len(re.findall(r'querySelectorAll\s*\(', content)),
            'createElement': len(re.findall(r'createElement\s*\(', content)),
            'appendChild': len(re.findall(r'appendChild\s*\(', content)),
            'removeChild': len(re.findall(r'removeChild\s*\(', content)),
            'innerHTML': len(re.findall(r'\.innerHTML\s*=', content)),
            'textContent': len(re.findall(r'\.textContent\s*=', content)),
            'style': len(re.findall(r'\.style\.', content)),
            'addEventListener': len(re.findall(r'addEventListener\s*\(', content)),
            'removeEventListener': len(re.findall(r'removeEventListener\s*\(', content))
        }
        
        # Поиск проблемных паттернов
        problematic_patterns = {
            'dom_in_loops': len(re.findall(r'for\s*\([^}]*\)\s*\{[^}]*querySelector', content, re.DOTALL)),
            'innerHTML_in_loops': len(re.findall(r'for\s*\([^}]*\)\s*\{[^}]*innerHTML', content, re.DOTALL)),
            'style_in_loops': len(re.findall(r'for\s*\([^}]*\)\s*\{[^}]*\.style\.', content, re.DOTALL)),
            'nested_queries': len(re.findall(r'querySelector.*querySelector', content)),
            'reflow_triggers': len(re.findall(r'\.(offsetWidth|offsetHeight|scrollTop|scrollLeft)', content))
        }
        
        return {
            "dom_operations": dom_operations,
            "problematic_patterns": problematic_patterns,
            "total_dom_operations": sum(dom_operations.values()),
            "total_problematic_patterns": sum(problematic_patterns.values())
        }
    
    def analyze_functions(self) -> Dict[str, Any]:
        """Анализ функций"""
        with open(self.js_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Поиск функций
        function_patterns = {
            'function_declarations': len(re.findall(r'function\s+\w+\s*\(', content)),
            'arrow_functions': len(re.findall(r'=>\s*\{', content)),
            'function_expressions': len(re.findall(r'=\s*function\s*\(', content)),
            'async_functions': len(re.findall(r'async\s+function', content)),
            'generator_functions': len(re.findall(r'function\s*\*', content))
        }
        
        # Анализ сложности функций
        functions = re.findall(r'function\s+\w+\s*\([^)]*\)\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}', content, re.DOTALL)
        complex_functions = 0
        long_functions = 0
        
        for func_body in functions:
            lines = func_body.count('\n')
            if lines > 20:
                long_functions += 1
            if len(func_body) > 500:
                complex_functions += 1
        
        return {
            "function_types": function_patterns,
            "total_functions": sum(function_patterns.values()),
            "complex_functions": complex_functions,
            "long_functions": long_functions,
            "average_function_length": round(sum(len(f) for f in functions) / len(functions), 2) if functions else 0
        }
    
    def analyze_performance_patterns(self) -> Dict[str, Any]:
        """Анализ паттернов производительности"""
        with open(self.js_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Поиск проблемных паттернов
        performance_issues = {
            'synchronous_requests': len(re.findall(r'XMLHttpRequest.*open.*false', content)),
            'eval_usage': len(re.findall(r'\beval\s*\(', content)),
            'with_statements': len(re.findall(r'\bwith\s*\(', content)),
            'document_write': len(re.findall(r'document\.write\s*\(', content)),
            'innerHTML_concatenation': len(re.findall(r'innerHTML\s*\+=', content)),
            'string_concatenation_in_loops': len(re.findall(r'for\s*\([^}]*\)\s*\{[^}]*\+=', content, re.DOTALL)),
            'global_variables': len(re.findall(r'var\s+\w+\s*=', content)) - len(re.findall(r'var\s+\w+\s*=.*function', content)),
            'console_logs': len(re.findall(r'console\.log\s*\(', content)),
            'debugger_statements': len(re.findall(r'debugger\s*;', content))
        }
        
        # Поиск оптимизаций
        optimizations = {
            'requestAnimationFrame': len(re.findall(r'requestAnimationFrame\s*\(', content)),
            'debounce': len(re.findall(r'debounce\s*\(', content)),
            'throttle': len(re.findall(r'throttle\s*\(', content)),
            'memoization': len(re.findall(r'memoize\s*\(', content)),
            'lazy_loading': len(re.findall(r'lazy|defer', content, re.IGNORECASE)),
            'event_delegation': len(re.findall(r'addEventListener.*capture.*true', content)),
            'document_fragment': len(re.findall(r'DocumentFragment', content)),
            'web_workers': len(re.findall(r'Worker\s*\(', content))
        }
        
        return {
            "performance_issues": performance_issues,
            "optimizations": optimizations,
            "total_issues": sum(performance_issues.values()),
            "total_optimizations": sum(optimizations.values())
        }
    
    def analyze_memory_usage(self) -> Dict[str, Any]:
        """Анализ использования памяти"""
        with open(self.js_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Поиск потенциальных утечек памяти
        memory_issues = {
            'event_listeners_without_cleanup': len(re.findall(r'addEventListener.*(?!removeEventListener)', content)),
            'timers_without_cleanup': len(re.findall(r'setTimeout|setInterval', content)) - len(re.findall(r'clearTimeout|clearInterval', content)),
            'closures_in_loops': len(re.findall(r'for\s*\([^}]*\)\s*\{[^}]*function', content, re.DOTALL)),
            'global_object_pollution': len(re.findall(r'window\.\w+\s*=', content)),
            'circular_references': len(re.findall(r'this\.\w+\s*=\s*this', content)),
            'large_arrays': len(re.findall(r'new\s+Array\s*\(\s*\d{4,}', content)),
            'large_objects': len(re.findall(r'new\s+Object\s*\(\s*\d{4,}', content))
        }
        
        return {
            "memory_issues": memory_issues,
            "total_memory_issues": sum(memory_issues.values())
        }
    
    def analyze_async_operations(self) -> Dict[str, Any]:
        """Анализ асинхронных операций"""
        with open(self.js_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        async_patterns = {
            'promises': len(re.findall(r'new\s+Promise\s*\(', content)),
            'async_await': len(re.findall(r'await\s+', content)),
            'then_calls': len(re.findall(r'\.then\s*\(', content)),
            'catch_calls': len(re.findall(r'\.catch\s*\(', content)),
            'fetch_calls': len(re.findall(r'fetch\s*\(', content)),
            'setTimeout': len(re.findall(r'setTimeout\s*\(', content)),
            'setInterval': len(re.findall(r'setInterval\s*\(', content)),
            'requestAnimationFrame': len(re.findall(r'requestAnimationFrame\s*\(', content))
        }
        
        # Поиск проблем с асинхронностью
        async_issues = {
            'unhandled_promises': len(re.findall(r'Promise\s*\([^)]*\)(?!\.then|\.catch)', content)),
            'callback_hell': len(re.findall(r'\.then\s*\([^)]*\.then', content)),
            'missing_error_handling': len(re.findall(r'\.then\s*\([^)]*\)(?!\.catch)', content)),
            'synchronous_async': len(re.findall(r'async\s+function[^{]*\{[^}]*await[^}]*await', content, re.DOTALL))
        }
        
        return {
            "async_patterns": async_patterns,
            "async_issues": async_issues,
            "total_async_operations": sum(async_patterns.values()),
            "total_async_issues": sum(async_issues.values())
        }
    
    def analyze_dependencies(self) -> Dict[str, Any]:
        """Анализ зависимостей"""
        with open(self.js_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Поиск импортов и зависимостей
        imports = {
            'es6_imports': len(re.findall(r'import\s+.*from\s+', content)),
            'require_calls': len(re.findall(r'require\s*\(', content)),
            'jquery_usage': len(re.findall(r'\$\s*\(', content)),
            'lodash_usage': len(re.findall(r'_\s*\.', content)),
            'external_libraries': len(re.findall(r'https?://[^"\']*\.js', content))
        }
        
        # Поиск неиспользуемых импортов (упрощенная версия)
        import_statements = re.findall(r'import\s+([^from]+)\s+from', content)
        unused_imports = []
        
        for import_stmt in import_statements:
            imported_items = re.findall(r'\{([^}]+)\}', import_stmt)
            if imported_items:
                for item in imported_items[0].split(','):
                    item = item.strip()
                    if item and item not in content.replace(import_stmt, ''):
                        unused_imports.append(item)
        
        return {
            "imports": imports,
            "unused_imports": unused_imports,
            "total_imports": sum(imports.values())
        }
    
    def run_full_analysis(self) -> Dict[str, Any]:
        """Запуск полного анализа"""
        start_time = time.time()
        
        self.analysis_results = {
            "file_info": self.analyze_file_size(),
            "dom_operations": self.analyze_dom_operations(),
            "functions": self.analyze_functions(),
            "performance_patterns": self.analyze_performance_patterns(),
            "memory_usage": self.analyze_memory_usage(),
            "async_operations": self.analyze_async_operations(),
            "dependencies": self.analyze_dependencies(),
            "analysis_time": time.time() - start_time
        }
        
        return self.analysis_results
    
    def generate_recommendations(self) -> List[str]:
        """Генерация рекомендаций по оптимизации"""
        recommendations = []
        
        # Рекомендации по размеру файла
        if self.analysis_results.get("file_info", {}).get("size_kb", 0) > 50:
            recommendations.append("JavaScript файл слишком большой (>50KB). Рекомендуется минификация и разделение на модули.")
        
        # Рекомендации по DOM операциям
        dom_ops = self.analysis_results.get("dom_operations", {})
        if dom_ops.get("total_dom_operations", 0) > 100:
            recommendations.append("Слишком много DOM операций. Кэшируйте селекторы и используйте DocumentFragment.")
        
        if dom_ops.get("problematic_patterns", {}).get("dom_in_loops", 0) > 0:
            recommendations.append("DOM операции в циклах обнаружены. Вынесите селекторы за пределы циклов.")
        
        # Рекомендации по функциям
        functions = self.analysis_results.get("functions", {})
        if functions.get("long_functions", 0) > 5:
            recommendations.append("Слишком много длинных функций. Разбейте на более мелкие функции.")
        
        # Рекомендации по производительности
        perf = self.analysis_results.get("performance_patterns", {})
        if perf.get("performance_issues", {}).get("console_logs", 0) > 10:
            recommendations.append("Много console.log в продакшене. Удалите или замените на условное логирование.")
        
        if perf.get("performance_issues", {}).get("eval_usage", 0) > 0:
            recommendations.append("Использование eval() обнаружено. Это серьезная проблема безопасности и производительности.")
        
        # Рекомендации по памяти
        memory = self.analysis_results.get("memory_usage", {})
        if memory.get("total_memory_issues", 0) > 5:
            recommendations.append("Потенциальные утечки памяти обнаружены. Проверьте очистку event listeners и таймеров.")
        
        # Рекомендации по асинхронности
        async_ops = self.analysis_results.get("async_operations", {})
        if async_ops.get("async_issues", {}).get("unhandled_promises", 0) > 0:
            recommendations.append("Необработанные Promise обнаружены. Добавьте .catch() для обработки ошибок.")
        
        return recommendations

def main():
    """Основная функция для запуска анализа"""
    js_file = "/Users/zainllw0w/PycharmProjects/TwoComms/twocomms/staticfiles/js/main.js"
    
    analyzer = JavaScriptPerformanceAnalyzer(js_file)
    results = analyzer.run_full_analysis()
    recommendations = analyzer.generate_recommendations()
    
    # Сохранение результатов
    output_file = "/Users/zainllw0w/PycharmProjects/TwoComms/js_performance_analysis.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            "analysis_results": results,
            "recommendations": recommendations,
            "timestamp": time.time()
        }, f, indent=2, ensure_ascii=False)
    
    print("JavaScript Performance Analysis completed!")
    print(f"Results saved to: {output_file}")
    print(f"Recommendations: {len(recommendations)}")
    for i, rec in enumerate(recommendations, 1):
        print(f"{i}. {rec}")

if __name__ == "__main__":
    main()
