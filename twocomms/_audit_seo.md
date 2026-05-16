# TwoComms — DEEP SEO PROD AUDIT

_Прод-домен: https://twocomms.shop. Сэмпл: 153 URL (статика×3 + категории×3 + 30 продуктов×3, plus fit-варианты)._

_Сканнер: 1 поток, retry на 5xx, sequential pause 1.5s. Фактическое время — ~9 минут (прод-LiteSpeed периодически отдавал 500). 3 URL остались с HTTP 500: `/contacts/`, `/ru/contacts/`, `/en/contacts/`._

## Top-of-file summary

| Метрика | Значение |
|---|---|
| URLs scanned | **153** (из ≤200 cap) |
| URLs OK (HTTP 200) | 150 |
| URLs failing | 3 (`/contacts/` × 3 локали — 500) |
| Indexable (`robots ≠ noindex`) | 150 |
| Pages with cross-language leaks | **100** |
| Total leak occurrences | **554** |

### Leak breakdown by field family

| Field family | Count |
|---|---:|
| `jsonld` | 297 |
| `meta_description` | 46 |
| `og_description` | 46 |
| `twitter_description` | 46 |
| `h2` | 34 |
| `title` | 24 |
| `og_title` | 24 |
| `twitter_title` | 24 |
| `h3` | 11 |
| `og_image_alt` | 2 |

### Leak breakdown by locale (pages with > 0 leaks)

| Locale | Pages with leaks | Total leaks |
|---|---:|---:|
| uk | 0 / 51 | 0 |
| ru | 50 / 51 | 252 |
| en | 50 / 51 | 302 |

### Issue type counts

| Issue type | Count |
|---|---:|
| `description_length` | 47 |
| `title_length` | 14 |
| `http_error` | 3 |

## Critical issues (block indexing or trigger Google penalty)

### `0` canonical_wrong

**Все 150 OK URL'ов имеют корректный self-referential canonical.** RU/EN canonical указывают сами на себя (после нашего fix `seo-v1.1-phase-2`). Phase 4 ✅.

### `0` hreflang_missing / hreflang_wrong

Каждая страница эмитит 4 alternate'а: `uk-UA`, `ru-UA`, `en-UA`, `x-default`, и каждый указывает на правильный per-locale path. Реципрокность работает. Phase 3 ✅.

Алиасные пути (`/about/` → `/pro-brand/`, `/help-center/` → `/dopomoga/`) корректно подменяют canonical/hreflang на canonical-URL — это нормальное поведение для permanent-redirect алиасов.

### `3` HTTP 500 на `/contacts/`

Прод возвращает 500 для всех трёх локалей `/contacts/`. **Полностью убирает страницу из индекса.** Это CRITICAL — нужно поднять приоритет (см. P0).

### `100%` `/ru/` и `/en/` — UA-токены в SEO-полях (полная подмена контента не работает)

Среднее число утечек на страницу: 5 (RU) и 6 (EN). Каждая страница `/ru/*` и `/en/*` содержит хотя бы один UA-маркер в title / meta description / og:* / twitter:* / JSON-LD / H2-H3.

Это NOT блокирующая ошибка для индексации (Google всё ещё индексирует страницы), но триггерит **near-duplicate clustering**: `/ru/product/X/` и `/en/product/X/` имеют одинаковый UA-текст в значимой части контента → кластеризуются с UA-вариантом, теряют органику.

## Per-URL leak list (top 50 наиболее проблемных)

| Pos | Locale | Leaks | Issues | URL |
|---:|---|---:|---:|---|
| 1 | `en` | 17 | 0 | `https://twocomms.shop/en/rozmirna-sitka/` |
| 2 | `ru` | 17 | 0 | `https://twocomms.shop/ru/rozmirna-sitka/` |
| 3 | `en` | 16 | 1 | `https://twocomms.shop/en/doglyad-za-odyagom/` |
| 4 | `en` | 13 | 2 | `https://twocomms.shop/en/product/pojuy-ts/oversize/` |
| 5 | `en` | 13 | 2 | `https://twocomms.shop/en/product/where-mi-present-ts/classic/` |
| 6 | `ru` | 13 | 1 | `https://twocomms.shop/ru/doglyad-za-odyagom/` |
| 7 | `en` | 13 | 0 | `https://twocomms.shop/en/product/hd-twocomms-reality-bends-future-2026/pink/` |
| 8 | `en` | 12 | 1 | `https://twocomms.shop/en/product/death-gbs-ass-ts/classic/` |
| 9 | `en` | 12 | 0 | `https://twocomms.shop/en/product/my-little-baby/coyote/` |
| 10 | `en` | 11 | 1 | `https://twocomms.shop/en/product/225-tshirt/classic/` |
| 11 | `en` | 11 | 1 | `https://twocomms.shop/en/product/225-tshirt/oversize/` |
| 12 | `en` | 11 | 1 | `https://twocomms.shop/en/product/business-money/classic/` |
| 13 | `en` | 11 | 1 | `https://twocomms.shop/en/product/classic-tshirt/oversize/` |
| 14 | `en` | 11 | 1 | `https://twocomms.shop/en/product/red-leaves-ts/classic/` |
| 15 | `en` | 10 | 1 | `https://twocomms.shop/en/product/last-breath/classic/` |
| 16 | `en` | 10 | 1 | `https://twocomms.shop/en/product/last-breath/oversize/` |
| 17 | `en` | 10 | 1 | `https://twocomms.shop/en/product/twocomms-beliveidea-ts/oversize/` |
| 18 | `ru` | 9 | 1 | `https://twocomms.shop/ru/product/225-tshirt/classic/` |
| 19 | `ru` | 9 | 1 | `https://twocomms.shop/ru/product/225-tshirt/oversize/` |
| 20 | `ru` | 9 | 1 | `https://twocomms.shop/ru/product/business-money/classic/` |
| 21 | `ru` | 9 | 1 | `https://twocomms.shop/ru/product/classic-tshirt/oversize/` |
| 22 | `ru` | 9 | 1 | `https://twocomms.shop/ru/product/death-gbs-ass-ts/classic/` |
| 23 | `ru` | 9 | 1 | `https://twocomms.shop/ru/product/last-breath/classic/` |
| 24 | `ru` | 9 | 1 | `https://twocomms.shop/ru/product/last-breath/oversize/` |
| 25 | `ru` | 9 | 1 | `https://twocomms.shop/ru/product/pojuy-ts/oversize/` |
| 26 | `ru` | 9 | 1 | `https://twocomms.shop/ru/product/red-leaves-ts/classic/` |
| 27 | `ru` | 9 | 1 | `https://twocomms.shop/ru/product/twocomms-beliveidea-ts/oversize/` |
| 28 | `ru` | 9 | 1 | `https://twocomms.shop/ru/product/where-mi-present-ts/classic/` |
| 29 | `en` | 7 | 0 | `https://twocomms.shop/en/product/20-twocomms-legend/black/` |
| 30 | `en` | 7 | 0 | `https://twocomms.shop/en/product/business-money/black/` |
| 31 | `en` | 7 | 0 | `https://twocomms.shop/en/product/classic-tshirt/black/` |
| 32 | `en` | 7 | 0 | `https://twocomms.shop/en/product/glory-of-ukraine-hd/black/` |
| 33 | `en` | 7 | 0 | `https://twocomms.shop/en/product/hd-twocomms-reality-bends-future-2026/` |
| 34 | `en` | 7 | 0 | `https://twocomms.shop/en/product/hoodie-classic/black/` |
| 35 | `en` | 7 | 0 | `https://twocomms.shop/en/product/v2-0-pokrovsk/black/` |
| 36 | `ru` | 7 | 0 | `https://twocomms.shop/ru/product/20-twocomms-legend/black/` |
| 37 | `ru` | 7 | 0 | `https://twocomms.shop/ru/product/glory-of-ukraine-hd/black/` |
| 38 | `ru` | 7 | 0 | `https://twocomms.shop/ru/product/hd-twocomms-reality-bends-future-2026/pink/` |
| 39 | `ru` | 7 | 0 | `https://twocomms.shop/ru/product/v2-0-pokrovsk/black/` |
| 40 | `en` | 6 | 2 | `https://twocomms.shop/en/pro-brand/` |
| 41 | `en` | 6 | 0 | `https://twocomms.shop/en/product/in-shee-ls/black/` |
| 42 | `en` | 6 | 0 | `https://twocomms.shop/en/product/lord-of-the-lending-hd/black/` |
| 43 | `en` | 6 | 0 | `https://twocomms.shop/en/product/pokrovsk-girl-ls/black/` |
| 44 | `en` | 6 | 0 | `https://twocomms.shop/en/product/red-leaves-ls/black/` |
| 45 | `ru` | 6 | 0 | `https://twocomms.shop/ru/product/business-money/black/` |
| 46 | `ru` | 6 | 0 | `https://twocomms.shop/ru/product/classic-tshirt/black/` |
| 47 | `ru` | 6 | 0 | `https://twocomms.shop/ru/product/in-shee-ls/black/` |
| 48 | `ru` | 6 | 0 | `https://twocomms.shop/ru/product/lord-of-the-lending-hd/black/` |
| 49 | `ru` | 6 | 0 | `https://twocomms.shop/ru/product/my-little-baby/coyote/` |
| 50 | `ru` | 6 | 0 | `https://twocomms.shop/ru/product/pokrovsk-girl-ls/black/` |

