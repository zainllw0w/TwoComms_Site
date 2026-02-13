# Аудит эффектов и компонентов для `dtf.twocomms.shop` (CODEX)

## 0) Что именно сделано в этом отчете

Я провел аудит по четырем источникам одновременно:

1. Реальный код проекта (`Django templates + static JS/CSS`) в `twocomms/dtf/*`.
2. Ваш каталог компонентов в `twocomms/Promt/Effects.MD`.
3. Фактические подключенные эффекты в `base.html` и их использование по страницам.
4. Визуальные артефакты QA-скринов (`specs/dtf-codex/perf/screens/*`) для проверки UX-конфликтов.

Отчет ниже закрывает ваши вопросы:
- как работают эффекты и компоненты,
- как их внедрять именно в ваш проект,
- лучшие практики,
- на чем писать код в вашем стеке,
- насколько это тяжело для сайта,
- нужен ли `npx` для каждого компонента,
- можно ли полностью хостить у себя,
- плюсы/минусы по компонентам,
- 100 конкретных идей внедрения по страницам `dtf.twocomms.shop`.

---

## 1) Быстрый вывод (Executive Summary)

1. У вас уже есть рабочая vanilla-инфраструктура эффектов (registry + idempotent init + HTMX re-init), и это правильное направление для текущего Django-стека.
2. Главный UX-конфликт подтвержден: внизу справа одновременно живут `FAB`, `floating dock` и `mobile dock`, что создает перекрытия CTA/навигации.
3. Из каталога `Effects.MD` часть компонентов уже портирована и работает, часть пока только как reference (не внедрена).
4. Для вашего проекта лучше **не** тянуть React/Framer в основной DTF-фронт. Оптимальный путь: продолжать vanilla-порт (как сейчас), с feature flags и прогрессивным улучшением.
5. `npx shadcn add ...` нужен только на этапе импорта исходника. В проде все может (и должно) работать полностью локально из ваших статики/скриптов, без runtime-зависимости от стороннего сайта.
6. По текущим размерам эффект-пакет легкий: компоненты около `~42.4 KB raw` (`~17.1 KB gzip`) суммарно, основной вес идет от `dtf.js`/`dtf.css` и изображений.

---

## 2) Текущая архитектура эффектов в проекте (факт)

## 2.1 Стек и runtime

- Backend: Django (`twocomms/dtf/views.py`, server-rendered templates).
- Frontend: vanilla JS + CSS + HTMX.
- Базовый шаблон: `twocomms/dtf/templates/dtf/base.html`.
- Глобальный JS lifecycle: `twocomms/dtf/static/dtf/js/dtf.js`.
- Effect registry (новый слой):
  - `twocomms/dtf/static/dtf/js/components/core.js`
  - `twocomms/dtf/static/dtf/js/components/_utils.js`

## 2.2 Что подключается глобально

В `base.html` подключены effect-модули:
- `effect.bg-beams`
- `effect.dotted-glow`
- `effect.encrypted-text`
- `effect.pointer-highlight`
- `effect.compare`
- `effect.stateful-button`
- `effect.tracing-beam`
- `effect.infinite-cards`
- плюс: `sparkles`, `floating-dock`, `multi-step-loader`, `vanish-input`, `tabs-download`, `cards-on-click`

Это правильно: эффекты централизованы и переиспользуются по страницам.

## 2.3 Где эффекты уже реально используются (по шаблонам)

По факту в `templates/dtf/*.html`:
- `compare`: 6 вхождений
- `bg-beams`: 4
- `dotted-glow`: 4
- `encrypted-text`: 3
- `tracing-beam`: 3
- `vanish-input`: 3
- `multi-step-loader`: 2
- `infinite-cards`: 1
- `sparkles`: 1
- `tabs-download`: 1

## 2.4 Подтвержденные проблемные зоны

### Проблема A: конфликт правого нижнего угла

Одновременно рендерятся:
- `div#dtf-fab`
- `nav[data-floating-dock]`
- `nav.mobile-dock`

Из-за этого на части экранов/сценариев есть визуальный шум и перекрытие важных кнопок.

### Проблема B: дубли/техдолг в JS

В `dtf.js` остаются legacy-реализации эффектов (`initCompare`, `initTracingBeam` и др.), при этом фактически активна новая модульная схема через `core.js + effect.*`. Это увеличивает сложность поддержки и риск расхождения поведения.

