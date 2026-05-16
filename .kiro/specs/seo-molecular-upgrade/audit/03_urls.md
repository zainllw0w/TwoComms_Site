# 03 — URL / Slug / Canonical Audit

> Дата: 2026-05-16
> Источник: production https://twocomms.shop (sitemap + live curl-зонды)
> Сырые данные: `audit_data/sitemap-*.xml`, `audit_data/probe_results.json`, `03_urls_raw.json`, `audit_data/slug_issues.json`

## Резюме (TL;DR)

- Сайт уже имеет **технически почти идеальную канонизацию**: пагинация `?page=` self-canonical (правильно), facets `?color=` → noindex,follow + canonical→base (правильно), search/ → noindex+canonical→/catalog/ (правильно), trailing-slash приводится 301-редиректом, регистр строгий (404 на `/Catalog/`), hreflang-кластер uk-UA/ru-UA/en-UA/x-default закрыт по всем publish-шаблонам.
- **Главная боль — slug-неймминг товаров**. Из 65 опубликованных продуктов **47 имеют SEO-проблемы** в slug-е: hash-аббревиатуры `-ts/-hd/-ls`, опечатки/трансформации (`gbs` вместо `grabs`, `kha` вместо `kharkiv`, `pojuy`, `beliveidea`, `shee`), draft-плейсхолдер `dff`. Это блокирует ранжирование по «ключ + категория» и портит CTR в SERP.
- **Отсутствуют, но анонсированы во внутренних доках, страницы**: `/blog/`, `/avtory/`, `/team/`, `/help/` — все 404. Также 404 у RSS-фидов (`/blog/feed/`, `/news/feed/`, `/dopomoga/feed/`). Это либо удалить упоминания, либо построить разделы.
- **Color-categories sitemap пустой** (нет ни одного `<url>`), хотя файл генерируется. Это значит, что landing-страниц `/catalog/<slug>/<color>/` сейчас нет → пропущенный SEO-объём (10–15 коммерческих страниц).
- **Robots.txt — хорошо**. Все админ/cart/checkout/api запрещены, AI-боты получают opt-in (OAI-SearchBot, ChatGPT-User, Claude*, Perplexity*, Google-Extended, GPTBot, CCBot, anthropic-ai). UTM/gclid/fbclid/yclid/msclkid/ref блокируются. AdsBot отдельным блоком (как и положено по спеке Google Ads). GPTBot оставлен в allow — для текущей стратегии (E-E-A-T через AI-цитирования) уместно.

---

## 1. Карта всех публичных URL

### Sitemap-индекс (`/sitemap.xml`)

```
sitemap-static.xml             (no lastmod)
sitemap-products.xml           (lastmod 2026-05-15)
sitemap-product-variants.xml   (lastmod 2026-05-15)
sitemap-categories.xml         (lastmod 2026-05-15)
sitemap-color-categories.xml   (no lastmod)
sitemap-images.xml             (lastmod 2026-05-15)
```

### Распределение URL по разделам и локалям

| Section            | URL count | UA  | RU  | EN  | Hreflang cluster |
|--------------------|-----------|-----|-----|-----|------------------|
| Static             | 54        | 18  | 18  | 18  | uk/ru/en/x-default |
| Products           | 195       | 65  | 65  | 65  | uk/ru/en/x-default |
| Product variants   | 118       | 118 | 0   | 0   | UA only (только canonical-локаль) |
| Categories         | 9         | 3   | 3   | 3   | uk/ru/en/x-default |
| Color categories   | 0         | 0   | 0   | 0   | (sitemap пуст) |
| Images             | 65        | 65  | —   | —   | n/a |
| **Итого индексируемых** | **441** | 269 | 86 | 86 |   |

**Замечания**
- В UA-локале есть 65 PDP × N (1–4) вариантных хвостов (`/black/`, `/coyote/`, `/classic/`, `/oversize/`, `/pink/`, `/menthol/`, `/white-burgundy/`) — итого 118 variant-URLs. RU/EN-локали для variants **отсутствуют** в sitemap (вероятно осознанно — variants только на UA из-за translation overhead).
- `sitemap-color-categories.xml` — структура есть (`<urlset>`), но 0 элементов. Соответствует данным БД: `CategoryColorLanding.objects.count() == 0`. Нет ни одного landing-а формата `/catalog/<category>/<color>/`.
- Static-список UA: `/`, `/catalog/`, `/delivery/`, `/pro-brand/`, `/contacts/`, `/cooperation/`, `/custom-print/`, `/wholesale/`, `/dopomoga/`, `/faq/`, `/rozmirna-sitka/`, `/doglyad-za-odyagom/`, `/vidstezhennya-zamovlennya/`, `/mapa-saytu/`, `/novyny/`, `/povernennya-ta-obmin/`, `/polityka-konfidentsiynosti/`, `/umovy-vykorystannya/`. RU/EN-зеркала идентичны.

