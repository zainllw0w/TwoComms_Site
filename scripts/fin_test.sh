#!/bin/bash
# Локальний запуск тестів/перевірок finance у DEBUG-режимі.
# Використання: bash scripts/fin_test.sh [<test path>]
export DEBUG=1
export SECRET_KEY="${SECRET_KEY:-dev-local-secret}"
PY=/Users/zainllw0w/TwoComms/site/.venv/bin/python
cd /Users/zainllw0w/TwoComms/site/twocomms || exit 1
"$PY" manage.py check finance || exit 1
if [ -n "$1" ]; then
  "$PY" manage.py test "$1" --noinput
else
  "$PY" manage.py test finance --noinput
fi
