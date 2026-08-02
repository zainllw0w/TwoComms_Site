# Обязательные результаты и контрольные ворота

## Файлы, создаваемые агентом в `docs/instagram_bot_audit/`

1. `00_PROGRESS.md`
2. `01_SYSTEM_MAP.md`
3. `02_AUDIT_CHECKLIST.md`
4. `03_FINDINGS_REGISTER.md`
5. `04_DECISION_LOG.md`
6. `05_DATA_AND_EVENT_CATALOG.md`
7. `06_TEST_MATRIX.md`
8. `07_IMPLEMENTATION_PLAN.md`
9. `08_COMPLETION_LOG.md`
10. `09_DEPLOYMENT_LOG.md`
11. `10_OPEN_QUESTIONS_AND_BLOCKERS.md`
12. `11_FINAL_VALIDATION_REPORT.md`

## Progress-файл

Храни текущую фазу, task ID, последний подтверждённый результат, следующий шаг, незакрытые проверки, finding IDs, изменения после commit, commit hash/environment и блокеры. Обновляй после каждого существенного блока.

## G0 — до аудита

- [ ] baseline branch/commit;
- [ ] environments и запретные production-действия;
- [ ] команды запуска/тестов;
- [ ] секреты не копируются;
- [ ] создана папка аудита и progress.

## G1 — карта системы

- [ ] entry points;
- [ ] agents/prompts/memory/providers;
- [ ] webhooks/workers/cron/queues;
- [ ] data models и Instagram user/order;
- [ ] component/data/sequence diagrams;
- [ ] нет неизвестных основных компонентов.

## G2 — завершение аудита

- [ ] 120 task IDs закрыты;
- [ ] у ISSUE есть finding;
- [ ] у PASS есть evidence;
- [ ] у BLOCKED есть конкретный блокер;
- [ ] критичные потоки проверены вторично;
- [ ] проверено фактическое поведение, а не только код.

## G3 — готовность плана

- [ ] tasks ссылаются на findings;
- [ ] P0–P3;
- [ ] dependencies/risk/migration;
- [ ] tests/acceptance;
- [ ] rollback;
- [ ] атомарные вертикальные срезы.

## G4 — готовность deploy

- [ ] red test;
- [ ] target tests green;
- [ ] regression green;
- [ ] migrations forward/backward;
- [ ] no secrets/PII;
- [ ] docs updated;
- [ ] atomic commit;
- [ ] staging/canary smoke;
- [ ] rollback ready.

## G5 — финал

- [ ] P0 и согласованный P1 закрыты;
- [ ] нет незадокументированных отклонений;
- [ ] аналитика сверена контрольной выборкой;
- [ ] нет duplicate messages/events;
- [ ] нет регрессий ownership/pause;
- [ ] UI не вводит администратора в заблуждение;
- [ ] final validation report готов.
