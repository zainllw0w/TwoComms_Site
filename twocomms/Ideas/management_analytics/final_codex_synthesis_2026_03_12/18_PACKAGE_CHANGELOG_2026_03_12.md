# Package Changelog 2026-03-12

## Назначение
Этот файл фиксирует, чем пакет `final_codex_synthesis_2026_03_12` отличается от baseline-папки `final_codex_synthesis_2026_03_06`.

Он нужен не как формальная история версий, а как быстрый ответ на вопрос:
"что именно стало новым authoritative слоем после большого мартовского отчёта?"

## Главные изменения пакета
- Сформирован новый authoritative слой, отделённый от historical/reference документов.
- В пакет добавлены явные документы по `traceability`, `code impact` и `package delta`.
- Убраны технологические допущения, не совместимые с текущим хостингом.
- Все ключевые подсистемы приведены к phase-aware и safe-by-default логике.
- Пакет теперь описывает не только продуктовые идеи, но и реальные точки будущего внедрения в `management`.

## Изменения по файлам

### Файлы, переписанные как нормативные
- `00_INDEX.md`
- `01_MASTER_SYNTHESIS.md`
- `02_MOSAIC_SCORE_SYSTEM.md`
- `03_PAYROLL_KPI_AND_PORTFOLIO.md`
- `04_ANTI_DUPLICATION_AND_FOLLOWUP_ENGINE.md`
- `05_IP_TELEPHONY_QA_AND_SUPERVISOR.md`
- `06_UI_UX_AND_MANAGER_CONSOLE.md`
- `07_IMPLEMENTATION_ROADMAP.md`
- `10_SOURCE_MAP_AND_EXTERNAL_BEST_PRACTICES.md`
- `11_PRODUCT_BACKLOG_FOR_MANAGEMENT_SUBDOMAIN.md`
- `12_CALIBRATION_DEFAULTS_AND_PRESETS.md`
- `13_CROSS_SYSTEM_GUARDRAILS.md`
- `14_OPUS_SECOND_PASS_DECISION_LOG.md`
- `15_ADMIN_ECONOMICS_AND_EARNED_DAY.md`

### Файлы, сохранённые как reference
- `08_CODEX_SUPERIORITY_ANALYSIS.md`
- `09_RESEARCH_QUESTIONS_FOR_DEEP_AGENT.md`
- `16_ADDITIONAL_RESEARCH_PROMPT.md`
- четыре больших исходных research-документа, которые остаются внутри папки для полноты контекста

### Новые файлы
- `17_TRACEABILITY_MATRIX_AND_CODE_IMPACT.md`
- `18_PACKAGE_CHANGELOG_2026_03_12.md`
- `19_MANAGEMENT_CODEBASE_ALIGNMENT_MAP.md`
- `20_SECOND_PASS_AUDIT_2026_03_12.md`
- `21_THIRD_PASS_AUDIT_2026_03_12.md`
- `22_LEGACY_FINAL_CODEX_REGRESSION_AUDIT_2026_03_13.md`

## Ключевые смысловые дельты

### 1. Технологии
Было:
- `Celery`
- `Redis`
- `pg_trgm`

Стало:
- `Django management commands`
- `cron`
- `FileBasedCache`
- `SequenceMatcher`

### 2. Score
Было:
- старая конфигурация MOSAIC с риском штрафа за DORMANT оси
- старый `Result`

Стало:
- `EWR` как финальная реализация `Result`
- `Component Readiness Registry`
- `Trust production + diagnostic`
- финальный `dampener` и `gate` без внутренних противоречий

### 3. Payroll
Было:
- риск cliff penalty
- неявная связь KPI и repeat-commission

Стало:
- `Soft Floor Cap`
- чёткие KPI для `new` и `total`
- phase-aware `DMT`
- weekend / excused / force majeure / snooze rules

### 4. Product + UX
Было:
- хорошие идеи разбросаны по отчётам

Стало:
- единая UX-спецификация для manager/admin
- `Radar`, `Top-5 rescue`, `Salary Simulator`, `Golden Hour`, recovery-first copy
- точная связь идей с текущими шаблонами `stats.html`, `admin.html`, `base.html`

### 5. Planning readiness
Было:
- идеи есть, но implementation traceability неполная

Стало:
- у каждой крупной идеи есть своё место в пакете
- есть matrix: `источник -> authoritative doc -> code impact`
- следующий этап можно переводить в полноценный implementation plan без повторного сбора контекста

## Дополнительный hardening после второго аудита
- добавлен `repeat vs reactivation` split с `180-day` cutoff;
- formalized `Omni-Touch` for Phase 0 и accelerator thresholds;
- зафиксированы `Batch Import Dry-Run`, merge rollback window и master-record rule;
- Radar выровнен по authoritative MOSAIC axes, а не по альтернативному coaching-profile набору;
- добавлены confidence labels, hold-harmless shadow rule и более точный validation protocol;
- расширены guardrails вокруг `Force Majeure`, `FileBasedCache` и day-status semantics.

## Дополнительный hardening после третьего аудита
- authoritative docs теперь явно фиксируют `Weibull` churn как primary rescue/portfolio model с logistic fallback для `<5` заказов, planned-gap guard и `k`-cap;
- возвращён `Wilson` conversion diagnostic как admin/shadow metric, чтобы не терять conservative small-sample validation рядом с `EWR`;
- `Top-5 rescue` больше не держится на неявном `P(churn)`: добавлены scaled `SPIFF (500-2000 грн)` и guard `max 3 rescue-leads/day + DQ grace`;
- anti-gaming rate limit смягчён до production-safe semantics: action записывается в CRM, но перестаёт приносить score-credit;
- shadow rollout теперь удерживает явные DICE guardrails и waterfall explainability contract;
- traceability, backlog и codebase alignment обновлены так, чтобы эти элементы больше не выпадали между docs и будущим implementation planning.

## Дополнительный hardening после legacy-regression pass
- старый Final Codex пакет и git-history были повторно сверены на предмет file-loss и idea-loss, а результат зафиксирован в `22_LEGACY_FINAL_CODEX_REGRESSION_AUDIT_2026_03_13.md`;
- в authoritative слой возвращены `commission dispute workflow` и optional weighted attribution как admin-approved exception;
- восстановлены explicit mobile-first manager requirements и `client communication timeline`;
- telephony/QA слой снова фиксирует `Call Competency Profile`, QA reliability thresholds, retention policy и supervisor actions;
- admin economics снова включает cost model, contribution proxy, break-even / payback / forecast logic;
- roadmap/backlog/alignment-map снова содержат optional `DTF read-only bridge` как отдельный, не смешиваемый с wholesale truth extension.

## Как использовать этот changelog
- Если нужно быстро понять, что изменилось глобально, читай этот файл.
- Если нужно понять, где теперь находится конкретное решение, переходи в `17_TRACEABILITY_MATRIX_AND_CODE_IMPACT.md`.
- Если нужно понять, куда это ляжет в текущем `management`, переходи в `19_MANAGEMENT_CODEBASE_ALIGNMENT_MAP.md`.
