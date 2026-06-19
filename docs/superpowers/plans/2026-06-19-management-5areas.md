# Management-субдомен TwoComms — 5 областей: план реализации

> **For agentic workers:** трекер многофазной работы. Шаги отмечаем `[x]`.
> Канон утверждён пользователем (см. «Решения»). Деньги/выплаты НЕ трогаем.

**Goal:** Глобально починить баг скролла; усилить AI-чекер лидов; починить и
улучшить IG-бота (live chat, баг обнуления, консоль, fallback моделей); сделать
надёжный каскад ключей Gemini (ротация API3→API4 + деградация моделей + пропуск
биллинговых); реактивировать и выправить рейтинг MOSAIC как чистую аналитику
качества (без влияния на деньги).

**Architecture:** Django 5 (Py 3.13), прод — MySQL + Passenger, статика —
WhiteNoise `CompressedManifestStaticFilesStorage`. Gemini — прямой REST через
`services/call_ai_analysis.py` (HTTP/перебор) + `services/gemini_keys.py`
(политика ключей/моделей/квот). IG-бот — webhook + демон `run_instagram_bot
--forever` (без Celery). MOSAIC — подневные `NightlyScoreSnapshot` (cron
`compute_nightly_scores`), `rollout_state=shadow`.

## Решения пользователя (канон)

- Порядок фаз: **0 скролл → 1 Gemini-ядро → 2 чекер → 3 IG-бот → 4 MOSAIC**.
- «3→4» = **ротация ключей `GEMINI_API3 → GEMINI_API4`** (в пуле management), не модели.
- **Деньги ↮ MOSAIC.** `weekly_kpi/weekly_review/payroll/compensation/payouts/
  manager_levels.promote` — НЕ менять. MOSAIC = аналитический рейтинг качества.
- **Канон MOSAIC = текущий код**, не MD-файлы в `Ideas/`. Поднять отключённое.
- MOSAIC должен зависеть от РАБОТЫ менеджера (B2B холодные звонки в физмагазины,
  эталона нет); «ниже 14» возможно при долгой бездеятельности, но трудно.

## Деплой после КАЖДОЙ фазы (workflow.md)

1. `git add <свои файлы>` (только свои!), commit, `git push` (main).
2. SSH-деплой: `git pull`; `migrate --no-input` (если миграции);
   `collectstatic --no-input` (если менялась статика/CSS/JS);
   `compress --force` (ТОЛЬКО если трогали `twocomms_django_theme/base.html`
   с `{% compress %}` — для management-страниц НЕ нужно, там прямые `{% static %}`);
   `touch tmp/restart.txt` последним.
3. Sanity-curl `/`, `/parsing/`, `/stats/` и т.п. — ожидать 200/302.

Пред-сущие чужие правки в дереве (`finance-payables-settlement/plan.md`,
`admin_manual_order.html`) — НЕ коммитить. Тесты: из корня репо
`SECRET_KEY=test_local_secret python twocomms/manage.py test management.<m> --settings=test_settings`.

---

## Фаза 0 — Глобальный фикс скролла (CSS-only, без JS/шаблонов)

**Корень:** `.workspace { height: calc(100vh - var(--shell-header-offset)) }`,
где `--shell-header-offset`=76px, а реальный `.global-header`=113px (76 + padding
18×2 + border 1; нет глобального `box-sizing` reset). При `body{overflow:hidden}`
низ контента (~37px) обрезается. JS (`management-shell.js`) чинит offset, но
только для whitelist-страниц (`data-mgmt-shell="1"`) → на остальных баг.

**Решение (debt-free, global):** `body` → grid `auto / 1fr` фикс. высоты 100vh;
`.workspace` берёт `1fr` (без calc и без зависимости от offset); `.content-area`
→ `box-sizing:border-box`. Работает при любой высоте хедера, без whitelist, без
JS. Безопасно: у `body` ровно 2 потоковых ребёнка (header + workspace); модалка
`position:fixed`, аудио-плеер — style+script, `::after` — absolute.

