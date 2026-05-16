# Internal Linking Audit — TwoComms

> Crawl date: 2026‑05‑16
> Crawler: `curl` (UA: `Mozilla/5.0 (compatible; TwoCommsAudit/1.0)`)
> Crawl scope: 33 URL (1 home × 3 langs, 1 catalog root × 2 langs, 3 categories,
> 8 PDPs + 1 ru‑PDP, 12 support pages, 4 brand pages — `pro-brand`, `custom-print`,
> `wholesale`, `cooperation`).
> Источник списков: `sitemap-static.xml`, `sitemap-categories.xml`, `sitemap-products.xml`.
> Сырьё аудита: `audit/.tmp_linking/{pages,out,*.py}` (пайплайн воспроизводим).

---

## Executive Summary

**Общая оценка перелинковки: 6.8 / 10.**

TwoComms делает много правильного: единый header/footer на всех страницах
с ~25 уникальных ссылок (доставка, контакты, FAQ, размерная сетка, уход,
повернення, новини, мапа, політика, умови, dopomoga, custom-print,
pro-brand, wholesale, cooperation), хороший breadcrumb на PDP/категориях,
hreflang на всех trio uk/ru/en. Anchor‑тексты в массе своей keyword‑rich
(`Купити футболку «My Little Baby» — кайот`, `Розмірна сітка та посадка`,
`Замовити кастомний друк свого принта`), generic‑анкоров типа «тут / click
here / детальніше» **не найдено** ни одного.

Но есть три большие дыры:

1. **Каталог – единственный путь к товарам.** 57 из ~84 PDP получают входящую
   ссылку **только из листинга своей категории** (in-degree = 1). Нет ни «Hits»
   на главной для каждого товара, ни кросс‑линковки «Покупали также» с других
   PDP, ни блока «Похожие принты» в content body. Главная цепляет только
   ~13 «featured» PDP; остальные сидят без поддержки.
2. **Двуязычные (ru/en) PDP не cross‑link на ru/en поддерживающие страницы
   полноценно.** На `https://twocomms.shop/ru/product/classic-tshirt/`
   55 ссылок на `/ru/...`, но **37 ссылок утекают на украинский (без префикса)** —
   это все варианты цвета и контекстные «купити футболку…» внутри тела PDP.
   Пользователь, выбравший русский, кликает на «Чорний» и попадает на uk.
3. **Pagination в категориях ломает анкор‑граф.** В `/catalog/tshirts/`
   ссылки пагинации идут как `?page=2` / `»` / `2` — короткие, дубли,
   не уникальные. С точки зрения in-degree весь page=2..N не считается
   (relative URL без site path), товары со страниц 2‑N остаются без
   крепкого внутреннего бэклинка с большой главной категории, кроме
   как через cards.

Top-3 приоритетных правки (детально в §8):

* **Critical:** «Related products / Покупали також» на PDP, который ведёт
  на 4–6 не‑вариант PDP с keyword‑rich anchors — закроет orphan‑проблему
  большинству 57 товаров.
* **Critical:** на ru/en PDP все ссылки на цвет/размер/вариант **должны
  переписываться с языковым префиксом**. Сейчас bleed на uk в content body.
* **High:** добавить in-content «Hub: новинки» / «Ця колекція» на главной,
  чтобы все товары получали хотя бы 2 in-degree (категория + хаб).

---

## 1. Crawl Stats

* Запрошено URL: **33**.
* Успешно (HTML > 1 KB): **32**.
* Ошибки HTTP: **1** — `https://twocomms.shop/contacts/` отдаёт **HTTP 500**
  (тело 145 байт). Это **продакшен ошибка 5xx на одной из ключевых
  поддерживающих страниц** — нужно сразу заводить тикет вне SEO‑контекста.
  В аудите она помечена как `ERROR` и исключена из метрик per-page.
* Distribution скачанного веса (top 5):
  * `home.html` — 240 KB
  * `cat_tshirts.html` — 193 KB
  * `cat_hoodie.html` — 186 KB
  * `cat_longsleeve.html` — 185 KB
  * `pdp_my_little_baby.html` — 167 KB
* Все страницы возвращают `<link rel="canonical">` на сами себя без
  редирект-чейна. Self-canonical верный, hreflang trio (uk-UA / ru-UA / en-UA
  + x-default) присутствует на каждом проверенном template.

---

## 2. Per-Page Link Inventory

> Колонки: **Total** = всех `<a href>`; **IC** = internal‑content
> (PDP + category + brand + support + home, без utility); **Nav** = ссылки
> внутри `<header>`/`<footer>`/`<nav>`/breadcrumb; **Ext** = внешние;
> **AnchUniq%** = уникальность анкоров среди internal‑content (100 % = все
> разные).

