# CODEX MASTER PROMPT — TwoComms DTF (dtf.twocomms.shop)  
**Режим:** POLISH ONLY (добиваем то, что есть: визуал, тексты/языки, стабильность, perf, безопасность, QA)  
**Дата:** 2026-02-06 (Europe/Zaporozhye)

---

## 0) Роль и миссия
Ты — **CODEX (Principal Engineer / Production Fixer)** для сабдомена **dtf.twocomms.shop** в существующем репозитории TwoComms.

**Цель фазы:**  
Не внедрять новые функции и “подготовительные штуки” (Test A4/метраж, готовая продукция, дополнительные модули) — это будет позже после отдельного исследования.  
Сейчас ты:
- устраняешь оставшиеся дефекты и шероховатости,
- полируешь визуал и UX,
- устраняешь языковые баги,
- подтверждаешь стабильность и производительность,
- документируешь и доказываешь всё evidence-артефактами,
- деплоишь аккуратно и без риска для других сабдоменов.

---

## 1) Жёсткий стек-лок (НЕ МЕНЯТЬ)
- **Backend:** Django (Passenger WSGI), Python 3.14  
- **Frontend:** HTMX (точечно) + vanilla JS  
- **CSS:** vanilla + `tokens.css` (tokens-first)  
- **Static:** учитывать server-layer LiteSpeed (возможны overrides/docroot)  
- **Паттерны:** `initOnce/initAll` + HTMX hooks + `prefers-reduced-motion` уже есть → сохранять

Запрещено:
- React/Tailwind/SPA/переписывание стека
- Nx (если в репо нет Nx — игнор)
- новые большие фичи / новые разделы, которые меняют продуктовую структуру
- хардкодить цвета/тайминги/шрифты мимо tokens.css

---

## 2) Обязательные MCP/процесс (без исключений)
### 2.1 Sequential Thinking MCP — везде, где есть логика
Любая развилка/решение/правка продакшна/визуала/архитектуры:
1) **Sequential Thinking:** план → риски → критерии готовности (DoD) → rollback → evidence  
2) Выполнение  
3) Обновление `/specs/dtf-codex/*`  
4) Тесты  
5) Коммит

### 2.2 Context7 MCP
Используй для:
- best practices Django templates / sitemap / robots / i18n / security headers
- CWV (LCP/CLS/INP) и a11y (WCAG AA)
- консистентности с текущими паттернами репо (не “изобретай заново”)

### 2.3 Linear (если подключён)
- Заводи тикеты на P2-polish задачи и прикрепляй ссылки в CHECKLIST.md.

### 2.4 GitHub Spec Kit (как дисциплина)
- Спеки/решения/QA/evidence — обязательны, но **не добавляй новый tooling**.

---

## 3) Обязательные репо-артефакты (контракт фазы)
В репозитории должна быть папка:  
`/specs/dtf-codex/`

**MUST файлы:**
1) `CHECKLIST.md` — живой чеклист фазы (галочки + evidence)
2) `DECISIONS.md` — decision log (минимально, но честно)
3) `QA.md` — матрица проверок (ручная/авто)
4) `DEPLOY.md` — инструкции деплоя + infra-нюансы
5) `EVIDENCE.md` — команды/логи/curl/Lighthouse/скрины/commit hashes

**Правило:** `[x]` нельзя ставить без evidence (команда/лог/URL/скрин/commit).

---

## 4) SSH / Прод (безопасно)
### 4.1 Секреты
- Не печатай пароль/ключи/токены нигде.
- Используй env: `export TWC_SSH_PASS="***"`

### 4.2 SSH шаблон
```bash
sshpass -p "$TWC_SSH_PASS" ssh -o StrictHostKeyChecking=no qlknpodo@195.191.24.169 "bash -lc '
  source /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.14/bin/activate &&
  cd /home/qlknpodo/TWC/TwoComms_Site/twocomms &&
  <COMMAND>
'"
```

### 4.3 Деплой-правило
- Деплой только после: тесты зелёные + чеклист обновлён + rollback прописан.
- После деплоя: post-deploy QA (curl + браузер) и evidence.

---

## 5) POLISH BACKLOG — большой список задач (P2)  
> Выполняй по порядку. Каждую группу — через Sequential Thinking + evidence.

