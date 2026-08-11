"""Pure contracts for standard Product locale ownership."""

from types import SimpleNamespace

from django.test import RequestFactory, SimpleTestCase

from storefront.services.locale_publication import (
    indexable_locales,
    locale_is_indexable,
    publication_context,
)
from storefront.templatetags.i18n_links import language_alternates


class _Faqs:
    def __init__(self, *rows):
        self.rows = rows

    def all(self):
        return list(self.rows)


def _product(**overrides):
    values = {
        "title_ru": "Чёрная футболка",
        "title_en": "Black T-shirt",
        "seo_title_ru": "Чёрная футболка — TwoComms",
        "seo_title_en": "Black T-shirt — TwoComms",
        "seo_description_ru": "Чёрная футболка TwoComms с авторским принтом.",
        "seo_description_en": "Black TwoComms T-shirt with an original print.",
        "full_description_ru": "Чёрная футболка TwoComms для повседневного гардероба.",
        "full_description_en": "A black TwoComms T-shirt for everyday wear.",
        "faqs": _Faqs(),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class LocalePublicationTests(SimpleTestCase):
    def test_ineligible_pdp_has_no_indexable_hreflang_cluster(self):
        request = RequestFactory().get("/en/product/untranslated-tee/")

        self.assertEqual(
            language_alternates(
                {
                    "request": request,
                    "locale_publication": {
                        "indexable": False,
                        "eligible_locales": ("uk",),
                    },
                }
            ),
            {},
        )

    def test_owned_raw_content_is_indexable_and_exposes_all_locales(self):
        product = _product()

        self.assertTrue(locale_is_indexable(product, "ru"))
        self.assertTrue(locale_is_indexable(product, "en"))
        self.assertEqual(indexable_locales(product), ("uk", "ru", "en"))

    def test_missing_raw_content_is_uk_only(self):
        product = _product(title_ru="", title_en="")

        self.assertEqual(indexable_locales(product), ("uk",))
        self.assertFalse(publication_context(product, "en")["indexable"])

    def test_partially_translated_active_faq_blocks_locale_owner(self):
        faq = SimpleNamespace(
            is_active=True,
            question_ru="Как сидит футболка?",
            answer_ru="Свободно.",
            question_en="",
            answer_en="Loose fit.",
        )
        product = _product(faqs=_Faqs(faq))

        self.assertTrue(locale_is_indexable(product, "ru"))
        self.assertFalse(locale_is_indexable(product, "en"))