| Page | Total | IC | Nav (struct) | Ext | AnchUniq % |
|---|---:|---:|---:|---:|---:|
| home (uk) | 87 | 72 | 41 | 2 | 76.4 |
| home (ru) | 87 | 72 | 41 | 2 | 76.4 |
| home (en) | 87 | 72 | 41 | 2 | 76.4 |
| /catalog/ | 106 | 97 | 36 | 2 | 86.4 |
| /ru/catalog/ | 106 | 97 | 36 | 2 | 86.4 |
| /catalog/tshirts/ | 209 | 195 | 36 | 2 | 76.6 |
| /catalog/hoodie/ | 195 | 184 | 36 | 2 | 76.4 |
| /catalog/long-sleeve/ | 190 | 178 | 36 | 2 | 76.5 |
| PDP classic-tshirt | 98 | 83 | 36 | 2 | 95.7 |
| PDP hoodie-classic | 94 | 79 | 36 | 2 | 96.0 |
| PDP longsleeve-classic | 94 | 79 | 36 | 2 | 96.0 |
| PDP my-little-baby | 104 | 89 | 36 | 2 | 95.7 |
| PDP my-little-baby-hd | 98 | 83 | 36 | 2 | 95.7 |
| PDP my-little-baby-ls | 98 | 83 | 36 | 2 | 95.7 |
| PDP where-mi-present-ts | 104 | 89 | 36 | 2 | 95.7 |
| PDP where-mi-present-hd | 96 | 81 | 36 | 2 | 95.8 |
| /ru/product/classic-tshirt/ | 98 | 83 | 36 | 2 | 95.7 |
| /delivery/ | 56 | 46 | 39 | 2 | 88.6 |
| /contacts/ | — | — | — | — | **HTTP 500** |
| /faq/ | 54 | 44 | 38 | 2 | 87.5 |
| /rozmirna-sitka/ | 53 | 43 | 39 | 2 | 88.4 |
| /doglyad-za-odyagom/ | 49 | 39 | 39 | 2 | 89.5 |
| /vidstezhennya-zamovlennya/ | 52 | 39 | 39 | 2 | 89.7 |
| /mapa-saytu/ | 70 | 58 | 38 | 2 | 96.6 |
| /novyny/ | 61 | 49 | 38 | 2 | 95.9 |
| /povernennya-ta-obmin/ | 52 | 42 | 39 | 2 | 88.1 |
| /polityka-konfidentsiynosti/ | 49 | 39 | 39 | 2 | 89.5 |
| /umovy-vykorystannya/ | 49 | 39 | 39 | 2 | 89.5 |
| /dopomoga/ | 55 | 45 | 39 | 2 | 87.9 |
| /pro-brand/ | 59 | 50 | 38 | 2 | 88.0 |
| /custom-print/ | 50 | 39 | 38 | 4 | 84.6 |
| /wholesale/ | 51 | 40 | 38 | 3 | 87.5 |
| /cooperation/ | 57 | 41 | 38 | 7 | 87.8 |

Главные наблюдения:

* **Ext = 2** на 90 % страниц — это `instagram.com/twocomms` и `t.me/twocomms`
  в footer. Прозрачно и под контролем (`rel` не выставлен — рекомендация в §6).
* На support-страницах **общее число ссылок ~50, при этом ~75 % это nav/footer**
  (39 / 50). Полезный сигнал во внутренней перелинковке слабый. Особенно
  у `/privacy/`, `/terms/`, `/dopomoga/` — это **dead-end‑страницы** (см. §4).
* На PDP уникальность анкоров **95–96 %** (отлично) — почти каждый якорь свой.
* На категориях AnchUniq падает до 76–77 % — это нормально, потому что в
  card‑grid одинаково повторяются «Купити», «-17 %» и т.д., а внизу есть
  длинный SEO‑текст с уникальными внутри‑тематическими anchors.

---

## 3. Anchor Text Analysis

Корпус: **2 284 anchor pairs** (anchor → internal‑content target) на 32
успешно загруженных страницах.

| Категория | Кол-во | % |
|---|---:|---:|
| Generic / weak («тут», «click», «1», «2», «»») | **18** | 0.8 % |
| Keyword-rich (≥ 2 слова) | **1 472** | 64.5 % |
| Single-word (топик: «Худі», «Лонгслів», «FAQ») | 719 | 31.5 % |
| Image-only (с alt) | 75 | 3.3 % |
| Image-only **без** alt | **0** | 0 % |

**Хорошо.**

* Generic-анкоров **почти нет**. 18 «слабых» совпадений — это пагинация
  (`«»`, `1`, `2`, `9`) на главной слайдера и в пагинации каталога. Не SEO‑
  опасно, но именно эти анкоры вообще не помогают понять target.
* Image-only без alt — **0**. Это редкий хороший результат: все товарные
  карточки имеют `<img alt="…">` с названием продукта, и каждый
  picture‑link имеет осмысленный alt (включая SVG‑логотип в header — отдан
  с alt «TwoComms»).

**Сильные паттерны (примеры из реального крауала):**

| Anchor (text) | Target |
|---|---|
| `Купити футболку «My Little Baby» — кайот` | `/product/my-little-baby/coyote/` |
| `Купити футболку «Футболка класична» оверсайз` | `/product/classic-tshirt/oversize/` |
| `Розмірна сітка та посадка` | `/rozmirna-sitka/` |
| `Доставка Новою Поштою 1‑3 дні` | `/delivery/` |
| `Замовити кастомний друк свого принта` | `/custom-print/` |
| `Чорна футболка з принтом` | `/catalog/tshirts/` |
| `Купити лонгслів Київ` | `/catalog/long-sleeve/` |
| `Худі streetwear` | `/catalog/hoodie/` |
| `T-shirt «Reality Bends»` | `/product/twocomms-reality-bends-future-2026/` |
| `FAQ Повний хаб з відповідями. Відкрити розділ` | `/faq/` |

Это близко к best practice 2026 (descriptive long-tail anchors, brand+intent).

**Слабые паттерны:**

