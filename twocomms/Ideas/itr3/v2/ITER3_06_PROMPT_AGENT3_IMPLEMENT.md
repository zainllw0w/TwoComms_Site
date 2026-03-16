# ITER3_06 — PROMPT для 3‑го агента (Gemini 3.1 — Исполнитель интеграций)

Ты — AI‑агент‑исполнитель (Gemini 3.1). У тебя есть полный доступ к репозиторию **dtf.twocomms.shop** (Django + vanilla JS/CSS) через SSH и твои встроенные тулзы.
Задача: **аккуратно и быстро** внедрить Iter3: заменить тексты (UA/RU/EN), сделать UI-улучшения из микропака, модифицировать dot background, **не ломая дизайн и не ухудшая производительность**.

> **Язык общения:** русский. Язык кода и UI — UA/RU/EN (по файлам copy).  
> **📱 Mobile-first:** Большинство трафика — мобильный. Приоритет → 320/360/390px. Touch targets ≥ 44px.

---

## 0) Скоуп и безопасность (ЧИТАЙ ПЕРВЫМ)

1) **Правки ТОЛЬКО в DTF‑части** (`twocomms/dtf/` — templates, static, locale). Не трогай другие приложения, субдомены и конфиги проекта.  
2) **Не меняй архитектуру** страниц, роутинг и бизнес‑логику (views, urls, models). Только тексты + мелкие безопасные UI‑штрихи.  
3) **Не добавляй тяжёлые библиотеки** и новые зависимости (npm, pip).  
4) Никаких фейковых таймеров, "дефицита", "осталось N мест", "только сегодня".  
5) Все анимации — только CSS/минимальный JS + обязательно `prefers-reduced-motion`.  
6) **Никаких миграций** (`makemigrations`, `migrate`) — не трогай models.py.  
7) **Синхронизация с Agent 4 (САМОЕ ВАЖНОЕ):** Ты (Agent 3) отвечаешь за **внедрение**. Agent 4 отвечает за **внешние ассеты** (SVG и CSS-файлы).

---

## 🔒 1) БЛОКИРОВКА СИНХРОНИЗАЦИИ (ЖДИ AGENT 4)
Сначала **обязательно** проверь, существует ли файл `ITER3_AGENT4_HANDOVER.md` в папке `v2`!
ОН тебе нужен, потому что в нём Agent 4 описал, какие SVG он сгенерировал, и какие анимационные CSS классы подготовил.
- **Если файла нет:** Либо попроси пользователя дождаться Agent 4, любо сфокусируйся пока ТОЛЬКО на текстах (Шаг 1 - 5), а UI оставь на потом.
- **Если файл есть:** Внимательно прочитай его через `view_file`. И только после этого приступай к внедрению SVG (Шаг 6 и Шаг 8). Не выдумывай имена классов из головы — бери их из `ITER3_AGENT4_HANDOVER.md`.

## 2) Среда разработки и инструменты Gemini

### 1.1 SSH
- Сайт работает на **удалённом сервере** (не localhost). Тебе дадут SSH-доступ.
- Все команды выполняй **через SSH** на сервере.
- Локально тестировать НЕТ смысла — на сервере другой конфиг, другая БД, другой Nginx.

### 2.2 Git & Tool Usage
1) Создай новую ветку (опционально, или работай в мастере, если так настроен CI): `git checkout -b iter3-copy-ui` 
2) Используй `multi_replace_file_content` для точечной вставки текстов в HTML. 
3) Для поиска текстов на замену используй худых агентов (например `grep_search`).
4) Каждый логический блок правок — **отдельным коммитом** (используй `run_command` для git команд):
   - `copy(P0): UA/RU/EN text update — hero, rotator`
   - `ui(P1): file-scan animation + breathing CTA (from Agent4 SVG)`

### 1.3 Деплой (в конце)
После завершения всех изменений и проверки:
```bash
git add -A
git commit -m "iter3: final review pass"
git push origin iter3-copy-ui
# Затем на сервере:
cd /path/to/project  # (путь к проекту на сервере)
git pull origin iter3-copy-ui
python manage.py collectstatic --noinput
# Сообщи владельцу если нужно перезагрузить gunicorn/uwsgi
# Если Cloudflare — предупреди о необходимости purge cache
```

---

## 3) Прочие инструменты (ОБЯЗАТЕЛЬНО используй)

### 2.1 Sequential Thinking (MCP)
Используй **sequential thinking** при:
- Планировании порядка изменений (какой файл первый, какой второй)
- Анализе сложных шаблонов перед правкой (hero layout, dock structure)
- Принятии решений при неоднозначных ситуациях
- Проверке что не ломаешь существующую логику

