#!/usr/bin/env python3
"""
Поиск дублирования кода в проекте TwoComms
Анализирует Python, JavaScript и CSS файлы
"""
import os
import re
import hashlib
from pathlib import Path
from collections import defaultdict
import difflib

class CodeDuplicationFinder:
    def __init__(self, project_root):
        self.project_root = Path(project_root)
        self.duplicates = defaultdict(list)
        self.similar_code = []
        
    def normalize_code(self, code):
        """Нормализовать код для сравнения"""
        # Удалить комментарии и пробелы
        code = re.sub(r'#.*$', '', code, flags=re.MULTILINE)
        code = re.sub(r'//.*$', '', code, flags=re.MULTILINE)
        code = re.sub(r'/\*.*?\*/', '', code, flags=re.DOTALL)
        code = re.sub(r'\s+', ' ', code)
        return code.strip()
    
    def get_code_hash(self, code):
        """Получить хеш кода"""
        normalized = self.normalize_code(code)
        return hashlib.md5(normalized.encode()).hexdigest()
    
    def find_duplicate_files(self, pattern):
        """Найти полностью дублирующиеся файлы"""
        print(f"\n🔍 Поиск дублирующихся {pattern} файлов...")
        
        file_hashes = defaultdict(list)
        files = list(self.project_root.rglob(pattern))
        
        for file_path in files:
            if '__pycache__' in str(file_path) or 'node_modules' in str(file_path):
                continue
                
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    code_hash = self.get_code_hash(content)
                    file_hashes[code_hash].append(file_path)
            except Exception as e:
                print(f"  ⚠️ Ошибка при чтении {file_path}: {e}")
        
        # Найти дубликаты
        duplicates_found = 0
        for hash_val, files in file_hashes.items():
            if len(files) > 1:
                duplicates_found += 1
                print(f"\n  🔴 Дубликат #{duplicates_found}:")
                for file in files:
                    size = file.stat().st_size
                    print(f"    - {file.relative_to(self.project_root)} ({size} bytes)")
        
        if duplicates_found == 0:
            print("  ✅ Полных дубликатов не найдено")
        else:
            print(f"\n  📊 Всего найдено дубликатов: {duplicates_found}")
        
        return duplicates_found
    
    def find_similar_functions(self, pattern, min_similarity=0.8):
        """Найти похожие функции"""
        print(f"\n🔍 Поиск похожих функций в {pattern} файлах...")
        
        # Регулярки для поиска функций
        if pattern == '*.py':
            func_pattern = r'def\s+(\w+)\s*\([^)]*\):\s*(.*?)(?=\n(?:def\s|\w+\s*=|class\s|$))'
        elif pattern == '*.js':
            func_pattern = r'function\s+(\w+)\s*\([^)]*\)\s*{(.*?)}'
        else:
            return 0
        
        functions = []
        files = list(self.project_root.rglob(pattern))
        
        for file_path in files:
            if '__pycache__' in str(file_path) or 'node_modules' in str(file_path):
                continue
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    matches = re.finditer(func_pattern, content, re.DOTALL | re.MULTILINE)
                    for match in matches:
                        func_name = match.group(1)
                        func_body = match.group(2)
                        if len(func_body.strip()) > 50:  # Игнорировать очень короткие функции
                            functions.append({
                                'name': func_name,
                                'body': func_body,
                                'file': file_path,
                                'normalized': self.normalize_code(func_body)
                            })
            except Exception as e:
                pass
        
        # Сравнить функции
        similar_count = 0
        checked = set()
        
        for i, func1 in enumerate(functions):
            for j, func2 in enumerate(functions[i+1:], i+1):
                pair_key = tuple(sorted([i, j]))
                if pair_key in checked:
                    continue
                checked.add(pair_key)
                
                # Сравнить нормализованный код
                similarity = difflib.SequenceMatcher(
                    None, 
                    func1['normalized'], 
                    func2['normalized']
                ).ratio()
                
                if similarity >= min_similarity and func1['file'] != func2['file']:
                    similar_count += 1
                    if similar_count <= 10:  # Показать первые 10
                        print(f"\n  🟡 Похожие функции (similarity: {similarity:.1%}):")
                        print(f"    1. {func1['name']} в {func1['file'].relative_to(self.project_root)}")
                        print(f"    2. {func2['name']} в {func2['file'].relative_to(self.project_root)}")
        
        if similar_count == 0:
            print("  ✅ Похожих функций не найдено")
        else:
            print(f"\n  📊 Всего найдено похожих функций: {similar_count}")
            if similar_count > 10:
                print(f"    (показано первые 10, всего {similar_count})")
        
        return similar_count
    
    def find_duplicate_blocks(self, pattern, min_lines=10):
        """Найти дублирующиеся блоки кода"""
        print(f"\n🔍 Поиск дублирующихся блоков кода ({min_lines}+ строк)...")
        
        blocks = defaultdict(list)
        files = list(self.project_root.rglob(pattern))
        
        for file_path in files:
            if '__pycache__' in str(file_path) or 'node_modules' in str(file_path):
                continue
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    
                    # Скользящее окно для поиска блоков
                    for i in range(len(lines) - min_lines + 1):
                        block = ''.join(lines[i:i+min_lines])
                        block_hash = self.get_code_hash(block)
                        blocks[block_hash].append({
                            'file': file_path,
                            'start_line': i + 1,
                            'block': block
                        })
            except Exception as e:
                pass
        
        # Найти дубликаты
        duplicates_found = 0
        for block_hash, occurrences in blocks.items():
            if len(occurrences) > 1:
                duplicates_found += 1
                if duplicates_found <= 5:  # Показать первые 5
                    print(f"\n  🔴 Дублирующийся блок #{duplicates_found}:")
                    for occ in occurrences[:3]:  # Показать первые 3 вхождения
                        print(f"    - {occ['file'].relative_to(self.project_root)}:{occ['start_line']}")
                    if len(occurrences) > 3:
                        print(f"    ... и ещё {len(occurrences) - 3} вхождений")
        
        if duplicates_found == 0:
            print("  ✅ Дублирующихся блоков не найдено")
        else:
            print(f"\n  📊 Всего найдено дублирующихся блоков: {duplicates_found}")
            if duplicates_found > 5:
                print(f"    (показано первые 5, всего {duplicates_found})")
        
        return duplicates_found
    
    def analyze_complexity(self, pattern):
        """Анализ сложности файлов"""
        print(f"\n🔍 Анализ сложности {pattern} файлов...")
        
        files_info = []
        files = list(self.project_root.rglob(pattern))
        
        for file_path in files:
            if '__pycache__' in str(file_path) or 'node_modules' in str(file_path):
                continue
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    loc = len([l for l in lines if l.strip() and not l.strip().startswith('#')])
                    
                    if pattern == '*.py':
                        # Подсчитать классы и функции
                        classes = len(re.findall(r'^class\s+\w+', ''.join(lines), re.MULTILINE))
                        functions = len(re.findall(r'^def\s+\w+', ''.join(lines), re.MULTILINE))
                    elif pattern == '*.js':
                        classes = len(re.findall(r'class\s+\w+', ''.join(lines)))
                        functions = len(re.findall(r'function\s+\w+|const\s+\w+\s*=\s*\(', ''.join(lines)))
                    else:
                        classes = 0
                        functions = 0
                    
                    files_info.append({
                        'file': file_path,
                        'loc': loc,
                        'classes': classes,
                        'functions': functions
                    })
            except Exception as e:
                pass
        
        # Сортировать по LOC
        files_info.sort(key=lambda x: x['loc'], reverse=True)
        
        print("\n  📊 Топ-10 самых больших файлов:")
        for i, info in enumerate(files_info[:10], 1):
            print(f"    {i}. {info['file'].relative_to(self.project_root)}")
            print(f"       LOC: {info['loc']}, Классов: {info['classes']}, Функций: {info['functions']}")
        
        # Статистика
        if files_info:
            total_loc = sum(f['loc'] for f in files_info)
            avg_loc = total_loc / len(files_info)
            print(f"\n  📈 Статистика:")
            print(f"    Всего файлов: {len(files_info)}")
            print(f"    Всего строк кода: {total_loc:,}")
            print(f"    Средний размер файла: {avg_loc:.0f} LOC")
            print(f"    Самый большой файл: {files_info[0]['loc']} LOC")
        
        return len(files_info)