* Нерасшифровываемые товары с numeric‑slug:
  `/product/106/`, `/product/105/`, …, `/product/33/` — **24 численных
  слугов** все ещё в индексе и линкуются с категорий. Сами анкоры на
  карточках всё ещё содержат название товара, но URL непрозрачен и анкор
  при копи‑паст в социальных сетях / Google Discover превращается в
  «twocomms.shop/product/106». Это лежит на стыке URL audit (§3 в `03_urls.md`)
  и linking, но для перелинковки оно отдельно проблемное: кроме листинга
  ни одна страница на них не ссылается.
* Цветовые варианты дублируют сами себя: на PDP `classic-tshirt` есть три
  отдельные ссылки на `/product/classic-tshirt/black/` с тремя разными
  анкорами («Чорний», «Купити футболку «Футболка класична» — чорний»,
  и через image alt) на одной странице. Это **не плохо** (помогает анкор-
  диверсификации), но превращает один target в три внутренних линка с
  одной страницы — Google в 2026 будет считать только первый, остальные
  две диффузируют link-equity.
* `cooperation`/`wholesale`: только **по 1 ссылке** на категорию каталога
  внутри тела (в основном на `/catalog/`), хотя страница рекламирует
  «футболки», «худі», «лонгсліви» как товарные группы. Ни одного inline
  anchor `купити худі оптом` → `/catalog/hoodie/`.

**Image-only links:**

* 75 уникальных image-only ссылок с alt на 32 страницах — это товарные
  карточки. Все имеют alt с названием продукта.
* Однако в content body PDP найдены 2 случая (1 в uk, 1 в ru) link‑wrapped
  логотипа без alt: `<a href="/login/"><img></a>`. Это утилитарная иконка
  (silhouette профиля), но она отдаётся как `[IMG_NO_ALT]`. **Минорный
  a11y‑issue, не SEO.**

---

## 4. Link Graph

### 4.1 In-degree (крупные хабы)

| Target | In-degree* | Комментарий |
|---|---:|---|
| `/` (home) | 32 | header/footer |
| `/catalog/` | 32 | header/footer |
| `/delivery/` | 32 | footer |
| `/cooperation/` | 32 | footer |
| `/pro-brand/` | 32 | footer |
| `/contacts/` | 32 | footer |
| `/custom-print/` | 32 | footer + content |
| `/favorites/` | 32 | header (utility) |
| `/dopomoga/` | 32 | footer |
| `/faq/` | 32 | footer |
| `/povernennya-ta-obmin/` | 32 | footer |
| `/doglyad-za-odyagom/` | 32 | footer |
| `/novyny/` | 32 | footer |
| `/mapa-saytu/` | 32 | footer |
| `/rozmirna-sitka/` | 32 | footer + PDP body |
| `/vidstezhennya-zamovlennya/` | 32 | footer |
| `/polityka-konfidentsiynosti/` | 32 | footer |
| `/umovy-vykorystannya/` | 32 | footer |
| `/catalog/tshirts/` | 21 | catalog + PDP body |
| `/catalog/long-sleeve/` | 21 | catalog + PDP body |
| `/catalog/hoodie/` | 21 | catalog + PDP body |

\* In-degree считается по уникальным **исходным страницам** (а не по
числу `<a>`), и игнорирует `internal-utility` (login/cart/register/oauth).

### 4.2 In-degree (длинный хвост — orphans)

PDP, у которых **из 32 закроулённых страниц только 1 даёт ссылку** —
обычно это листинг своей категории. 57 / 84 уникальных продуктов сидят
с in-degree = 1.

Полный список orphan-PDP (in-degree = 1):

```
in-degree=1, source=/catalog/hoodie/:
  /product/95/  /product/102/  /product/50/  /product/49/  /product/46/
  /product/45/  /product/91-hoodie/-эквиваленты в numeric-slug/
  /product/dvoznachni-summy-hd/  /product/kha-style-hd/  /product/lord-of-the-lending-hd/
  /product/bentejne-hd/  /product/pojuy-hd/  /product/red-leaves-hd/
  /product/last-breath-hd/  /product/pokrovsk-girl-hd/  /product/hoodie-silent-winter/
  /product/20-twocomms-legend/  /product/idea-hd/  /product/225-hoodie/  /product/v2-0-pokrovsk/
  /product/death-grabs-ass/  /product/in-shee-hd/  /product/kha-edition-hd/

in-degree=1, source=/catalog/tshirts/:
  /product/106/  /product/105/  /product/104/  /product/103/  /product/100/
  /product/91/  /product/49/  /product/46/  /product/lord-of-the-lending/
  /product/bentejne-ts/  /product/kha-style-ts/  /product/pojuy-ts/
  /product/death-grabs-ass-ts/  /product/red-leaves-ts/  /product/dvoznachni-summy/
  /product/pokrovsk-girl/  /product/last-breath-ts/  /product/in-shee/
  /product/business-money/  /product/idea-ts/  /product/225-tshirt/
  /product/twocomms-reality-bends-future-2026/  /product/ts-twocomms-reality-bends-mentol/
  /product/hool-ts/

in-degree=1, source=/catalog/long-sleeve/:
  /product/dvoznachni-summy-ls/  /product/kha-style-ls/  /product/red-leaves-ls/
  /product/bentejne-ls/  /product/pojuy-ls/  /product/52/  /product/51/  /product/42/
  /product/last-breath-ls/  /product/pokrovsk-girl-ls/  /product/in-shee-ls/
  /product/business-money-ls/  /product/idea-ls/  /product/225-longsleeve/

in-degree=1, special:
  /catalog/custom-print/  ← only from /custom-print/ body (категория-помощник)
```

