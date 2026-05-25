"""Phase 17c — register translatable model fields with django-modeltranslation.

For every registered field, modeltranslation auto-creates one column per
language declared in ``MODELTRANSLATION_LANGUAGES`` (``name_uk``,
``name_ru``, ``name_en``, …). Reads through the original attribute
``instance.name`` return the value for the active language with fallback
to Ukrainian (see ``MODELTRANSLATION_FALLBACK_LANGUAGES``).

After running ``manage.py makemigrations`` + ``migrate``, run
``manage.py update_translation_fields storefront`` to copy existing
values into ``*_uk`` columns.
"""

from __future__ import annotations

from modeltranslation.translator import TranslationOptions, register

from storefront.models import (
    BlogCategory,
    BlogPost,
    Category,
    Product,
    ProductFAQ,
)


@register(Category)
class CategoryTranslationOptions(TranslationOptions):
    fields = (
        "name",
        "description",
        "seo_text_title",
        "seo_intro_html",
        "seo_title",
        "seo_h1",
        "seo_description",
    )


@register(BlogCategory)
class BlogCategoryTranslationOptions(TranslationOptions):
    fields = (
        "name",
        "description",
        "seo_title",
        "seo_h1",
        "seo_description",
        "bottom_title",
        "bottom_text",
    )


@register(BlogPost)
class BlogPostTranslationOptions(TranslationOptions):
    fields = (
        "title",
        "excerpt",
        "content_html",
        "cover_alt",
        "cta_label",
        "cta_text",
        "seo_title",
        "seo_description",
        "seo_keywords",
    )


@register(Product)
class ProductTranslationOptions(TranslationOptions):
    fields = (
        "title",
        "short_description",
        "description",
        "full_description",
        "target_audience",
        "care_instructions",
        "main_image_alt",
        "seo_title",
        "seo_description",
        "seo_keywords",
        "seo_bottom_html",
    )


@register(ProductFAQ)
class ProductFAQTranslationOptions(TranslationOptions):
    fields = ("question", "answer")