### Проблема C: текущий `vanish-input` не выполняет вашу бизнес-идею полностью

Сейчас он делает shake/highlight на invalid, но не очищает поле. Вы явно хотите поведение: “ошибка -> красиво исчезло и очистилось”. Нужно доработать.

---

## 3) Ответы на ваши прямые вопросы

## 3.1 Нужен ли `npx` для каждого компонента?

Коротко: **нет, не в проде**.

- `npx shadcn@latest add @aceternity/...` нужен только на этапе импорта исходного React-компонента в dev.
- После импорта код живет у вас в репозитории.
- В проде никакой вызов `npx` не нужен.

## 3.2 Это будет работать со стороннего сайта или можно у нас?

Можно и нужно полностью у вас.

- JS/CSS/иконки/изображения хостятся в `twocomms/dtf/static/dtf/*`.
- Для SEO и стабильности это правильнее.
- Из внешнего желательно оставить только то, что действительно нужно (например, шрифты при желании тоже можно self-host).

## 3.3 На чем лучше писать в вашем проекте?

Для `dtf.twocomms.shop`:

1. Основной путь (рекомендуется): **vanilla JS + CSS + Django templates + HTMX**.
2. React/Next нужен только если вы делаете отдельный тяжелый SPA-блок (например, advanced-конструктор как изолированный микрофронт).
3. Текущая структура уже подготовлена под подход №1, ее надо развивать, а не ломать.

## 3.4 Насколько это тяжелое для сайта?

Замер по локальным файлам:

- `dtf.js`: `81,820 B raw`, `18,948 B gzip`
- `dtf.css`: `99,392 B raw`, `16,776 B gzip`
- все `js/components/*.js`: `33,754 B raw`, `12,446 B gzip`
- все `css/components/*.css`: `8,690 B raw`, `4,640 B gzip`

Итого эффект-пакет сам по себе умеренный. Основная нагрузка обычно от изображений, фонов и непродуманной одновременной анимации на одном экране.

---

## 4) Лучшие практики для внедрения эффектов в вашем проекте

## 4.1 Правило слоев эффектов (очень важно)

На одном экране держать:
- Heavy: максимум 1
- Medium: до 2–3
- Micro: до 6–8

Это убирает “перегрев” страницы и сохраняет CTR.

## 4.2 Progressive enhancement

- SSR-контент всегда читаемый без JS.
- Эффект только улучшает восприятие, но не ломает базовый сценарий.
- Для `prefers-reduced-motion` всегда fallback.

## 4.3 SEO-safe анимации

Для `Infinite Moving Cards`:
- контент карточек должен существовать в DOM как обычный текст/ссылки,
- анимация через CSS transform,
- клон трека помечать `aria-hidden="true"`.

## 4.4 Feature flags + A/B

Хорошо, что у вас уже есть `get_feature_flags()`.
Рекомендую каждый новый heavy/medium эффект включать через флаг:
- можно быстро отключить на проде,
- удобно тестировать влияние на конверсию.

## 4.5 Политика docking/quick-actions

На экране одновременно должен жить только **один** первичный floating action узел.

Рекомендованная стратегия:
- Desktop: `floating dock`
- Mobile: `mobile dock`
- FAB “Менеджер”: только как fallback, или пункт внутри dock, но не отдельный плавающий блок.

---

## 5) Компоненты из `Effects.MD`: аудит, плюсы/минусы, внедряемость

Оценка:
- Сложность внедрения: 1 (просто) — 5 (сложно)
- Нагрузка: Низкая / Средняя / Высокая

