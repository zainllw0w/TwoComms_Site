# Django 6.1 Stage 1: отчёт о завершении

Дата: 2026-08-17. Область: все non-DTF Django applications и субдомены.

## Release evidence

- [x] Code SHA `cdb8f78b13d7b642b12c395afe04eee5d8cb0552` интегрирован в
  GitHub `main` и получен production checkout через
  `git pull --ff-only origin main`.
- [x] Локальный и production runtime: CPython `3.14.6`, Django `6.1`.
- [x] Production MariaDB: `11.4.12-MariaDB-cll-lve`.
- [x] Единый Stage 1 regression gate: `61/61`.
- [x] Warning gate: `blocked=0`, `allowed=0`, пустой vendor allowlist,
  subprocess return codes `0/0/0`.
- [x] `manage.py check --database=default` локально прошёл; production
  выдал только четыре ранее зафиксированных `DJ6-BASE-004`
  MariaDB capability warnings.
- [x] `makemigrations --check --dry-run --noinput` вернул
  `No changes detected`.
- [x] Changed Python modules, active `views.py.backup` и `git diff --check`
  прошли.
- [x] Storefront, management, storage и finance production probes вернули
  HTTP `200` после ожидаемых login redirects.
- [x] DTF URL, код, миграции, статика, процессы и база не
  изменялись и не использовались как acceptance target.

## Закрытые пункты

| ID | Результат | Основное доказательство |
| --- | --- | --- |
| `DJ6-SEC-001` | Explicit SHA-1 сохранил historical payment signatures | Frozen vector + model acceptance test |
| `DJ6-COOKIE-001` | Global fallback не включён; affected/unaffected signing paths закреплены | `django61-stage1-signed-cookie-matrix.md` |
| `DJ6-FORM-001` | Project URL forms явно сохраняют HTTPS default и legacy HTTP behavior | `test_django61_urlfield_contracts.py` |
| `DJ6-SEC-002` | Credential/PII/provider Base64 parsing стал strict | `django61-stage1-sec002-base64.md` |
| `DJ6-EMAIL-001` | Введены `default`, `transactional`, `reports` mailers | Email contract + `mail.E001` |
| `DJ6-EMAIL-002` | Deprecated kwargs удалены, exception policy закреплена | HTTP/cron/recovery SMTP failure tests |
| `DJ6-BASE-003` | Полный non-DTF email call graph закрыт | `django61-stage1-email-call-graph.md` |
| `DJ6-COMPAT-002` | Social-auth admin warning устранён без risky dependency jump | Empty warning allowlist |
| `DJ6-LEGACY-001` | Active legacy loader не содержит no-argument `select_related()` | AST contract + `/pricelist_opt.xlsx` route tests |
| `DJ6-PY-001` | `load_module()` заменён до Python 3.15 | Forced fallback identity/error tests |

## Side-effect boundaries

- [x] Все три mailer aliases в tests используют `locmem`.
- [x] `test_settings_no_network_non_dtf` блокирует внешние socket connections.
- [x] SMTP, OAuth, Monobank и provider boundaries заменены mocks/local keys.
- [x] Тесты не отправляли реальные письма, payment events или provider calls.

Stage 1 закрыт. Следующий implementation batch начинается с Stage 2 ORM
quick wins и локального fetch-mode/query-count evidence.
