---
title: "TwoComms Custom Configurator — final doctrine v7.1"
subtitle: "Final handoff doctrine before wireflow / implementation brief — reinforced after final audit"
author: "Synthesized from internal research, critique cycles, and external verification"
date: "13 April 2026 — v7.1"
lang: ru-RU
mainfont: DejaVu Serif
sansfont: DejaVu Sans
monofont: DejaVu Sans Mono
fontsize: 11pt
geometry: margin=1in
colorlinks: false
header-includes:
  - |
    \usepackage{fancyhdr}
    \pagestyle{fancy}
    \fancyhf{}
    \fancyfoot[C]{\thepage}
    \fancyhead[L]{TwoComms Configurator v7.1}
    \setlength{\headheight}{14pt}
  - |
    \usepackage{longtable}
    \usepackage{booktabs}
    \usepackage{array}
    \usepackage{enumitem}
    \setlist{nosep}
---

# Что это за документ

Это финальная **doctrine-level спецификация** перед wireflow и implementation brief.

Она отвечает на четыре вопроса:

1. Что в v1 обязательно сделать.
2. Как это должно работать на уровне UX, визуала и инженерных контрактов.
3. Что считать гипотезой, а не законом.
4. Что не раздувать в реализации.

Это **не** код, не pixel-perfect макет и не полный QA-runbook.
Но это уже достаточно плотный handoff-документ для агента, у которого есть доступ к проекту и который понимает ваш стек.

# Как использовать документ

В документе используются пометки уверенности:

- **[A]** — стандарт, platform requirement или почти обязательный engineering guardrail.
- **[B]** — сильный UX-паттерн или практика, которая хорошо подходит проекту.
- **[C]** — продуктовая гипотеза или controlled enhancement, которую не надо трактовать как закон.

Правило простое:

- [A] внедряется без творческого переизобретения.
- [B] внедряется как базовое решение, если нет жёсткого конфликта с реальным проектом.
- [C] внедряется только если не утяжеляет v1 и не ломает общую архитектуру.

# Что было усилено в v7 и что сознательно не вошло

## Что вошло

- **Value & Trust layer** как обязательный слой v1. [B]
- **Safe exit data contract + persistence strategy** вместо расплывчатого обещания “не потерять прогресс”. [A]
- **Rendering contract for Product Stage** с рекомендуемым v1-пайплайном, а не с тремя равновесными трактовками. [A]
- **Breakpoint values, baseline mechanics, launch matrix и red-flag playbook**. [B]
- **Tone of voice rules** для конфигуратора. [B]
- **Build Strip examples и component interaction notes** для клавиатуры / screen readers. [B]
- **Choice architecture rules** вместо расплывчатых рассуждений про “перегруз”. [B]
- **Analytics event schema** и baseline capture. [A]
- **Safe exit к менеджеру** как отдельный механический контракт, а не просто обещание. [B]
- **State maps** для Product Stage, Build Strip и Price Capsule. [B]
- **Responsive ASCII-схемы** для phone, landscape, tablet, desktop. [B]
- **Error states и submission failure** как обязательная часть flow. [A]
- **Более точный File Triage** с явными эвристиками для screenshot/reference cases. [A]

## Что не вошло в ядро

- Псевдоточные нейроцифры вроде “+29% мотивации”, “+18% completion”, “+80% brand recall”. Они звучат эффектно, но для этого проекта не дают надёжного проектного выигрыша. [C]
- Агрессивные social-proof / FOMO / scarcity-приёмы. Для TwoComms это риск подорвать доверие. [C]
- Полноценный i18n / RTL scope для v1. Добавлены только future-safe guardrails. [C]
- Полный implementation-level spec с кодом всех состояний. Следующий артефакт после этого документа — wireflow / implementation brief. [B]
- Общие утверждения в духе “украинцы всегда реагируют так-то” или точные проценты uplift без вашей валидации. Это остаётся hypothesis territory, а не doctrine law. [C]

# 1. North star продукта

TwoComms нужен **guided custom-flow**, который ощущается как сборка вещи, а не как бюрократическая форма.

## 1.1 Что пользователь должен чувствовать

- контроль,
- визуальную предметность,
- понятный прогресс,
- низкий риск ошибки,
- прозрачную стоимость,
- возможность быстро перейти к живому человеку без потери уже сделанного.

## 1.2 Что пользователь не должен чувствовать

- что его посадили в мини-Photoshop,
- что ему сразу продают что-то сложное и дорогое,
- что цена “орёт” сильнее самой вещи,
- что он заполняет длинную производственную анкету,
- что B2C, B2B, подарок, логистика и дизайн-помощь перемешаны в один комок.

## 1.3 Итоговая структура v1

1. Hero / вход
2. Quick start / выбор пути
3. Выбор изделия
4. Core hoodie flow
5. Файлы / reference / помощь с дизайном
6. Контакты / доставка / review
7. Submit или safe exit к менеджеру

# 2. Визуальный принцип: это должен быть TwoComms

## 2.1 Базовое правило [A]

Конфигуратор должен выглядеть как **естественное продолжение текущего сайта TwoComms**, а не как чужой UI-kit, Android-demo или generic SaaS-панель.

## 2.2 Что сохраняем [B]

- фирменную атмосферу,
- цветовую палитру,
- характер типографики,
- базовую плотность и настроение интерфейса,
- ощущение street / custom / premium utility.

## 2.3 Что улучшаем [B]

- иерархию,
- spacing,
- состояния controls,
- responsive-поведение,
- логику CTA,
- читаемость сложных шагов,
- дисциплину summary и review.

## 2.4 Что не делаем [A]

- не копируем Material визуально;
- не строим конфигуратор как dashboard;
- не делаем “совсем новый дизайн” без связи с сайтом;
- не уходим в glossy-tech эстетику, если она ломает тон бренда.

## 2.5 Practical token pass для внедряющего агента [B]