| Компонент | Статус в проекте | Сложность | Нагрузка | Плюсы | Минусы/риски | Рекомендация |
|---|---:|---:|---|---|---|---|
| Tooltip Card | Не внедрен | 2 | Низкая | Компактные пояснения, меньше перегруза текста | На mobile hover не работает как на desktop | Использовать точечно в прайсе/требованиях |
| Dotted Glow Background | Внедрен | 1 | Низкая | Атмосфера бренда, мягкий depth | При избытке ухудшает читабельность | Оставить в hero/лендингах |
| Encrypted Text | Внедрен | 2 | Низкая | Отличный “tech-feel” для preflight/QC | Легко перейти в “декоративный шум” | Использовать только в 1-2 местах на странице |
| Images Badge | Не внедрен | 2 | Низкая | Идеально для upload/file-state | Нужно аккуратно с a11y и alt/label | Внедрить в конструктор и upload-блоки |
| Compare (+Sparkles) | Внедрен (compare), sparkles точечно | 3 | Средняя | Сильный доверительный блок “до/после” | Требует качественных парных изображений | Оставить и расширить в галерее/качестве |
| Cover | Не внедрен | 2 | Низкая | Сильный хедлайн-акцент | Может конфликтовать с уже активным hero-стеком | Использовать только для отдельных промо-блоков |
| Floating Dock | Внедрен | 3 | Низкая | Быстрые действия, рост конверсии в deep-scroll | Сейчас конфликтует с FAB/mobile dock | Перестроить логику показа (см. раздел 8) |
| Loaders (общие) | Частично | 2 | Низкая | Ясный feedback в long-run сценариях | Псевдо-прогресс раздражает, если не привязан к этапам | Привязать к реальным backend-этапам |
| Tracing Beam | Внедрен | 2 | Низкая | Читаемая длинная статья/таймлайн | Перегруз, если часто повторять | Оставить в блоге/требованиях |
| Animated Tooltip | Не внедрен | 2 | Низкая | Микро-объяснения без модалок | Может отвлекать при частом применении | Для цен, терминов, material specs |
| Flip Words | Внедрен | 2 | Низкая | Сильный hero-акцент | Может ухудшать ясность оффера | Оставить только на главном оффере |
| Infinite Moving Cards | Частично (lab) | 3 | Средняя | Живой social-proof/USP поток | SEO и a11y ошибки при неправильной реализации | Внедрять только SEO-safe вариантом |
| Placeholders and Vanish Input | Частично (есть vanish-input) | 3 | Низкая | Хорошая UX-реакция на invalid | Сейчас не очищает поле как вы хотите | Доработать под “очистка+анимация” |
| Sidebar | Не внедрен | 4 | Средняя | Отлично для конструктора/кабинета | Для текущих страниц может быть избыточно | Использовать в constructor/cabinet, не глобально |
| Text Generate Effect | Не внедрен | 2 | Низкая | Хороший storytelling/скорость/обещание | Если длинный текст — замедляет сканирование | Короткие слоганы/резюме |
| Multi Step Loader | Внедрен (база), можно расширить | 3 | Низкая | Идеален для preflight и проверки документа | Нужны реальные шаги/статусы от сервера | Внедрить ваш сценарий “проверка по пунктам” |

---

## 6) Обязательные сценарии из вашего ТЗ (как внедрить правильно)

## 6.1 Floating Dock + upload иконка с Image Badge в конструкторе

Что делать:
- В `constructor_app` сделать dock как workspace-actions:
  - `Загрузить`
  - `Слои`
  - `Проверка`
  - `Экспорт`
- Кнопка `Загрузить` получает `image badge` при наличии файла.
- На desktop: hover анимация badge (scale/shine), на mobile: без hover, только active-state.

## 6.2 Multi-step loader для проверки документа по этапам

Ваши шаги (обязательно):
1. Тонкие линии
2. Ширина 60 см
3. Выход за границы
4. DPI
5. Прозрачность
6. Белая подложка (если нужна)

Технически:
- На фронте показывать очередь шагов.
- На бэке preflight API возвращает массив step-status.
- UI обновляется по фактическим событиям, а не таймером.

## 6.3 Блог в постоянном движении как Infinite Moving Cards, но SEO-индексируемо

Правильно:
- Сервер рендерит обычный список карточек с текстом/ссылками.
- Первый трек видимый и индексируемый.
- Второй трек — только клон для бесшовного цикла и `aria-hidden="true"`.
- Для reduced motion: статичный список.

## 6.4 Неверный ввод: очищение поля с эффектом Placeholders & Vanish

Сейчас у вас только “потрясти/подсветить”.
Нужно расширить:
- invalid -> анимация -> очистка value -> возврат placeholder.
- добавить whitelist полей, где авто-очистка уместна (телефон, код, номер заказа), и не делать это для длинных textarea.

## 6.5 Эффект скорости текста (для “отправка день в день”)

Лучшее место:
- `home hero` рядом с SLA
- `order summary` рядом с кнопкой отправки

