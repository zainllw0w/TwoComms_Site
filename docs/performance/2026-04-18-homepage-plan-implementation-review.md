# Review of Homepage Performance Plan and Partial Implementation

Дата: `2026-04-18`  
Основной repo: `/Users/zainllw0w/TwoComms/site`  
Проверенная реализация другого агента: worktree `/Users/zainllw0w/TwoComms/site/.claude/worktrees/exciting-knuth-90e872`  
Ветка реализации: `claude/exciting-knuth-90e872`

## Цель этого документа

Этот файл нужен как handoff для следующего агента.

Задача была двойная:

1. Оценить, насколько качественно другой агент выполнил уже начатые Phase 1 изменения.
2. Зафиксировать реальный статус плана: что сделано хорошо, что сделано частично, что пока нельзя считать выполненным, и что нужно брать следующим шагом.

Важно:

- этот review основан на фактическом коде в worktree `claude/exciting-knuth-90e872`, а не на optimistic summary
- line refs ниже относятся именно к проверенной версии в этом worktree
- существующий файл `docs/performance/2026-04-18-homepage-phase1-implementation-report.md` в worktree полезен как черновик, но не должен считаться source of truth без поправок

---

## Короткий вердикт

### Общая оценка

План у агента сильный. Он хорошо попал в реальные bottlenecks и выстроил приоритеты в правильном порядке:

- images
- fonts
- analytics / third-party
- layout thrash
- dead code

Но фактическая реализация пока неравномерная.

Что сделано хорошо:

- font dedupe как quick win
- Font Awesome opt-out на home
- удаление реально мертвого кода в `optimizers.js`
- отключение mobile equalization по viewport
- замена forced reflow через `offsetHeight` на `double requestAnimationFrame`
- wiring strict warning в `responsive_images.py`

Что сделано частично или переоценено:

- analytics deferral реализован не до конца и в текущем виде не дает заявленного эффекта
- `device-class` логика начата, но unified detector не внедрен
- survey startup path не стал click-lazy, а только убрал дубль импорта
- image pipeline не починен, а только получил warning hook
- phase1 implementation report местами утверждает вещи, которых в коде пока нет

Итоговая оценка по текущей реализации:

- план: `8.5/10`
- внедренный код: `6/10`
- качество безопасных quick wins: `8/10`
- качество analytics/device-tier части: `4/10`

---

## Главные findings до merge

### 1. `analytics-loader.js` все еще почти сразу загружает pixels после `window.load`

Файлы:

- `twocomms/twocomms_django_theme/static/js/analytics-loader.js:1411-1421`
- `twocomms/twocomms_django_theme/static/js/analytics-loader.js:1401-1409`

Проблема:

- агент добавил `requestIdleCallback`/timeout-based defer для `initializePixelsDeferred()`
- но оставил `window.load` fallback, который через `500 ms` вызывает `initializePixelsDeferred()`, если pixels еще не loaded
- на практике это почти полностью съедает benefit от idle-delay

Что это значит:

- Meta/TikTok stack все равно приедет очень рано
- post-load jank на mobile останется намного ближе к прежнему поведению, чем заявлено в отчете

Вердикт:

- это не “finished optimization”
- это partial change с критическим остаточным loophole

### 2. Low-device ветки analytics и equalization читают `dataset.deviceClass`, но он вообще не выставляется

Файлы:

- `twocomms/twocomms_django_theme/static/js/analytics-loader.js:1350-1351`
- `twocomms/twocomms_django_theme/static/js/main.js:2057-2060`
- `twocomms/twocomms_django_theme/templates/base.html:106-135`

Подтверждено:

- в `base.html` выставляется только класс `perf-lite`
- `data-device-class` в шаблоне не задается
- отдельный grep/check подтвердил: `data-device-class present: False`

Что это значит:

- `isLowDevice` в `analytics-loader.js` сейчас всегда вычисляется из пустого `dataset.deviceClass` и остается `false`
- skip для TikTok и Clarity на low-end сейчас фактически не работает
- часть Phase 1 summary про low-device behavior сейчас ложная

Нюанс:

- в `main.js` mobile equalization все равно отключается по viewport `< 900px`, поэтому этот кусок частично полезен
- но именно low-device tiering пока не реализован

### 3. `survey.js` больше не импортируется дважды, но все еще импортируется сразу на home-load, а не по клику

Файлы:

- `twocomms/twocomms_django_theme/static/js/main.js:2550`
- `twocomms/twocomms_django_theme/templates/pages/index.html:1652-1658`

Что реально сделано:

- дубль импорта из `main.js` убран

Что не сделано:

- `index.html` по-прежнему импортирует `survey.js` сразу при загрузке страницы
- click-lazy mounting не внедрен

Что это значит:

- Phase 1.5 выполнен только частично
- Phase 1 report ошибочно формулирует это как будто `survey.js` уже ушел в click path

### 4. Strict image warning добавлен, но по умолчанию не будет работать на production без явного settings flag

Файлы:

- `twocomms/storefront/templatetags/responsive_images.py:19`
- `twocomms/storefront/templatetags/responsive_images.py:243-244`