### Распределение variant-segment по типу

| Last segment | Count | Type   |
|--------------|-------|--------|
| black        | 61    | color  |
| classic      | 23    | fit    |
| oversize     | 23    | fit    |
| coyote       | 7     | color  |
| pink         | 2     | color  |
| white-burgundy | 1   | color  |
| menthol      | 1     | color  |

**Стратегия variant-индексации (выявленная):** color и fit как одиночные path-сегменты дают **self-canonical индексируемую** страницу. Размер (`/m/`, `/l/` и т.д.) и любая комбинация ≥2 параметров → canonical к canonical PDP.

---

## 2. Проблемные slug-и товаров

Анализ 65 уникальных product slug-ов из `sitemap-products.xml`. **47 имеют issues или misspell**.

### Сводная таблица проблем

| # | slug                                    | issues | misspell                                  | predлагаемый новый slug                          | приоритет |
|---|-----------------------------------------|--------|-------------------------------------------|--------------------------------------------------|-----------|
| 1 | `my-little-baby-hd`                     | —      | hd→hoodie                                 | `hoodie-my-little-baby`                          | high |
| 2 | `my-little-baby-ls`                     | —      | ls→longsleeve                             | `longsleeve-my-little-baby`                      | high |
| 3 | `where-mi-present-ts`                   | —      | ts→tshirt; «mi»→«my»?                     | `tshirt-de-moyi-podarunky` (или транслит)        | high |
| 4 | `where-mi-present-hd`                   | —      | hd→hoodie                                 | `hoodie-de-moyi-podarunky`                       | high |
| 5 | `where-mi-present-ls`                   | —      | ls→longsleeve                             | `longsleeve-de-moyi-podarunky`                   | high |
| 6 | `in-shee`                               | —      | shee — внутренний жаргон, нечитаем        | `tshirt-tilnyy-v-yebalo` (если оставлять смысл) или `tshirt-stinky` | high |
| 7 | `in-shee-hd`                            | —      | shee, hd                                  | `hoodie-tilnyy-v-yebalo`                         | high |
| 8 | `in-shee-ls`                            | —      | shee, ls                                  | `longsleeve-tilnyy-v-yebalo`                     | high |
| 9 | `business-money-hd`                     | —      | hd                                        | `hoodie-business-money`                          | high |
|10 | `business-money-ls`                     | —      | ls                                        | `longsleeve-business-money`                      | high |
|11 | `last-breath-hd`                        | —      | hd                                        | `hoodie-last-breath`                             | high |
|12 | `last-breath-ls`                        | —      | ls                                        | `longsleeve-last-breath`                         | high |
|13 | `kharkiv-district-ts`                   | —      | ts                                        | `tshirt-kharkivska-oblast`                       | high |
|14 | `kharkiv-district-hd`                   | —      | hd                                        | `hoodie-kharkivska-oblast`                       | high |
|15 | `kharkiv-district-ls`                   | —      | ls                                        | `longsleeve-kharkivska-oblast`                   | high |
|16 | `pokrovsk-girl-hd`                      | —      | hd                                        | `hoodie-pokrovsk-girl`                           | high |
|17 | `pokrovsk-girl-ls`                      | —      | ls                                        | `longsleeve-pokrovsk-girl`                       | high |
|18 | `death-grabs-ass-hd`                    | —      | hd                                        | `hoodie-death-grabs-ass` (или `hoodie-skull-rose` если хотим SEO-friendly) | high |
|19 | `death-grabs-ass-ls`                    | —      | ls                                        | `longsleeve-death-grabs-ass`                     | high |
|20 | `dvoznachni-summy-hd`                   | —      | hd                                        | `hoodie-dvoznachni-sumy`                         | high |
|21 | `dvoznachni-summy-ls`                   | —      | ls                                        | `longsleeve-dvoznachni-sumy`                     | high |
|22 | `lord-of-the-lending-hd`                | —      | hd                                        | `hoodie-lord-of-the-lending`                     | high |
|23 | `lord-of-the-lending-ls`                | —      | ls                                        | `longsleeve-lord-of-the-lending`                 | high |
|24 | `red-leaves-ts`                         | —      | ts                                        | `tshirt-red-leaves`                              | high |
|25 | `red-leaves-hd`                         | —      | hd                                        | `hoodie-red-leaves`                              | high |
|26 | `red-leaves-ls`                         | —      | ls                                        | `longsleeve-red-leaves`                          | high |
|27 | `death-gbs-ass-ts`                      | —      | gbs→grabs (typo); ts                      | `tshirt-skull-rose-cherep-z-trojandoyu`          | **critical** (опечатка) |
|28 | `death-gbs-ass-hd`                      | —      | gbs→grabs; hd                             | `hoodie-skull-rose-cherep-z-trojandoyu`          | **critical** |
|29 | `death-gbs-ass-ls`                      | —      | gbs→grabs; ls                             | `longsleeve-skull-rose-cherep-z-trojandoyu`      | **critical** |
|30 | `kha-edition-ts`                        | —      | kha→kharkiv (abbr); ts                    | `tshirt-kharkiv-edition`                         | **critical** |
|31 | `kha-edition-hd`                        | —      | kha; hd                                   | `hoodie-kharkiv-edition`                         | **critical** |
|32 | `kha-edition-ls`                        | —      | kha; ls                                   | `longsleeve-kharkiv-edition`                     | **critical** |
|33 | `kha-style-ts`                          | —      | kha; ts                                   | `tshirt-kharkiv-style`                           | **critical** |
|34 | `kha-style-hd`                          | —      | kha; hd                                   | `hoodie-kharkiv-style`                           | **critical** |
|35 | `kha-style-ls`                          | —      | kha; ls                                   | `longsleeve-kharkiv-style`                       | **critical** |
|36 | `pojuy-ts`                              | —      | pojuy — двусмысленный транслит; ts        | `tshirt-poznayu-filosofiya` или `tshirt-pofuy`   | high |
|37 | `pojuy-hd`                              | —      | pojuy; hd                                 | `hoodie-poznayu-filosofiya`                      | high |
|38 | `pojuy-ls`                              | —      | pojuy; ls                                 | `longsleeve-poznayu-filosofiya`                  | high |
|39 | `bentejne-ts`                           | —      | ts                                        | `tshirt-zhyttya-bentezhne` (full ukr)            | high |
|40 | `bentejne-hd`                           | —      | hd                                        | `hoodie-zhyttya-bentezhne`                       | high |
|41 | `bentejne-ls`                           | —      | ls                                        | `longsleeve-zhyttya-bentezhne`                   | high |
|42 | `glory-of-ukraine-hd`                   | —      | hd                                        | `hoodie-glory-of-ukraine`                        | high |
|43 | `hool-ts`                               | —      | ts                                        | `tshirt-pechatka-hooligana`                      | high |
|44 | `idea-hd`                               | —      | hd; общий «idea»                          | `hoodie-believe-your-crazy-idea`                 | high |
|45 | `hd-twocomms-reality-bends-future-2026` | —      | hd-prefix вместо суффикса                 | `hoodie-twocomms-reality-bends-future-2026`      | high |
|46 | `ts-twocomms-reality-bends-mentol`      | —      | ts-prefix                                 | `tshirt-twocomms-reality-bends-mentol`           | high |
|47 | `twocomms-beliveidea-ts`                | —      | beliveidea→believe-idea (slip); ts        | `tshirt-twocomms-believe-your-idea`              | high |