Режим:
- короткий jitter/velocity only on hover/focus
- авто-анимации без ховера минимальные, чтобы не ухудшать читаемость.

## 6.6 Before/After (анимированный вариант + альтернатива)

У вас уже есть compare slider. Добавить второй режим:
- режим A: manual slider
- режим B: auto-sweep preview (2-3 цикла), потом freeze на ручном

Это дает и wow-эффект, и контроль пользователя.

---

## 7) Рекомендации по коду (как должно выглядеть в вашем проекте)

## 7.1 Базовый паттерн эффекта (у вас уже верный)

```js
// static/dtf/js/components/effect.example.js
(function () {
  const DTF = (window.DTF = window.DTF || {});

  function initExample(node, ctx) {
    if (!node) return null;
    if (ctx && ctx.reducedMotion) {
      node.classList.add('is-static');
      return null;
    }

    const onClick = () => node.classList.toggle('is-active');
    node.addEventListener('click', onClick);

    return function cleanup() {
      node.removeEventListener('click', onClick);
    };
  }

  if (DTF.registerEffect) {
    DTF.registerEffect('example', '[data-effect~="example"]', initExample);
  }
})();
```

## 7.2 SEO-safe infinite cards (паттерн)

```html
<section data-effect="infinite-cards" class="seo-marquee">
  <div class="infinite-track">
    <a class="infinite-item" href="/blog/post-1/">Как подготовить файл</a>
    <a class="infinite-item" href="/blog/post-2/">DPI и тонкие линии</a>
    <a class="infinite-item" href="/blog/post-3/">DTF vs DTG</a>
  </div>
  <div class="infinite-track" aria-hidden="true">
    <a class="infinite-item" href="/blog/post-1/" tabindex="-1">Как подготовить файл</a>
    <a class="infinite-item" href="/blog/post-2/" tabindex="-1">DPI и тонкие линии</a>
    <a class="infinite-item" href="/blog/post-3/" tabindex="-1">DTF vs DTG</a>
  </div>
</section>
```

## 7.3 Vanish input с очисткой (ваш сценарий)

```js
function attachVanishClear(field) {
  const shouldClear = field.matches('[data-vanish-clear="true"]');

  const runInvalid = () => {
    field.classList.add('is-vanish');
    window.setTimeout(() => {
      if (shouldClear) field.value = '';
      field.classList.remove('is-vanish');
      field.focus({ preventScroll: true });
    }, 320);
  };

  field.addEventListener('invalid', (e) => {
    e.preventDefault();
    runInvalid();
  });
}
```

## 7.4 Единая политика quick actions (чтобы убрать конфликт справа снизу)

```css
/* Desktop: dock, Mobile: mobile dock, FAB hidden by default */
.dtf-fab { display: none; }
@media (min-width: 961px) {
  .dtf-floating-dock { display: grid; }
  .mobile-dock { display: none !important; }
}
@media (max-width: 960px) {
  .dtf-floating-dock { display: none !important; }
  .mobile-dock { display: grid; }
}
```

---

## 8) План удаления/замены проблемных компонентов (что вы просили)

## 8.1 Убрать перекрытие справа снизу

Сделать в ближайшем спринте:

1. Оставить один primary floating слой на breakpoint.
2. FAB не дублировать с dock.
3. На `order`/`constructor` скрывать лишние quick-nav элементы полностью.
4. Проверить `z-index` для modal/drawer/fab/dock.

## 8.2 Cleanup техдолга

1. Удалить неиспользуемые legacy-инициализаторы эффектов из `dtf.js` после миграции на `effect.*`.
2. Удалить дубли component файлов, которые не подключаются.
3. Зафиксировать единый стиль naming: только `effect.*` для новых эффектов.

## 8.3 UX-правки обязательных эффектов

1. `vanish-input` -> добавить режим clear.
2. `multi-step-loader` -> связать с реальными check step результатами.
3. `infinite-cards` -> включать только при наличии достаточного контента, с SEO-safe разметкой.

---

## 9) Установка и “локальность” компонентов (по каждому CLI из `Effects.MD`)

Ниже команды, но важный принцип один: `npx` используется только в dev для импорта исходника; в проде все локально.

