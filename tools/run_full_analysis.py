#!/usr/bin/env python3
"""
Full Performance Analysis Runner
Запускает полный анализ производительности сайта TwoComms
"""

import os
import sys
import time
import subprocess
from pathlib import Path

def run_analysis_script(script_path: str, description: str) -> bool:
    """Запуск скрипта анализа"""
    print(f"\n{'='*60}")
    print(f"Запуск: {description}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run([sys.executable, script_path], 
                              capture_output=True, 
                              text=True, 
                              cwd=os.path.dirname(script_path))
        
        if result.returncode == 0:
            print(f"✅ {description} - УСПЕШНО")
            if result.stdout:
                print("Вывод:")
                print(result.stdout)
            return True
        else:
            print(f"❌ {description} - ОШИБКА")
            if result.stderr:
                print("Ошибки:")
                print(result.stderr)
            if result.stdout:
                print("Вывод:")
                print(result.stdout)
            return False
            
    except Exception as e:
        print(f"❌ {description} - ИСКЛЮЧЕНИЕ: {e}")
        return False

def install_requirements():
    """Установка необходимых зависимостей"""
    print("\n" + "="*60)
    print("Установка зависимостей")
    print("="*60)
    
    requirements = [
        "requests",
        "Pillow",
        "openai"
    ]
    
    for req in requirements:
        try:
            print(f"Устанавливаю {req}...")
            subprocess.run([sys.executable, "-m", "pip", "install", req], 
                         check=True, capture_output=True)
            print(f"✅ {req} установлен")
        except subprocess.CalledProcessError as e:
            print(f"❌ Ошибка установки {req}: {e}")
            return False
    
    return True

def main():
    """Основная функция"""
    print("🚀 Запуск полного анализа производительности TwoComms")
    print(f"Время начала: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Определяем пути
    tools_dir = Path(__file__).parent
    project_root = tools_dir.parent
    
    # Список скриптов анализа
    analysis_scripts = [
        {
            "script": tools_dir / "css_performance_analyzer.py",
            "description": "Анализ CSS производительности"
        },
        {
            "script": tools_dir / "js_performance_analyzer.py", 
            "description": "Анализ JavaScript производительности"
        },
        {
            "script": tools_dir / "django_performance_analyzer_simple.py",
            "description": "Анализ Django производительности"
        },
        {
            "script": tools_dir / "media_performance_analyzer.py",
            "description": "Анализ медиа файлов"
        },
        {
            "script": tools_dir / "network_performance_analyzer.py",
            "description": "Анализ сетевой производительности"
        },
        {
            "script": tools_dir / "ai_performance_analyzer.py",
            "description": "AI анализ производительности"
        }
    ]
    
    # Установка зависимостей
    if not install_requirements():
        print("❌ Не удалось установить зависимости. Продолжаем без них...")
    
    # Запуск анализа
    successful_analyses = 0
    failed_analyses = 0
    
    for analysis in analysis_scripts:
        if analysis["script"].exists():
            success = run_analysis_script(str(analysis["script"]), analysis["description"])
            if success:
                successful_analyses += 1
            else:
                failed_analyses += 1
        else:
            print(f"⚠️  Скрипт не найден: {analysis['script']}")
            failed_analyses += 1
    
    # Генерация отчета
    print(f"\n{'='*60}")
    print("Генерация отчета")
    print(f"{'='*60}")
    
    report_script = tools_dir / "report_generator.py"
    if report_script.exists():
        success = run_analysis_script(str(report_script), "Генерация отчета")
        if success:
            print("✅ Отчет сгенерирован успешно")
        else:
            print("❌ Ошибка генерации отчета")
    else:
        print("⚠️  Скрипт генерации отчета не найден")
    
    # Итоговая статистика
    print(f"\n{'='*60}")
    print("ИТОГОВАЯ СТАТИСТИКА")
    print(f"{'='*60}")
    print(f"✅ Успешных анализов: {successful_analyses}")
    print(f"❌ Неудачных анализов: {failed_analyses}")
    print(f"📊 Общее количество: {successful_analyses + failed_analyses}")
    print(f"⏱️  Время завершения: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Поиск сгенерированных файлов
    print(f"\n{'='*60}")
    print("СГЕНЕРИРОВАННЫЕ ФАЙЛЫ")
    print(f"{'='*60}")
    
    analysis_files = [
        "css_performance_analysis.json",
        "js_performance_analysis.json",
        "django_performance_analysis.json", 
        "media_performance_analysis.json",
        "network_performance_analysis.json",
        "ai_performance_analysis.json"
    ]
    
    report_files = list(project_root.glob("performance_analysis_report_*.md"))
    
    print("Файлы анализа:")
    for file in analysis_files:
        file_path = project_root / file
        if file_path.exists():
            size = file_path.stat().st_size
            print(f"✅ {file} ({size} байт)")
        else:
            print(f"❌ {file} (не найден)")
    
    print("\nОтчеты:")
    for file in report_files:
        size = file.stat().st_size
        print(f"✅ {file.name} ({size} байт)")
    
    if successful_analyses > 0:
        print(f"\n🎉 Анализ завершен! Проверьте сгенерированные файлы в {project_root}")
    else:
        print(f"\n😞 Анализ не удался. Проверьте ошибки выше.")

if __name__ == "__main__":
    main()
