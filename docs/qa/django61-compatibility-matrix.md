# Django 6.1 compatibility matrix

Матрица фиксирует текущие locked versions и фактические contracts Stage 0.
Она не означает, что все зависимости нужно немедленно обновить до latest.
Каждое изменение vendor-пакета требует отдельной изолированной проверки и
нового lock.

Named contracts для перечисленных integrations реализованы и подтверждены
release SHA `df5a99d09b4135bdc7d70baba7956e89e3610ca9`, GitHub Django run
`31967237986`, MariaDB run `31967237927` и production post-deploy matrices.
Stage 0 закрывает совместимость текущих pins, но не разрешает их массовое
обновление без отдельного lock diff и regression proof.

## Runtime contract

| Компонент | Locked version | Contract | Текущее evidence | Статус Stage 0 |
| --- | --- | --- | --- | --- |
| CPython | 3.14.6 | `scripts/verify_project_runtime.py` | exact verifier, CI и server matrix | Stage 0 подтвержден |
| Django | 6.1 | exact verifier + Django compatibility tests | import/check, full smoke comparison и production runtime | Stage 0 подтвержден |
| Django REST Framework | 3.18.0 | router/import and API compatibility tests | import contract, schema generation и server matrix | Stage 0 подтвержден |
| mysqlclient | 2.2.8 | MySQLdb import/version + locked requirements | lock CI, disposable MariaDB и production MariaDB 11.4.12 | Stage 0 подтвержден |

## Active integrations

| Integration | Locked version | Required contract | Current evidence | Gap / owner action |
| --- | --- | --- | --- | --- |
| django-compressor | 4.6.0 | isolated `collectstatic` + `compress --force`, offline manifest, representative `{% compress %}` render | CI static artifact runs both commands, renders `base.html` and resolves non-empty `/static/CACHE/` URLs | Current pin proven; review any package bump separately |
| WhiteNoise | 6.7.0 | `CompressedManifestStaticFilesStorage`, hashed asset URL resolves from temporary root | CI static artifact resolves hashed CSS URLs and confirms rendered files exist | Current pin proven; review upstream support before upgrade |
| drf-spectacular | 0.27.2 | schema generation and representative non-DTF operation count | Schema contract builds `44` paths and `44` operations, with DTF absent | Current pin proven; package bump remains separate |
| django-ratelimit | 4.1.0 | decorator import plus representative request/rate-limit contract | AJAX login accepts 10 POST requests and returns `429`/`limited` on the next request | Current pin proven in CI |
| django-redis | 5.4.0 | client/cache backend import and settings construction without requiring Redis | RedisCache and DefaultClient construct lazily with `_clients=[None]` and no connection | Import/config compatibility proven; production Redis capability remains a separate Stage 6 prerequisite |
| social-auth-app-django | 5.6.0 | admin/login import and OAuth callback smoke | Google backend, URLs, begin/callback pass without provider call | Current pin works; owner/expiry warning remains Stage 1 debt before Django 7 |
| django-mathfilters | 1.0.0 | render templates using `{% load mathfilters %}` | Named render contract passes in CI | Current pin works; retain until isolated replacement proof |

## Commands used by the matrix

Run all commands with the project interpreter, never a bare system Python:

```bash
TWC_PYTHON="$(cd "$(git rev-parse --git-common-dir)/.." && pwd)/.venv/bin/python"
"$TWC_PYTHON" scripts/verify_project_runtime.py
"$TWC_PYTHON" -m unittest tests.test_django61_compatibility -v
"$TWC_PYTHON" scripts/run_django_warning_gate.py --output /tmp/twocomms-warning-gate.json
"$TWC_PYTHON" scripts/run_static_gate.py --output /tmp/twocomms-static-gate.json
```

The general CI workflow additionally runs the migration profile, management
command import/parser smoke and sanitized non-DTF inventory. CI artifacts are
the release evidence; local `/tmp` files are not a substitute for them.

## Warning policy

Project-owned Django 7 warnings fail the gate. The only current vendor
allowlist entry is `social_django.admin.list_select_related`, owned by
`runtime-maintainers` and expiring `2026-10-01`. A new warning, a changed
message, or an expired entry must fail review rather than being silently
ignored.

## Compatibility decision rules

- Keep the current pins during Stage 0 unless a replacement has a clean Python
  3.14.6/Django 6.1 install, focused contract tests, static/schema evidence and
  a reviewed lock diff.
- Do not infer Redis/Celery capability from an import-only test; production Redis
  availability and connection budget are separate evidence.
- Each active row now has a named contract. Это подтверждает compatibility
  текущих pins, но не разрешает массово обновлять vendor-пакеты без отдельного
  lock diff и regression proof.
- This document covers only non-DTF integrations. DTF packages, URLconf,
  database alias and server routes are outside the matrix.
