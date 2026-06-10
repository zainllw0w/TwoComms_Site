# B2B Commercial Offer Revamp Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Переработать B2B-коммерческие предложения в субдомене management: тёмное адаптивное письмо с graceful-degradation картинок, упрощённый красивый интерфейс менеджера с живым превью, и полноценный трекинг + привязка КП к клиентам.

**Architecture:** Всё в Django-приложении `management`. Email-билдер (`email_templates/twocomms_cp.py`) отдаёт полный HTML-документ из нового тёмного шаблона. UI-страница (`commercial_offer_email.html`) переходит на секции-аккордеон + device-превью. Трекинг и привязка строятся поверх существующих моделей (`CommercialOfferEmailLog`, `ClientCPLink`, `ClientInteractionAttempt`, `ClientFollowUp`) + новые поля лога.

**Tech Stack:** Django 5, MySQL (prod) / SQLite (local), Django templates, vanilla JS, django-compressor, `python manage.py test`.

**Test command (local):** `SECRET_KEY=test_local_secret python manage.py test management.tests.<module> --settings=twocomms.settings` из каталога `twocomms/`. Известно: часть тестов даёт 301 из-за i18n+SECURE_SSL_REDIRECT — это не баг наших правок.

**Palette (inline hex for email + CSS for UI):** bg `#0b0e14`, panel `#131824`/`#171c28`, border `#232a38`, text `#e8edf7`/`#9aa4b8`/`#6c7382`, accent `#ff7e29`/`#f3a43d`, на оранжевой кнопке текст `#0b0e14`.

---

## ФАЗА 1 — Письмо

### Task 1.1: Синхронный прайс опт-таблицы в билдере

**Files:**
- Modify: `twocomms/management/email_templates/twocomms_cp.py`
- Test: `twocomms/management/tests/test_cp_email_builder.py` (create)

- [ ] **Step 1:** Добавить в билдер функцию `get_twocomms_cp_opt_grid()`, возвращающую список тиражей с ценами tee/hoodie из `OPT_TIER_WHOLESALE_TEE/HOODIE` (единый источник с `invoice_service`). Формат: `[{"range": "8–15 шт", "tee": 540, "hoodie": 1300}, ...]`.
- [ ] **Step 2:** Тест `test_opt_grid_is_monotonic`: цена tee и hoodie не возрастает по тиражам (инвариант 2).
- [ ] **Step 3:** Тест `test_opt_grid_matches_invoice_service`: значения совпадают с `invoice_service.get_management_wholesale_price_context()`.
- [ ] **Step 4:** Прогнать тесты, убедиться, что зелёные.
- [ ] **Step 5:** Commit `feat(cp): opt price grid helper in email builder`.

### Task 1.2: Новый тёмный шаблон письма (полный HTML-документ)

**Files:**
- Create: `twocomms/management/templates/management/emails/twocomms_cp_dark.html`
- Modify: `twocomms/management/email_templates/twocomms_cp.py` (рендер нового шаблона, полный документ, контекст `opt_grid`, `trust_points`, `why_us`)
- Test: `twocomms/management/tests/test_cp_email_builder.py`