Что сделано:

- warning hook подключен корректно

Что не хватает:

- `PERF_IMAGE_STRICT` нигде не добавлен в production settings
- fallback по умолчанию идет в `settings.DEBUG`, а на production это `False`

Что это значит:

- как quick win для dev/ops это нормально
- как “Phase 1 image pipeline strict mode on prod” это пока incomplete

### 5. Existing Phase 1 implementation report переоценивает текущий эффект и местами расходится с кодом

Файл:

- `docs/performance/2026-04-18-homepage-phase1-implementation-report.md` в worktree `claude/exciting-knuth-90e872`

Конкретные расхождения:

- `:20-21` утверждает, что TikTok + Clarity отключены на `device-class=low`, хотя `data-device-class` не выставляется
- `:99` ссылается на CSS-grid / `grid-auto-rows: 1fr` и `min-height: calc(2*1.4em)`, но такой Phase 1 CSS change в активных стилях не был добавлен
- `:114` утверждает, что survey import теперь идет “по клику на CTA”, но `index.html` все еще делает eager module import на page load
- `:138` заявляет `726 → ~150 KB` third-party transfer, хотя текущий код это не подтверждает и `window.load` fallback мешает такому выигрышу

Вывод:

- сам файл полезен как narrative draft
- но его нельзя использовать как точный статус-файл без исправлений

---

## Статус по плану: done / partial / not done

### Phase 1.1 — Image pipeline

Статус: `partial`

Что реально сделано:

- добавлен logger
- добавлен `_STRICT_MODE`
- добавлен `_warn_missing_variants()`
- добавлен реальный call в `optimized_image()`

Что не сделано:

- production media не прогнаны через `optimize_images`
- нет signal / cron / auto-regeneration
- не добавлены `fetchpriority="high"` path для first-fold/LCP карточек
- нет responsive preload для hero image
- нет production setting для `PERF_IMAGE_STRICT`

Оценка качества:

- хороший технический задел
- но проблему homepage images он пока не решает

### Phase 1.2 — Fonts

Статус: `done as quick win`, но `not complete vs full plan`

Что реально сделано:

- из `fonts.css` удалены 400/700
- оставлены только 500/600
- duplicate load для `Regular/Bold` реально снимается

Что не сделано:

- Inter Variable не внедрен
- unicode-range / subset / refined font strategy не внедрены
- mobile system font fallback по device-tier не внедрен

Оценка качества:

- изменение хорошее и безопасное
- это один из лучших уже выполненных кусков

### Phase 1.3 — Third-party / analytics

Статус: `partial with important flaws`

Что реально сделано:

- `mousemove` убран из interactionEvents
- добавлены `pointerdown` и `keydown`
- добавлены idle-based schedules для GA/Clarity/Pixels
- TikTok условно пропускается на low-device
- Clarity условно не грузится на low-device

Что ломает ожидаемый эффект:

- `window.load` fallback почти сразу вызывает pixel init
- `deviceClass` нигде не задается
- `gtag.js` не убран, GTM-only path не внедрен
- Consent Mode v2 не внедрен

Оценка качества:

- направление правильное
- текущий код нельзя считать завершенным optimization block

### Phase 1.4 — Layout equalization / reflow

Статус: `mostly done`

Что реально сделано:

- mobile viewport `< 900px` теперь не проходит через equalization
- `offsetHeight` forced reflow удален
- оставлен desktop path

Что не сделано:

- CSS replacement strategy явно не доведена как часть этого же этапа
- low-device gating по `deviceClass` пока формально incomplete

Оценка качества:

- хороший практичный quick win
- даже в текущем виде должен дать реальный плюс на mobile

### Phase 1.5 — Dead code / cleanup

Статус: `mostly done`, но не полностью

Что реально сделано:

- удален `scrollThreshold`
- удален `optimizeMobileImages()`
- убран duplicate survey import из `main.js`
- home получил FA opt-out

Что не сделано:

- survey не переведен на click-lazy import
- inline fallback JS в `base.html` не удален
- Bootstrap JS не тронут

Оценка качества:

- чистка в целом полезная
- но summary агента называет этот этап более завершенным, чем он есть

---

## Что сделано реально хорошо

### 1. Font Awesome opt-out на home

Файлы:

- `twocomms/twocomms_django_theme/templates/base.html:21-26`
- `twocomms/twocomms_django_theme/templates/pages/index.html:11-12`

Почему это хорошо:

- изменение локальное
- не ломает другие 23 шаблона, где FA реально используется
- дает понятный и почти безрисковый win

### 2. Удаление `scrollThreshold` и `optimizeMobileImages()`

Файл:

- `twocomms/twocomms_django_theme/static/js/modules/optimizers.js`

Почему это хорошо:

- это реальный dead code cleanup
- подтверждается grep-поиском
- не требует предположений

### 3. Деактивация equalization на mobile viewport

Файл:

- `twocomms/twocomms_django_theme/static/js/main.js:2052-2062`

Почему это хорошо:

- эта логика бьет прямо по подтвержденному layout bottleneck
- даже без `device-class` она работает за счет viewport gate