Перед wireflow / макетированием:

1. Снять с текущего сайта токены: шрифты, размеры, веса, radius, spacing rhythm, состояния кнопок, ссылки, формы.
2. Выделить, какие элементы реально фирменные и узнаваемые.
3. Строить конфигуратор из этих токенов и их расширений, а не из нового визуального словаря.

## 2.6 Цвет и семантика — без псевдопсихологии [B]

Используйте семантику цвета утилитарно, а не как “нейромагию”:

- success / completed state — согласованный зелёный или иной уже принятый в системе success-color;
- error / destructive — читаемый error-color;
- warning / needs-work — warning-color;
- primary CTA — тот цвет, который уже работает в TwoComms как главный action-color;
- secondary actions — облегчённые по весу, но не спрятанные.

Никаких обязательных правил типа “только зелёный CTA” или “красный нельзя никогда” — это должно подчиняться реальному бренду и контрасту, а не общим мифам. [C]

## 2.7 Tone of voice для конфигуратора [B]

Конфигуратор должен говорить с человеком в том же характере, что и TwoComms, но чуть яснее и тише, чем маркетинговая витрина.

Правила:

- короткие фразы вместо канцелярита;
- уважительный, уверенный тон без заискивания;
- технические пояснения — человеческим языком;
- не смешивать в одном экране официальный и разговорный регистр;
- если интерфейс на украинском — держать его украинским целиком, без случайных русских вкраплений.

Практический ориентир:

- labels и helper text — нейтральные и короткие;
- error copy — конкретный, спокойный, без обвиняющего тона;
- trust / review copy — уверенный, объясняющий, без пафоса;
- менеджерский safe-exit copy — дружелюбный, но не жалобный.

Нужно выбрать один адрес обращения для v1 — на “ви” или на “ти” — и не прыгать между ними. Если текущий сайт уже последовательно говорит на “ви”, конфигуратор не должен внезапно уходить в “ти”. [A]

# 3. Entry Flow и Quick Start

## 3.1 Entry architecture [B]

Вход двухуровневый:

- **Hero:** “Создать свой дизайн” + secondary action “Связаться с менеджером”.
- После primary CTA — лёгкий режимный слой:
  - Для себя
  - Для команды / бренда

Подарочный сценарий **не** живёт отдельной стартовой веткой v1. Он включается как дополнительная опция ближе к review. [B]

## 3.2 Цель Quick Start [B]

Не дать человеку застрять в пустом макете и при этом не перегрузить его тремя равновесными сценариями.

## 3.3 Финальный состав Quick Start [B]

**Primary path**
- Начать с нуля / собрать самому

**Secondary paths**
- У меня есть файл
- Показать стартовые стили

## 3.4 Что такое “стартовые стили” [A]

Чтобы не было дыры в handoff, фиксируем:

**Стартовые стили** — это не шаблонная библиотека и не каталог готовых принтов.
Это **3 кураторских стартовых направления** с мини-превью и одним предложением-пояснением.

Пример для v1:
- Minimal — чистый, спокойный старт
- Bold — крупнее и заметнее
- Logo-first — фокус на символе / надписи

Они нужны как стартовая опора, а не как отдельный магазин шаблонов.

## 3.5 Визуальная иерархия Quick Start [A]

```text
┌──────────────────────────────────────────────┐
│ Что хотите сделать дальше?                   │
│                                              │
│ [████████████████████████████████████████]   │
│ [      Начать с нуля / собрать самому      ] │  ← Primary CTA
│ [████████████████████████████████████████]   │
│                                              │
│ Уже есть макет или нужен быстрый старт?      │
│ [ У меня есть файл ]   [ Показать стили ]    │  ← Secondary
└──────────────────────────────────────────────┘
```

## 3.6 Quick Start validation checks [B]

Перед утверждением дизайна или интерактива проверить:

1. Видно ли primary CTA сразу.
2. Видно ли, что upload path существует.
3. Не выглядят ли все три действия как равновесные конкуренты.
4. Нет ли вопроса “а где загрузить файл, если он уже есть?”.
5. Нет ли ступора дольше 8–10 секунд без действия.

Число 8–10 секунд — не стандарт, а практический heuristic marker для moderated usability. [C]

## 3.7 Decision tree для QA / UX review [B]

```text
Пользователь попал в Quick Start
│
├─ Видит primary CTA за 2 секунды?
│   ├─ Да → дальше
│   └─ Нет → иерархия сломана
│
├─ Видит secondary actions без поиска?
│   ├─ Да → дальше
│   └─ Нет → discoverability fail
│
├─ Понимает, что "У меня есть файл" — рабочий путь?
│   ├─ Да → дальше
│   └─ Нет → переписать copy / иерархию
│
└─ Не задаёт вопрос "где здесь начать?"
    ├─ Да → Quick Start ок
    └─ Нет → шаг требует переработки
```

## 3.8 Что сознательно не делаем [A]

- auto-start;
- mandatory quiz;
- скрытый upload path;
- 5–6 стартовых стилей прямо в Quick Start;
- отдельную gift-ветку здесь;
- дополнительную “commitment modal” после primary CTA.

# 4. Choice architecture rules

Это новый обязательный раздел, потому что именно тут раньше было много абстракции.

## 4.1 Базовое правило [B]

На одном экране пользователь не должен принимать слишком много **однородных** решений сразу.

## 4.2 Практический лимит видимых опций [B]

Это не “закон природы”, а рабочий guardrail для v1:

- mobile: **3–6 видимых опций** в первом экране шага;
- desktop/tablet: **4–8 видимых опций**;
- всё, что сверх этого, должно уходить в show more, фильтрацию, вторичный слой или менеджерский path.

Причина не в том, что “больше 7 всегда ломает конверсию”, а в том, что эффект choice overload контекстный и сильно зависит от понятности выбора. Поэтому используем лимит как проектную дисциплину, а не как псевдонаучный догмат. [B]