- `npx shadcn@latest add @aceternity/tooltip-card`
- `npx shadcn@latest add @aceternity/dotted-glow-background`
- `npx shadcn@latest add @aceternity/encrypted-text`
- `npx shadcn@latest add @aceternity/images-badge`
- `npx shadcn@latest add @aceternity/compare @aceternity/sparkles`
- `npx shadcn@latest add @aceternity/cover`
- `npx shadcn@latest add @aceternity/floating-dock`
- `npx shadcn@latest add @aceternity/loader`
- `npx shadcn@latest add @aceternity/tracing-beam`
- `npx shadcn@latest add @aceternity/animated-tooltip`
- `npx shadcn@latest add @aceternity/flip-words`
- `npx shadcn@latest add @aceternity/infinite-moving-cards`
- `npx shadcn@latest add @aceternity/placeholders-and-vanish-input`
- `npx shadcn@latest add @aceternity/sidebar`
- `npx shadcn@latest add @aceternity/text-generate-effect`
- `npx shadcn@latest add @aceternity/multi-step-loader`

Для вашего текущего проекта рекомендовано:
- не подключать runtime React-зависимости на всех страницах DTF,
- брать компонент как reference и портировать в ваш vanilla-effect слой (как уже сделано по части эффектов).

---

## 10) 100 идей внедрения по `dtf.twocomms.shop`

Ниже список из 100 конкретных идей, включая ваши обязательные сценарии.

1. **Global/Header**: `Tooltip Card` на языковых переключателях с пояснением локали/контента.
2. **Global/Header**: `Animated Tooltip` на пункте “Допомога” с подсказкой “файл не пройдет preflight?”.
3. **Global/Header**: `Text Generate Effect` в коротком слогане при первом визите.
4. **Global/Header**: `Encrypted Text` для статуса secure-upload в хедере конструктора.
5. **Global/Footer**: `Infinite Moving Cards` с trust-фактами (с SEO-safe markup).
6. **Global/Footer**: `Pointer Highlight` на критичных ссылках “Контакти/Умови/Повернення”.
7. **Global/CTA**: `Stateful Button` для всех primary submit.
8. **Global/Nav**: единый `Floating Dock` вместо FAB+dock дубля.
9. **Global/Nav**: mobile dock с активной секцией + мягким glow (без лишних эффектов).
10. **Global/Error pages**: `Cover` для 404/500 headline.

11. **Home/Hero**: оставить `Flip Words` только на 1 строке оффера.
12. **Home/Hero**: `Text Generate Effect` для “відправка день в день” (ваш speed-сценарий).
13. **Home/Hero**: `Dotted Glow Background` с уменьшенной интенсивностью на mobile.
14. **Home/Hero**: `Sparkles` только на бейдже Hot Peel.
15. **Home/Hero**: `Encrypted Text` для preflight-line (“verified before print”).
16. **Home/Hero**: `Cover` на вторичной строке при hover CTA.
17. **Home/Quick calc**: `Stateful Button` на кнопке “Далі”.
18. **Home/Quick calc**: `Vanish Input` на поле метров при invalid.
19. **Home/How it works**: `Tracing Beam` для вертикальной последовательности шагов.
20. **Home/How it works**: `Animated Tooltip` на терминах “preflight/hot peel”.
21. **Home/Works**: `Compare` карточка “до/после” (уже есть, усилить автопревью).
22. **Home/Works**: `Images Badge` над кейсами: “новий”, “топ”, “для чорної тканини”.
23. **Home/Works**: `Cards on click` для расширенного паспорта кейса.
24. **Home/Works**: `Tooltip Card` с параметрами материала/тиража.
25. **Home/Knowledge preview**: SEO-safe `Infinite Moving Cards` из свежих постов.
26. **Home/Knowledge preview**: `Stateful Link` на “читати окремо”.
27. **Home/Requirements teaser**: `Pointer Highlight` на ключевых требованиях.
28. **Home/Delivery teaser**: `Text Generate Effect` для SLA блока.
29. **Home/FAQ**: `Animated Tooltip` на “є білий шар?” с мини-иллюстрацией.
30. **Home/Final CTA**: `Floating Dock` авто-скрытие рядом с футером.