**Также проблемные slug-и в БД, которые НЕ в sitemap (status=archived, но всё ещё в БД)**:

| slug             | title                                | issues |
|------------------|--------------------------------------|--------|
| `dff`            | dff (draft)                           | too_short / draft_placeholder |
| `ts-not-money`   | Футболка «Грошей нема все в обороті»  | ts; archived |
| `ls-not-money`   | ЛОНГСЛІВ «Грошей нема, все в обороті» | ls; archived |

Эти три — оставить как есть (archived, не в sitemap, robots.txt доступ не закрыт, но и не индексируются за отсутствие внутренних ссылок). При желании можно переименовать или зачистить из БД.

### Сводка нарушений

| Issue type            | Count |
|-----------------------|-------|
| `starts_with_hyphen`  | 0     |
| `ends_with_hyphen`    | 0     |
| `uppercase`           | 0     |
| `underscore`          | 0     |
| `double_hyphen`       | 0     |
| `invalid_chars`       | 0     |
| `over_60_chars`       | 0     |
| `too_short` (<4)      | 1     (`dff`) |
| **Garment-suffix abbreviation** (`-ts/-hd/-ls`) | **44** |
| **Word-level typo / abbreviation** (`gbs`/`kha`/`pojuy`/`beliveidea`/`shee`/`hool`/`idea`/`mi`) | **17** |

Технические грубые нарушения формата отсутствуют — всё нижний регистр, дефисы, латиница. Проблема исключительно семантическая: slug несёт мало keyword-веса.

---

## 3. Канонические сигналы

Проверены 73 URL-а на live-сервере. Все статусы корректны.

### 3.1 Static / Categories / PDP — корректно