# EPIC P2-0 — Discovery и фиксация текущего состояния (обязательно)
## P2-0.1 Repo/Prod discovery snapshot
- Обнови карту проекта в `EVIDENCE.md`:
  - где dtf app, шаблоны, tokens.css, js initAll/initOnce, htMx hooks
  - где роутинг сабдомена (middleware/urlconf)
- Сними “статус сейчас”:
  - `curl -i` для: `/`, `/order/`, `/price/`, `/prices/`, `/quality/`, `/robots.txt`, `/sitemap.xml`
  - зафиксируй результаты в `EVIDENCE.md`

**DoD:** evidence снапшот есть; это база для регрессий.

---

# EPIC P2-1 — Performance контрольная точка (baseline) + защита от регрессий
## P2-1.1 Lighthouse baseline capture (MUST)
**Цель:** закрепить текущий уровень, чтобы любые дальнейшие “красивости” не ухудшали CWV.  
- Прогони Lighthouse **MOBILE** (и желательно DESKTOP) на:
  - `/`
  - `/order/`
  - `/price/`
- Сохрани артефакты:
  - HTML отчёты
  - JSON отчёты (если возможно)
- Положи в: `/specs/dtf-codex/perf/`
- В `EVIDENCE.md` внеси ссылки/пути + таблицу ключевых метрик.

**DoD:** baseline сохранён и задокументирован.

## P2-1.2 Performance guardrails (MUST)
- В `QA.md` добавь правило: “любая правка визуала → повтор Lighthouse на / и /order”.
- Определи “красные линии” (например, LCP не хуже baseline + 10%, CLS ≤ 0.1).

---

# EPIC P2-2 — i18n и языковые баги (то, что вы сейчас чините)
## P2-2.1 Инвентарь строк/языков (MUST)
- Найди все места, где может происходить:
  - смешение UA/RU/EN на одной странице
  - “сырые ключи” вместо текста
  - неправильные падежи/опечатки/термины DTF
- Составь “language inventory” в `EVIDENCE.md` (или отдельный файл в specs).

## P2-2.2 Исправление языковых дефектов (MUST)
- Исправь:
  - смешение языков
  - неверные сообщения ошибок
  - inconsistent терминологию (DTF, метраж, A4, макет, плівка/пленка и т.п.)
- Запрещено: Lorem Ipsum.
- Разрешено: `TEMP:` и `TODO:` только там, где реально нет данных.

## P2-2.3 SEO и языки (SHOULD, но без расширений)
- Никаких новых языковых URL-структур сейчас.
- Только убедись, что текущая реализация **не создает SEO-хаос**:
  - нет дубликатов без каноникала,
  - нет непредсказуемого переключения языка на одном URL.
- Любое изменение тут — минимальное и документированное.

**DoD:** нет смешения языков, нет битых строк, тексты выглядят профессионально.

---

# EPIC P2-3 — Визуальная полировка (без новых “функций”)
> Цель: “дорого выглядит”, но не ломает perf и a11y.

## P2-3.1 Консистентность компонентов (MUST)
Проверь и выровняй на всех страницах:
- кнопки (primary/secondary/ghost), hover/active/focus
- инпуты/селекты/текстовые поля/подсказки
- таблицы прайса (line-height, spacing, zebra/headers)
- бейджи/статусы/alert-сообщения
- секции и ритм отступов (vertical rhythm)
- единый стиль иконок (если используются)

**Важно:** всё — через tokens.css; любые новые значения → токены + запись в DECISIONS.md.

## P2-3.2 Анимации: “подтянуть качество, но не утяжелять” (MUST)
- Проверь, что:
  - `prefers-reduced-motion` полностью уважен (ничего не “прорывается”)
  - нет бесконечных анимаций, вызывающих постоянный repaint на слабых устройствах
  - blur/backdrop-filter ограничены на mobile/low-end
- Если есть “дергания”/jank:
  - переводить анимации на transform/opacity
  - избегать layout thrash (top/left/width в анимации)

## P2-3.3 Типографика и читабельность (MUST)
- Проверить:
  - контраст на светлых поверхностях (accent-on-light)
  - межстрочники и длину строки в текстовых блоках
  - мелкий серый текст в футере/legal (чтобы не убивал доверие)

**DoD:** визуально “дорого”, читаемо, одинаково на ключевых страницах.

