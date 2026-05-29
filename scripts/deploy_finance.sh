#!/bin/bash
# Деплой фінансового кабінету на сервер: pull → makemigrations → migrate →
# collectstatic → restart. Пароль береться з env DEPLOY_SERVER_PASSWORD,
# або (фолбек) з аргументу. Venv на сервері — 3.14 (за вказівкою власника).
set -euo pipefail

PASS="${DEPLOY_SERVER_PASSWORD:-${1:-}}"
if [ -z "$PASS" ] && [ -f "$(dirname "$0")/../.deploy_pass" ]; then
  PASS="$(head -n1 "$(dirname "$0")/../.deploy_pass")"
fi
if [ -z "$PASS" ]; then
  echo "Set DEPLOY_SERVER_PASSWORD, pass as arg 1, or create .deploy_pass" >&2
  exit 1
fi

HOST="qlknpodo@195.191.24.169"
VENV="/home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.14/bin/activate"
APPDIR="/home/qlknpodo/TWC/TwoComms_Site/twocomms"

sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no "$HOST" bash -lc "'
  set -e
  source $VENV
  cd $APPDIR
  echo \"== pre-pull cleanup (server-generated migration now tracked in git) ==\"
  if git ls-files --error-unmatch finance/migrations/0001_initial.py >/dev/null 2>&1; then
    : # already tracked, nothing to do
  fi
  # Remove the untracked copy so an identical tracked version can be pulled cleanly.
  if [ -f finance/migrations/0001_initial.py ] && ! git ls-files --error-unmatch finance/migrations/0001_initial.py >/dev/null 2>&1; then
    rm -f finance/migrations/0001_initial.py
  fi
  echo \"== git pull ==\"
  git pull --ff-only origin main
  echo \"== makemigrations finance ==\"
  python manage.py makemigrations finance
  echo \"== migrate ==\"
  python manage.py migrate --noinput
  echo \"== collectstatic ==\"
  python manage.py collectstatic --noinput
  echo \"== restart ==\"
  mkdir -p tmp && touch tmp/restart.txt
  echo \"== done ==\"
'"