- [ ] `management.css`: `.management-body` → `height:100vh; display:grid; grid-template-rows:auto 1fr;` (было `min-height:100vh`).
- [ ] `management.css`: `.workspace` → убрать `height:calc(...)` (берёт 1fr).
- [ ] `management.css`: `.content-area` → добавить `box-sizing:border-box;`.
- [ ] `management.css`: мобильный `@media(max-width:1080px)` → `.management-body{display:block;height:auto;overflow:auto}` (вернуть поток на мобиле).
- [ ] `management.css`: удалить per-page band-aid выплат (`calc(100vh-113px)`).
- [ ] `management-stats.css`: удалить per-page band-aid статистики (оставить `.stats-page--v2{padding-bottom}`).
- [ ] Тест: `tests_template_regressions` зелёные; быстрый прогон `tests_cp_page`/смежных.
- [ ] Деплой: collectstatic + restart (compress не нужен). Sanity-curl ключевых страниц.

**Риск:** низкий (CSS-only, обобщает уже работающий в проде band-aid). Регресс
SPA-скролла (`management-shell.js` использует `.content-area` как скролл-контейнер
— он сохранён). Визуальная проверка — на проде сразу после деплоя.

---

## Фаза 1 — Gemini-ядро: ротация ключей + надёжный каскад

**Файлы:** `services/gemini_keys.py` (политика), `services/call_ai_analysis.py`
(перебор), миграция при изменении `GeminiKeyState`. Потребители (не сломать):
бот `chat` (`instagram_bot.py`), `bot_orders/bot_vision` (management),
`analyze_call`+`run_call_ai_analyses` (management), чекер (`lead_checker` grounded).

**Задачи (детализировать при старте фазы, TDD на `tests_gemini_keys.py`):**
- [ ] Подтвердить реальные ID моделей через `ListModels` двумя ключами; привести цепочки к доступным; гарантировать нижний фолбэк (2.5-flash/lite) для management.
- [ ] «3→4» ротация ключей: внутри пула management чередовать API3→API4 (key-major-aware), сохранив принцип «3.5 раньше младших». Учесть, что текущий model-major — осознанное решение (docstring `iter_attempts`); согласовать оба требования.
- [ ] Статический per-role skip-list платных моделей (pro-preview) + рантайм-кэш «модель платная сегодня» в БД (межпроцессно, как `GeminiKeyState`), чтобы не бить платную N×.
- [ ] Дедлайн для management (сейчас нет) против зависаний; backoff без лишних кругов.
- [ ] Учёт токенов per-key/day (агрегат) для прогноза/бюджета (используется в Фазе 2 UI).
- [ ] Обновить мокающие тесты (`tests_checker_gemini`, `tests_ig_*`, `tests_bot_memory`).

**Риск:** ВЫСОКИЙ (общее ядро для бота/чекера/анализа; пул API5/6 общий
checker-own + chat/mgmt-borrow). Снять baseline тестов до правок.

---

## Фаза 2 — AI-чекер лидов

**Файлы:** `services/lead_checker.py`, `lead_check_job.py`, `checker_views.py`,
`templates/management/leadops/_checker_*.html`, `parsing_views.py` (модерация),
`models.py` (агрегаты токенов на `LeadCheckJob`?). Пред-сущий план:
`docs/superpowers/plans/2026-06-18-ai-lead-checker.md`.

**Задачи:**
- [ ] Промпт: рубрика-якоря + few-shot + жёсткий гейт «не продаёт одежду → unfit/потолок» (бренд = одежда; снаряга/оптика/оружие без текстиля не подходят). Добавить критерий `apparel_focus`; переосмыслить `military_tactical`, чтобы не тянул воентторги.
- [ ] Серверная калибровка score (детерминированный пересчёт из взвешенных критериев + гейты) → убрать «всегда ~85».
- [ ] UI: токены потрачено (сессия/ключ), прогноз «сколько ещё успеем» (avg×remaining + бюджет квоты), таймер; пауза уже есть — проверить UX.
- [ ] Модерация: фильтры по ключевому слову / `ai_verdict` / `ai_score` / городу; показать AI-вердикт в карточке (`_serialize_moderation_lead`).
- [ ] Фоновый чекинг на дни: усилить `checker_tick` cron + бюджетирование квот.
- [ ] Мёртвый код: удалить `checker.html`; решить судьбу `model_chain` (оживить/убрать). `checker_recheck` синхронный → фон/пошагово.
- [ ] Тесты: `tests_checker_scoring/gemini/job/views` + новые.

**Риск:** средний. Зависит от Фазы 1 (модели/токены).

---

## Фаза 3 — IG-бот: баг обнуления, live chat, консоль, модели

**Файлы:** `templates/management/bot.html` (JS), `bot_views.py`
(`bot_status_api`, `bot_client_detail_api`), `services/instagram_bot.py`,
`ig_bot_models.py`.