- [ ] **Step 1:** Создать шаблон: полный `<!doctype html>` с `<head>` (meta viewport, `<style>` с медиазапросами `@media (max-width:480px)` для stack-колонок, `.cp-stack{width:100%!important;display:block!important}`), тёмная палитра инлайн, ghost-таблицы Outlook (`<!--[if mso]>`).
- [ ] **Step 2:** Блоки шаблона: header, hero, opt-grid таблица, юнит-экономика, карточки товаров (с тёмным плейсхолдером `bgcolor` и `alt`), 2 CTA (асортимент + зв'язатися), trust-strip, «Чому ми», контакти, футер. Картинки с `alt` и фоновым `#171c28`.
- [ ] **Step 3:** В `build_twocomms_cp_email` рендерить `twocomms_cp_dark.html`, добавить в контекст `opt_grid`, `trust_points`, `why_us`, `cta_secondary_url` (каталог/опт). Поле `html` = полный документ.
- [ ] **Step 4:** Тест `test_builder_returns_full_document`: `html` начинается с `<!doctype` и содержит opt-grid значения и оба CTA.
- [ ] **Step 5:** Тест `test_email_readable_without_images` (инвариант 1): убрать из html все `<img...>` regex-ом — ключевые строки (ціни, «Зв'язатися», контакти менеджера) всё ещё присутствуют.
- [ ] **Step 6:** Тест `test_builder_total_on_empty_payload` (инвариант 6): `build_twocomms_cp_email({})` не кидает, `html` и `text` непустые.
- [ ] **Step 7:** Прогнать тесты.
- [ ] **Step 8:** Commit `feat(cp): dark bulletproof email template`.

### Task 1.3: Превью = отправка (один путь)

**Files:**
- Modify: `twocomms/management/views.py` (preview API и send используют `email_build["html"]`)
- Test: `twocomms/management/tests/test_cp_email_builder.py`

- [ ] **Step 1:** Убедиться, что и send (`commercial_offer_email`, `commercial_offer_email_send_api`) и preview (`commercial_offer_email_preview_api`) берут один и тот же `email_build["html"]` для VISUAL.
- [ ] **Step 2:** Тест `test_preview_equals_send_html` (инвариант 5): для одинакового payload preview-HTML == send-HTML (один билдер).
- [ ] **Step 3:** Прогнать тесты.
- [ ] **Step 4:** Commit `refactor(cp): single source for preview and send html`.

---

## ФАЗА 2 — Интерфейс менеджера

### Task 2.1: Упрощение формы (человеческие подписи, CTA 2–3 варианта)

**Files:**
- Modify: `twocomms/management/forms.py`
- Test: `twocomms/management/tests/test_cp_form.py` (create)

- [ ] **Step 1:** Переписать `label`-ы полей на человеческие укр. подписи (без `OPT_TIER` и кодов). Сократить `CTA_TYPE_CHOICES` до: «Авто», «Telegram менеджера», «WhatsApp менеджера», «На email». Удалить из UI `TELEGRAM_GENERAL`/`REPLY_HINT_ONLY`/`CUSTOM_URL` из выбора (оставить нормализацию в билдере для совместимости со старыми логами).
- [ ] **Step 2:** Тест `test_form_cta_choices_simplified`: в `CTA_TYPE_CHOICES` ≤ 4 пунктов.
- [ ] **Step 3:** Тест `test_form_valid_minimal`: форма валидна с одним `recipient_email`.
- [ ] **Step 4:** Прогнать тесты.
- [ ] **Step 5:** Commit `feat(cp): simplify manager form labels and CTA choices`.

### Task 2.2: Переверстать страницу — секции-аккордеон + device-превью

**Files:**
- Modify: `twocomms/management/templates/management/commercial_offer_email.html`
- Modify: `twocomms/twocomms_django_theme/static/css/management.css` (новые классы `.cp-section`, `.cp-device`, `.cp-picker`, KPI и т.д.)

- [ ] **Step 1:** Левая колонка: 4 секции `<details class="cp-section">` (Кому открыта, остальные закрыты): Кому / Що показуємо / Ціни / Менеджер і зв'язок. Человеческие подписи, подсказки.
- [ ] **Step 2:** Правая колонка: device-превью — обёртка с переключателем Десктоп(600)/Мобайл(360) и тоглом «без картинок»; `<iframe srcdoc>` грузит полный HTML.
- [ ] **Step 3:** Кнопки внизу: «Надіслати КП» (primary), «Надіслати тест собі», «Мої контакти».
- [ ] **Step 4:** CSS под тёмную палитру менеджмента; адаптив (колонки складываются на узких).
- [ ] **Step 5:** Ручная проверка рендера через локальный сервер/`render_to_string` smoke (Task 2.6).
- [ ] **Step 6:** Commit `feat(cp): accordion sections + device preview UI`.

### Task 2.3: Визуальный пикер товаров

**Files:**
- Modify: `twocomms/management/views.py` (API списка товаров для пикера — переиспользовать `_get_gallery_default_urls`/добавить `commercial_offer_email_products_api`)
- Modify: `twocomms/management/urls.py`
- Modify: `commercial_offer_email.html` (JS пикера)
- Test: `twocomms/management/tests/test_cp_products_api.py` (create)

- [ ] **Step 1:** View `commercial_offer_email_products_api` (GET): вернуть опубликованные товары `[{slug, title, img_url, category}]` (tee/hoodie/longsleeve), макс ~24.
- [ ] **Step 2:** URL `commercial-offer/email/products/`.
- [ ] **Step 3:** JS: сетка карточек, выбор ≤3, синхронизация в скрытое поле gallery (существующий формат slug-ов), кнопка «Підібрати автоматично».
- [ ] **Step 4:** Тест `test_products_api_returns_published`: только PUBLISHED, поля присутствуют, 200 для менеджера, 403 для анонима.
- [ ] **Step 5:** Прогнать тесты.
- [ ] **Step 6:** Commit `feat(cp): visual product picker`.

### Task 2.4: «Надіслати тест собі»

**Files:**
- Modify: `twocomms/management/views.py` (повторно использовать send-логику, recipient = email менеджера/профиля)
- Modify: `twocomms/management/urls.py`
- Modify: `commercial_offer_email.html` (JS кнопки)
- Test: `twocomms/management/tests/test_cp_send_test.py` (create)

- [ ] **Step 1:** View `commercial_offer_email_send_test_api` (POST): строит письмо текущего payload и шлёт на `request.user.email`; НЕ пишет в `CommercialOfferEmailLog` (это тест) либо пишет со статусом-меткой test (решение: не писать в лог). Использует `EmailMultiAlternatives`.
- [ ] **Step 2:** URL `commercial-offer/email/send-test/`.
- [ ] **Step 3:** JS: кнопка шлёт текущую форму, показывает тост.
- [ ] **Step 4:** Тест `test_send_test_uses_manager_email` (locmem backend): письмо ушло на email менеджера, лог не вырос.
- [ ] **Step 5:** Прогнать тесты.
- [ ] **Step 6:** Commit `feat(cp): send test email to manager`.

### Task 2.5: Автосейв черновика + «Мої контакти»

**Files:**
- Modify: `commercial_offer_email.html` (JS)

- [ ] **Step 1:** JS: автосейв значений формы в `localStorage` (debounce), восстановление при загрузке (кроме `recipient_email`).
- [ ] **Step 2:** JS: «Мої контакти» — подставить контакты менеджера из data-атрибутов (профиль).
- [ ] **Step 3:** Commit `feat(cp): draft autosave + my-contacts shortcut`.

### Task 2.6: Smoke-тест рендера страницы и сайдбар

**Files:**
- Modify: `twocomms/twocomms_django_theme/static/css/styles.css` (если правим сайдбар — синхронно `styles.purged.css`)
- Test: `twocomms/management/tests/test_cp_page_render.py` (create)

- [ ] **Step 1:** Тест `test_cp_page_renders_200`: GET страницы менеджером (HTTP_HOST management) рендерит без ошибок, содержит секции и превью-iframe.
- [ ] **Step 2:** Причесать сайдбар-меню (отступы/иконки/active) в management.css.
- [ ] **Step 3:** Прогнать тест.
- [ ] **Step 4:** Commit `feat(cp): page render smoke test + sidebar polish`.

---

## ФАЗА 3 — Трекинг и привязка

### Task 3.1: Миграция полей лога

**Files:**
- Modify: `twocomms/management/models.py` (`CommercialOfferEmailLog`)
- Create: миграция `management/migrations/00XX_cp_tracking_fields.py`
- Test: `twocomms/management/tests/test_cp_tracking_model.py` (create)

- [ ] **Step 1:** Добавить поля: `track_token` (UUIDField, default uuid4, unique, db_index), `opened_at` (null), `first_click_at` (null), `click_count` (PositiveInteger default 0), `response_outcome` (CharField choices, blank), `response_note` (TextField blank). Добавить `ResponseOutcome(TextChoices)`.
- [ ] **Step 2:** `makemigrations management`.
- [ ] **Step 3:** Тест `test_log_has_track_token`: новый лог получает уникальный `track_token`.
- [ ] **Step 4:** `migrate` (SQLite local) + прогнать тест.
- [ ] **Step 5:** Commit `feat(cp): tracking + response fields on email log`.

### Task 3.2: Pixel и click-redirect эндпоинты

**Files:**
- Modify: `twocomms/management/views.py`
- Modify: `twocomms/management/urls.py`
- Test: `twocomms/management/tests/test_cp_tracking_endpoints.py` (create)

- [ ] **Step 1:** View `cp_track_open` (GET `cp/o/<uuid:track_token>.png`): ставит `opened_at` если пусто, возвращает 1×1 прозрачный PNG (`HttpResponse(content_type="image/png")`), без auth, try/except → всегда 200.
- [ ] **Step 2:** View `cp_track_click` (GET `cp/c/<uuid:track_token>/`): принимает `?u=<signed>`, инкремент `click_count`, ставит `first_click_at`, 302 на расшифрованный `signing.loads` URL; невалидный токен/подпись → редирект на сайт (без 500).
- [ ] **Step 3:** Встроить pixel и обёртку click-redirect в билдер письма (CTA-ссылки заворачиваются через signed redirect; pixel в конце письма). Хелпер `_wrap_tracking(url, token)`.
- [ ] **Step 4:** Тест `test_open_pixel_sets_opened_at` + `test_open_pixel_invalid_token_no_500` (инвариант 4).
- [ ] **Step 5:** Тест `test_click_redirect_only_signed`: неподписанный/чужой URL не редиректит наружу.
- [ ] **Step 6:** Прогнать тесты.
- [ ] **Step 7:** Commit `feat(cp): open pixel + signed click redirect tracking`.

### Task 3.3: Привязка КП к клиенту (модалка)

**Files:**
- Modify: `twocomms/management/views.py` (search API + link API)
- Modify: `twocomms/management/urls.py`
- Modify: `commercial_offer_email.html` (модалка + JS)
- Test: `twocomms/management/tests/test_cp_link_client.py` (create)

- [ ] **Step 1:** View `commercial_offer_link_client_api` (POST): принимает `log_id` + (`client_id` или данные нового клиента). Создаёт/находит `Client`, ставит `call_result=SENT_EMAIL`, `get_or_create` `ClientCPLink(client, cp_log)`, создаёт `ClientInteractionAttempt(cp_log=..., result=SENT_EMAIL)`. Идемпотентно.
- [ ] **Step 2:** View `commercial_offer_client_search_api` (GET `q`): поиск Client по phone_last7/shop_name.
- [ ] **Step 3:** URLs.
- [ ] **Step 4:** JS: кнопка «Прив'язати до клієнта» в строке лога → модалка (поиск/создание, префил названия из лога).
- [ ] **Step 5:** Тест `test_link_idempotent` (инвариант 3): двойная привязка не плодит `ClientCPLink`, не 500.
- [ ] **Step 6:** Тест `test_link_sets_sent_email_and_attempt`.
- [ ] **Step 7:** Прогнать тесты.
- [ ] **Step 8:** Commit `feat(cp): link commercial offer to client`.

### Task 3.4: Поповер «Опрацювати КП» (реакция + передзвон)

**Files:**
- Modify: `twocomms/management/views.py` (API установки `response_outcome` + опц. `ClientFollowUp`)
- Modify: `twocomms/management/urls.py`
- Modify: `commercial_offer_email.html` (поповер + JS)
- Test: `twocomms/management/tests/test_cp_process.py` (create)

- [ ] **Step 1:** View `commercial_offer_process_api` (POST): ставит `response_outcome`/`response_note` на лог; если передан `next_call_at` и лог привязан к клиенту — создаёт `ClientFollowUp(kind=CALLBACK, due_at=...)`.
- [ ] **Step 2:** URL.
- [ ] **Step 3:** JS: поповер в строке лога: select реакции + опц. дата → сохранить.
- [ ] **Step 4:** Тест `test_process_sets_outcome` + `test_process_creates_followup_when_linked`.
- [ ] **Step 5:** Прогнать тесты.
- [ ] **Step 6:** Commit `feat(cp): process outcome + schedule callback`.

### Task 3.5: KPI-полоса + фильтры лога

**Files:**
- Modify: `twocomms/management/views.py` (агрегаты + фильтры в `commercial_offer_email`)
- Modify: `commercial_offer_email.html` (KPI + фильтры + бейджи в строках)
- Modify: `twocomms/twocomms_django_theme/static/css/management.css`
- Test: `twocomms/management/tests/test_cp_kpi.py` (create)

- [ ] **Step 1:** В view посчитать KPI за период: sent, opened, linked, ordered, missed (missed = `ClientFollowUp` MISSED, связанные с cp). Поддержать GET-фильтры `status`/`outcome`/`linked`/`period`.
- [ ] **Step 2:** Шаблон: KPI-полоса (5 чисел), панель фильтров, в строках лога бейджи статуса/реакции/привязки + кнопки «Прив'язати»/«Опрацювати».
- [ ] **Step 3:** Тест `test_kpi_counts`: создать логи/привязки/followup и проверить числа.
- [ ] **Step 4:** Прогнать тест.
- [ ] **Step 5:** Commit `feat(cp): KPI strip + log filters`.

### Task 3.6: «Пропущені КП» в нагадуваннях + тост привязки

**Files:**
- Modify: `commercial_offer_email.html` (тост после отправки «Прив'язати?»)
- Modify: соответствующий сервис нагадувань при необходимости (`services/followups.py`) — только если требуется пометка источника КП.
- Test: существующие + `test_cp_kpi.py`

- [ ] **Step 1:** После успешной отправки (send API) — в ответе флаг `offer_log_id`; JS показывает тост с кнопкой «Прив'язати до клієнта».
- [ ] **Step 2:** Убедиться, что followup по КП попадает в существующие reminders (проверить `build_reminder_digest`); при необходимости пометить `meta={"source":"cp"}`.
- [ ] **Step 3:** Прогнать тесты фазы 3.
- [ ] **Step 4:** Commit `feat(cp): post-send link nudge + missed-cp reminders`.

---

## Финал

- [ ] Прогнать весь набор тестов `management.tests` (учесть известные 301).
- [ ] Локальный `collectstatic` dry-run не требуется; на деплое — `collectstatic` + `compress` (трогаем CSS и шаблоны).
- [ ] `git push` в ветку, затем деплой по чек-листу workflow.md: pull → migrate (есть миграция) → collectstatic (правили static/css) → compress --force (CSS в `{% compress %}`) → touch restart.txt → sanity-curl.

## Self-Review

- Спек-покрытие: блок1→Фаза1, блок2→Фаза2, блок3→Фаза3; инварианты 1,2 (1.1–1.2), 5 (1.3), 6 (1.2), 3 (3.3), 4 (3.2). ОК.
- Плейсхолдеров нет.
- Имена согласованы: `track_token`, `response_outcome`, `ClientCPLink`, `commercial_offer_*_api`.
