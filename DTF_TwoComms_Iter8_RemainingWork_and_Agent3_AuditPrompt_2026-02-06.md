# TwoComms DTF (dtf.twocomms.shop) — Iter8: что ещё осталось + “10 отделов” (Gap Map) + PROMPT для 3‑го агента (полный аудит кода/сервера/визуала)
**Дата:** 2026-02-06 (Europe/Zaporozhye)  
**Контекст:** по отчёту верификации `dtf_full_backlog_verification_report.md` базовый P0/P1 backlog выполнен на ~95% (18/19), сайт в стадии полировки (языки/мелкие фиксы).

---

## 1) Что уже сделано (зафиксировано как “done” по текущим отчётам)
> Важно: ниже — не “обещания”, а то, что заявлено в отчёте верификации. 3‑й агент обязан перепроверить (см. PROMPT).

### P0 (блокеры)
- `/quality/` = 200 + smoke-test.
- `/prices/` → 301 на `/price/`, ссылки/сайтмап обновлены.
- DTF `robots.txt` — host-aware + dtf sitemap.
- DTF `sitemap.xml` — dtf-only URLs (включая legal).
- Legal pages: privacy/terms/returns/requisites.

### P1 (конверсия/скорость/доступность)
- Оптимизация LCP (AVIF/WebP, srcset, preload/fetchpriority).
- CLS фикс (width/height + aspect-ratio).
- Blur/backdrop-filter — fallbacks, reduced-motion.
- Контраст “accent on light” через токен `--c-molten-onlight`.
- /order sticky overlap исправлен.
- Server-side upload security: allowlist ext, MIME+magic, size limit, safe filenames.
- 19 автотестов, spec-файлы (CHECKLIST/DECISIONS/QA/DEPLOY/EVIDENCE) поддержаны.

### Осталось по прошлому backlog
- P2: Lighthouse baseline capture (как “контрольная точка”).
- P2: dead code cleanup (если доказано, что не используется).
- P2: AV scanning (опционально, отдельное решение).
- P2: lint/CI (не навязывали, но можно минимально).

---

## 2) “10 отделов” — что было задумано и что ещё не закрыто (Gap Map)
Ниже — сводка “по отделам”, чтобы не потерять первоначальную концепцию.

### 2.1 Product/Strategy (продуктовая стратегия)
**Сделано:** фундамент (P0/P1), wow-эстетика, стабильный order flow.  
**Осталось (обязательно, без новых фич):**
- Чёткая продуктовая матрица (DTF печать / DTF аутсорс / срочность / доп. услуги).
- Понятная “гарантия/ответственность” (что делаем при браке, сроки, повторный принт).
- Политика “TEMP vs real” данных (чтобы не подрывать доверие).

### 2.2 Growth/Marketing (конверсия, воронка)
**Сделано:** скорость/CLS, устранены блокеры, улучшены подсказки в /order.  
**Осталось (обязательно):**
- Event-модель аналитики (GA4/GTM/Meta) + события: CTA, upload start/success/fail, submit, contact click.
- Trust proof: реальные контакты/реквизиты/соцсети/портфолио/“мы бренд”.
- Микрокопирайтинг (отдельная итерация, но подготовить структуру).

### 2.3 UX/Psychology (когнитивная нагрузка, доверие)
**Сделано:** reduced motion, focus-visible, устранение перекрытий, ясные ошибки.  
**Осталось (обязательно):**
- “Снятие страха”: таймлайн “что дальше”, SLA по ответу, примеры до/после, FAQ про цвета/сводимость.
- “Снижение неопределённости”: стоимость/минимальный заказ/сроки на видном месте.

### 2.4 Design/Brand (визуал, вау, консистентность)
**Сделано:** tokens-first, индустриальная signature-анимация, light surfaces для данных.  
**Осталось (обязательно):**
- Консистентность компонентов (таблицы/кнопки/инпуты/бейджи) на всех страницах.
- Набор “компонентов доверия”: бейджи качества, фото реальной продукции/бренда, упаковка, контроль качества.

### 2.5 SEO/Content (индексация, структура)
**Сделано:** robots/sitemap, canonical для legal (по отчёту), исправлены битые URL.  
**Осталось (обязательно):**
- Проверка реальной индексации: корректность sitemap namespace, размер, частота, noindex где надо.
- Контент-план для посадочных: “DTF печать Киев/Украина”, “срочная DTF”, “DTF аутсорс для брендов” (без спама).
- Hreflang/языки — если реально есть UA/RU/EN, то сделать правильно (иначе выключить лишнее).

### 2.6 Engineering Frontend (надёжность UI)
**Сделано:** initOnce/initAll, HTMX lifecycle, reduced-motion, focus trap.  
**Осталось (обязательно):**
- Доказать, что нет “двойных listeners” и memory leaks после навигации/HTMX.
- Визуальные регрессии на брейкпоинтах 320/375/768/1024/1440.

