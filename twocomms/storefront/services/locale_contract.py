from __future__ import annotations

from typing import Final


_DEFAULT_LANGUAGE: Final = "uk"
_INTL_LOCALES: Final = {
    "uk": "uk-UA",
    "ru": "ru-UA",
    "en": "en-UA",
}
_CURRENCY_CODE: Final = "UAH"
_CURRENCY_SUFFIXES: Final = {
    "uk": "грн",
    "ru": "грн",
    "en": "UAH",
}


def build_storefront_locale_contract(language: str | None) -> dict[str, object]:
    """Return the stable, public locale metadata shared by storefront scripts."""
    normalized_language = (language or "").lower().replace("_", "-").split("-", 1)[0]
    if normalized_language not in _INTL_LOCALES:
        normalized_language = _DEFAULT_LANGUAGE

    return {
        "language": normalized_language,
        "intlLocale": _INTL_LOCALES[normalized_language],
        "currency": {
            "code": _CURRENCY_CODE,
            "suffix": _CURRENCY_SUFFIXES[normalized_language],
        },
    }