### Подробности по top-10

#### 1. `https://twocomms.shop/en/rozmirna-sitka/`  (en, 17 leaks, 0 issues)

- **title** (34 ch): `Size guide and fit tips | TwoComms`
- **description** (112 ch): `TwoComms size guide: confirmed garment measurements, fit tips, how to measure, and when to reach out to support.`
- **h1**: `Size guide and fit tips`

  Leaks:
  - `jsonld[0][0]:Organization.foundingLocation.name` → markers=['cyr:Харків', 'cyr:Україна'] | `Харків, Україна`
  - `jsonld[2][0]:HowTo.name` → markers=['cyr:Як', 'cyr:зняти', 'cyr:мірки', 'cyr:і'] | `Як зняти мірки і обрати розмір TwoComms`
  - `jsonld[2][0]:HowTo.description` → markers=['cyr:Покрокова', 'cyr:інструкція', 'cyr:як', 'cyr:з'] | `Покрокова інструкція, як з’ясувати свій розмір TwoComms за власною футболкою чи худі без рулетки на тілі.`
  - `jsonld[2][0]:HowTo.tool[0].name` → markers=['cyr:Сантиметрова', 'cyr:стрічка', 'cyr:або', 'cyr:лінійка'] | `Сантиметрова стрічка або лінійка`
  - `jsonld[2][0]:HowTo.supply[0].name` → markers=['cyr:Своя', 'cyr:річ', 'cyr:для', 'cyr:звірки'] | `Своя річ для звірки`
  - `jsonld[2][0]:HowTo.step[0].name` → markers=['cyr:Покладіть', 'cyr:свою', 'cyr:річ', 'cyr:на'] | `Покладіть свою річ на рівну поверхню`
  - `jsonld[2][0]:HowTo.step[0].text` → markers=['cyr:Розправте', 'cyr:футболку', 'cyr:чи', 'cyr:худі'] | `Розправте футболку чи худі на столі, без складок. Це базова умова для точних мірок.`
  - `jsonld[2][0]:HowTo.step[1].name` → markers=['cyr:Зніміть', 'cyr:ширину', 'cyr:по', 'cyr:грудях'] | `Зніміть ширину по грудях`

#### 2. `https://twocomms.shop/ru/rozmirna-sitka/`  (ru, 17 leaks, 0 issues)

- **title** (46 ch): `Размерная сетка и советы по посадке | TwoComms`
- **description** (131 ch): `Размерная сетка TwoComms: подтверждённые garment measurements, советы по посадке, как снимать мерки и когда обращаться в поддержку.`
- **h1**: `Размерная сетка и советы по посадке`

  Leaks:
  - `jsonld[0][0]:Organization.foundingLocation.name` → markers=['ua:і'] | `Харків, Україна`
  - `jsonld[2][0]:HowTo.name` → markers=['ua:і', 'ua:розмір'] | `Як зняти мірки і обрати розмір TwoComms`
  - `jsonld[2][0]:HowTo.description` → markers=['ua:і', 'ua:розмір'] | `Покрокова інструкція, як з’ясувати свій розмір TwoComms за власною футболкою чи худі без рулетки на тілі.`
  - `jsonld[2][0]:HowTo.tool[0].name` → markers=['ua:і'] | `Сантиметрова стрічка або лінійка`
  - `jsonld[2][0]:HowTo.supply[0].name` → markers=['ua:і'] | `Своя річ для звірки`
  - `jsonld[2][0]:HowTo.step[0].name` → markers=['ua:і'] | `Покладіть свою річ на рівну поверхню`
  - `jsonld[2][0]:HowTo.step[0].text` → markers=['ua:і'] | `Розправте футболку чи худі на столі, без складок. Це базова умова для точних мірок.`
  - `jsonld[2][0]:HowTo.step[1].name` → markers=['ua:і'] | `Зніміть ширину по грудях`

#### 3. `https://twocomms.shop/en/doglyad-za-odyagom/`  (en, 16 leaks, 1 issues)