### 4. Замена forced reflow на double-rAF

Файл:

- `twocomms/twocomms_django_theme/static/js/main.js:2461-2468`

Почему это хорошо:

- это реальная технически грамотная замена
- визуальную семантику сохраняет
- main thread path становится чище

### 5. Wiring strict warning в `responsive_images.py`

Файл:

- `twocomms/storefront/templatetags/responsive_images.py:23-32`
- `twocomms/storefront/templatetags/responsive_images.py:243-244`

Почему это хорошо:

- аккуратный low-risk change
- не маскирует проблему
- прямо помогает ops-level диагностике

---

## Что нельзя пока считать завершенным

### 1. “Low-device optimization” как тема

Пока в коде есть только куски, зависящие от `dataset.deviceClass`, но единого раннего device detector нет.

До внедрения unified detector нельзя утверждать, что:

- low-end устройства реально пропускают TikTok
- low-end устройства реально не получают Clarity
- низкий device tier реально влияет на JS path системно

### 2. “Survey lazy path”

Сейчас это только:

- удаление одного из двух imports

Но не:

- lazy mount modal по клику
- lazy import `survey.js` по интеракции
- уменьшение startup DOM/JS стоимости survey path

### 3. “Image pipeline fixed”

Сейчас image bottleneck не исправлен.

Исправлено только:

- логирование missing variants

Не исправлено:

- отсутствие самих AVIF/WebP variants на production assets
- first-fold priority hints
- regeneration pipeline

### 4. “Phase 1 metrics reached”

Никаких post-change production замеров в этом review не подтверждено.

До нового production audit нельзя утверждать:

- что fonts уже ушли к `≤ 260 KB`
- что third-party initial stack реально стал `~150 KB`
- что LCP/TTI уже существенно улучшились

---

## Что стоит брать в merge/cherry-pick в первую очередь

### Safe and useful now

- `twocomms/twocomms_django_theme/static/css/fonts.css`
- `twocomms/twocomms_django_theme/templates/base.html`
- `twocomms/twocomms_django_theme/templates/pages/index.html` block override для FA
- `twocomms/twocomms_django_theme/static/js/modules/optimizers.js`
- `twocomms/twocomms_django_theme/static/js/main.js` equalization early return + reflow removal
- `twocomms/storefront/templatetags/responsive_images.py` warning hook

### Needs rework before merge

- `twocomms/twocomms_django_theme/static/js/analytics-loader.js`
- `docs/performance/2026-04-18-homepage-phase1-implementation-report.md` из worktree

Причина:

- analytics change пока вводит ложное ощущение сильно улучшенного startup path
- report фиксирует как факт то, что пока не доведено до рабочего состояния

---

## Что должен делать следующий агент

### 1. Не переаудировать заново весь homepage

Главные bottlenecks уже локализованы предыдущим production audit.
Следующий шаг — не новый глобальный анализ, а точный рефакторинг по приоритету.

### 2. Исправить analytics block до реально рабочего состояния

Минимально нужно:

- убрать или сильно ослабить `window.load` fallback в `analytics-loader.js`
- внедрить единый ранний `data-device-class` detector в `base.html`
- перевести `analytics-loader.js` на этот detector
- после этого повторно проверить реальный post-load network tail

### 3. Не считать survey-path оптимизированным

Нужно отдельно сделать:

- click-lazy import `survey.js`
- lazy mount `#survey-modal`
- по возможности облегчение survey SVG/overlay path

### 4. Довести image pipeline до production-safe результата

Нужно отдельно сделать:

- production run `optimize_images`
- возможно cron / signal / background generation
- явный first-fold priority strategy для карточек на home

### 5. Исправить статусный phase1-report

Если следующий агент будет использовать existing phase1-report, его надо сначала привести в соответствие с реальным кодом.

---

## Верификация, выполненная для этого review

Проверено:

- `python3 -m py_compile twocomms/storefront/templatetags/responsive_images.py` — passed
- `node --check` для:
  - `static/js/main.js`
  - `static/js/analytics-loader.js`
  - `static/js/modules/optimizers.js`
  - `static/js/modules/shared.js`
  — passed
- поиском подтверждено:
  - `data-device-class` в шаблонах не выставляется
  - `survey.js` в `index.html` все еще импортируется сразу на page load

Не проверялось:

- production deploy
- production Lighthouse after changes
- visual regression на реальном staging/prod

---

## Финальный вывод

Другой агент сделал полезную и местами сильную groundwork-работу, но внедрение неравномерное.

Самое ценное, что уже есть:

- safe quick wins по fonts / FA / dead code / mobile equalization
- хороший план, который можно использовать как основу рефакторинга

Самое опасное сейчас:

- поверить existing phase1-report как будто большая часть P0 уже “готова”

Корректная формулировка статуса на сейчас:

- Phase 1 частично начат
- часть low-risk оптимизаций сделана качественно
- analytics / device-tier / survey-lazy / image-pipeline остаются незавершенными
- следующий агент должен идти в targeted refactor, а не в повторный broad audit
