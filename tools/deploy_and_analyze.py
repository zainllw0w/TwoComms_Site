#!/usr/bin/env python3
"""
Deploy and Analyze Script
Деплоит инструменты анализа на сервер и запускает анализ
"""

import os
import subprocess
import time
from pathlib import Path

class ServerDeployer:
    def __init__(self):
        self.ssh_host = "195.191.24.169"
        self.ssh_user = "qlknpodo"
        self.ssh_password = "trs5m4t1"
        self.project_path = "/home/qlknpodo/TWC/TwoComms_Site/twocomms"
        self.venv_path = "/home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.13/bin/activate"
        
    def run_ssh_command(self, command: str) -> tuple:
        """Выполнение команды на сервере через SSH"""
        ssh_cmd = [
            "/opt/homebrew/bin/sshpass", "-p", self.ssh_password,
            "ssh", "-o", "StrictHostKeyChecking=no",
            f"{self.ssh_user}@{self.ssh_host}",
            f"bash -lc 'source {self.venv_path} && cd {self.project_path} && {command}'"
        ]
        
        try:
            result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=300)
            return result.returncode == 0, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return False, "", "Command timed out"
        except Exception as e:
            return False, "", str(e)
    
    def upload_file(self, local_path: str, remote_path: str) -> bool:
        """Загрузка файла на сервер"""
        scp_cmd = [
            "/opt/homebrew/bin/sshpass", "-p", self.ssh_password,
            "scp", "-o", "StrictHostKeyChecking=no",
            local_path,
            f"{self.ssh_user}@{self.ssh_host}:{remote_path}"
        ]
        
        try:
            result = subprocess.run(scp_cmd, capture_output=True, text=True, timeout=60)
            return result.returncode == 0
        except Exception as e:
            print(f"Ошибка загрузки файла {local_path}: {e}")
            return False
    
    def deploy_analysis_tools(self) -> bool:
        """Деплой инструментов анализа на сервер"""
        print("🚀 Деплой инструментов анализа на сервер...")
        
        # Создаем директорию tools на сервере
        success, stdout, stderr = self.run_ssh_command("mkdir -p tools")
        if not success:
            print(f"Ошибка создания директории tools: {stderr}")
            return False
        
        # Список файлов для загрузки
        tools_dir = Path(__file__).parent
        files_to_upload = [
            "css_performance_analyzer.py",
            "js_performance_analyzer.py", 
            "django_performance_analyzer.py",
            "media_performance_analyzer.py",
            "network_performance_analyzer.py",
            "ai_performance_analyzer.py",
            "report_generator.py",
            "run_full_analysis.py"
        ]
        
        uploaded_files = 0
        for filename in files_to_upload:
            local_file = tools_dir / filename
            if local_file.exists():
                remote_file = f"{self.project_path}/tools/{filename}"
                if self.upload_file(str(local_file), remote_file):
                    print(f"✅ Загружен: {filename}")
                    uploaded_files += 1
                else:
                    print(f"❌ Ошибка загрузки: {filename}")
            else:
                print(f"⚠️  Файл не найден: {filename}")
        
        print(f"📊 Загружено файлов: {uploaded_files}/{len(files_to_upload)}")
        return uploaded_files > 0
    
    def install_server_dependencies(self) -> bool:
        """Установка зависимостей на сервере"""
        print("📦 Установка зависимостей на сервере...")
        
        dependencies = [
            "requests",
            "Pillow", 
            "openai"
        ]
        
        for dep in dependencies:
            print(f"Устанавливаю {dep}...")
            success, stdout, stderr = self.run_ssh_command(f"pip install {dep}")
            if success:
                print(f"✅ {dep} установлен")
            else:
                print(f"❌ Ошибка установки {dep}: {stderr}")
                return False
        
        return True
    
    def run_analysis_on_server(self) -> bool:
        """Запуск анализа на сервере"""
        print("🔍 Запуск анализа производительности на сервере...")
        
        # Сначала обновляем код
        print("Обновляю код на сервере...")
        success, stdout, stderr = self.run_ssh_command("git pull")
        if not success:
            print(f"Ошибка обновления кода: {stderr}")
            return False
        
        # Запускаем анализ
        analysis_script = f"{self.project_path}/tools/run_full_analysis.py"
        success, stdout, stderr = self.run_ssh_command(f"python {analysis_script}")
        
        if success:
            print("✅ Анализ завершен успешно")
            print("Вывод:")
            print(stdout)
        else:
            print("❌ Ошибка выполнения анализа")
            print("Ошибки:")
            print(stderr)
            if stdout:
                print("Вывод:")
                print(stdout)
        
        return success
    
    def download_results(self) -> bool:
        """Скачивание результатов анализа с сервера"""
        print("📥 Скачивание результатов анализа...")
        
        # Список файлов для скачивания
        result_files = [
            "css_performance_analysis.json",
            "js_performance_analysis.json",
            "django_performance_analysis.json",
            "media_performance_analysis.json", 
            "network_performance_analysis.json",
            "ai_performance_analysis.json"
        ]
        
        # Поиск отчетов
        success, stdout, stderr = self.run_ssh_command("find . -name 'performance_analysis_report_*.md' -type f")
        if success and stdout.strip():
            report_files = stdout.strip().split('\n')
            result_files.extend(report_files)
        
        downloaded_files = 0
        for filename in result_files:
            remote_file = f"{self.project_path}/{filename}"
            local_file = f"/Users/zainllw0w/PycharmProjects/TwoComms/{os.path.basename(filename)}"
            
            scp_cmd = [
                "/opt/homebrew/bin/sshpass", "-p", self.ssh_password,
                "scp", "-o", "StrictHostKeyChecking=no",
                f"{self.ssh_user}@{self.ssh_host}:{remote_file}",
                local_file
            ]
            
            try:
                result = subprocess.run(scp_cmd, capture_output=True, text=True, timeout=60)
                if result.returncode == 0:
                    print(f"✅ Скачан: {filename}")
                    downloaded_files += 1
                else:
                    print(f"❌ Ошибка скачивания {filename}: {result.stderr}")
            except Exception as e:
                print(f"❌ Исключение при скачивании {filename}: {e}")
        
        print(f"📊 Скачано файлов: {downloaded_files}/{len(result_files)}")
        return downloaded_files > 0
    
    def run_full_deployment(self) -> bool:
        """Полный процесс деплоя и анализа"""
        print("🚀 Запуск полного процесса деплоя и анализа")
        print(f"Время начала: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        steps = [
            ("Деплой инструментов", self.deploy_analysis_tools),
            ("Установка зависимостей", self.install_server_dependencies),
            ("Запуск анализа", self.run_analysis_on_server),
            ("Скачивание результатов", self.download_results)
        ]
        
        successful_steps = 0
        for step_name, step_function in steps:
            print(f"\n{'='*60}")
            print(f"Шаг: {step_name}")
            print(f"{'='*60}")
            
            try:
                if step_function():
                    print(f"✅ {step_name} - УСПЕШНО")
                    successful_steps += 1
                else:
                    print(f"❌ {step_name} - ОШИБКА")
            except Exception as e:
                print(f"❌ {step_name} - ИСКЛЮЧЕНИЕ: {e}")
        
        print(f"\n{'='*60}")
        print("ИТОГОВАЯ СТАТИСТИКА")
        print(f"{'='*60}")
        print(f"✅ Успешных шагов: {successful_steps}")
        print(f"❌ Неудачных шагов: {len(steps) - successful_steps}")
        print(f"📊 Общее количество шагов: {len(steps)}")
        print(f"⏱️  Время завершения: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        if successful_steps == len(steps):
            print("\n🎉 Полный процесс деплоя и анализа завершен успешно!")
            return True
        else:
            print(f"\n😞 Процесс завершен с ошибками. Успешно выполнено {successful_steps}/{len(steps)} шагов.")
            return False

def main():
    """Основная функция"""
    deployer = ServerDeployer()
    
    # Проверяем наличие необходимых инструментов
    try:
        subprocess.run(["/opt/homebrew/bin/sshpass", "-V"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ sshpass не установлен. Установите его для работы с SSH:")
        print("   macOS: brew install hudochenkov/sshpass/sshpass")
        print("   Ubuntu: sudo apt-get install sshpass")
        return
    
    # Запускаем полный процесс
    success = deployer.run_full_deployment()
    
    if success:
        print("\n📁 Проверьте скачанные файлы в директории проекта:")
        print("   - performance_analysis_report_*.md - детальные отчеты")
        print("   - *_performance_analysis.json - данные анализа")
    else:
        print("\n🔧 Для ручного запуска на сервере используйте:")
        print(f"   /opt/homebrew/bin/sshpass -p '{deployer.ssh_password}' ssh -o StrictHostKeyChecking=no {deployer.ssh_user}@{deployer.ssh_host}")
        print(f"   'bash -lc \"source {deployer.venv_path} && cd {deployer.project_path} && python tools/run_full_analysis.py\"'")

if __name__ == "__main__":
    main()
