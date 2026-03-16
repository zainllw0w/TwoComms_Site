# Firewall 403 Activity Pulse Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Убрать серию `403` на `management/activity/pulse/`, из-за которой CrowdSec блокирует IP как `http-generic-403-bf`.

**Architecture:** Корневая причина находится в фронтенд-пульсе активности менеджмента: скрипт шлёт фоновые POST с пустым/битым `X-CSRFToken`, когда в браузере есть дубли `csrftoken` или cookie нельзя корректно извлечь. Исправление должно быть минимальным: добавить регрессионный JS-тест, заменить чтение cookie на Django-совместимый разбор, добавить fallback на DOM token и сохранить cache-busting для нового статического файла.

**Tech Stack:** Django 5.2, plain browser JavaScript, Node built-in test runner, Apache/shared hosting deployment over SSH.

---

### Task 1: Add failing regression test

**Files:**
- Create: `tests/js/management-activity.test.js`
- Test: `twocomms/twocomms_django_theme/static/js/management-activity.js`

**Step 1: Write the failing test**

Create a Node test that:
- loads `twocomms/twocomms_django_theme/static/js/management-activity.js` into a VM sandbox,
- simulates `document.cookie` with two `csrftoken` values,
- simulates a valid hidden `csrfmiddlewaretoken` DOM field,
- asserts the first pulse request uses a valid `X-CSRFToken` instead of an empty string.

**Step 2: Run test to verify it fails**

Run: `node --test tests/js/management-activity.test.js`
Expected: FAIL because the current script sends an empty `X-CSRFToken` when duplicate cookies are present.

### Task 2: Implement minimal JS fix

**Files:**
- Modify: `twocomms/twocomms_django_theme/static/js/management-activity.js`
- Modify: `twocomms/management/templates/management/base.html`

**Step 1: Replace cookie parsing**

Use a Django-style cookie parser that iterates over `document.cookie.split(';')` and returns the first matching value instead of failing on duplicate-name cookies.

**Step 2: Add safer CSRF resolution**

Resolve token in this order:
- `<meta name="csrf-token">`
- `[name="csrfmiddlewaretoken"]`
- `csrftoken` cookie

Only send the pulse request when the token matches Django-accepted lengths (`32` or `64` alnum chars).

**Step 3: Ensure new JS is fetched**

Keep/update the versioned static include in `management/templates/management/base.html` so production browsers don’t keep the broken cached file.

### Task 3: Verify locally

**Files:**
- Test: `tests/js/management-activity.test.js`

**Step 1: Run regression test**

Run: `node --test tests/js/management-activity.test.js`
Expected: PASS

**Step 2: Run relevant Django checks/tests**

Run: `cd twocomms && python3 manage.py test management.tests --keepdb`
Expected: relevant management tests stay green.

### Task 4: Ship and deploy

**Files:**
- Modify tracked files only for this fix

**Step 1: Commit**

Run:
```bash
git add docs/plans/2026-03-10-firewall-403-activity-pulse.md tests/js/management-activity.test.js twocomms/twocomms_django_theme/static/js/management-activity.js twocomms/management/templates/management/base.html
git commit -m "fix: stop management activity pulse csrf 403 spam"
```

**Step 2: Push**

Run: `git push`

**Step 3: Deploy**

Run:
```bash
sshpass -p 'trs5m4t1' ssh -o StrictHostKeyChecking=no qlknpodo@195.191.24.169 "bash -lc 'source /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.13/bin/activate && cd /home/qlknpodo/TWC/TwoComms_Site/twocomms && git pull'"
```

**Step 4: Post-deploy verification**

Run remote checks that confirm:
- deployed JS contains the new CSRF resolver,
- `django.log` stops accumulating fresh `Forbidden ... /activity/pulse/` lines during a short observation window.
