"""Hand-curated RU/EN translations for catalog categories.

Long HTML bodies (``description``, ``seo_intro_html``) are translated in a
later phase. Phase A covers the short SEO fields that appear in titles,
meta tags, listing pages and breadcrumbs.
"""
from __future__ import annotations

# Keyed by Ukrainian ``name``. The importer matches case-insensitively but
# whitespace must be exact.
CATEGORIES: dict[str, dict[str, dict[str, str]]] = {
    "Футболки": {
        "name": {
            "ru": "Футболки",
            "en": "T-shirts",
        },
        "seo_text_title": {
            "uk": "Футболки TwoComms — стрітвір з характером",
            "ru": "Футболки TwoComms — стритвир с характером",
            "en": "TwoComms T-shirts — streetwear with character",
        },
        "seo_title": {
            "uk": "Футболки TwoComms — купити стрітвір футболки в Україні",
            "ru": "Футболки TwoComms — купить стритвир футболки в Украине",
            "en": "TwoComms T-shirts — buy streetwear tees in Ukraine",
        },
        "seo_h1": {
            "uk": "Футболки TwoComms — авторський streetwear із принтами",
            "ru": "Футболки TwoComms — авторский streetwear с принтами",
            "en": "TwoComms T-shirts — author streetwear with prints",
        },
        "seo_description": {
            "uk": "Футболки TwoComms: щільна бавовна, авторський DTF-друк, силует для повсякденного носіння. Доставка Новою Поштою по всій Україні.",
            "ru": "Футболки TwoComms: плотный хлопок, авторская DTF-печать, силуэт для повседневной носки. Доставка Новой Почтой по всей Украине.",
            "en": "TwoComms T-shirts: dense cotton, author DTF print, silhouette built for daily wear. Nova Poshta delivery across Ukraine.",
        },
    },
    "Худі": {
        "name": {
            "ru": "Худи",
            "en": "Hoodies",
        },
        "seo_text_title": {
            "uk": "Худі TwoComms — тепло, ДНК streetwear",
            "ru": "Худи TwoComms — тепло, ДНК streetwear",
            "en": "TwoComms Hoodies — warm streetwear DNA",
        },
        "seo_title": {
            "uk": "Худі TwoComms — купити худі з принтом в Україні",
            "ru": "Худи TwoComms — купить худи с принтом в Украине",
            "en": "TwoComms Hoodies — buy a printed hoodie in Ukraine",
        },
        "seo_h1": {
            "uk": "Худі TwoComms — авторські принти, тепла бавовна",
            "ru": "Худи TwoComms — авторские принты, тёплый хлопок",
            "en": "TwoComms Hoodies — author prints, warm cotton",
        },
        "seo_description": {
            "uk": "Худі TwoComms: тепла бавовна, авторський DTF-друк, oversize та regular силует. Доставка Новою Поштою, підтримуємо ЗСУ.",
            "ru": "Худи TwoComms: тёплый хлопок, авторская DTF-печать, oversize и regular силуэт. Доставка Новой Почтой, поддерживаем ВСУ.",
            "en": "TwoComms Hoodies: warm cotton, author DTF print, oversize and regular fits. Nova Poshta delivery, we support Ukraine's army.",
        },
    },
    "лонгсліви": {
        "name": {
            "ru": "лонгсливы",
            "en": "longsleeves",
        },
        "seo_text_title": {
            "uk": "Лонгсліви TwoComms — тактичний streetwear на щодень",
            "ru": "Лонгсливы TwoComms — тактический streetwear на каждый день",
            "en": "TwoComms Longsleeves — tactical streetwear for every day",
        },
        "seo_title": {
            "uk": "Лонгсліви TwoComms — лаконічний стрітвір з рукавами",
            "ru": "Лонгсливы TwoComms — лаконичный стритвир с рукавами",
            "en": "TwoComms Longsleeves — minimalist streetwear with sleeves",
        },
        "seo_h1": {
            "uk": "Лонгсліви TwoComms — щільна бавовна, мілітарі та streetwear принти",
            "ru": "Лонгсливы TwoComms — плотный хлопок, милитари и streetwear принты",
            "en": "TwoComms Longsleeves — dense cotton, militari & streetwear prints",
        },
        "seo_description": {
            "uk": "Лонгсліви TwoComms: щільна бавовна, акуратна посадка, авторський DTF-друк. Streetwear та мілітарі лонгсліви від українського бренду.",
            "ru": "Лонгсливы TwoComms: плотный хлопок, аккуратная посадка, авторская DTF-печать. Streetwear и милитари лонгсливы от украинского бренда.",
            "en": "TwoComms Longsleeves: dense cotton, careful fit, author DTF print. Streetwear and militari longsleeves from a Ukrainian brand.",
        },
    },
}
