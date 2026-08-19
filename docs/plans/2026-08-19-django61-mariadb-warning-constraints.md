# Django 6.1 MariaDB Warning Constraints Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Заменить четыре allowlisted MariaDB warning реальными non-DTF database constraints без изменения существующих write-path.

**Architecture:** Nullable stored generated columns преобразуют conditional uniqueness в обычные MariaDB unique indexes. Для web-push `SeparateDatabaseAndState` убирает ложный Django warning, сохраняя существующий physical `UNIQUE endpoint USING HASH` без DDL. Non-atomic миграции fail-closed проверяют дубли до idempotent MyISAM DDL, а disposable MariaDB gate доказывает физическую schema и отсутствие warning.

**Tech Stack:** CPython 3.14.6, Django 6.1, MariaDB 11.4.12, MyISAM compatibility gate, Django migrations/unittest.

---

### Task 1: Зафиксировать RED contract

**Files:**
- Modify: `tests/test_mariadb_gate_runner.py`
- Create: `twocomms/reviews/tests/test_mariadb_constraints.py`
- Create: `twocomms/storefront/tests/test_mariadb_constraints.py`

1. Добавить tests, требующие ноль allowlisted warnings, реальные generated
   columns/indexes и fail-closed duplicate preflight.
2. Запустить только эти focused tests и подтвердить ожидаемый RED из-за старых
   conditional constraints/allowlist.

### Task 2: Реализовать model state и migrations

**Files:**
- Modify: `twocomms/reviews/models.py`
- Create: `twocomms/reviews/migrations/0002_mariadb_vote_uniqueness.py`
- Modify: `twocomms/storefront/models.py`
- Create: `twocomms/storefront/migrations/0097_mariadb_generated_uniqueness.py`

1. Заменить conditional constraints на обычные unique constraints и две stored
   generated fields; endpoint изменить только в state, сохранив HASH index.
2. До idempotent `ADD ... IF NOT EXISTS` выполнить duplicate scans через
   historical models и остановить migration при любом конфликте.
3. Использовать `Migration.atomic = False`, проверять exact column/index после
   каждого MyISAM DDL и дать повторяемый `DROP ... IF EXISTS` reverse.
4. Запустить focused model/migration tests до GREEN.

### Task 3: Сделать MariaDB gate fail-closed без allowlist

**Files:**
- Modify: `scripts/run_mariadb_gate.py`
- Modify: `tests/test_mariadb_gate_runner.py`
- Modify: `docs/qa/django61-stage4-base004-db002.md`

1. Удалить временный warning allowlist и потребовать `allowed_warnings=0`.
2. До target migrations перевести три disposable таблицы в MyISAM; после них
   проверить engines, две generated columns, три новых indexes, сохранённый
   endpoint HASH index и отсутствие digest/старых conditional keys.
3. Запустить `tests.test_mariadb_gate_runner` до GREEN.

### Task 4: Единый verification gate

1. Запустить focused non-DTF tests один раз.
2. Запустить `makemigrations --check`.
3. Запустить lifecycle gate на disposable MariaDB 11.4.12 и подтвердить ноль
   database-check warnings, реальные constraints и cleanup.
4. Проверить scoped diff и создать commit; push/deploy выполнять только после
   отдельной интеграционной сверки с актуальным `origin/main`.
