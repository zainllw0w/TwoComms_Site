"""Per-product SEO content block (US-3).

This module owns the **single biggest SEO win** in the molecular-upgrade
spec: dynamic, per-product long-form copy that gives every PDP a
genuinely unique footer block instead of the 80%+ shared boilerplate
the audit found in ``audit/01b_pdp_findings.md``.

Why this matters
----------------
The audit measured pairwise 5-gram shingle Jaccard overlap of >70% on
40+ PDP pairs and >80% on the worst offenders. Google's near-duplicate
detection collapses such clusters and refuses to index more than one
representative — so the catalogue ranks for the brand head-term but
loses essentially all long-tail traffic.

This service generates seven self-contained sections per product. Each
section pulls from a **pool of variants** (3–5 alternative wordings)
and the variant index is selected deterministically from a hash of
the product slug + section id. Combined with product-specific tokens
(title, slug, category, palette, sizes, fit, material, topic
narrative), the 5-gram shingle Jaccard between any two PDPs stays
materially below the 80% baseline; CP-3.1 targets ≤30%.

Phase A (initial commit, 2026-05-16)
------------------------------------
* Single template per section. Effective overlap ~55–70%.

Phase B (this commit, 2026-05-16)
---------------------------------
* Variant pools per section (3–5 wordings) with deterministic pick.
* Topic-specific FAQ deltas merged on top of the generic 4-item base.
* Section paragraph ordering shuffled per product hash so the 5-gram
  windows differ even when individual sentences repeat.
* Per-product material / colour / size narratives plug into multiple
  positions so token diversity rises with each variant pick.
"""
from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional, Sequence, Tuple

from django.utils.translation import get_language
from django.utils.translation import gettext as _

# ---------------------------------------------------------------------------
# Topic detection — maps title/slug tokens to a narrative archetype.
# Order matters: the first match wins, so put more specific keys first.
# ---------------------------------------------------------------------------

_TOPIC_KEYWORDS: List[Tuple[str, Tuple[str, ...]]] = [
    ("kharkiv", ("kharkiv", "kha-style", "kha-edition", "харків", "харьков")),
    ("pokrovsk", ("pokrovsk", "покровськ", "покровск")),
    ("ukraine_glory", ("glory-of-ukraine", "glory_of_ukraine", "слава україн", "слава украин")),
    ("zsu_225", ("225", "ошп", "штурмовий", "штурмов")),
    ("business_code", ("business-money", "бізнес", "бизнес", "business")),
    ("reality_bends", ("reality-bends", "reality_bends", "future-2026", "future_2026")),
    ("military_print", ("military", "мілітарі", "милитари", "war", "soldier", "tactical")),
    ("street_print", ("street", "стріт", "стрит", "skate", "punk", "graff")),
]

