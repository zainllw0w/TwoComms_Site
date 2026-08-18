# Stage 7: current runtime documentation evidence

Дата: 2026-08-18  
Scope: `DJ6-DOC-001`, `DJ6-DOC-002`  
Worktree: `codex/django61-stage7-candidate-20260818`

## Что обновлено

- `ARCHITECTURE_SUMMARY.md` теперь явно показывает поддерживаемый runtime:
  CPython 3.14.6, Django 6.1, DRF 3.18.0, MariaDB 11.4.12 и mysqlclient
  2.2.8. Старые оценки документа помечены как historical snapshot.
- `README_ARCHITECTURE.md` получил актуальный Django badge, exact runtime
  contract и ссылку на operational runbook. Ручная установка DRF удалена;
  dependency changes проходят через pinned requirements.
- `DEPLOYMENT_INSTRUCTIONS.md` переписан как current-facing contract:
  commit/push в `main`, fast-forward SSH pull с CloudLinux-bound venv и
  read-only post-deploy proof. Старая feature-ветка, старый IP, `pip install`,
  автоматические migrations/collectstatic и release wrappers удалены из
  рабочего пути.

Исторические audit/incident/planning документы не переписывались. DTF-код,
DTF-модели, DTF-миграции и DTF-серверные команды не изменялись.

## Проверки

- `rg` по трём current-facing документам не находит executable-инструкций со
  старым Django 5.2/PyMySQL runtime или старым deployment path.
- Версии сверены с `AGENTS.md`, `.python-version`,
  `twocomms/requirements.in` и `docs/qa/django61-compatibility-matrix.md`.
- `git diff --check` прошёл перед интеграцией candidate; после rebase на
  актуальный `origin/main` повторяется тем же release gate.

Чекбоксы implementation plan отмечаются только после интеграции этого
коммита в `main` и разрешённого deployment proof; локальная документационная
правка сама по себе не является production evidence.
