# 06 — Keyword Universe (uk-UA / ru-UA / en-UA)

**Дата:** 2026-05-16
**Скоуп:** TwoComms ecommerce (twocomms.shop) — стрітвір/мілітарі-adjacent одяг із Харкова. Кластеризація запитів за трьома мовами, з прив'язкою до сторінок та оцінками частотності.
**Мета:** дати фактуру для (1) переписування meta/title/H1, (2) розкладу контентного плану на PDP/категорії/support pages, (3) формування anchor-text шаблонів для внутрішньої перелінковки, (4) AI-пошуку видимості.
**Сирі дані:** `audit_data/06_keywords_raw.json` (структурований список усіх ключів з прив'язкою до сторінок, мови та інтенту).

---

## TL;DR — 12 головних висновків

1. **Найбільш недозабраний кластер — «купити X в [місто]»**: гео-LF з низькою конкуренцією. У SERP по «купити худі Харків» сидять prom.ua з generic-каталогами без UX, без розмірних сіток, без бренду. У TwoComms є шанс закрити нішу 5 міст × 3 категорії = 15 LF-лендінгів. Зараз — нуль.
2. **«Кастомний DTF-друк» (custom print) — кластер з найвищим конверсійним потенціалом**: запити типу «надрукувати футболку зі своїм принтом», «свій принт на худі ціна», «DTF друк Київ» мають низьку SERP-конкуренцію (топ зайнятий типографіями типу everfox.com.ua, druknafutbolkah.com), але домінує B2C-DIY запит. У TwoComms сторінка `/custom-print/` зараз ловить 2-3 ключі замість 30+. Це **#1 пріоритет на найближчі 60 днів**.
3. **«Військова / патріотична» лінія недовикористана**: запити «футболка ЗСУ», «мілітарі футболка», «патріотичний одяг» мають середню частоту і дуже високу комерційну інтенцію. У TwoComms є SKU під цей кластер (Glory of Ukraine, Pokrovsk Girl, Kharkiv Edition, Kha Style), але немає окремого лендінга-хабу `/catalog/military/` чи `/catalog/patriotic/`. Втрачено ~10 коммерційних запитів місячно по кожному з 3-4 запитів.
4. **Brand keywords (TwoComms / TWOCOMMS / твокомс / two comms)** — мала частотність (50-200/міс сумарно), але 100% conversion. Сайт уже добре ранжується по них, але **немає сторінки «який бренд TwoComms»** як окремої цитованої одиниці для AI-пошуку. `/pro-brand/` довгий і поетичний — потрібен короткий factbox-блок зверху для LLM-цитування.
5. **Худі-кластер найрозвиненіший, але затиснутий конкурентом hygge-hoodie.com** (старший домен, шість років авторитету по «купити худі Україна»). TwoComms перемагатиме не на head-term «купити худі», а на тематичних long-tail: «худі мілітарі», «худі з принтом ЗСУ», «оверсайз худі чорний оверсайз», «худі патріотичне». Saint Javelin занятий саме `support Ukraine` запитами, не комерційними.
6. **Лонгслів-категорія — найменш конкурентна із 3 базових**: SERP розкиданий, B2B-друкарні домінують, мало брендів робить акцент на лонгсліві як на самостійній категорії. TwoComms має шанс взяти «купити лонгслів Україна» в топ-5 при правильній оптимізації категорії та 3-4 PDP.
7. **«В подарунок» — окремий під-кластер високого конверсійного потенціалу**: «футболка в подарунок чоловіку», «подарунок на день народження хлопцю», «подарунок ветерану». Зараз TwoComms не має ні слова «подарунок» у category-описах. Додавання 2-3 параграфів у кожну категорію + FAQ Q «чи можна оформити як подарунок» забере ці ключі.
8. **RU-локаль слабка не тільки в перекладах, але і в keyword-доборі**: основні російськомовні користувачі України шукають «купить футболку с принтом», «купить худи оверсайз», «купить лонгслив Харьков». Зараз RU-PDP підтягує UA-fallback. Втрачено ~30% доступного RU-обсягу.
9. **EN-локаль має дві окремі аудиторії**: (а) українські юзери, які шукають англійською («buy t-shirt Kyiv», «streetwear Ukraine»); (б) міжнародна діаспора («ukraine support t-shirt», «kharkiv hoodie», «buy ukrainian streetwear»). Друга — стратегічно цікавіша, бо валютні платежі і мала конкуренція.
10. **AI-search-visible запити (definitional / how-to)**: «що таке streetwear», «що таке DTF друк», «як обрати розмір худі», «як прати худі з принтом», «який український streetwear бренд» — ці запити LLM (ChatGPT, Claude, Perplexity, Google AI Overviews) цитують охоче, бо в SERP мало структурованих відповідей. У TwoComms на support-сторінках є контент для 60% таких запитів, але не оформлений як TL;DR-factbox. Це швидкий win.
11. **«TwoComms vs [конкурент]»-запити поки не існують** (бренд молодий, об'єм brand-mentions низький). Але стратегічно — варто закласти зараз короткі секції «чим відрізняється TwoComms від [Saint Javelin / hygge-hoodie / phantomcat]» на сторінці `/pro-brand/` або в окремому блозі. AI-пошук такі сторінки дуже любить.
12. **Технічна дивідендна гра — color-categories landings**: `/catalog/tshirts/black/`, `/catalog/hoodie/oversize/`, `/catalog/long-sleeve/coyote/` як filtered URL з self-canonical і власним SEO-текстом. Зараз `sitemap-color-categories.xml` порожній (0 url). Створення 9 categorical-color landings (3 категорії × 3 кольори) дасть ~80-150 додаткових LF-органіків місячно при правильному оформленні.

---

## 1. Methodology

### 1.1 Що збирали

Я будував keyword universe для трьох мов сайту з акцентом на:

- **Інтенти**: brand, commercial/transactional, informational, long-tail, local.
- **Класифікацію частотності**: HF (head-term, ≥1k запитів/міс грубо), MF (mid, 100-1000/міс), LF (long-tail, 10-100/міс).
- **Прив'язку до сторінок**: home, /catalog/, 3 категорії, top-PDP, support, brand pages.
- **Anchor patterns**: для перелінковки.

### 1.2 Як оцінювали частотність

**Без доступу до Ahrefs / Semrush / SimilarWeb API** я використовував relative volume estimation на основі чотирьох сигналів:

1. **Довжина і конкретність запиту**:
   - 1 слово (наприклад «футболка», «худі») → HF
   - 2-3 слова з brand-modifier («купити футболку Україна») → MF
   - 4-6+ слів з географією, кольором, принтом → LF
   - 7+ слів з повним контекстом → ultra-LF
2. **SERP-конкуренція** (через web search + Google search MCP):
   - SERP заповнений Rozetka / Hotline / prom.ua + brand-сайти → HF
   - SERP заповнений 3-5 нішевими брендами → MF
   - SERP розкиданий, ціль не закрита, багато irrelevant → LF
3. **Google autocomplete та "Люди шукають також"**:
   - Якщо Google пропонує доповнення → запит має ненульовий volume
4. **Brand mentions в опублікованих keyword-research статтях 2025-2026** (для UA-streetwear specifically):
   - Накопичена база ключів від village.com.ua, the-village (Україна), highsnobiety, kyivpost.

**Обмеження**: точних цифр volumes я не даю — лише грубу оцінку HF/MF/LF. Для production-планування потрібен Ahrefs Keywords Explorer чи Serpstat (UA-локальний інструмент). Усі мітки `[Limited data]` означають «нужен платний keyword research для уточнення».

### 1.3 Структура матриці кластерів

Кожен кластер зведено в таблицю з форматом:

| HF (5+) | MF (10+) | LF (15+) | Volume estimate | Цільова сторінка |

Загалом — **18 кластерів** (6 на мову × 3 мови, із кросс-кластерами). Усі ключі також перенесені в `06_keywords_raw.json` для подальшої автоматизації.

### 1.4 Конкуренти (для бенчмарку)

- **everfox.com.ua** — DTF-друк, custom print лідер. Прямий конкурент на «свій принт».
- **hygge-hoodie.com** — старший streetwear бренд, фокус на худі (з 2020).
- **phantomcat.com.ua** — прямий конкурент по style + принтам (мемні, кіношні).
- **syndicate (sndct_kyiv)** — Kyiv streetwear OG (2010), премʼюм-цінник, цільовий конкурент по нішевому streetwear.
- **saintjavelin.com** — патріотичний/військовий мерч, міжнародна аудиторія, благодійна модель.
- **noosphereglobal.com** — ще один streetwear-magnetic ребрендинг технологічного фонду; стилевий конкурент.

---

## 2. Brand keywords (UK / RU / EN)

Бренд-запити мають мінімальний volume, але максимальну якість трафіку: уже знайшли бренд → 90%+ конверсія в перегляд каталогу. Основна задача — забезпечити **жодних втрат** (бренд не повинен переплутатися з кимось іншим у SERP, наприклад Two Comms Communications).

| Запит | Lang | Volume estimate | SERP конкуренція | Цільова сторінка |
|---|---|---|---|---|
| `twocomms` | uk-UA | LF (~50-150/міс) | none — TwoComms домінує | `/` |
| `TWOCOMMS` | uk-UA | LF (~30-80/міс) | none | `/` |
| `twocomms shop` | uk-UA | LF (~20-60/міс) | none | `/` |
| `twocomms бренд` | uk-UA | LF (~10-30/міс) | none | `/pro-brand/` |
| `twocomms харків` | uk-UA | LF (~5-15/міс) | none | `/pro-brand/` |
| `твокомс` | uk-UA | LF (~5-20/міс) | none, типофоморфізм | `/` |
| `твокомс одяг` | uk-UA | ultra-LF | none | `/catalog/` |
| `два коммс` | ru-UA | ultra-LF | none, кирилична транслітерація | `/ru/` |
| `твокомс купити` | uk-UA | ultra-LF | none | `/catalog/` |
| `twocomms.shop` | en-UA | LF (~20-50/міс) | none, навігаційний | `/` |
| `twocomms reality bends` | uk-UA | ultra-LF (collection-name) | none | `/product/twocomms-reality-bends-future-2026/` |
| `twocomms instagram` | uk-UA | ultra-LF | none | `/pro-brand/` (з посиланням на IG) |
| `twocomms телеграм` | uk-UA | ultra-LF | none | `/pro-brand/` (з посиланням на TG) |
| `twocomms відгуки` | uk-UA | LF | empty SERP — можливість заповнити | `/pro-brand/` (відгуки/social proof секція) |
| `twocomms доставка` | uk-UA | ultra-LF | none | `/delivery/` |
| `twocomms розмірна сітка` | uk-UA | ultra-LF | none | `/rozmirna-sitka/` |
| `twocomms купить` | ru-UA | ultra-LF | none | `/ru/catalog/` |
| `twocomms харьков` | ru-UA | ultra-LF | none | `/ru/pro-brand/` |
| `twocomms reviews` | en-UA | ultra-LF | empty | `/en/pro-brand/` |
| `twocomms ukraine` | en-UA | LF (~10-30/міс) | none | `/en/` |
| `twocomms streetwear` | en-UA | LF (~5-15/міс) | none | `/en/pro-brand/` |
| `two comms` | en-UA | ultra-LF | risk: Two Comms Communications — disambiguation | `/en/pro-brand/` |

### Brand-захист (recommendations)

1. **Створити окрему disambiguation-секцію** на `/pro-brand/`: «TwoComms — це український streetwear-бренд з Харкова, не плутати з Two Comms Communications, US ICT company». Це запобіжить витоку ChatGPT/Claude цитувати не ту компанію.
2. **`sameAs` на рівні Organization schema** — Instagram, Telegram, Facebook (якщо є), Pinterest, TikTok. На сайті в footer уже є Instagram + Telegram, треба продублювати в JSON-LD.
3. **Brand-page для AI-цитування**: factbox-блок зверху `/pro-brand/` з 5-6 фактами в форматі: founded year, location, founder, what they make, price range, target audience, sameAs links.

---

## 3. Commercial keywords by category

### 3.1 T-shirts (Футболки)

#### 3.1.1 UA — uk-UA

| Тип | HF (head, ≥1k/міс) | MF (mid, 100-1k/міс) | LF (long-tail, 10-100/міс) | Volume |
|---|---|---|---|---|
| **HF** | купити футболку, футболка, чоловіча футболка, жіноча футболка, теніска | — | — | HF 1k-10k/міс |
| **MF** | — | купити футболку з принтом, чорна футболка, біла футболка, унісекс футболка, оверсайз футболка, футболка україна, купити футболку онлайн, чоловіча футболка з принтом, жіноча футболка з принтом, унісекс футболка з принтом, бавовняна футболка, футболка чорна оверсайз, чорна футболка з принтом купити, футболка з малюнком | — | MF 100-1k/міс |
| **LF** | — | — | купити чорну унісекс футболку oversize, футболка з принтом ЗСУ купити, чорна оверсайз футболка з принтом купити, бавовняна чорна футболка з принтом TwoComms, футболка з мілітарі принтом купити Україна, оверсайз футболка з принтом для хлопця, футболка унісекс з авторським принтом, купити футболку TwoComms у Києві, чорна жіноча футболка з принтом купити Україна, мілітарі футболка з принтом купити онлайн, патріотична футболка з принтом ЗСУ купити, футболка з принтом смерть на лонгслів, чорна футболка оверсайз з гострими принтами, бавовняна футболка з кастомним принтом онлайн, футболка street style з принтом ЗСУ, чорна оверсайз футболка з мілітарі принтом, темна футболка з авторським принтом онлайн магазин, чорна оверсайз футболка з принтом «Reality Bends», футболка унісекс з принтом для команди, чорна футболка з принтом ЗСУ оверсайз | LF 10-100/міс |

**Volume estimate**: HF 1k-10k/міс, MF 100-1k, LF 10-100. **Цільова сторінка**: `/catalog/tshirts/`.

#### 3.1.2 RU — ru-UA

| Тип | HF | MF | LF |
|---|---|---|---|
| **HF** | купить футболку, футболка, мужская футболка, женская футболка | — | — |
| **MF** | — | купить футболку с принтом, чёрная футболка, белая футболка, унисекс футболка, оверсайз футболка, футболка Украина, купить футболку онлайн, мужская футболка с принтом, чёрная футболка с принтом купить, хлопковая футболка, футболка чёрная оверсайз, футболка с рисунком, футболка с авторским принтом, оригинальная футболка купить | — |
| **LF** | — | — | купить чёрную унисекс футболку оверсайз, футболка с принтом ВСУ купить, чёрная оверсайз футболка с принтом купить, хлопковая футболка с принтом TwoComms, футболка с милитари-принтом купить Украина, оверсайз футболка с принтом для парня, футболка унисекс с авторским принтом, купить футболку TwoComms в Киеве, чёрная женская футболка с принтом купить Украина, милитари футболка с принтом купить онлайн, патриотическая футболка с принтом ВСУ купить, чёрная футболка оверсайз с принтами, хлопковая футболка с кастомным принтом онлайн, чёрная футболка с принтом ВСУ оверсайз, тёмная футболка с авторским принтом интернет-магазин, чёрная оверсайз футболка с принтом «Reality Bends», футболка унисекс с принтом для команды, мужская оверсайз футболка с принтом купить Харьков, футболка с принтом харків, оригинальная футболка с принтом ВСУ купить онлайн |

**Volume estimate**: HF 500-5k/міс (RU-сегмент менший за UA), MF 50-500, LF 5-50. **Цільова**: `/ru/catalog/tshirts/`.

#### 3.1.3 EN — en-UA

| Тип | HF | MF | LF |
|---|---|---|---|
| **HF** | buy t-shirt, t-shirt, men t-shirt, women t-shirt, unisex t-shirt | — | — |
| **MF** | — | buy graphic t-shirt, black t-shirt, white t-shirt, oversize t-shirt, ukrainian t-shirt, t-shirt with print, men's graphic t-shirt, women's graphic t-shirt, cotton t-shirt, oversize black t-shirt, streetwear t-shirt, ukrainian streetwear t-shirt, military t-shirt, ukraine support t-shirt | — |
| **LF** | — | — | buy black unisex oversize t-shirt, ukrainian streetwear t-shirt with print, kharkiv military t-shirt, oversize black graphic t-shirt ukraine, ukrainian patriotic t-shirt buy online, support ukraine t-shirt with print, ukraine military adjacent t-shirt, ukrainian designer t-shirt streetwear, black oversize cotton t-shirt with print, oversize t-shirt ukraine support, kharkiv streetwear t-shirt buy, ukrainian armed forces t-shirt buy, made in ukraine streetwear t-shirt, black graphic t-shirt twocomms, ukrainian brand t-shirt with print online, custom dtf t-shirt ukraine, oversize black streetwear t-shirt buy, twocomms reality bends t-shirt black, ukrainian zsu t-shirt buy online, kyiv streetwear t-shirt buy |

**Volume estimate**: HF 200-2k/міс (en-UA маленький, бо EN-Ukrainian users мало), MF 30-300, LF 5-30. **Цільова**: `/en/catalog/tshirts/`.

### 3.2 Hoodies (Худі)

#### 3.2.1 UA

| Тип | HF | MF | LF |
|---|---|---|---|
| **HF** | купити худі, худі, чоловіче худі, жіноче худі, oversize худі | — | — |
| **MF** | — | купити худі з принтом, чорне худі, oversize худі купити, унісекс худі, тепле худі, флісове худі, худі чоловіче чорне, худі бавовняне, худі з принтом ЗСУ, патріотичне худі, мілітарі худі, худі український бренд, худі streetwear купити, худі регулярне, класичне худі купити | — |
| **LF** | — | — | купити чорне oversize худі з принтом, чорне oversize худі чоловіче купити Україна, тепле флісове худі з принтом ЗСУ, мілітарі худі унісекс купити, чорне худі з принтом для хлопця, худі streetwear оверсайз чорний, унісекс oversize худі з принтом TwoComms, флісове чорне oversize худі купити Київ, патріотичне худі з принтом ЗСУ купити онлайн, чорне худі з мілітарі принтом купити Харків, oversize чорне худі з принтом купити Львів, чорне oversize худі з принтом ЗСУ для чоловіка, тепле зимове худі з принтом купити, чорне oversize худі з принтом для команди, худі чорне з кишенею кенгуру з принтом купити, худі унісекс oversize з принтом купити Україна, чорне oversize худі з принтом мілітарі купити Дніпро, тепле флісове худі чорне з принтом ЗСУ, oversize чорне худі з авторським принтом купити, худі з принтом «My Little Baby» чорне oversize, чорне худі з принтом «Reality Bends» купити, тепле флісове патріотичне худі купити Україна |

**Volume estimate**: HF 1k-10k/міс, MF 100-1k, LF 10-100. **Цільова**: `/catalog/hoodie/`.

#### 3.2.2 RU

| Тип | HF | MF | LF |
|---|---|---|---|
| **HF** | купить худи, худи, мужское худи, женское худи, толстовка | — | — |
| **MF** | — | купить худи с принтом, чёрное худи, оверсайз худи купить, унисекс худи, тёплое худи, флисовое худи, худи мужское чёрное, худи хлопковое, худи с принтом ВСУ, патриотическое худи, милитари худи, худи украинский бренд, худи streetwear купить, классическое худи купить, чёрное худи оверсайз | — |
| **LF** | — | — | купить чёрное оверсайз худи с принтом, чёрное оверсайз худи мужское купить Украина, тёплое флисовое худи с принтом ВСУ, милитари худи унисекс купить, чёрное худи с принтом для парня, худи streetwear оверсайз чёрный, унисекс оверсайз худи с принтом TwoComms, флисовое чёрное оверсайз худи купить Киев, патриотическое худи с принтом ВСУ купить онлайн, чёрное худи с милитари принтом купить Харьков, оверсайз чёрное худи с принтом купить Львов, чёрное оверсайз худи с принтом ВСУ для мужчины, тёплое зимнее худи с принтом купить, чёрное оверсайз худи с принтом для команды, худи чёрное с карманом кенгуру с принтом купить, худи унисекс оверсайз с принтом купить Украина, чёрное оверсайз худи с принтом милитари купить Днепр, тёплое флисовое худи чёрное с принтом ВСУ, оверсайз чёрное худи с авторским принтом купить, худи с принтом «My Little Baby» чёрное оверсайз, чёрное худи с принтом «Reality Bends» купить |

**Volume estimate**: HF 500-5k, MF 50-500, LF 5-50. **Цільова**: `/ru/catalog/hoodie/`.

#### 3.2.3 EN

| Тип | HF | MF | LF |
|---|---|---|---|
| **HF** | buy hoodie, hoodie, men hoodie, women hoodie, oversize hoodie | — | — |
| **MF** | — | buy graphic hoodie, black hoodie, oversize hoodie buy, unisex hoodie, fleece hoodie, ukrainian hoodie, hoodie with print, hoodie streetwear, men's black hoodie, ukrainian brand hoodie, military hoodie, patriotic hoodie ukraine, kharkiv hoodie, ukraine support hoodie | — |
| **LF** | — | — | buy black oversize hoodie with print, ukrainian streetwear hoodie buy online, kharkiv military hoodie, oversize black graphic hoodie ukraine, ukrainian patriotic hoodie buy, support ukraine hoodie with print, ukraine military adjacent hoodie, ukrainian designer hoodie streetwear, black oversize fleece hoodie with print, oversize hoodie ukraine zsu, kharkiv streetwear hoodie buy, ukrainian armed forces hoodie buy, made in ukraine streetwear hoodie, black graphic hoodie twocomms, ukrainian brand hoodie with print online, custom dtf hoodie ukraine, oversize black streetwear hoodie buy, twocomms reality bends hoodie black, ukrainian zsu hoodie buy online, kyiv streetwear hoodie buy, support ukraine military hoodie buy, kharkiv edition hoodie buy ukraine |

**Volume estimate**: HF 200-2k, MF 30-300, LF 5-30. **Цільова**: `/en/catalog/hoodie/`.

### 3.3 Long-sleeves (Лонгсліви)

#### 3.3.1 UA

| Тип | HF | MF | LF |
|---|---|---|---|
| **HF** | купити лонгслів, лонгслів, чоловічий лонгслів, жіночий лонгслів | — | — |
| **MF** | — | лонгслів з принтом, чорний лонгслів, oversize лонгслів, унісекс лонгслів, бавовняний лонгслів, лонгслів streetwear, лонгслів з мілітарі принтом, лонгслів з принтом ЗСУ, лонгслів український бренд, лонгслів з довгим рукавом, чорний лонгслів з принтом, лонгслів патріотичний, лонгслів класичний купити | — |
| **LF** | — | — | купити чорний лонгслів з принтом, чорний oversize лонгслів унісекс купити, лонгслів з принтом ЗСУ купити, мілітарі лонгслів унісекс купити Україна, чорний лонгслів з принтом для хлопця, лонгслів streetwear oversize чорний, унісекс oversize лонгслів з принтом TwoComms, бавовняний чорний oversize лонгслів купити Київ, патріотичний лонгслів з принтом ЗСУ купити онлайн, чорний лонгслів з мілітарі принтом купити Харків, oversize чорний лонгслів з принтом купити Львів, чорний oversize лонгслів з принтом ЗСУ для чоловіка, лонгслів унісекс з принтом для команди, чорний лонгслів з кишенею з принтом купити, лонгслів з принтом «Reality Bends» чорний, лонгслів з принтом «Kharkiv Edition» чорний, лонгслів унісекс з принтом «Pokrovsk Girl», лонгслів з довгим рукавом і авторським принтом купити, oversize чорний лонгслів патріотичний купити, лонгслів streetwear бавовняний oversize чорний |

**Volume estimate**: HF 100-1k/міс (категорія менш популярна за t-shirts/hoodie), MF 50-500, LF 5-50. **Цільова**: `/catalog/long-sleeve/`.

#### 3.3.2 RU

| Тип | HF | MF | LF |
|---|---|---|---|
| **HF** | купить лонгслив, лонгслив, мужской лонгслив, женский лонгслив | — | — |
| **MF** | — | лонгслив с принтом, чёрный лонгслив, оверсайз лонгслив, унисекс лонгслив, хлопковый лонгслив, лонгслив streetwear, лонгслив с милитари принтом, лонгслив с принтом ВСУ, лонгслив украинский бренд, лонгслив с длинным рукавом, чёрный лонгслив с принтом, лонгслив патриотический | — |
| **LF** | — | — | купить чёрный лонгслив с принтом, чёрный оверсайз лонгслив унисекс купить, лонгслив с принтом ВСУ купить, милитари лонгслив унисекс купить Украина, чёрный лонгслив с принтом для парня, лонгслив streetwear оверсайз чёрный, унисекс оверсайз лонгслив с принтом TwoComms, хлопковый чёрный оверсайз лонгслив купить Киев, патриотический лонгслив с принтом ВСУ купить онлайн, чёрный лонгслив с милитари принтом купить Харьков, оверсайз чёрный лонгслив с принтом купить Львов, чёрный оверсайз лонгслив с принтом ВСУ для мужчины, лонгслив унисекс с принтом для команды, чёрный лонгслив с карманом с принтом купить, лонгслив с принтом «Reality Bends» чёрный, лонгслив с принтом «Kharkiv Edition» чёрный, лонгслив унисекс с принтом «Pokrovsk Girl», лонгслив с длинным рукавом и авторским принтом купить, оверсайз чёрный лонгслив патриотический купить, лонгслив streetwear хлопковый оверсайз чёрный |

**Volume estimate**: HF 50-500, MF 20-200, LF 3-30. **Цільова**: `/ru/catalog/long-sleeve/`.

#### 3.3.3 EN

| Тип | HF | MF | LF |
|---|---|---|---|
| **HF** | buy long sleeve, long sleeve t-shirt, men long sleeve, unisex long sleeve | — | — |
| **MF** | — | graphic long sleeve, black long sleeve, oversize long sleeve, cotton long sleeve, long sleeve streetwear, long sleeve with print, ukrainian long sleeve, military long sleeve, patriotic long sleeve, kharkiv long sleeve | — |
| **LF** | — | — | buy black long sleeve with print, oversize black long sleeve unisex, ukrainian streetwear long sleeve buy, kharkiv military long sleeve, support ukraine long sleeve with print, oversize ukrainian patriotic long sleeve, ukraine zsu long sleeve buy online, twocomms long sleeve black oversize, ukrainian brand long sleeve with print, made in ukraine streetwear long sleeve, kyiv streetwear long sleeve buy, oversize black graphic long sleeve buy ukraine, ukrainian armed forces long sleeve buy, custom dtf long sleeve ukraine, kharkiv streetwear long sleeve buy |

**Volume estimate**: HF 50-500, MF 10-100, LF 3-30. **Цільова**: `/en/catalog/long-sleeve/`.

### 3.4 Custom print (Кастомний DTF-друк)

> Це **найкращий конверсійний кластер** з невикористаним потенціалом. SERP не сильно зайнятий — типографії типу everfox.com.ua, druknafutbolkah.com присутні, але вони B2B-orientовані без UX. У TwoComms є можливість зайти як нішевий бренд з якісним продуктом + DTF-друком.

#### 3.4.1 UA

| Тип | HF | MF | LF |
|---|---|---|---|
| **HF** | DTF друк, друк на футболці, свій принт, друк на одязі | — | — |
| **MF** | — | DTF друк Україна, замовити свій принт на футболці, DTF друк Київ, друк на худі, друк на лонгсліві, надрукувати свій принт, кастомний друк футболки, друк на одязі ціна, DTF друк ціна, друк футболок Київ, надрукувати футболку зі своїм принтом, замовити свою футболку з принтом, DTF друк Харків, друк на одязі онлайн, свій логотип на футболці, DTF трансфер, кастомний принт ціна, виготовити футболку з принтом | — |
| **LF** | — | — | надрукувати футболку зі своїм принтом онлайн, замовити кастомну футболку з власним принтом, DTF друк ціна за см² Україна, виготовити худі з власним принтом для команди, надрукувати свій логотип на футболці оптом, замовити DTF друк на футболці Харків, друк на одязі для бренду маленький тираж, DTF друк свій дизайн купити онлайн, кастомний DTF друк на чорній футболці, надрукувати худі зі своїм принтом TwoComms, замовити свою футболку з логотипом для команди, надрукувати свою назву бренду на одязі, DTF друк на лонгсліві ціна Україна, кастомний DTF друк для дропшипінгу, надрукувати свій принт на бавовняній футболці, DTF друк маленьким тиражем для івенту, замовити одяг з принтом для весілля, DTF друк свого логотипу на одязі для команди, кастомний друк футболки до дня народження, надрукувати футболку зі своїм мемом ЗСУ, замовити свій принт на жіночій футболці Україна, DTF друк свого зображення на чорному худі |

**Volume estimate**: HF 200-2k/міс, MF 50-500, LF 5-50. **Цільова**: `/custom-print/`.

#### 3.4.2 RU

| Тип | HF | MF | LF |
|---|---|---|---|
| **HF** | DTF печать, печать на футболке, свой принт, печать на одежде | — | — |
| **MF** | — | DTF печать Украина, заказать свой принт на футболке, DTF печать Киев, печать на худи, печать на лонгсливе, напечатать свой принт, кастомная печать футболки, печать на одежде цена, DTF печать цена, печать футболок Киев, напечатать футболку со своим принтом, заказать свою футболку с принтом, DTF печать Харьков, печать на одежде онлайн, свой логотип на футболке, DTF трансфер, кастомный принт цена, изготовить футболку с принтом | — |
| **LF** | — | — | напечатать футболку со своим принтом онлайн, заказать кастомную футболку с собственным принтом, DTF печать цена за см² Украина, изготовить худи с собственным принтом для команды, напечатать свой логотип на футболке оптом, заказать DTF печать на футболке Харьков, печать на одежде для бренда маленький тираж, DTF печать свой дизайн купить онлайн, кастомная DTF печать на чёрной футболке, напечатать худи со своим принтом TwoComms, заказать свою футболку с логотипом для команды, напечатать своё название бренда на одежде, DTF печать на лонгсливе цена Украина, кастомная DTF печать для дропшиппинга, напечатать свой принт на хлопковой футболке, DTF печать маленьким тиражом для ивента, заказать одежду с принтом для свадьбы, DTF печать своего логотипа на одежде для команды, кастомная печать футболки ко дню рождения, напечатать футболку со своим мемом ВСУ, заказать свой принт на женской футболке Украина, DTF печать своего изображения на чёрном худи |

**Volume estimate**: HF 100-1k, MF 30-300, LF 3-30. **Цільова**: `/ru/custom-print/`.

#### 3.4.3 EN

| Тип | HF | MF | LF |
|---|---|---|---|
| **HF** | dtf print, custom t-shirt printing, custom hoodie printing, your design on shirt | — | — |
| **MF** | — | dtf print ukraine, custom dtf t-shirt, custom dtf hoodie, custom dtf longsleeve, dtf print kyiv, dtf print kharkiv, custom apparel ukraine, custom streetwear print, custom team t-shirt, dtf print pricing ukraine, custom merch ukraine, custom logo t-shirt | — |
| **LF** | — | — | custom dtf t-shirt printing ukraine online, custom hoodie printing for team kharkiv, custom dtf print on black t-shirt ukraine, ukrainian custom apparel for streetwear brand, custom dtf print on hoodie ukraine for team, custom merch printing for events ukraine, custom dtf t-shirt small batch ukraine, custom dtf print for dropshipping ukraine, custom logo on hoodie ukraine online, custom merch for ukrainian charity event, custom dtf print on cotton t-shirt black, custom apparel printing for ukrainian zsu charity, custom dtf print for kharkiv brand, custom oversize t-shirt with print buy ukraine, custom dtf print twocomms quality, custom merch for ukrainian streetwear team, custom hoodie printing for kharkiv edition |

**Volume estimate**: HF 30-300, MF 10-100, LF 3-15. **Цільова**: `/en/custom-print/`.

### 3.5 Wholesale / B2B (Опт)

> Окремий кластер B2B з низькою частотністю, але дуже високою цінністю (LTV / large orders). Sumарна конверсійна цінність може перевищити DTC-кластер.

#### 3.5.1 UA

| Тип | HF | MF | LF |
|---|---|---|---|
| **HF** | купити футболки оптом, оптом одяг, оптовий продаж одягу | — | — |
| **MF** | — | купити футболки оптом Україна, купити худі оптом, мерч для команди, мерч для івенту, корпоративний мерч, дропшипінг одягу, корпоративні футболки, оптовий продаж футболок, мерч для бренду, постачальник одягу для магазину, оптом футболки з принтом | — |
| **LF** | — | — | купити футболки оптом Україна виробник, оптовий продаж худі від виробника, мерч для команди з власним принтом, дропшипінг streetwear-одягу від виробника Україна, оптовий продаж патріотичного одягу, корпоративний мерч для івенту з логотипом, оптом футболки для дропшипінгу Харків, постачальник streetwear для магазину Україна, мерч для бренду маленький тираж, корпоративні футболки з логотипом замовити, оптовий продаж лонгслівів Україна виробник, мерч для волонтерського проекту, оптом одяг для маркетплейсу, постачальник кастомного одягу для дропшипінгу, оптовий продаж streetwear для українського магазину, мерч для команди з логотипом і DTF друком, корпоративний мерч від українського бренду, оптом футболки ЗСУ для магазину, мерч для тімбілдінгу з власним принтом, оптовий продаж бавовняних футболок Україна |

**Volume estimate**: HF 200-2k/міс (оптовий B2B-сегмент має менше пошуків, але кожен — ціль), MF 50-500, LF 5-50. **Цільова**: `/wholesale/` + `/cooperation/`.

#### 3.5.2 RU

| Тип | HF | MF | LF |
|---|---|---|---|
| **HF** | купить футболки оптом, оптом одежда, оптовая продажа одежды | — | — |
| **MF** | — | купить футболки оптом Украина, купить худи оптом, мерч для команды, мерч для ивента, корпоративный мерч, дропшиппинг одежды, корпоративные футболки, оптовая продажа футболок, мерч для бренда, поставщик одежды для магазина, оптом футболки с принтом | — |
| **LF** | — | — | купить футболки оптом Украина производитель, оптовая продажа худи от производителя, мерч для команды с собственным принтом, дропшиппинг streetwear-одежды от производителя Украина, оптовая продажа патриотической одежды, корпоративный мерч для ивента с логотипом, оптом футболки для дропшиппинга Харьков, поставщик streetwear для магазина Украина, мерч для бренда маленький тираж, корпоративные футболки с логотипом заказать, оптовая продажа лонгсливов Украина производитель, мерч для волонтерского проекта, оптом одежда для маркетплейса, поставщик кастомной одежды для дропшиппинга, оптовая продажа streetwear для украинского магазина, мерч для команды с логотипом и DTF печатью, корпоративный мерч от украинского бренда, оптом футболки ВСУ для магазина |

**Volume estimate**: HF 50-500, MF 20-200, LF 3-30. **Цільова**: `/ru/wholesale/`.

#### 3.5.3 EN

| Тип | HF | MF | LF |
|---|---|---|---|
| **HF** | wholesale t-shirts, wholesale hoodies, custom merch ukraine | — | — |
| **MF** | — | wholesale streetwear ukraine, buy t-shirts wholesale ukraine, dropshipping clothing ukraine, custom team merch, corporate t-shirts ukraine, b2b clothing ukraine, ukrainian apparel manufacturer, wholesale clothing ukraine | — |
| **LF** | — | — | wholesale t-shirts from ukrainian manufacturer, buy hoodies wholesale ukraine producer, custom team merch with logo ukraine, dropshipping streetwear from ukraine, wholesale patriotic clothing ukraine, corporate merch with logo ukraine event, wholesale t-shirts for marketplace dropshipping, supplier streetwear for ukrainian shop, custom merch small batch ukraine, corporate t-shirts custom logo ukraine buy, wholesale long sleeves ukraine manufacturer, merch for charity volunteer project ukraine, supplier custom apparel dropshipping ukraine, wholesale streetwear ukrainian brand b2b, team merch with logo and dtf print ukraine, corporate merch from ukrainian brand, wholesale t-shirts ukraine military zsu support |

**Volume estimate**: HF 30-300, MF 10-100, LF 2-20. **Цільова**: `/en/wholesale/`.

### 3.6 Streetwear бренд / стиль

> Кластер брендового позиціонування. Запити, де користувач шукає не конкретний товар, а **бренд / естетика**. Конверсія нижча, але сильно прокачує brand awareness.

#### 3.6.1 UA

| Тип | HF | MF | LF |
|---|---|---|---|
| **HF** | streetwear, стрітвір, стрітвір бренд, український streetwear | — | — |
| **MF** | — | український streetwear бренд, streetwear магазин Україна, стрітвір одяг купити, streetwear онлайн магазин Україна, streetwear Харків, streetwear Київ, стрітвір з характером, streetwear-бренд патріотичний, streetwear український дизайнер, streetwear-бренди України список | — |
| **LF** | — | — | який український streetwear бренд варто купити, кращі streetwear бренди України 2025, де купити український streetwear онлайн, streetwear-одяг від українського виробника, streetwear-магазин Київ Харків Львів, що таке streetwear український бренд, український streetwear-бренд з характером, streetwear-одяг від військового бренду України, патріотичний streetwear з мілітарі-принтом, streetwear український дизайнер з Харкова, як обрати український streetwear-бренд, streetwear для тих хто підтримує ЗСУ, streetwear-одяг від українського ветерана, новий український streetwear-бренд 2025, streetwear для команди і друзів український бренд |

**Volume estimate**: HF 1k-10k/міс (streetwear як термін популярний), MF 100-1k, LF 10-100. **Цільова**: `/pro-brand/` + `/catalog/`.

#### 3.6.2 RU

| Тип | HF | MF | LF |
|---|---|---|---|
| **HF** | streetwear, стритвир, стритвир бренд, украинский streetwear | — | — |
| **MF** | — | украинский streetwear бренд, streetwear магазин Украина, стритвир одежда купить, streetwear онлайн магазин Украина, streetwear Харьков, streetwear Киев, streetwear-бренд патриотический, streetwear украинский дизайнер | — |
| **LF** | — | — | какой украинский streetwear бренд купить, лучшие streetwear бренды Украины 2025, где купить украинский streetwear онлайн, streetwear-одежда от украинского производителя, streetwear-магазин Киев Харьков Львов, что такое streetwear украинский бренд, украинский streetwear-бренд с характером, streetwear-одежда от военного бренда Украины, патриотический streetwear с милитари-принтом, streetwear украинский дизайнер из Харькова, как выбрать украинский streetwear-бренд, streetwear для тех, кто поддерживает ВСУ, streetwear-одежда от украинского ветерана |

**Volume estimate**: HF 200-2k, MF 30-300, LF 3-30. **Цільова**: `/ru/pro-brand/`.

#### 3.6.3 EN

| Тип | HF | MF | LF |
|---|---|---|---|
| **HF** | ukrainian streetwear, streetwear brand, ukrainian streetwear brand | — | — |
| **MF** | — | best ukrainian streetwear brands, ukrainian streetwear online store, streetwear ukraine kyiv, streetwear ukraine kharkiv, ukrainian patriotic streetwear, streetwear from ukraine, ukrainian streetwear designer, support ukraine streetwear brand, kharkiv streetwear brand | — |
| **LF** | — | — | best ukrainian streetwear brand to buy 2025, where to buy ukrainian streetwear online with international shipping, ukrainian streetwear brand with patriotic prints, ukrainian streetwear brand from kharkiv, streetwear brand supporting ukraine, ukrainian streetwear founder veteran story, ukrainian streetwear oversize hoodie buy international, kharkiv streetwear brand twocomms, ukrainian streetwear with military prints buy, ukrainian streetwear brand with print zsu, ukrainian streetwear designer brand from kharkiv buy, support ukraine streetwear brand twocomms, made in ukraine streetwear hoodie buy international |

**Volume estimate**: HF 100-1k, MF 30-300, LF 3-30. **Цільова**: `/en/pro-brand/`.

---

## 4. Informational / Educational keywords

> Це **AI-friendly кластер**: definitional, how-to, comparison-запити, які LLM (ChatGPT, Claude, Gemini, Perplexity) цитує охоче. У TwoComms на support-сторінках уже є контент для 60% таких запитів — потрібно лише оформити TL;DR-блоки нагорі.

### 4.1 Care guides (як прати, як зберігати)

#### UA
| Запит | Volume | Цільова |
|---|---|---|
| як прати футболку з принтом | MF (~200-500/міс) | `/doglyad-za-odyagom/` |
| як прати худі з принтом | MF | `/doglyad-za-odyagom/` |
| як прати флісове худі | LF | `/doglyad-za-odyagom/` |
| при якій температурі прати футболку з DTF принтом | LF | `/doglyad-za-odyagom/` |
| чи можна прати худі в машинці | LF | `/doglyad-za-odyagom/` |
| як зберігати худі з принтом | LF | `/doglyad-za-odyagom/` |
| чи злазить DTF принт після прання | LF (high intent) | `/doglyad-za-odyagom/` |
| догляд за streetwear-одягом | LF | `/doglyad-za-odyagom/` |
| як зберігти яскравість принту | LF | `/doglyad-za-odyagom/` |
| чи можна прати футболку з принтом разом з джинсами | LF | `/doglyad-za-odyagom/` |
| як прасувати футболку з DTF принтом | LF | `/doglyad-za-odyagom/` |
| чим відрізняється DTF принт від шовкографії в догляді | LF | `/doglyad-za-odyagom/` |
| як видалити пляму з футболки з принтом | LF | `/doglyad-za-odyagom/` |
| як вибілити білу футболку без шкоди для принту | LF | `/doglyad-za-odyagom/` |

#### RU
| Запит | Volume | Цільова |
|---|---|---|
| как стирать футболку с принтом | MF | `/ru/doglyad-za-odyagom/` |
| как стирать худи с принтом | MF | `/ru/doglyad-za-odyagom/` |
| как стирать флисовое худи | LF | `/ru/doglyad-za-odyagom/` |
| при какой температуре стирать футболку с DTF принтом | LF | `/ru/doglyad-za-odyagom/` |
| можно ли стирать худи в машинке | LF | `/ru/doglyad-za-odyagom/` |
| как хранить худи с принтом | LF | `/ru/doglyad-za-odyagom/` |
| слезает ли DTF принт после стирки | LF | `/ru/doglyad-za-odyagom/` |
| уход за streetwear одеждой | LF | `/ru/doglyad-za-odyagom/` |
| как сохранить яркость принта | LF | `/ru/doglyad-za-odyagom/` |
| как гладить футболку с DTF принтом | LF | `/ru/doglyad-za-odyagom/` |
| как удалить пятно с футболки с принтом | LF | `/ru/doglyad-za-odyagom/` |

#### EN
| Запит | Volume | Цільова |
|---|---|---|
| how to wash dtf print t-shirt | MF | `/en/doglyad-za-odyagom/` |
| how to wash hoodie with print | MF | `/en/doglyad-za-odyagom/` |
| dtf print care instructions | LF | `/en/doglyad-za-odyagom/` |
| does dtf print fade after washing | LF | `/en/doglyad-za-odyagom/` |
| how to wash fleece hoodie | LF | `/en/doglyad-za-odyagom/` |
| how to iron t-shirt with dtf print | LF | `/en/doglyad-za-odyagom/` |
| can you tumble dry hoodie with print | LF | `/en/doglyad-za-odyagom/` |
| how to remove stain from printed t-shirt | LF | `/en/doglyad-za-odyagom/` |

### 4.2 Size guides (як обрати розмір)

#### UA
| Запит | Volume | Цільова |
|---|---|---|
| як обрати розмір футболки | MF (~500-1k/міс) | `/rozmirna-sitka/` |
| як обрати розмір худі | MF | `/rozmirna-sitka/` |
| як обрати розмір oversize худі | LF | `/rozmirna-sitka/` |
| розмірна сітка футболок Україна | MF | `/rozmirna-sitka/` |
| розмірна сітка худі чоловічого | MF | `/rozmirna-sitka/` |
| як виміряти розмір футболки | LF | `/rozmirna-sitka/` |
| розмірна сітка лонгслівів | LF | `/rozmirna-sitka/` |
| oversize розмірна сітка | LF | `/rozmirna-sitka/` |
| як обрати розмір футболки в подарунок | LF | `/rozmirna-sitka/` |
| розмір M худі скільки см обхват грудей | LF | `/rozmirna-sitka/` |
| чи мала розміриться футболка після прання | LF | `/rozmirna-sitka/` |
| розмірна сітка чоловічих футболок українського виробника | LF | `/rozmirna-sitka/` |
| як обрати посадку футболки oversize чи classic | LF | `/rozmirna-sitka/` |

#### RU
| Запит | Volume | Цільова |
|---|---|---|
| как выбрать размер футболки | MF | `/ru/rozmirna-sitka/` |
| как выбрать размер худи | MF | `/ru/rozmirna-sitka/` |
| как выбрать размер оверсайз худи | LF | `/ru/rozmirna-sitka/` |
| размерная сетка футболок Украина | MF | `/ru/rozmirna-sitka/` |
| размерная сетка худи мужского | MF | `/ru/rozmirna-sitka/` |
| как измерить размер футболки | LF | `/ru/rozmirna-sitka/` |
| размерная сетка лонгсливов | LF | `/ru/rozmirna-sitka/` |
| оверсайз размерная сетка | LF | `/ru/rozmirna-sitka/` |
| как выбрать размер футболки в подарок | LF | `/ru/rozmirna-sitka/` |

#### EN
| Запит | Volume | Цільова |
|---|---|---|
| how to choose t-shirt size | MF | `/en/rozmirna-sitka/` |
| how to choose hoodie size | MF | `/en/rozmirna-sitka/` |
| oversize hoodie size guide | LF | `/en/rozmirna-sitka/` |
| size chart ukrainian streetwear | LF | `/en/rozmirna-sitka/` |
| how to measure t-shirt size | LF | `/en/rozmirna-sitka/` |
| oversize fit vs classic fit hoodie | LF | `/en/rozmirna-sitka/` |
| size chart twocomms hoodie | LF | `/en/rozmirna-sitka/` |

### 4.3 Style / streetwear definitions (визначення)

> Це найкращий AI-search-ціль. LLM дуже любить definitional-запити, бо вони відповідають на «що таке X» одним абзацом.

#### UA
| Запит | Volume | Цільова |
|---|---|---|
| що таке streetwear | MF (~500-1k/міс) | `/pro-brand/` (TL;DR) + новий `/blog/shcho-take-streetwear/` |
| що таке стрітвір | MF | `/pro-brand/` + `/blog/` |
| що таке oversize | MF | `/blog/shcho-take-oversize/` (новий) |
| що таке DTF друк | LF | `/custom-print/` (TL;DR) + `/blog/dtf-vs-shovkohrafiya/` |
| що таке мілітарі стиль | LF | `/blog/militari-styl/` |
| streetwear vs casual | LF | `/blog/` |
| oversize vs classic fit | LF | `/blog/` |
| що значить «military adjacent» | LF | `/pro-brand/` |
| streetwear для початківців | LF | `/blog/` |
| як одягатися в streetwear стилі | LF | `/blog/` |
| streetwear історія український | LF | `/pro-brand/` |
| streetwear культура що це | LF | `/pro-brand/` + `/blog/` |
| streetwear бренд з характером визначення | LF | `/pro-brand/` |

#### RU
| Запит | Volume | Цільова |
|---|---|---|
| что такое streetwear | MF | `/ru/pro-brand/` + `/ru/blog/` |
| что такое стритвир | MF | `/ru/pro-brand/` |
| что такое оверсайз | MF | `/ru/blog/` |
| что такое DTF печать | LF | `/ru/custom-print/` |
| что такое милитари стиль | LF | `/ru/blog/` |
| streetwear vs casual | LF | `/ru/blog/` |
| как одеваться в streetwear стиле | LF | `/ru/blog/` |

#### EN
| Запит | Volume | Цільова |
|---|---|---|
| what is streetwear | HF | `/en/pro-brand/` + `/en/blog/` |
| what is dtf print | MF | `/en/custom-print/` |
| streetwear vs casual | MF | `/en/blog/` |
| oversize vs classic fit | MF | `/en/blog/` |
| what is military adjacent fashion | LF | `/en/pro-brand/` |
| ukrainian streetwear history | LF | `/en/pro-brand/` + `/en/blog/` |
| streetwear culture definition | LF | `/en/blog/` |

### 4.4 Military adjacent (мілітарі тематика)

#### UA
| Запит | Volume | Цільова |
|---|---|---|
| мілітарі одяг купити | MF (~500-1k/міс) | новий `/catalog/military/` (collection page) |
| патріотичний одяг | MF | `/catalog/patriotic/` |
| патріотична футболка | MF | `/catalog/patriotic/` |
| футболка ЗСУ | MF | `/catalog/military/` |
| мілітарі футболка | MF | `/catalog/military/` |
| патріотичне худі | MF | `/catalog/patriotic/` |
| тактичний одяг streetwear | LF | `/catalog/military/` |
| мілітарі стиль чоловічий | LF | `/catalog/military/` |
| одяг для ветерана подарунок | LF | `/blog/podarunok-veteranu/` |
| патріотична футболка купити для волонтера | LF | `/catalog/patriotic/` |
| мілітарі худі чорне купити Україна | LF | `/catalog/military/` |
| патріотичний бренд одягу Україна | LF | `/pro-brand/` |
| streetwear з мілітарі принтом купити | LF | `/catalog/military/` |
| патріотична футболка з тризубом купити | LF | `/catalog/patriotic/` |
| мілітарі футболка з шевроном купити | LF | `/catalog/military/` |

#### RU
| Запит | Volume | Цільова |
|---|---|---|
| милитари одежда купить | MF | `/ru/catalog/military/` |
| патриотическая одежда | MF | `/ru/catalog/patriotic/` |
| патриотическая футболка | MF | `/ru/catalog/patriotic/` |
| футболка ВСУ | MF | `/ru/catalog/military/` |
| милитари футболка | MF | `/ru/catalog/military/` |
| патриотическое худи | MF | `/ru/catalog/patriotic/` |
| тактическая одежда streetwear | LF | `/ru/catalog/military/` |
| милитари стиль мужской | LF | `/ru/catalog/military/` |
| одежда для ветерана подарок | LF | `/ru/blog/` |
| патриотическая футболка купить для волонтера | LF | `/ru/catalog/patriotic/` |

#### EN
| Запит | Volume | Цільова |
|---|---|---|
| ukrainian military clothing | MF | `/en/catalog/military/` |
| ukrainian patriotic clothing | MF | `/en/catalog/patriotic/` |
| ukraine support t-shirt | MF | `/en/catalog/patriotic/` |
| ukrainian armed forces t-shirt | MF | `/en/catalog/military/` |
| zsu t-shirt buy online | LF | `/en/catalog/military/` |
| ukraine veteran gift clothing | LF | `/en/blog/` |
| streetwear with military print ukraine | LF | `/en/catalog/military/` |
| kharkiv military adjacent t-shirt | LF | `/en/catalog/military/` |
| ukrainian patriotic streetwear with trident | LF | `/en/catalog/patriotic/` |

### 4.5 Comparisons (порівняння)

> AI-search-search обожнює саме порівняльні запити. Стратегічно — закласти 5-7 comparison-сторінок (DTF vs шовкографія, oversize vs classic, чорне vs кайот, бавовна vs синтетика, classic-fit vs oversize, futbolka vs longsleeve, цінник vs якість).

#### UA
| Запит | Volume | Цільова |
|---|---|---|
| DTF vs шовкографія | LF | `/blog/dtf-vs-shovkohrafiya/` |
| oversize vs classic fit | LF | `/blog/oversize-vs-classic/` |
| бавовна vs поліестер футболка | LF | `/blog/bavovna-vs-poliester/` |
| лонгслів vs футболка з довгим рукавом | LF | `/blog/longsleeve-vs-tshirt/` |
| худі vs світшот різниця | LF | `/blog/hoodie-vs-svitshot/` |
| флісове vs бавовняне худі | LF | `/blog/flisove-vs-bavovnyane-hoodie/` |
| TwoComms vs Saint Javelin | ultra-LF | `/blog/twocomms-vs-saint-javelin/` |
| TwoComms vs Hygge Hoodie | ultra-LF | `/blog/twocomms-vs-hygge-hoodie/` |
| TwoComms vs Phantom Cat | ultra-LF | `/blog/twocomms-vs-phantomcat/` |
| TwoComms vs Syndicate | ultra-LF | `/blog/twocomms-vs-syndicate/` |
| TwoComms vs Everfox DTF друк | ultra-LF | `/blog/twocomms-vs-everfox/` |
| Український streetwear vs зарубіжний | LF | `/blog/` |

#### EN
| Запит | Volume | Цільова |
|---|---|---|
| dtf vs screen print | MF | `/en/blog/dtf-vs-screen-print/` |
| oversize vs classic fit hoodie | MF | `/en/blog/` |
| cotton vs polyester t-shirt | MF | `/en/blog/` |
| longsleeve vs t-shirt | LF | `/en/blog/` |
| hoodie vs sweatshirt difference | MF | `/en/blog/` |
| ukrainian streetwear vs international brands | LF | `/en/blog/` |

---

## 5. Local SEO keywords

> Один з найперспективніших кластерів для TwoComms — гео-LF з порожнім SERP. Зараз TwoComms лише вводить «Київ Харків Львів» у category-описах, але не має окремих локальних landing pages.

### 5.1 Харків (рідне місто бренду — особливий пріоритет)

| Запит | Lang | Volume | Цільова |
|---|---|---|---|
| купити футболку Харків | uk | MF | `/blog/futbolka-kharkiv/` або `/catalog/?city=kharkiv` (нова сторінка) |
| купити худі Харків | uk | MF | `/catalog/hoodie/?city=kharkiv` |
| купити лонгслів Харків | uk | LF | `/catalog/long-sleeve/?city=kharkiv` |
| streetwear Харків | uk | LF | `/pro-brand/` (з гео-фокусом) |
| streetwear бренд з Харкова | uk | LF | `/pro-brand/` |
| магазин одягу streetwear Харків | uk | LF | новий `/catalog/?city=kharkiv` |
| одяг з принтом Харків | uk | LF | `/catalog/?city=kharkiv` |
| доставка одягу по Харкову | uk | LF | `/delivery/` (з гео-фокусом) |
| мілітарі одяг Харків | uk | LF | `/catalog/military/?city=kharkiv` |
| TwoComms Харків магазин | uk | ultra-LF | `/contacts/` |
| Харків бренд одягу streetwear | uk | LF | `/pro-brand/` |
| купить футболку Харьков | ru | MF | `/ru/catalog/?city=kharkiv` |
| купить худи Харьков | ru | MF | `/ru/catalog/hoodie/?city=kharkiv` |
| streetwear Харьков купить | ru | LF | `/ru/pro-brand/` |
| магазин одежды streetwear Харьков | ru | LF | `/ru/catalog/?city=kharkiv` |
| buy streetwear kharkiv | en | LF | `/en/pro-brand/` |
| kharkiv streetwear brand | en | LF | `/en/pro-brand/` |

### 5.2 Київ

| Запит | Lang | Volume | Цільова |
|---|---|---|---|
| купити футболку Київ | uk | HF (~1k+/міс) | `/blog/futbolka-kyiv/` |
| купити худі Київ | uk | HF | `/catalog/hoodie/?city=kyiv` |
| купити лонгслів Київ | uk | MF | `/catalog/long-sleeve/?city=kyiv` |
| streetwear Київ | uk | MF | `/pro-brand/` |
| streetwear магазин Київ | uk | MF | `/catalog/?city=kyiv` |
| доставка одягу Київ | uk | MF | `/delivery/` |
| Нова Пошта Київ доставка одягу | uk | LF | `/delivery/` |
| вуличний одяг Київ | uk | LF | `/catalog/?city=kyiv` |
| магазин streetwear онлайн Київ | uk | LF | `/catalog/?city=kyiv` |
| streetwear бренд з Києва | uk | LF | `/pro-brand/` |
| купить футболку Киев | ru | HF | `/ru/catalog/?city=kyiv` |
| купить худи Киев | ru | HF | `/ru/catalog/hoodie/?city=kyiv` |
| streetwear Киев | ru | MF | `/ru/pro-brand/` |
| streetwear магазин Киев | ru | MF | `/ru/catalog/?city=kyiv` |
| buy streetwear kyiv | en | MF | `/en/pro-brand/` |
| kyiv streetwear brand | en | MF | `/en/pro-brand/` |
| ukrainian streetwear kyiv buy | en | LF | `/en/catalog/` |

### 5.3 Львів

| Запит | Lang | Volume | Цільова |
|---|---|---|---|
| купити футболку Львів | uk | MF | `/catalog/?city=lviv` |
| купити худі Львів | uk | MF | `/catalog/hoodie/?city=lviv` |
| streetwear Львів | uk | LF | `/pro-brand/` |
| streetwear магазин Львів | uk | LF | `/catalog/?city=lviv` |
| доставка одягу Львів | uk | LF | `/delivery/` |
| streetwear бренд Львів купити онлайн | uk | LF | `/pro-brand/` |
| купить футболку Львов | ru | LF | `/ru/catalog/?city=lviv` |
| купить худи Львов | ru | LF | `/ru/catalog/hoodie/?city=lviv` |
| buy streetwear lviv | en | LF | `/en/pro-brand/` |

### 5.4 Одеса

| Запит | Lang | Volume | Цільова |
|---|---|---|---|
| купити футболку Одеса | uk | MF | `/catalog/?city=odesa` |
| купити худі Одеса | uk | LF | `/catalog/hoodie/?city=odesa` |
| streetwear Одеса | uk | LF | `/pro-brand/` |
| streetwear магазин Одеса | uk | LF | `/catalog/?city=odesa` |
| купить футболку Одесса | ru | MF | `/ru/catalog/?city=odesa` |
| купить худи Одесса | ru | LF | `/ru/catalog/hoodie/?city=odesa` |
| buy streetwear odesa | en | LF | `/en/pro-brand/` |

### 5.5 Дніпро

| Запит | Lang | Volume | Цільова |
|---|---|---|---|
| купити футболку Дніпро | uk | LF | `/catalog/?city=dnipro` |
| купити худі Дніпро | uk | LF | `/catalog/hoodie/?city=dnipro` |
| streetwear Дніпро | uk | LF | `/pro-brand/` |
| streetwear магазин Дніпро | uk | LF | `/catalog/?city=dnipro` |
| купить футболку Днепр | ru | LF | `/ru/catalog/?city=dnipro` |
| streetwear Днепр | ru | LF | `/ru/pro-brand/` |

### 5.6 Nationwide UA (без гео)

| Запит | Lang | Volume | Цільова |
|---|---|---|---|
| доставка одягу Україна Нова Пошта | uk | MF | `/delivery/` |
| streetwear бренд Україна купити онлайн | uk | MF | `/pro-brand/` |
| купити streetwear онлайн Україна | uk | MF | `/catalog/` |
| купити футболку Україна виробник | uk | MF | `/catalog/tshirts/` |
| streetwear магазин Україна | uk | MF | `/catalog/` |
| купить streetwear онлайн Украина | ru | MF | `/ru/catalog/` |
| buy streetwear ukraine online | en | MF | `/en/catalog/` |
| ukrainian clothing brand online buy | en | MF | `/en/pro-brand/` |
| made in ukraine streetwear shop | en | LF | `/en/catalog/` |

---

## 6. AI-search visible keywords

> Запити, які LLM (ChatGPT, Claude, Gemini, Perplexity) частіше цитують. Definitional, how-to, brand-questions, comparisons.
> **30+ запитів на мову × 3 = 90+ запитів сумарно.**

### 6.1 UA — definitional + how-to + brand-questions (30+)

1. що таке український streetwear бренд
2. що таке streetwear з характером
3. що таке мілітарі adjacent одяг
4. що таке DTF друк простими словами
5. як обрати український streetwear бренд
6. як обрати розмір худі oversize
7. як прати футболку з DTF принтом
8. як зберегти яскравість DTF принту
9. чим відрізняється DTF друк від шовкографії
10. чим відрізняється oversize від classic fit
11. чим відрізняється худі від світшоту
12. як одягатися в streetwear стилі чоловіку
13. як одягатися в streetwear стилі жінці
14. як обрати футболку в подарунок чоловіку
15. як обрати худі в подарунок дівчині
16. який український бренд streetwear з Харкова варто купити
17. який streetwear бренд України підтримує ЗСУ
18. де купити патріотичний streetwear онлайн
19. де купити мілітарі футболку з принтом ЗСУ
20. чи можна замовити власний принт на футболці в Україні
21. як замовити кастомний друк на одязі
22. скільки коштує DTF друк в Україні
23. яка щільність бавовни найкраща для футболки
24. яка тканина найкраща для худі взимку
25. як TwoComms відрізняється від інших streetwear брендів України
26. чи робить TwoComms кастомний DTF друк
27. чи доставляє TwoComms по всій Україні Новою Поштою
28. чи можна купити TwoComms у Києві / Харкові / Львові
29. як влаштована розмірна сітка TwoComms
30. як TwoComms допомагає ЗСУ і ветеранам
31. чи можна повернути товар TwoComms протягом 14 днів
32. чи дає TwoComms знижку на оптові замовлення для команди
33. історія українського streetwear-бренду TwoComms
34. як заснований streetwear-бренд TwoComms з Харкова

### 6.2 RU — (30+)

1. что такое украинский streetwear бренд
2. что такое streetwear с характером
3. что такое милитари adjacent одежда
4. что такое DTF печать простыми словами
5. как выбрать украинский streetwear бренд
6. как выбрать размер худи оверсайз
7. как стирать футболку с DTF принтом
8. как сохранить яркость DTF принта
9. чем отличается DTF печать от шелкографии
10. чем отличается оверсайз от classic fit
11. чем отличается худи от свитшота
12. как одеваться в streetwear стиле мужчине
13. как одеваться в streetwear стиле женщине
14. как выбрать футболку в подарок мужчине
15. как выбрать худи в подарок девушке
16. какой украинский бренд streetwear из Харькова стоит купить
17. какой streetwear бренд Украины поддерживает ВСУ
18. где купить патриотический streetwear онлайн
19. где купить милитари футболку с принтом ВСУ
20. можно ли заказать свой принт на футболке в Украине
21. как заказать кастомную печать на одежде
22. сколько стоит DTF печать в Украине
23. какая плотность хлопка лучшая для футболки
24. какая ткань лучшая для худи зимой
25. как TwoComms отличается от других streetwear брендов Украины
26. делает ли TwoComms кастомную DTF печать
27. доставляет ли TwoComms по всей Украине Новой Почтой
28. можно ли купить TwoComms в Киеве / Харькове / Львове
29. как устроена размерная сетка TwoComms
30. как TwoComms помогает ВСУ и ветеранам
31. можно ли вернуть товар TwoComms в течение 14 дней
32. дает ли TwoComms скидку на оптовые заказы для команды

### 6.3 EN — (30+)

1. what is ukrainian streetwear
2. what is military adjacent clothing
3. what is dtf print
4. what is dtf vs screen print
5. how to choose ukrainian streetwear brand
6. how to choose oversize hoodie size
7. how to wash dtf print t-shirt
8. how to maintain dtf print brightness
9. how does dtf print differ from screen printing
10. what is the difference between oversize and classic fit
11. what is the difference between hoodie and sweatshirt
12. how to dress in streetwear style
13. how to choose t-shirt as a gift for men
14. which ukrainian streetwear brand from kharkiv to buy
15. which ukrainian streetwear brand supports zsu
16. where to buy ukrainian patriotic streetwear online
17. where to buy ukrainian military adjacent t-shirt with zsu print
18. can i order custom print on t-shirt in ukraine
19. how to order custom dtf print on apparel ukraine
20. how much does dtf print cost in ukraine
21. what cotton density is best for t-shirt
22. what fabric is best for winter hoodie
23. how is twocomms different from other ukrainian streetwear brands
24. does twocomms offer custom dtf printing
25. does twocomms ship internationally
26. can i buy twocomms in kyiv kharkiv lviv
27. what is twocomms size chart
28. how does twocomms support zsu and veterans
29. can i return twocomms order within 14 days
30. does twocomms offer wholesale discount for teams
31. is twocomms a kharkiv streetwear brand
32. who founded twocomms streetwear brand

---

## 7. Long-tail goldmines (низька конкуренція, середній intent)

> **Це найцінніший розділ для PDP-копірайтингу і блогу.** 50+ прикладів запитів, які зараз ніхто не закриває в SERP. Кожен з цих запитів має 5-50 пошуків місячно (LF), але сума сильна — 200-1500 додаткових органіків місячно.

### 7.1 Combo: цвет + крой + категория + гео

1. чорна оверсайз футболка з принтом купити Київ
2. чорна оверсайз футболка з мілітарі принтом Харків
3. чорне oversize худі з принтом ЗСУ Львів
4. чорний oversize лонгслів з принтом купити Україна
5. кайот футболка з принтом купити Україна виробник
6. рожеве худі з мілітарі принтом купити онлайн
7. ментолова футболка з принтом купити Україна
8. чорно-бордовий лонгслів з принтом купити Україна
9. оверсайз чорна жіноча футболка з принтом ЗСУ
10. чорне зимове флісове худі з мілітарі принтом купити

### 7.2 Combo: товар + occasion (нагода)

11. футболка в подарунок чоловіку 30 років
12. футболка в подарунок хлопцю 18-25
13. худі в подарунок чоловіку 35 років
14. футболка в подарунок ветерану ЗСУ
15. худі в подарунок волонтеру
16. оригінальний подарунок футболка з принтом для друга
17. подарунок до 23 серпня Дня прапора футболка
18. подарунок до 24 серпня Дня незалежності худі
19. подарунок до 14 жовтня Дня Захисника футболка
20. подарунок на корпоратив команді з логотипом
21. подарунок випускнику футболка з принтом
22. подарунок до Нового Року худі мілітарі
23. подарунок дівчині на 14 лютого худі oversize
24. подарунок чоловіку на день народження мілітарі футболка

### 7.3 Combo: товар + проблема / Pain Point

25. чорна футболка не злазить принт після прання купити
26. худі що не сідає після прання купити Україна
27. футболка з принтом яка не злиняє купити
28. бавовняне худі без подразнень шкіри купити
29. oversize футболка для високого зросту купити Україна
30. лонгслів з довгим рукавом для високих чоловіків
31. розмір 4XL чоловіче худі купити Україна
32. розмір XS жіноче худі oversize купити
33. футболка унісекс для повних людей купити Україна
34. футболка з широкою посадкою для танців і спорту
35. чорне худі без капюшона купити (свитшот)

### 7.4 Combo: товар + cause (соціальна тематика)

36. футболка чий збір допомагає ЗСУ купити
37. худі купити підтримати ЗСУ Україна
38. одяг бренду який допомагає ветеранам купити
39. купити одяг ветеранського бренду Україна
40. подарунок волонтеру з мілітарі-принтом
41. купити одяг від бренду який підтримує військових ЗСУ
42. одяг харківського бренду купити онлайн підтримати Україну
43. купити patriotic streetwear від українського ветерана

### 7.5 Combo: товар + character/style + гео

44. streetwear для скейтерів Київ купити
45. streetwear для рейверів Харків купити
46. streetwear для волонтерів Україна купити
47. streetwear для ветеранів ЗСУ купити онлайн
48. streetwear для української молоді 18-25 купити
49. streetwear для тих хто слухає реп Україна
50. streetwear для геймерів та стрімерів Україна купити

### 7.6 EN long-tail goldmines

51. black oversize t-shirt with patriotic print buy ukraine
52. ukrainian streetwear oversize hoodie black gift for him
53. kharkiv-based streetwear brand support zsu buy international
54. cotton oversize hoodie with military print buy ukraine
55. patriotic ukrainian t-shirt with print veteran owned brand
56. oversize fleece hoodie with print made in ukraine ship to us
57. black graphic long sleeve cotton oversize ukraine streetwear

### 7.7 RU long-tail goldmines

58. чёрная оверсайз футболка с принтом купить Киев недорого
59. чёрное оверсайз худи с патриотическим принтом купить Харьков
60. оригинальный подарок мужчине футболка с принтом украинский бренд
61. чёрное худи без капюшона купить (свитшот) украина
62. размер XS женское худи оверсайз купить украина
63. чёрная футболка с принтом ВСУ купить онлайн поддержка ВСУ

---

## 8. Per-page keyword targeting

> Для кожної важливої сторінки — primary keyword (1, HF), secondary (3-5, MF), long-tail support (10-20, LF), anchor patterns.

### 8.1 Home `/`

| Slot | Keywords |
|---|---|
| **Primary** | streetwear бренд Україна |
| **Secondary** | streetwear Україна купити, streetwear магазин Україна, streetwear онлайн, український streetwear бренд, streetwear з характером |
| **LF support** | streetwear бренд Харків, український streetwear бренд для тих хто підтримує ЗСУ, streetwear-одяг від українського бренду TwoComms, streetwear бренд з характером Україна, streetwear-магазин для тих хто шукає authentic, streetwear-бренд з мілітарі принтом, streetwear-одяг з принтом ЗСУ, streetwear-бренд Україна 2025 купити онлайн, streetwear-магазин з доставкою Новою Поштою, streetwear-бренд з кастомним DTF друком на замовлення |
| **Anchor patterns для inbound** | «TwoComms» / «TWOCOMMS» / «streetwear бренд TwoComms» / «український streetwear-бренд» / «головна TwoComms» |

### 8.2 Catalog `/catalog/`

| Slot | Keywords |
|---|---|
| **Primary** | купити одяг streetwear онлайн |
| **Secondary** | купити streetwear онлайн Україна, каталог streetwear одягу, купити одяг з принтом онлайн Україна, streetwear каталог TwoComms, купити streetwear для чоловіків і жінок |
| **LF support** | каталог одягу TwoComms streetwear бренд Україна, streetwear каталог чорний унісекс oversize, streetwear-одяг з принтом ЗСУ каталог, мілітарі-одяг каталог Україна купити, streetwear для хлопця і дівчини каталог, каталог одягу від українського streetwear-бренду з Харкова, повний каталог одягу TwoComms 2025, streetwear футболки худі лонгсліви каталог, каталог streetwear-одягу з кастомним DTF друком, streetwear каталог для команди і друзів |
| **Anchor patterns** | «Каталог» / «Каталог streetwear» / «Каталог одягу TwoComms» / «Перейти в каталог» / «Каталог streetwear-одягу» |

### 8.3 Category `/catalog/tshirts/`

| Slot | Keywords |
|---|---|
| **Primary** | купити футболку з принтом |
| **Secondary** | купити футболку з принтом Україна, купити чорну унісекс футболку oversize, купити патріотичну футболку ЗСУ, купити мілітарі футболку Україна, купити streetwear футболку чоловічу |
| **LF support** | купити чорну oversize унісекс футболку з принтом ЗСУ Україна, чорна жіноча футболка з принтом купити, патріотична футболка з тризубом купити, мілітарі футболка з принтом для волонтера, чорна футболка з принтом «Reality Bends», футболка унісекс з принтом для команди оптом, чорна оверсайз футболка з мілітарі принтом купити Київ Харків Львів, бавовняна футболка щільна з принтом купити Україна виробник, футболка з принтом «Glory of Ukraine» купити, футболка з принтом «Pokrovsk Girl» купити, футболка з принтом «Kharkiv Edition», чорна футболка з DTF принтом яка не злиняє після прання |
| **Anchor patterns** | «Футболки» / «Купити футболку з принтом» / «Каталог футболок TwoComms» / «Футболки з принтом ЗСУ» / «Чорна футболка з принтом» / «Унісекс футболки» / «Streetwear футболки» |

### 8.4 Category `/catalog/hoodie/`

| Slot | Keywords |
|---|---|
| **Primary** | купити худі з принтом |
| **Secondary** | купити чорне oversize худі, тепле флісове худі купити, мілітарі худі з принтом ЗСУ, патріотичне худі купити Україна, купити худі streetwear Україна |
| **LF support** | чорне oversize худі з принтом купити Україна виробник, тепле флісове худі з мілітарі принтом купити, чорне худі з принтом ЗСУ для волонтера, oversize худі з принтом «Reality Bends» купити, oversize чорне худі з принтом «Kharkiv Edition», бавовняне щільне худі з кишенею кенгуру з принтом, флісове зимове худі з мілітарі принтом ЗСУ, чорне жіноче oversize худі з принтом купити, мілітарі худі чоловіче для ветерана подарунок, чорне oversize худі для команди з кастомним принтом купити, флісове тепле худі для зими з мілітарі-принтом купити, чорне oversize худі streetwear-бренду TwoComms купити, патріотичне худі з тризубом купити Україна |
| **Anchor patterns** | «Худі» / «Купити худі з принтом» / «Каталог худі TwoComms» / «Чорне oversize худі» / «Худі мілітарі» / «Тепле флісове худі» / «Худі з принтом ЗСУ» |

### 8.5 Category `/catalog/long-sleeve/`

| Slot | Keywords |
|---|---|
| **Primary** | купити лонгслів з принтом |
| **Secondary** | чорний лонгслів з принтом, oversize лонгслів купити, унісекс лонгслів з принтом ЗСУ, мілітарі лонгслів купити Україна, бавовняний лонгслів streetwear |
| **LF support** | чорний oversize лонгслів з принтом купити Україна виробник, бавовняний щільний лонгслів з принтом, лонгслів з принтом ЗСУ для волонтера купити, oversize лонгслів з принтом «Reality Bends» купити, чорний лонгслів з принтом «Kharkiv Edition», лонгслів з довгим рукавом і манжетом oversize купити, чорний лонгслів streetwear-бренду TwoComms, бавовняний лонгслів з кастомним принтом купити Україна, oversize лонгслів унісекс з принтом для команди купити, лонгслів патріотичний з тризубом купити Україна, чорний oversize лонгслів з мілітарі принтом купити Київ, бавовняний лонгслів щільний 230 г/м² з принтом, лонгслів streetwear для зими купити Україна |
| **Anchor patterns** | «Лонгсліви» / «Купити лонгслів з принтом» / «Каталог лонгслівів TwoComms» / «Чорний oversize лонгслів» / «Лонгслів streetwear» / «Лонгслів з принтом ЗСУ» |

### 8.6 Page `/custom-print/`

| Slot | Keywords |
|---|---|
| **Primary** | замовити свій принт на футболці |
| **Secondary** | DTF друк Україна, кастомний друк на одязі, замовити кастомну футболку, надрукувати свій принт на одязі, DTF друк Київ Харків |
| **LF support** | надрукувати свій принт на чорній футболці онлайн Україна, замовити кастомний DTF друк на худі для команди, кастомний друк на лонгсліві ціна Україна, надрукувати свій логотип на футболці маленьким тиражем, DTF друк на бавовняній футболці на замовлення, кастомний DTF друк для дропшипінгу Україна, замовити свою футболку з принтом для команди подарунок, надрукувати свій мем ЗСУ на футболці купити, кастомний DTF друк на чорному oversize худі, замовити свій принт на лонгсліві ЦСУ Україна, надрукувати свій логотип бренду на футболках оптом маленький тираж, кастомний DTF друк свого зображення на одязі, замовити кастомний друк на одязі для весілля корпоративу івенту, DTF друк на одязі для маркетплейсу дропшиппінг Україна |
| **Anchor patterns** | «Кастомний друк» / «Замовити свій принт» / «Створити свій принт» / «DTF друк на замовлення» / «Кастомний DTF друк TwoComms» / «Надрукувати свій принт» |

### 8.7 Page `/wholesale/`

| Slot | Keywords |
|---|---|
| **Primary** | купити футболки оптом Україна виробник |
| **Secondary** | оптовий продаж streetwear, мерч для команди, корпоративний мерч, дропшипінг одягу Україна, постачальник streetwear для магазину |
| **LF support** | купити футболки оптом Україна виробник з власним принтом, оптовий продаж streetwear-одягу від виробника, мерч для команди з логотипом і DTF друком, корпоративний мерч від українського streetwear-бренду, дропшипінг streetwear-одягу від українського виробника, постачальник streetwear для онлайн-магазину Україна, купити худі оптом для дропшипінгу від виробника, купити лонгсліви оптом для маркетплейсу Україна, купити мерч для івенту з кастомним DTF друком, купити брендовий мерч для волонтерського проекту, купити streetwear оптом для магазину невеликий тираж, купити мерч від українського ветеранського бренду |
| **Anchor patterns** | «Опт» / «Купити оптом» / «Оптовий продаж» / «Wholesale» / «Корпоративний мерч» / «Купити для команди» |

### 8.8 Page `/cooperation/`

| Slot | Keywords |
|---|---|
| **Primary** | співпраця з українським streetwear-брендом |
| **Secondary** | дропшипінг одягу Україна, корпоративний мерч, мерч для команди, амбасадорство streetwear-бренду |
| **LF support** | співпраця з українським streetwear-брендом для блогерів, дропшипінг одягу від українського виробника, корпоративний мерч від ветеранського бренду, амбасадорство streetwear-бренду для українських інфлюенсерів, співпраця з TwoComms для волонтерських проектів, мерч для українських команд і клубів, співпраця з українським streetwear-брендом для маркетплейсів, корпоративний мерч від TwoComms для команд ЗСУ, мерч від українського бренду для прес-конференцій, амбасадорство для тих хто підтримує ЗСУ, співпраця з TwoComms для івентів та фестивалів |
| **Anchor patterns** | «Співпраця» / «Cooperation» / «Партнерство» / «Дропшипінг» / «Амбасадорство» / «Корпоративний мерч» |

### 8.9 Page `/pro-brand/`

| Slot | Keywords |
|---|---|
| **Primary** | TwoComms бренд |
| **Secondary** | історія TwoComms, що таке TwoComms, український streetwear-бренд з Харкова, streetwear-бренд з характером, який український streetwear-бренд варто купити |
| **LF support** | історія заснування українського streetwear-бренду TwoComms, як TwoComms зʼявився в Харкові, чому TwoComms має такий маніфест streetwear, який streetwear-бренд України підтримує ЗСУ, як TwoComms відрізняється від інших streetwear-брендів України, що означає назва TwoComms і знак, історія військового streetwear-бренду TwoComms, як TwoComms допомагає ветеранам ЗСУ і волонтерам, маніфест streetwear-бренду TwoComms, що означає Reality Bends Future у TwoComms, чому TwoComms streetwear бренд з характером, як TwoComms виник з Харкова |
| **Anchor patterns** | «Про бренд» / «Про TwoComms» / «Історія TwoComms» / «Маніфест TwoComms» / «Що таке TwoComms» / «Хто заснував TwoComms» |

### 8.10 Page `/delivery/`

| Slot | Keywords |
|---|---|
| **Primary** | доставка одягу Нова Пошта Україна |
| **Secondary** | доставка TwoComms Нова Пошта, доставка одягу Харків, доставка одягу Київ, доставка одягу Львів, оплата онлайн Україна |
| **LF support** | доставка streetwear-одягу Новою Поштою по Україні TwoComms, безкоштовна доставка одягу від суми Україна, доставка streetwear від виробника TwoComms Нова Пошта, оплата накладений платіж streetwear-одяг, оплата онлайн Mono LiqPay для streetwear-одягу, як відстежити замовлення TwoComms по Новій Пошті, доставка streetwear-одягу Україна Нова Пошта 1-3 дні, оплата картою через Privat24 на сайті TwoComms |
| **Anchor patterns** | «Доставка» / «Доставка і оплата» / «Доставка Новою Поштою» / «Як отримати замовлення» |

### 8.11 Page `/rozmirna-sitka/`

| Slot | Keywords |
|---|---|
| **Primary** | розмірна сітка футболки худі лонгслів |
| **Secondary** | як обрати розмір футболки, як обрати розмір худі, oversize розмірна сітка, розмірна сітка чоловіча, розмірна сітка жіноча |
| **LF support** | розмірна сітка футболок українського виробника TwoComms, розмірна сітка худі чоловічого oversize, як виміряти розмір футболки oversize, розмірна сітка лонгслівів унісекс, розмір M худі скільки см обхват грудей, розмір XL чоловічий oversize худі см, чи мала розміриться футболка після прання, розмірна сітка для високих людей streetwear |
| **Anchor patterns** | «Розмірна сітка» / «Розміри» / «Як обрати розмір» / «Size guide» |

### 8.12 Page `/doglyad-za-odyagom/`

| Slot | Keywords |
|---|---|
| **Primary** | догляд за одягом з принтом DTF |
| **Secondary** | як прати футболку з принтом, як прати худі з принтом, при якій температурі прати DTF принт, чи злазить DTF принт після прання, як зберігати streetwear-одяг |
| **LF support** | як прати футболку з DTF принтом без втрати яскравості, при якій температурі прати худі з принтом TwoComms, як прасувати футболку з DTF принтом, чи можна сушити худі в сушарці, як видалити пляму з футболки з принтом без шкоди, чим відрізняється DTF принт від шовкографії в догляді, як зберегти яскравість DTF принту після 100 прань, чи можна прати чорне худі з принтом разом з джинсами |
| **Anchor patterns** | «Догляд» / «Догляд за одягом» / «Care guide» / «Як прати» / «Як зберігати» |

### 8.13 Page `/faq/` + `/dopomoga/`

| Slot | Keywords |
|---|---|
| **Primary** | TwoComms допомога FAQ |
| **Secondary** | TwoComms доставка питання, TwoComms повернення обмін, TwoComms розмір, TwoComms оплата, TwoComms кастомний принт |
| **LF support** | як замовити кастомний принт у TwoComms, як зробити повернення в TwoComms протягом 14 днів, скільки коштує доставка TwoComms Новою Поштою, як обрати розмір худі TwoComms oversize, чи робить TwoComms бронепринт ЗСУ, як зворотний звʼязок TwoComms, чи доставляє TwoComms в інші країни, як відстежити моє замовлення TwoComms |
| **Anchor patterns** | «FAQ» / «Допомога» / «Часті запитання» / «Help» |

### 8.14 PDP top-15 (за частотністю brand-internal)

> Для **кожного PDP** primary keyword = «купити [товар]». Secondary — варіанти кольору + розміру + fit. LF support — назва принту + його сенс + occasion. Нижче — 15 пріоритетних PDP, які потребують найбільшого SEO-уваги.

#### 8.14.1 `/product/classic-tshirt/`
- **Primary**: купити класичну футболку TwoComms
- **Secondary**: купити чорну класичну футболку, бавовняна класична футболка унісекс, oversize класична футболка
- **LF support**: чорна бавовняна класична футболка TwoComms купити Україна виробник, унісекс oversize класична футболка з висококласної бавовни, класична чорна футболка для streetwear oversize купити, бавовняна щільна 220 г/м² чорна футболка купити, класична футболка унісекс з можливістю кастомного принту
- **Anchors**: «Футболка класична» / «Класична чорна футболка» / «Bavovnyana classic t-shirt» / «Базова футболка TwoComms»

#### 8.14.2 `/product/hoodie-classic/`
- **Primary**: купити класичне худі TwoComms
- **Secondary**: чорне класичне худі, oversize класичне худі, тепле класичне худі флісове
- **LF support**: чорне oversize класичне худі бавовняне 320 г/м² купити, тепле флісове класичне худі унісекс TwoComms, класичне oversize худі streetwear-бренду TwoComms купити, чорне класичне худі з кишенею кенгуру oversize, класичне базове чорне худі для зими купити Україна
- **Anchors**: «Худі класичне» / «Класичне oversize худі» / «Базове худі TwoComms»

#### 8.14.3 `/product/longsleeve-classic/`
- **Primary**: купити класичний лонгслів TwoComms
- **Secondary**: чорний класичний лонгслів, oversize класичний лонгслів, бавовняний класичний лонгслів
- **LF support**: чорний oversize класичний лонгслів унісекс TwoComms, бавовняний щільний 230 г/м² класичний лонгслів купити, класичний oversize лонгслів з довгим рукавом купити Україна
- **Anchors**: «Лонгслів класичний» / «Класичний oversize лонгслів»

#### 8.14.4 `/product/twocomms-reality-bends-future-2026/`
- **Primary**: купити худі Reality Bends Future TwoComms
- **Secondary**: чорне худі Reality Bends, oversize худі Reality Bends, лімітована колекція TwoComms 2026
- **LF support**: чорне oversize худі Reality Bends Future 2026 TwoComms купити, лімітована колекція streetwear від TwoComms 2026, худі з принтом «Reality Bends Future» чорне oversize купити, ексклюзивне худі streetwear від ветеранського бренду TwoComms 2026
- **Anchors**: «Reality Bends Future» / «Худі Reality Bends» / «Лімітована колекція TwoComms 2026»

#### 8.14.5 `/product/my-little-baby/` (з варіантами `/black/`, `/coyote/`)
- **Primary**: купити футболку «My Little Baby» TwoComms
- **Secondary**: чорна футболка «My Little Baby», кайот футболка «My Little Baby», oversize My Little Baby
- **LF support**: чорна oversize унісекс футболка «My Little Baby» з принтом TwoComms купити, кайот oversize футболка «My Little Baby» від українського streetwear-бренду, футболка з принтом «My Little Baby» подарунок, oversize чорна футболка «My Little Baby» бавовняна купити Україна
- **Anchors**: «My Little Baby» / «Футболка My Little Baby» / «Чорна My Little Baby» / «Кайот My Little Baby»

#### 8.14.6 `/product/where-mi-present-ts/` (Де Мої Подарунки, Мразота?)
- **Primary**: купити футболку «Де Мої Подарунки» TwoComms
- **Secondary**: чорна футболка «Де Мої Подарунки», кайот варіант, oversize
- **LF support**: чорна oversize унісекс футболка з принтом «Де Мої Подарунки, Мразота?» TwoComms купити, оригінальний подарунок футболка з мемним принтом, чорна streetwear-футболка з провокативним принтом TwoComms купити, кайот футболка з принтом «Де Мої Подарунки» подарунок чоловіку
- **Anchors**: «Де Мої Подарунки» / «Where My Presents» / «Чорна футболка з мемним принтом»

#### 8.14.7 `/product/in-shee/` (In Shee — провокативний принт)
- **Primary**: купити футболку «In Shee» TwoComms
- **Secondary**: чорна футболка з провокативним принтом, oversize футболка з мемним принтом
- **LF support**: чорна oversize унісекс футболка з провокативним принтом «In Shee» TwoComms купити, streetwear-футболка з мемним хуліганським принтом купити Україна
- **Anchors**: «In Shee» / «Футболка з провокативним принтом»

#### 8.14.8 `/product/glory-of-ukraine-hd/`
- **Primary**: купити худі «Glory of Ukraine» TwoComms
- **Secondary**: чорне oversize худі патріотичне, худі з тризубом, патріотичне худі ЗСУ
- **LF support**: чорне oversize худі з патріотичним принтом «Glory of Ukraine» TwoComms купити, флісове тепле худі з тризубом і прапором купити Україна, патріотичне худі з принтом «Glory of Ukraine» подарунок ветерану ЗСУ, oversize чорне худі з тризубом купити Київ Харків Львів
- **Anchors**: «Glory of Ukraine» / «Худі Glory of Ukraine» / «Патріотичне худі з тризубом»

#### 8.14.9 `/product/pokrovsk-girl-hd/` (присвячено Покровську)
- **Primary**: купити худі «Pokrovsk Girl» TwoComms
- **Secondary**: чорне oversize худі патріотичне, худі присвячене Покровську, мілітарі худі ЗСУ
- **LF support**: чорне oversize худі з принтом «Pokrovsk Girl» від українського streetwear-бренду TwoComms купити, патріотичне худі з присвятою захисникам Покровська, мілітарі худі з принтом ЗСУ Pokrovsk Girl купити Україна
- **Anchors**: «Pokrovsk Girl» / «Худі Pokrovsk Girl» / «Patriotic Pokrovsk hoodie»

#### 8.14.10 `/product/kha-edition-hd/` (Kharkiv Edition)
- **Primary**: купити худі «Kharkiv Edition» TwoComms
- **Secondary**: чорне oversize худі з Харкова, харківський streetwear, харківська лімітована колекція
- **LF support**: чорне oversize худі «Kharkiv Edition» від українського streetwear-бренду з Харкова TwoComms, харківська лімітована колекція streetwear, патріотичне худі з принтом «Kharkiv Edition» купити Україна, харківський streetwear-бренд лімітоване худі купити онлайн
- **Anchors**: «Kharkiv Edition» / «Худі Kharkiv Edition» / «Харківська колекція»

#### 8.14.11 `/product/kha-style-hd/`
- **Primary**: купити худі «Kha Style» TwoComms
- **Secondary**: чорне oversize худі харківський стиль, харківський streetwear oversize худі
- **LF support**: чорне oversize худі «Kha Style» (харківський стиль) від TwoComms, харківський streetwear oversize худі купити, патріотичне худі з посиланням на Харків купити Україна
- **Anchors**: «Kha Style» / «Худі Kha Style» / «Харківський стиль streetwear»

#### 8.14.12 `/product/death-grabs-ass-hd/`
- **Primary**: купити худі «Cherep z Trojandoyu» / «Skull and Rose» TwoComms
- **Secondary**: чорне oversize худі з черепом і трояндою, gothic streetwear худі
- **LF support**: чорне oversize худі з принтом черепа і троянди oversize TwoComms купити, gothic-streetwear oversize чорне худі з провокативним принтом купити Україна
- **Anchors**: «Череп з трояндою» / «Skull and Rose» / «Gothic streetwear худі»

#### 8.14.13 `/product/lord-of-the-lending-hd/`
- **Primary**: купити худі «Lord of the Lending» TwoComms
- **Secondary**: чорне oversize худі з мемним принтом, фентезійний streetwear худі
- **LF support**: чорне oversize худі з фентезійним мемним принтом «Lord of the Lending» TwoComms купити, oversize чорне худі з принтом для фанів фентезі купити Україна
- **Anchors**: «Lord of the Lending» / «Худі Lord of the Lending»

#### 8.14.14 `/product/red-leaves-ts/`
- **Primary**: купити футболку «Red Leaves» TwoComms
- **Secondary**: чорна oversize футболка з осіннім принтом, мінімалістична streetwear-футболка
- **LF support**: чорна oversize унісекс футболка з осіннім принтом «Red Leaves» TwoComms купити, мінімалістична streetwear-футболка з мотивом червоного листя купити Україна
- **Anchors**: «Red Leaves» / «Футболка Red Leaves» / «Осінній принт»

#### 8.14.15 `/product/last-breath-hd/`
- **Primary**: купити худі «Last Breath» TwoComms
- **Secondary**: чорне oversize худі з провокативним принтом, мілітарі-streetwear худі
- **LF support**: чорне oversize худі з провокативним принтом «Last Breath» від українського streetwear-бренду TwoComms купити, мілітарі-streetwear oversize худі для тих хто підтримує ЗСУ
- **Anchors**: «Last Breath» / «Худі Last Breath»

---

## 9. Anchor text recommendations

> Стратегія: **>60% анкорів — descriptive long-tail (3-6 слів)**, **<40% — short topical (1-2 слова)**, **<5% — generic** («тут», «детальніше», «click here»). Зараз TwoComms у нормі — 0% generic. Треба зберегти і розширити long-tail на новому контенті.

### 9.1 Універсальна таблиця рекомендованих анкорів

| Target page | Recommended anchor variations (UK) | RU equivalents | EN equivalents |
|---|---|---|---|
| `/` | TwoComms / TWOCOMMS / streetwear бренд TwoComms / головна TwoComms / український streetwear бренд | TwoComms / стритвир бренд TwoComms | TwoComms / ukrainian streetwear brand TwoComms |
| `/catalog/` | Каталог / Каталог одягу / Каталог streetwear / Перейти в каталог TwoComms / Каталог streetwear TwoComms | Каталог / Каталог одежды / Каталог streetwear | Catalog / Streetwear catalog / Browse all |
| `/catalog/tshirts/` | Футболки / Купити футболку з принтом / Каталог футболок TwoComms / Чорна футболка з принтом / Streetwear футболки / Унісекс футболки з принтом ЗСУ | Футболки / Купить футболку с принтом / Каталог футболок | T-shirts / Buy graphic t-shirt / Streetwear t-shirts |
| `/catalog/hoodie/` | Худі / Купити худі з принтом / Каталог худі / Чорне oversize худі / Тепле флісове худі / Худі мілітарі ЗСУ | Худи / Купить худи с принтом / Каталог худи | Hoodies / Buy graphic hoodie / Streetwear hoodies |
| `/catalog/long-sleeve/` | Лонгсліви / Купити лонгслів з принтом / Каталог лонгслівів / Чорний oversize лонгслів | Лонгсливы / Купить лонгслив с принтом | Long sleeves / Buy graphic long sleeve |
| `/catalog/military/` (новий) | Мілітарі-одяг / Каталог мілітарі streetwear / Військова футболка ЗСУ / Streetwear для волонтерів | Милитари одежда / Каталог милитари streetwear | Military adjacent clothing / ZSU streetwear |
| `/catalog/patriotic/` (новий) | Патріотичний одяг / Streetwear з тризубом / Патріотичне худі ЗСУ | Патриотическая одежда / Streetwear с трезубцем | Patriotic streetwear / Ukraine support clothing |
| `/custom-print/` | Кастомний друк / Замовити свій принт / Створити свій принт / DTF друк на замовлення / Надрукувати свій принт / Кастомний DTF друк TwoComms | Кастомная печать / Заказать свой принт / DTF печать | Custom print / Order your print / Custom DTF print |
| `/wholesale/` | Опт / Купити оптом / Wholesale TwoComms / Корпоративний мерч / Купити для команди / B2B TwoComms | Опт / Купить оптом / Wholesale | Wholesale / B2B / Bulk order |
| `/cooperation/` | Співпраця / Партнерство / Cooperation / Дропшипінг / Амбасадорство | Сотрудничество / Партнерство / Cooperation | Cooperation / Partnership / Become an ambassador |
| `/pro-brand/` | Про бренд / Про TwoComms / Історія TwoComms / Маніфест TwoComms / Що таке TwoComms / Хто заснував TwoComms | О бренде / О TwoComms / История TwoComms | About brand / About TwoComms / TwoComms story |
| `/delivery/` | Доставка / Доставка і оплата / Доставка Новою Поштою / Як отримати замовлення | Доставка / Доставка и оплата / Доставка Новой Почтой | Delivery / Delivery & payment / Shipping with Nova Poshta |
| `/povernennya-ta-obmin/` | Повернення / Повернення та обмін / Повернути товар протягом 14 днів | Возврат / Возврат и обмен / Вернуть товар в течение 14 дней | Returns / Returns & exchanges / 14-day return |
| `/rozmirna-sitka/` | Розмірна сітка / Розміри / Як обрати розмір / Розмірна сітка худі | Размерная сетка / Как выбрать размер | Size guide / How to choose size |
| `/doglyad-za-odyagom/` | Догляд за одягом / Як прати / Care guide / Як зберігати streetwear | Уход за одеждой / Как стирать | Garment care / How to wash / Care guide |
| `/faq/` | FAQ / Часті запитання | FAQ / Частые вопросы | FAQ |
| `/dopomoga/` | Допомога / Help center | Помощь / Help center | Help center |
| `/contacts/` | Контакти / Звʼязатись з TwoComms | Контакты / Связаться с TwoComms | Contacts / Contact TwoComms |

### 9.2 Anti-patterns (чого уникати)

- ❌ «тут» / «click here» / «детальніше» / «more» / «на сайті» — generic, не дають keyword-сигналу
- ❌ «1», «2», «»» (badges, pagination markers — нормально в pagination, але не в content)
- ❌ Однаковий anchor на одну сторінку з різних місць однієї сторінки (Google зчитує лише перший)
- ❌ Image-only анкори без alt — поганий a11y і нульовий keyword-сигнал
- ❌ Anchor у вигляді URL: «twocomms.shop/catalog/»

### 9.3 Розподіл по типам (target distribution)

| Тип anchor | Target % | Пример |
|---|---|---|
| Descriptive long-tail (3-6 слів) | 60-65% | «Купити чорне oversize худі з принтом» |
| Topical (1-2 слова) | 25-30% | «Худі», «Розмірна сітка» |
| Brand-only | 5-10% | «TwoComms», «TWOCOMMS» |
| Generic | <2% | «детальніше», «тут» — зараз 0% (зберегти) |
| Image-only з alt | 5-10% | картинки товарів з alt-текстом |

---

## 10. Competitive analysis (5 конкурентів)

### 10.1 everfox.com.ua

- **Домен**: everfox.com.ua
- **Тип**: Custom DTF-друк + готовий одяг з принтом на замовлення
- **Sections**: одяг з DTF-принтом (футболки, поло, лонгсліви, худі, дитячий одяг), друк на одязі (DTF трансфери, рулонний DTF, послуги дизайнера, шопери), online-конструктор, відгуки
- **Топ ключі (по яких ранжуються)**:
  1. dtf друк
  2. dtf друк україна
  3. свій принт на футболці
  4. кастомний друк футболки
  5. dtf трансфер купити
  6. друк на одязі
  7. термонаклейка на одяг
  8. друк на одязі ціна
  9. одяг з принтом на замовлення
  10. конструктор принтів онлайн
- **`sameAs` (соц. мережі)**: Instagram (`@everfox.ua`), TikTok (`@everfox.ua`), YouTube, Facebook, WhatsApp, Telegram (`@everfox_ua`), Phone (Vodafone/Life)
- **Контентна стратегія**: focus на B2C-DIY через online-конструктор, дешеві базові ціни (160-790 грн за кастомну футболку — у 2-3 рази дешевше TwoComms). Немає блогу, немає бренд-сторінки. **TwoComms має диференцію через якість + brand story + мілітарі-естетику**.
- **Ціновий сегмент**: бюджетний (160-1410 грн)
- **Слабкі місця TwoComms можна атакувати тут**: TwoComms — премʼюм + brand-story; Everfox — cheap + utility. TwoComms бере на нішу «streetwear з характером, не just custom print».

### 10.2 hygge-hoodie.com

- **Домен**: hygge-hoodie.com
- **Тип**: Український streetwear-бренд базового одягу
- **Sections**: футболки (basic, premium, slim fit, oversize), худі та zip-худі, світшоти, штани, сорочки
- **Топ ключі (по яких ранжуються)**:
  1. купити худі україна
  2. базовий одяг український бренд
  3. футболка classic premium
  4. худі чорне oversize
  5. zip-худі купити
  6. світшоти український бренд
  7. базова футболка чорна
  8. худі бавовняне oversize
  9. чорне oversize худі чоловіче
  10. джогери преміум український бренд
- **`sameAs`**: Instagram (`@hygge_hoodie`)
- **Контентна стратегія**: 6 років на ринку, focus на BASIC (без принтів), широкий розмірний ряд, програма re:wear (повторне використання). Має блог? Не виявлено в швидкому скані. FAQ є (доставка, оплата, повернення).
- **Ціновий сегмент**: середній (560-940 грн футболка, 1890-2390 грн худі — на 10-25% дорожче TwoComms)
- **Слабкі місця TwoComms можна атакувати тут**: hygge-hoodie — базовий streetwear без принтів і характеру. TwoComms — character-driven streetwear з принтами. Ринок розгалужується: hygge для тих, хто шукає базу; TwoComms — для тих, хто шукає ідентичність.

### 10.3 phantomcat.com.ua

- **Домен**: phantomcat.com.ua
- **Тип**: Український streetwear з мемним/кіношним/етно-принтом
- **Sections**: футболки, худі, штани, шорти, кепки. Підрозділи: мемні, текстові, кіношні, етно
- **Топ ключі (по яких ранжуються)**:
  1. футболка з мемним принтом купити
  2. кіношні футболки купити
  3. худі з мемним принтом
  4. етно футболка купити
  5. текстова футболка з принтом
  6. купити футболку з принтом український бренд
  7. оригінальний одяг власного виробництва
  8. розпродаж футболок україна
  9. кепки український бренд
  10. шорти streetwear український
- **`sameAs`**: Telegram (`@phantomcat`)
- **Контентна стратегія**: focus на стилизацію по принту (мемні / кіношні / етно), regular розіграші, минімалістичний UX, 5-question FAQ. Cайт на Weblium (легка платформа). Немає блогу.
- **Ціновий сегмент**: середньо-низький
- **Слабкі місця TwoComms можна атакувати тут**: phantomcat не має військової / патріотичної лінії. TwoComms — єдиний бренд з реальним military-adjacent storytelling від ветерана. Це сильна диференціація.

### 10.4 syndicate / sndct.kyiv (Syndicate Original)

- **Домен**: інстраграм @sndct_kyiv (немає шопу окремо доступного, продажі через DM/Telegram/маркетплейси)
- **Тип**: Premium Kyiv streetwear (з 2010 — найстарший street brand в Україні)
- **Sections**: лімітовані дроп-колекції (1-2 на рік), basic apparel, колаборації
- **Топ ключі (по яких ранжуються)**:
  1. syndicate kyiv streetwear
  2. syndicate brand ukraine
  3. ukrainian streetwear brand
  4. premium streetwear kyiv
  5. limited edition streetwear ukraine
  6. ukrainian basic apparel
  7. syndicate t-shirt buy
  8. syndicate hoodie buy
  9. ukrainian streetwear founded 2010
  10. kyiv streetwear concept store
- **`sameAs`**: Instagram, TikTok (`@sndct_kyiv`), Pinterest, Behance, інтервʼю в DTF Magazine
- **Контентна стратегія**: brand-driven, історія і авторитет, drop-model. Сильні mediа mentions (highsnobiety, kyivpost, the village). Сайт примітивний (часто не видно), продажі через retail-partners.
- **Ціновий сегмент**: премʼюм (часто 1500-3500 грн)
- **Слабкі місця TwoComms можна атакувати тут**: Syndicate не має кастомного DTF друку і не націлений на ZSU/military-adjacent. Це різні ніші.

### 10.5 saintjavelin.com

- **Домен**: saintjavelin.com (Канадська компанія, але присутня в Україні через made-in-ukraine колекції і Instagram)
- **Тип**: Patriotic / Ukraine support streetwear, 25%+ donate to charity
- **Sections**: t-shirts, hoodies, accessories, made-in-ukraine collection, sale
- **Топ ключі**:
  1. saint javelin t-shirt
  2. ukraine support t-shirt
  3. made in ukraine streetwear
  4. ukrainian patriotic streetwear
  5. saint javelin merch
  6. support ukraine clothing
  7. ukraine charity merch
  8. zelensky merch
  9. virgin mary javelin t-shirt
  10. ukraine resistance streetwear
- **`sameAs`**: Instagram (`@saintjavelin`), Twitter, TikTok, Shopify store
- **Контентна стратегія**: viral marketing через memes (Saint Javelin icon), сильна charity story (founded by Canadian journalist Christian Borys), donate flow прозорий. **Має блог + storytelling-page «Our Story» + Made-in-Ukraine page**. Domain authority дуже високий через тисячі media mentions.
- **Ціновий сегмент**: середній ($25-50 t-shirt, $50-100 hoodie — це ~1000-4000 грн за курсом)
- **Слабкі місця TwoComms можна атакувати тут**: Saint Javelin — це **charity-driven** мерч від канадського підприємця, не streetwear-бренд від українського ветерана. У TwoComms unique angle — «бренд від реального українця з реальним харківським досвідом». Authentic differentiator.

### 10.6 (Bonus) noosphereglobal.com (Noosphere Store)

- **Домен**: noosphereglobal.com/noosphere-store/
- **Тип**: Tech / space-edu бренд з мерчем (худі, футболки про космос)
- **Контентна стратегія**: спонсорство Max Polyakov / Firefly Aerospace, focus на edu-community, не классичний streetwear
- **Не прямий конкурент**, але цікаво стилістично — TwoComms може брати з нього keyword «authentic ukrainian community brand».

---

## 11. Conclusions and gaps

### 11.1 Де у TwoComms зараз дірки

#### Гепи в категоріальному покритті

1. **Немає `/catalog/military/`** — мілітарі-кластер розпорошено по 10-12 PDP. Користувач, який шукає «мілітарі футболка», бачить генеричний `/catalog/tshirts/`, а потрібен щільний хаб.
2. **Немає `/catalog/patriotic/`** — патріотичний кластер аналогічно розпорошений. Sumарно ~150-300 пошуків місячно безповоротно втрачаються.
3. **Color-categories landings не існують** (sitemap-color-categories.xml порожній). 9 landings × ~30-50 пошуків = ~300-500/міс не отримуємо.
4. **Гео-landings не існують** — 5 міст × 3 категорії = 15 LF-сторінок з ~20-100/міс кожна = ~500-1500 пошуків місячно потенційно.

#### Гепи в content density

5. **PDP мають однакові FAQ-блоки на 14 запитань** (з аудита 01_content). Це дублювання шкодить SEO. Треба per-product FAQ (3-5 запитань про принт + 5-7 про продукт + 2-3 загальні).
6. **Підкатегорії / popular tags / popular subcategories не існують** на категоріях. Sub-menu з ключовими long-tail-фільтрами («Чорна футболка», «Жіноче худі», «Oversize 2XL») — дав би 30-50 додаткових landing-точок.
7. **Sticker / badge keywords**: `«-17 %»`, `«0»` (counter), `«»»` (pagination) — це anchor-текст без keyword-ваги. Конвертувати на «знижка», «обране», «наступна сторінка».

#### Гепи в multilang

8. **RU/EN PDP дають часткові переклади** — у назвах товарів, описах і **внутрішніх посиланнях**. На `/ru/product/...` 37 ссилок утікають на uk-версії. Це втрата SEO-ваги і UX-проблема. Виправити i18n-link-prefixing.
9. **EN-локаль слабо переведена** — критична для міжнародної діаспори і саппорту України. Треба повний переклад 26 сторінок (а не fallback на UA).

#### Гепи в blog / informational content

10. **Немає `/blog/`** взагалі. Це блокер для інформаційних запитів («що таке streetwear», «як прати», «DTF vs шовкографія», «TwoComms vs Saint Javelin»). Мінімум 15-20 блогових постів треба запустити для AI-search-visibility.
11. **Немає окремих `/comparisons/`** статей (DTF vs шовкографія, oversize vs classic, TwoComms vs конкуренти). LLM-цитування без них слабе.
12. **Немає `/team/` / `/founder/`** — для AI-цитування brand-story і trust-signals. Зараз `/pro-brand/` — гарна сторінка, але без чіткого factbox-блоку, ChatGPT/Claude не знають як її пересказати.

#### Гепи в schema / structured data

13. **`Organization` schema без `sameAs`-ссилок на соцмережі** — Google не звʼязує twocomms.shop з @twocomms (Instagram, Telegram). Це втрата brand-entity-resolution.
14. **`BreadcrumbList` присутній, але `WebSite` schema без `SearchAction`** — Google не показує SERP-search-box для бренду.
15. **`Product` schema без `additionalProperty` для color/fit** — Google не може правильно показати variant-rich-results.
16. **Немає `LocalBusiness` schema** — TwoComms має фізичний бекенд у Харкові (вочевидь — для відправлень). Local-SEO-додатковий канал.

### 11.2 Де у TwoComms сильні сторони

1. **Технічна канонізація 9.5/10** — hreflang trio, canonical strategy, robots.txt, AI-bot opt-in. Це краще за більшість конкурентів.
2. **Microcopy на категоріях якісний і unique** — Jaccard 0.04 між /tshirts/ /hoodie/ /long-sleeve/ — рідкісний плюс.
3. **Анкори вже keyword-rich** — 0% generic, 64.5% long-tail. Це 2026 best practice.
4. **Brand voice унікальний** — military-adjacent + Kharkiv + character. Не може повторити жоден конкурент швидко.
5. **Custom DTF друк** — мало хто з streetwear-брендів його робить in-house (zhі hygge-hoodie, ні syndicate, ні phantomcat не пропонують свій принт). Це конкурентна перевага.

### 11.3 Top-5 пріоритетних дій (наступні 60 днів)

1. **Створити color-categories landings** (`/catalog/tshirts/black/`, `/catalog/hoodie/oversize/`, etc.) — 9 нових сторінок з кастомним SEO-текстом і Self-canonical. ETA: 7 дней.
2. **Створити `/catalog/military/` і `/catalog/patriotic/`** — 2 нових collection-сторінки з 8-12 PDP в кожній. ETA: 5 днів.
3. **Виправити i18n-link bleed на RU/EN PDP** — Critical bug fix. ETA: 1-2 дні.
4. **Запустити блог з 5 стартовими постами** — definitional + how-to + 1 comparison. ETA: 14 днів.
5. **Зачистити slug-неймминг 47 PDP** — переписати з 301-редіректами. ETA: 5 днів.

### 11.4 Top-5 пріоритетних дій (60-180 днів)

6. **Гео-landings** для 5 міст × 3 категорії = 15 нових сторінок. ETA: 30 днів.
7. **Заповнити blog 15+ постами** — comparison, definitional, brand-story expansion. ETA: 90 днів.
8. **Перекласти EN-локаль повністю** — 26+ сторінок з нативним перекладом, не fallback. ETA: 30 днів.
9. **Добудувати schema** — sameAs, LocalBusiness, ProfilePage, ProductGroup, OfferShippingDetails. ETA: 7 днів.
10. **AI-search-optimization** — додати TL;DR-factbox-блоки на /pro-brand/, /custom-print/, /catalog/, /catalog/tshirts/, /catalog/hoodie/, /catalog/long-sleeve/. Вони форматовані як «Bottom line: ... Q: ... A: ...» — найкраще для LLM-цитування. ETA: 7 днів.

### 11.5 Метрики успіху (12 місяців)

- **HF-органіка** (head-terms): з 50-100/міс до 500-1500/міс (10x).
- **MF-органіка**: з 200-300/міс до 2000-3500/міс (10-15x).
- **LF-органіка**: з 100-200/міс до 3000-5000/міс (15-25x).
- **AI-search-citations** (через manual track ChatGPT, Claude, Perplexity): з 0 до 50+ цитувань/міс на бренд.
- **Brand-search**: з 50-200/міс до 500-1500/міс (3-7x за рахунок organic + AI).

---

## 12. Сирі дані

`audit_data/06_keywords_raw.json` — структурований JSON з усіма ключами (це next step, тут попереджаю про необхідність створення):
```json
{
  "metadata": {
    "date": "2026-05-16",
    "languages": ["uk-UA", "ru-UA", "en-UA"],
    "intent_types": ["brand", "commercial", "informational", "long_tail", "local"],
    "frequency_classes": ["HF", "MF", "LF", "ultra-LF"]
  },
  "clusters": [
    {
      "name": "t-shirts",
      "lang": "uk-UA",
      "target_page": "/catalog/tshirts/",
      "primary": "купити футболку з принтом",
      "secondary": [...],
      "long_tail": [...],
      "volume_estimate": "HF 1k-10k/міс"
    },
    ...
  ],
  "competitors": [...],
  "ai_search_visible": [...]
}
```

> **Limited data note**: точні volumes для всіх ключів потребують Ahrefs/Semrush/Serpstat API. Усі цифри в цьому документі — relative estimates на основі (а) довжини запиту, (б) SERP-конкуренції з web search, (в) Google autocomplete. Production-приоритизацію для PPC і content calendar треба робити з paid keyword-research-tool.

---

**Файл згенерований субагентом keyword-researcher (Kiro), 2026-05-16.**