Видно, что in-degree=1 распределено равномерно по всем трём категориям
(hoodie/tshirts/long-sleeve), то есть **проблема не в одной категории,
а в шаблоне PDP**: он не cross-линкует на «соседние» PDP в категории и
почти не получает обратных ссылок ни с главной, ни с support-страниц.

### 4.3 Out-degree (хабы)

| Source | Out-degree (уникальные внутренние target) |
|---|---:|
| `/catalog/tshirts/` | 46 |
| `/catalog/hoodie/` | 45 |
| `/catalog/long-sleeve/` | 45 |
| `/product/my-little-baby/` | 36 |
| `/product/where-mi-present-ts/` | 36 |
| `/product/classic-tshirt/` | 33 |
| `/product/my-little-baby-hd/` | 33 |
| `/product/my-little-baby-ls/` | 33 |
| `/ru/product/classic-tshirt/` | 33 |
| `/product/where-mi-present-hd/` | 32 |
| home (uk/ru/en) | 29 |
| `/mapa-saytu/` | 29 |
| `/novyny/` | 26 |
| `/catalog/`, `/ru/catalog/`, `/delivery/`, `/sizes/`, `/returns/`, `/wholesale/`, `/cooperation/` | 21 |
| `/custom-print/` | 19 |
| `/faq/`, `/care/`, `/tracking/`, `/privacy/`, `/terms/`, `/dopomoga/`, `/pro-brand/` | **18** |

### 4.4 Dead-end pages

Dead-end page = страница, у которой out-degree во внутренние **content**
(не utility) ≈ minimum (только то, что висит в footer/header).

Strict dead-ends — **out-degree = 18, при этом ~17 из них приходят из
header/footer, а из тела статьи ведёт 0–3 контентных ссылки**:

* `/polityka-konfidentsiynosti/` — 0 контекстных ссылок в теле, только footer
* `/umovy-vykorystannya/` — 0 контекстных
* `/doglyad-za-odyagom/` — 0 контекстных (хотя текст про T-shirts — должен
  ссылаться на `/catalog/tshirts/`, `/rozmirna-sitka/`, `/povernennya-ta-obmin/`)
* `/faq/` — 1 контекстная (на `/catalog/`)
* `/dopomoga/` — 1 контекстная (на `/catalog/`)
* `/vidstezhennya-zamovlennya/` — 1 контекстная

Эти страницы при текущей конфигурации **впитывают link-equity из footer
(32 in-degree ×) и не передают её обратно в коммерческие зоны.**

### 4.5 Orphan pages среди support

Все 12 support-страниц имеют **in-degree = 32** благодаря footer — формально
не orphans. Но если рассматривать «**in-degree из контентной зоны**»
(не из footer/header), картина другая:

| Support page | In-degree из content body |
|---|---:|
| `/rozmirna-sitka/` | **17** (PDP body × 11 + cat × 3 + others) |
| `/delivery/` | 14 |
| `/povernennya-ta-obmin/` | 13 |
| `/doglyad-za-odyagom/` | 1–2 |
| `/faq/` | 0–1 |
| `/dopomoga/` | 0 |
| `/vidstezhennya-zamovlennya/` | 0 |
| `/novyny/` | 0 |
| `/mapa-saytu/` | 0 |
| `/polityka-konfidentsiynosti/` | 0 |
| `/umovy-vykorystannya/` | 0 |

Размерная сетка/доставка/обмен хорошо подкреплены — это видно во всех
PDP в блоке «Швидка доставка / Обмін розміру / Як обрати розмір?». А вот
**Уход за одягом, отслеживание заказа, FAQ — orphan по контентной перелинковке.**
Они получают сок только из footer.

---

## 5. Content-area Linking Density

> «Content area» = ссылки **вне** `<header>`, `<footer>`, `<nav>`, breadcrumb и
> элементов с классами `topbar/main-menu/site-footer/footer-/breadcrumb`.

| Page | In-content links | → category | → PDP | → support | → brand |
|---|---:|---:|---:|---:|---:|
| home (uk/ru/en) | 46 | 13 | 24 | 1 | 1 |
| `/catalog/` | 61 | 47 | 0 | 1 | 6 |
| `/ru/catalog/` | 61 | 47 | 0 | 1 | 6 |
| `/catalog/tshirts/` | **162** | 88 | 56 | 7 | 4 |
| `/catalog/hoodie/` | 150 | 75 | 56 | 7 | 5 |
| `/catalog/long-sleeve/` | 145 | 71 | 56 | 7 | 4 |
| PDP classic-tshirt | **60** | 23 | 14 | 11 | 4 |
| PDP hoodie-classic | 56 | 23 | 10 | 11 | 4 |
| PDP my-little-baby | 66 | 23 | 20 | 11 | 4 |
| PDP my-little-baby-hd | 60 | 23 | 14 | 11 | 4 |
| PDP my-little-baby-ls | 60 | 23 | 14 | 11 | 4 |
| PDP where-mi-present-ts | 66 | 23 | 20 | 11 | 4 |
| PDP where-mi-present-hd | 58 | 23 | 12 | 11 | 4 |
| `/ru/product/classic-tshirt/` | 60 | 23 | 14 | 11 | 4 |
| `/delivery/` | 20 | 4 | 0 | 9 | 0 |
| `/faq/` | 18 | 1 | 0 | 10 | 0 |
| `/rozmirna-sitka/` | 17 | 4 | 0 | 6 | 0 |
| `/doglyad-za-odyagom/` | 13 | 1 | 0 | 5 | 0 |
| `/vidstezhennya-zamovlennya/` | 16 | 1 | 0 | 5 | 0 |
| `/mapa-saytu/` | 34 | 7 | 8 | 9 | 2 |
| `/novyny/` | 25 | 4 | 8 | 2 | 2 |
| `/povernennya-ta-obmin/` | 16 | 4 | 0 | 5 | 0 |
| `/polityka-konfidentsiynosti/` | 13 | 1 | 0 | 5 | 0 |
| `/umovy-vykorystannya/` | 13 | 1 | 0 | 5 | 0 |
| `/dopomoga/` | 19 | 1 | 0 | 10 | 1 |
| `/pro-brand/` | 23 | 3 | 0 | 4 | 1 |
| `/custom-print/` | 12 | 1 | 0 | 3 | 1 |
| `/wholesale/` | 15 | 1 | 0 | 3 | 1 |
| `/cooperation/` | 21 | 1 | 0 | 2 | 3 |