_TOPIC_NARRATIVES: Dict[str, Dict[str, List[str]]] = {
    "kharkiv": {
        "uk": [
            "Це принт про Харків — місто, де народився TwoComms і де щодня відбувається його справжнє тестування. Малюнок на {title} зроблений як знак для тих, хто розуміє, звідки бренд і чому ми не вдягаємось як інші.",
            "Графіка {title} — про харківську оптику. Не туристичну і не пафосну: про щоденний ритм міста, в якому народжуються і ламаються стилі.",
            "Харків — це не локація на упаковці, це матриця бренду. {title} робилась у цеху за 700 метрів від місця, яке стало іконою.",
        ],
        "ru": [
            "Это принт о Харькове — городе, где родился TwoComms и где каждый день идёт его настоящая проверка. Рисунок на {title} сделан как знак для тех, кто понимает, откуда бренд и почему мы не одеваемся как остальные.",
            "Графика {title} — о харьковской оптике. Не туристической и не пафосной: о ежедневном ритме города, в котором рождаются и ломаются стили.",
            "Харьков — это не локация на упаковке, это матрица бренда. {title} делалась в цехе за 700 метров от места, которое стало иконой.",
        ],
        "en": [
            "This is a Kharkiv print — about the city where TwoComms was born and where the brand is stress-tested every day. The graphic on {title} is a sign for the ones who know the source.",
            "The {title} graphic is built around the Kharkiv lens — not the tourist version, not the heroic one. The everyday rhythm of a city where styles are born and broken.",
            "Kharkiv isn't a tag on the packaging — it's the brand's operating system. {title} was made 700 meters from a place that's now an icon.",
        ],
    },
    "pokrovsk": {
        "uk": [
            "Принт «Покровськ» — про стійкість міста і людей, які тримають його лінію. {title} робилась тиражем, який не перевиробляється: малюнок належить історії, а не маркетинговій сезонності.",
            "Покровськ — символ прифронтової стійкості. {title} носить цей знак без агітки і без пафосу: знає той, хто знає.",
            "Принт відсилає до людей з Покровська — у місто, у яке поверталися навіть з 7-х категорій поранень. {title} зберігає цей тон як код, не як декорацію.",
        ],
        "ru": [
            "Принт «Покровск» — о стойкости города и людей, держащих его линию. {title} делалась тиражом, который не масштабируется: рисунок принадлежит истории, а не маркетинговому сезону.",
            "Покровск — символ прифронтовой стойкости. {title} несёт этот знак без агитки и без пафоса: знает тот, кто знает.",
            "Принт отсылает к людям из Покровска — в город, в который возвращались даже с 7-й категории ранений. {title} держит этот тон как код, не как декор.",
        ],
        "en": [
            "The Pokrovsk print speaks about a city and the people holding its line. {title} ships in a deliberately small run — the graphic belongs to history, not to a sales calendar.",
            "Pokrovsk is a symbol of frontline endurance. {title} carries the mark without slogans and without theatrics — recognised by the people who know.",
            "The graphic refers to those who returned to Pokrovsk even from category-7 wounds. {title} keeps the tone as code, not as decoration.",
        ],
    },
    "ukraine_glory": {
        "uk": [
            "Принт «Glory of Ukraine» працює як ідентифікаційний знак: вдягаючи {title}, ти не декларуєш патріотизм — ти його повсякденно носиш разом з усім іншим, що з тобою щодня.",
            "{title} — про спокійну українську ідентичність без зайвих доказів. Ми не пишемо «слава Україні» гігантськими літерами; знак вдягається як гардероб, не як прапор.",
            "Glory of Ukraine у дизайні TwoComms — це не лозунг, це короткий шифр для тих, хто звик читати між рядків. {title} має його у спокійній графічній мові.",
        ],
        "ru": [
            "Принт «Glory of Ukraine» работает как опознавательный знак: надевая {title}, ты не декларируешь патриотизм — ты его ежедневно носишь вместе со всем остальным, что с тобой каждый день.",
            "{title} — о спокойной украинской идентичности без лишних доказательств. Мы не пишем «слава Украине» гигантскими буквами; знак надевается как гардероб, не как флаг.",
            "Glory of Ukraine в дизайне TwoComms — это не лозунг, это короткий шифр для тех, кто читает между строк. {title} держит его в спокойной графике.",
        ],
        "en": [
            "The Glory of Ukraine print works as an identifier: wearing {title} you don't declare patriotism — you carry it day to day, alongside everything else that travels with you.",
            "{title} carries a quiet Ukrainian identity that doesn't shout. There is no oversize banner — the mark dresses like wardrobe, not like a flag.",
            "Glory of Ukraine in the TwoComms design language is not a slogan but a short cypher for the people who read between the lines — {title} holds it inside a calm graphic.",
        ],
    },
    "zsu_225": {
        "uk": [
            "Принт відсилає до 225-го окремого штурмового полку — підрозділу, командир якого, Герой України Олег Ширяєв, особисто проявив інтерес до бренду. {title} — частина серії речей з кодом, який зчитує лише той, хто має до нього стосунок.",
            "{title} — у серії 225-го ОШП. Один із кодів, який дізнаються одиниці, але саме вони і є цільовою аудиторією.",
            "Графіка 225-го ОШП на {title} — це знак конкретного підрозділу, не загальна патріотична образність. Носять знаючі.",
        ],
        "ru": [
            "Принт отсылает к 225-му отдельному штурмовому полку — подразделению, командир которого, Герой Украины Олег Ширяев, лично проявил интерес к бренду. {title} — часть серии вещей с кодом, который считывает только тот, кто к нему причастен.",
            "{title} — в серии 225-го ОШП. Один из кодов, который узнают единицы, но именно они и есть целевая аудитория.",
            "Графика 225-го ОШП на {title} — знак конкретного подразделения, а не общая патриотическая образность. Носят знающие.",
        ],
        "en": [
            "The print references the 225th Independent Assault Regiment — the unit whose commander, Hero of Ukraine Oleh Shyryaiev, personally engaged with the brand. {title} belongs to a series carrying a code only the people inside read.",
            "{title} sits inside the 225th regiment series — a code that only a few read, but those few are exactly the audience.",
            "The 225th regiment graphic on {title} is the sign of a specific unit, not a generic patriotic motif. Worn by people in the know.",
        ],
    },
    "business_code": {
        "uk": [
            "«Бізнес — це математика» — принт про підприємницьку оптику: не магія, а формула. {title} зроблена для людей, які тримають P&L у голові і не розраховують на удачу.",
            "Принт нагадує: підприємництво — про арифметику маржі, юніт-економіку і витривалість. {title} — щоденна форма для тих, хто живе у цій формулі.",
            "{title} — для аудиторії, яка дивиться на бізнес як на систему рівнянь. Принт читається як заголовок книги, яку ти тримаєш у голові.",
        ],
        "ru": [
            "«Бизнес — это математика» — принт о предпринимательской оптике: не магия, а формула. {title} сделана для людей, которые держат P&L в голове и не рассчитывают на удачу.",
            "Принт напоминает: предпринимательство — это арифметика маржи, юнит-экономика и выносливость. {title} — ежедневная форма для тех, кто живёт в этой формуле.",
            "{title} — для аудитории, которая смотрит на бизнес как на систему уравнений. Принт читается как заголовок книги, которую держишь в голове.",
        ],
        "en": [
            "Business is math — a print about an operator's optics: no magic, just formulas. {title} is made for people who keep their P&L in their head and don't bet on luck.",
            "The print reminds you: entrepreneurship is margin arithmetic, unit economics and endurance. {title} is the daily uniform for the people who live inside that formula.",
            "{title} is for the audience that sees business as a system of equations. The print reads like a book title you carry in your head.",
        ],
    },
    "reality_bends": {
        "uk": [
            "Принт «Reality Bends» з колекції Future 2026 — про здатність продовжувати після критичної точки. {title} носить це повідомлення без декору і пафосу, як робочий інструмент.",
            "Reality Bends — три варіанти принта в одній капсулі. {title} тримає не графіку, а коротке твердження: реальність гнеться, але не ламає тих, хто продовжує.",
            "{title} зашифрована у мовою Future 2026: рукотворний шрифт, мінімалістичний шум, без декоративного слою. Носиться як підпис.",
        ],
        "ru": [
            "Принт «Reality Bends» из коллекции Future 2026 — о способности продолжать после критической точки. {title} несёт это сообщение без декора и пафоса, как рабочий инструмент.",
            "Reality Bends — три варианта принта в одной капсуле. {title} держит не графику, а короткое утверждение: реальность гнётся, но не ломает тех, кто продолжает.",
            "{title} зашифрована в языке Future 2026: рукотворный шрифт, минималистичный шум, без декоративного слоя. Носится как подпись.",
        ],
        "en": [
            "The Reality Bends print from the Future 2026 capsule is about the ability to continue past a critical point. {title} carries that message without decor or theatrics, as a working tool.",
            "Reality Bends comes in three variants inside a single capsule. {title} doesn't carry a graphic but a short statement: reality bends, but it doesn't break those who continue.",
            "{title} is written in the Future 2026 language: a hand-drawn typeface, minimalist noise, no decorative layer. Worn as a signature.",
        ],
    },
    "military_print": {
        "uk": [
            "Це частина military-adjacent ліній TwoComms — естетика без косплею. {title} вдягнута в харківський ДНК бренду і в код людей, які мають стосунок до служби, але одягаються щодня, не на параді.",
            "{title} — military без агітки. Графіка, яка зчитується для своїх і не виглядає декоративною для всіх інших.",
            "Принт працює у military-adjacent логіці: без шевронів-копій, без бутафорії, з акуратною графікою для повсякденного носіння.",
        ],
        "ru": [
            "Это часть military-adjacent линий TwoComms — эстетика без косплея. {title} одета в харьковский ДНК бренда и в код людей, которые имеют отношение к службе, но одеваются каждый день, не на параде.",
            "{title} — military без агитки. Графика, которая считывается для своих и не выглядит декоративной для всех остальных.",
            "Принт работает в military-adjacent логике: без шевронов-копий, без бутафории, с аккуратной графикой для ежедневного ношения.",
        ],
        "en": [
            "Part of the TwoComms military-adjacent lines — aesthetic without cosplay. {title} carries the Kharkiv DNA of the brand and the code of people connected to service who dress every day, not for parade.",
            "{title} is military without slogans. A graphic that reads for the insiders and doesn't look decorative to anyone else.",
            "The print runs in a military-adjacent logic: no copy-paste patches, no costume jewellery, only clean graphics for everyday wear.",
        ],
    },
    "street_print": {
        "uk": [
            "Це принт зі streetwear-крила TwoComms: без політики, без військових цитат, чистий міський код. {title} зібрана для звичайного дня, в якому одяг має тримати свою лінію.",
            "{title} — streetwear як код для свого, а не як форма безбородої молоді. Чисті лінії, акуратна графіка, без галасу.",
            "Принт зі streetwear-капсулі: без героїчних мотивів, без меседжів — графічна щільність і характер посадки роблять свою справу.",
        ],
        "ru": [
            "Это принт из streetwear-крыла TwoComms: без политики, без военных цитат, чистый городской код. {title} собрана для обычного дня, в котором одежда должна держать свою линию.",
            "{title} — streetwear как код для своих, а не как форма безбородой молодёжи. Чистые линии, аккуратная графика, без шума.",
            "Принт из streetwear-капсулы: без героических мотивов, без месседжей — графическая плотность и характер посадки делают своё дело.",
        ],
        "en": [
            "From the TwoComms streetwear wing: no politics, no military quotes, just an urban code. {title} is built for the ordinary day in which clothing has to hold its line.",
            "{title} reads streetwear as a code for the insiders, not as a uniform for unmoored youth. Clean lines, careful graphics, no noise.",
            "A print from the streetwear capsule: no heroic motifs, no messaging — graphic density and the cut do the work.",
        ],
    },
    "generic": {
        "uk": [
            "{title} — частина авторської лінії TwoComms, заснованого ветераном з Харкова. Кожна модель серії «{slug}» носить власну причину існування: ми не випускаємо одяг заради сезону.",
            "{title} створена як окремий висказ, не як ще одна позиція у сезонному дропі. Серія «{slug}» зашифрована у графіку, яку важко переплутати з масовим streetwear.",
            "Серія «{slug}» — частина авторського ряду TwoComms. {title} — її конкретна реалізація: щільна база, чітка посадка, графіка зі змістом.",
        ],
        "ru": [
            "{title} — часть авторской линии TwoComms, основанного ветераном из Харькова. Каждая модель серии «{slug}» несёт собственную причину существования: мы не выпускаем одежду ради сезона.",
            "{title} создана как отдельное высказывание, а не очередная позиция в сезонном дропе. Серия «{slug}» зашифрована в графике, которую сложно спутать с массовым streetwear.",
            "Серия «{slug}» — часть авторского ряда TwoComms. {title} — её конкретная реализация: плотная база, чёткая посадка, графика со смыслом.",
        ],
        "en": [
            "{title} belongs to the author line of TwoComms, founded by a Kharkiv veteran. Every piece in the «{slug}» series carries its own reason to exist — we don't ship clothing just for the season.",
            "{title} is built as a standalone statement, not another item in a seasonal drop. The «{slug}» series is written in graphics that are hard to mistake for mass streetwear.",
            "The «{slug}» series is part of the TwoComms author line. {title} is its concrete realisation: dense base, clean fit, graphics with meaning.",
        ],
    },
}

