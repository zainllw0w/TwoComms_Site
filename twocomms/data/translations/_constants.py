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