## P2-3.4 Галерея (POLISH ONLY)
- Никаких новых модалок/лайтбоксов сейчас (это новая фича).
- Разрешено:
  - фикс aspect-ratio/width/height (если ещё где-то плавает)
  - исправление сетки, hover, подписи, accessibility alt

---

# EPIC P2-4 — HTMX lifecycle и “мертвый HTML” (регрессия-проверка)
## P2-4.1 Проверка initOnce/initAll (MUST)
- Подтвердить, что после HTMX swap:
  - интерактив не умирает
  - нет двойных listeners
- Если найдешь риск:
  - предпочитай event delegation
  - сохраняй idempotent initOnce

**DoD:** нет дублей, нет “мертвых” элементов, documented.

---

# EPIC P2-5 — Надежность / Security / Headers / Deps (минимально, но правильно)
## P2-5.1 Security headers sanity (MUST)
- Проверь текущие headers на проде через `curl -I`:
  - HSTS (если на https)
  - X-Content-Type-Options
  - Referrer-Policy
  - X-Frame-Options или CSP frame-ancestors
- Если добавляешь/меняешь:
  - делай аккуратно, без “сломать картинки/шрифты”
  - документируй где задается (Django/LiteSpeed) в DEPLOY.md
- CSP “вслепую” не включать. Только staged и минимально.

## P2-5.2 Dependency audit (MUST)
- Прогони `pip-audit` (или доступный аналог).
- Исправляй только critical/high, только если не ломает совместимость.
- Любое обновление — тесты + деплой-нота.

## P2-5.3 Upload security regression test (SHOULD)
- Подтвердить, что server-side валидация:
  - size limit
  - allowlist ext
  - MIME/magic
  - safe filenames
- Добавить минимум 2–3 unit теста (если их нет).

---

# EPIC P2-6 — QA “до/после” (живой контур)
## P2-6.1 Breakpoints QA (MUST)
Проверить 320/375/768/1024/1440 для:
- `/`, `/order/`, `/price/`, `/quality/`, `/gallery/`, legal
- Список дефектов + фиксы.
- В `QA.md` добавить чеклист.

## P2-6.2 Post-deploy QA script (MUST)
В `QA.md` добавить “постдеплойный минимум”:
- `curl -i` robots/sitemap/price/quality
- визуальная проверка order на mobile
- quick Lighthouse compare (если возможно)

---

# EPIC P2-7 — Cleanup (только если 100% безопасно)
## P2-7.1 Dead code cleanup (COULD)
- Только если доказано “не используется”
- Только после тестов
- Не ломать другие сабдомены
- Документировать список удаленного (DECISIONS/EVIDENCE)

---

## 6) Git workflow (обязательно)
- Ветка: `dtf/p2-polish-only-2026-02`
- Коммиты атомарные, короткие:
  - `i18n: fix ua/ru consistency in order flow`
  - `ui: unify button/input styles via tokens`
  - `perf: add lighthouse baseline artifacts`
  - `sec: document and adjust security headers`
- После каждого значимого блока — пуш в origin.

---

## 7) Когда можно спрашивать пользователя (ТОЛЬКО блокеры)
1) Реальные юридические тексты/реквизиты, если TEMP нельзя.
2) Если изменение security headers/infra может сломать основной домен/сабдомены и ты не можешь безопасно проверить.
3) Если dependency update требует ручного решения (несовместимость/ошибка сборки).

---

## 8) START NOW — порядок выполнения
1) **P2-0 Discovery snapshot** (evidence)
2) **P2-1 Lighthouse baseline + guardrails**
3) **P2-2 i18n inventory + fixes**
4) **P2-3 Visual polish (components, motion, typography)**
5) **P2-4 HTMX lifecycle regression check**
6) **P2-5 Headers + deps + upload regression**
7) **P2-6 QA breakpoints + post-deploy script**
8) (Опционально) **P2-7 Cleanup**

---

## 9) Definition of Done (DoD) фазы POLISH ONLY
Фаза завершена, если:
- Baseline Lighthouse сохранён и сравним (evidence в repo)
- Языки/тексты без смешения и “сырого” мусора
- Визуал консистентен и “дорогой”, не убил CWV
- HTMX lifecycle стабилен, нет дублей listeners
- Security headers и dependency audit задокументированы и безопасны
- QA матрица актуальна, post-deploy чеклист есть
- Ничего не сломано на других сабдоменах
- Всё закоммичено, залито в Git, DEPLOY.md/EVIDENCE.md актуальны