# ---------------------------------------------------------------------------
# Section variant pools — each section has 3–5 wordings per language.
# A deterministic per-product hash picks one variant; combined with
# product tokens (title/slug/category/colors/sizes/material), this
# yields the section diversity required by CP-3.1.
# ---------------------------------------------------------------------------

_SECTION_TEMPLATES: Dict[str, Dict[str, List[str]]] = {
    "hero_followup": {
        "uk": [
            "Цей {category_phrase} зроблений у Харкові — TwoComms веде дизайн, друк і контроль якості з одного цеху. Жодних абстрактних колаборацій з невідомим виробником: усе, що ти бачиш на фото {title}, виходить з одних рук.",
            "{title} — щільна база і авторський DTF-друк, виготовлено в Україні. Жодних офшорних масштабувань: тираж тримається у межах, де можна особисто перевірити якість.",
            "Виробництво {title} у Харкові, контроль кожного етапу — від крою до пакування. Ми не шиємо тисячами одиниць заради знижки; ми шиємо стільки, скільки можемо стояти за кожною річчю.",
            "{title} проходить п'ять стадій контролю: тканина, крій, пошиття, друк, фінішна перевірка. Робимо це у Харкові і пакуємо тут же; жодних довгих ланцюгів між штатами.",
        ],
        "ru": [
            "Эта {category_phrase} сделана в Харькове — TwoComms ведёт дизайн, печать и контроль качества из одного цеха. Никаких абстрактных коллабораций с неизвестным производителем: всё, что ты видишь на фото {title}, выходит из одних рук.",
            "{title} — плотная база и авторская DTF-печать, изготовлено в Украине. Никаких офшорных масштабирований: тираж держится в пределах, где можно лично проверить качество.",
            "Производство {title} в Харькове, контроль каждого этапа — от кроя до упаковки. Мы не шьём тысячами единиц ради скидки; мы шьём столько, сколько можем стоять за каждой вещью.",
            "{title} проходит пять стадий контроля: ткань, крой, пошив, печать, финишная проверка. Делаем это в Харькове и упаковываем здесь же; никаких длинных цепей между штатами.",
        ],
        "en": [
            "This {category_phrase} is made in Kharkiv — TwoComms runs design, print and QA from one workshop. No abstract collaborations with an unknown factory: everything you see on the {title} photos comes out of a single set of hands.",
            "{title} ships with a dense base and an author DTF print, made in Ukraine. No offshore scaling — the run stays within a size where the founder can inspect each unit personally.",
            "{title} is produced in Kharkiv, with QA at every stage from cut to packaging. We don't push thousands of units for a discount; we ship the volume we can personally vouch for.",
            "{title} passes five inspection stages: fabric, cut, sewing, print, final QA. Done in Kharkiv, packed in Kharkiv — no long supply chains across states.",
        ],
    },
    "who_for": {
        "uk": [
            "{title} підійде тим, хто шукає не просто {category_phrase} з принтом, а річ, яка має причину існування. Розміри {size_phrase} закривають класичну і oversize посадку, кольори ({color_phrase}) дають вибір під щоденну ротацію.",
            "Цільова аудиторія {title} — люди, які не вдягаються «під сезон», а збирають гардероб як систему. Розмірний ряд {size_phrase}, палітра {color_phrase}.",
            "Ця {category_phrase} буде працювати як повсякденна база для тих, хто звик читати графіку як шифр, а не як декорацію. Розміри {size_phrase}; доступні відтінки: {color_phrase}.",
            "{title} робилась під людей, для яких принт — частина характеру, а не сезонне настроєння. Посадка — вибір regular або oversize, розміри {size_phrase}, кольори {color_phrase}.",
            "Якщо ти серед тих, хто шукає {category_phrase} з характером і власним кодом — {title} тобі підходить. Розміри: {size_phrase}; палітра: {color_phrase}.",
        ],
        "ru": [
            "{title} подойдёт тем, кто ищет не просто {category_phrase} с принтом, а вещь, у которой есть причина существования. Размеры {size_phrase} закрывают классическую и оверсайз посадку, цвета ({color_phrase}) дают выбор под ежедневную ротацию.",
            "Целевая аудитория {title} — люди, которые не одеваются «под сезон», а собирают гардероб как систему. Размерный ряд {size_phrase}, палитра {color_phrase}.",
            "Эта {category_phrase} будет работать как повседневная база для тех, кто привык читать графику как шифр, а не как декор. Размеры {size_phrase}; доступные оттенки: {color_phrase}.",
            "{title} делалась под людей, для которых принт — часть характера, а не сезонное настроение. Посадка — выбор regular или оверсайз, размеры {size_phrase}, цвета {color_phrase}.",
            "Если ты среди тех, кто ищет {category_phrase} с характером и собственным кодом — {title} тебе подходит. Размеры: {size_phrase}; палитра: {color_phrase}.",
        ],
        "en": [
            "{title} works for people who don't want just another printed {category_phrase} but a piece with a reason to exist. Sizes {size_phrase} cover both regular and oversize fits; colours ({color_phrase}) give options for the daily rotation.",
            "The audience for {title} is the people who don't dress «for the season» but build their wardrobe as a system. Size run {size_phrase}, palette {color_phrase}.",
            "This {category_phrase} works as a daily base for the people who read graphics as a cypher, not decoration. Sizes {size_phrase}; available shades: {color_phrase}.",
            "{title} was made for people whose print is a part of their character, not a seasonal mood. Choose between regular and oversize fit, sizes {size_phrase}, colours {color_phrase}.",
            "If you're looking for a {category_phrase} with character and a private code — {title} fits. Sizes: {size_phrase}; palette: {color_phrase}.",
        ],
    },
    "how_to_style": {
        "uk": [
            "{title} тримає форму як у соло-образі, так і в шарі: під лонгслівом, всередині розстібнутої сорочки, з технічними штанами або з прямими денімами. Якщо береш одну з кольорових версій — спробуй збирати гардероб поверх неї, а не від «верхнього шару».",
            "Стилізація {title}: працює як основа під техвір-куртку, як солод під оверсайз худі або як самостійний верх у міському casual-сетапі. Палітра ({color_phrase}) дозволяє грати з тонами карго і техніки.",
            "Кращий сетап для {title} — пряма пара денімів, технічні мокасини або робочі чо́боти і поясна сумка. Якщо береш темну версію — додай металевий аксесуар; якщо світлу — нейтральний хедвір.",
            "{title} читається у трьох сетапах: техноурбан з карго і кросами; робочий smart-casual з прямими брюками і черевиками; і чистий streetwear з оверсайз-низом. Універсальна базова форма.",
        ],
        "ru": [
            "{title} держит форму и в соло-образе, и в слое: под лонгсливом, внутри расстёгнутой рубашки, с техническими штанами или с прямыми денимами. Если берёшь одну из цветовых версий — попробуй собирать гардероб поверх неё, а не от «верхнего слоя».",
            "Стилизация {title}: работает как основа под техвир-куртку, как солод под оверсайз худи или как самостоятельный верх в городском casual-сетапе. Палитра ({color_phrase}) даёт играть с тонами карго и техники.",
            "Лучший сетап для {title} — прямая пара денимов, технические мокасины или рабочие ботинки и поясная сумка. Если берёшь тёмную версию — добавь металлический аксессуар; если светлую — нейтральный хедвир.",
            "{title} читается в трёх сетапах: техноурбан с карго и кроссами; рабочий smart-casual с прямыми брюками и ботинками; и чистый streetwear с оверсайз-низом. Универсальная базовая форма.",
        ],
        "en": [
            "{title} holds shape solo and in a layer: under a long sleeve, inside an unbuttoned shirt, with technical pants or with straight denim. If you pick one of the colour options, try building the wardrobe over it instead of from the «outer layer».",
            "{title} styling: works as a base for a techwear jacket, as a solid under an oversize hoodie, or as a standalone top in an urban casual setup. The palette ({color_phrase}) lets you play with cargo and tech tones.",
            "Best setup for {title}: a straight pair of denim, tech mocs or work boots, and a waist bag. With the darker version, add a metal accessory; with a lighter one, go with a neutral headpiece.",
            "{title} reads in three setups: technurban with cargo and trainers; working smart-casual with straight trousers and boots; clean streetwear with oversize bottoms. A universal base.",
        ],
    },
    "care": {
        "uk": [
            "Прання {title} — холодна вода 30 °C, без хлорних відбілювачів. DTF-принт зберігає колір довше, якщо сушити річ навиворіт. Прасуй з виворіту, не наводь праску прямо на зону друку. Матеріал — {material}.",
            "{title} витримує до 30 циклів прання без помітної усадки при дотриманні режиму. Не сушити в електросушарці на високій температурі; матеріал — {material}.",
            "Догляд за {title}: ручне або делікатне прання у машинці, температура до 30 °C, віджим до 600 об/хв. Сушка горизонтально на рушнику. Матеріал — {material}; повний гайд у розділі «Догляд за одягом».",
            "{title} прати з виворіту разом з речами схожого кольору. Без агресивних плямовивідників. Прасування — теплою праскою з виворіту, не на принті. Матеріал — {material}.",
        ],
        "ru": [
            "Стирка {title} — холодная вода 30 °C, без хлорных отбеливателей. DTF-принт держит цвет дольше, если сушить вещь наизнанку. Гладь с изнанки, не направляй утюг на зону печати. Материал — {material}.",
            "{title} выдерживает до 30 циклов стирки без заметной усадки при соблюдении режима. Не сушить в электросушилке на высокой температуре; материал — {material}.",
            "Уход за {title}: ручная или деликатная стирка в машине, температура до 30 °C, отжим до 600 об/мин. Сушка горизонтально на полотенце. Материал — {material}; полный гайд в разделе «Уход за одеждой».",
            "{title} стирай с изнанки вместе с вещами схожего цвета. Без агрессивных пятновыводителей. Глажка — тёплым утюгом с изнанки, не на принте. Материал — {material}.",
        ],
        "en": [
            "Wash {title} in cold water at 30 °C, no chlorine bleach. The DTF print keeps its colour longer when you dry the piece inside-out. Iron from the inside; do not point the iron at the print area directly. Material: {material}.",
            "{title} survives up to 30 wash cycles without meaningful shrinkage if you follow the regime. Do not tumble-dry on high heat; material: {material}.",
            "Care for {title}: hand or delicate-cycle machine wash, max 30 °C, max 600 RPM spin. Dry flat on a towel. Material: {material}; full guide in the «Apparel care» section.",
            "Wash {title} inside-out with similarly coloured items. No aggressive stain removers. Iron with a warm setting from the inside, not over the print. Material: {material}.",
        ],
    },
    "delivery": {
        "uk": [
            "{title} відвантажуємо за 1–2 робочі дні після підтвердження. Доставка Новою Поштою або Укрпоштою по всій Україні; для Києва і Харкова доступний кур'єр того ж дня для готових позицій.",
            "Доставка {title} — Нова Пошта (відділення / поштомат / адресна), Укрпошта, DPD. Замовлення підтверджуємо протягом 1 години у робочий час, відправляємо в той же день при оформленні до 14:00.",
            "{title} приходить у щільному поліетиленовому пакеті з логотипом TwoComms у крафт-конверт; всередині — наклейка з QR на сторінку догляду і подяку від команди. Доставка по Україні — Нова Пошта.",
            "Заявку на {title} приймаємо у будь-який зручний час. Менеджер пишеться у Telegram або по телефону. Оплата онлайн (картка / Apple Pay / Google Pay) або накладений платіж на отриманні.",
        ],
        "ru": [
            "{title} отгружаем за 1–2 рабочих дня после подтверждения. Доставка Новой Почтой или Укрпочтой по всей Украине; для Киева и Харькова доступен курьер день в день для готовых позиций.",
            "Доставка {title} — Новая Почта (отделение / почтомат / адресная), Укрпочта, DPD. Заказы подтверждаем в течение 1 часа в рабочее время, отправляем в тот же день при оформлении до 14:00.",
            "{title} приходит в плотном полиэтиленовом пакете с логотипом TwoComms внутри крафт-конверта; внутри — наклейка с QR на страницу ухода и благодарность от команды. Доставка по Украине — Новая Почта.",
            "Заявку на {title} принимаем в любое удобное время. Менеджер пишет в Telegram или по телефону. Оплата онлайн (карта / Apple Pay / Google Pay) или наложенный платёж на получении.",
        ],
        "en": [
            "We ship {title} within 1–2 business days after order confirmation. Delivery via Nova Poshta or Ukrposhta across Ukraine; same-day courier is available for Kyiv and Kharkiv on in-stock items.",
            "Shipping options for {title}: Nova Poshta (depot / post-locker / door-to-door), Ukrposhta, DPD. Orders are confirmed within an hour during business hours and dispatched the same day if placed before 14:00.",
            "{title} arrives in a dense polyethylene branded sleeve inside a kraft envelope. Inside you'll find a QR sticker linking to the care page and a thank-you note. Domestic delivery via Nova Poshta.",
            "Order {title} any time of day. Our manager will follow up via Telegram or phone. Pay online (card / Apple Pay / Google Pay) or use cash on delivery on pick-up.",
        ],
    },
    "why_us": {
        "uk": [
            "{title} робиться брендом, який заснував бойовий ветеран — Артем Синіло, Харків. Ми не масштабуємо тиражі заради знижки і не випускаємо колекції, де принти не мають змісту.",
            "Чому варто {title} саме у TwoComms: бренд має реальну ветеранську біографію, а не маркетингову; принти створюються з власною думкою, а не як тренд-слідування; виробництво — у Харкові з контролем кожного етапу.",
            "{title} приходить з гарантією 14 днів на повернення без причин і обмін на інший розмір/колір без додаткових витрат. Якщо щось не сходиться — пиши; ми відповідаємо швидко і не шукаємо причини відмовити.",
            "TwoComms — український streetwear / military-adjacent бренд з Харкова, заснований 1 липня 2025 року бойовим ветераном. {title} продовжує цей контекст: одяг з кодом для людей, які тримають форму зсередини.",
        ],
        "ru": [
            "{title} делается брендом, который основал боевой ветеран — Артём Синило, Харьков. Мы не масштабируем тиражи ради скидки и не выпускаем коллекции, где принты не имеют смысла.",
            "Почему стоит {title} именно у TwoComms: у бренда реальная ветеранская биография, а не маркетинговая; принты создаются со своим мнением, а не как следование трендам; производство — в Харькове с контролем каждого этапа.",
            "{title} приходит с гарантией 14 дней на возврат без причин и обмен на другой размер/цвет без доплат. Если что-то не сходится — напиши; мы отвечаем быстро и не ищем причины отказать.",
            "TwoComms — украинский streetwear / military-adjacent бренд из Харькова, основан 1 июля 2025 года боевым ветераном. {title} продолжает этот контекст: одежда с кодом для людей, которые держат форму изнутри.",
        ],
        "en": [
            "{title} is made by a brand founded by a combat veteran — Artem Synylo, Kharkiv. We don't scale runs for the sake of a discount and we don't ship collections whose graphics don't mean anything.",
            "Why buy {title} from TwoComms: the brand has a real veteran biography (not a marketing one); prints are made with an opinion, not as trend-following; production is in Kharkiv with QA at every stage.",
            "{title} ships with a 14-day no-questions-asked return policy and a free size/colour exchange. If anything doesn't add up, write to us; we reply fast and we don't look for reasons to decline.",
            "TwoComms is a Ukrainian streetwear / military-adjacent brand from Kharkiv, founded on July 1 2025 by a combat veteran. {title} continues that context: clothes with code for people who hold their shape from inside.",
        ],
    },
}