### 2.7 Engineering Backend (Django correctness)
**Сделано:** endpoints, tests, upload security.  
**Осталось (обязательно):**
- Проверка security headers, CSRF, ограничения upload, storage perms.
- Проверка форм: серверные ошибки корректно отображаются, логируются, не теряются данные.

### 2.8 DevOps/Infra (стабильность, деплой)
**Сделано:** DEPLOY.md, фиксы docroot override (по отчёту).  
**Осталось (обязательно):**
- Проверить, что изменения docroot не ломают основной домен/другие сабдомены.
- Настроить минимальную наблюдаемость: error logs, rotation, alarms (хотя бы через email/telegram).
- Бэкапы критичных данных (uploads/orders).

### 2.9 Security/Compliance (риски)
**Сделано:** server-side upload validation, safe filenames.  
**Осталось (обязательно):**
- Мини-аудит зависимостей (pip-audit) + критические CVE закрыть.
- Rate-limit реально работает? (Redis/htaccess/headers) — подтвердить.
- Проверить, что ни в репо, ни на сервере не утекли секреты (пароли, токены).

### 2.10 Copywriting/Localization (языки и тексты)
**Сделано:** базовая локализация присутствует (по отчёту), но есть языковые баги (вы сейчас чините).  
**Осталось (обязательно):**
- Полный контент-инвентарь: где какой язык, нет ли смешения UA/RU/EN на одной странице.
- Глоссарий терминов DTF (UA/RU) + единый стиль.
- Тексты доверия: “мы бренд”, “как контролируем качество”, “сроки и ответственность”.

---

## 3) Новые функции “следующая волна” (готовим фундамент, но внедряем аккуратно)
> Эти задачи НЕ должны ломать текущий фундамент. Всё — feature-flagged и документировано.

### 3.1 “Тестовый метраж / тестовая линейка (A4)” — MUST в план, реализация по этапам
**Функциональная цель:** пользователь может заказать “тестовый набор” (A4 тест-печать / тест-метраж) с понятным UI.  
**Рекомендованный путь:**
- V1: как отдельный преднастроенный “продукт” в /order (выбор: Test A4 / Test 1m / Test 3m) → добавляет фиксированные параметры + подсказки.
- V2: отдельная landing `/test-print/` с CTA в /order.
- V3: расчёт стоимости/сроков.

### 3.2 “Готовая продукция” (готовые принты/пачки/мерч) — P2/P3
**Риск:** уводит в e-commerce. Делать только как “каталог + заявка” (V1), без оплаты.  
- V1: `/products/` (каталог карточек) + кнопка “Запросить наличие/сделать заказ” (в /order prefilled).
- V2: интеграция со складом/CRM.

### 3.3 Trust proof через основной бренд (TwoComms main)
- Вставить блок “Мы бренд, знаем качество”: фото продукции, упаковки, QC, ссылки на main site.
- Важно: это должно быть “честно и подтверждаемо”, без фейковых цифр.

---

## 4) Нужен ли ещё “огромный ряд тестов” от 3‑го агента?
Да — но не абстрактно. Нужен **один финальный Master Verification Audit**, который:
- сверяет “заявлено в отчётах” vs “реально в коде/на сервере/на сайте”,
- ищет оставшиеся дыры (i18n, security, headers, broken links, perf regressions),
- выдаёт новый “micro-backlog” на 2–4 недели допила.

---

# 5) PROMPT для 3‑го агента (имеет доступ к сайту, серверу по SSH и репозиторию)
Скопируй целиком и передай агенту.  
⚠️ **Не вставляй пароль в отчёт и не коммить его.** Передавать пароль только через секреты окружения.

