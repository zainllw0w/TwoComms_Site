# Протокол выполнения, тестов, commit, push и deploy

## До изменения

Обновить progress; указать task/findings; проверить рабочее дерево; baseline tests; безопасные fixtures; подтвердить root cause; проверить зависимости/риск.

## Red–Green–Refactor

**Red:** тест воспроизводит баг/новое поведение; внешний API — fixture/contract; UI — E2E/component; аналитика — фиксированный dataset.

**Green:** минимальное изменение; side effects за orchestration boundary; idempotency/observability сразу.

**Refactor:** убрать дубли, улучшить имена, вынести config, не менять контракт без migration, снова запустить tests.

## Перед commit

Formatter/linter/typecheck, unit, integration, contract, relevant E2E, migration check, secret scan, diff review и docs.

## Commit

`<type>(instagram-bot): <результат> [IMP-###]`

Body: findings, изменения, tests, migration/rollback, ограничения. Commit атомарный, без случайного formatting noise.

## Push/deploy

Push после local green и успешного CI. Deploy не выполнять вслепую: staging/canary/flag, migrations, предыдущая версия, smoke, logs/metrics/queues, sandbox flow. При отклонении rollback.

## После deploy

Обновить completion/deployment logs, finding/task status, commit hash, environment/version, smoke evidence, residual risks и следующий шаг.

## Запреты

Не тестировать на реальных клиентах без контроля; не создавать реальные production orders/TTN/payments; не раскрывать keys; не удалять без backup; не считать CI достаточным без product smoke; не продолжать при неизвестной migration или расхождении источников истины.