## 4.3 Transparent recommendation [B]

Допустимо использовать метку:

- “Рекомендуем”
- “Популярный баланс”
- “Подходит большинству”

Но **не** допускаются скрытые платные дефолты. [A]


### 4.3.1 Порядок показа опций [B]

Если шаг содержит несколько вариантов одного типа, порядок по умолчанию должен быть предсказуемым:

1. рекомендованный / самый понятный вариант;
2. ещё 1-2 массово релевантных варианта;
3. всё длиннохвостое — в `show more`, secondary sheet или к менеджеру.

Не сортировать “подороже сначала” только ради апсейла. Если вариант помечен как recommended, это должно быть честно объяснимо ценностью или частотой выбора, а не скрытым revenue-priority. [A]

## 4.4 Good / Better / Best [C]

Этот паттерн допустим только там, где он реально упрощает сложное решение, а не плодит коммерческую театральность.

Для v1 он уместен максимум в 1–2 местах:

- ткань;
- тип помощи с дизайном / подготовкой файла.

Не надо раскладывать так весь конфигуратор.

## 4.5 “Показать ещё” vs “вынести к менеджеру” [B]

Если редкие варианты не нужны большинству, то безопаснее:

- показать 2–3 главных варианта в интерфейсе;
- ещё редкие cases перевести в “уточнить с менеджером” или “расширенные варианты”.

# 5. Core hoodie flow

## 5.1 Последовательность v1 [B]

1. Крой
2. Ткань
3. Цвет
4. Опции / комфорт / детали
5. Размер
6. Зона и формат нанесения
7. Файл / reference / помощь с дизайном
8. Контакты / доставка / review

## 5.2 Почему так [B]

Это не доказанный психологический закон, а сильная продуктовая гипотеза, основанная на общей UX-логике:

- сначала пользователь собирает визуальный образ вещи;
- потом подтверждает функциональные параметры;
- затем переходит к наиболее технически рискованному шагу — artwork path;
- финал остаётся коротким и утилитарным.

## 5.3 Почему colour-before-size сохраняется [C]

- Цвет даёт быстрый и понятный отклик на Product Stage.
- Размер чаще вызывает более рациональный контроль и сомнения.
- Смешивание этих решений утяжеляет сцену.

Это решение должно проверяться по step-time, drop-off и moderated tests, а не восприниматься как вечная истина.

## 5.4 Размер и цена [B]

Используем:

> **Одна цена для всех размеров XS–2XL**

или

> **В этой сетке все размеры по одной цене**

Если у бренда есть короткое честное объяснение, можно добавить tooltip:

> “В этой модели цена не меняется от XS до 2XL”.

Не используем сухое и потенциально недоверительное “размер не влияет на цену”.

## 5.5 Что такое шаг “Опции / комфорт / детали” [A]

Чтобы не было расплывчатости, для v1 под этим понимаются только:

- люверсы / шнурки,
- флис / без флиса (если реально доступно),
- принт на рукаве,
- дополнительные простые finishing choices, если они уже поддерживаются продуктом.

В этот шаг **не** надо тащить редкие производственные случаи и B2B-спецлогику.

## 5.6 Gift option [C]

Если включается в v1, то только на review:

- подарочная упаковка,
- короткая записка,
- safe copy про подарок.

Не отдельная стартовая ветка.

# 6. Product Stage, Build Strip, Price Capsule

Это ядро конфигуратора. Здесь в v5 было слишком много хороших принципов и слишком мало state contracts. В v6 это исправлено.

## 6.1 Product Stage — что это [A]

Product Stage — главный визуальный контейнер конфигуратора.
Он всегда показывает **текущую вещь**, а не декоративный hero-shot.

## 6.2 Product Stage — state map [A]

```text
STATE 0: base garment
- выбран базовый силуэт
- без активной подсветки зон

STATE 1: visual configuration
- цвет / ткань / крой отражены
- stage обновляется без перезагрузки сцены

STATE 2: print placement mode
- активная сторона (front/back/sleeve)
- подсветка допустимой зоны
- примерный контур масштаба нанесения

STATE 3: review-ready
- stage показывает итоговую конфигурацию
- без лишних служебных подсказок
```

## 6.3 Product Stage — rendering contract [A]

Чтобы не было дорогого додумывания на этапе реализации, для v1 фиксируем **предпочтительный рендер-пайплайн**:

1. **Base renders / prepared assets** для силуэта и ключевых сторон (front/back, при необходимости sleeve-view).
2. **Цветовая вариативность** решается либо заранее подготовленными вариантами, либо проверенной системой recolor, если она уже существует в проекте и даёт приемлемую точность.
3. **Print placement mode** строится поверх базового превью через координатные зоны и overlay-контуры, а не через отдельный рендер на каждую комбинацию масштаба.
4. **Review-ready state** использует тот же источник превью, без отдельной “магической” версии.

Для v1 **не закладывать** full 3D, свободное drag-and-drop размещение или физически точную симуляцию ткани. [A]

Минимальный scope, который должен быть явно определён до wireflow:

- какие силуэты реально входят в v1;
- сколько цветовых вариантов входят в v1;
- какие стороны preview обязаны существовать;
- как задаются координаты допустимых print-зон для каждого силуэта.

Недопустимо обещать “preview в реальном времени”, если под этим скрывается ненадёжный CSS-фильтр, который в реальности искажает вещь. [A]

## 6.4 Build Strip — что это [A]

Build Strip — живая, но компактная линия уже принятых решений.
Он не должен быть тяжёлым степпером и не должен оттягивать внимание от вещи.

## 6.5 Build Strip — state map [A]

```text
EMPTY
- виден как лёгкий контейнер или скрыт до первого значимого выбора

PARTIAL
- показывает уже сделанные ключевые выборы
- допускает возврат на соответствующий шаг

FULL
- показывает основные выбранные параметры перед review
- второстепенные детали могут быть свернуты в "ещё"
```