- **title** (25 ch): `Garment care for TwoComms`
- **description** (108 ch): `How to care for TwoComms garments: washing, drying, ironing, and basic tips to keep the shape and the print.`
- **h1**: `Garment care`

  Leaks:
  - `jsonld[0][0]:Organization.foundingLocation.name` → markers=['cyr:Харків', 'cyr:Україна'] | `Харків, Україна`
  - `jsonld[2][0]:HowTo.name` → markers=['cyr:Як', 'cyr:прати', 'cyr:і', 'cyr:доглядати'] | `Як прати і доглядати за одягом TwoComms з DTF-принтом`
  - `jsonld[2][0]:HowTo.description` → markers=['cyr:Покрокова', 'cyr:інструкція', 'cyr:з', 'cyr:догляду'] | `Покрокова інструкція з догляду за футболками, худі та лонгслівами TwoComms, щоб зберегти форму, колір і яскравість DTF-принта.`
  - `jsonld[2][0]:HowTo.tool[0].name` → markers=['cyr:Пральна', 'cyr:машина'] | `Пральна машина`
  - `jsonld[2][0]:HowTo.tool[1].name` → markers=['cyr:Праска'] | `Праска`
  - `jsonld[2][0]:HowTo.supply[0].name` → markers=['cyr:Делікатний', 'cyr:пральний', 'cyr:засіб'] | `Делікатний пральний засіб`
  - `jsonld[2][0]:HowTo.step[0].name` → markers=['cyr:Виверніть', 'cyr:виріб', 'cyr:навиворіт'] | `Виверніть виріб навиворіт`
  - `jsonld[2][0]:HowTo.step[0].text` → markers=['cyr:Перед', 'cyr:пранням', 'cyr:обов', 'cyr:язково'] | `Перед пранням обов’язково виверніть футболку, худі чи лонгслів навиворіт, щоб мінімізувати тертя по принту.`

  Issues:
  - `title_length`: 25

#### 4. `https://twocomms.shop/en/product/pojuy-ts/oversize/`  (en, 13 leaks, 2 issues)

- **title** (75 ch): `T-shirt «i don't give a damn — it's a philosophy» — оверсайз фіт — TwoComms`
- **description** (196 ch): `T-shirt «i don't give a damn — it's a philosophy», оверсайз фіт — щільна бавовна, DTF-друк, доставка Новою Поштою по всій Україні за 1–3 дні. Лаконічний стрітвеар від українського бренду TwoComms.`
- **h1**: `T-shirt «i don't give a damn — it's a philosophy»`

  Leaks:
  - `title` → markers=['cyr:оверсайз', 'cyr:фіт'] | `T-shirt «i don't give a damn — it's a philosophy» — оверсайз фіт — TwoComms`
  - `meta_description` → markers=['cyr:оверсайз', 'cyr:фіт', 'cyr:щільна', 'cyr:бавовна'] | `T-shirt «i don't give a damn — it's a philosophy», оверсайз фіт — щільна бавовна, DTF-друк, доставка Новою Поштою по всій Україні за 1–3 дні…`
  - `og_title` → markers=['cyr:оверсайз', 'cyr:фіт'] | `T-shirt «i don't give a damn — it's a philosophy» — оверсайз фіт — TwoComms`
  - `og_description` → markers=['cyr:оверсайз', 'cyr:фіт', 'cyr:щільна', 'cyr:бавовна'] | `T-shirt «i don't give a damn — it's a philosophy», оверсайз фіт — щільна бавовна, DTF-друк, доставка Новою Поштою по всій Україні за 1–3 дні…`
  - `twitter_title` → markers=['cyr:оверсайз', 'cyr:фіт'] | `T-shirt «i don't give a damn — it's a philosophy» — оверсайз фіт — TwoComms`
  - `twitter_description` → markers=['cyr:оверсайз', 'cyr:фіт', 'cyr:щільна', 'cyr:бавовна'] | `T-shirt «i don't give a damn — it's a philosophy», оверсайз фіт — щільна бавовна, DTF-друк, доставка Новою Поштою по всій Україні за 1–3 дні…`
  - `h2[1]` → markers=['cyr:Футболка', 'cyr:базова'] | `Футболка базова`
  - `h3[0]` → markers=['cyr:Чому', 'cyr:оверсайз-посадка'] | `Чому оверсайз-посадка`

  Issues:
  - `title_length`: 75
  - `description_length`: 196

#### 5. `https://twocomms.shop/en/product/where-mi-present-ts/classic/`  (en, 13 leaks, 2 issues)

- **title** (70 ch): `T-shirt «Where Are My Gifts, You Bastards?» — класичний фіт — TwoComms`
- **description** (191 ch): `T-shirt «Where Are My Gifts, You Bastards?», класичний фіт — щільна бавовна, DTF-друк, доставка Новою Поштою по всій Україні за 1–3 дні. Лаконічний стрітвеар від українського бренду TwoComms.`
- **h1**: `T-shirt «Where Are My Gifts, You Bastards?»`

  Leaks:
  - `title` → markers=['cyr:класичний', 'cyr:фіт'] | `T-shirt «Where Are My Gifts, You Bastards?» — класичний фіт — TwoComms`
  - `meta_description` → markers=['cyr:класичний', 'cyr:фіт', 'cyr:щільна', 'cyr:бавовна'] | `T-shirt «Where Are My Gifts, You Bastards?», класичний фіт — щільна бавовна, DTF-друк, доставка Новою Поштою по всій Україні за 1–3 дні. Лак…`
  - `og_title` → markers=['cyr:класичний', 'cyr:фіт'] | `T-shirt «Where Are My Gifts, You Bastards?» — класичний фіт — TwoComms`
  - `og_description` → markers=['cyr:класичний', 'cyr:фіт', 'cyr:щільна', 'cyr:бавовна'] | `T-shirt «Where Are My Gifts, You Bastards?», класичний фіт — щільна бавовна, DTF-друк, доставка Новою Поштою по всій Україні за 1–3 дні. Лак…`
  - `twitter_title` → markers=['cyr:класичний', 'cyr:фіт'] | `T-shirt «Where Are My Gifts, You Bastards?» — класичний фіт — TwoComms`
  - `twitter_description` → markers=['cyr:класичний', 'cyr:фіт', 'cyr:щільна', 'cyr:бавовна'] | `T-shirt «Where Are My Gifts, You Bastards?», класичний фіт — щільна бавовна, DTF-друк, доставка Новою Поштою по всій Україні за 1–3 дні. Лак…`
  - `h2[1]` → markers=['cyr:Футболка', 'cyr:базова'] | `Футболка базова`
  - `h3[0]` → markers=['cyr:Чому', 'cyr:класична', 'cyr:посадка'] | `Чому класична посадка`

  Issues:
  - `title_length`: 70
  - `description_length`: 191

#### 6. `https://twocomms.shop/ru/doglyad-za-odyagom/`  (ru, 13 leaks, 1 issues)