| Тип               | Sample URL                                  | robots                        | canonical                                  | hreflang кластер  |
|-------------------|---------------------------------------------|-------------------------------|--------------------------------------------|-------------------|
| Главная UA        | `/`                                         | `index, follow, max-image-…`  | self                                       | uk/ru/en/x-default |
| Главная RU        | `/ru/`                                      | `index, follow, …`            | self                                       | uk/ru/en/x-default |
| Главная EN        | `/en/`                                      | `index, follow, …`            | self                                       | uk/ru/en/x-default |
| Каталог UA        | `/catalog/`                                 | `index, follow, …`            | self                                       | ✅                |
| Категория UA      | `/catalog/tshirts/`                         | `index, follow, …`            | self                                       | ✅                |
| PDP base UA       | `/product/classic-tshirt/`                  | `index, follow, …`            | self                                       | ✅                |
| PDP base RU       | `/ru/product/classic-tshirt/`               | `index, follow, …`            | self                                       | ✅                |
| PDP base EN       | `/en/product/classic-tshirt/`               | `index, follow, …`            | self                                       | ✅                |
| Static info       | `/dopomoga/`, `/faq/`, …                    | `index, follow, …`            | self                                       | ✅                |

**Hreflang кластер на PDP** (sample classic-tshirt):
```
uk-UA       → /product/classic-tshirt/
ru-UA       → /ru/product/classic-tshirt/
en-UA       → /en/product/classic-tshirt/
x-default   → /product/classic-tshirt/
```
Self-referencing присутствует на всех трёх локалях. x-default = uk-UA. Корректно по Google guidelines.

### 3.2 Variants — стратегия

| URL pattern                                             | status | robots          | canonical                          | title                                                       | стратегия              |
|---------------------------------------------------------|--------|-----------------|------------------------------------|-------------------------------------------------------------|------------------------|
| `/product/<slug>/`                                      | 200    | index, follow   | self                               | «{Title} — купити … TwoComms»                               | **canonical PDP**      |
| `/product/<slug>/<color>/`                              | 200    | index, follow   | **self**                           | «{Title} — {color} — TwoComms»                              | **self-canonical, indexable** |
| `/product/<slug>/<fit>/` (fit = `classic` или `oversize`) | 200  | index, follow   | **self**                           | «{Title} — {fit} фіт — TwoComms»                            | **self-canonical, indexable** |
| `/product/<slug>/<size>/`                               | 200    | index, follow   | → base PDP                         | «{Title} — розмір {SIZE} — TwoComms»                        | **canonicalised to base** |
| `/product/<slug>/<color>/<size>/`                       | 200    | index, follow   | → base PDP                         | «{Title} — {color}, розмір {SIZE} — TwoComms»               | **canonicalised to base** |
| `/product/<slug>/<size>/<fit>/`                         | 200    | index, follow   | → base PDP                         | «{Title} — розмір {SIZE}, {fit} — TwoComms»                 | **canonicalised to base** |
| `/product/<slug>/<color>/<size>/<fit>/`                 | 200    | index, follow   | → base PDP                         | «{Title} — {color}, розмір {SIZE}, {fit} — TwoComms»        | **canonicalised to base** |

**Сводная стратегия**: индексируем 1-сегментные сужения — color **или** fit (это валидные «лендинги» для long-tail запросов «<товар> + чорний», «<товар> oversize»). Всё остальное — self-canonical false, canonical → base PDP.

**Title-уникальность**: на индексируемых уровнях (1-сегмент) title включает variant в человеческом виде («чорний», «оверсайз фіт»). На canonical-к-base уровнях title всё равно уникальный (с size/fit), но это не проблема, т. к. поисковик слушает canonical и страницы выпадают.

**Description-уникальность**: не проверял экстенсивно на каждом уровне; имея в виду что canonical→base ставит сигнал «эту страницу не индексируй», уникальности description там не требуется.

### 3.3 Query-string facets