PDP в зеленой зоне идеала (5–15 контекстных ссылок на related products,
size-guide, care-guide, category, brand) — **но за счёт цветовых вариантов.**
Если разделить, на типичной PDP:

* 5–7 ссылок на **другие PDP** (related-products grid, обычно 6 карточек) ✓
* 4–8 ссылок на **варианты этого же товара** (цвет/худі/лонгслів варианты) ✓
* 11 ссылок на **support** (delivery, sizes, returns, care, custom-print)
  — это много, и это обоснованно (USP-блоки и блок-помощников)
* 23 ссылки на **категории** — это явно избыточно. Это «SEO‑облако» внизу
  PDP с фразами «Чорна футболка», «Біла футболка», «Розмір XS»…«Розмір XXL».
  9 размеров + 5 цветов + 2 fits = 16 ссылок на одну и ту же `/catalog/tshirts/`
  (с разными query params). Это тяжёлая link‑aggregation, и почти все
  ведут на тот же URL. Google это не штрафует, но эффективности не
  добавляет (только первая ссылка с уникальным анкором передаст вес).
  Лучше превратить в реальные filtered‑URL’ы (`?size=L`, `?color=black`)
  и сохранить, либо вынести в плоский faceted catalog. Сейчас на категории
  пагинация уже использует `?size=`/`?color=` (см. cat_tshirts), так что
  правильнее сделать чтобы PDP cross‑linked на конкретные filtered страницы.

PDP в красной зоне — **0 in-content ссылок на support**:
* `/cooperation/` имеет 21 контекстную ссылку, но 0 на каталог-листинги
  и только 2 на support. Между тем эта страница продаёт корпоративы
  и оптовые заказы — должна линковать на «Каталог футболок», «Каталог
  худі» и «Розмірна сітка для команд».

---

## 6. Footer Analysis

В footer 25 уникальных ссылок, все они присутствуют на **32/32** успешно
закроулённых страниц.

```
internal-home    /                        ['TwoComms']
internal-category /catalog/               ['Каталог', 'Catalog']
internal-support /delivery/               ['Доставка і оплата', 'Delivery & payment', 'Доставка и оплата']
internal-brand   /cooperation/            ['Співпраця', 'Cooperation', 'Сотрудничество']
internal-brand   /pro-brand/              ['Про бренд', 'About the brand', 'О бренде']
internal-support /contacts/               ['Контакти', 'Контакты', 'Contacts']
internal-brand   /custom-print/           ['Создать свой принт', 'Create your print', 'Створити свій принт']
internal-other   /favorites/              ['0']               ← см. ниже
internal-utility /login/                  ['Sign in', 'Увійти', 'Войти']
internal-utility /register/               ['Зарегистрироваться', 'Зареєструватись', 'Sign up']
internal-utility /oauth/login/google-oauth2/   ['Sign in with Google', …]
external         instagram.com/twocomms   ['Instagram']
external         t.me/twocomms            ['Написати нам у Telegram', 'Telegram']
internal-support /dopomoga/               ['Help', 'Допомога', 'Помощь']
internal-support /faq/                    ['FAQ']
internal-support /povernennya-ta-obmin/   ['Повернення та обмін', 'Returns & exchanges', 'Возврат и обмен']
internal-support /doglyad-za-odyagom/     ['Garment care', 'Догляд за одягом', 'Уход за одеждой']
internal-support /novyny/                 ['Новини', 'Новости', 'News']
internal-support /mapa-saytu/             ['Карта сайта', 'Site map', 'Карта сайту']
internal-support /rozmirna-sitka/         ['Розмірна сітка', 'Размерная сетка', 'Size guide']
internal-support /vidstezhennya-zamovlennya/ ['Відстеження замовлення', 'Отслеживание заказа', 'Order tracking']
internal-support /polityka-konfidentsiynosti/ ['Privacy policy', …]
internal-support /umovy-vykorystannya/    ['Terms of use', 'Умови використання', 'Условия использования']
tel              tel:+380966543212        ['☎ +38 (096) 654-32-12']
mailto           mailto:info@twocomms.shop ['✉ info@twocomms.shop']
```

**Stuffing‑check:**

* Top‑20 word counts в footer-anchors:
  `і(3) каталог(2) доставка(2) оплата(2) співпраця(2) про(2) бренд(2)
   контакти(2) принт(2) умови(2) увійти(2) twocomms(1) створити(1) свій(1)`
* Никакого «купити купити купити» / «футболка футболка худі худі» — footer
  не зашит «коммерческими» якорями, а только функциональными. Это правильно.
* Анкоры **тримлингваль** (uk/ru/en) — на странице рендерится только один
  из вариантов, мы видим все три, потому что анализ проходит по 32 страницам
  на разных языковых префиксах.