# ---------------------------------------------------------------------------
# FAQ pools — base 4 questions per language with multiple answer
# variants. Topic-specific deltas append additional Q/A on top.
# ---------------------------------------------------------------------------

_BASE_FAQ_POOL: Dict[str, List[List[Dict[str, List[str]]]]] = {
    "uk": [
        [
            {
                "q": ["Чи дає {title} усадку після прання?"],
                "a": [
                    "При дотриманні температури 30 °C і сушці на горизонтальній поверхні {title} тримає форму без помітної усадки. Матеріал — {material}, виробництво Україна, попередньо декатований.",
                    "Якщо стирати у режимі «делікатне» при 30 °C і сушити горизонтально, {title} зберігає посадку без усадки понад 1–2%. Тканина — {material}, попередньо декатована.",
                    "Усадка у межах 1% при правильному режимі прання. {title} проходить попередню декатировку у виробничому циклі; матеріал — {material}.",
                ],
            },
        ],
        [
            {
                "q": ["Які кольори доступні для {title}?", "У яких відтінках є {title}?"],
                "a": [
                    "{color_phrase} — саме ці варіанти зараз представлені у каталозі. Якщо потрібен інший колір — пиши менеджеру через сторінку «Контакти».",
                    "На сторінці товару показано усі кольори: {color_phrase}. Інші відтінки доступні під замовлення (терміни — від 7 днів).",
                    "Поточна палітра: {color_phrase}. Якщо плануєш командну партію — узгоджуємо колір окремо, без додаткової націнки за нестандартний відтінок.",
                ],
            },
        ],
        [
            {
                "q": ["Як обрати розмір {title}?", "Який розмір замовити для {title}?"],
                "a": [
                    "Розмірний ряд {title}: {size_phrase}. Якщо ти між розмірами — TwoComms рекомендує менший для посадки regular і більший для oversize. Деталі — у розмірній сітці.",
                    "Якщо вагаєшся між розмірами {size_phrase} — пиши свої заміри менеджеру і підкажемо. У сумнівах між «впритул» і «вільно» — обирай більший розмір для oversize-сетапа.",
                    "Розміри {size_phrase} відповідають класичній посадці. Для oversize-сетапа бери на 1 розмір більше. Деталі замірів — у таблиці розмірів TwoComms.",
                ],
            },
        ],
        [
            {
                "q": ["Скільки коштує доставка {title}?", "Як працює доставка {title} по Україні?"],
                "a": [
                    "За тарифами Нової Пошти / Укрпошти. Безкоштовна доставка при замовленні від 2500 грн на основні відділення.",
                    "Доставка по Україні — за тарифами перевізника. Замовлення від 2500 грн відвантажуємо безкоштовно на відділення Нової Пошти або Укрпошти.",
                    "Тариф визначається перевізником при формуванні накладної; зазвичай у межах 60–110 грн на відділення Нової Пошти. Безкоштовно — від 2500 грн.",
                ],
            },
        ],
    ],
    "ru": [
        [
            {
                "q": ["Даёт ли {title} усадку после стирки?"],
                "a": [
                    "При соблюдении температуры 30 °C и сушке на горизонтальной поверхности {title} держит форму без заметной усадки. Материал — {material}, производство Украина, предварительно декатирован.",
                    "Если стирать в режиме «деликатная» при 30 °C и сушить горизонтально, {title} сохраняет посадку без усадки сверх 1–2%. Ткань — {material}, предварительно декатирована.",
                    "Усадка в пределах 1% при правильном режиме стирки. {title} проходит предварительную декатировку в производственном цикле; материал — {material}.",
                ],
            },
        ],
        [
            {
                "q": ["Какие цвета доступны для {title}?", "В каких оттенках есть {title}?"],
                "a": [
                    "{color_phrase} — именно эти варианты сейчас представлены в каталоге. Если нужен другой цвет — напиши менеджеру через страницу «Контакты».",
                    "На странице товара показаны все цвета: {color_phrase}. Другие оттенки доступны под заказ (сроки — от 7 дней).",
                    "Текущая палитра: {color_phrase}. Если планируешь командную партию — согласовываем цвет отдельно, без дополнительной наценки за нестандартный оттенок.",
                ],
            },
        ],
        [
            {
                "q": ["Как выбрать размер {title}?", "Какой размер заказать для {title}?"],
                "a": [
                    "Размерный ряд {title}: {size_phrase}. Если ты между размерами — TwoComms рекомендует меньший для посадки regular и больший для оверсайз. Детали — в размерной сетке.",
                    "Если сомневаешься между размерами {size_phrase} — напиши свои замеры менеджеру и подскажем. В сомнениях между «впритык» и «свободно» — выбирай больший размер для оверсайз-сетапа.",
                    "Размеры {size_phrase} соответствуют классической посадке. Для оверсайз-сетапа бери на 1 размер больше. Детали замеров — в таблице размеров TwoComms.",
                ],
            },
        ],
        [
            {
                "q": ["Сколько стоит доставка {title}?", "Как работает доставка {title} по Украине?"],
                "a": [
                    "По тарифам Новой Почты / Укрпочты. Бесплатная доставка при заказе от 2500 грн на основные отделения.",
                    "Доставка по Украине — по тарифам перевозчика. Заказы от 2500 грн отгружаем бесплатно в отделения Новой Почты или Укрпочты.",
                    "Тариф определяется перевозчиком при формировании накладной; обычно в пределах 60–110 грн на отделение Новой Почты. Бесплатно — от 2500 грн.",
                ],
            },
        ],
    ],
    "en": [
        [
            {
                "q": ["Does {title} shrink after washing?"],
                "a": [
                    "At 30 °C and flat-drying, {title} keeps its shape with no meaningful shrinkage. Material is {material}, made in Ukraine, pre-shrunk before cut and sew.",
                    "Wash on the «delicate» cycle at 30 °C and dry flat — {title} stays within 1–2% shrinkage. Fabric is {material}, pre-shrunk.",
                    "Shrinkage stays within 1% on the correct wash regime. {title} is pre-shrunk in production; material: {material}.",
                ],
            },
        ],
        [
            {
                "q": ["Which colours does {title} come in?", "What shades are available for {title}?"],
                "a": [
                    "{color_phrase} — these are the variants currently in the catalogue. If you need a different colour, write to us via the Contacts page.",
                    "Product page lists every colour: {color_phrase}. Additional shades are available on order (lead time from 7 days).",
                    "Current palette: {color_phrase}. For a team batch, we can agree on a custom colour without an extra surcharge.",
                ],
            },
        ],
        [
            {
                "q": ["How do I pick the right size for {title}?", "Which size of {title} should I order?"],
                "a": [
                    "{title} ships in {size_phrase}. If you're between sizes, TwoComms recommends sizing down for a regular fit and up for oversize. Full detail in the size guide.",
                    "If you're hesitating between sizes {size_phrase}, send your measurements to our manager — we'll suggest a size. In doubt between «fitted» and «relaxed», size up for oversize setups.",
                    "Sizes {size_phrase} follow a classic fit. For oversize, add one size. Measurement details live in the TwoComms size guide.",
                ],
            },
        ],
        [
            {
                "q": ["How much is shipping for {title}?", "How does shipping work for {title} in Ukraine?"],
                "a": [
                    "Standard Nova Poshta or Ukrposhta tariffs. Free shipping on orders above UAH 2500 to the carrier's main depots.",
                    "Ukraine-wide delivery follows the carrier's tariff. Orders above UAH 2500 ship free to Nova Poshta or Ukrposhta depots.",
                    "Tariff is set by the carrier when the waybill is issued — typically UAH 60–110 to a Nova Poshta depot. Free shipping kicks in at UAH 2500.",
                ],
            },
        ],
    ],
}

