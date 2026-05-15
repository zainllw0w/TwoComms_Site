"""Phase 17z5 — shared constants for the product translation generator.

Translations are split into multiple modules so each file stays
human-reviewable. ``build_product_translations.py`` imports everything and
emits the final JSON consumed by ``manage.py import_product_translations``.
"""
from __future__ import annotations


PTYPES = {
    "tshirt": {
        "uk": {"nom": "Футболка", "gen": "футболку"},
        "ru": {"nom": "Футболка", "gen": "футболку"},
        "en": {"nom": "T-shirt", "gen": "a T-shirt"},
    },
    "hoodie": {
        "uk": {"nom": "Худі", "gen": "худі"},
        "ru": {"nom": "Худи", "gen": "худи"},
        "en": {"nom": "Hoodie", "gen": "a hoodie"},
    },
    "longsleeve": {
        "uk": {"nom": "Лонгслів", "gen": "лонгслів"},
        "ru": {"nom": "Лонгслив", "gen": "лонгслив"},
        "en": {"nom": "Longsleeve", "gen": "a longsleeve"},
    },
}

PTYPE_KW_TAIL = {
    "tshirt": {
        "uk": "футболка TwoComms, купити футболку, футболка з принтом, патріотична футболка, українська футболка, футболка ЗСУ, стрітвір футболка, футболка унісекс, DTF друк",
        "ru": "футболка TwoComms, купить футболку, футболка с принтом, патриотическая футболка, украинская футболка, футболка ВСУ, стритвир футболка, футболка унисекс, DTF печать",
        "en": "TwoComms tshirt, buy tshirt, printed tshirt, patriotic tshirt, Ukrainian tshirt, Ukraine tshirt, streetwear tshirt, unisex tshirt, DTF print",
    },
    "hoodie": {
        "uk": "худі TwoComms, купити худі, худі з принтом, патріотичне худі, українське худі, худі ЗСУ, стрітвір худі, худі унісекс, тепле худі, DTF друк",
        "ru": "худи TwoComms, купить худи, худи с принтом, патриотичная худи, украинская худи, худи ВСУ, стритвир худи, худи унисекс, тёплая худи, DTF печать",
        "en": "TwoComms hoodie, buy hoodie, printed hoodie, patriotic hoodie, Ukrainian hoodie, Ukraine hoodie, streetwear hoodie, unisex hoodie, warm hoodie, DTF print",
    },
    "longsleeve": {
        "uk": "лонгслів TwoComms, купити лонгслів, лонгслів з принтом, український лонгслів, патріотичний лонгслів, лонгслів ЗСУ, стрітвір лонгслів, лонгслів унісекс, DTF друк",
        "ru": "лонгслив TwoComms, купить лонгслив, лонгслив с принтом, украинский лонгслив, патриотический лонгслив, лонгслив ВСУ, стритвир лонгслив, лонгслив унисекс, DTF печать",
        "en": "TwoComms longsleeve, buy longsleeve, printed longsleeve, Ukrainian longsleeve, Ukraine longsleeve, patriotic longsleeve, streetwear longsleeve, unisex longsleeve, DTF print",
    },
}

SEO_TAIL = {
    "uk": "Шиємо в Україні, DTF-друк, бавовна. Доставка Новою Поштою. Підтримуємо ЗСУ.",
    "ru": "Шьём в Украине, DTF-печать, хлопок. Доставка Новой Почтой. Поддерживаем ВСУ.",
    "en": "Made in Ukraine, DTF print, cotton. Nova Poshta shipping. We support the Ukrainian Armed Forces.",
}

TARGET_TAIL = {
    "uk": "Підійде тим, хто шукає базову, але авторську річ — без масмаркету і копій західних брендів. Для щоденного носіння у місті, активного відпочинку чи як подарунок патріотичним рідним.",
    "ru": "Подойдёт тем, кто ищет базовую, но авторскую вещь — без масс-маркета и копий западных брендов. Для повседневной носки в городе, активного отдыха или как подарок патриотичным близким.",
    "en": "A perfect pick for anyone seeking a basic yet author-driven piece — no mass market, no Western brand knock-offs. Made for daily city wear, active leisure or a gift for patriotic friends and family.",
}

