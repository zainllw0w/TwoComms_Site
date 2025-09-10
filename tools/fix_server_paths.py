#!/usr/bin/env python3
"""
Fix Server Paths Script
Исправляет пути в скриптах для работы на сервере
"""

import os
import re
from pathlib import Path

def fix_paths_in_file(file_path: str, local_path: str, server_path: str):
    """Исправляет пути в файле"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Заменяем локальные пути на серверные
    content = content.replace(local_path, server_path)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"✅ Исправлены пути в {file_path}")

def main():
    """Основная функция"""
    tools_dir = Path(__file__).parent
    
    # Пути для замены
    local_paths = [
        "/Users/zainllw0w/PycharmProjects/TwoComms/twocomms",
        "/Users/zainllw0w/PycharmProjects/TwoComms"
    ]
    
    server_paths = [
        "/home/qlknpodo/TWC/TwoComms_Site/twocomms",
        "/home/qlknpodo/TWC/TwoComms_Site/twocomms"
    ]
    
    # Файлы для исправления
    files_to_fix = [
        "css_performance_analyzer.py",
        "js_performance_analyzer.py",
        "django_performance_analyzer_simple.py",
        "media_performance_analyzer.py",
        "network_performance_analyzer.py",
        "ai_performance_analyzer.py",
        "report_generator.py"
    ]
    
    for filename in files_to_fix:
        file_path = tools_dir / filename
        if file_path.exists():
            for local_path, server_path in zip(local_paths, server_paths):
                fix_paths_in_file(str(file_path), local_path, server_path)
        else:
            print(f"⚠️  Файл не найден: {filename}")

if __name__ == "__main__":
    main()