def main():
    print("╔══════════════════════════════════════════════════════════════════════╗")
    print("║          ПОИСК ДУБЛИРОВАНИЯ КОДА В TWOCOMMS                          ║")
    print("╚══════════════════════════════════════════════════════════════════════╝")
    
    project_root = Path(__file__).parent / 'twocomms'
    finder = CodeDuplicationFinder(project_root)
    
    results = {}
    
    # Python файлы
    print("\n" + "=" * 70)
    print("АНАЛИЗ PYTHON ФАЙЛОВ")
    print("=" * 70)
    results['py_duplicates'] = finder.find_duplicate_files('*.py')
    results['py_similar'] = finder.find_similar_functions('*.py', min_similarity=0.85)
    results['py_blocks'] = finder.find_duplicate_blocks('*.py', min_lines=15)
    results['py_complexity'] = finder.analyze_complexity('*.py')
    
    # JavaScript файлы
    print("\n" + "=" * 70)
    print("АНАЛИЗ JAVASCRIPT ФАЙЛОВ")
    print("=" * 70)
    results['js_duplicates'] = finder.find_duplicate_files('*.js')
    results['js_similar'] = finder.find_similar_functions('*.js', min_similarity=0.85)
    results['js_blocks'] = finder.find_duplicate_blocks('*.js', min_lines=15)
    results['js_complexity'] = finder.analyze_complexity('*.js')
    
    # CSS файлы
    print("\n" + "=" * 70)
    print("АНАЛИЗ CSS ФАЙЛОВ")
    print("=" * 70)
    results['css_duplicates'] = finder.find_duplicate_files('*.css')
    results['css_blocks'] = finder.find_duplicate_blocks('*.css', min_lines=10)
    results['css_complexity'] = finder.analyze_complexity('*.css')
    
    # Итоговый отчёт
    print("\n" + "=" * 70)
    print("ИТОГОВЫЙ ОТЧЁТ")
    print("=" * 70)
    print(f"\nPython:")
    print(f"  Дублирующихся файлов: {results['py_duplicates']}")
    print(f"  Похожих функций: {results['py_similar']}")
    print(f"  Дублирующихся блоков: {results['py_blocks']}")
    print(f"  Всего файлов: {results['py_complexity']}")
    
    print(f"\nJavaScript:")
    print(f"  Дублирующихся файлов: {results['js_duplicates']}")
    print(f"  Похожих функций: {results['js_similar']}")
    print(f"  Дублирующихся блоков: {results['js_blocks']}")
    print(f"  Всего файлов: {results['js_complexity']}")
    
    print(f"\nCSS:")
    print(f"  Дублирующихся файлов: {results['css_duplicates']}")
    print(f"  Дублирующихся блоков: {results['css_blocks']}")
    print(f"  Всего файлов: {results['css_complexity']}")
    
    print("\n✅ Анализ завершён!")
    print("\nРекомендации:")
    total_issues = sum([
        results['py_duplicates'], results['py_similar'], results['py_blocks'],
        results['js_duplicates'], results['js_similar'], results['js_blocks'],
        results['css_duplicates'], results['css_blocks']
    ])
    
    if total_issues > 0:
        print(f"  🔴 Найдено {total_issues} проблем с дублированием кода")
        print("  📝 Рекомендуется провести рефакторинг для улучшения поддерживаемости")
    else:
        print("  ✅ Критичных проблем с дублированием не обнаружено")

if __name__ == '__main__':
    main()