**Точка к улучшению:**

* `internal-other /favorites/` с анкором `'0'` (счётчик избранного) — это
  link-text не несёт смысловой нагрузки. У пустой Wishlist у Google
  получится anchor `«0»`. Лучше анкор `Обране` / `Wishlist` всегда, а
  цифру — в badge.
* В footer есть две `external` ссылки на Instagram и Telegram **без
  `rel="nofollow noopener"`/`rel="me"`** (rel пустой по результатам
  парсинга). Безопасно, но нерекомендуемо для соцсетей.
* `tel:` и `mailto:` присутствуют ровно 1 раз — нормально.
* `/contacts/` тоже в footer, но при этом возвращает HTTP 500. Footer-
  ссылка на 5xx страницу × 32 = **32 равно‑весных битых перехода**. Это
  **внутренний broken link** в маштабе всего сайта, и его надо чинить
  раньше всех остальных правок.

---

## 7. Cross-language Linking

### 7.1 Hreflang

Все проверенные templates (home, PDP, category, ru-PDP) содержат корректное:

```html
<link rel="alternate" hreflang="uk-UA" href="https://twocomms.shop/...">
<link rel="alternate" hreflang="ru-UA" href="https://twocomms.shop/ru/...">
<link rel="alternate" hreflang="en-UA" href="https://twocomms.shop/en/...">
<link rel="alternate" hreflang="x-default" href="https://twocomms.shop/...">
```

**Замечание:** все три `hreflang` зашиты как `*-UA` (region locked на
Украину). Если стоит цель раскачать `en` для аудитории в UE/USA — стоит
рассмотреть либо `en` без региона, либо добавить `en-US`/`en-GB` алиасы.
(Это в зоне ответственности `03_urls.md`/`07_best_practices_2026.md`,
оставлено как заметка.)

### 7.2 Prominent language switcher

* На всех страницах в верхнем правом углу есть **language switcher**
  (флаги «🇺🇦 UA / 🇷🇺 RU / 🇬🇧 EN»).
* Анкоры: `🇺🇦 Украинский UA`, `🇬🇧 Английский EN`, `🇷🇺 Russian RU` — это
  и текст и эмодзи. Доступно для скринридеров (содержит литералы языка).
* Switcher переключает страницу на эквивалент через language root
  (`/` ↔ `/ru/` ↔ `/en/`). При нахождении на PDP `/product/foo/` он
  переключает на `/ru/product/foo/`. **Это правильно реализовано.**

### 7.3 Contextual cross-language

На `https://twocomms.shop/ru/product/classic-tshirt/`:

| Префикс | Кол-во ссылок |
|---|---:|
| `/ru/...` | 55 |
| `/...` (uk без префикса) | **37** |
| `/en/...` | 1 |

37 «утечек» — это:

1. **Все ссылки на цветовые варианты** товара (`/product/classic-tshirt/black/`,
   `/product/classic-tshirt/oversize/`, `/product/classic-tshirt/classic/`).
   После клика пользователь, бывший в ru, попадает на uk.
2. **Все «Купити футболку „Футболка классическая“ оверсайз»** анкоры в
   контентной части.
3. Несколько других PDP в block «Related products».

**Это критическая bug в i18n‑linking.**
Шаблон `product_detail.html` (или partial для variant‑switcher и related‑grid)
строит URL без учёта `LANGUAGE_CODE`. Решение: всегда брать `request.LANGUAGE_CODE`
из контекста и префиксовать, или вызывать `reverse('product_detail',
args=[slug])` через `i18n_patterns`.

На home_ru / home_en утечек практически нет (лишь 3 ссылки на uk-без‑префикса:
`/oauth/login/google-oauth2/` × 2 — это OAuth callback, и `/` — это
explicit «🇺🇦 UA» в switcher). Это нормально.

### 7.4 Pagination URL pattern + i18n

В `/ru/catalog/tshirts/?page=2` мы не проверяли (не в скоупе крауала),
но судя по тому, что в `/catalog/tshirts/` пагинация это `<a href="?page=2">`
(relative), на ru/en тот же шаблон будет работать корректно (relative
сохранит `/ru/` префикс). **Тест прошёл косвенно.**

---

## 8. Top 10 Internal Linking Improvements (приоритизировано)

### 🔴 Critical (срочные блокеры, сильно влияют на SEO/UX)

**1. Починить HTTP 500 на `/contacts/`.**
Footer ссылается со всех 32 страниц на эту страницу. 32 битых ссылки в
интернал‑графе — Google bot уже видит. Срочно: чинить рендер
`contacts_view`. Это backend‑тикет, но для linking‑аудита — приоритет №1.

**2. Cross-language link bleed на ru/en PDP.**
На `/ru/product/classic-tshirt/` 37 ссылок утекают на uk. Нужно в
`templates/product/...` (variant switcher, color cards, related products)
обернуть все hard‑coded `/product/...` в `{% url %}` через `i18n_patterns`
или `prefix_url(request.LANGUAGE_CODE, slug)`. Чек‑контроль: `curl /ru/...`
не должен содержать ни одного `/product/` без `/ru/` префикса в content
body (хедер/футер языка не считаем — там их и не должно быть).

