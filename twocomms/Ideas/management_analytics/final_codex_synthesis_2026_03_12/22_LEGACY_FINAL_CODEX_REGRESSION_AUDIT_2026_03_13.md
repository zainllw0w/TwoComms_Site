# Legacy Final Codex Regression Audit 2026-03-13

## 1. Зачем нужен этот файл
Этот аудит отвечает на конкретный риск:
при переписывании baseline-пакета `final_codex_synthesis_2026_03_06` в новый authoritative пакет могли потеряться старые важные идеи, even if newer ideas were added successfully.

Задача этого файла:
- проверить, что file inventory не деградировал;
- проверить, что старые смысловые блоки не выпали случайно;
- вернуть только то, что было действительно потеряно и не было качественно заменено лучшей новой логикой.

## 2. Что именно сверялось

### 2.1 Папки
- baseline package: `final_codex_synthesis_2026_03_06`
- authoritative package: `final_codex_synthesis_2026_03_12`

### 2.2 Git history
Проверялись baseline-коммиты, из которых исторически собирался старый пакет:
- `b9f7eebe` — add final management analytics synthesis package
- `f66b2045` — refine management analytics synthesis from Opus audit
- `378696da` — integrate Opus second-pass management decisions
- `e725623e` — integrate Opus 4.8 admin economics safely
- `de0bcb81` — strengthen deep research formulas and integrations brief

### 2.3 Метод
- file inventory diff между baseline и authoritative package;
- heading/section comparison для одноимённых файлов;
- точечный semantic search по legacy-терминам;
- manual review only for suspected losses, чтобы не вернуть устаревшие или уже superseded ideas.

## 3. File-level result
По инвентарю baseline-файлы не пропали.

Authoritative package:
- сохраняет весь baseline reference-layer;
- добавляет новые audit / traceability / alignment docs;
- не теряет старые filenames как контейнеры контекста.

Итог:
- file-loss не обнаружен;
- риск был именно в semantic loss, а не в потере файлов.

## 4. Что действительно было потеряно и восстановлено

### 4.1 Payroll carry-forward
Восстановлено:
- `commission dispute workflow`;
- `optional weighted attribution for complex disputes` как admin-approved exception;
- `gross/net preview` only where payroll math supports it without fake precision.

Почему возвращено:
- это не конфликтовало с новой payroll-safe логикой;
- это давало важный admin review contour, который в baseline был сильнее прописан.

Куда возвращено:
- `03_PAYROLL_KPI_AND_PORTFOLIO.md`
- `07_IMPLEMENTATION_ROADMAP.md`
- `11_PRODUCT_BACKLOG_FOR_MANAGEMENT_SUBDOMAIN.md`
- `17_TRACEABILITY_MATRIX_AND_CODE_IMPACT.md`

### 4.2 UI / manager workflow carry-forward
Восстановлено:
- explicit mobile-first manager requirements;
- `client communication timeline`;
- mobile-safe action shell / no-touch report confirm / earnings snapshot as backlog surfaces.

Почему возвращено:
- baseline содержал более точную operational UX-spec;
- новая версия сохранила принципы, но потеряла часть конкретных work surfaces.

Куда возвращено:
- `06_UI_UX_AND_MANAGER_CONSOLE.md`
- `07_IMPLEMENTATION_ROADMAP.md`
- `11_PRODUCT_BACKLOG_FOR_MANAGEMENT_SUBDOMAIN.md`
- `17_TRACEABILITY_MATRIX_AND_CODE_IMPACT.md`
- `19_MANAGEMENT_CODEBASE_ALIGNMENT_MAP.md`

### 4.3 Telephony / QA carry-forward
Восстановлено:
- `Call Competency Profile`;
- QA reliability thresholds (`kappa` bands);
- recording retention / legal hold;
- supervisor actions `monitor / whisper / barge`;
- stricter short-call integrity defaults.

Почему возвращено:
- новый telephony doc сохранил phase-model, но ослабил operational supervisor contour;
- baseline имел полезные safety details, не конфликтующие с current stack.

Куда возвращено:
- `05_IP_TELEPHONY_QA_AND_SUPERVISOR.md`
- `07_IMPLEMENTATION_ROADMAP.md`
- `11_PRODUCT_BACKLOG_FOR_MANAGEMENT_SUBDOMAIN.md`
- `17_TRACEABILITY_MATRIX_AND_CODE_IMPACT.md`

### 4.4 Admin economics carry-forward
Восстановлено:
- explicit cost model;
- contribution proxy;
- break-even / payback signals;
- forecast scenarios;
- clearer confidence structure.

Почему возвращено:
- baseline admin economics был конкретнее;
- новая версия сохранила безопасный framing, но потеряла часть business-interpretation layer.

Куда возвращено:
- `15_ADMIN_ECONOMICS_AND_EARNED_DAY.md`
- `06_UI_UX_AND_MANAGER_CONSOLE.md`
- `11_PRODUCT_BACKLOG_FOR_MANAGEMENT_SUBDOMAIN.md`
- `17_TRACEABILITY_MATRIX_AND_CODE_IMPACT.md`
- `19_MANAGEMENT_CODEBASE_ALIGNMENT_MAP.md`

### 4.5 DTF bridge carry-forward
Восстановлено:
- optional `DTF read-only bridge` как late-phase extension;
- explicit non-mixing rule between DTF and wholesale truth.

Почему возвращено:
- baseline roadmap/backlog содержал этот bridge;
- новая версия сохранила принцип раздельности, но потеряла его как staged module.

Куда возвращено:
- `07_IMPLEMENTATION_ROADMAP.md`
- `11_PRODUCT_BACKLOG_FOR_MANAGEMENT_SUBDOMAIN.md`
- `17_TRACEABILITY_MATRIX_AND_CODE_IMPACT.md`
- `19_MANAGEMENT_CODEBASE_ALIGNMENT_MAP.md`

## 5. Что сознательно не возвращалось
Не возвращались идеи, которые уже были качественно заменены или признаны unsafe:
- любые implicit `Celery / Redis / pg_trgm` assumptions;
- старый `Result` вместо `EWR`;
- weakly specified penalty logic;
- DORMANT-component punishment by default;
- смешивание DTF metrics в wholesale score;
- telephony-heavy payroll dependency до реального rollout.

## 6. Итоговая оценка
После regression pass:
- baseline file inventory сохранён;
- ключевые legacy-идеи, которые действительно выпали из authoritative слоя, возвращены;
- устаревшие или unsafe baseline assumptions обратно не затащены.

Финальный вывод:
критичного legacy context loss больше не видно.

Оставшийся риск уже не в docs synthesis, а в следующем шаге:
при переводе этого пакета в implementation tasks нужно сохранить ту же дисциплину traceability и phase-gating.