# ---------------------------------------------------------------------------
# FULL DESCRIPTION building blocks (per product type)
# ---------------------------------------------------------------------------
# Paragraph 2 — material & construction. Used in ``full_description``.
MATERIAL_PARAGRAPH = {
    "tshirt": {
        "uk": "Виготовлена зі щільного бавовняного трикотажу 180–220 г/м²: не просвічується, добре тримає форму після прання, м'яка до шкіри. Принт нанесено методом DTF-друку — насичені кольори, тонкі деталі та стійкість до 50+ циклів прання при дотриманні правил догляду.",
        "ru": "Изготовлена из плотного хлопкового трикотажа 180–220 г/м²: не просвечивает, хорошо держит форму после стирки, мягкая к коже. Принт нанесён методом DTF-печати — насыщенные цвета, тонкие детали и стойкость к 50+ циклам стирки при соблюдении правил ухода.",
        "en": "Built from dense cotton jersey at 180–220 g/m²: opaque, holds its shape after washing, soft to the skin. The print is applied by DTF printing — saturated colours, fine detail and a lifespan of 50+ wash cycles when care instructions are followed.",
    },
    "hoodie": {
        "uk": "Худі виготовлене зі щільного трикотажу з начосом 280–320 г/м²: тримає тепло, добре сидить, не витягується після прання. Капюшон двошаровий, із плетеним шнурком; манжети та низ — посилена резинка. Принт нанесено DTF-друком — стійка фарба, що передає всі деталі ілюстрації.",
        "ru": "Худи изготовлено из плотного трикотажа с начёсом 280–320 г/м²: держит тепло, хорошо сидит, не растягивается после стирки. Капюшон двухслойный, с плетёным шнурком; манжеты и низ — усиленная резинка. Принт нанесён DTF-печатью — стойкая краска, передающая все детали иллюстрации.",
        "en": "The hoodie is crafted from dense brushed-back jersey at 280–320 g/m²: holds heat, fits well, doesn't sag after washing. A double-layer hood with a braided drawstring; reinforced ribbed cuffs and hem. The print is applied by DTF printing — durable ink that preserves every illustrative detail.",
    },
    "longsleeve": {
        "uk": "Лонгслів виготовлений з бавовняного трикотажу 200–240 г/м² — щільнішого за футбольний, легшого за худі. Манжети — двошарова резинка, тримає рукав на місці. Принт нанесено DTF-друком: насичені стійкі кольори, тонкі деталі.",
        "ru": "Лонгслив выполнен из хлопкового трикотажа 200–240 г/м² — плотнее футболочного, легче худи. Манжеты — двухслойная резинка, держит рукав на месте. Принт нанесён DTF-печатью: насыщенные стойкие цвета, тонкие детали.",
        "en": "The longsleeve is made from cotton jersey at 200–240 g/m² — denser than tee fabric, lighter than a hoodie. Cuffs feature a two-layer rib that keeps sleeves in place. The print is applied by DTF: saturated, durable colours and fine detail.",
    },
}

