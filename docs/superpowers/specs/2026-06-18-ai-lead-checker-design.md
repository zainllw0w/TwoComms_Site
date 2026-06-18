# AI-чекер спарсенных аккаунтов — дизайн

> Дата: 2026-06-18. Статус: утверждён пользователем (v2).
> Контекст: субдомен менеджмента TwoComms, Django-приложение `management`.

## 1. Проблема и цель

Парсер Google Places насобирал ~4000 `ManagementLead` (статус `moderation`,
`lead_source=parser`). Модератор вручную не успевает понять, какие аккаунты
пригодны для сотрудничества. Нужен AI-чекер: оценивает каждый спарсенный
аккаунт через Gemini с веб-поиском (grounding), ставит балл 0-100 по 10
критериям, даёт разбор бренда и рекомендацию по каналу сотрудничества.
Чекер — отдельная вкладка рядом с «Парсинг», единое целое с парсером.

## 2. Аудитория TwoComms (эталон для промпта)

Бренд: украинский streetwear с military-adjacent ДНК и патриотикой, унисекс.
Ассортимент: футболки, худі, лонгсліви, мерч, **кастомный DTF-друк**. Сегмент —
«доступний streetwear-преміум».

Покупатели: ≈40% военные · ≈20% волонтёры / окловоенные / «українська
військова рух» · ≈40% гражданские, которым близка urban / streetwear /
military-adjacent эстетика. Мужчины И женщины. **Эстетика важнее пола** —
гендер не является дисквалифицирующим фильтром.

Ориентир-сегмент конкурентов: украинские streetwear-бренды (STLV-подобные,
Good Boys Club, Hate Cult и т.п.) — живут в Instagram, drop-культура,
кастомные принты, авторская графика.

## 3. Каналы сотрудничества (`partnership_fit`, список)

1. `wholesale` — опт готового ассортимента TwoComms
2. `custom_print` — кастом-друк под их бренд (white-label; питч «возьмёте опт —
   напечатаем любой принт, хоть из Pinterest»)
3. `collab` — совместный дроп
4. `dropship` — дропшип
5. `test_batch` — тестовая партия
6. `shelf` — физмагазин / военторг ставит наш товар на полку

Кандидат может подходить под несколько каналов одновременно.

## 4. Критерии оценки (10, каждый 0-10)

1. Релевантность товара (одежда/мерч/принтованный текстиль).
2. Стиль/эстетика (streetwear / urban / military-adjacent / патриотика / авторская графика).
3. Совпадение ЦА (военные/волонтёры/окловоенные/молодёжь/патриоты/urban; без штрафа за женскую аудиторию).
4. Милитари/тактика (военторг/армейский магазин — сильный плюс).
5. Потенциал кастом-друку / white-label.
6. Потенциал опта готового ассортимента.
7. Потенциал коллаборации (свой бренд + история + drop-культура + прошлые коллабы).
8. Онлайн-присутствие и охват (сайт И/ИЛИ Instagram/TikTok, активность).
9. Бизнес-профиль (своё производство/бренд vs перекуп; масштаб город/сеть/онлайн).
10. Реалистичность захода (контактность, бизнес живой, не самодостаточный конкурент).

Доп. поля вердикта:
- `overall_score` 0-100 — холистическая оценка (НЕ простая сумma критериев).
- `verdict_category` ∈ {physical_store, retail_chain, dropshipper, brand,
  voentorg, marketplace_seller, irrelevant}.
- `partnership_fit[]` — список каналов из §3.
- `confidence` ∈ {low, medium, high} — отражает достаточность данных.
- `brand_summary`, `audience_guess`, `instagram_url`, `comment`,
  `recommendation` (что менеджеру питчить), `sources[]` (ссылки из grounding).

**Полосы вердикта:** 0-39 «не подходит» · 40-69 «под вопросом» · 70-100
«подходит» → маппинг в существующий `ManagementLead.niche_status`
(non_niche / maybe / niche), чтобы результат бесшовно лёг в очередь модерации.

## 5. Конвейер на один аккаунт (один grounded-вызов)

1. Контекст из лида: `shop_name`, `city`, `website_url`, Google-типы и адрес
   из `extra_data`, `google_maps_url`.
2. Best-effort фетч главной страницы сайта (timeout ~6с, текст ~6KB). Не
   блокирует — мёртвый сайт пропускаем.