### 3.2 Context7 (MCP)
Используй **Context7** для:
- Уточнения синтаксиса Django template tags (`{% blocktrans %}`)
- Работы с Javascript HTMX (если затронуто)
- Разрешения конфликтов IntersectionObserver API

### 3.3 Linear (опционально)
Если настроен MCP Linear:
Создай **Linear issue** и обновляй чек-листы:
- [ ] P0: Термины
- [ ] P0: Навигация + footer
- [ ] P1: Dot Background (repulsion + breathing + glow)
- [ ] Чтение Handover
- [ ] Интеграция SVG и CSS (Agent 4)

### 2.4 Управление контекстом (256K токенов)
Твой контекст — 256 000 токенов. При работе с большим количеством файлов:
1) **Каждые 3–4 шага** — записывай промежуточный чеклист в комментарий Linear issue: что сделано ✅, что осталось ⬜
2) **Перед крупной правкой** — сначала составь краткий план (какие файлы, какие строки), потом правь
3) **По завершении** — составь финальный отчёт (changelog + что не успел)
4) Если чувствуешь, что контекст заканчивается — запиши TODO-файл `ITER3_PROGRESS.md` в корне `Ideas/itr3/v2/` с текущим статусом

### 2.5 Другие навыки
Используй все доступные тебе навыки по мере надобности: поиск по коду, grep, анализ файлов, браузер для проверки и т.д.

---

## 4) Источники истины (читай и следуй)

| Файл | Путь | Что внутри |
|------|------|-----------|
| **Тексты UA** | `twocomms/Ideas/itr3/v2/ITER3_02_COPY_UA.md` | Мастер-версия всех текстов |
| **Тексты RU** | `twocomms/Ideas/itr3/v2/ITER3_03_COPY_RU.md` | Русский перевод |
| **Тексты EN** | `twocomms/Ideas/itr3/v2/ITER3_04_COPY_EN.md` | Английский перевод |
| **UI Micro‑pack** | `twocomms/Ideas/itr3/v2/ITER3_05_UI_MICROPACK.md` | Анимации и эффекты |
| **Business answers** | `twocomms/Ideas/itr3/v2/ITER3_08_BUSINESS_ANSWERS.md` | Правда бизнеса (без conditionals) |
| **Глоссарий** | `twocomms/Ideas/itr3/v2/ITER3_GLOSSARY.md` | UA/RU/EN термины (быстрый lookup) |
| **Карта файлов** | `twocomms/Ideas/itr3/v2/ITER3_FILE_MAP.md` | Template→URL→Copy, CSS/JS структура |

> **ВАЖНО:** Все тексты берёшь СТРОГО из этих файлов. Не выдумывай свои формулировки.  
> **📋 Начни с ГЛОССАРИЯ и FILE_MAP** — это сэкономит токены на поиске файлов.

---

## 5) Порядок выполнения (ВАЖНО — не меняй)

### Шаг 1 — Тексты и термины (P0)

**4.1.1 Глобальная чистка терминов**
Пройтись по шаблонам и локализациям DTF‑части и убрать из UA/RU UI‑строк:

```bash
# Поиск с исключением документации:
rg -i "preflight|gang.sheet|ганг.лист|hot.peel|QC|Knowledge.Base|Safe.area" \
  --glob '!twocomms/Ideas/**' --glob '!*.py' twocomms/dtf/
```

Замены (берём из Copy A2):
| Найти | UA | RU | EN |
|-------|----|----|-----|
| `preflight` | `перевірка файлу` | `проверка файла` | `file check` |
| `gang sheet/ганг-лист` | `лист 60 см` | `лист 60 см` | `60 cm sheet` |
| `hot peel` | `гаряче зняття` | `горячее снятие` | `peel while hot` |
| `QC` | `контроль якості` | `контроль качества` | `quality check` |
| `Summary` (в UA/RU) | `Підсумок` | `Итог` | `Summary` (оставить) |
| `Knowledge Base` | `База знань` | `База знаний` | `Knowledge base` |
| `Safe area` | `Безпечна зона` | `Безопасная зона` | `Safe area` |
| `OK/INFO/WARN/FAIL` | K1 из copy | K1 из copy | K1 из copy |

**4.1.2 Навигация (header/menu)**
- Если в меню есть `Конструктор` → заменить на `Зібрати лист 60 см` (UA) / `Собрать лист 60 см` (RU) / `Build a 60 cm sheet` (EN)
- Если кнопка `Усі статті Knowledge Base` → `Усі статті бази знань` (UA) / `Все статьи базы знаний` (RU) / `All knowledge base articles` (EN)