Каждый элемент Build Strip должен иметь минимум два состояния:
- selected / current;
- editable history item.


### 6.5.1 Build Strip — минимальные примеры [B]

**Phone portrait**

```text
[✓ Крой] [✓ Ткань] [→ Цвет] [+ ещё 4]
```

или, если места мало:

```text
[✓ Regular fit] [✓ Cotton] [→ Выбрать цвет] [Ещё 4]
```

**Desktop / tablet landscape**

```text
[✓ Regular] [✓ Cotton] [✓ Black] [→ Chest print] [○ Artwork] [○ Review]
```

Правило: Build Strip показывает только ключевые решения. Второстепенные детали не должны раздувать его в каталог чипов. [A]

## 6.6 Что Build Strip не делает [A]

- не копирует product summary целиком;
- не заменяет review;
- не превращается в второй навигационный хаб с десятком чипов;
- не требует горизонтального скролла на обычном phone portrait, пока это можно избежать.

## 6.7 Price Capsule — что это [A]

Цена и главный CTA живут в компактной капсуле:
- всегда рядом,
- всегда доступны,
- не доминируют над Product Stage.

## 6.8 Price Capsule — state map [A]

```text
COLLAPSED
- показывает итог / from-price / CTA
- минимально мешает контенту

EXPANDED
- раскрывает breakdown только по намерению пользователя
- показывает цену, допы, delivery note, если уместно

SUBMIT-READY
- на review становится самым понятным местом действия
```

## 6.9 Цена — не бухгалтерский блок [B]

Не делаем sticky sidebar-чек, который визуально равен главному контенту.
Price Capsule должна ощущаться как часть инструмента, а не как навязанный кассовый аппарат.

# 7. File Triage — финальная инженерная спецификация v1

## 7.1 Главный принцип [A]

Файловый шаг — это **маршрутизация**, а не запрет.

Результат этого шага всегда должен быть один из трёх:
- файл годится;
- файл можно использовать, но лучше доработать;
- файл лучше использовать как reference.

## 7.2 Effective resolution [A]

```text
effective_ppi = min(
  image_width_px  / (print_area_width_cm  / 2.54),
  image_height_px / (print_area_height_cm / 2.54)
)
```

Смысл: система оценивает качество относительно **выбранной зоны печати**, а не по голому DPI файла.

## 7.3 Общие статусы [A]

- `print-ready`
- `needs-work`
- `reference-only`

## 7.4 Классификация v1 [B]

- **print-ready:** effective PPI примерно 250+ или файл в формате, пригодном для дальнейшей подготовки;
- **needs-work:** примерно 150–249 PPI;
- **reference-only:** ниже 150 PPI, либо файл выглядит как reference / screenshot / найденная картинка.

Причина именно такой логики: в POD/DTG практике 300 DPI часто рекомендуются как идеал, но реальные продуктовые гайды допускают и более низкие значения в зависимости от носителя и площади печати. Поэтому v1 опирается на контекстный effective resolution, а не на фразу “только 300 DPI”. [A]

## 7.5 Псевдокод-контракт [A]

```python
def classify_artwork(
    image_width_px: int,
    image_height_px: int,
    print_area_width_cm: float,
    print_area_height_cm: float,
    mime_type: str,
    screenshot_suspected: bool,
    vector_like: bool = False,
) -> dict:
    if vector_like and mime_type in {"image/svg+xml", "application/pdf"}:
        return {
            "status": "print-ready",
            "effective_ppi": None,
            "next_actions": ["continue", "replace"]
        }

    width_in = print_area_width_cm / 2.54
    height_in = print_area_height_cm / 2.54
    ppi_w = image_width_px / width_in
    ppi_h = image_height_px / height_in
    effective_ppi = min(ppi_w, ppi_h)

    if screenshot_suspected:
        return {
            "status": "reference-only",
            "effective_ppi": round(effective_ppi),
            "next_actions": ["use_as_reference", "replace"]
        }

    if effective_ppi >= 250:
        return {
            "status": "print-ready",
            "effective_ppi": round(effective_ppi),
            "next_actions": ["continue", "replace"]
        }

    if effective_ppi >= 150:
        return {
            "status": "needs-work",
            "effective_ppi": round(effective_ppi),
            "next_actions": ["continue_anyway", "request_fix", "replace"]
        }

    return {
        "status": "reference-only",
        "effective_ppi": round(effective_ppi),
        "next_actions": ["use_as_reference", "replace"]
    }
```

## 7.6 Как определять screenshot_suspected и vector_like [A]

Эти флаги в v5 были недоопределены. В v6 фиксируем минимальную практическую логику:

### screenshot_suspected
Эвристика, а не абсолютная истина. Флаг может подниматься, если совпадает несколько признаков:

- соотношение сторон похоже на screen capture;
- очень низкое effective resolution для выбранной зоны;
- у изображения есть визуальные поля/рамки/UI-элементы;
- источник — clipboard / direct photo screenshot path;
- формат и метаданные типичны для screen export.

Если уверенность низкая, не надо жёстко маркировать как screenshot. Лучше склоняться в `needs-work`. [A]

### vector_like
Флаг ставится только при достаточно надёжных признаках:

- MIME / extension: SVG или PDF;
- система смогла открыть документ без raster-fallback как единое изображение;
- файл не является просто обёрнутым скриншотом в PDF.

Если есть сомнение, не обещать “vector-safe”, а передавать как `needs-review` менеджеру или production path. [A]

## 7.7 Форматы v1 [B]

Практически допустимы:
- JPG / JPEG,
- PNG,
- WebP,
- PDF.

Advanced only if pipeline already supports:
- SVG,
- PSD,
- AI / EPS.

Не обещаем full parsing сложных исходников, если проект этого реально не держит. [A]

