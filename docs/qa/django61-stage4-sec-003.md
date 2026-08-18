# Django 6.1 Stage 4: DJ6-SEC-003

Дата проверки: 2026-08-18.

## Результат

Contract-аудит non-DTF `csrf_exempt` surface завершён. Полный tracked inventory
и требования к компенсирующим controls находятся в
`docs/security/csrf-exempt-contracts.md`. Массовое снятие exemptions не
выполнялось.

Исторический grep в плане показывал 26 совпадений. AST-инвентаризация
подтвердила 25 исполняемых occurrences: 20 function decorators и 5 URL-level
wrappers. Оставшееся совпадение является поясняющим комментарием в
`twocomms/storefront/urls.py`, а не endpoint. Отдельно учтены семь decorators
в runtime-loaded `twocomms/storefront/views.py.backup`, включая их фактическое
отношение к `_LEGACY_VIEW_NAMES` и внешним route wrappers.

Для каждого исполняемого occurrence зафиксированы:

- route и method;
- auth или provider signature;
- replay/idempotency contract;
- rate-limit contract или честно отмеченный gap;
- origin/host boundary;
- observability, owner и removal plan;
- обязательные negative-test scenarios.

Статический gate сканирует только tracked Python sources, проверяет AST,
legacy-loader provenance и соответствие Markdown inventory. Он падает при
появлении незадокументированного exemption, исчезнувшего source site или
неполного contract row. Gate не импортирует Django, не использует сеть и не
изменяет БД.

## Проверка

```text
$ TWC_PYTHON=.../.venv/bin/python \
    \"$TWC_PYTHON\" -m unittest tests/test_csrf_exempt_contract.py
Ran 26 tests in 2.600s
OK
```

## Оставшиеся remediation gaps

`DJ6-SEC-003` закрывает contract-аудит, но не выдаёт непроверенным controls
статус реализованных. В inventory явно остаются follow-up задачи: публичные
legacy Telegram link/debug endpoints, fail-open конфигурация warehouse
Telegram webhook, replay markers для части provider callbacks, а также
endpoint-level rate limits и reject metrics там, где они отсутствуют. Эти
изменения нужно выпускать отдельными узкими security slices с runtime tests;
они не блокируют полноту inventory и Stage 4 contract exit gate. Остальные
exit gates Stage 4 (CSP browser matrix, observability и MariaDB constraints)
остаются открыты.
