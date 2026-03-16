# Codex Analysis Index

## Цель
Этот пакет документов фиксирует decision-complete спецификацию для management-аналитики, anti-abuse системы, KPI/оплаты, алертов и DTF read-only интеграции в единой управленческой среде.

## Как использовать пакет
1. Прочитать `01_COMPARATIVE_AUDIT.md` и `02_DECISION_MATRIX.md`.
2. Зафиксировать формулы и правила в `03..08`.
3. Использовать `09..11` как технический контракт для имплементации.
4. Применить `12..14` для UX текста, risk-контроля и rollout.

## Карта файлов
- `00_INDEX.md` — навигация и порядок чтения.
- `01_COMPARATIVE_AUDIT.md` — сравнение текущих AI-доков и нового стандарта.
- `02_DECISION_MATRIX.md` — ветки решений A/B/C и финальные выборы.
- `03_HYBRID_SCORE_SPEC.md` — гибридный score (HES + Gate + Trust + ROI + ELO).
- `04_TRUST_AND_ANTI_ABUSE.md` — anti-gaming и trust-логика.
- `05_KPI_PAYROLL_UNIT_ECONOMICS.md` — KPI, test period, ставка/проценты, ROI.
- `06_CLIENT_PROCESSING_FLOW.md` — обязательный flow обработки клиента.
- `07_ALERTS_AND_ADVICE.md` — daily/10:00 алерты, no-report, советы.
- `08_DASHBOARDS_ADMIN_MANAGER.md` — различие manager/admin аналитики.
- `09_DTF_BRIDGE_V1.md` — DTF read-only bridge без смешивания метрик.
- `10_DATA_MODEL_API_CONTRACT.md` — модели, API, права, ограничения.
- `11_TEST_ACCEPTANCE_MATRIX.md` — тесты и acceptance criteria.
- `12_UI_MODAL_COPY_BRIEF.md` — короткий пакет UX/microcopy.
- `13_RISK_REGISTER_BRIEF.md` — краткий реестр рисков.
- `14_ROLLOUT_DEPLOY_BRIEF.md` — краткий план внедрения.

## Сравнение с текущим `management_analytics`
- Этот пакет не заменяет `01..08`, а является контрольным эталоном для сравнения.
- Критерий качества: документы должны быть готовы к прямой имплементации без дополнительных продуктовых решений.

## Базовые решения
- Hard gate по конверсиям: включен.
- Trust coefficient: включен.
- Dual KPI (weekly hard + daily soft): включен.
- ROI component: включен.
- DTF v1: read-only bridge.
- Alerts: TG + in-app.
- No-report в 10:00: manager не получает digest, admin получает флаг.
- Дисциплинарные штрафы: только admin-verified.
