# 02_AUDIT_CHECKLIST — статус 120 исходных проверок

Источник строк: `instagram_bot_audit_prompt_package/03_AUDIT_CHECKLIST_120_TASKS.md`.
Это статус **аудита**, а не утверждение, что все implementation-задачи закрыты.
Каждая строка исходного A01–L10 проверена; code gaps вынесены в `F-*` и `IMP-*`.

| Домен | Проверенные IDs | Статус аудита | Основное evidence |
|---|---|---|---|
| A. Архитектура | A01–A10 | [x] DONE | `01_SYSTEM_MAP.md`, `03_FINDINGS_REGISTER.md` |
| B. Код/долг | B01–B10 | [x] DONE | `03_FINDINGS_REGISTER.md`, `04_DECISION_LOG.md` |
| C. Ключи/провайдеры | C01–C10 | [x] DONE | `01_SYSTEM_MAP.md`, `03` F-AI/F-SEC, contract tests |
| D. AI/prompt/memory | D01–D10 | [x] DONE | `03` F-AI, `05_IMPROVEMENTS_REGISTER.md` |
| E. Продажи/follow-up | E01–E10 | [x] DONE | `06_FUNNEL_CLOSING_DESIGN.md`, W4B/W5 entries in `07` |
| F. Воронки | F01–F10 | [x] DONE | W6/F-STATE entries in `03` and `07` |
| G. Checkout/payments | G01–G10 | [x] DONE | `05_DATA_AND_EVENT_CATALOG.md`, F-PAY entries |
| H. Nova Poshta/post-sale | H01–H10 | [x] DONE | F-SHIP/F-OPS entries, IMP-020…024/055/062 |
| I. Скоринг/классификация | I01–I10 | [x] DONE | F-SCORE entries, IMP-013…019/029/030 |
| J. Реклама/аналитика | J01–J10 | [x] DONE | F-DATA/F-STAT entries, IMP-043/058 |
| K. Admin UX | K01–K10 | [x] DONE | W7 evidence, `bot_views.py`, UI tests |
| L. Security/tests/release | L01–L10 | [x] DONE | F-SEC/F-TEST, `06_TEST_MATRIX.md`, deploy logs |

**Итого:** 120/120 audit items have evidence. `DONE` здесь означает «проверено и
отражено», а не «все найденные дефекты исправлены». Текущий implementation
остаток находится только в `07_IMPLEMENTATION_PLAN.md`.

**Checkpoint 2026-08-05:** повторная сверка коммерческих эпизодов и W9 не
добавила пропущенных исходных A01-L10, но добавила четыре конкретные находки в
реестр: F-CAT-005, F-CAT-006, F-CAT-007 и F-PAY-015. Все четыре теперь
`FIXED / VERIFIED`; для F-CAT-007 production `0ad694bc` доказывает точный
variant-specific price/size prompt contract. Follow-up source reconciliation
добавила requirements `IMPR-FUP-014/015` и `IMP-102/103`; delivery pair
`IMP-102`/`IMPR-FUP-014` и event continuation `IMP-103`/`IMPR-FUP-015`
закрыты production `13bedf8f`.
Выявленная и исправленная race F-FUP-013 добавлена в findings register, но не
меняет число исходных audit items: оно остаётся 120.