- **title** (24 ch): `Уход за одеждой TwoComms`
- **description** (104 ch): `Как ухаживать за одеждой TwoComms: стирка, сушка, глажка и базовые советы для сохранения формы и принта.`
- **h1**: `Уход за одеждой`

  Leaks:
  - `jsonld[0][0]:Organization.foundingLocation.name` → markers=['ua:і'] | `Харків, Україна`
  - `jsonld[2][0]:HowTo.name` → markers=['ua:і', 'ua:одяг'] | `Як прати і доглядати за одягом TwoComms з DTF-принтом`
  - `jsonld[2][0]:HowTo.description` → markers=['ua:і'] | `Покрокова інструкція з догляду за футболками, худі та лонгслівами TwoComms, щоб зберегти форму, колір і яскравість DTF-принта.`
  - `jsonld[2][0]:HowTo.supply[0].name` → markers=['ua:і'] | `Делікатний пральний засіб`
  - `jsonld[2][0]:HowTo.step[0].name` → markers=['ua:і'] | `Виверніть виріб навиворіт`
  - `jsonld[2][0]:HowTo.step[0].text` → markers=['ua:і'] | `Перед пранням обов’язково виверніть футболку, худі чи лонгслів навиворіт, щоб мінімізувати тертя по принту.`
  - `jsonld[2][0]:HowTo.step[1].name` → markers=['ua:і'] | `Періть на 30 °C у делікатному режимі`
  - `jsonld[2][0]:HowTo.step[1].text` → markers=['ua:і'] | `Використовуйте температуру не вище 30 °C і делікатний режим. Уникайте відбілювачів і агресивних плямовивідників.`

  Issues:
  - `title_length`: 24

#### 7. `https://twocomms.shop/en/product/hd-twocomms-reality-bends-future-2026/pink/`  (en, 13 leaks, 0 issues)

- **title** (43 ch): `Hoodie «Reality Bends» — рожевий — TwoComms`
- **description** (148 ch): `Hoodie «Reality Bends» (рожевий) — авторський streetwear від TwoComms. Якісний стріт & мілітарі одяг з ексклюзивним дизайном, доставка Новою Поштою.`
- **h1**: `Hoodie «Reality Bends»`

  Leaks:
  - `title` → markers=['cyr:рожевий'] | `Hoodie «Reality Bends» — рожевий — TwoComms`
  - `meta_description` → markers=['cyr:рожевий', 'cyr:авторський', 'cyr:від', 'cyr:Якісний'] | `Hoodie «Reality Bends» (рожевий) — авторський streetwear від TwoComms. Якісний стріт & мілітарі одяг з ексклюзивним дизайном, доставка Новою…`
  - `og_title` → markers=['cyr:рожевий'] | `Hoodie «Reality Bends» — рожевий — TwoComms`
  - `og_description` → markers=['cyr:рожевий', 'cyr:авторський', 'cyr:від', 'cyr:Якісний'] | `Hoodie «Reality Bends» (рожевий) — авторський streetwear від TwoComms. Якісний стріт & мілітарі одяг з ексклюзивним дизайном, доставка Новою…`
  - `og_image_alt` → markers=['cyr:Рожевий'] | `Hoodie «Reality Bends» — Рожевий — photo 1 TwoComms`
  - `twitter_title` → markers=['cyr:рожевий'] | `Hoodie «Reality Bends» — рожевий — TwoComms`
  - `twitter_description` → markers=['cyr:рожевий', 'cyr:авторський', 'cyr:від', 'cyr:Якісний'] | `Hoodie «Reality Bends» (рожевий) — авторський streetwear від TwoComms. Якісний стріт & мілітарі одяг з ексклюзивним дизайном, доставка Новою…`
  - `h2[1]` → markers=['cyr:Худі'] | `Худі`

#### 8. `https://twocomms.shop/en/product/death-gbs-ass-ts/classic/`  (en, 12 leaks, 1 issues)

- **title** (48 ch): `T-shirt «Last Breath» — класичний фіт — TwoComms`
- **description** (169 ch): `T-shirt «Last Breath», класичний фіт — щільна бавовна, DTF-друк, доставка Новою Поштою по всій Україні за 1–3 дні. Лаконічний стрітвеар від українського бренду TwoComms.`
- **h1**: `T-shirt «Last Breath»`

  Leaks:
  - `title` → markers=['cyr:класичний', 'cyr:фіт'] | `T-shirt «Last Breath» — класичний фіт — TwoComms`
  - `meta_description` → markers=['cyr:класичний', 'cyr:фіт', 'cyr:щільна', 'cyr:бавовна'] | `T-shirt «Last Breath», класичний фіт — щільна бавовна, DTF-друк, доставка Новою Поштою по всій Україні за 1–3 дні. Лаконічний стрітвеар від …`
  - `og_title` → markers=['cyr:класичний', 'cyr:фіт'] | `T-shirt «Last Breath» — класичний фіт — TwoComms`
  - `og_description` → markers=['cyr:класичний', 'cyr:фіт', 'cyr:щільна', 'cyr:бавовна'] | `T-shirt «Last Breath», класичний фіт — щільна бавовна, DTF-друк, доставка Новою Поштою по всій Україні за 1–3 дні. Лаконічний стрітвеар від …`
  - `twitter_title` → markers=['cyr:класичний', 'cyr:фіт'] | `T-shirt «Last Breath» — класичний фіт — TwoComms`
  - `twitter_description` → markers=['cyr:класичний', 'cyr:фіт', 'cyr:щільна', 'cyr:бавовна'] | `T-shirt «Last Breath», класичний фіт — щільна бавовна, DTF-друк, доставка Новою Поштою по всій Україні за 1–3 дні. Лаконічний стрітвеар від …`
  - `h3[0]` → markers=['cyr:Чому', 'cyr:класична', 'cyr:посадка'] | `Чому класична посадка`
  - `jsonld[0][0]:Organization.foundingLocation.name` → markers=['cyr:Харків', 'cyr:Україна'] | `Харків, Україна`

  Issues:
  - `description_length`: 169

#### 9. `https://twocomms.shop/en/product/my-little-baby/coyote/`  (en, 12 leaks, 0 issues)