3. Один вызов Gemini с `google_search` grounding. JSON-mime НЕ используется
   (grounding несовместим со structured output —
   https://discuss.ai.google.dev/t/why-is-using-a-response-schema-not-supported-when-using-grounded-search/92327),
   JSON извлекаем из текста.
4. `_parse_model_json` (срезает ```-фенсы, вырезает {..}), валидация,
   сохранение. Провал парсинга после ретраев → `status=error`, лид доступен
   для re-check.

## 6. Бэкенд

Архитектура — браузер-driven stepping (как парсер; на Passenger нет
серверного воркера). **Один лид на `step`** (короткий шаг, гранулярный
стоп, rpm-троттлинг через `next_step_not_before`). Всё проверенное сразу в
БД — закрытие вкладки не теряет прогресс.

- `management/services/lead_checker.py` — сборка контекста, фетч сайта,
  скоринг одного лида, маппинг полос, идемпотентность.
- `management/services/lead_checker_job.py` (или в том же модуле) — движок
  job: start/step/pause/resume/stop/status, singleton-lock.
- В `management/services/call_ai_analysis.py` добавить публичный хелпер
  `gemini_generate_grounded(system_instruction, user_text, *, models=None,
  max_output_tokens=...)` — строит payload c `tools:[{google_search:{}}]`
  (без `responseMimeType`), гоняет через существующий `_run_payload_with_models`.
  400 при несовместимости tools трактуется как skip-model (не fatal).
- Ключ Gemini: `LeadCheckerSettings.gemini_api_key` (вводит админ в UI) →
  фолбек ENV `GEMINI_API` → `settings.GEMINI_API_KEY`. Чек-цепочка
  grounding-capable моделей (по умолчанию `gemini-2.5-flash` →
  `gemini-3.5-flash`), настраиваемая.

## 7. Модели данных

### `LeadAICheck` (FK→ManagementLead, related_name `ai_checks`)
- `status` ∈ {pending, processing, done, error}
- `overall_score` (int 0-100, null)
- `criteria` (JSON: список 10× `{key, title, score, comment}`)
- `verdict_category` (char), `partnership_fit` (JSON list), `confidence` (char)
- `brand_summary`, `audience_guess`, `instagram_url`, `comment`,
  `recommendation` (text)
- `sources` (JSON list of `{title, url}`)
- `website_fetched` (bool), `model_used` (char), `tokens` (JSON usage),
  `error` (text)
- `checked_by` (FK User, null), `created_at`

Кэш-поля на `ManagementLead` для быстрых списков/сортировки:
`ai_score` (int, null, db_index), `ai_verdict` (char, db_index),
`ai_checked_at` (datetime, null, db_index).

### `LeadCheckJob` (облегчённый аналог `LeadParsingJob`)
- `status` ∈ {running, paused, stopped, completed, failed}
- `scope` ∈ {unchecked, all, by_city, by_band}, `city`, `band` (фильтр)
- `target_limit` (0 = без лимита)
- счётчики: `total_selected, processed, scored, errors, fit_count,
  maybe_count, unfit_count`
- `requests_per_minute`, `current_lead_id`, `next_step_not_before`
- тайминги: `started_at, finished_at, last_step_at, avg_seconds`,
  `last_error`, `stop_reason_code`, `created_by`

### `LeadCheckRuntimeLock`
Singleton-лок активной чек-сессии (как `LeadParsingRuntimeLock`).

## 8. Эндпоинты (плоские имена `management_checker_*`, доступ Top Manager+)

- `checker/` → страница (`management_checker`)
- `checker/api/start/` `step/` `pause/` `resume/` `stop/` `status/`
- `checker/api/results/` — список с фильтром band/city + пагинация
- `checker/api/leads/<int:lead_id>/recheck/` — перепроверить один лид
- `checker/api/settings/` — сохранить API-ключ/настройки

Вьюхи в новом `management/checker_views.py` по образцу `parsing_views.py`.

## 9. UI (стиль `management.css`, тёмная тема, акцент `--accent`)

- Вкладка «Чекер» в `header-tabs` под `{% if request.user.is_staff %}`.
- Hero: статус-чип, кнопки Старт/Пауза/Стоп, живые метрики (Проверено /
  Осталось / Прошло сек / Сред. время / Подходит / Под вопросом / Не подходит).
- Форма запуска: scope, размер выборки/лимит, поле API-ключа (опц.), оценка
  стоимости.
- Результаты: вкладки-фильтры **Все / Подходит ≥70 / Под вопросом /
  Не подходит / Ошибки**; таблица Магазин · Оценка (gauge-бейдж) · Категория ·
  Бренд · Каналы · Сайт/IG · Действие. Клик → модалка: 10 критериев,
  источники, рекомендация + «В базу» / «Не подходит» (переиспользуем
  `lead_moderation_action_api`).
- JS самозапускающийся `initCheckerPage` (apiRequest / pollStatus /
  scheduleStep / applyPayload — паттерн `parsing.html`).
- Шаблон `templates/management/checker.html` (`{% extends "management/base.html" %}`,
  блоки extra_css/content/extra_js). Стили — инлайн в extra_css + при нужде
  классы в конец `twocomms_django_theme/static/css/management.css`.

## 10. Риски и митигейшены

| Риск | Митигейшен |
|---|---|
| Стоимость/время на 4000 | scope-фильтры, лимит сессии, оценка стоимости в UI, кэш + идемпотентность (`ai_checked_at`) |
| Длинный step на Passenger | 1 лид/step, rpm-троттлинг |
| JSON без json-mime | строгий промпт + `_parse_model_json` + ретрай; провал → `status=error`, re-check |
| 400 на модели без tools | grounding-цепочка моделей, 400-tools → skip-model |
| Галлюцинации бренда | требуем `sources[]`; нет → `confidence=low`; промпт запрещает выдумывать |
| Instagram плохо индексируется | honest-by-design: `confidence` отражает нехватку данных |
| Квота 429 | фолбек моделей + троттлинг (уже в `_run_payload_with_models`) |

## 11. Тестирование

TDD по сервису (Gemini мокаем): скоринг, маппинг полос → niche_status,
`_parse_model_json` на грязных ответах, фолбек ключа, сборка контекста,
идемпотентность, движок job (курсор, счётчики, lock, стоп). После деплоя —
реальный прогон на 5-6 спарсенных лидах с сервера, замер времени/токенов.
При частых JSON-провалах — опционально двухступенчатый вызов (research →
score) как улучшение, не в MVP.

## 12. Осознанно НЕ делаем

- Не расширяем Google Places fieldmask (рейтинг/отзывы — удорожает парсинг;
  рейтинг найдёт grounding).
- Не трогаем сам парсер — только добавляемся рядом, переиспользуя паттерны.