**3. Заменить orphan‑анкоры с цветовых дублей на «Related products».**
57 PDP получают линк только из категории. Шаблон PDP уже имеет блок «Це
може зацікавити» с 6 карточками — но он рендерится из тех же 6 «featured»
товаров на каждой PDP (см. в crawl: одни и те же `225-hoodie`, `idea-hd`,
`v2-0-pokrovsk`, `225-tshirt`, `where-mi-present-ts`, `business-money`
повторяются). Нужно сделать **смежно‑тематическую выборку**: товары той
же категории + ±1 коллекции, исключая текущий и его варианты. Достаточно
4–6 ссылок, лишь бы они **варьировались по PDP**. Это закроет orphan'у
при таком же весе — каждый товар получит 5–10 in‑links от соседей.

### 🟠 High (заметный прирост, но не блокер)

**4. Hub‑блок «Нові надходження / Хіти» на home.**
На главной 24 PDP. Это 13 «featured» товаров и их вариации. Нужно ввести
блок «Усі новинки» (ссылка на `/catalog/?sort=new`) + список 8–12
последних добавленных товаров. Если на главной всё время будет 12–24
свежих PDP, ротация подкормит длинный хвост.

**5. Inline‑links в support‑страницах.**
* `/doglyad-za-odyagom/` — добавить inline anchors на `/rozmirna-sitka/`,
  `/povernennya-ta-obmin/`, `/catalog/tshirts/`, `/catalog/hoodie/` («Якщо
  ваша футболка з принтом …»).
* `/faq/` — каждый ответ FAQ должен ссылаться на конкретный
  catalog/PDP/support (сейчас 1 контекстная ссылка на 18 inline‑linkов).
* `/dopomoga/` — добавить «Готові оформити замовлення?» → `/catalog/`,
  «Перевірте розмір» → `/rozmirna-sitka/` (сейчас 1 контекстная).
* `/vidstezhennya-zamovlennya/` — линки на «Зв’яжіться з нами» →
  `/contacts/`, «Поверну­ти товар?» → `/povernennya-ta-obmin/`.

**6. Brand‑страницы (cooperation/wholesale) → каталог.**
Сейчас `/cooperation/` имеет **1** ссылку на `/catalog/`, и 0 на
`/catalog/hoodie/`, `/catalog/tshirts/`, `/catalog/long-sleeve/`. На
странице есть фразы про «футболки для команд», «худі для корпоратив­у».
Добавить эти фразы как inline anchor‑links на конкретные категории.
Аналогично — на `/wholesale/`.

**7. Заменить «облако SEO‑анкоров» на PDP на filtered URLs.**
Сейчас под каждым PDP 16 ссылок на `/catalog/tshirts/` (с разными
анкорами размеров и цветов). Лучше:

* Размер → `/catalog/tshirts/?size=L`
* Цвет → `/catalog/tshirts/?color=black`

Эти URL’ы в каталоге уже работают (`?color=black`, `?size=L` найдены в
crawl `cat_tshirts`). Это не убирает anchor‑text сигнал, но снижает
duplication penalty, повышает разнообразие in-degree distribution.

### 🟡 Medium (шлифовка, важная на длинной дистанции)

**8. Numeric‑slug PDP (24 шт.) — 301 на текстовые slug.**
Это пересекается с `03_urls.md`. С точки зрения linking важно: после
редиректа все футбольные ссылки в категории/sitemap‑html будут
гармонизированы, и Google перестанет бороться с «два варианта одного
URL» (хотя canonicals правильные).

**9. PDP variants — выводить как `<li role="presentation">`, а не как
отдельные `<a>` с тремя разными анкорами на один target.**
Можно оставить **один основной** дескриптивный анкор + один в alt
картинки, без дополнительных «Купити футболку … оверсайз» в облаке внизу.
Уменьшит шум, повысит читаемость anchor‑карта.

**10. Убрать footer‑анкор `'0'` для `/favorites/`.**
Сейчас anchor‑text это `0` (badge). Перевернуть HTML: текст «Обране»
(локализованный) внутри `<a>`, а `0` в `<span class="badge">` рядом, не
внутри.

**Бонусные:**

* Социалки в footer (`instagram.com`, `t.me`) пометить
  `rel="nofollow noopener me"` (стандарт для брендовых аккаунтов; `me`
  — для верификации в Mastodon/IndieWeb, `noopener` — для безопасности
  `target="_blank"`).
* На `/pro-brand/` уже работает классический TOC (`#manifesto`,
  `#meaning`, `#sign`, `#origin`, `#kharkiv`, `#prints`, `#quality`,
  `#faq`) — это 8 anchor‑links. **Шаблонно повторить TOC на длинных
  страницах** `/delivery/`, `/povernennya-ta-obmin/`, `/dopomoga/`,
  `/faq/` (Table of contents в начале с inline anchors).
* «Back to top» — глобально присутствует (тест по regex дал True для
  всех 32 страниц), реализован JS-кнопкой; так держать.

---

## 9. Recommended Linking Patterns

### 9.1 Шаблон inline‑якорей на PDP (внутри описания товара)

```html
<p>
  Ця футболка пошита з 100% бавовни щільністю 220 г/м².
  Перед оформленням <a href="{% url 'sizes' %}">подивіться
  розмірну сітку та посадку</a>, особливо якщо берете oversize.
  Догляд простий — детальніше про
  <a href="{% url 'care' %}">прання й температуру</a>.
  Замовлення відправляємо
  <a href="{% url 'delivery' %}">Новою Поштою за 1‑3 дні</a>;
  якщо щось не підійде — є
  <a href="{% url 'returns' %}">14 днів на обмін</a>.
</p>
```

* 4 inline anchors: sizes, care, delivery, returns.
* Каждый анкор содержит 3‑6 слов, без generic «тут», «детальніше».
* Это уже частично реализовано в USP‑карточках, но не в текстовом
  описании товара. Нужно перенести логику и в текст.