**4.1.3 Footer trust line**
Добавить/обновить короткую подпись в footer (см. Copy A6):
- UA: `Файл перевіряємо до друку. Нюанси погоджуємо в Telegram.`
- RU: `Файл проверяем до печати. Нюансы согласовываем в Telegram.`
- EN: `We check your file before printing. We confirm details in Telegram.`

**4.1.4 Demo-контент**
Если на `/gallery/` или других страницах есть placeholder-карточки без реального контента — добавить маркировку `DEMO / оновлюємо` (мелкий бейдж).

**Acceptance:** визуально на UA/RU нет англо-терминов в UI; `rg` не находит запрещённые термины.

---

### Шаг 2 — Hero главной (P0)

**Цель:** Hero содержит ≤ 7 информационных элементов.

1) **Убрать перегруз:**
   - Убрать/не использовать eyebrow (если дублирует H1/rotator)
   - Убрать дубли "контроль білого/QC/preflight"
   - Убрать любые "красные" предупреждения (типа "ризикові файли…")
   
2) **Оставить 7 элементов:**
   - Rotator bar (наверху)
   - H1 (из Copy B)
   - Subtitle (из Copy B)
   - Price card (из Copy B, hero card): `від 280 грн/м`
   - Primary CTA: `Замовити друк`
   - Secondary CTA: `Безкоштовний тест`
   - Text link: `Запитати в Telegram →`

3) **Price card:** `від 280 грн/м` (не диапазон!)

4) **Mobile layout (< 768px) — порядок элементов:**
   ```
   Rotator → H1 → Subtitle → Price card → [Primary CTA] → [Secondary CTA] → Text link
   ```
   CTA-кнопки на мобилке — **full-width, stacked вертикально**.

---

### Шаг 3 — Telegram deep‑link (P0)

1) Все кнопки/ссылки "Telegram" должны вести на deep‑link:
   ```
   https://t.me/<USERNAME>?text=<URL_ENCODED_TEXT>
   ```
2) Текст — из раздела **K4** в copy‑файлах (UA/RU/EN) **по контексту страницы**:
   - Home / Price / Requirements / Order-success / Quality
3) Если Telegram username хранится в настройках/шаблонах — используй существующий источник, не хардкодь.

**Acceptance:** клик по Telegram‑CTA открывает чат с **уже набранным сообщением**.

---

### Шаг 4 — Статусы проверки (P0)

Заменить `OK/INFO/WARN/FAIL` на локализованные статусы (см. K1):

| Было | UA | RU | EN |
|------|----|----|-----|
| OK | `Все добре` | `Все хорошо` | `All good` |
| INFO | `Є рекомендація` | `Есть рекомендация` | `Recommendation` |
| WARN | `Потрібна увага` | `Нужно внимание` | `Needs attention` |
| FAIL | `Потрібна правка` | `Нужна правка` | `Needs fix` |

Добавить иконки рядом (✅ ℹ️ ⚠️ ❌) — но без тяжёлых компонентов.

---

### Шаг 5 — Остальные страницы (P0)

Пройтись по copy-файлам секция за секцией и обновить тексты:

| Секция copy | Страница | URL | Что править |
|-------------|----------|-----|-----------|
| B | Головна | `/` | Hero (уже в шаге 2) |
| C | Ціни | `/price/` | H1, вступ, калькулятор |
| D | Замовлення | `/order/` | H1, вступ, dropzone, post-submit |
| E | Вимоги | `/requirements/` | H1, вступ, "файл не в розмірі", безпечна зона |
| F | Шаблони | `/templates/` | H1, вступ |
| G | Якість | `/quality/` | H1, вступ, тези |
| H | Кейси | `/gallery/` | H1, вступ + demo-маркировка |
| I | FAQ | `/faq/` | H1, вопросы/ответы (формат "Коротко/Детальніше") |
| J | Конструктор | `/constructor/app/` | H1, stepper |
| P | Безкоштовний тест | `/sample/` | **Новая страница** (создать если нет) |

**Страницы L, M, N, O** (`/payment-delivery/`, `/returns/`, `/privacy/`, `/terms/`):
- Сначала **проверь существуют ли** они в роутинге Django.
- Если существуют — обнови тексты из copy.
- Если НЕТ — **ничего не создавай**, пометь в отчёте.

---

### Шаг 6 — UI micro-pack (P1)

