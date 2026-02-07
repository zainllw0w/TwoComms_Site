# TwoComms DTF (dtf.twocomms.shop) — Полный список задач для CODEX + финальный вид сайта (Vision & Backlog)
**Дата:** 2026-02-06 (Europe/Zaporozhye)  
**Назначение:** этот документ = “единый источник правды” для CODEX: что должно быть на сайте, как это должно выглядеть, и что именно нужно сделать в коде/на сервере.  
**Стек-лок:** Django (Passenger WSGI, Python 3.13) + HTMX (точечно) + vanilla JS + vanilla CSS + `tokens.css`. Стек не меняем.

---

## 0) Правила выполнения (обязательны)
### 0.1 Режим “непрерывная работа”
- CODEX **работает без остановки**, задаёт вопросы **только при блокерах**.
- Любая развилка/логика/выбор → **MCP Sequential Thinking** (план → риски → DoD → выполнено → evidence).

### 0.2 MCP/инструменты
- **Sequential Thinking MCP** — перед каждым эпиком/пакетом изменений.
- **Context7 MCP** — для сверки с лучшими практиками (Django templates, HTMX lifecycle, CWV, WCAG) и для проверки консистентности с текущим репо.
- **Linear** — если доступ есть: создать тикеты P0/P1/P2, ссылки писать в CHECKLIST.md.
- **NX MCP** — использовать **только если** Nx уже реально есть в репозитории (обнаружить, не предполагать).
- **GitHub Spec Kit** — использовать как **процесс спецификаций** (CHECKLIST/DECISIONS/QA/DEPLOY/EVIDENCE), не как обязательную установку нового тулчейна.

### 0.3 Секреты и SSH
- **Запрещено** писать пароль/секреты в файлы репо, коммиты, отчёты, логи.
- Для sshpass использовать переменную окружения: `TWC_SSH_PASS`.
- Команда (шаблон, параметры — из вашей инфраструктуры):
  ```bash
  sshpass -p "$TWC_SSH_PASS" ssh -o StrictHostKeyChecking=no USER@HOST "bash -lc '
    source /home/USER/virtualenv/TWC/TwoComms_Site/twocomms/3.13/bin/activate &&
    cd /home/USER/TWC/TwoComms_Site/twocomms &&
    <COMMAND>
  '"
  ```

---

## 1) Обязательные репозиторные артефакты (создать/обновлять всегда)
В репозитории создать (если нет) папку:
`/specs/dtf-codex/`

Файлы (MUST):
1) `CHECKLIST.md` — живой чеклист (обновлять после каждого шага)
2) `DECISIONS.md` — decision log (что решили, почему, ссылка на evidence)
3) `QA.md` — чеклист ручных/авто проверок
4) `DEPLOY.md` — деплой + infra-шага (особенно server docroot override для robots/sitemap)
5) `EVIDENCE.md` — команды, логи, curl, Lighthouse, ссылки на страницы

**Политика evidence:** любой пункт `[x]` в CHECKLIST должен иметь ссылку/команду/лог, доказывающие выполнение.

---

## 2) Финальный вид сайта (Vision): как должен выглядеть и ощущаться
### 2.1 Brand / Visual DNA
- **Темный industrial “shell”** (фон “carbon/void”), **светлые/нейтральные рабочие поверхности** (для прайса, таблиц, форм), чтобы не убить читабельность и конверсию.
- Акцент: “Molten Orange” как **брендовый сигнал**, но на светлом — только через безопасный токен (см. A11y).

### 2.2 Дизайн-система (tokens-first)
- Все цвета/отступы/типографика/тени/радиусы/скорости анимаций — через `dtf/static/dtf/css/tokens.css`.
- Запрещено “впрыснуть” новые хардкоды. Любой новый оттенок = новый токен + запись в DECISIONS.md.

### 2.3 Анимации и “signature”
- Поддерживать текущую signature-анимацию (scan/industrial noise) — **но**:
  - не ухудшать LCP/CLS/INP,
  - уважать `prefers-reduced-motion`,
  - избегать тяжёлых blur/backdrop-filter на mobile/low-end.