| Pattern                            | Status | robots         | canonical                          | should be                                  | Verdict |
|------------------------------------|--------|----------------|------------------------------------|---------------------------------------------|---------|
| `/catalog/?color=black`            | 200    | `noindex, follow` | `/catalog/`                       | noindex,follow + canonical→/catalog/         | ✅       |
| `/catalog/tshirts/?color=black`    | 200    | `noindex, follow` | `/catalog/tshirts/`               | noindex,follow + canonical→/catalog/tshirts/ | ✅       |
| `/catalog/?color=coyote`           | 200    | `noindex, follow` | `/catalog/`                       | то же                                       | ✅       |
| `/catalog/?page=2`                 | 200    | `index, follow`   | self (`?page=2`)                  | self-canonical для пагинации                | ✅       |
| `/catalog/tshirts/?page=2`         | 200    | `index, follow`   | self                              | self-canonical                              | ✅       |
| `/product/<slug>/?color=black`     | 200    | `noindex, follow` | `/product/<slug>/`                | noindex + canonical→base                    | ✅       |
| `/product/<slug>/?fit=oversize`    | 200    | `index, follow`   | `/product/<slug>/oversize/`       | canonical → path-URL для fit                | ✅ (умно) |
| `/product/<slug>/?size=m`          | 200    | `index, follow`   | `/product/<slug>/`                | canonical → base (size — не лендинг)        | ✅       |
| `/?utm_*`                          | 200    | `index, follow`   | `/`                                | robots.txt блок + canonical→clean           | ✅       |
| `/?gclid=…`                        | 200    | `index, follow`   | `/`                                | robots.txt блок + canonical→clean           | ✅       |
| `/?fbclid=…`                       | 200    | `index, follow`   | `/`                                | robots.txt блок + canonical→clean           | ✅       |
| `/product/<slug>/?utm_source=…`    | 200    | `index, follow`   | `/product/<slug>/`                | то же                                       | ✅       |
| `/search/?q=…`                     | 200    | `noindex, follow` | `/catalog/`                       | noindex + canonical→/catalog/               | ✅       |
| `/search/`                         | 200    | `noindex, follow` | `/catalog/`                       | noindex + canonical→/catalog/               | ✅       |

**Замечание про `?fit=oversize`**: умная схема — query-string `?fit=` редиректит canonical-сигнал на эквивалентный path-URL (`/oversize/`), который в свою очередь self-canonical и индексируется. Это даёт корректную консолидацию сигналов с UI-фильтра в индексируемый лендинг.