- **title** (43 ch): `T-shirt «My Little Baby» — кайот — TwoComms`
- **description** (148 ch): `T-shirt «My Little Baby» (кайот) — авторський streetwear від TwoComms. Якісний стріт & мілітарі одяг з ексклюзивним дизайном, доставка Новою Поштою.`
- **h1**: `T-shirt «My Little Baby»`

  Leaks:
  - `title` → markers=['cyr:кайот'] | `T-shirt «My Little Baby» — кайот — TwoComms`
  - `meta_description` → markers=['cyr:кайот', 'cyr:авторський', 'cyr:від', 'cyr:Якісний'] | `T-shirt «My Little Baby» (кайот) — авторський streetwear від TwoComms. Якісний стріт & мілітарі одяг з ексклюзивним дизайном, доставка Новою…`
  - `og_title` → markers=['cyr:кайот'] | `T-shirt «My Little Baby» — кайот — TwoComms`
  - `og_description` → markers=['cyr:кайот', 'cyr:авторський', 'cyr:від', 'cyr:Якісний'] | `T-shirt «My Little Baby» (кайот) — авторський streetwear від TwoComms. Якісний стріт & мілітарі одяг з ексклюзивним дизайном, доставка Новою…`
  - `twitter_title` → markers=['cyr:кайот'] | `T-shirt «My Little Baby» — кайот — TwoComms`
  - `twitter_description` → markers=['cyr:кайот', 'cyr:авторський', 'cyr:від', 'cyr:Якісний'] | `T-shirt «My Little Baby» (кайот) — авторський streetwear від TwoComms. Якісний стріт & мілітарі одяг з ексклюзивним дизайном, доставка Новою…`
  - `h2[1]` → markers=['cyr:Футболка', 'cyr:базова'] | `Футболка базова`
  - `jsonld[0][0]:Organization.foundingLocation.name` → markers=['cyr:Харків', 'cyr:Україна'] | `Харків, Україна`

#### 10. `https://twocomms.shop/en/product/225-tshirt/classic/`  (en, 11 leaks, 1 issues)

- **title** (58 ch): `T-shirt «225th Assault Brigade» — класичний фіт — TwoComms`
- **description** (179 ch): `T-shirt «225th Assault Brigade», класичний фіт — щільна бавовна, DTF-друк, доставка Новою Поштою по всій Україні за 1–3 дні. Лаконічний стрітвеар від українського бренду TwoComms.`
- **h1**: `T-shirt «225th Assault Brigade»`

  Leaks:
  - `title` → markers=['cyr:класичний', 'cyr:фіт'] | `T-shirt «225th Assault Brigade» — класичний фіт — TwoComms`
  - `meta_description` → markers=['cyr:класичний', 'cyr:фіт', 'cyr:щільна', 'cyr:бавовна'] | `T-shirt «225th Assault Brigade», класичний фіт — щільна бавовна, DTF-друк, доставка Новою Поштою по всій Україні за 1–3 дні. Лаконічний стрі…`
  - `og_title` → markers=['cyr:класичний', 'cyr:фіт'] | `T-shirt «225th Assault Brigade» — класичний фіт — TwoComms`
  - `og_description` → markers=['cyr:класичний', 'cyr:фіт', 'cyr:щільна', 'cyr:бавовна'] | `T-shirt «225th Assault Brigade», класичний фіт — щільна бавовна, DTF-друк, доставка Новою Поштою по всій Україні за 1–3 дні. Лаконічний стрі…`
  - `twitter_title` → markers=['cyr:класичний', 'cyr:фіт'] | `T-shirt «225th Assault Brigade» — класичний фіт — TwoComms`
  - `twitter_description` → markers=['cyr:класичний', 'cyr:фіт', 'cyr:щільна', 'cyr:бавовна'] | `T-shirt «225th Assault Brigade», класичний фіт — щільна бавовна, DTF-друк, доставка Новою Поштою по всій Україні за 1–3 дні. Лаконічний стрі…`
  - `h2[1]` → markers=['cyr:Футболка', 'cyr:базова'] | `Футболка базова`
  - `h3[0]` → markers=['cyr:Чому', 'cyr:класична', 'cyr:посадка'] | `Чому класична посадка`

  Issues:
  - `description_length`: 179

## Phrase clusters (top 20 повторяющихся утечек)

Сгруппировал утечки по нормализованному значению. Эти строки — единый источник, который правится в одном месте кода.

| × | Phrase (truncated) | Source(s) | Rough count |
|---:|---|---|---:|
| 100 | `Харків, Україна` | `storefront/seo_utils.py:1037:                "name": _("Харків, Україна"),`<br>`locale/ru/LC_MESSAGES/django.po:594:msgid "Харків, Україна"`<br>`locale/en/LC_MESSAGES/django.po:603:msgid "Харків, Україна"` | 100 |
| 100 | `бавовна` | `storefront/migrations/0054_phase10c_extended_seo_copy.py:300:бавовна 200+ г/м² може бути замало для холодних спалень — оберіть`<br>`storefront/migrations/0054_phase10c_extended_seo_copy.py:334:        ("Худі бавовна",                      "/catalog/hoodie/"),`<br>`storefront/migrations/0054_phase10c_extended_seo_copy.py:381:        ("Футболка бавовна",                  "/catalog/tshirts/"),` | 100 |
| 18 | `трьохнитка` | `storefront/seo_utils.py:102:        return "трьохнитка"`<br>`storefront/services/product_seo_autofill.py:138:    320 г/м² трьохнитка. Branch on category so each PDP gets a`<br>`storefront/services/product_seo_autofill.py:148:            "відправляємо, інакше трьохнитка сяде. Прасування з вивороту "` | 18 |
| 16 | `Худі` | — | 16 |
| 12 | `Футболка базова` | `storefront/tests/test_product_size_guides.py:118:            title="Футболка базова чорна",`<br>`storefront/tests/test_product_size_guides.py:241:            title="Футболка базова чорна",`<br>`storefront/tests/test_static_support_pages.py:125:        self.assertNotContains(response, "Футболка базова")` | 12 |
| 6 | `Чому класична посадка` | `storefront/tests/test_phase16_fit_seo.py:130:        self.assertIn("Чому класична посадка", html)`<br>`storefront/services/product_seo_landing.py:84:        "h3": "Чому класична посадка",` | 6 |
| 6 | `Кайот, Black` | — | 6 |
| 5 | `Чому оверсайз-посадка` | `storefront/tests/test_phase16_fit_seo.py:124:        self.assertIn("Чому оверсайз-посадка", html)`<br>`storefront/tests/test_phase16_fit_seo.py:140:        self.assertNotIn("Чому оверсайз-посадка", classic)`<br>`storefront/services/product_seo_landing.py:71:        "h3": "Чому оверсайз-посадка",` | 5 |
| 4 | `Рожевий` | `storefront/tests/test_phase19h_seo_admin_overrides.py:41:        cls.pink = Color.objects.create(name="Рожевий", primary_hex="#F7A1B9")`<br>`storefront/custom_print_config.py:417:                        {"value": "thermo_pink", "label": "Рожевий (Термо)", "hex": "#e78ba7"}`<br>`storefront/services/color_filter.py:51:    "Рожевий",` | 4 |
| 3 | `Hoodie «Drones Around 2.0» (black) — авторський streetwear від TwoComms. Якісний стріт & м` | — | 3 |
| 3 | `T-shirt «225th Assault Brigade» — класичний фіт — TwoComms` | — | 3 |
| 3 | `T-shirt «225th Assault Brigade», класичний фіт — щільна бавовна, DTF-друк, доставка Новою ` | — | 3 |
| 3 | `T-shirt «225th Assault Brigade» — оверсайз фіт — TwoComms` | — | 3 |
| 3 | `T-shirt «225th Assault Brigade», оверсайз фіт — щільна бавовна, DTF-друк, доставка Новою П` | — | 3 |
| 3 | `T-shirt «Business Is Math» (black) — авторський streetwear від TwoComms. Якісний стріт & м` | — | 3 |
| 3 | `T-shirt «Business Is Math» — класичний фіт — TwoComms` | — | 3 |
| 3 | `T-shirt «Business Is Math», класичний фіт — щільна бавовна, DTF-друк, доставка Новою Пошто` | — | 3 |
| 3 | `Classic T-shirt (black) — авторський streetwear від TwoComms. Якісний стріт & мілітарі одя` | — | 3 |
| 3 | `Classic T-shirt — оверсайз фіт — TwoComms` | — | 3 |
| 3 | `Classic T-shirt, оверсайз фіт — щільна бавовна, DTF-друк, доставка Новою Поштою по всій Ук` | — | 3 |