31. **Order/Upload zone**: `Images Badge` на загруженном файле (ваш обязательный сценарий).
32. **Order/Upload zone**: анимация badge на desktop hover (ваш обязательный сценарий).
33. **Order/Upload zone**: `Multi Step Loader` с реальными этапами preflight (ваш обязательный сценарий).
34. **Order/Upload zone**: шаг “тонкие линии” как отдельный статус (ваш обязательный сценарий).
35. **Order/Upload zone**: шаг “ширина 60 см” как отдельный статус (ваш обязательный сценарий).
36. **Order/Upload zone**: шаг “границы макета” как отдельный статус (ваш обязательный сценарий).
37. **Order/Upload zone**: шаг “DPI” как отдельный статус (ваш обязательный сценарий).
38. **Order/Upload zone**: шаг “прозрачность/подложка” как отдельный статус.
39. **Order/Upload zone**: `Tooltip Card` на каждом статусе проверки с расшифровкой.
40. **Order/Preview**: `Compare` режим “превью с/без underbase”.
41. **Order/Preview**: второй режим compare — auto-sweep 2 цикла, потом ручной.
42. **Order/Preflight terminal**: `Text Generate Effect` для вывода подсказок.
43. **Order/Preflight terminal**: `Encrypted Text` в строке checksum/верификации.
44. **Order/Fields**: `Placeholders and Vanish Input` c очисткой invalid (ваш обязательный сценарий).
45. **Order/Fields**: `Animated Tooltip` на поле “Копії”.
46. **Order/Fields**: `Animated Tooltip` на “Відділення НП”.
47. **Order/Summary**: `Stateful Button` + optimistic state submit.
48. **Order/Summary**: `Text Generate Effect` для “відповімо протягом робочого дня”.
49. **Order/Page**: полностью скрывать FAB и floating dock, оставлять только нужный mobile dock.
50. **Order/Page**: `Floating Dock` в desktop-версии только после скролла 40%.

51. **Constructor/Landing**: `Dotted Glow` + `Cover` на заголовке “MVP”.
52. **Constructor/Landing**: `Tooltip Card` на этапах “виріб/друк/доставка”.
53. **Constructor/App left sidebar**: внедрить `Sidebar` компонент для шагов (ваш пример про dashboard).
54. **Constructor/App**: `Floating Dock` как action-panel конструктора (Upload/Layers/Preview/Submit).
55. **Constructor/App**: пункт dock “Upload” с `Images Badge` (ваш обязательный сценарий).
56. **Constructor/App**: dock hover-анимации на desktop, статично на mobile.
57. **Constructor/App**: `Multi Step Loader` в preflight-карте с backend этапами.
58. **Constructor/App**: `Text Generate Effect` для пояснения ошибок preflight.
59. **Constructor/App**: `Animated Tooltip` у поля size breakdown.
60. **Constructor/App**: `Animated Tooltip` у placement.
61. **Constructor/App**: `Vanish Input` + clear для телефона (как вы хотите).
62. **Constructor/App**: `Stateful Button` на “Зберегти чернетку”.
63. **Constructor/App**: `Stateful Button` на “Надіслати запит”.
64. **Constructor/App**: `Compare` для “до/после коррекции макета”.
65. **Constructor/App**: `Tooltip Card` с “почему WARN не блокирует заказ”.
66. **Constructor/App**: `Tracing Beam` для текущего шага в правой колонке.
67. **Constructor/App**: `Encrypted Text` для session checksum.
68. **Constructor/App**: `Images Badge` на saved preview (“saved”, “needs review”).
69. **Constructor/App**: `Cards on click` для выбора типовых заготовок.
70. **Constructor/App**: `Flip Words` только в heading блока прогресса.

71. **Status/Form**: `Placeholders and Vanish Input` с очисткой invalid order number.
72. **Status/Form**: `Stateful Button` на “Перевірити”.
73. **Status/Pipeline**: `Tracing Beam` для длинного таймлайна этапов.
74. **Status/Pipeline**: `Animated Tooltip` на каждом статус-иконе.
75. **Status/Timeline**: `Text Generate Effect` на “що перевірено”.
76. **Status/Delivery**: `Stateful Button` на копировании tracking link.
77. **Requirements/Hero**: `Cover` на заголовке “Вимоги до файлів”.
78. **Requirements/List**: `Pointer Highlight` на “60 см”, “300 DPI”, “Прозорий фон”.
79. **Requirements/List**: `Tooltip Card` с примерами bad/good файла.
80. **Requirements/Examples**: `Compare` “OK vs RISK” интерактивный.
81. **Templates/Page**: `Tabs Download` + `Stateful Button` на download.
82. **Templates/Page**: `Encrypted Text` для checksum у шаблонов.