# Topic-specific FAQ deltas (one extra Q/A per topic per language).
_TOPIC_FAQ_DELTAS: Dict[str, Dict[str, Dict[str, str]]] = {
    "kharkiv": {
        "uk": {
            "q": "Чому акцент саме на Харкові у дизайні {title}?",
            "a": "TwoComms заснований у Харкові, виробництво — у Харкові, авторський колектив — у Харкові. {title} несе цей бекграунд як частину ідентичності бренду, а не як декоративну деталь.",
        },
        "ru": {
            "q": "Почему акцент именно на Харькове в дизайне {title}?",
            "a": "TwoComms основан в Харькове, производство — в Харькове, авторский коллектив — в Харькове. {title} несёт этот бэкграунд как часть идентичности бренда, а не как декоративную деталь.",
        },
        "en": {
            "q": "Why does the {title} design lean on Kharkiv?",
            "a": "TwoComms is founded in Kharkiv, the production runs in Kharkiv, the author collective sits in Kharkiv. {title} carries that background as part of the brand identity, not as a decorative detail.",
        },
    },
    "zsu_225": {
        "uk": {
            "q": "Чи треба бути військовим, щоб носити {title} з принтом 225-го ОШП?",
            "a": "Ні. {title} відкритий для усіх, хто розуміє контекст і поважає його. Принт — це знак, не атрибут служби.",
        },
        "ru": {
            "q": "Нужно ли быть военным, чтобы носить {title} с принтом 225-го ОШП?",
            "a": "Нет. {title} открыт для всех, кто понимает контекст и уважает его. Принт — это знак, не атрибут службы.",
        },
        "en": {
            "q": "Do I need to be military to wear {title} with the 225th regiment print?",
            "a": "No. {title} is open to anyone who understands the context and respects it. The print is a sign, not a service attribute.",
        },
    },
    "pokrovsk": {
        "uk": {
            "q": "Це політичний принт, чи буде комфортно носити {title} щодня?",
            "a": "{title} зроблений як спокійна графіка, не як політичне висказування. Носиться як щоденна форма; принт читається тими, хто розуміє контекст.",
        },
        "ru": {
            "q": "Это политический принт, будет ли комфортно носить {title} каждый день?",
            "a": "{title} сделан как спокойная графика, не как политическое высказывание. Носится как ежедневная форма; принт читается теми, кто понимает контекст.",
        },
        "en": {
            "q": "Is this a political print — is it comfortable to wear {title} every day?",
            "a": "{title} is built as a calm graphic, not as a political statement. It wears as everyday gear; the print is read by people who know the context.",
        },
    },
    "business_code": {
        "uk": {
            "q": "Чи підійде {title} під робочий гардероб?",
            "a": "Так. {title} тримає посадку у smart-casual сетапах: пряма пара брюк, чисті кеди або черевики, накладений жакет. Принт читається як частина авторської графіки, не як декорація.",
        },
        "ru": {
            "q": "Подойдёт ли {title} под рабочий гардероб?",
            "a": "Да. {title} держит посадку в smart-casual сетапах: прямая пара брюк, чистые кеды или ботинки, наложенный жакет. Принт читается как часть авторской графики, не как декорация.",
        },
        "en": {
            "q": "Does {title} work with a smart-casual wardrobe?",
            "a": "Yes. {title} holds shape in smart-casual setups: straight trousers, clean trainers or boots, a layered jacket. The print reads as part of the author graphic, not as decoration.",
        },
    },
    "reality_bends": {
        "uk": {
            "q": "Скільки одиниць тиражу {title} у капсулі Future 2026?",
            "a": "Капсула Future 2026 — обмежена, виробляється короткими тиражами під попередні замовлення. {title} може зникнути з каталогу після поточного циклу — питай менеджера про залишок.",
        },
        "ru": {
            "q": "Сколько единиц тиража {title} в капсуле Future 2026?",
            "a": "Капсула Future 2026 — ограниченная, производится короткими тиражами под предзаказ. {title} может исчезнуть из каталога после текущего цикла — спрашивай менеджера про остаток.",
        },
        "en": {
            "q": "How many units of {title} are in the Future 2026 capsule?",
            "a": "The Future 2026 capsule is limited and ships on a short pre-order run. {title} may leave the catalogue after the current cycle — ask our manager about the remaining stock.",
        },
    },
    "ukraine_glory": {
        "uk": {
            "q": "Куди йдуть кошти від продажу {title}?",
            "a": "Частина прибутку TwoComms спрямовується на підтримку 225-го ОШП і ветеранських ініціатив (Український ветеранський фонд). Деталі — на сторінці «Про бренд».",
        },
        "ru": {
            "q": "Куда идут средства от продажи {title}?",
            "a": "Часть прибыли TwoComms направляется на поддержку 225-го ОШП и ветеранских инициатив (Украинский ветеранский фонд). Детали — на странице «О бренде».",
        },
        "en": {
            "q": "Where do the proceeds from {title} go?",
            "a": "Part of TwoComms' profit supports the 225th Independent Assault Regiment and veteran-focused initiatives (the Ukrainian Veteran Foundation). Details on the «About the brand» page.",
        },
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _category_phrase(language: str, category_name: str) -> str:
    cat = (category_name or "").lower().strip()
    table_uk = {
        "футболки": "футболка",
        "худі": "худі",
        "лонгсліви": "лонгслів",
        "tshirts": "футболка",
        "hoodie": "худі",
        "long-sleeve": "лонгслів",
    }
    table_ru = {
        "футболки": "футболка",
        "худі": "худи",
        "худи": "худи",
        "лонгсліви": "лонгслив",
        "лонгсливы": "лонгслив",
        "tshirts": "футболка",
        "hoodie": "худи",
        "long-sleeve": "лонгслив",
    }
    table_en = {
        "футболки": "t-shirt",
        "худі": "hoodie",
        "лонгсліви": "long sleeve",
        "tshirts": "t-shirt",
        "hoodie": "hoodie",
        "long-sleeve": "long sleeve",
    }
    table = {"uk": table_uk, "ru": table_ru, "en": table_en}.get(language, table_uk)
    return table.get(cat, cat or table[next(iter(table))])


def _color_phrase(language: str, colors: List[str]) -> str:
    if not colors:
        if language == "ru":
            return "базовая палитра TwoComms"
        if language == "en":
            return "the TwoComms base palette"
        return "базова палітра TwoComms"
    return ", ".join(colors[:5])


def _size_phrase(language: str, sizes: List[str]) -> str:
    if not sizes:
        return "S–XXL"
    return ", ".join(sizes[:8])


def _detect_topic(product) -> str:
    haystack = " ".join(
        filter(
            None,
            [
                (getattr(product, "slug", None) or "").lower(),
                (getattr(product, "title", None) or "").lower(),
                (getattr(getattr(product, "category", None), "name", "") or "").lower(),
            ],
        )
    )
    for key, tokens in _TOPIC_KEYWORDS:
        for tok in tokens:
            if tok in haystack:
                return key
    return "generic"


def _topic_phrase(language: str, topic: str, idx: int, *, title: str, slug: str) -> str:
    bucket = _TOPIC_NARRATIVES.get(topic) or _TOPIC_NARRATIVES["generic"]
    variants = bucket.get(language) or bucket["uk"]
    template = variants[idx % len(variants)]
    return template.format(title=title, slug=slug)


def _safe_attr(obj, attr, default=""):
    try:
        v = getattr(obj, attr, default)
        return v if v is not None else default
    except Exception:
        return default


def _collect_color_names(product) -> List[str]:
    try:
        from productcolors.models import ProductColorVariant
        from .color_filter import _translate_color_label
    except Exception:
        return []
    out: List[str] = []
    seen = set()
    try:
        variants = (
            ProductColorVariant.objects.filter(product=product)
            .select_related("color")
            .only("color__name")
        )
        for v in variants:
            name = getattr(getattr(v, "color", None), "name", "") or ""
            if not name:
                continue
            label = str(_translate_color_label(name))
            if label and label not in seen:
                seen.add(label)
                out.append(label)
    except Exception:
        pass
    return out


def _collect_sizes(product) -> List[str]:
    try:
        from .size_guides import resolve_product_sizes
        return list(resolve_product_sizes(product) or [])
    except Exception:
        return []


def _normalize_language(code: Optional[str]) -> str:
    if not code:
        code = get_language() or "uk"
    code = (code or "uk").lower().split("-")[0]
    if code not in {"uk", "ru", "en"}:
        return "uk"
    return code


def _hash_seed(slug: str, salt: str) -> int:
    """Deterministic 32-bit integer derived from slug + salt.

    Using SHA1 (truncated) over UTF-8 bytes guarantees stable picks
    across requests while keeping a flat distribution for variant
    rotation. Salt differentiates the picks per section so the same
    slug doesn't always land on variant 0.
    """
    digest = hashlib.sha1(f"{slug}|{salt}".encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big")


def _pick(variants: Sequence[str], slug: str, salt: str) -> str:
    if not variants:
        return ""
    idx = _hash_seed(slug, salt) % len(variants)
    return variants[idx]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_product_seo_block(
    product, language_code: Optional[str] = None
) -> Dict[str, Any]:
    """Build the per-product SEO content block.

    Returns a dict with keys::

        {
            "topic": str,
            "language": "uk" | "ru" | "en",
            "sections": [
                {
                    "id": "hero_intro",
                    "heading": str,
                    "paragraphs": [str, ...],
                    "speakable": bool,
                },
                ...
            ],
            "faq": [{"question": str, "answer": str}, ...],
        }
    """
    language = _normalize_language(language_code)
    topic = _detect_topic(product)

    title = _safe_attr(product, "title", "")
    slug = _safe_attr(product, "slug", "") or "product"
    category_name = _safe_attr(getattr(product, "category", None), "name", "")
    category_phrase = _category_phrase(language, category_name)
    material = _safe_attr(product, "material", "") or (
        "трьохнитка" if "худ" in category_name.lower() else "бавовна"
    )

    colors = _collect_color_names(product)
    sizes = _collect_sizes(product)
    color_phrase = _color_phrase(language, colors)
    size_phrase = _size_phrase(language, sizes)

    tokens = {
        "title": title,
        "slug": slug,
        "category_phrase": category_phrase,
        "color_phrase": color_phrase,
        "size_phrase": size_phrase,
        "material": material,
    }

    sections: List[Dict[str, Any]] = []

    # -------- Section 1: hero_intro --------
    topic_idx = _hash_seed(slug, "topic") % 100
    hero_topic_para = _topic_phrase(language, topic, topic_idx, title=title, slug=slug)
    hero_followup_pool = _SECTION_TEMPLATES["hero_followup"][language]
    hero_followup_para = _pick(hero_followup_pool, slug, "hero_followup").format(**tokens)
    # Shuffle order via hash so first 5-grams differ.
    if _hash_seed(slug, "hero_order") % 2 == 0:
        hero_paragraphs = [hero_topic_para, hero_followup_para]
    else:
        hero_paragraphs = [hero_followup_para, hero_topic_para]
    sections.append(
        {
            "id": "hero_intro",
            "heading": (
                f"Що це за {title}"
                if language == "uk"
                else (f"Что это за {title}" if language == "ru" else f"About this {title}")
            ),
            "paragraphs": hero_paragraphs,
            "speakable": True,
        }
    )

    # -------- Section 2: who_for --------
    who_pool = _SECTION_TEMPLATES["who_for"][language]
    sections.append(
        {
            "id": "who_for",
            "heading": (
                f"Кому підійде {title}"
                if language == "uk"
                else (f"Кому подойдёт {title}" if language == "ru" else f"Who {title} is for")
            ),
            "paragraphs": [_pick(who_pool, slug, "who_for").format(**tokens)],
            "speakable": False,
        }
    )

    # -------- Section 3: how_to_style --------
    style_pool = _SECTION_TEMPLATES["how_to_style"][language]
    sections.append(
        {
            "id": "how_to_style",
            "heading": (
                f"Як стилізувати {title}"
                if language == "uk"
                else (f"Как стилизовать {title}" if language == "ru" else f"How to style {title}")
            ),
            "paragraphs": [_pick(style_pool, slug, "how_to_style").format(**tokens)],
            "speakable": False,
        }
    )

    # -------- Section 4: care --------
    care_pool = _SECTION_TEMPLATES["care"][language]
    sections.append(
        {
            "id": "care",
            "heading": (
                f"Догляд за {title}"
                if language == "uk"
                else (f"Уход за {title}" if language == "ru" else f"Caring for {title}")
            ),
            "paragraphs": [_pick(care_pool, slug, "care").format(**tokens)],
            "speakable": False,
        }
    )

    # -------- Section 5: delivery --------
    delivery_pool = _SECTION_TEMPLATES["delivery"][language]
    sections.append(
        {
            "id": "delivery",
            "heading": (
                f"Доставка {title}"
                if language == "uk"
                else (f"Доставка {title}" if language == "ru" else f"Shipping {title}")
            ),
            "paragraphs": [_pick(delivery_pool, slug, "delivery").format(**tokens)],
            "speakable": False,
        }
    )

    # -------- Section 6: why_us --------
    why_pool = _SECTION_TEMPLATES["why_us"][language]
    sections.append(
        {
            "id": "why_us",
            "heading": (
                f"Чому варто купити {title} саме у TwoComms"
                if language == "uk"
                else (
                    f"Почему стоит купить {title} именно у TwoComms"
                    if language == "ru"
                    else f"Why buy {title} from TwoComms"
                )
            ),
            "paragraphs": [_pick(why_pool, slug, "why_us").format(**tokens)],
            "speakable": False,
        }
    )

    # -------- FAQ --------
    base_pool = _BASE_FAQ_POOL.get(language) or _BASE_FAQ_POOL["uk"]
    faq: List[Dict[str, str]] = []
    for slot_idx, slot in enumerate(base_pool):
        item_pool = slot[0]
        q_variants = item_pool["q"]
        a_variants = item_pool["a"]
        q = q_variants[_hash_seed(slug, f"faq_q_{slot_idx}") % len(q_variants)]
        a = a_variants[_hash_seed(slug, f"faq_a_{slot_idx}") % len(a_variants)]
        faq.append(
            {
                "question": q.format(**tokens),
                "answer": a.format(**tokens),
            }
        )
    # Topic-specific FAQ delta.
    delta = _TOPIC_FAQ_DELTAS.get(topic, {}).get(language)
    if delta:
        faq.append(
            {
                "question": delta["q"].format(**tokens),
                "answer": delta["a"].format(**tokens),
            }
        )

    return {
        "topic": topic,
        "language": language,
        "sections": sections,
        "faq": faq,
    }