## Source code traces

### Где живут UA-only фразы, попадающие на /ru/ /en/

**A. Build-on-the-fly (UA hardcoded, без gettext):**

- `storefront/services/variant_meta.py` (~L152-178) — fit-aware PDP description **в f-string без `_()`**:

  ```python
  page_description = (
      f"{inputs.product_title}, {fit_lc} фіт — щільна бавовна, "
      f"DTF-друк, доставка Новою Поштою по всій Україні за 1–3 дні. "
      f"Лаконічний стрітвеар від українського бренду TwoComms."
  )
  ```

  → Эта строка светится во всех `/ru/product/<slug>/<fit>/` и `/en/…/` (12 fit-страниц на каждую локаль), 36 утечек. P0 fix.

- `storefront/services/variant_meta.py` (~L173-176) — non-fit-variant PDP description тоже UA-only:

  ```python
  page_description = (
      f"{inputs.product_title} ({suffix}) — авторський "
      f"streetwear від TwoComms. Якісний стріт & мілітарі "
      f"одяг з ексклюзивним дизайном, доставка Новою Поштою."
  )
  ```

  → Везде, где есть color/size variant, выдаёт UA в `/ru/…/black/` и `/en/…/coyote/`. ~30 утечек.

**B. Persisted in DB (UA-only автозалив, RU/EN не сгенерированы):**

- `storefront/services/product_seo_autofill.py` — builders `_build_seo_description` и `_build_seo_keywords` пишут чистую UA-строку с `… — авторський {nom} TwoComms з мілітарним ДНК. DTF-друк, бавовна, шиємо в Україні. Доставка Новою Поштою…` в `Product.seo_description` (одно поле без `_uk`/`_ru`/`_en`-суффиксов из modeltranslation для seo_*; см. `storefront/translation.py:38-54`).
- `storefront/services/product_copy_v2.py` — то же самое для `seo_*` v2 формата.
- `storefront/migrations/0054_phase10c_extended_seo_copy.py` — seed-описания для категорий/SEO-блоков, тоже UA-only.

  → JSON-LD `Product.description`, meta description, og:description, twitter:description берут это поле один-в-один на /ru/ и /en/ без перевода. Это самый большой кластер leaks (≈300).

**C. Translations есть в .po, но не применяются на проде:**

- `storefront/seo_utils.py:1037` → `_("Харків, Україна")` для JSON-LD `Organization.foundingLocation.name`.
- `locale/ru/LC_MESSAGES/django.po:594` — `msgstr "Харьков как ДНК"` (есть!)
- `locale/en/LC_MESSAGES/django.po:603` — `msgstr "Kharkiv as DNA"` (есть!)
- Однако прод отдаёт `"Харків, Україна"` для /ru/ и /en/ (100 утечек × 2 поля).
- **Гипотеза:** на проде не пересобран `.mo` после последнего обновления `.po` ИЛИ activation language не выставляется в контексте, где формируется JSON-LD (вероятно, метатег рендерится из view, который не использует `with translation.override(locale): …`). P0 — проверить compile_messages + сборку JSON-LD.

### Где живут другие повторяющиеся UA-фразы

- `Харків, Україна` (100×):
  - `storefront/seo_utils.py:1037:                "name": _("Харків, Україна"),`
  - `locale/ru/LC_MESSAGES/django.po:594:msgid "Харків, Україна"`
  - `locale/en/LC_MESSAGES/django.po:603:msgid "Харків, Україна"`
- `бавовна` (100×):
  - `storefront/migrations/0054_phase10c_extended_seo_copy.py:300:бавовна 200+ г/м² може бути замало для холодних спалень — оберіть`
  - `storefront/migrations/0054_phase10c_extended_seo_copy.py:334:        ("Худі бавовна",                      "/catalog/hoodie/"),`
  - `storefront/migrations/0054_phase10c_extended_seo_copy.py:381:        ("Футболка бавовна",                  "/catalog/tshirts/"),`
- `трьохнитка` (18×):
  - `storefront/seo_utils.py:102:        return "трьохнитка"`
  - `storefront/services/product_seo_autofill.py:138:    320 г/м² трьохнитка. Branch on category so each PDP gets a`
  - `storefront/services/product_seo_autofill.py:148:            "відправляємо, інакше трьохнитка сяде. Прасування з вивороту "`
- `Футболка базова` (12×):
  - `storefront/tests/test_product_size_guides.py:118:            title="Футболка базова чорна",`
  - `storefront/tests/test_product_size_guides.py:241:            title="Футболка базова чорна",`
  - `storefront/tests/test_static_support_pages.py:125:        self.assertNotContains(response, "Футболка базова")`
- `Чому класична посадка` (6×):
  - `storefront/tests/test_phase16_fit_seo.py:130:        self.assertIn("Чому класична посадка", html)`
  - `storefront/services/product_seo_landing.py:84:        "h3": "Чому класична посадка",`
- `Чому оверсайз-посадка` (5×):
  - `storefront/tests/test_phase16_fit_seo.py:124:        self.assertIn("Чому оверсайз-посадка", html)`
  - `storefront/tests/test_phase16_fit_seo.py:140:        self.assertNotIn("Чому оверсайз-посадка", classic)`
  - `storefront/services/product_seo_landing.py:71:        "h3": "Чому оверсайз-посадка",`