Внедри из `ITER3_05_UI_MICROPACK.md` (секции 1-7):
1) "File scan" (иконка + scan-line) для состояния `Перевіряємо файл…`
2) Лёгкий breathing-pulse для Secondary CTA `Безкоштовний тест`
3) One-shot glow для Telegram в dock
4) FAQ-аккордеон (Коротко/Детальніше) с плавным max-height
5) (Опционально) Multi-Step Loader (4 шага)

**SVG-иконки:** используй их из папки `dtf/static/dtf/svg/` так, как тебе передал Agent 4 в файле `ITER3_AGENT4_HANDOVER.md`. (Подключаются через `{% include %}`).

**Регистрация эффектов:**
```javascript
if (DTF.registerEffect) {
  DTF.registerEffect('effect-name', 'CSS-selector', initFunction);
}
```

---

### Шаг 7 — Dot Distortion Background (P1)

> **Подробная спецификация:** см. `ITER3_05_UI_MICROPACK.md`, секция 8.  
> **⚠️ Псевдокод в MICROPACK — ОРИЕНТИР.** Изучи текущую реализацию, подумай, как сделать LUCHSHE, и напиши свой код. Копируй только идеальные фрагменты.

**Файл:** `dtf/static/dtf/js/dtf.js` → функция `initHomeDotBackground()` (строка ~1124)

**Что менять:**
1) **Физика:** заменить PULL (притяжение) на **REPULSION (отталкивание)** — точки отталкиваются от курсора
2) **Убрать flashlight:** удалить `createRadialGradient` halo (строки ~1224-1229)
3) **Добавить breathing:** каждая точка пульсирует ±15% размера (индивидуальная фаза)
4) **Добавить glow pulses:** случайные точки изредка ярко мигают (1-2 в сек)
5) **Spring-back:** точки мягко пружинят к grid-позиции

**Сохранить без изменений:**
- ✅ Систему тиров (`resolveAmbientTier`)
- ✅ Оранжевую палитру
- ✅ Canvas-подход
- ✅ `prefers-reduced-motion` → `is-static`
- ✅ frameBudget throttling

**Mobile:**
- Tier 1-2: influenceRadius = 80-100px (vs 150 desktop)
- Touch: `pointermove` для позиции distortion
- Max dots mobile: ≤620, spacing ≥34px
- Tier 0: CSS static dots (radial-gradient)

**Context7:** обязательно проверь canvas animation best practices, requestAnimationFrame patterns, и touch event handling.

**Acceptance:** точки отталкиваются от курсора, дышат, иногда мигают. Нет flashlight-halo. На mobile всё плавно.

---

### Шаг 8 — Component Visual Polish (P1)

> **Подробная спецификация:** см. `ITER3_05_UI_MICROPACK.md`, секция 9.  
> **⚠️ CSS в MICROPACK — ОРИЕНТИР.** Возьми идею, но реализуй свой вариант если можешь сделать лучше.

**Что внедрить (используя CSS классы из отчёта Agent4):**
1) **Кнопки:** hover `scale(1.02)` + shadow + active `scale(0.98)`
2) **Карточки:** `fade-in-up` через IntersectionObserver (staggered)
3) **Form inputs:** animated underline на focus
4) **Dropzone:** dashed border pulse при drag-over
5) **Price badge:** shimmer gradient animation
6) **Mobile dock:** slide-up entrance с bounce
7) **Touch targets:** `min-height: 48px` при `@media (pointer: coarse)`

**Acceptance:** кнопки анимируются при наведении, карточки появляются при скролле, формы имеют animated focus. Всё выключается при `prefers-reduced-motion`.

---

## 6) Координация с Agent4 (Gemini 3.1 — Дизайнер)

### 5.1 Что делает Agent4
Agent4 создаёт SVG-иконки и CSS-анимации по промпту `ITER3_07_PROMPT_AGENT4_GEMINI.md`.

### 5.2 Контракт интеграции

**Naming convention:**
- SVG-файлы: `icon-{name}.svg` (напр. `icon-check.svg`, `icon-scan.svg`, `icon-bulb.svg`)
- CSS-классы: `.dtf-icon-{name}` (напр. `.dtf-icon-check`, `.dtf-icon-scan`)
- Анимации: `.dtf-icon-animate` (добавляется JS-ом при срабатывании)

**Расположение файлов:**
- SVG: `dtf/static/dtf/svg/` (или inline через Django `{% include %}`)
- CSS анимаций: `dtf/static/dtf/css/components/icons.css`

