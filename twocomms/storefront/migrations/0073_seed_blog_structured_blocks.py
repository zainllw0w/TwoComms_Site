from django.db import migrations


def _field(post, name, default=""):
    return getattr(post, name, None) or getattr(post, name.replace("_uk", ""), None) or default


def _html_payload(post):
    return {
        "uk": _field(post, "content_html_uk", _field(post, "content_html")),
        "ru": _field(post, "content_html_ru", _field(post, "content_html")),
        "en": _field(post, "content_html_en", _field(post, "content_html")),
    }


def seed_structured_blog(apps, schema_editor):
    BlogCategory = apps.get_model("storefront", "BlogCategory")
    BlogPost = apps.get_model("storefront", "BlogPost")
    BlogPostBlock = apps.get_model("storefront", "BlogPostBlock")
    db = schema_editor.connection.alias

    news, _ = BlogCategory.objects.using(db).get_or_create(
        slug="news",
        defaults={"name": "Новини", "description": "Новини TwoComms", "order": 0, "is_active": True},
    )
    reviews, _ = BlogCategory.objects.using(db).get_or_create(
        slug="reviews",
        defaults={"name": "Огляди", "description": "Огляди продукції TwoComms", "order": 10, "is_active": True},
    )
    veteran, _ = BlogCategory.objects.using(db).get_or_create(
        slug="veteran-fund",
        defaults={
            "name": "Український ветеранський фонд",
            "description": "Звіти та новини щодо Українського ветеранського фонду.",
            "order": 0,
            "is_active": True,
        },
    )
    product_reviews, _ = BlogCategory.objects.using(db).get_or_create(
        slug="product-reviews",
        defaults={"name": "Огляди продукції", "description": "Огляди речей TwoComms.", "order": 0, "is_active": True},
    )
    if veteran.parent_id != news.pk:
        veteran.parent = news
        veteran.save(update_fields=["parent"])
    if product_reviews.parent_id != reviews.pk:
        product_reviews.parent = reviews
        product_reviews.save(update_fields=["parent"])

    try:
        post = BlogPost.objects.using(db).get(slug="twocomms-veteran-fund-progress")
    except BlogPost.DoesNotExist:
        post = None
    if post:
        if post.category_id != veteran.pk:
            post.category = veteran
            post.save(update_fields=["category"])
        if not BlogPostBlock.objects.using(db).filter(post=post).exists():
            BlogPostBlock.objects.using(db).bulk_create(
                [
                    BlogPostBlock(
                        post=post,
                        block_type="metric_cards",
                        sort_order=0,
                        payload={
                            "cards": [
                                {"label": {"uk": "Внутрішній прогрес", "ru": "Внутренний прогресс", "en": "Internal progress"}, "value": "2/4", "caption": {"uk": "етапи закрито", "ru": "этапы закрыты", "en": "stages complete"}},
                                {"label": {"uk": "Виробництво", "ru": "Производство", "en": "Production"}, "value": "DTF", "caption": {"uk": "власний друк", "ru": "собственная печать", "en": "in-house print"}},
                                {"label": {"uk": "Можливості", "ru": "Возможности", "en": "Capabilities"}, "value": "B2B/B2C", "caption": {"uk": "кастом і колаборації", "ru": "кастом и коллаборации", "en": "custom and collaborations"}},
                            ]
                        },
                    ),
                    BlogPostBlock(
                        post=post,
                        block_type="rich_text",
                        sort_order=10,
                        payload={"html": _html_payload(post)},
                    ),
                    BlogPostBlock(
                        post=post,
                        block_type="source_list",
                        sort_order=20,
                        payload={
                            "sources": [
                                {
                                    "label": {
                                        "uk": "Офіційна історія Українського ветеранського фонду",
                                        "ru": "Официальная история Украинского ветеранского фонда",
                                        "en": "Official Ukrainian Veterans Fund story",
                                    },
                                    "url": getattr(post, "source_url", ""),
                                }
                            ]
                        },
                    ),
                    BlogPostBlock(
                        post=post,
                        block_type="cta_group",
                        sort_order=30,
                        payload={
                            "layout": "full",
                            "buttons": [
                                {
                                    "provider": "telegram",
                                    "label": {"uk": _field(post, "cta_label_uk", "Написати в Telegram"), "ru": _field(post, "cta_label_ru", "Написать в Telegram"), "en": _field(post, "cta_label_en", "Message us on Telegram")},
                                    "caption": {"uk": _field(post, "cta_text_uk"), "ru": _field(post, "cta_text_ru"), "en": _field(post, "cta_text_en")},
                                    "url": getattr(post, "cta_url", "") or "https://t.me/twocomms",
                                }
                            ],
                        },
                    ),
                ]
            )

    try:
        post_111 = BlogPost.objects.using(db).get(slug="111")
    except BlogPost.DoesNotExist:
        post_111 = None
    if post_111:
        if post_111.category_id != product_reviews.pk:
            post_111.category = product_reviews
            post_111.save(update_fields=["category"])
        if not BlogPostBlock.objects.using(db).filter(post=post_111).exists():
            BlogPostBlock.objects.using(db).create(
                post=post_111,
                block_type="rich_text",
                sort_order=10,
                payload={"html": _html_payload(post_111)},
            )


class Migration(migrations.Migration):

    dependencies = [
        ("storefront", "0072_blogmediaasset_blogpostblock_blogpromocampaign_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_structured_blog, migrations.RunPython.noop),
    ]