**Задачи:**
- [ ] Баг обнуления: устранить JS Temporal Dead Zone (`activate(startTab)` зовёт `Clients.load()` до `const Clients`). Объявить модули до `activate`, обернуть IIFE в try/catch.
- [ ] Live chat: инкрементальный polling переписки в карточке (курсор `after_id`, как у логов), бэк-офф когда вкладка скрыта/бот неактивен; без WebSocket (Passenger). Не нагружать сервер.
- [ ] Консоль: структурировать события (сценарий/функция/шаг/sender), читаемость.
- [ ] Модель: оживить или убрать мёртвый dropdown `gemini_model`; синхронизировать имена моделей с Фазой 1.
- [ ] Оптимизация polling (статус 2с всегда → бэк-офф при stopped/idle).
- [ ] Тесты: `tests_ig_clients_ui`, `tests_ig_*` + новые на live-курсор и инициализацию.

**Риск:** средний. Демон/webhook двойная обработка — не сломать `_claim_next`.

---

## Фаза 4 — MOSAIC: реактивация + выправление формул (только рейтинг)

**Файлы (РЕЙТИНГ, можно менять):** `services/score.py`, `snapshots.py`,
`trust.py`, `analytics_v7.py`, `candidate_potential.py`, `outcomes.py`,
`stats_service.py` (compute_kpd/_shadow_score_payload), `telephony.py`,
`payroll.py` ТОЛЬКО `compute_onboarding_floor_score`/`compute_rescue_spiff`/
`compute_earned_day_state`/`effective_phase0_dmt`, `config_versions.py`,
`appeals.py`, `commands/compute_nightly_scores.py`, `seed_management_defaults.py`.
**НЕ трогать (деньги):** `weekly_kpi.py`, `weekly_review.py`, `compensation.py`,
`payouts.py`, `payroll.compute_working_factor/compute_repeat_commission`,
`tasks.accrue_weekly_salaries`, `manager_levels.promote/demote`.

**Подтверждённые баги (исправить, TDD):**
- [ ] `candidate_potential.py:169` `confidence/100` → `clamp01(confidence)` (confidence уже 0..1).
- [ ] `trust.py:61-62` мёртвая строка телефонии (перекрыта клампом ≥0.85) — убрать/осмыслить.
- [ ] `trust.py` двойной штраф `overdue_followups` (report_integrity + anomaly) — развести.
- [ ] `score.py:124` `verified_slice = base*verified_share` применяет долю result ко ВСЕМУ base — считать от вклада оси result.
- [ ] `analytics_v7.py:425` апелляции `delta_score=0` всегда — считать дельту при approve; `appeals.py:24` хардкод 48h → из конфига.
- [ ] `snapshots.py` историч.снапшоты `freshness=0→recency=1.0` — хранить `computed_at`.
- [ ] Пороги confidence рассинхрон (`is_low_confidence<0.65` vs band 0.50/0.80) — единый из конфига.
- [ ] `value_at_risk` фабрикуется хардкодом — из реальной выручки.

**Free-baseline → «ниже 14 возможно, но трудно»:**
- [ ] EWR neutral/effort за пустой объём (`score.py:42,45`); follow_up=1.0 при total=0 (`snapshots.py`); data_quality≈1.0/reason_quality=1.0 при 0 обязательств (`outcomes`); source_fairness=0.5; vc floor=0.25 → вне `active`. Добавить `inactivity_decay(consecutive_zero_workdays)` (плавно, по образцу onboarding_floor).

**Реактивация (осторожно):**
- [ ] Проверить в проде строки `ComponentReadiness` (shadow vs dormant для VC) перед изменением весов.
- [ ] `tasks.check_auto_promotions` — уведомление админу (TODO) — но сначала ужесточить анти-абьюз условий (это влияет на промоушн→деньги, согласовать).
- [ ] Двойная материализация `ManagerDayFact` (`snapshots`+`analytics_v7`) — устранить дубль.
- [ ] `mosaic_config.weights` игнорируется (`score.MOSAIC_WEIGHTS` хардкод) — подключить конфиг или зафиксировать намеренно.

**Риск:** высокий (формулы, ночной пересчёт по всем). Менять только рейтинг,
деньги не трогать. Огромный набор тестов: `tests_phase3_snapshots`,
`tests_phase4_analytics`, `tests_visible_points_v2`, `tests_manager_levels` + новые.