```text
ROLE
You are Agent-3: Principal Verification Auditor (Full-Stack + DevOps + UX/Visual QA) for dtf.twocomms.shop.
You have access to:
- live website (browser),
- repository (read/write),
- production server via SSH (commands allowed).
Your job: verify what is implemented vs what was planned, find gaps and risks, and produce a large, evidence-based audit + improvement ideas.

HARD RULES
1) NO SECRETS in output: do NOT print passwords, tokens, keys, IP-only sensitive paths if they expose private data.
2) Separate FACT vs HYPOTHESIS. For every strong claim, provide evidence:
   - command output snippet, file path + line range, URL + status code, screenshot reference.
3) Be strict and practical: propose fixes in the current stack (Django + HTMX + vanilla + tokens.css). No “rewrite to React”.
4) Minimize scope creep: prioritize P0/P1; put everything else into P2/P3.

INPUT DOCS (READ FIRST)
- dtf_full_backlog_verification_report.md (claims 18/19 done)
- DTF_TwoComms_DTF_Full_Backlog_and_Final_Vision_for_CODEX_2026-02-06.md (vision + backlog)
- CODEX_PROMPT_TwoComms_DTF_vFinal_Master_2026-02-06.md (execution standards)

TASKS

A) PRODUCTION VERIFICATION (curl + browser)
1) Confirm status and content:
   - /, /order/, /price/, /prices/, /quality/, /robots.txt, /sitemap.xml
2) Provide evidence:
   - curl -i (status, headers)
   - confirm /prices redirect behavior (301 location)
   - validate sitemap XML loads in browser and contains only dtf URLs

B) SERVER-LAYER CHECK (LiteSpeed/docroot/caching)
1) Locate and document any static overrides in docroot:
   - robots.txt, sitemap.xml
2) Confirm they are removed/backed up and not overriding dtf.
3) Verify caching rules are not serving main-site files to dtf.
4) Provide a safe rollback plan for these infra changes.

C) REPO & CODE VERIFICATION (what changed, where)
1) Identify the exact files modified for:
   - robots/sitemap endpoints
   - /quality fix
   - /prices redirect + nav fixes
   - image optimization (AVIF/WebP/srcset/preload)
   - a11y tokens (--c-molten-onlight) + focus-visible + skip-link
   - sticky overlap fix
   - upload security (forms validation + storage)
2) Provide a table: Feature → files → short description → risk.

D) TESTS / BUILD / QUALITY GATES
1) Run and record:
   - python manage.py test dtf
   - python manage.py check
   - any CSS build command used (npm run build:css if exists)
2) Confirm tests cover P0/P1 (robots, sitemap, price redirect, quality, uploads).
3) Identify missing tests (if any) and propose additions.

E) PERF / CWV CONFIRMATION
1) Run Lighthouse MOBILE (or equivalent) on:
   - home (/)
   - /order/
   - /price/
2) Record: LCP, CLS, INP proxy, total bytes, image bytes.
3) Confirm LCP hero uses preload/fetchpriority and srcset sizes.
4) Provide top 10 heaviest assets and where they are referenced.
5) Check reduced-motion does not disable required UX.

F) VISUAL & INTERACTION QA (breakpoints + browsers)
1) Breakpoints: 320, 375, 768, 1024, 1440
2) Check:
   - nav/drawer behavior
   - order sticky summary does not overlap
   - focus states (keyboard)
   - reduced motion
   - modal/lightbox behavior (gallery)
3) Cross-browser: Chrome, Firefox, Safari iOS (emulated if no device).
4) List any UI regressions with screenshots + CSS/JS file references.

G) I18N / LOCALIZATION AUDIT (critical, since polishing now)
1) Inventory all languages used (UA/RU/EN):
   - any mixed-language blocks on same page?
   - missing translations / fallback issues?
2) Verify SEO language handling:
   - if multiple languages exist, check hreflang or decide to disable extra languages.
3) Provide a glossary suggestion for DTF terms.

H) SECURITY AUDIT (practical)
1) Upload security: confirm server-side validation works:
   - magic bytes, MIME, ext allowlist, size limit
   - safe storage paths/permissions
2) Dependency audit:
   - pip-audit (or similar) and list critical vulnerabilities
3) Headers:
   - CSP (if any), HSTS, X-Content-Type-Options, Referrer-Policy, COOP/COEP (if relevant)
4) Check for secrets leakage in repo and on server:
   - grep for passwords/tokens (DO NOT print them; only report that leaks exist and where).
5) Rate limiting: confirm middleware is active and Redis (if required) works.

I) “NEXT WAVE” PREP CHECK (future features)
Assess readiness for:
1) Test print / A4 metric feature:
   - best integration point (/order prefilled product vs separate page)
   - required data model changes (if any)
2) Ready-made products catalog:
   - minimal V1 (catalog + lead) without ecommerce complexity
3) Trust proof integration with main brand:
   - where to place, what assets needed, how to avoid “fake proof”.

DELIVERABLE
One big Markdown report: dtf_master_verification_audit_v1.md with sections:
0) Executive summary (10 bullets)
1) Implemented vs Planned (table, include “10 departments” mapping)
2) P0/P1/P2 findings (each with evidence + fix plan)
3) Performance results (numbers + assets)
4) i18n findings (with examples)
5) Security findings (practical + fix priority)
6) Visual regression log (screenshots references)
7) Next-wave recommendations (test print, products, trust)
8) Micro-backlog (2–4 weeks) with effort estimates (S/M/L) and risk.

DO NOT
- propose a full rewrite (React/Tailwind/Nx) unless repo already uses it and it's required.
- include secrets in output.
```

---

## 6) Что делать после отчёта 3‑го агента
1) Превратить micro-backlog в Linear (если используете).  
2) Отдельно: итерация по текстам (copywriting + доверие) — как вы и планировали.  
3) Потом: аккуратное внедрение “Test A4 / Test meter” как V1 (feature-flag).

---

## 7) Мини-проверка “прямо сейчас” (если хотите быстро)
Если вы хотите “быстрый sanity check”, попросите 3‑го агента сначала выполнить только разделы A+B+D (prod + server-layer + tests) и отдать короткий отчёт за 30–60 минут. Потом — полный аудит.