## 7.8 UI-сообщения [A]

**Print-ready**
```text
OK - Файл подходит для выбранной зоны
2480×3508 px • A4 • ~300 PPI
[Продолжить] [Заменить]
```

**Needs-work**
```text
WARN - Файл можно использовать, но качество на грани
2000×3000 px • A4 • ~242 PPI
[Продолжить с этим файлом] [Заказать доработку] [Заменить]
```

**Reference-only**
```text
NO - Для выбранной зоны файл слишком слабый
800×1200 px • A4 • ~97 PPI
[Использовать как reference] [Заменить файл]
```

## 7.9 Файл после upload [A]

- статус triage должен сохраняться в заявке;
- менеджер должен видеть и исходный файл, и triage-status, и выбранную зону печати;
- triage не должен “поглощать” файл без следа;
- при падении triage-сервиса заявка всё равно должна уходить в safe manual review.

# 8. Motion system

## 8.1 Motion нужен для трёх вещей [A]

- feedback,
- ориентация,
- подтверждение изменения состояния.

Не для шоу.

## 8.2 Motion tokens [A]

```css
--tc-motion-instant: 80ms linear;
--tc-motion-fast: 150ms cubic-bezier(0.4, 0, 0.2, 1);
--tc-motion-enter: 250ms cubic-bezier(0.2, 0, 0, 1);
--tc-motion-exit: 200ms cubic-bezier(0.4, 0, 1, 1);
--tc-motion-large: 280ms cubic-bezier(0.2, 0, 0, 1);
```

## 8.3 Mapping на компоненты [A]

- `instant` — control states, toggle, selected/unselected;
- `fast` — микро-feedback на pills / swatches / small state changes;
- `enter` — step panel reveal, bottom sheet open, inline section expand;
- `exit` — close / collapse / dismiss;
- `large` — только заметные transitions preview или крупного sheet.

## 8.4 Reduced motion [A]

```css
@media (prefers-reduced-motion: reduce) {
  * {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```

## 8.5 Low-end device rule [B]

Если на средних/слабых телефонах motion начинает “заикаться”:

- сокращать длительность;
- убирать декоративные transforms;
- упрощать preview transition;
- не спорить с FPS ради красоты.

Никаких сложных performance-adaptive CSS-детекторов в doctrine фиксировать не нужно — это уже implementation detail. [C]

# 9. Accessibility minimum protocol

## 9.1 Базовый стандарт [A]

Ориентир для v1 — **WCAG 2.2 AA**.

## 9.2 Обязательные требования [A]

- минимум по Target Size соблюдён;
- drag never exclusive;
- keyboard проходит основной путь;
- screen reader получает контекст шагов, статусов и ошибок;
- цвет не единственный носитель смысла;
- reduced motion respected.

## 9.3 Target sizes [A]

- **минимум по стандарту:** 24×24 CSS px;
- **практический комфортный ориентир для важных touch targets:** 44–48 px / pt / dp.

Для конфигуратора TwoComms ориентироваться надо не на “минимум, лишь бы пройти”, а на удобное касание. [B]

## 9.4 Keyboard walkthrough [A]

Минимальный сценарий:

Quick Start → выбор пути → изделие → хотя бы один выбор в core flow → artwork step → review → submit / safe exit.

Проверить:

- tab order логичен;
- focus виден;
- enter / space работают;
- escape закрывает overlays;
- нет keyboard trap;
- overlays не съедают фокус навсегда.


### 9.4.1 Component-level keyboard rules [B]

- **Product Stage**: если это только визуальный контейнер без прямых действий, он не обязан быть в tab-order; если содержит action controls, они должны фокусироваться отдельно.
- **Build Strip items**: editable элементы должны быть достижимы с клавиатуры и возвращать пользователя на соответствующий шаг.
- **Price Capsule**: collapsed/expanded состояние открывается по Enter / Space, закрывается по Escape.
- **Swatches / size pills / option chips**: если они реализованы как кастомные controls, им нужны role, name и понятный focus state.

## 9.5 Screen reader smoke test — minimum matrix [B]

**Обязательно для v1:**
- VoiceOver + Safari (macOS/iOS)
- NVDA + Firefox или Chrome (Windows)
- TalkBack + Chrome (Android)

**Желательно, если доступно:**
- JAWS + Chrome (Windows)

JAWS полезен, особенно если продукт пойдёт в enterprise-heavy среду, но не должен блокировать запуск v1, если у команды нет доступа к лицензии и инфраструктуре. [C]

## 9.6 Dynamic announcements [A]

В динамическом конфигураторе должны быть предусмотрены aria-live / equivalent announcements минимум для:

- статуса file triage;
- критичных form errors;
- submit failure / success;
- значимых updates в цене;
- контекста шага / review state.

Не надо пытаться озвучивать screen reader-ом каждый косметический микрошаг. Только важное. [B]

# 10. Error states и recovery

## 10.1 Главный принцип [A]

Локальная ошибка не должна сбрасывать весь прогресс пользователя.

## 10.2 File upload errors [A]

Типы ошибок и recovery-path:

- network failure → retry / choose another file;
- file too large → explain limit / replace;
- unsupported format → explain allowed formats / replace;
- triage unavailable → manual review fallback.

## 10.3 Form / configuration errors [A]

Нужны не только правила, но и примеры copy.

**Контакт**
```text
Проверьте номер телефона — кажется, формат неполный.
```

**Количество**
```text
Количество должно быть не меньше 1.
```

**Пустое обязательное поле**
```text
Нам нужен этот параметр, чтобы подготовить заявку.
```

## 10.4 Submission failure — обязательный сценарий [A]

Это один из самых критичных gaps прошлых версий, поэтому в v6 фиксируем:

```text
Не удалось отправить заявку прямо сейчас.
Ваши выбранные параметры сохранены.
[Повторить отправку] [Связаться с менеджером] [Скопировать данные заявки]
```

