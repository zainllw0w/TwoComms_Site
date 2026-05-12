"""Phase 19g (2026-05-10) — colour-aware long-form SEO copy for catalog screens.

Covers three contexts (a single service so the catalog view has one
entry point):

1. ``/catalog/`` (no category, no colour) — brand-level catalogue
   landing copy with internal links to all three category pages +
   the most stocked colour filters.

2. ``/catalog/?color=<slug>`` (cross-category colour filter) — copy
   focused on the chosen colour with internal links into every
   category filtered by the same colour.

3. ``/catalog/<category>/?color=<slug>`` (category × colour) — copy
   focused on the category-colour intersection (e.g. *чорне худі*),
   with HF / MF / LF query chips and links to the alternative
   categories of the same colour.

Each block returns ``{h2, paragraphs, queries}`` where ``queries`` is
``[{label, url, freq: 'hf'|'mf'|'lf'}]``. The template renders the
paragraphs as ``<p>`` and the queries as a chip strip. Copy is
written by hand — no AI generation runtime — to guarantee that the
text is unique per (category, colour) cell and never collides with
the per-category description (Phase 10 / 10b).

The catalog view passes a ``color_seo_copy`` context variable; the
template (``partials/catalog_color_seo.html``) renders it inside the
existing ``catalog-category-description`` panel so the styling stays
consistent with per-category descriptions.

Phase 17i (2026-05-12) — full RU/EN translation. Every curated colour
palette is provided in three languages; the brand-level catalogue
copy and the generic colour fallback use ``gettext_lazy`` so the
strings show up in the standard ``django.po`` workflow. The view
selects the palette via :func:`django.utils.translation.get_language`
at request time, so the same code path serves UA / RU / EN visitors
correctly once we lift the Path A noindex on RU/EN renders.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from django.utils.translation import gettext_lazy as _
from django.utils.translation import get_language


# ---------------------------------------------------------------------------
# Curated palettes. Hand-written copy for the colours the catalogue
# stocks most: чорний, кайот, олива, сірий, білий. Other colours fall
# back to a templated paragraph that still carries category links and
# a sensible chip strip — never empty.
#
# Each curated colour is a ``{"uk": …, "ru": …, "en": …}`` triplet so
# the view can render the same long-form copy in the visitor's active
# language without losing the adjective inflection that proper Ukrainian
# / Russian grammar requires (худі — середній рід, футболка — жіночий,
# лонгслів — чоловічий). English uses a single uninflected adjective.
# ---------------------------------------------------------------------------


_BLACK = {
    "uk": {
        "name": "чорний",
        "adj_n": "чорне",        # худі
        "adj_f": "чорна",        # футболка
        "adj_m": "чорний",       # лонгслів
        "adj_pl": "чорні",       # принти
        "tone_paragraph": (
            "Чорний — найуніверсальніший колір у гардеробі вуличного стилю: "
            "він не сперечається з принтом, легко комбінується з джинсами, карго "
            "й мілітарі-аксесуарами, і однаково доречний у місті, на концерті чи "
            "у форматі smart-casual. У TwoComms ми друкуємо принти на щільному "
            "чорному поліci так, щоб композиція не «світилася» через тканину навіть "
            "після десятка прань — це різниця між дешевим мерчем і одягом, "
            "який служить роками."
        ),
        "queries_seed": [
            ("Купити чорне худі", "/catalog/hoodie/?color=black", "hf"),
            ("Чорна футболка з принтом", "/catalog/tshirts/?color=black", "hf"),
            ("Чорний лонгслів", "/catalog/long-sleeve/?color=black", "hf"),
            ("Чорне худі ЗСУ", "/catalog/hoodie/?color=black", "mf"),
            ("Чорна футболка унісекс", "/catalog/tshirts/?color=black", "mf"),
            ("Чорний український стрітвір", "/catalog/?color=black", "mf"),
            ("Чорне худі з тризубом купити Київ", "/catalog/hoodie/?color=black", "lf"),
            ("Чорна футболка з патріотичним принтом", "/catalog/tshirts/?color=black", "lf"),
            ("Чорний лонгслів мілітарі стиль", "/catalog/long-sleeve/?color=black", "lf"),
            ("Чорний одяг донат ЗСУ", "/catalog/?color=black", "lf"),
        ],
    },
    "ru": {
        "name": "чёрный",
        "adj_n": "чёрное",
        "adj_f": "чёрная",
        "adj_m": "чёрный",
        "adj_pl": "чёрные",
        "tone_paragraph": (
            "Чёрный — самый универсальный цвет в гардеробе уличного стиля: "
            "он не спорит с принтом, легко комбинируется с джинсами, карго "
            "и милитари-аксессуарами, и одинаково уместен в городе, на концерте "
            "или в формате smart-casual. В TwoComms мы печатаем принты на "
            "плотном чёрном полотне так, чтобы композиция не «светилась» сквозь "
            "ткань даже после десятка стирок — это разница между дешёвым мерчем "
            "и одеждой, которая служит годами."
        ),
        "queries_seed": [
            ("Купить чёрное худи", "/catalog/hoodie/?color=black", "hf"),
            ("Чёрная футболка с принтом", "/catalog/tshirts/?color=black", "hf"),
            ("Чёрный лонгслив", "/catalog/long-sleeve/?color=black", "hf"),
            ("Чёрное худи ВСУ", "/catalog/hoodie/?color=black", "mf"),
            ("Чёрная футболка унисекс", "/catalog/tshirts/?color=black", "mf"),
            ("Чёрный украинский стритвир", "/catalog/?color=black", "mf"),
            ("Чёрное худи с тризубом купить Киев", "/catalog/hoodie/?color=black", "lf"),
            ("Чёрная футболка с патриотическим принтом", "/catalog/tshirts/?color=black", "lf"),
            ("Чёрный лонгслив милитари стиль", "/catalog/long-sleeve/?color=black", "lf"),
            ("Чёрная одежда донат ВСУ", "/catalog/?color=black", "lf"),
        ],
    },
    "en": {
        "name": "black",
        "adj_n": "black",
        "adj_f": "black",
        "adj_m": "black",
        "adj_pl": "black",
        "tone_paragraph": (
            "Black is the most versatile colour in a streetwear wardrobe: it "
            "never argues with the print, pairs effortlessly with jeans, cargo "
            "trousers and tactical accessories, and looks just as right in the "
            "city, at a concert or in a smart-casual outfit. At TwoComms we "
            "print on a dense black knit so the artwork doesn't shine through "
            "the fabric even after ten washes — the difference between cheap "
            "merch and clothing that lasts for years."
        ),
        "queries_seed": [
            ("Buy black hoodie", "/catalog/hoodie/?color=black", "hf"),
            ("Black T-shirt with print", "/catalog/tshirts/?color=black", "hf"),
            ("Black long sleeve", "/catalog/long-sleeve/?color=black", "hf"),
            ("Black hoodie AFU support", "/catalog/hoodie/?color=black", "mf"),
            ("Black T-shirt unisex", "/catalog/tshirts/?color=black", "mf"),
            ("Black Ukrainian streetwear", "/catalog/?color=black", "mf"),
            ("Black hoodie with trident Kyiv", "/catalog/hoodie/?color=black", "lf"),
            ("Black T-shirt with patriotic print", "/catalog/tshirts/?color=black", "lf"),
            ("Black long sleeve military style", "/catalog/long-sleeve/?color=black", "lf"),
            ("Black clothing donate AFU", "/catalog/?color=black", "lf"),
        ],
    },
}

_COYOTE = {
    "uk": {
        "name": "кайот",
        "adj_n": "кайотове",
        "adj_f": "кайотова",
        "adj_m": "кайотовий",
        "adj_pl": "кайотові",
        "tone_paragraph": (
            "Кайот — мілітарний відтінок, який поєднує тепло пісочного та "
            "стриманість оливи. Це саме той колір, що носять військові, "
            "інженери та люди, які цінують дискретність у вуличному вбранні. "
            "TwoComms друкує принти на кайоті з підвищеним контрастом, щоб "
            "графіка читалася навіть у похмуру погоду, а самі тканини добираємо "
            "щільніші: вони витримують щоденні навантаження, не «дають усадки» "
            "після першого прання й залишаються в кольорі без вицвітання."
        ),
        "queries_seed": [
            ("Купити кайотове худі", "/catalog/hoodie/?color=coyote", "hf"),
            ("Кайотова футболка ЗСУ", "/catalog/tshirts/?color=coyote", "hf"),
            ("Кайотовий лонгслів", "/catalog/long-sleeve/?color=coyote", "hf"),
            ("Худі мілітарі кайот", "/catalog/hoodie/?color=coyote", "mf"),
            ("Футболка кайот унісекс", "/catalog/tshirts/?color=coyote", "mf"),
            ("Кайотовий одяг донат", "/catalog/?color=coyote", "mf"),
            ("Кайотове худі з тризубом купити Харків", "/catalog/hoodie/?color=coyote", "lf"),
            ("Кайотова футболка з патріотичним принтом ЗСУ", "/catalog/tshirts/?color=coyote", "lf"),
            ("Подарунок захиснику кайот мерч", "/catalog/?color=coyote", "lf"),
        ],
    },
    "ru": {
        "name": "койот",
        "adj_n": "койотовое",
        "adj_f": "койотовая",
        "adj_m": "койотовый",
        "adj_pl": "койотовые",
        "tone_paragraph": (
            "Койот — милитарный оттенок, который сочетает тепло песочного и "
            "сдержанность оливы. Это именно тот цвет, который носят военные, "
            "инженеры и люди, ценящие дискретность в уличном гардеробе. "
            "TwoComms печатает принты на койоте с повышенным контрастом, чтобы "
            "графика читалась даже в пасмурную погоду, а сами ткани подбираем "
            "плотнее: они выдерживают ежедневные нагрузки, не «садятся» после "
            "первой стирки и остаются в цвете без выцветания."
        ),
        "queries_seed": [
            ("Купить койотовое худи", "/catalog/hoodie/?color=coyote", "hf"),
            ("Койотовая футболка ВСУ", "/catalog/tshirts/?color=coyote", "hf"),
            ("Койотовый лонгслив", "/catalog/long-sleeve/?color=coyote", "hf"),
            ("Худи милитари койот", "/catalog/hoodie/?color=coyote", "mf"),
            ("Футболка койот унисекс", "/catalog/tshirts/?color=coyote", "mf"),
            ("Койотовая одежда донат", "/catalog/?color=coyote", "mf"),
            ("Койотовое худи с тризубом купить Харьков", "/catalog/hoodie/?color=coyote", "lf"),
            ("Койотовая футболка с патриотическим принтом ВСУ", "/catalog/tshirts/?color=coyote", "lf"),
            ("Подарок защитнику койот мерч", "/catalog/?color=coyote", "lf"),
        ],
    },
    "en": {
        "name": "coyote",
        "adj_n": "coyote",
        "adj_f": "coyote",
        "adj_m": "coyote",
        "adj_pl": "coyote",
        "tone_paragraph": (
            "Coyote is a tactical shade that blends the warmth of sand with "
            "the restraint of olive. It's the colour worn by service members, "
            "engineers and anyone who values understated streetwear. TwoComms "
            "prints on coyote with extra contrast so the artwork reads even on "
            "an overcast day, and we pick heavier fabrics here: they take "
            "everyday wear, don't shrink after the first wash and hold their "
            "colour without fading."
        ),
        "queries_seed": [
            ("Buy coyote hoodie", "/catalog/hoodie/?color=coyote", "hf"),
            ("Coyote T-shirt AFU support", "/catalog/tshirts/?color=coyote", "hf"),
            ("Coyote long sleeve", "/catalog/long-sleeve/?color=coyote", "hf"),
            ("Military coyote hoodie", "/catalog/hoodie/?color=coyote", "mf"),
            ("Coyote T-shirt unisex", "/catalog/tshirts/?color=coyote", "mf"),
            ("Coyote streetwear AFU donation", "/catalog/?color=coyote", "mf"),
            ("Coyote hoodie with trident Kharkiv", "/catalog/hoodie/?color=coyote", "lf"),
            ("Coyote T-shirt patriotic AFU print", "/catalog/tshirts/?color=coyote", "lf"),
            ("Gift for soldier coyote merch", "/catalog/?color=coyote", "lf"),
        ],
    },
}

_OLIVE = {
    "uk": {
        "name": "олива",
        "adj_n": "оливкове",
        "adj_f": "оливкова",
        "adj_m": "оливковий",
        "adj_pl": "оливкові",
        "tone_paragraph": (
            "Оливковий — класичний мілітарний колір, який стає основою для "
            "патріотичного стрітверу і чудово грає з графікою у білих, "
            "кайотових і червоних акцентах. Олива не вицвітає на сонці так "
            "швидко, як темно-зелені фарби, тому одяг у цьому кольорі довго "
            "тримає товарний вигляд. Усі моделі TwoComms у оливі — це "
            "100% бавовна або щільні поліcі без синтетичного блиску."
        ),
        "queries_seed": [
            ("Купити оливкове худі", "/catalog/hoodie/?color=olive", "hf"),
            ("Оливкова футболка з принтом", "/catalog/tshirts/?color=olive", "hf"),
            ("Оливковий лонгслів", "/catalog/long-sleeve/?color=olive", "hf"),
            ("Худі олива ЗСУ", "/catalog/hoodie/?color=olive", "mf"),
            ("Оливкова футболка унісекс", "/catalog/tshirts/?color=olive", "mf"),
            ("Олива одяг український бренд", "/catalog/?color=olive", "mf"),
            ("Оливкове худі мілітарі стиль", "/catalog/hoodie/?color=olive", "lf"),
            ("Оливкова футболка з тризубом", "/catalog/tshirts/?color=olive", "lf"),
            ("Оливковий лонгслів streetwear купити", "/catalog/long-sleeve/?color=olive", "lf"),
        ],
    },
    "ru": {
        "name": "олива",
        "adj_n": "оливковое",
        "adj_f": "оливковая",
        "adj_m": "оливковый",
        "adj_pl": "оливковые",
        "tone_paragraph": (
            "Оливковый — классический милитарный цвет, который становится "
            "основой для патриотического стритвира и отлично играет с графикой "
            "в белых, койотовых и красных акцентах. Олива не выцветает на солнце "
            "так быстро, как тёмно-зелёные краски, поэтому одежда в этом цвете "
            "долго сохраняет товарный вид. Все модели TwoComms в оливе — это "
            "100% хлопок или плотные полотна без синтетического блеска."
        ),
        "queries_seed": [
            ("Купить оливковое худи", "/catalog/hoodie/?color=olive", "hf"),
            ("Оливковая футболка с принтом", "/catalog/tshirts/?color=olive", "hf"),
            ("Оливковый лонгслив", "/catalog/long-sleeve/?color=olive", "hf"),
            ("Худи олива ВСУ", "/catalog/hoodie/?color=olive", "mf"),
            ("Оливковая футболка унисекс", "/catalog/tshirts/?color=olive", "mf"),
            ("Олива одежда украинский бренд", "/catalog/?color=olive", "mf"),
            ("Оливковое худи милитари стиль", "/catalog/hoodie/?color=olive", "lf"),
            ("Оливковая футболка с тризубом", "/catalog/tshirts/?color=olive", "lf"),
            ("Оливковый лонгслив streetwear купить", "/catalog/long-sleeve/?color=olive", "lf"),
        ],
    },
    "en": {
        "name": "olive",
        "adj_n": "olive",
        "adj_f": "olive",
        "adj_m": "olive",
        "adj_pl": "olive",
        "tone_paragraph": (
            "Olive is the classic military colour that anchors patriotic "
            "streetwear and pairs beautifully with white, coyote and red "
            "accents. Olive doesn't fade in the sun as fast as dark-green "
            "pigments, so the garment keeps its retail look for longer. "
            "Every TwoComms olive piece is 100% cotton or a heavy knit with "
            "no synthetic shine."
        ),
        "queries_seed": [
            ("Buy olive hoodie", "/catalog/hoodie/?color=olive", "hf"),
            ("Olive T-shirt with print", "/catalog/tshirts/?color=olive", "hf"),
            ("Olive long sleeve", "/catalog/long-sleeve/?color=olive", "hf"),
            ("Olive AFU hoodie", "/catalog/hoodie/?color=olive", "mf"),
            ("Olive T-shirt unisex", "/catalog/tshirts/?color=olive", "mf"),
            ("Olive Ukrainian brand clothing", "/catalog/?color=olive", "mf"),
            ("Olive hoodie military style", "/catalog/hoodie/?color=olive", "lf"),
            ("Olive T-shirt with trident", "/catalog/tshirts/?color=olive", "lf"),
            ("Buy olive long sleeve streetwear", "/catalog/long-sleeve/?color=olive", "lf"),
        ],
    },
}

_GREY = {
    "uk": {
        "name": "сірий",
        "adj_n": "сіре",
        "adj_f": "сіра",
        "adj_m": "сірий",
        "adj_pl": "сірі",
        "tone_paragraph": (
            "Сірий — нейтральна база, яка робить будь-який принт "
            "виразнішим і не втомлює око. Його легко «зчитувати» з джинсами, "
            "хакі-штанами або чорними карго, тому сірі худі й футболки "
            "TwoComms лідирують у замовленнях у міжсезоння. Ми тримаємо два "
            "відтінки — світлий меланж і темний графіт — щоб клієнт міг "
            "обрати посадку під свій тон шкіри й освітлення."
        ),
        "queries_seed": [
            ("Купити сіре худі", "/catalog/hoodie/?color=grey", "hf"),
            ("Сіра футболка з принтом", "/catalog/tshirts/?color=grey", "hf"),
            ("Сірий лонгслів", "/catalog/long-sleeve/?color=grey", "hf"),
            ("Худі сірий меланж", "/catalog/hoodie/?color=grey", "mf"),
            ("Футболка сіра унісекс", "/catalog/tshirts/?color=grey", "mf"),
            ("Сірий стрітвір TwoComms", "/catalog/?color=grey", "mf"),
            ("Сіре худі з тризубом купити Україна", "/catalog/hoodie/?color=grey", "lf"),
            ("Сіра футболка ЗСУ донат", "/catalog/tshirts/?color=grey", "lf"),
            ("Сірий лонгслів патріотичний принт", "/catalog/long-sleeve/?color=grey", "lf"),
        ],
    },
    "ru": {
        "name": "серый",
        "adj_n": "серое",
        "adj_f": "серая",
        "adj_m": "серый",
        "adj_pl": "серые",
        "tone_paragraph": (
            "Серый — нейтральная база, которая делает любой принт выразительнее "
            "и не утомляет глаз. Его легко «считывать» с джинсами, штанами хаки "
            "или чёрными карго, поэтому серые худи и футболки TwoComms лидируют "
            "в заказах в межсезонье. Мы держим два оттенка — светлый меланж и "
            "тёмный графит — чтобы клиент мог подобрать посадку под свой тон "
            "кожи и освещение."
        ),
        "queries_seed": [
            ("Купить серое худи", "/catalog/hoodie/?color=grey", "hf"),
            ("Серая футболка с принтом", "/catalog/tshirts/?color=grey", "hf"),
            ("Серый лонгслив", "/catalog/long-sleeve/?color=grey", "hf"),
            ("Худи серый меланж", "/catalog/hoodie/?color=grey", "mf"),
            ("Футболка серая унисекс", "/catalog/tshirts/?color=grey", "mf"),
            ("Серый стритвир TwoComms", "/catalog/?color=grey", "mf"),
            ("Серое худи с тризубом купить Украина", "/catalog/hoodie/?color=grey", "lf"),
            ("Серая футболка ВСУ донат", "/catalog/tshirts/?color=grey", "lf"),
            ("Серый лонгслив патриотический принт", "/catalog/long-sleeve/?color=grey", "lf"),
        ],
    },
    "en": {
        "name": "grey",
        "adj_n": "grey",
        "adj_f": "grey",
        "adj_m": "grey",
        "adj_pl": "grey",
        "tone_paragraph": (
            "Grey is the neutral base that makes any print look sharper without "
            "tiring the eye. It reads easily with jeans, khaki trousers or "
            "black cargo, which is why grey TwoComms hoodies and tees top "
            "off-season orders. We stock two shades — a light heather and a "
            "dark graphite — so customers can pick the fit that suits their "
            "skin tone and lighting."
        ),
        "queries_seed": [
            ("Buy grey hoodie", "/catalog/hoodie/?color=grey", "hf"),
            ("Grey T-shirt with print", "/catalog/tshirts/?color=grey", "hf"),
            ("Grey long sleeve", "/catalog/long-sleeve/?color=grey", "hf"),
            ("Grey heather hoodie", "/catalog/hoodie/?color=grey", "mf"),
            ("Grey T-shirt unisex", "/catalog/tshirts/?color=grey", "mf"),
            ("Grey streetwear TwoComms", "/catalog/?color=grey", "mf"),
            ("Grey hoodie with trident Ukraine", "/catalog/hoodie/?color=grey", "lf"),
            ("Grey T-shirt AFU donation", "/catalog/tshirts/?color=grey", "lf"),
            ("Grey long sleeve patriotic print", "/catalog/long-sleeve/?color=grey", "lf"),
        ],
    },
}

_WHITE = {
    "uk": {
        "name": "білий",
        "adj_n": "біле",
        "adj_f": "біла",
        "adj_m": "білий",
        "adj_pl": "білі",
        "tone_paragraph": (
            "Білий — колір, що не пробачає компромісів у якості друку: "
            "слабка фарба «втрачається», а пухкий сітч-друк дає матовий "
            "відбиток, який швидко вицвітає. TwoComms друкує на білому "
            "технологією DTF з повним нанесенням базового шару, тому "
            "ілюстрації виглядають насиченими навіть на фото у "
            "природному світлі. Білий ідеальний для фотоконтенту в "
            "Instagram і для весняно-літнього вуличного стилю."
        ),
        "queries_seed": [
            ("Купити білу футболку з принтом", "/catalog/tshirts/?color=white", "hf"),
            ("Біле худі", "/catalog/hoodie/?color=white", "hf"),
            ("Білий лонгслів", "/catalog/long-sleeve/?color=white", "hf"),
            ("Біла футболка ЗСУ", "/catalog/tshirts/?color=white", "mf"),
            ("Худі біле жіноче", "/catalog/hoodie/?color=white", "mf"),
            ("Білий одяг український бренд", "/catalog/?color=white", "mf"),
            ("Біла футболка з тризубом купити Львів", "/catalog/tshirts/?color=white", "lf"),
            ("Біле худі з патріотичним принтом", "/catalog/hoodie/?color=white", "lf"),
            ("Білий лонгслів streetwear купити", "/catalog/long-sleeve/?color=white", "lf"),
        ],
    },
    "ru": {
        "name": "белый",
        "adj_n": "белое",
        "adj_f": "белая",
        "adj_m": "белый",
        "adj_pl": "белые",
        "tone_paragraph": (
            "Белый — цвет, который не прощает компромиссов в качестве печати: "
            "слабая краска «теряется», а рыхлая ситчатая печать даёт матовый "
            "отпечаток, который быстро выцветает. TwoComms печатает на белом "
            "по технологии DTF с полным нанесением базового слоя, поэтому "
            "иллюстрации выглядят насыщенными даже на фото в естественном "
            "освещении. Белый идеален для фотоконтента в Instagram и для "
            "весенне-летнего уличного стиля."
        ),
        "queries_seed": [
            ("Купить белую футболку с принтом", "/catalog/tshirts/?color=white", "hf"),
            ("Белое худи", "/catalog/hoodie/?color=white", "hf"),
            ("Белый лонгслив", "/catalog/long-sleeve/?color=white", "hf"),
            ("Белая футболка ВСУ", "/catalog/tshirts/?color=white", "mf"),
            ("Худи белое женское", "/catalog/hoodie/?color=white", "mf"),
            ("Белая одежда украинский бренд", "/catalog/?color=white", "mf"),
            ("Белая футболка с тризубом купить Львов", "/catalog/tshirts/?color=white", "lf"),
            ("Белое худи с патриотическим принтом", "/catalog/hoodie/?color=white", "lf"),
            ("Белый лонгслив streetwear купить", "/catalog/long-sleeve/?color=white", "lf"),
        ],
    },
    "en": {
        "name": "white",
        "adj_n": "white",
        "adj_f": "white",
        "adj_m": "white",
        "adj_pl": "white",
        "tone_paragraph": (
            "White is the colour that doesn't forgive compromises in print "
            "quality: weak ink disappears, and a loose mesh print leaves a "
            "matte mark that fades fast. TwoComms prints on white with the "
            "DTF process and a full base layer so the artwork stays saturated "
            "even in natural-light photos. White is ideal for Instagram "
            "content and spring/summer streetwear looks."
        ),
        "queries_seed": [
            ("Buy white T-shirt with print", "/catalog/tshirts/?color=white", "hf"),
            ("White hoodie", "/catalog/hoodie/?color=white", "hf"),
            ("White long sleeve", "/catalog/long-sleeve/?color=white", "hf"),
            ("White T-shirt AFU support", "/catalog/tshirts/?color=white", "mf"),
            ("Women's white hoodie", "/catalog/hoodie/?color=white", "mf"),
            ("White clothing Ukrainian brand", "/catalog/?color=white", "mf"),
            ("White T-shirt with trident Lviv", "/catalog/tshirts/?color=white", "lf"),
            ("White hoodie patriotic print", "/catalog/hoodie/?color=white", "lf"),
            ("Buy white long sleeve streetwear", "/catalog/long-sleeve/?color=white", "lf"),
        ],
    },
}


_CURATED: Dict[str, Dict[str, Dict[str, Any]]] = {
    "black": _BLACK,
    "coyote": _COYOTE,
    "olive": _OLIVE,
    "grey": _GREY,
    "gray": _GREY,
    "white": _WHITE,
}


def _active_lang() -> str:
    """Resolve active language code (``uk``/``ru``/``en``).

    Falls back to ``uk`` for any unknown / sub-tagged code (e.g. ``ru-UA``)
    so the rest of the module never has to guess the bucket.
    """
    code = (get_language() or "uk").split("-")[0].lower()
    if code not in ("uk", "ru", "en"):
        return "uk"
    return code


def _palette(color_slug: str) -> Optional[Dict[str, Any]]:
    """Return the curated palette dict for *color_slug* in the active language.

    Returns ``None`` when the colour is not in the curated set (caller
    falls back to :func:`_generic_color_copy`).
    """
    bundle = _CURATED.get((color_slug or "").lower())
    if bundle is None:
        return None
    lang = _active_lang()
    return bundle.get(lang) or bundle["uk"]


# ---------------------------------------------------------------------------
# Generic colour fallback. Used when the colour slug isn't curated above
# (e.g. "navy" or any unique shade). Pulls the human-readable colour
# name from the chip data passed in by the view so we don't print the
# slug to end users.
# ---------------------------------------------------------------------------

def _generic_color_copy(color_slug: str, color_label: str) -> Dict[str, Any]:
    label = (color_label or color_slug or _("вибраний")).strip()
    label_lower = label.lower()
    tone_paragraph = _(
        "Колір «%(label)s» у каталозі TwoComms — це вибір для тих, "
        "хто хоче відійти від базової палітри, але не готовий поступатися "
        "якістю принту. Ми друкуємо на цьому відтінку DTF-технологією з "
        "підвищеним базовим шаром, тому ілюстрація не «провалюється» у тон "
        "тканини й залишається насиченою після десятків прань."
    ) % {"label": label}
    seed: List[tuple[Any, str, str]] = [
        (
            _("Купити %(color)s худі") % {"color": label_lower},
            f"/catalog/hoodie/?color={color_slug}", "hf",
        ),
        (
            _("%(color)s футболка з принтом") % {"color": label.capitalize()},
            f"/catalog/tshirts/?color={color_slug}", "hf",
        ),
        (
            _("%(color)s лонгслів") % {"color": label.capitalize()},
            f"/catalog/long-sleeve/?color={color_slug}", "hf",
        ),
        (
            _("%(color)s стрітвір TwoComms") % {"color": label.capitalize()},
            f"/catalog/?color={color_slug}", "mf",
        ),
        (
            _("%(color)s одяг ЗСУ донат") % {"color": label.capitalize()},
            f"/catalog/?color={color_slug}", "mf",
        ),
        (
            _("%(color)s футболка з тризубом купити Україна") % {"color": label.capitalize()},
            f"/catalog/tshirts/?color={color_slug}", "lf",
        ),
        (
            _("%(color)s худі з патріотичним принтом") % {"color": label.capitalize()},
            f"/catalog/hoodie/?color={color_slug}", "lf",
        ),
    ]
    return {
        "name": label_lower,
        "adj_n": label_lower,
        "adj_f": label_lower,
        "adj_m": label_lower,
        "adj_pl": label_lower,
        "tone_paragraph": tone_paragraph,
        "queries_seed": seed,
    }


# ---------------------------------------------------------------------------
# General catalog (no category, no colour). Brand-level landing copy.
# ---------------------------------------------------------------------------

GENERAL_CATALOG_SEO_COPY: Dict[str, Any] = {
    "h2": _("Каталог одягу TwoComms — український стрітвір з характером"),
    "paragraphs": [
        _(
            "TwoComms — це український бренд одягу, який створює стрітвір "
            "у трьох ключових категоріях: <a href=\"/catalog/hoodie/\">худі</a>, "
            "<a href=\"/catalog/tshirts/\">футболки</a> й "
            "<a href=\"/catalog/long-sleeve/\">лонгсліви</a>. Усі моделі ми "
            "розробляємо в Україні, друкуємо принти на власному обладнанні "
            "за технологією DTF і підбираємо тканини так, щоб одяг витримував "
            "щоденне носіння, прання й любий клімат — від літньої спеки до "
            "сирої осені."
        ),

        _(
            "Кожен товар у каталозі доступний у кількох кольорах: класичний "
            "<a href=\"/catalog/?color=black\">чорний</a> для тих, хто шукає "
            "універсальну базу під будь-який принт; "
            "<a href=\"/catalog/?color=coyote\">кайот</a> і "
            "<a href=\"/catalog/?color=olive\">олива</a> для прихильників "
            "мілітарної естетики; нейтральний "
            "<a href=\"/catalog/?color=grey\">сірий</a> і чистий "
            "<a href=\"/catalog/?color=white\">білий</a> для весняно-літніх "
            "образів. Усі кольори перевіряються на стійкість до УФ та "
            "перфектне зберігання форми навіть після 30+ циклів прання."
        ),

        _(
            "Більшість принтів TwoComms — це авторські ілюстрації на тему "
            "патріотизму, ЗСУ, української історії та сучасної поп-культури. "
            "Ми передаємо частину прибутку на підтримку Збройних Сил України, "
            "тому кожна покупка — це одночасно вибір якісного одягу й вклад у "
            "перемогу. На сторінці кожного товару ви знайдете розмірну сітку, "
            "детальні фото матеріалу, відгуки клієнтів і прозору інформацію "
            "про склад тканини."
        ),

        _(
            "Якщо ви не знайшли потрібну графіку — спробуйте розділ "
            "<a href=\"/custom-print/\">«Власний принт»</a>: ми надрукуємо "
            "будь-яку ілюстрацію на обраній моделі від однієї одиниці. "
            "Доставка по Україні — Новою Поштою на відділення або в "
            "поштомат за 1–2 дні. Оплата — карткою через Monobank/LiqPay "
            "або накладеним платежем. Усі товари мають 14 днів на повернення, "
            "якщо не підійшов розмір."
        ),
    ],
    "queries": [
        # HF
        {"label": _("Купити худі"), "url": "/catalog/hoodie/", "freq": "hf"},
        {"label": _("Купити футболку з принтом"), "url": "/catalog/tshirts/", "freq": "hf"},
        {"label": _("Купити лонгслів"), "url": "/catalog/long-sleeve/", "freq": "hf"},
        {"label": _("Український стрітвір"), "url": "/catalog/", "freq": "hf"},
        # MF
        {"label": _("Худі ЗСУ"), "url": "/catalog/hoodie/?color=coyote", "freq": "mf"},
        {"label": _("Чорна футболка з тризубом"), "url": "/catalog/tshirts/?color=black", "freq": "mf"},
        {"label": _("Кайотовий лонгслів"), "url": "/catalog/long-sleeve/?color=coyote", "freq": "mf"},
        {"label": _("Оливкове худі мілітарі"), "url": "/catalog/hoodie/?color=olive", "freq": "mf"},
        # LF
        {"label": _("Подарунок захиснику український бренд"),
         "url": "/catalog/?color=coyote", "freq": "lf"},
        {"label": _("Худі з патріотичним принтом купити Київ"),
         "url": "/catalog/hoodie/?color=black", "freq": "lf"},
        {"label": _("Футболка ЗСУ донат на ЗСУ Україна"),
         "url": "/catalog/tshirts/?color=coyote", "freq": "lf"},
        {"label": _("Власний принт на одязі від 1 одиниці"),
         "url": "/custom-print/", "freq": "lf"},
    ],
}


# ---------------------------------------------------------------------------
# Builder.
# ---------------------------------------------------------------------------

_CATEGORY_LABELS: Dict[str, Dict[str, str]] = {
    # match by lowercase slug substring → human-readable category noun
    # per language. Adding a slug here makes the matching deterministic
    # regardless of which slug spelling the admin saved.
    "hoodie":     {"uk": "худі",     "ru": "худи",     "en": "hoodies"},
    "hudi":       {"uk": "худі",     "ru": "худи",     "en": "hoodies"},
    "khudi":      {"uk": "худі",     "ru": "худи",     "en": "hoodies"},
    "tshirt":     {"uk": "футболки", "ru": "футболки", "en": "T-shirts"},
    "tshirts":    {"uk": "футболки", "ru": "футболки", "en": "T-shirts"},
    "futbolki":   {"uk": "футболки", "ru": "футболки", "en": "T-shirts"},
    "futbolky":   {"uk": "футболки", "ru": "футболки", "en": "T-shirts"},
    "long":       {"uk": "лонгсліви","ru": "лонгсливы","en": "long sleeves"},
    "longsleeve": {"uk": "лонгсліви","ru": "лонгсливы","en": "long sleeves"},
    "longslivy":  {"uk": "лонгсліви","ru": "лонгсливы","en": "long sleeves"},
    "longslivi":  {"uk": "лонгсліви","ru": "лонгсливы","en": "long sleeves"},
}


def _category_label(category) -> str:
    lang = _active_lang()
    fallback = {"uk": "одяг", "ru": "одежда", "en": "clothing"}[lang]
    if category is None:
        return fallback
    slug = (getattr(category, "slug", "") or "").lower()
    for token, labels in _CATEGORY_LABELS.items():
        if token in slug:
            return labels.get(lang) or labels["uk"]
    # If the admin used a custom slug we don't recognise, fall back to
    # the category's own name (already locale-aware via modeltranslation).
    return (getattr(category, "name", "") or fallback).lower()


def _build_color_paragraphs(color_data: Dict[str, Any], category) -> List[Any]:
    """Compose the two follow-up paragraphs after the tone paragraph.

    Returns a list of strings / lazy-translation proxies — the template
    renders them as ``<p>``. We keep ``_("...")`` wrappers so the
    msgid lands in ``django.po`` for translation; the ``%`` formatting
    happens lazily at render time.
    """

    cat_label = _category_label(category)
    color_adj_n = color_data["adj_n"]
    color_adj_n_cap = color_adj_n[:1].upper() + color_adj_n[1:]
    color_name = color_data["name"]
    color_slug = color_data.get("slug", "") or ""

    paragraphs: List[Any] = [color_data["tone_paragraph"]]

    if category is None:
        # Cross-category landing copy.
        paragraphs.append(_(
            "У каталозі TwoComms ви знайдете %(adj_n)s "
            "<a href=\"/catalog/hoodie/?color=%(slug)s\">худі</a>, "
            "<a href=\"/catalog/tshirts/?color=%(slug)s\">футболки</a> "
            "та <a href=\"/catalog/long-sleeve/?color=%(slug)s\">"
            "лонгсліви</a> з авторськими принтами. Усі моделі шиємо в "
            "Україні з натуральних тканин, друкуємо DTF-технологією й "
            "перевіряємо на стійкість кольору до прання. %(adj_n_cap)s "
            "одяг легко комбінувати з джинсами, карго-штанами та "
            "мілітарними аксесуарами."
        ) % {
            "adj_n": color_adj_n,
            "adj_n_cap": color_adj_n_cap,
            "slug": color_slug,
        })
        paragraphs.append(_(
            "Якщо вас цікавить конкретний принт у %(name)s — "
            "скористайтесь сторінкою <a href=\"/custom-print/\">«Власний "
            "принт»</a>: ми надрукуємо будь-яку ілюстрацію на обраній "
            "моделі від однієї одиниці. Доставка Новою Поштою по всій "
            "Україні — 1–2 дні; оплата карткою або накладеним платежем; "
            "повернення впродовж 14 днів, якщо не підійшов розмір."
        ) % {"name": color_name})
    else:
        # Category × colour landing copy.
        paragraphs.append(_(
            "У категорії «%(cat)s» %(adj_n)s TwoComms — це "
            "поєднання якісної тканини, насиченого друку й продуманої "
            "посадки. Ми використовуємо щільні полотна, так що принт "
            "не просвічується, а сам одяг тримає форму після десятків "
            "прань. Звертайте увагу на розмірну сітку — %(cat)s у "
            "TwoComms ідуть у двох посадках: класична та оверсайз."
        ) % {"cat": cat_label, "adj_n": color_adj_n})
        paragraphs.append(_(
            "Подивіться також %(adj_n)s <a href=\"/catalog/?color="
            "%(slug)s\">в інших категоріях</a> або "
            "оберіть інший відтінок цієї ж категорії — "
            "<a href=\"/catalog/%(cat_slug)s/\">%(cat)s TwoComms</a>. "
            "Якщо потрібен конкретний принт — "
            "скористайтесь сторінкою <a href=\"/custom-print/\">"
            "«Власний принт»</a>: ми надрукуємо вашу ілюстрацію на "
            "обраній моделі від однієї одиниці."
        ) % {
            "adj_n": color_adj_n,
            "slug": color_slug,
            "cat_slug": getattr(category, "slug", "") or "",
            "cat": cat_label,
        })

    return paragraphs


def _build_queries_from_seed(color_data: Dict[str, Any]) -> List[Dict[str, str]]:
    return [
        {"label": str(label), "url": url, "freq": freq}
        for (label, url, freq) in color_data.get("queries_seed", [])
    ]


def _load_override(scope: str, color_slug: str, category) -> Optional[Dict[str, Any]]:
    """Phase 19h: try to load an admin-managed override row.

    Returns the curated payload merged with override fields (only the
    non-empty fields override the defaults), or ``None`` when no
    override exists / DB is not yet migrated.
    """
    try:  # late import — avoids circular import with models.
        from ..models import CatalogColorSeoOverride
    except Exception:
        return None
    try:
        qs = CatalogColorSeoOverride.objects.filter(
            scope=scope,
            color_slug=(color_slug or "").lower(),
            is_active=True,
        )
        if category is None:
            qs = qs.filter(category__isnull=True)
        else:
            qs = qs.filter(category=category)
        row = qs.first()
    except Exception:
        # Migration not applied yet, or DB error — silently bypass so
        # the curated palette still renders.
        return None
    if row is None:
        return None
    return {
        "h2": (row.h2 or "").strip(),
        "body_html": (row.body_html or "").strip(),
        "queries_json": list(row.queries_json or []),
    }


def _split_html_paragraphs(body_html: str) -> List[str]:
    """Split admin-entered ``<p>...</p>`` HTML into paragraph strings."""
    import re as _re
    if not body_html:
        return []
    chunks = _re.findall(r"<p[^>]*>(.*?)</p>", body_html, flags=_re.S | _re.I)
    if chunks:
        return [c.strip() for c in chunks if c.strip()]
    # No <p> tags — treat the entire blob as a single paragraph.
    return [body_html.strip()]


def build_catalog_color_seo(
    *,
    category: Optional[Any],
    selected_color_slugs: Optional[List[str]],
    available_colors: Optional[List[Dict[str, Any]]] = None,
) -> Optional[Dict[str, Any]]:
    """Return ``{h2, paragraphs, queries}`` for the given catalog state.

    Args:
        category: ``Category`` instance or ``None`` for /catalog/ root.
        selected_color_slugs: list of colour slugs from
            ``parse_color_filter`` (single or multi-select).
        available_colors: chip dicts with ``slug``/``label`` to resolve
            human-readable colour names for non-curated slugs.

    Returns:
        dict ready for the template, or ``None`` when no copy applies
        (per-category catalog with no colour filter — that screen
        already has ``category.description``).
    """
    color_slug = (selected_color_slugs or [None])[0]
    if color_slug is None and category is not None:
        # /catalog/<category>/ without colour filter — let the existing
        # category description handle SEO. Returning None lets the
        # template skip the new block cleanly.
        return None

    if color_slug is None:
        # /catalog/ root — brand-level copy. Phase 19h: admin override
        # via CatalogColorSeoOverride(scope="general", color_slug="").
        override = _load_override("general", "", None)
        if override is not None:
            return _merge_curated_with_override(
                base_h2=GENERAL_CATALOG_SEO_COPY["h2"],
                base_paragraphs=GENERAL_CATALOG_SEO_COPY["paragraphs"],
                base_queries=GENERAL_CATALOG_SEO_COPY["queries"],
                override=override,
                color_slug="",
            )
        return {
            "h2": GENERAL_CATALOG_SEO_COPY["h2"],
            "paragraphs": GENERAL_CATALOG_SEO_COPY["paragraphs"],
            "queries": GENERAL_CATALOG_SEO_COPY["queries"],
            "color_slug": "",
        }

    # Resolve a human-readable label for the colour, used by the
    # generic fallback. We prefer the chip label (matches what the
    # user clicked) over the slug itself.
    color_label = ""
    for chip in available_colors or []:
        if (chip.get("slug") or "") == color_slug:
            color_label = chip.get("label") or ""
            break

    color_data = _palette(color_slug)
    if color_data is None:
        color_data = _generic_color_copy(color_slug, color_label)
    color_data = dict(color_data)
    color_data["slug"] = color_slug

    cat_label = _category_label(category)
    color_name = color_data["name"]
    adj_m = color_data["adj_m"]
    adj_m_cap = adj_m[:1].upper() + adj_m[1:]
    adj_n = color_data["adj_n"]
    adj_n_cap = adj_n[:1].upper() + adj_n[1:]
    if category is None:
        h2 = _(
            "%(adj_m_cap)s одяг TwoComms — стрітвір у відтінку «%(name)s»"
        ) % {"adj_m_cap": adj_m_cap, "name": color_name}
    else:
        h2 = _(
            "%(adj_n_cap)s %(cat)s TwoComms — український стрітвір з принтом"
        ) % {"adj_n_cap": adj_n_cap, "cat": cat_label}

    base_paragraphs = _build_color_paragraphs(color_data, category)
    base_queries = _build_queries_from_seed(color_data)

    # Phase 19h: admin override (scope=brand for /catalog/?color=…,
    # scope=category for /catalog/<cat>/?color=…). Only non-empty
    # fields override the curated palette.
    scope = "category" if category is not None else "brand"
    override = _load_override(scope, color_slug, category)
    if override is not None:
        return _merge_curated_with_override(
            base_h2=h2,
            base_paragraphs=base_paragraphs,
            base_queries=base_queries,
            override=override,
            color_slug=color_slug,
        )

    return {
        "h2": h2,
        "paragraphs": base_paragraphs,
        "queries": base_queries,
        "color_slug": color_slug,
    }


def _merge_curated_with_override(
    *,
    base_h2: Any,
    base_paragraphs: List[Any],
    base_queries: List[Dict[str, Any]],
    override: Dict[str, Any],
    color_slug: str,
) -> Dict[str, Any]:
    """Merge curated palette with non-empty override fields."""
    h2 = override.get("h2") or base_h2
    body_html = override.get("body_html") or ""
    paragraphs = _split_html_paragraphs(body_html) if body_html else base_paragraphs
    queries_override = override.get("queries_json") or []
    if queries_override:
        # Validate and pass through only well-shaped chips.
        queries: List[Dict[str, str]] = []
        for chip in queries_override:
            if not isinstance(chip, dict):
                continue
            label = (chip.get("label") or "").strip()
            url = (chip.get("url") or "").strip()
            freq = (chip.get("freq") or "mf").strip().lower()
            if not label or not url:
                continue
            if freq not in {"hf", "mf", "lf"}:
                freq = "mf"
            queries.append({"label": label, "url": url, "freq": freq})
        if queries:
            base_queries = queries
    return {
        "h2": h2,
        "paragraphs": paragraphs,
        "queries": base_queries,
        "color_slug": color_slug,
    }
