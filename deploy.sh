#!/usr/bin/env bash
# Деплой TwoComms на продакшен-сервере.
# Запускается НА сервере (никаких секретов внутри): bash deploy.sh
# Порядок критичен: миграции ДО перезапуска кода, иначе главная отдаёт 500
# в окно деплоя (код видит старую схему БД).
set -euo pipefail

PROJECT_DIR="/home/qlknpodo/TWC/TwoComms_Site/twocomms"
VENV_ACTIVATE="/home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.14/bin/activate"

cd "$PROJECT_DIR"
# shellcheck disable=SC1090
source "$VENV_ACTIVATE"

echo "[1/5] pip install -r requirements.txt"
pip install -r requirements.txt --quiet 2>&1 | tail -2 || echo "pip install failed (non-fatal, continuing)"

echo "[2/5] migrate"
python manage.py migrate --noinput

echo "[3/5] collectstatic"
python manage.py collectstatic --noinput --verbosity 0

echo "[4/5] compress"
python manage.py compress --force --verbosity 0 || echo "compress failed (non-fatal)"

echo "[5/5] restart (Passenger)"
mkdir -p tmp && touch tmp/restart.txt

echo "Deploy done: $(date '+%F %T')"