- `Рожевий` (4×):
  - `storefront/tests/test_phase19h_seo_admin_overrides.py:41:        cls.pink = Color.objects.create(name="Рожевий", primary_hex="#F7A1B9")`
  - `storefront/custom_print_config.py:417:                        {"value": "thermo_pink", "label": "Рожевий (Термо)", "hex": "#e78ba7"}`
  - `storefront/services/color_filter.py:51:    "Рожевий",`

## Phase 6 — UA / RU / EN translation parity

Для статических страниц (home, /catalog/, /faq/, /dopomoga/, /wholesale/) **всё переведено** в title / meta description / og:* / h1 — gettext + django-modeltranslation работают.

**Базовые product PDP** (без variant): `name` / `title` / `og:title` / `h1` тоже переведены — django-modeltranslation поля `Product.title_ru` / `_en` залиты.

**Однако** `Product.description` / `Product.short_description` / `Product.seo_description` (поля, на которых modeltranslation `register`-нут — см. `storefront/translation.py:42-54`) залиты только в `*_uk`. Поэтому при рендере /ru/ и /en/ Django падает на UA fallback, и meta description / og:description / Product JSON-LD `description` остаются **полностью UA**.

**Variant PDP** (`/product/<slug>/<color>/`, `/<fit>/`) — двойная проблема: variant_meta.py строит description f-string'ами без gettext (см. выше).

Пример: `/product/225-tshirt/classic/`

| Поле | UK | RU | EN |
|---|---|---|---|
| title | `Футболка 225ОШП — класичний фіт — TwoComms` | `Футболка «225 ОШБр» — класичний фіт — TwoComms` | `T-shirt «225th Assault Brigade» — класичний фіт — TwoComms` |
| description | `Футболка 225ОШП, класичний фіт — щільна бавовна, DTF-друк, доставка Новою Поштою…` | `Футболка «225 ОШБр», класичний фіт — щільна бавовна, DTF-друк, доставка Новою Поштою…` | `T-shirt «225th…», класичний фіт — щільна бавовна, DTF-друк, доставка Новою Поштою…` |

Title переведён частично (бренд+продукт переведены через `Product.title_*` modeltranslation, fit_label «класичний фіт» — нет, потому что f-string).

Description **полностью UA** на всех локалях.

## Phase 5 — длины и H1

### Title length вне 30-65 (14 URL)

| URL | length | title |
|---|---:|---|
| `https://twocomms.shop/ru/doglyad-za-odyagom/` | 24 | `Уход за одеждой TwoComms` |
| `https://twocomms.shop/en/doglyad-za-odyagom/` | 25 | `Garment care for TwoComms` |
| `https://twocomms.shop/en/polityka-konfidentsiynosti/` | 25 | `Privacy policy | TwoComms` |
| `https://twocomms.shop/ru/delivery/` | 28 | `Доставка и оплата — TwoComms` |
| `https://twocomms.shop/en/delivery/` | 29 | `Delivery & payment — TwoComms` |
| `https://twocomms.shop/en/catalog/` | 66 | `TwoComms catalogue — t-shirts, hoodies and longsleeves with prints` |
| `https://twocomms.shop/en/cooperation/` | 70 | `Partnerships with TwoComms — dropshipping, wholesale and brand collabs` |
| `https://twocomms.shop/en/product/where-mi-present-ts/classic/` | 70 | `T-shirt «Where Are My Gifts, You Bastards?» — класичний фіт — TwoComms` |
| `https://twocomms.shop/pro-brand/` | 72 | `TwoComms — харківський бренд одягу про характер, стійкість і продовження` |
| `https://twocomms.shop/product/hd-twocomms-reality-bends-future-2026/pink/` | 72 | `Худі TWOCOMMS «Reality Bends»: Колекція Future 2026 — рожевий — TwoComms` |
| `https://twocomms.shop/ru/pro-brand/` | 72 | `TwoComms — харьковский бренд одежды о характере, стойкости и продолжении` |
| `https://twocomms.shop/en/product/pojuy-ts/oversize/` | 75 | `T-shirt «i don't give a damn — it's a philosophy» — оверсайз фіт — TwoComms` |
| `https://twocomms.shop/en/pro-brand/` | 77 | `TwoComms — Kharkiv apparel brand about character, resilience and continuation` |
| `https://twocomms.shop/product/twocomms-beliveidea-ts/oversize/` | 90 | `Чорна футболка унісекс TwoComms «Довіряй своїй божевільній ідеї» — оверсайз фіт …` |

### Meta description length вне 50-160 (47 URL)

| URL | length | description |
|---|---:|---|
| `https://twocomms.shop/en/product/classic-tshirt/oversize/` | 162 | `Classic T-shirt, оверсайз фіт — щільна бавовна, DTF-друк, доставка Новою Поштою …` |
| `https://twocomms.shop/product/225-tshirt/oversize/` | 162 | `Футболка 225ОШП, оверсайз фіт — щільна бавовна, DTF-друк, доставка Новою Поштою …` |
| `https://twocomms.shop/product/225-tshirt/classic/` | 163 | `Футболка 225ОШП, класичний фіт — щільна бавовна, DTF-друк, доставка Новою Поштою…` |
| `https://twocomms.shop/pro-brand/` | 164 | `TwoComms — український streetwear / military-adjacent бренд одягу з Харкова. Реч…` |
| `https://twocomms.shop/product/classic-tshirt/oversize/` | 164 | `Футболка класична, оверсайз фіт — щільна бавовна, DTF-друк, доставка Новою Пошто…` |
| `https://twocomms.shop/en/catalog/` | 166 | `TwoComms street & military apparel catalogue: t-shirts, hoodies and longsleeves …` |
| `https://twocomms.shop/ru/product/225-tshirt/oversize/` | 166 | `Футболка «225 ОШБр», оверсайз фіт — щільна бавовна, DTF-друк, доставка Новою Пош…` |
| `https://twocomms.shop/cooperation/` | 167 | `Співпраця з TwoComms для магазинів, шоурумів, дропшиперів, дизайнерів, блогерів …` |
| `https://twocomms.shop/ru/product/225-tshirt/classic/` | 167 | `Футболка «225 ОШБр», класичний фіт — щільна бавовна, DTF-друк, доставка Новою По…` |
| `https://twocomms.shop/en/product/red-leaves-ts/classic/` | 168 | `T-shirt «Red Leaves», класичний фіт — щільна бавовна, DTF-друк, доставка Новою П…` |
| `https://twocomms.shop/ru/product/classic-tshirt/oversize/` | 168 | `Футболка классическая, оверсайз фіт — щільна бавовна, DTF-друк, доставка Новою П…` |
| `https://twocomms.shop/custom-print/` | 169 | `Кастомний DTF-конфігуратор для худі, футболок, лонгслівів і свого одягу. Зберіть…` |
| `https://twocomms.shop/en/product/death-gbs-ass-ts/classic/` | 169 | `T-shirt «Last Breath», класичний фіт — щільна бавовна, DTF-друк, доставка Новою …` |
| `https://twocomms.shop/product/red-leaves-ts/classic/` | 169 | `Футболка «Red Leaves», класичний фіт — щільна бавовна, DTF-друк, доставка Новою …` |
| `https://twocomms.shop/ru/product/red-leaves-ts/classic/` | 169 | `Футболка «Red Leaves», класичний фіт — щільна бавовна, DTF-друк, доставка Новою …` |
| `https://twocomms.shop/en/product/last-breath/oversize/` | 171 | `T-shirt «Skull and Rose», оверсайз фіт — щільна бавовна, DTF-друк, доставка Ново…` |
| `https://twocomms.shop/ru/pro-brand/` | 171 | `TwoComms — украинский streetwear / military-adjacent бренд одежды из Харькова. В…` |
| `https://twocomms.shop/ru/product/last-breath/oversize/` | 171 | `Футболка «Череп С Розой», оверсайз фіт — щільна бавовна, DTF-друк, доставка Ново…` |
| `https://twocomms.shop/en/product/last-breath/classic/` | 172 | `T-shirt «Skull and Rose», класичний фіт — щільна бавовна, DTF-друк, доставка Нов…` |
| `https://twocomms.shop/product/death-gbs-ass-ts/classic/` | 172 | `Футболка «Череп с дупою», класичний фіт — щільна бавовна, DTF-друк, доставка Нов…` |