Обязательные условия:
- прогресс не теряется;
- user понимает, что данные не исчезли;
- есть retry-path;
- есть manager-safe-exit.

## 10.5 Error UX rules [A]

- ошибка рядом с проблемой;
- текст + иконка + цвет, не только цвет;
- ошибка объясняет как исправить;
- для screen reader критичные ошибки должны объявляться.

# 11. Loading states

## 11.1 Общий принцип [B]

Loading должен объяснять ожидание, а не усиливать тревогу.

## 11.2 Initial load [B]

- Product Stage получает skeleton / placeholder;
- LCP-контент должен появиться раньше второстепенных слоёв;
- Build Strip и secondary widgets могут догружаться после основы.

## 11.3 File upload [A]

Если upload идёт заметно дольше мгновенного:

- показать progress;
- дать cancel/retry, если это возможно в пайплайне;
- не маскировать долгую загрузку пустотой.

## 11.4 Price recalculation [B]

- быстрые изменения — без лишнего spinner-theatre;
- если вычисление не мгновенно, нужен компактный pending state;
- нельзя блокировать весь интерфейс из-за пересчёта цены.

# 12. Value & Trust layer

Это новое обязательное усиление v6.

## 12.1 Зачем это нужно [B]

Для кастома главный барьер часто не цена сама по себе, а страх ошибки и неопределённость процесса.

## 12.2 Что должно появиться в review / рядом с финалом [A]

Короткий блок “Что будет дальше”:

1. Мы проверим ваш макет и параметры.
2. Если что-то нужно уточнить, напишем вам до запуска.
3. После подтверждения передадим заказ в производство.

## 12.3 Что ещё допустимо показать [B]

Только если это правда и поддерживается процессом:

- ориентир по срокам;
- доступные каналы связи;
- понятные delivery / payment options;
- короткий сигнал о локальной работе / производстве, если это реально важно бренду и подтверждаемо.


### 12.3.1 Enhancements / апсейл без давления [B]

В v1 допустим только **честный, opt-in апсейл**, который улучшает результат и не ломает основной путь.

Разрешённые точки:

- после выбора ткани / базы;
- после выбора print-zone, если enhancement очевидно улучшает вещь;
- на review, если это ускорение, упаковка или дополнительная помощь.

Правила:

- не больше 1 апсейл-предложения на экран;
- всегда показывать, что именно пользователь получает за доплату;
- никогда не блокировать submit ради апсейла;
- не подсовывать pre-checked платные улучшения. [A]

## 12.4 Что нельзя делать [A]

- fake scarcity;
- выдуманные live-purchase popups;
- фальшивые “осталось 2 места” таймеры;
- обещания, которые операционно не поддерживаются.

# 13. KPI, baseline и analytics schema

## 13.1 Главное правило [A]

Метрики без baseline — декоративны.

## 13.2 Что нужно снять до rollout [A]

Минимум:

- текущий end-to-end conversion / request submission rate;
- desktop vs mobile;
- current manager-escalation rate;
- текущие step-level exits, если они уже как-то трекаются;
- сколько заявок реально доходит до usable manager brief.

## 13.3 Healthy launch logic [B]

После запуска смотреть не на одну цифру, а на комбинацию:

- completion не просел драматически относительно baseline;
- mobile не провалился;
- manager escalation не улетел в потолок;
- submission quality выросла или не обрушилась;
- form / upload errors не съели flow.

## 13.4 Red flags [B]

Повод для срочного разбора:

- completion заметно хуже baseline;
- mobile completion драматически ниже desktop;
- file step массово ломает flow;
- submission failure / retry rate высок;
- пользователи часто уходят через manager-safe-exit из простых кейсов.

## 13.5 Minimum analytics event schema [A]

| Event | Trigger | Required props |
|---|---|---|
| `config_start` | пользователь вошёл в flow | source, device_type |
| `quickstart_path_selected` | выбран путь | path_type |
| `step_view` | открыт шаг | step_name, step_index |
| `step_complete` | шаг завершён | step_name, step_index |
| `option_change` | изменён ключевой параметр | step_name, option_group, value |
| `price_capsule_expand` | раскрыт breakdown | step_name |
| `file_uploaded` | файл загружен | mime_type, size_bucket |
| `file_triage_result` | triage вернул статус | status, effective_ppi_bucket |
| `manager_safe_exit` | выбран выход к менеджеру | from_step, reason_if_known |
| `submit_attempt` | попытка отправки | final_step |
| `submit_success` | заявка отправлена | request_type |
| `submit_fail` | отправка не удалась | fail_type |

Это минимальный schema-set. Дополнительные события можно расширять в implementation brief.

### 13.5.1 Interpretation rules [B]

- **Drop-off по шагу** считать как `step_view` без последующего `step_complete` в разумное окно сессии.
- **Step time** считать как разницу между `step_view` и `step_complete`, а не как суммарное время страницы в аналитике браузера.
- **Submission quality** для v1 оценивать proxy-наборами: triage status, полнота ключевых полей, доля safe-exit, менеджерские пометки по итогам разбора.
- **Manager-safe-exit rate** не трактовать автоматически как провал: для сложных кейсов это нормальный предохранитель, если качество лидов остаётся рабочим.

## 13.6 Experiment plan v1 [B]

Не больше 3–5 гипотез одновременно.

Рекомендуемые кандидаты:

1. Quick Start: current asymmetry vs slightly simplified secondary copy.
2. Price Capsule: степень раскрытия breakdown.
3. Artwork step: wording around `needs-work` vs `reference-only`.
4. Review trust block: наличие / отсутствие “что будет дальше”.

Если трафик недостаточен для статистически внятного A/B, эксперимент переводится в qualitative mode: 5-8 moderated sessions + funnel review + session recordings. [B]

### 13.7 Launch decision matrix [A]

**GO**