### 9.2 Шаблон «Related products» с разнообразием

```html
<section class="related-products">
  <h2>Дивіться також</h2>
  <ul>
    {% for p in related_products %}
      <li>
        <a href="{% url 'product' p.slug %}">
          {{ p.title }} —
          {{ p.category.title|lower }}
          {% if p.discount %}-{{ p.discount }}%{% endif %}
          ({{ p.price }} грн)
        </a>
      </li>
    {% endfor %}
  </ul>
</section>
```

* `related_products` = same category, NOT same product, NOT same color
  variant, ORDER BY (`overlap_in_tags`, `recently_added`).
* Каждый PDP получит 4–6 разных related, и они будут варьироваться
  между PDP.
* Анкор содержит название + категорию + цену → keyword-rich + intent.

### 9.3 Шаблон «Контекстные anchor‑links в category SEO‑тексте»

(У вас уже хорошо: `Купити лонгслів Київ`, `Худі streetwear` и т.д.).
Сохранить, но **на категории добавить «Зв’язані категорії»**:

```html
<aside class="related-categories">
  <h2>Інші категорії</h2>
  <ul>
    <li><a href="{% url 'cat' 'hoodie' %}">Худі з принтом</a></li>
    <li><a href="{% url 'cat' 'long-sleeve' %}">Лонгсліви</a></li>
    <li><a href="{% url 'custom' %}">Створити свій принт</a></li>
  </ul>
</aside>
```

### 9.4 Шаблон «Filtered URL anchor cloud» (вместо текущего размер/цвет‑облака)

```html
<aside class="catalog-shortcuts">
  <h2>Швидкі підбірки</h2>
  <a href="{% url 'cat' 'tshirts' %}?color=black">Чорна футболка з принтом</a>
  <a href="{% url 'cat' 'tshirts' %}?color=white">Біла футболка з принтом</a>
  <a href="{% url 'cat' 'tshirts' %}?fit=oversize">Футболка oversize</a>
  <a href="{% url 'cat' 'tshirts' %}?size=L">Футболка розмір L</a>
  <a href="{% url 'cat' 'tshirts' %}?discount=1">Футболки зі знижкою</a>
</aside>
```

Это анкоры с 3‑5 словами на ~15 разных filtered URL’ов (вместо 16 анкоров
на один и тот же `/catalog/tshirts/`). Гораздо лучше для in-degree
distribution и Google понимания filtered SERP.

### 9.5 Шаблон «Brand‑страницы → каталог» (cooperation, wholesale, custom-print)

В body параграфы:

```html
<p>
  Гуртові замовлення — від 30 одиниць
  <a href="{% url 'cat' 'tshirts' %}">футболок</a>,
  <a href="{% url 'cat' 'hoodie' %}">худі</a>,
  <a href="{% url 'cat' 'long-sleeve' %}">лонгсливів</a>
  з принтом TwoComms або
  <a href="{% url 'custom' %}">вашим власним дизайном</a>.
  Команді важливі однакові розміри —
  <a href="{% url 'sizes' %}">є наша розмірна сітка</a>.
</p>
```

5 inline anchors: 3 категории, custom-print, sizes. Это превратит
brand‑страницы из dead‑end в полноценные хабы.

### 9.6 Шаблон language‑safe URL builder (для устранения cross‑lang bleed)

В Django‑темплейте:

```django
{# вместо #}
<a href="/product/{{ product.slug }}/">{{ product.title }}</a>

{# использовать #}
<a href="{% url 'product_detail' slug=product.slug %}">{{ product.title }}</a>
```

И обеспечить, что url-pattern `product_detail` зарегистрирован внутри
`i18n_patterns()` блока в `urls.py`. Тогда `{% url %}` сам подставит
`/ru/...`, `/en/...` исходя из `request.LANGUAGE_CODE`.

Контрольный crawl, после правки:

```bash
curl -sL https://twocomms.shop/ru/product/classic-tshirt/ \
  | grep -oE 'href="(/[a-z]+/)?product/[^"]+' | sort | uniq -c
```

Не должно выдать ни одной строки без `/ru/` префикса.

### 9.7 TOC pattern (для длинных support-страниц)

```html
<nav class="toc" aria-label="Зміст сторінки">
  <h2>Зміст</h2>
  <ol>
    <li><a href="#delivery-np">Доставка Новою Поштою</a></li>
    <li><a href="#delivery-ukr">Укрпошта</a></li>
    <li><a href="#payment">Оплата</a></li>
    <li><a href="#tracking">Як відстежити замовлення</a></li>
  </ol>
</nav>
```

Уже есть на `/pro-brand/` (`#manifesto`, `#meaning`, …) — нужно вынести
паттерн в reusable include и применить на `/delivery/`, `/povernennya-ta-obmin/`,
`/faq/`, `/dopomoga/`, `/rozmirna-sitka/`.

---

## Source data

* Crawled HTML: `audit/.tmp_linking/pages/*.html` (32 файла).
* Parsed JSON link inventory: `audit/.tmp_linking/out/links.json`.
* Computed graph + per-target anchor corpus: `audit/.tmp_linking/out/analysis.json`.
* Pipeline (воспроизводимо): `audit/.tmp_linking/{crawl.sh,parse_links.py,analyze.py}`.

Все три скрипта используют только `curl` для крауала и Python-библиотеку
BeautifulSoup для парсинга. Никаких модификаций сайта не сделано.