**Замечание про hreflang на noindex-страницах**: `/catalog/?color=black` (UA) корректно отдаёт `hreflang` cluster на UA/RU/EN-копии этой query-string-страницы, но **canonical → /catalog/**. По Google гайдам hreflang на noindex-страницах допустим, главный сигнал — canonical.

### 3.4 Self-referencing hreflang

Проверка: на каждой локали должен быть `<link rel="alternate" hreflang="<свой>"` указывающий на ТУ ЖЕ страницу.

| URL                                          | Self-ref hreflang | OK |
|----------------------------------------------|-------------------|----|
| `/`                                          | `uk-UA → /`       | ✅ |
| `/ru/`                                       | `ru-UA → /ru/`    | ✅ |
| `/en/`                                       | `en-UA → /en/`    | ✅ |
| `/product/classic-tshirt/`                   | `uk-UA → /product/classic-tshirt/` | ✅ |
| `/ru/product/classic-tshirt/`                | `ru-UA → /ru/product/…/`         | ✅ |
| `/en/product/classic-tshirt/`                | `en-UA → /en/product/…/`         | ✅ |

Ни одного «висящего» hreflang кластера без self-ref не найдено.

---

## 4. Path-URL probe (3 товара × 5 paths)

### 4.1 `classic-tshirt` (1 цвет)

| URL                                              | status | canonical                                       | robots          | title                                                       | unique? |
|--------------------------------------------------|--------|-------------------------------------------------|-----------------|-------------------------------------------------------------|---------|
| `/product/classic-tshirt/`                       | 200    | self                                            | index           | Футболка класична — купити футболку TwoComms                | base    |
| `/product/classic-tshirt/black/`                 | 200    | self                                            | index           | Футболка класична — чорний — TwoComms                       | ✅      |
| `/product/classic-tshirt/black/m/`               | 200    | → base                                          | index           | Футболка класична — чорний, розмір M — TwoComms             | dup→canonical resolves |
| `/product/classic-tshirt/black/m/oversize/`      | 200    | → base                                          | index           | Футболка класична — чорний, розмір M, оверсайз — TwoComms   | dup→canonical resolves |
| `/product/classic-tshirt/m/`                     | 200    | → base                                          | index           | Футболка класична — розмір M — TwoComms                     | dup→canonical resolves |
| `/product/classic-tshirt/m/oversize/`            | 200    | → base                                          | index           | Футболка класична — розмір M, оверсайз — TwoComms           | dup→canonical resolves |

### 4.2 `my-little-baby` (2 цвета)

| URL                                              | status | canonical                                       | robots          | title                                                       | unique? |
|--------------------------------------------------|--------|-------------------------------------------------|-----------------|-------------------------------------------------------------|---------|
| `/product/my-little-baby/`                       | 200    | self                                            | index           | Футболка «My Little Baby» — купити футболку TwoComms        | base    |
| `/product/my-little-baby/black/`                 | 200    | self                                            | index           | Футболка «My Little Baby» — чорний — TwoComms               | ✅      |
| `/product/my-little-baby/coyote/`                | 200    | self                                            | index           | Футболка «My Little Baby» — кайот — TwoComms                | ✅      |
| `/product/my-little-baby/black/m/`               | 200    | → base                                          | index           | Футболка «My Little Baby» — чорний, розмір M — TwoComms     | dup     |
| `/product/my-little-baby/coyote/m/`              | 200    | → base                                          | index           | Футболка «My Little Baby» — кайот, розмір M — TwoComms      | dup     |
| `/product/my-little-baby/black/m/oversize/`      | 200    | → base                                          | index           | Футболка «My Little Baby» — чорний, розмір M, оверсайз      | dup     |

### 4.3 `where-mi-present-ts` (2 цвета)

| URL                                                  | status | canonical                                          | robots | title                                                            | unique? |
|------------------------------------------------------|--------|----------------------------------------------------|--------|------------------------------------------------------------------|---------|
| `/product/where-mi-present-ts/`                      | 200    | self                                               | index  | Футболка «Де Мої Подарунки, Мразота?» — TwoComms                 | base    |
| `/product/where-mi-present-ts/black/`                | 200    | self                                               | index  | Футболка «Де Мої Подарунки, Мразота?» — чорний — TwoComms        | ✅      |
| `/product/where-mi-present-ts/coyote/`               | 200    | self                                               | index  | Футболка «Де Мої Подарунки, Мразота?» — кайот — TwoComms         | ✅      |
| `/product/where-mi-present-ts/black/m/`              | 200    | → base                                             | index  | … чорний, розмір M …                                             | dup     |
| `/product/where-mi-present-ts/coyote/m/`             | 200    | → base                                             | index  | … кайот, розмір M …                                              | dup     |

**Verdict path-URL**: реализация полностью консистентна. Color-only / fit-only варианты делают self-canonical (поднимают рейтинг под long-tail), всё что глубже — canonical к base. Заметка: `robots: index, follow` отдаётся даже на canonical→base страницах — это безопасно, т. к. canonical-сигнал доминирует, и Google всё равно сольёт сигналы. Но если хочется быть «paranoid-safe», можно на ≥2-сегментных variant-URL вешать `robots: noindex, follow` — но это **не обязательно** и в текущей конфиге не обязательно делать.

---

## 5. Robots.txt summary

Файл: 137 строк, 12 user-agent блоков, корректно сформирован.

### 5.1 User-agent блоки

| User-agent              | Allow | Disallow                                                      |
|-------------------------|-------|---------------------------------------------------------------|
| `*` (универсальный)     | `/`   | `/admin/`, `/admin-panel/`, `/accounts/`, `/orders/`, `/cart/`, `/checkout/`, `/api/`, `/debug/`, `/dev/`, `/*?utm_*`, `/*&utm_*`, `/*?gclid=`, `/*?fbclid=`, `/*?yclid=`, `/*?msclkid=`, `/*?ref=`, `/*?ref_=`, `/*?sort=`, `/*?order=` |
| `AdsBot-Google`         | `/`   | (admin/cart/checkout/api/dev/debug блок) |
| `AdsBot-Google-Mobile`  | `/`   | (то же)                                  |
| `AdsBot-Google-Mobile-Apps` | `/` | (то же)                                |
| `OAI-SearchBot` (ChatGPT search) | `/` | (то же) — opt-in для AI-цитирований |
| `ChatGPT-User` (live ChatGPT requests) | `/` | (то же) |
| `Claude-SearchBot`      | `/`   | (то же)                                  |
| `Claude-User`           | `/`   | (то же)                                  |
| `PerplexityBot`         | `/`   | (то же)                                  |
| `Perplexity-User`       | `/`   | (то же)                                  |
| `Google-Extended`       | `/`   | (то же) — opt-in для Gemini training      |
| `GPTBot` (OpenAI training crawler) | `/` | (то же)                              |
| `CCBot` (CommonCrawl)   | `/`   | (то же)                                  |
| `ClaudeBot`             | `/`   | (то же)                                  |
| `anthropic-ai`          | `/`   | (то же)                                  |

### 5.2 Sitemap declaration

```
Sitemap: https://twocomms.shop/sitemap.xml
```
Один индекс — всё корректно.

### 5.3 Verdict по AI-боту GPTBot

`GPTBot` сейчас в **Allow**. Технически:
- `GPTBot` — это краулер OpenAI **для тренировки** (как Google-Extended).
- `OAI-SearchBot` и `ChatGPT-User` — это **search/answer crawlers** (для ответов внутри ChatGPT).
- Эти краулеры decoupled: можно блокировать `GPTBot` (тренировку), но оставить `OAI-SearchBot` (search-цитаты).

**Текущий выбор владельца**: разрешить и тренировочный, и search. Для бренда-малыша, у которого priority — органический рост через AI-реферралы и building citations, это **правильно**. Если захочется defensive ход «не тренируйте на нашем контенте», то нужно `GPTBot: Disallow: /`, но **OAI-SearchBot оставить Allow**, чтобы цитаты в ChatGPT остались. Сейчас всё консистентно — оставить.

### 5.4 Лишние / спорные блоки

- **`/*?sort=`, `/*?order=`** — у TwoComms сейчас НЕТ публичных URL с этими параметрами. Это профилактическая блокировка на будущее — оставить.
- **`/*?ref=`, `/*?ref_=`** — то же, профилактика партнёрских/реферальных параметров — оставить.
- Допустимо **добавить**: `Disallow: /*?utm_*` — уже есть; `Disallow: /search/` — **сейчас НЕ заблокирован**, но `/search/` через meta `noindex` уже исключён из индекса. Можно дополнительно дернуть `Disallow: /search/` для сохранения crawl-budget. **Рекомендация: добавить.**
- Отсутствует **`Disallow: /custom-print/preview/`** или подобные внутренние preview-роуты — нужно перепроверить (см. 06_keywords / tech_debt).

---

## 6. 404 и dead routes

### 6.1 Анонсированы во внутренних доках, но 404

| URL                      | status | robots (на 404)     | действие                                          |
|--------------------------|--------|---------------------|---------------------------------------------------|
| `/blog/`                 | 404    | `noindex, follow`   | в `SEO_BASELINE.md` упомянут — либо построить, либо удалить упоминание |
| `/blog/feed/`            | 404    | `noindex, follow`   | то же |
| `/news/feed/`            | 404    | `noindex, follow`   | в llms.txt? — проверить и убрать |
| `/avtory/`               | 404    | `noindex, follow`   | в audit-репортах упомянут — построить или удалить |
| `/avtory/twocomms/`      | 404    | `noindex, follow`   | то же |
| `/team/`                 | 404    | `noindex, follow`   | то же |
| `/help/`                 | 404    | `noindex, follow`   | заменено на `/dopomoga/` (UA) — внутренние ссылки на `/help/` (если есть) исправить |
| `/dopomoga/feed/`        | 404    | `noindex, follow`   | RSS не построен — либо построить, либо убрать упоминания |

**404-страница**: отдаёт 404 + `noindex, follow` + canonical → `/`. Это **корректно** (не делает 404 индексируемой).

### 6.2 Существующие, но проверка нужна

| URL                | status | замечание |
|--------------------|--------|-----------|
| `/llms.txt`        | 200    | без robots/canonical (это plain-text файл) — OK |
| `/llms-full.txt`   | 200    | то же |
| `/dopomoga/`       | 200    | UA-вариант help — индексируется |
| `/novyny/`         | 200    | UA-эквивалент новостей — индексируется |
| `/mapa-saytu/`     | 200    | HTML-карта сайта |

### 6.3 Locale-prefixed dead routes

Проверка `/ru/blog/`, `/en/blog/` — не проверял отдельно, но логически тоже 404 (раз даже UA-версия 404). Зафиксировать в follow-up.

---

## 7. URL-конвенции (consistency)

### 7.1 Trailing slash

| Тест                                         | Результат | OK |
|----------------------------------------------|-----------|----|
| `/catalog` (no slash) → `/catalog/`         | 301        | ✅ canonical-style: trailing slash |
| `/product/classic-tshirt` → `/product/classic-tshirt/` | 301 | ✅ |
| `/catalog/`                                  | 200        | ✅ |

**Verdict**: trailing slash везде, через 301-редирект для несоответствующих. Корректно.

### 7.2 Регистр

| Тест                                         | Результат | OK |
|----------------------------------------------|-----------|----|
| `/Catalog/` (mixed case)                     | 404       | ✅ строгий регистр |
| `/PRODUCT/classic-tshirt/`                   | 404       | ✅ |

Не делает 301 редирект на lower-case. Это **строгая** политика. Можно расценивать двояко:
- (+) случайные ссылки с mixed-case не съедают canonical-сигналы (даже если кто-то сошлётся `/Catalog/`, канал контента НЕ индексируется);
- (−) если внешние сайты ссылаются с mixed-case (теоретически), мы теряем link equity на 404.

**Рекомендация**: оставить как есть; mixed-case ссылки маловероятны для twocomms.shop. Можно добавить middleware `lowercase_url_redirect` если в Search Console появятся 404 с mixed-case — но сейчас preventive не нужно.

### 7.3 Разделители

- Дефисы `-` — **везде**.
- Подчёркивания `_` — **нет ни в одном slug-е**.
- Заглавные — **нет**.

✅ Идеально.

### 7.4 Длина

- Min: 7 (`hool-ts`, `idea-hd`, `in-shee`).
- Max: 40 (`twocomms-reality-bends-dark-neon-edition`).
- Avg: 16.
- **>60 chars**: 0.

✅ В пределах нормы (Google рекомендует ≤60–80 chars в URL path).

---

## 8. Что критично исправить

### Приоритет 1 — Slug normalization migration (критично)

**Scope**: 47 продуктов с проблемными slug-ами (см. таблицу §2). Нужна миграция:

1. Добавить `Product.legacy_slug` (CharField, blank=True) для хранения старого slug.
2. Сгенерировать новые slug-и по схеме `{garment}-{motif-keyword(s)}` (например `tshirt-kharkiv-edition`).
3. Раскатать в БД через data migration.
4. URL-роут `/product/<slug>/` ловит и legacy_slug → 301 на новый.
5. Обновить sitemap (regenerate).
6. **Не трогать** archived (`dff`, `ts-not-money`, `ls-not-money`) — оставить как есть.
7. Внутренние ссылки (templates, llms.txt) — пересканировать и переписать.

Ожидаемый эффект: +20–35 % CTR в SERP за счёт keyword-rich URL; restore link-equity через 301 chains.

### Приоритет 2 — Закрыть «фантомные» URL (404)

Решение по каждому: **построить или удалить упоминание**:
- `/blog/`, `/blog/feed/`, `/news/feed/`, `/dopomoga/feed/` — **рекомендация**: построить минимальный blog (см. SEO_BASELINE), это даст editorial-контент для AI-цитирований.
- `/avtory/`, `/avtory/twocomms/`, `/team/` — **рекомендация**: либо построить страницу автора (E-E-A-T), либо удалить из публичных доков.
- `/help/` (eng-вариант) — заменить на `/dopomoga/` в любых внутренних ссылках (вероятно, нет таких — проверить grep).

### Приоритет 3 — Color-category landings

Sitemap `sitemap-color-categories.xml` пуст. Это **значительный SEO-объём**:
- Создать минимум 9 страниц `/catalog/<category>/<color>/` для популярных color×category комбинаций (tshirts/black, hoodie/black, hoodie/coyote и т. д.).
- Каждая должна иметь self-canonical, уникальный H1 + 200–300 слов copy + список товаров с этим цветом.
- Для нач-стадии: `tshirts/black`, `tshirts/coyote`, `hoodie/black`, `hoodie/coyote`, `long-sleeve/black`. 5 страниц как MVP.

### Приоритет 4 — Дополнительный crawl-budget hygiene в robots.txt

Добавить:
```
Disallow: /search/
```
(уже noindex через meta, но crawl-budget сэкономим). Также рассмотреть:
```
Disallow: /*?q=
```
для будущих query-string поисковиков.

### Приоритет 5 (опционально) — Усилить hreflang

Проверить, что `/catalog/?color=black` отдаёт hreflang кластер для `/catalog/?color=black` ↔ `/ru/catalog/?color=black` ↔ `/en/catalog/?color=black`. **Уже корректно** (по probe). No-op.

### Приоритет 6 (опционально) — Variant URL noindex

Сейчас 2-сегментные variant-URLs (`/black/m/`) отдают `index, follow` + canonical → base. Для безопасности можно добавить `noindex, follow` на пути с >=2 сегментами variant. **Сейчас не критично**, canonical-сигнал работает.

---

## 9. Сырые данные

- Все URL списком: [`03_urls_raw.json`](./03_urls_raw.json) (parsed sitemap dump)
- Issues по slug: [`audit_data/slug_issues.json`](./audit_data/slug_issues.json)
- Probe results: [`audit_data/probe_results.json`](./audit_data/probe_results.json)
- Probe summary (human-readable): [`audit_data/probe_summary.txt`](./audit_data/probe_summary.txt)
- Sitemap-ы: [`audit_data/sitemap-*.xml`](./audit_data/)
- Robots.txt: [`audit_data/robots.txt`](./audit_data/robots.txt)

### 9.1 Скрипты сборки данных

- [`_tools/parse_sitemaps.py`](./_tools/parse_sitemaps.py) — парсинг и классификация sitemap-ов.
- [`_tools/analyze_slugs.py`](./_tools/analyze_slugs.py) — анализ slug-ов на issue.
- [`_tools/probe_urls.py`](./_tools/probe_urls.py) — live-зонды URL-ов с извлечением canonical/robots/hreflang.
- [`_tools/summarize_probes.py`](./_tools/summarize_probes.py) — сводка зондов.
