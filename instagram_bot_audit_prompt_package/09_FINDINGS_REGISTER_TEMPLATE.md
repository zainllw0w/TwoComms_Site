# FINDINGS_REGISTER — шаблон

## Правила

Один finding — одна конкретная проблема/риск. Любое утверждение имеет evidence. IDs: `F-ARCH-001`, `F-AI-001`, `F-UX-001`. Закрытые findings не удалять.

## Карточка

### F-<DOMAIN>-<NNN>: <название>

- **Статус:** OPEN / CONFIRMED / PLANNED / IN_PROGRESS / FIXED / VERIFIED / ACCEPTED_RISK / NOT_REPRODUCED
- **Тип:** bug / logic / architecture / debt / security / performance / AI / data / analytics / UX / documentation
- **Severity:** P0 / P1 / P2 / P3
- **Confidence:** low / medium / high
- **Audit tasks:**
- **Компоненты/файлы:**
- **Первое обнаружение:** timestamp/commit
- **Фактическое поведение:**
- **Ожидаемое поведение:**
- **Воспроизведение:**
- **Evidence:** code/test/log/query/screenshot ID
- **Первопричина:**
- **Почему важно:**
- **Пользовательское влияние:**
- **Data/finance/operations:**
- **Связанные подсистемы:**
- **Граничные случаи:**
- **Варианты решения:**
- **Рекомендация и обоснование:**
- **Риск изменения:**
- **Тесты:**
- **Migration/backfill:**
- **Rollback:**
- **Acceptance criteria:**
- **Implementation task:**
- **Commit/PR/deploy:**
- **Post-deploy verification:**
- **Residual risk:**

## Сводный реестр

| ID | Название | Severity | Status | Confidence | Audit task | Owner | Implementation |
|---|---|---:|---|---|---|---|---|
