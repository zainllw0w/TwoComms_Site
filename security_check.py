#!/usr/bin/env python3
"""
Security Check Script для TwoComms
Проверяет основные security issues в проекте
"""
import os
import subprocess
import sys
from pathlib import Path

def check_env_files():
    """Проверить наличие .env файлов в Git"""
    try:
        result = subprocess.run(
            ['git', 'ls-files', '*.env*'],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent
        )
        if result.stdout.strip():
            print("🔴 КРИТИЧНО: Найдены .env файлы в Git:")
            for file in result.stdout.strip().split('\n'):
                print(f"  - {file}")
            return False
        print("✅ .env файлы не найдены в Git")
        return True
    except Exception as e:
        print(f"⚠️ Ошибка проверки env файлов: {e}")
        return True  # Не блокируем если git не доступен

def check_secret_key():
    """Проверить наличие SECRET_KEY"""
    if not os.environ.get('SECRET_KEY'):
        print("🔴 КРИТИЧНО: SECRET_KEY не установлен в environment")
        print("   Сгенерируйте: python -c \"from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())\"")
        return False
    print("✅ SECRET_KEY установлен")
    return True

def check_debug():
    """Проверить DEBUG режим"""
    debug = os.environ.get('DEBUG', 'True').lower() in ('true', '1', 'yes')
    if debug:
        print("⚠️ ПРЕДУПРЕЖДЕНИЕ: DEBUG включён (небезопасно для production)")
        return False
    print("✅ DEBUG выключен")
    return True

def check_console_logs():
    """Проверить наличие console.log в JS файлах"""
    js_dir = Path(__file__).parent / 'twocomms' / 'static' / 'js'
    if not js_dir.exists():
        print("⚠️ Папка static/js не найдена")
        return True
    
    found = []
    for js_file in js_dir.rglob('*.js'):
        with open(js_file, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            for i, line in enumerate(lines, 1):
                if 'console.log' in line or 'console.warn' in line:
                    found.append(f"{js_file.name}:{i}")
    
    if found:
        print(f"⚠️ ПРЕДУПРЕЖДЕНИЕ: Найдено {len(found)} console.log/warn в JS файлах:")
        for item in found[:5]:  # Показываем первые 5
            print(f"  - {item}")
        if len(found) > 5:
            print(f"  ... и ещё {len(found) - 5}")
        return False
    print("✅ console.log не найдены в JS")
    return True

def check_redis_config():
    """Проверить конфигурацию Redis"""
    docker_compose = Path(__file__).parent / 'docker-compose.yml'
    if not docker_compose.exists():
        print("⚠️ docker-compose.yml не найден")
        return True
    
    with open(docker_compose, 'r') as f:
        content = f.read()
        if '6379:6379' in content and 'requirepass' not in content:
            print("⚠️ ПРЕДУПРЕЖДЕНИЕ: Redis порт открыт без пароля")
            return False
    
    print("✅ Redis конфигурация безопасна")
    return True

def check_csrf_exempt():
    """Проверить использование @csrf_exempt"""
    views_dir = Path(__file__).parent / 'twocomms' / 'storefront'
    if not views_dir.exists():
        print("⚠️ Папка storefront не найдена")
        return True
    
    count = 0
    for py_file in views_dir.rglob('*.py'):
        with open(py_file, 'r', encoding='utf-8', errors='ignore') as f:
            count += f.read().count('@csrf_exempt')
    
    if count > 0:
        print(f"⚠️ ПРЕДУПРЕЖДЕНИЕ: Найдено {count} использований @csrf_exempt")
        return False
    print("✅ @csrf_exempt не используется")
    return True

def main():
    """Запустить все проверки"""
    print("🔍 Проверка безопасности TwoComms проекта\n")
    print("=" * 60)
    
    checks = [
        ("Env files в Git", check_env_files),
        ("SECRET_KEY установлен", check_secret_key),
        ("DEBUG выключен", check_debug),
        ("Console.log в JS", check_console_logs),
        ("Redis безопасность", check_redis_config),
        ("CSRF protection", check_csrf_exempt),
    ]
    
    passed = 0
    failed = 0
    warnings = 0
    total = len(checks)
    
    for name, check in checks:
        print(f"\n[{name}]", end=" ")
        try:
            if check():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"\n📊 Результаты:")
    print(f"   ✅ Пройдено: {passed}/{total}")
    print(f"   ❌ Провалено: {failed}/{total}")
    print(f"   ⚠️ Предупреждений: {warnings}")
    
    if failed > 0:
        print("\n🔴 ТРЕБУЮТСЯ ИСПРАВЛЕНИЯ!")
        print("   См. FULL_PROJECT_AUDIT_REPORT.md для деталей")
        sys.exit(1)
    else:
        print("\n✅ Все проверки пройдены!")
        sys.exit(0)

if __name__ == '__main__':
    main()