- все [A]-требования реализованы;
- safe exit работает и передаёт контекст;
- submission failure не теряет собранные данные;
- mobile путь измерим аналитически;
- accessibility smoke-test пройден;
- performance не вываливается в red zone.

**NO-GO / остановка релиза**

- заявка может потеряться без recovery path;
- file triage ведёт себя как жёсткий reject вместо routing;
- safe exit отсутствует или уходит без контекста;
- mobile flow не проходит end-to-end;
- нет baseline / analytics hooks для оценки релиза.

### 13.8 Red flag playbook [B]

Если после запуска один из red flags срабатывает:

- **completion резко ниже baseline** → сначала исключить технический дефект, потом провести быстрые usability sessions;
- **mobile сильно слабее desktop** → проверить клавиатуру, file picker, sticky CTA, target sizes, layout under keyboard;
- **слишком много `reference-only` / abandon на artwork step** → пересмотреть пороги triage и copy объяснений, а не только “ужесточать качество”;
- **manager-safe-exit слишком высок** → смотреть, где именно люди срываются: на непонимании шага, на цене или на файле.

# 14. Responsive shell

В v5 тут было много таблиц и мало образа. В v7 добавляем ещё и baseline breakpoints, чтобы не было разных трактовок “tablet” и “landscape”.

## 14.0 Breakpoint baseline [A]

Для v1 принять одну систему breakpoints и не смешивать её с другой по ходу проекта.

Рекомендуемый baseline:

- **phone portrait**: `< 640px`
- **phone landscape / small tablet**: `640–767px`
- **tablet portrait**: `768–1023px`
- **tablet landscape / desktop compact**: `1024–1279px`
- **desktop**: `1280px+`

Это не закон платформы, а проектный baseline, чтобы дизайнер, фронтенд и QA говорили об одном и том же. [B]

## 14.1 Phone portrait [A]

```text
┌──────────────────────────────────┐
│ Header / close / manager help    │
├──────────────────────────────────┤
│ Product Stage                    │
│                                  │
├──────────────────────────────────┤
│ Current step panel               │
│ controls / pills / options       │
├──────────────────────────────────┤
│ Price Capsule / primary CTA      │
└──────────────────────────────────┘
```

## 14.2 Phone landscape [B]

```text
┌──────────────────────────────────────────────┐
│ Build Strip                                  │
├──────────────────────┬───────────────────────┤
│ Product Stage        │ Current step panel    │
│                      │                       │
├──────────────────────┴───────────────────────┤
│ Price Capsule / CTA                          │
└──────────────────────────────────────────────┘
```

## 14.3 Tablet portrait [B]

```text
┌──────────────────────────────────────────────┐
│ Header / Build Strip / Price Capsule         │
├──────────────────────┬───────────────────────┤
│ Product Stage        │ Current step panel    │
│ bigger preview       │ more spacious         │
└──────────────────────┴───────────────────────┘
```

## 14.4 Desktop / tablet landscape [B]

```text
┌─────────────────────────────────────────────────────────────┐
│ Header + Build Strip + compact summary controls            │
├──────────────────────────────┬──────────────────────────────┤
│ Product Stage                │ Decision Panel              │
│ dominates visually           │ step content                │
│                              │ contextual support          │
├──────────────────────────────┴──────────────────────────────┤
│ Price Capsule / action area                                 │
└─────────────────────────────────────────────────────────────┘
```

## 14.5 Responsive rules [A]

- tablet остаётся touch-first устройством;
- touch targets на tablet не деградируют до desktop minimum;
- hover не должен быть единственным носителем функции;
- keyboard appearance не должна ломать layout на мобильных.

# 15. Performance budget

## 15.1 Актуальная метрика responsiveness [A]

Используем **INP**, не FID.

## 15.2 Core targets [A]

- LCP ≤ 2.5s
- INP ≤ 200ms
- CLS ≤ 0.1

## 15.3 Conditions matter [B]

Измерения должны фиксироваться с указанными условиями, а не “как попало”:

- desktop: без throttling, cache disabled при лабораторной проверке;
- mobile simulation: Slow 4G / CPU slowdown для lab checks;
- реальная проверка хотя бы на одном iPhone и одном среднем Android.

Reference device-class для Android: mid-range устройство уровня Snapdragon 6xx/7xx, 4-6 GB RAM, типичный экран 1080px width-class. Это не жёсткая модель, а воспроизводимый класс устройств для QA. [B]

## 15.4 Yellow zone [B]

Если проект image-heavy и реалистично не попадает в идеал на старте, это не всегда блокер релиза — но требует явного optimisation backlog.

## 15.5 Performance — это не только CWV [B]

В implementation brief отдельно зафиксировать:
- image weight;
- preview asset strategy;
- lazy loading границ;
- upload-path resilience.

# 16. Safe exit к менеджеру

Этот механизм раньше был обещанием без описания. В v6 он становится явным контрактом.

## 16.1 Когда safe exit виден [A]

Минимум в трёх точках:

- в header / secondary help action;
- на artwork step;
- на review / submit step;
- дополнительно — в error / submission failure states.

## 16.2 Что делает safe exit [A]

Safe exit не просто открывает чат.
Он должен **сериализовать и передать контекст** уже собранной конфигурации.

Минимальный payload-contract для v1:

- session / config id;
- current step;
- выбранное изделие;
- ключевые параметры конфигурации;
- если есть — artwork status и имя / тип файла;
- уже введённый контактный способ;
- source / device context, если это уже есть в analytics layer.

На уровне doctrine не фиксируется конкретный транспорт (CRM, backend endpoint, письмо, чат-bridge), но фиксируется результат: менеджер получает **не пустой диалог, а нормализованный контекст**. [A]

Пример минимального объекта:

```json
{
  "config_id": "...",
  "current_step": "artwork",
  "product": "hoodie",
  "options": {
    "fit": "regular",
    "fabric": "cotton",
    "color": "black",
    "print_zone": "front_chest"
  },
  "artwork_status": "needs-work",
  "contact": {
    "channel": "telegram"
  }
}
```

### 16.2.1 Persistence strategy [A]

Чтобы safe exit и submission failure не врали пользователю, проекту нужен один согласованный способ хранения промежуточного состояния.

Для v1 рекомендуемый принцип:

- локальные шаговые данные сохраняются сразу по мере прогресса;
- на момент safe exit / submit создаётся нормализованный snapshot;
- если сеть падает, локальный snapshot не исчезает до явного сброса.

Какой именно механизм выбран (localStorage, session-backed flow, backend draft) — решает implementation brief, но он должен быть выбран **осознанно и единообразно**, а не “как получится в одном компоненте”. [A]

## 16.3 UX-копирайт [B]

Допустимый тип формулировок:

- “Нужна помощь менеджера?”
- “Сложный случай? Передадим всё, что вы уже собрали.”
- “Не хотите разбираться дальше? Продолжим с человеком.”

Не использовать tone, который превращает конфигуратор в неуверенный полуфабрикат.

# 17. Non-goals v1

## 17.1 Не делаем [A]

- новый визуальный язык вместо TwoComms;
- heavy 3D / AR как обязательную часть v1;
- “нейромаркетинговый театр” с надуманными микроэффектами;
- fake urgency / fake social proof;
- full internationalization scope;
- B2B-first архитектуру;
- огромную gift-ветку.

## 17.2 Почему [B]

Потому что цель v1 — не показать максимальное количество идей, а собрать **понятный, предметный, внедряемый конфигуратор**, который не ломает бренд и не создаёт лишний production-risk.

# 18. Handoff checklist для следующего артефакта

Следующий артефакт после этого документа — **wireflow / implementation brief**.

## 18.1 В нём уже обязательно должны быть [A]

- экраны и переходы по шагам;
- layout rules по breakpoints;
- конкретные состояния Product Stage / Build Strip / Price Capsule;
- event schema implementation mapping;
- file triage UX states;
- error and loading states;
- safe exit path;
- trust layer placement;
- baseline capture hooks.

## 18.2 Чего не надо заново оспаривать [A]

- асимметричный Quick Start как базовую идею;
- Product Stage как центр опыта;
- triage как маршрутизацию, а не жесткий reject;
- Price Capsule вместо тяжёлого sticky-блока;
- сохранение визуального языка TwoComms;
- manager-safe-exit как обязательный fallback.

## 18.3 Что можно уточнять / тестировать [C]

- детали copy;
- объём раскрытия trust layer;
- степень явности recommended labels;
- степень раскрытия price breakdown;
- точную форму review summary.

# 19. Future-safe notes

## 19.1 i18n / RTL [C]

Не part of v1 scope, но уже сейчас стоит:
- по возможности использовать logical CSS properties;
- не шить layout намертво на left/right;
- не делать directional icons единственным носителем смысла.

## 19.2 Governance [B]

Раз в 6 месяцев пересматривать:
- WCAG / platform accessibility updates;
- Core Web Vitals changes;
- production learnings from analytics;
- нужно ли обновлять doctrine.

# 20. Selected evidence notes

Ниже не полный bibliography, а короткий набор ориентиров, на которые реально опирается эта финальная версия.

## 20.1 Standards / platforms

Проверено при сборке v7.0:

- **WCAG 2.2 Target Size (Minimum)** — 24x24 CSS px minimum, со spacing exception: https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html
- **WCAG 2.2 Dragging Movements** — drag не должен быть единственным способом действия: https://www.w3.org/WAI/WCAG22/Understanding/dragging-movements.html
- **WCAG 2.2 Status Messages** — динамические статусные обновления должны быть доступны assistive tech: https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html
- **web.dev / Core Web Vitals** — INP стал Core Web Vital в марте 2024; “good” threshold <= 200 ms: https://web.dev/blog/inp-cwv-march-12 и https://web.dev/articles/inp
- **WebAIM Screen Reader Survey #10** — JAWS и NVDA важны на desktop, VoiceOver доминирует на mobile среди респондентов: https://webaim.org/blog/screen-reader-user-survey-10-results/

## 20.2 Print / artwork handling

- **Printful** — practical guidance: accepted PNG/JPEG, ideal 150-300 DPI, smaller detailed products often prefer 300 DPI, RGB/sRGB accepted for their workflow: https://www.printful.com/blog/everything-you-need-to-know-to-prepare-the-perfect-printfile
- **User-provided internal research archive** — использовать как контекст, но не как единственную доказательную базу для порогов triage.

## 20.3 UX / research

- **Baymard cart abandonment snapshot** — ориентир по общей боли checkout, но не прямой benchmark для кастомного configurator flow: https://baymard.com/lists/cart-abandonment-rate
- **Scheibehenne, Greifeneder, Todd (2010)** — meta-analysis показывает, что средний choice-overload effect близок к нулю и сильно зависит от контекста: https://scheibehenne.com/ScheibehenneGreifenederTodd2010.pdf
- **MDN ARIA live regions** — practical explainer для динамических объявлений: https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Guides/Live_regions

## 20.4 Local context

- **Promodo Ukraine eCommerce snapshot** — можно использовать как directional context, но не как прямой UI-law. Если проект опирается на локальные рыночные цифры, их нужно проверять в момент релиза.

# 21. Итоговый вердикт

Финальная v6 должна восприниматься не как ещё одна серия критики, а как **последний нормальный master-file перед implementation brief**.

Её цель — не доказать, что все решения “научно истинны”, а сделать так, чтобы:

- агент не додумывал критические механики сам;
- визуал остался TwoComms;
- сложные места были объяснены точно;
- гипотезы не маскировались под стандарты;
- проект стал проще внедрять, а не сложнее спорить о нём.

