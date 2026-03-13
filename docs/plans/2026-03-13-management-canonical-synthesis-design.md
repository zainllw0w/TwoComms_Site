# Management Canonical Synthesis Design

**Date:** 2026-03-13

## Goal

Создать новую canonical-папку для management analytics, которая заменяет роль `final_codex_synthesis_2026_03_12` как основной handoff-пакет для следующего агента, готовящего единый implementation file.

## Why A New Package

- Базовый пакет уже силён как normative слой, но часть улучшений осталась во внешнем addendum.
- `tc_mosaic_improvements` усиливает слабые места формул, governance, UX и operational semantics.
- `i1` добавляет критичный code-reality слой: скрытые интеграции, реальные модели, service/view mapping, dependency order и implementation blockers.
- Следующий агент не должен повторно собирать контекст из трёх разрозненных наборов файлов.

## Design Decision

Новая папка строится как единый canonical package, а не как patch-set над старой версией.

Внутри неё должны быть:

1. `authoritative`-контракт по каждой подсистеме.
2. Явная связка с реальным кодом и текущими ограничениями проекта.
3. Anti-loss механизмы: source coverage, decision log, rejected/reference-only items.
4. Implementation-facing артефакты: dependency order, testing contract, agent handoff brief.

## Proposed File Shape

- `00_INDEX_AND_AUTHORITY_MANIFEST.md`
- `01_EXECUTIVE_CANONICAL_SYNTHESIS.md`
- `02_SYSTEM_ARCHITECTURE_AND_INVARIANTS.md`
- `03_SCORE_MOSAIC_EWR_CONFIDENCE.md`
- `04_PAYROLL_KPI_PORTFOLIO_EARNED_DAY.md`
- `05_IDENTITY_DEDUPE_FOLLOWUP_ANTI_ABUSE.md`
- `06_TELEPHONY_QA_SUPERVISOR_VERIFIED_COMMUNICATION.md`
- `07_MANAGER_ADMIN_UX_EXPLAINABILITY.md`
- `08_ADMIN_ECONOMICS_FORECAST_DECISION_SAFETY.md`
- `09_CODE_REALITY_MODEL_SERVICE_ENDPOINT_MAP.md`
- `10_GOVERNANCE_DATA_MODEL_JOBS_ROLLOUT.md`
- `11_EDGE_CASES_FAILURE_MODES_AND_SCENARIOS.md`
- `12_TEST_STRATEGY_VALIDATION_ACCEPTANCE.md`
- `13_IMPLEMENTATION_BLUEPRINT_AND_DEPENDENCY_ORDER.md`
- `14_AGENT_HANDOFF_BRIEF_FOR_IMPLEMENTATION_FILE.md`
- `15_TRACEABILITY_MATRIX_AND_SOURCE_COVERAGE.md`
- `16_DECISION_LOG_REJECTED_IDEAS_AND_BACKLOG.md`
- `17_PACKAGE_CHANGELOG_AND_SUPERSESSION.md`

## Content Rules

- Текст только declarative, без диалоговой подачи.
- Любая новая идея должна иметь статус: `authoritative`, `shadow/admin-only`, `backlog`, `reference-only` или `rejected`.
- Любая integration-sensitive идея должна иметь привязку к коду или explicit note, что это future extension.
- Любой крупный раздел должен содержать:
  - invariant rules,
  - activation/phase semantics,
  - failure/edge guards,
  - implementation anchors,
  - запреты на неверную реализацию.

## Acceptance Criteria

- Ни один источник из трёх входных папок не остаётся без покрытия в source coverage matrix.
- Новый пакет читается последовательно без необходимости открывать старые папки.
- Следующий агент может построить implementation file, не восстанавливая вручную структуру системы.
- В пакете есть явное разделение между production-contract, shadow layer и reference history.

## Execution Note

Пользователь уже подтвердил этот дизайн и ожидает немедленную сборку пакета в той же сессии.