… и ещё 27.

Большинство «слишком длинных» description (160-184 ch) — не критично: Google обрежет до 155-160ch в SERP, но снаружи ничего не ломает. Главная боль — **UA-only содержимое на /ru/ /en/**, а не длина.

### H1 missing/empty: 0

Все 150 страниц имеют непустой H1. ✅

## Recommendations (prioritised)

### P0 — блокирующее

1. **Перевести `Product.description` / `short_description` / `seo_description` / `seo_keywords` на RU и EN.** Сейчас 65 продуктов × 3 поля × 2 локали = ~390 пустых полей. Текстовые поля зарегистрированы в `storefront/translation.py:42-54`, но залиты только `*_uk`. Без RU/EN переводов meta description / og:description / Product JSON-LD `description` всегда уходят в UA fallback. → Запустить i18n-batch в админке (или autofill через AI с переводом).

2. **Заменить f-string-builders в `storefront/services/variant_meta.py` на gettext-обёрнутые шаблоны** (lines ~152-178). Это в одном файле и лечит 36+ утечек на fit-страницах и 30+ на color/size-variant страницах:

   ```python
   page_description = _(
       "{product_title}, {fit_lc} фіт — щільна бавовна, "
       "DTF-друк, доставка Новою Поштою по всій Україні за 1–3 дні. "
       "Лаконічний стрітвеар від українського бренду TwoComms."
   ).format(product_title=…, fit_lc=…)
   # затем: makemessages → перевести → compilemessages
   ```

3. **Починить `/contacts/` на проде.** Все 3 локали отдают HTTP 500. Это **полностью убирает страницу из индекса** (Google de-indexes 5xx URLs за дни). Чек-лист: `tail -200 django.log | grep -A20 contacts`. Если упало после моего параллельного скана — скорее всего просто app-server overloaded, перезапустить passenger. Если же 500 воспроизводимый — это P0 баг.

4. **Пересобрать `.mo` на проде.** Translations `«Харків, Україна» → «Харьков как ДНК»` / `Kharkiv as DNA` лежат в `locale/ru/django.po` (L594) и `locale/en/django.po` (L603), но прод не применяет их. Что добавить в deploy: `python manage.py compilemessages -l ru -l en`.

5. **Verify `with translation.override(locale)` в JSON-LD builders.** Если перерендер работает в правильном языке, то после fix #4 `Organization.foundingLocation.name` сразу станет переводиться. Проверить `storefront/seo_utils.py:1037` и место, где собирается Organization JSON-LD — что в момент рендера активна нужная локаль (`request.LANGUAGE_CODE`).

### P1 — высокий

6. **Перевести seed-данные `storefront/migrations/0054_phase10c_extended_seo_copy.py`** в `name_ru` / `description_ru` / `name_en` / `description_en` для всех категорий и SEO-блоков (или вынести в отдельный data-migration `0064_translate_seed_to_ru_en.py`).

7. **Переключить hardcoded UA-фразы в builder-сервисах на gettext:**
   - `storefront/services/product_seo_autofill.py:82-86, 116, 124-127, 214-228` — все f-string'и с `авторський {nom} TwoComms` / `Авторський дизайн TwoComms` нужно обернуть `_()`.
   - `storefront/services/product_copy_v2.py:337-354` — fallback intro_short / intro_long / faq.
   - `storefront/services/color_seo_copy.py:602-712` — color×category SEO copy.

8. **Сократить description до ≤155-160ch** где она >160ch (47 страниц). Большинство — категорийные SEO-meta, которые Google и так обрежет, но это удерживает CTR в SERP. Скорректировать в `storefront/support_content.py` (для статики) и `storefront/services/product_seo_autofill.py:_build_seo_description` (для PDP).

### P2 — средний / косметика

9. **Удлинить 14 «слишком коротких» titles до 30-50ch.** В основном статика — `/contacts/`, `/cooperation/`, `/wholesale/`. Использовать SERP-budget полностью.

10. **Color-category landings** — sitemap-color-categories.xml пустой (0 URL), при этом view и модель `CategoryColorLanding` живут (`storefront/models.py:2256+`, `storefront/views/catalog.py:826`). Либо опубликовать их (через `is_published=True`), либо удалить sitemap-секцию из index. Сейчас выглядит как заглушка, на которую Google пингуется впустую.

11. **Добавить в `storefront/services/variant_meta.py` тест на cross-language** в стиле property-теста: для каждого `(uk, ru, en)` × `(fit, color, size)` ожидать, что description содержит хотя бы один маркер целевой локали. Пред-otherwise тест-suite проходит, но регрессия не ловится (всё чистый UA).

## Артефакты сканера

- `_audit/urls_all.txt` — все 519 URL из sitemap-index.
- `_audit/urls_sample.txt` — выбранный сэмпл 153 URL.
- `_audit/raw_results.json` — полный raw-вывод сканера (HTML-метаданные).
- `_audit/raw_results_filtered.json` — после второго прохода детектора с word-boundary матчингом.
- `_audit/summary.json` — агрегации (поля/фразы/локали).
- `_audit/source_trace.json` — top-30 phrase clusters + grep-источники.
- `_audit/phase6_compare.json` — UA/RU/EN parity сравнение.
- `/tmp/_audit_seo.json` — копия raw для повторного использования.