**HTML-шаблон использования:**
```html
<span class="dtf-icon dtf-icon-check" aria-hidden="true">
  {% include "dtf/svg/icon-check.svg" %}
</span>
```

**Fallback (если SVG от Agent4 ещё нет):**
```html
<span class="dtf-icon dtf-icon-check" aria-hidden="true">✅</span>
```

### 5.3 CSS-переменные (общие для обоих агентов)
```css
:root {
  --dtf-accent: #3b82f6;
  --dtf-success: #22c55e;
  --dtf-warning: #eab308;
  --dtf-danger: #ef4444;
  --dtf-info: #3b82f6;
  --dtf-border: #e5e7eb;
}
```

---

## 9) Cache invalidation (ПОСЛЕ всех изменений)

```bash
# 1. Собрать статику
python manage.py collectstatic --noinput

# 2. Если CSS/JS НЕ используют hash-суффиксы:
#    — Обновить ?v= query string в <link> и <script> тегах:
#    — Формат: ?v=iter3-20260224

# 3. Если Cloudflare — сообщить владельцу о purge cache

# 4. Проверить что загружается свежая версия CSS/JS
```

---

## 10) Чек-лист проверки перед финалом (DoD)

### ✅ ТЕКСТЫ
- [ ] `rg` по DTF-части: 0 вхождений `preflight|QC|hot peel|gang|ганг|Knowledge Base|Safe area|OK/INFO/WARN/FAIL` в UI-строках (UA/RU)
- [ ] Все H1 на каждой странице соответствуют copy-файлам (3 языка)
- [ ] CTA-тексты совпадают с copy-файлами
- [ ] CTA Primary ≤ 14 символов на UA (для мобильной безопасности 320px)
- [ ] Rotator: ≥ 3 фразы, НЕ дублирующие Hero
- [ ] FAQ: формат «Коротко: ... / Детальніше: ...» (UA/RU/EN)
- [ ] Post-submit: содержит эмоцию и доп. ссылки
- [ ] Footer trust line обновлён

### ✅ ВИЗУАЛ
- [ ] Hero содержит ≤ 7 информационных элементов
- [ ] Ценовой якорь = `від 280 грн/м` (не диапазон)
- [ ] Нет "красных" предупреждений на первом экране
- [ ] Mobile dock: 4 иконки, без дублей
- [ ] Telegram link = deep-link с `?text=`

### ✅ MOBILE (проверить на сервере)
- [ ] Hero на 320px: не ломается, CTA не переносятся на 2 строки
- [ ] Hero на 360px: ок
- [ ] Hero на 390px: ок
- [ ] Dock не перекрывает CTA
- [ ] **Touch targets ≥ 44×44px** на всех интерактивных элементах

### ✅ PERFORMANCE
- [ ] Все анимации — `transform`/`opacity` only
- [ ] `prefers-reduced-motion: reduce` — анимации выключаются
- [ ] Lighthouse Mobile: не ухудшился (сравнить до/после)
- [ ] **Dot background: ≤620 dots на mobile, не ронять FPS**

### ✅ VISUAL POLISH
- [ ] Кнопки анимируются при hover/active
- [ ] Карточки появляются с fade-in-up
- [ ] Dot background: repulsion physics работает
- [ ] Component polish НЕ ломает существующий layout

### ✅ I18N
- [ ] Все 3 языка (uk/ru/en) обновлены синхронно
- [ ] Нет смешения языков на одной странице
- [ ] Системные строки K1/K2/K3 есть на всех языках
- [ ] TG deep-link prefill работает на всех языках

### ✅ SAFETY
- [ ] Изменения ТОЛЬКО в `twocomms/dtf/`
- [ ] Никакие `*.py` backend файлы не затронуты (кроме views если нужна page `/sample/`)
- [ ] Никакие миграции не созданы
- [ ] `collectstatic` выполнен
- [ ] Cache version обновлён (?v= параметр)

### ✅ GIT + DEPLOY
- [ ] Все коммиты осмысленные (не один гигантский)
- [ ] `git push origin iter3-copy-ui` выполнен
- [ ] Pull на сервере выполнен
- [ ] `collectstatic` на сервере выполнен
- [ ] Сайт работает после деплоя

---

## 11) Отчёт в конце

В конце пришли **краткий отчёт**:
1) Что сделано — по шагам (P0.1, P0.2, ...)
2) Что НЕ сделано — если не успел (и почему)
3) Где именно лежат изменения — файлы + коммиты
4) Скриншоты/описание проверки hero на 320px
5) Результат DoD (пункт за пунктом)
6) Обновить Linear issue с финальным статусом