### 2.4 Страницы и структура (MUST)
- `/` — Hero + value proposition + trust bar + CTA на /order/ + блоки “Цены”, “Процесс”, “Качество”, “Галерея”, “FAQ”, “Контакты”.
- `/order/` — основной сценарий заказа: данные + загрузка + требования + итоги + CTA.
- `/price/` — прозрачный прайс, скидки, сроки, опции, “что включено/не включено”, доставка/оплата.
- `/quality/` — объяснение качества, примеры, допуски, гарантия, что делать при браке.
- `/requirements/` — требования к макетам и файлам (PDF/PNG), цветность, вылеты, рекомендации.
- `/templates/` — шаблоны/гайд по подготовке.
- `/gallery/` — примеры работ.
- Legal (если в проекте принято): `/privacy/`, `/terms/`, `/returns/`, `/requisites/` (можно TEMP контент, но честно маркированный).

### 2.5 Языки (UA/RU)
- UA — default.
- RU — опционально (toggle), без ломки SEO (если делается — документировать подход: отдельные URL или один URL + переключатель).
- Запрещено использовать Lorem Ipsum. Только `TEMP:` и `TODO:`.

---

## 3) Полный список задач (Backlog) для CODEX
Ниже — большой, детализированный список. CODEX обязан:
- завести/обновить CHECKLIST.md
- исполнять по приоритетам P0 → P1 → P2
- по завершению каждого блока обновлять EVIDENCE.md и DECISIONS.md

---

# EPIC A — Верификация текущего состояния (сразу)
**A1 (P0) Реальная проверка на проде**  
- Проверить HTTP статусы и контент:
  - `/quality/`, `/price/`, `/prices/`, `/order/`, `/robots.txt`, `/sitemap.xml`
- Evidence:
  - `curl -i https://dtf.twocomms.shop/robots.txt`
  - `curl -i https://dtf.twocomms.shop/sitemap.xml`
  - `curl -i https://dtf.twocomms.shop/prices/` (если 301 — показать Location)
- DoD: в CHECKLIST стоят галочки только после evidence.

---

# EPIC B — P0: SEO/ошибки/битые роуты (чинить первым)
## B1 (P0) /quality 500 (регрессия-щит)
**Цель:** `/quality/` всегда 200, статические ресурсы работают.  
**Tasks:**
- Исправить шаблон (`{% load static %}`).
- Добавить smoke-test Django: GET `/quality/` = 200.
- DoD: тесты зелёные, на проде 200, evidence.

## B2 (P0) /prices → /price (навсегда)
**Цель:** нигде в UI/SEO не фигурирует битый `/prices/`.  
**Tasks:**
- Найти все ссылки/меню/кнопки, исправить на `/price/`.
- (Рекомендуется) сделать 301 redirect `/prices/` → `/price/`.
- Обновить canonical (если используется), OG, sitemap entries.
- DoD: `/price/` = 200; `/prices/` = 301 на `/price/` или 404 без внутренних ссылок; в шаблонах нет “/prices”.

## B3 (P0) robots.txt для DTF — правильный и реально отдаётся
**Цель:** роботы получают DTF robots, не основной домен.  
**Tasks:**
- App:
  - реализовать/проверить Django endpoint `robots_txt` (DTF host, Sitemap на dtf sitemap).
  - убедиться, что роут подключен именно в dtf urlconf (например, `twocomms/urls_dtf.py`).
- Infra:
  - устранить server docroot static override (robots.txt в public_html), иначе Django не будет вызван.
- Tests:
  - тест на содержимое robots (есть dtf sitemap, нет основного домена).
- DoD: `curl -i /robots.txt` = 200 и корректный контент; тест зелёный; infra-шага задокументирован в DEPLOY.md.

## B4 (P0) sitemap.xml для DTF — 200 + валидный XML + dtf URLs
**Цель:** sitemap работает и содержит только dtf-ссылки.  
**Tasks:**
- App:
  - обеспечить генерацию sitemap в dtf urlconf (Django `sitemap` view), loc → dtf host.
  - убедиться, что sitemap включает `/price/` и исключает нерелевантные main-site URLs.