# Paragraph 3 — universal styling / sizing. Used in ``full_description``.
STYLING_PARAGRAPH = {
    "tshirt": {
        "uk": "Універсальна форма: пасує і для сольного носіння, і для шарування під сорочку, худі або легку куртку. Поєднується з джинсами, карго-штанами, шортами чи спідницею. Доступні regular та oversize-силуети, розміри XS–XXL.",
        "ru": "Универсальная форма: подходит и для одиночной носки, и для лайеринга под рубашку, худи или лёгкую куртку. Сочетается с джинсами, карго-штанами, шортами или юбкой. Доступны regular и oversize силуэты, размеры XS–XXL.",
        "en": "A universal shape: works solo or layered under a shirt, hoodie or light jacket. Pairs with jeans, cargo pants, shorts or a skirt. Available in regular and oversize silhouettes, sizes XS–XXL.",
    },
    "hoodie": {
        "uk": "Базовий шар streetwear-гардероба: сидить як у regular, так і в oversize-силуеті, поєднується з футболкою, лонгслівом або сорочкою. Підходить для прохолодної погоди, активного відпочинку та щоденного носіння. Розміри XS–XXL.",
        "ru": "Базовый слой streetwear-гардероба: сидит и в regular, и в oversize-силуэте, сочетается с футболкой, лонгсливом или рубашкой. Подходит для прохладной погоды, активного отдыха и повседневной носки. Размеры XS–XXL.",
        "en": "A streetwear-wardrobe staple: works in regular or oversize fits, pairs with a tee, longsleeve or shirt. Built for cool weather, active leisure and daily wear. Sizes XS–XXL.",
    },
    "longsleeve": {
        "uk": "Універсальний базовий шар streetwear-гардероба: можна носити окремо у прохолодну погоду, шарувати під худі або легку куртку. Поєднується з джинсами, карго та темним низом. Силуети — regular та oversize, розміри XS–XXL.",
        "ru": "Универсальный базовый слой streetwear-гардероба: можно носить отдельно в прохладную погоду, лайерить под худи или лёгкую куртку. Сочетается с джинсами, карго и тёмным низом. Силуэты — regular и oversize, размеры XS–XXL.",
        "en": "A universal streetwear base layer: wear solo in cool weather, layer under a hoodie or light jacket. Pairs with jeans, cargos and dark bottoms. Available in regular and oversize fits, sizes XS–XXL.",
    },
}


CARE = {
    "tshirt": {
        "uk": "Прати при 30 °C у режимі для бавовни, навиворіт, без агресивних відбілювачів. Сушити на повітрі, без сушильної машини. Прасувати з вивороту або через тканину — не торкайтеся праскою принта.",
        "ru": "Стирать при 30 °C в режиме для хлопка, наизнанку, без агрессивных отбеливателей. Сушить на воздухе, без сушильной машины. Гладить с изнанки или через ткань — не касайтесь утюгом принта.",
        "en": "Wash at 30 °C on a cotton cycle, inside out, no harsh bleach. Air-dry only, no tumble drying. Iron inside out or through a cloth — never touch the print directly.",
    },
    "hoodie": {
        "uk": "Прати при 30 °C, навиворіт, без агресивних засобів. Сушити природним способом — не на батареї та не в сушильній машині. Прасувати лише з вивороту або через тканину. При перших пранні можлива усадка до 2% — це природна властивість бавовни.",
        "ru": "Стирать при 30 °C, наизнанку, без агрессивных средств. Сушить естественным способом — не на батарее и не в сушильной машине. Гладить только с изнанки или через ткань. При первой стирке возможна усадка до 2% — это естественное свойство хлопка.",
        "en": "Wash at 30 °C, inside out, without harsh detergents. Air-dry naturally — not on a radiator or in a tumble dryer. Iron inside out or through a cloth only. Up to 2% shrinkage on the first wash is normal for cotton.",
    },
    "longsleeve": {
        "uk": "Прати при 30 °C у режимі для бавовни, навиворіт. Сушити на повітрі, без сушильної машини. Прасувати з вивороту або через тканину. Мінімальна усадка (до 2%) при першому пранні є природною властивістю бавовни.",
        "ru": "Стирать при 30 °C в режиме для хлопка, наизнанку. Сушить на воздухе, без сушильной машины. Гладить с изнанки или через ткань. Минимальная усадка (до 2%) при первой стирке — естественное свойство хлопка.",
        "en": "Wash at 30 °C on a cotton cycle, inside out. Air-dry only, no tumble drying. Iron inside out or through a cloth. Minor shrinkage (up to 2%) on first wash is normal for cotton.",
    },
}