83. **Gallery/Grid**: `Cards on click` для детального кейса (уже есть, расширить метаданными).
84. **Gallery/Grid**: `Images Badge` на кейсах: “спорт”, “мерч”, “дрібний текст”.
85. **Gallery/Compare**: dual-mode compare (manual + auto-sweep).
86. **Gallery/Compare**: `Animated Tooltip` на ползунке compare (“drag to inspect”).
87. **Gallery/Lens**: `Text Generate Effect` в подписи “макро-деталь”.
88. **Gallery/CTA**: `Stateful Link` на “Зробити як тут”.
89. **Blog/List**: SEO-safe `Infinite Moving Cards` с постами/тегами (ваш обязательный сценарий).
90. **Blog/List**: `Tracing Beam` (уже есть) + lazy-threshold tuning.
91. **Blog/List**: `Tooltip Card` в карточке поста с mini-summary.
92. **Blog/Post**: `Text Generate Effect` для ключевого абзаца “суть за 10 секунд”.
93. **Blog/Post**: `Animated Tooltip` на технических терминах.
94. **Blog/Post**: `Stateful Link` на CTA в заказ.

95. **Quality/Page**: `Compare` по результатам теста стирки “до/после циклов”.
96. **Quality/Page**: `Images Badge` на фото QC (“підкладка”, “край”, “порошок”).
97. **Sample/Page**: `Stateful Button` + `Vanish Input` на контактах.
98. **Price/Page**: `Tooltip Card` на “базова/знижка” с реальными примерами.
99. **Cabinet/Home**: `Sidebar` для секций кабинета + `Floating Dock` быстрых действий.
100. **Cabinet/Sessions**: `Multi Step Loader` на прогрессах сессий конструктора.

---

## 11) Внедряемость в сайт: насколько это просто

Оценка по проекту в целом:

- **Просто (1-2 дня):** tooltip, pointer highlight, stateful кнопки, text generate, vanish-input (база).
- **Средне (3-5 дней):** images badge, improved compare (dual mode), SEO-safe infinite cards, tracing beam tuning.
- **Сложнее (5-10 дней):** sidebar в constructor/cabinet, глубокий multi-step preflight с real backend этапами.

Итог: внедряемость высокая, потому что архитектурная база уже есть.

---

## 12) Рекомендуемый roadmap (чтобы получить лучший результат)

## Sprint 1 (обязательное из вашего ТЗ)

1. Устранить конфликт FAB/dock/mobile dock.
2. Доработать `vanish-input` до режима “ошибка -> очистка + эффект”.
3. Сделать `multi-step preflight` с реальными шагами проверки.
4. Внедрить `images badge` в upload-конструктор.
5. Запустить SEO-safe `infinite cards` в блоге.

## Sprint 2 (усиление wow + конверсии)

1. Compare dual-mode (manual + auto-sweep).
2. Speed text effect в hero/order CTA.
3. Tooltip cards в price/requirements/status.
4. Кабинет/конструктор: sidebar + action dock.

## Sprint 3 (чистка и стабилизация)

1. Удалить legacy-дубли в `dtf.js`.
2. Довести единый naming и init-contract для всех эффектов.
3. Добавить A/B-флаги для heavy эффектов и сверить по метрикам.

---

## 13) Что важно зафиксировать перед реализацией

1. Вы хотите максимально “живой” интерфейс, но для коммерческого DTF-сайта критичнее конверсия и ясность шага заказа.
2. Поэтому ключевое правило: эффект должен повышать доверие/понятность, а не просто “двигаться”.
3. Самая большая ценность у вас — это preflight, контроль качества и прозрачность процесса. Эффекты должны обслуживать именно это.

---

## 14) Финальный вывод

- Ваша текущая база уже достаточно зрелая, чтобы сделать очень сильный визуальный продукт без перехода на React-стек целиком.
- Главный фокус сейчас: убрать конфликт правого нижнего UI, реализовать ваш сценарий preflight-loader + vanish clear + SEO-safe infinite cards + dock для конструктора с image badge.
- После этого проект будет выглядеть заметно “дороже” и при этом останется быстрым, индексируемым и поддерживаемым.

