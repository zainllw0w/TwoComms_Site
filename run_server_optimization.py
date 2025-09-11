#!/usr/bin/env python3
"""
Скрипт для запуска оптимизации на сервере
"""

import subprocess
import sys
import os

def run_server_command(command, description):
    """Выполняет команду на сервере"""
    print(f"🔄 {description}...")
    
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            check=True
        )
        print(f"✅ {description} - успешно!")
        if result.stdout:
            print(f"Вывод: {result.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} - ошибка!")
        print(f"Код ошибки: {e.returncode}")
        if e.stdout:
            print(f"Вывод: {e.stdout}")
        if e.stderr:
            print(f"Ошибка: {e.stderr}")
        return False

def main():
    """Основная функция"""
    print("🚀 Запуск оптимизации на сервере...")
    
    # Команды для выполнения на сервере
    commands = [
        {
            'command': 'sshpass -p \'[REDACTED_SSH_PASSWORD]\' ssh -o StrictHostKeyChecking=no qlknpodo@195.191.24.169 "bash -lc \'source /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.13/bin/activate && cd /home/qlknpodo/TWC/TwoComms_Site/twocomms && python optimize_all_images.py\'"',
            'description': 'Запуск оптимизации изображений'
        },
        {
            'command': 'sshpass -p \'[REDACTED_SSH_PASSWORD]\' ssh -o StrictHostKeyChecking=no qlknpodo@195.191.24.169 "bash -lc \'source /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.13/bin/activate && cd /home/qlknpodo/TWC/TwoComms_Site/twocomms && python optimize_performance.py\'"',
            'description': 'Запуск анализа производительности'
        },
        {
            'command': 'sshpass -p \'[REDACTED_SSH_PASSWORD]\' ssh -o StrictHostKeyChecking=no qlknpodo@195.191.24.169 "bash -lc \'cd /home/qlknpodo/TWC/TwoComms_Site/twocomms && python manage.py collectstatic --noinput\'"',
            'description': 'Сбор статических файлов'
        },
        {
            'command': 'sshpass -p \'[REDACTED_SSH_PASSWORD]\' ssh -o StrictHostKeyChecking=no qlknpodo@195.191.24.169 "bash -lc \'cd /home/qlknpodo/TWC/TwoComms_Site/twocomms && python manage.py compress\'"',
            'description': 'Сжатие статических файлов'
        }
    ]
    
    success_count = 0
    total_count = len(commands)
    
    for cmd in commands:
        if run_server_command(cmd['command'], cmd['description']):
            success_count += 1
        print()  # Пустая строка для разделения
    
    print("=" * 50)
    print("📊 РЕЗУЛЬТАТЫ ВЫПОЛНЕНИЯ")
    print("=" * 50)
    print(f"Успешно выполнено: {success_count}/{total_count}")
    
    if success_count == total_count:
        print("🎉 Все команды выполнены успешно!")
        return 0
    else:
        print("⚠️ Некоторые команды завершились с ошибками")
        return 1

if __name__ == '__main__':
    sys.exit(main())