- Infra:
  - устранить server docroot static override (sitemap.xml в public_html).
- Tests:
  - тест: `/sitemap.xml` = 200, содержит `<loc>https://dtf.twocomms.shop/` и `/price/`, и не содержит `https://twocomms.shop/`.
- DoD: `curl -i /sitemap.xml` = 200; content-type корректный; тест зелёный; запись в EVIDENCE/DEPLOY.

## B5 (P0/P1) Legal pages (если сейчас 404)
**Цель:** страницы существуют и связаны из футера.  
**Tasks:**
- Добавить роуты + шаблоны (UA+RU или UA+TEMP RU).
- В футере на всех страницах есть ссылки.
- DoD: 200 на всех legal URL; no Lorem Ipsum; TEMP маркировка.

---

# EPIC C — P1: Performance (CWV) — LCP/CLS (главный буст)
## C1 (P1) Оптимизация LCP изображений (hero/background)
**Цель:** LCP ≤ 2.5s на mobile (home + order), без потери визуала.  
**Tasks:**
- Выявить LCP элемент на home и /order (обычно hero image).
- Конвертировать тяжёлые ассеты в WebP/AVIF + fallback (PNG/JPG).
- Добавить responsive `srcset`/`sizes`.
- Добавить `preload` или `fetchpriority="high"` для LCP картинки.
- DoD:
  - Lighthouse mobile: Home LCP ≤ 2.5s; /order LCP ≤ 2.5s.
  - В EVIDENCE.md приложить отчёты (или скрин/JSON).

## C2 (P1) Устранение CLS (особенно на главной)
**Цель:** CLS ≤ 0.10 на mobile.  
**Tasks:**
- Прописать `width/height` или `aspect-ratio` для img и media контейнеров (home + gallery + price).
- Стабилизировать блоки, которые “прыгают” (карточки/гриды).
- DoD: Lighthouse mobile CLS ≤ 0.10; evidence.

## C3 (P1/P2) Дорогие эффекты: blur/backdrop-filter/overdraw
**Цель:** не убивать слабые устройства.  
**Tasks:**
- Найти `filter: blur(...)`, `backdrop-filter`, большие box-shadow.
- Ввести медиа-ограничения:
  - отключать/уменьшать на mobile/low-end,
  - уважать reduced motion.
- DoD: визуал сохраняется, перф не деградирует.

---

# EPIC D — P1: Accessibility (WCAG AA) и UX-качество
## D1 (P1) Контраст “accent on light”
**Цель:** не использовать яркий molten как текст на белом (провал AA).  
**Tasks:**
- Добавить токен типа `--c-molten-onlight` (темнее) или сменить паттерн (оранжевый как фон, текст тёмный).
- Пройтись по /price/ и /order/ (inputs/help/labels).
- DoD: ключевые тексты на светлом ≥ 4.5:1 (для normal text), documented in DECISIONS.

## D2 (P1) Focus/keyboard/labels
**Tasks:**
- Убедиться, что все интерактивные элементы имеют видимый focus.
- Labels/aria для inputs (особенно файл upload).
- Skip link (опционально) на /order.
- DoD: keyboard navigation без “ловушек”, QA.md checklist.

## D3 (P1) Reduced motion — регрессию не допускать
**Tasks:**
- Проверка `prefers-reduced-motion: reduce` для hero/кнопок/scanline.
- JS не должен принудительно запускать анимации при reduce.
- DoD: в QA.md есть пункт и пройден.

---

# EPIC E — UX/Conversion: “чётко, быстро, без риска”
## E1 (P1) /order sticky overlap
**Цель:** sticky summary не перекрывает форму на узких экранах.  
**Tasks:**
- Правка CSS breakpoints, z-index, sticky behavior.
- DoD: 320px viewport — поля и CTA доступны.

