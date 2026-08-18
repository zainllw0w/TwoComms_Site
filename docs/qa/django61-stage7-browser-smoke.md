# Django 6.1 Stage 7: statistics browser smoke

Date: 2026-08-18

Scope: `DJ6-TPL-001` exit gate (`response parity` plus local browser smoke).

Source baseline: `origin/main=34f2517c4df4ea2e7c04ab0f6e7a152d83171279`.

## Runtime and test contract

- Interpreter: CPython `3.14.6` from the shared project `.venv`.
- Framework: Django `6.1`.
- Database: temporary local SQLite database owned by the browser harness; no
  production database or MariaDB connection was used.
- Authentication: synthetic local user `stage7-browser`, created by the
  harness only for this smoke.

The response-parity gate was run before the browser session:

```bash
TWC_PYTHON="$(cd "$(git rev-parse --git-common-dir)/.." && pwd)/.venv/bin/python"
"$TWC_PYTHON" -c 'import django,sys; assert sys.version_info[:3] == (3,14,6); assert django.get_version() == "6.1"; print(sys.executable, django.get_version())'
cd twocomms
SECRET_KEY=codex-django-stage7-browser-test "$TWC_PYTHON" manage.py test \
  orders.tests.test_dropshipper_statistics_template_parity \
  --settings=test_settings --noinput -v 2
```

Result: `Ran 2 tests ... OK` (`2/2`). The test proves normalized fragment
content is included exactly once in the full response and that the full-page
shell is absent from the fragment.

## Local browser smoke

The existing local harness served `127.0.0.1:8765` with a temporary SQLite
settings module and seeded the synthetic user. Playwright logged in through the
local `/login/` form, then navigated the two route variants:

| Request | Status | Browser evidence |
| --- | ---: | --- |
| `GET /orders/dropshipper/statistics/` | `200` | Full shell markers (`data-tab-panel="statistics"`, `dropshipper.js`, `ds-modal`) and statistics markers rendered. |
| `GET /orders/dropshipper/statistics/?partial=1` | `200` | Statistics markers rendered; full shell markers were absent. |

The page-level marker set included `Аналітика продажів`, `Усього замовлень`,
`Динаміка по місяцях`, and `Топ-товари` in both responses. Captured response
sizes were 108,494 bytes (full) and 4,942 bytes (fragment).

Before navigation, the browser context intercepted every request whose origin
was not `http://127.0.0.1:8765` (or `http://localhost:8765`), recorded its URL
and resource type, and aborted it. Fourteen external requests were recorded,
including Meta/Facebook, Ahrefs, Google Tag Manager/Analytics, TikTok, Clarity,
and Bootstrap CDN assets. This keeps provider traffic out of the smoke and
documents it as out of scope rather than treating blocked analytics as a
production result.

## Boundaries

- No production credentials, production auth session, SSH command, deploy, or
  live endpoint was used.
- No external analytics, payment, Telegram, Meta, TikTok, Google, Ahrefs, or
  Clarity provider was contacted; all non-local browser requests were aborted.
- No DTF behavior or DTF data was exercised; DTF, migrations, CI configuration,
  and production data were outside this smoke's scope.
- This is local template/route evidence only, not production acceptance proof.
  A production claim still requires the authorized deployment path and a
  separate live verification against the deployed SHA.