## E2 (P1) Order flow clarity (без A/B, но с правилами)
**Tasks:**
- Добавить ясные подсказки: “какой файл”, “как назвать”, “что будет дальше”.
- Error messages: конкретно, что исправить.
- Автосохранение draft (если уже есть — проверить), иначе минимум: не терять данные при HTMX swap.
- DoD: сценарий заказа проходит без “тупиков”.

## E3 (P1/P2) Gallery usability
**Tasks:**
- Добавить lightbox (легкий modal) для просмотра примеров (если бизнес-ценность подтверждена).
- Прописать размеры/аспект для превентивного CLS.
- DoD: работает без heavy JS, respects reduced motion.

## E4 (P2) SEO content hygiene
**Tasks:**
- Заголовки H1/H2 корректны на каждой странице.
- Meta description/OG на ключевых страницах.
- (Опционально) schema.org для Organization/LocalBusiness/Service (только если легко и безопасно).
- DoD: no duplicate titles, canonical если нужен.

---

# EPIC F — Security: Upload server-side (обязательно)
## F1 (P1) Server-side file validation
**Цель:** ограничения не только на фронте.  
**Tasks:**
- В `dtf/forms.py`:
  - size limit (конфиг, default 50MB)
  - allowlist ext: pdf/png
  - MIME/magic validation (если dependency можно поставить; иначе аккуратный fallback с честной записью рисков)
- Storage:
  - случайные имена файлов,
  - раздача только как download,
  - не исполнять.
- DoD: тесты на валидацию (минимум unit), documented.

## F2 (P2) AV scanning / quarantine (если объёмы оправдывают)
- Только как отдельное решение (инфра + ресурсы).

---

# EPIC G — Tests/QA/CI (минимальный фундамент)
## G1 (P0/P1) Авто-тесты регрессии
**MUST tests:**
- `/quality/` 200
- `/price/` 200
- `/prices/` 301 → `/price/` (если внедрено)
- `/robots.txt` корректный (dtf sitemap, нет основного домена)
- `/sitemap.xml` 200 + dtf URLs

## G2 (P2) Линт/формат/CI (только если вписывается в репо)
- Не навязывать новый стиль, если репо уже стандартизирован иначе.
- Любое внедрение tooling — через DECISIONS.md и минимально.

---

# EPIC H — Deploy & Evidence (боевой контур)
## H1 (P0) DEPLOY.md должен включать infra-изменения
- Где лежали статические `robots.txt`/`sitemap.xml`, как их бэкапнули и убрали.
- Как перезапускали Passenger.
- Как проверяли URL после деплоя.

## H2 (P0/P1) Post-deploy checklist (в QA.md)
- curl проверки (robots, sitemap, price, quality)
- визуальная проверка /order на mobile
- Lighthouse (если возможно)

---

## 4) Tie-breaker правила (чтобы не спорить бесконечно)
Если возникает конфликт “красиво vs конверсия”:
1) Если ухудшается читабельность прайса/форм — выбираем читабельность.
2) Если анимация ухудшает LCP/CLS/INP — анимация упрощается или уходит под reduced motion/mobile.
3) Если сомнение в безопасности upload — выбираем безопасность.
4) Если изменение может сломать основной домен/другие сабдомены — требуем evidence-план и rollback.

---

## 5) Что CODEX обязан отдать в конце (deliverables)
1) Обновлённый `/specs/dtf-codex/CHECKLIST.md` (всё отмечено + evidence)
2) `DECISIONS.md` (все токены/SEO/infra решения)
3) `QA.md` (ручные + авто проверки)
4) `DEPLOY.md` (включая docroot override fix)
5) `EVIDENCE.md` (curl, тесты, Lighthouse, ссылки)
6) Git: ветка + коммиты + PR (если принято)
7) Прод: подтверждение URL статусов и ключевых метрик (или честное объяснение ограничения)

---

## 6) START (порядок, по которому CODEX должен идти)
1) EPIC A (верификация на проде + evidence)
2) EPIC B (весь P0 блок)
3) EPIC C (perf)
4) EPIC D (a11y)
5) EPIC E (order UX + gallery)
6) EPIC F (upload security)
7) EPIC G (тесты/QA)
8) EPIC H (деплой + доказательства)
