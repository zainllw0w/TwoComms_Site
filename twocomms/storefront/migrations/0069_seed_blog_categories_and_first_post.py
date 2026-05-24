from django.db import migrations
from django.utils import timezone


SOURCE_URL = "https://veteranfund.com.ua/stories-of-winner/artem-sinilo-istoriia-veterana/"


def _set_fields(obj, values):
    for field, value in values.items():
        if hasattr(obj, field):
            setattr(obj, field, value)


def seed_blog(apps, schema_editor):
    BlogCategory = apps.get_model("storefront", "BlogCategory")
    BlogPost = apps.get_model("storefront", "BlogPost")
    db_alias = schema_editor.connection.alias

    categories = [
        {
            "slug": "brand-news",
            "order": 10,
            "name_uk": "Новини бренда TwoComms",
            "name_ru": "Новости бренда TwoComms",
            "name_en": "TwoComms brand news",
            "description_uk": "Офіційні оновлення бренда, команди, виробництва і важливих етапів розвитку TwoComms.",
            "description_ru": "Официальные обновления бренда, команды, производства и важных этапов развития TwoComms.",
            "description_en": "Official updates about the TwoComms brand, team, production and key development milestones.",
            "seo_title_uk": "Новини бренда TwoComms",
            "seo_title_ru": "Новости бренда TwoComms",
            "seo_title_en": "TwoComms brand news",
            "seo_h1_uk": "Новини бренда TwoComms",
            "seo_h1_ru": "Новости бренда TwoComms",
            "seo_h1_en": "TwoComms brand news",
            "seo_description_uk": "Офіційні новини TwoComms: розвиток бренда, виробництво, колаборації та важливі етапи.",
            "seo_description_ru": "Официальные новости TwoComms: развитие бренда, производство, коллаборации и важные этапы.",
            "seo_description_en": "Official TwoComms news: brand growth, production, collaborations and key milestones.",
            "bottom_title_uk": "Більше контексту про TwoComms",
            "bottom_title_ru": "Больше контекста о TwoComms",
            "bottom_title_en": "More context about TwoComms",
            "bottom_text_uk": "Тут збираються матеріали про походження бренда, нові дропи, виробничі рішення і події, які формують характер TwoComms.",
            "bottom_text_ru": "Здесь собираются материалы о происхождении бренда, новых дропах, производственных решениях и событиях, которые формируют характер TwoComms.",
            "bottom_text_en": "This page collects stories about the brand origin, new drops, production decisions and events shaping TwoComms.",
        },
        {
            "slug": "product-reviews",
            "order": 20,
            "name_uk": "Огляди продукції",
            "name_ru": "Обзоры продукции",
            "name_en": "Product reviews",
            "description_uk": "Огляди речей TwoComms: посадка, матеріали, принти, сезонність і сценарії носіння.",
            "description_ru": "Обзоры вещей TwoComms: посадка, материалы, принты, сезонность и сценарии носки.",
            "description_en": "Reviews of TwoComms apparel: fit, materials, prints, seasonality and use cases.",
            "seo_title_uk": "Огляди продукції TwoComms",
            "seo_title_ru": "Обзоры продукции TwoComms",
            "seo_title_en": "TwoComms product reviews",
            "seo_h1_uk": "Огляди продукції TwoComms",
            "seo_h1_ru": "Обзоры продукции TwoComms",
            "seo_h1_en": "TwoComms product reviews",
            "seo_description_uk": "Практичні огляди худі, футболок, лонгслівів і кастомних речей TwoComms.",
            "seo_description_ru": "Практичные обзоры худи, футболок, лонгсливов и кастомных вещей TwoComms.",
            "seo_description_en": "Practical reviews of TwoComms hoodies, T-shirts, long sleeves and custom apparel.",
        },
        {
            "slug": "guides",
            "order": 30,
            "name_uk": "Корисні знання",
            "name_ru": "Полезные знания",
            "name_en": "Useful knowledge",
            "description_uk": "Гайди про догляд за одягом, друк, тканини, розміри і деталі, які продовжують життя речі.",
            "description_ru": "Гайды об уходе за одеждой, печати, тканях, размерах и деталях, которые продлевают жизнь вещи.",
            "description_en": "Guides on garment care, printing, fabrics, sizing and details that extend a piece's life.",
            "seo_title_uk": "Корисні знання про одяг і принти",
            "seo_title_ru": "Полезные знания об одежде и принтах",
            "seo_title_en": "Useful knowledge about apparel and prints",
            "seo_h1_uk": "Корисні знання",
            "seo_h1_ru": "Полезные знания",
            "seo_h1_en": "Useful knowledge",
            "seo_description_uk": "Поради TwoComms про догляд, вибір розміру, матеріали, DTF-друк і щоденне використання речей.",
            "seo_description_ru": "Советы TwoComms об уходе, выборе размера, материалах, DTF-печати и ежедневном использовании вещей.",
            "seo_description_en": "TwoComms advice on care, sizing, materials, DTF printing and daily apparel use.",
        },
    ]

    category_by_slug = {}
    for item in categories:
        slug = item["slug"]
        obj, _ = BlogCategory.objects.using(db_alias).get_or_create(
            slug=slug,
            defaults={
                "name": item["name_uk"],
                "description": item["description_uk"],
                "seo_title": item["seo_title_uk"],
                "seo_h1": item["seo_h1_uk"],
                "seo_description": item["seo_description_uk"],
                "order": item["order"],
                "is_active": True,
            },
        )
        _set_fields(obj, {
            "name": item["name_uk"],
            "description": item["description_uk"],
            "seo_title": item["seo_title_uk"],
            "seo_h1": item["seo_h1_uk"],
            "seo_description": item["seo_description_uk"],
            "bottom_title": item.get("bottom_title_uk", ""),
            "bottom_text": item.get("bottom_text_uk", ""),
            "is_active": True,
            "order": item["order"],
            **item,
        })
        obj.save(using=db_alias)
        category_by_slug[slug] = obj

    published_at = timezone.now()
    post_values = {
        "category": category_by_slug["brand-news"],
        "title": "TwoComms і Український ветеранський фонд: 2 з 4 етапів уже закрито",
        "title_uk": "TwoComms і Український ветеранський фонд: 2 з 4 етапів уже закрито",
        "title_ru": "TwoComms и Украинский ветеранский фонд: 2 из 4 этапов уже закрыты",
        "title_en": "TwoComms and the Ukrainian Veterans Fund: 2 of 4 stages are already complete",
        "excerpt": "TwoComms фіксує внутрішній прогрес після підтримки Українського ветеранського фонду: два етапи з чотирьох уже закрито, наступні кроки готуються.",
        "excerpt_uk": "TwoComms фіксує внутрішній прогрес після підтримки Українського ветеранського фонду: два етапи з чотирьох уже закрито, наступні кроки готуються.",
        "excerpt_ru": "TwoComms фиксирует внутренний прогресс после поддержки Украинского ветеранского фонда: два этапа из четырех уже закрыты, следующие шаги готовятся.",
        "excerpt_en": "TwoComms is tracking internal progress after support from the Ukrainian Veterans Fund: two of four stages are complete and the next steps are being prepared.",
        "content_html": (
            "<p>TwoComms продовжує розвивати бренд після підтримки Українського ветеранського фонду. "
            "Публічна історія фонду розповідає про Артема Синіло, ветеранський досвід і запуск TwoComms як українського бренда з характером.</p>"
            "<p>За внутрішнім планом команди вже закрито 2 з 4 етапів: базові виробничі процеси стабілізовано, "
            "а контентна та продуктова система отримала перший робочий каркас. Наступні етапи стосуватимуться масштабування, "
            "нових матеріалів і сильнішої комунікації навколо речей TwoComms.</p>"
            "<p>Це тестова редакційна публікація для нового розділу «Новини та блог». Ми ще доповнимо її деталями, фото і точними датами, "
            "але вже зараз фіксуємо головне: TwoComms рухається по плану і збирає історію бренда в одному канонічному місці.</p>"
        ),
        "content_html_uk": (
            "<p>TwoComms продовжує розвивати бренд після підтримки Українського ветеранського фонду. "
            "Публічна історія фонду розповідає про Артема Синіло, ветеранський досвід і запуск TwoComms як українського бренда з характером.</p>"
            "<p>За внутрішнім планом команди вже закрито 2 з 4 етапів: базові виробничі процеси стабілізовано, "
            "а контентна та продуктова система отримала перший робочий каркас. Наступні етапи стосуватимуться масштабування, "
            "нових матеріалів і сильнішої комунікації навколо речей TwoComms.</p>"
            "<p>Це тестова редакційна публікація для нового розділу «Новини та блог». Ми ще доповнимо її деталями, фото і точними датами, "
            "але вже зараз фіксуємо головне: TwoComms рухається по плану і збирає історію бренда в одному канонічному місці.</p>"
        ),
        "content_html_ru": (
            "<p>TwoComms продолжает развивать бренд после поддержки Украинского ветеранского фонда. "
            "Публичная история фонда рассказывает об Артеме Синило, ветеранском опыте и запуске TwoComms как украинского бренда с характером.</p>"
            "<p>По внутреннему плану команды уже закрыты 2 из 4 этапов: базовые производственные процессы стабилизированы, "
            "а контентная и продуктовая система получила первый рабочий каркас. Следующие этапы будут связаны с масштабированием, "
            "новыми материалами и более сильной коммуникацией вокруг вещей TwoComms.</p>"
            "<p>Это тестовая редакционная публикация для нового раздела «Новости и блог». Мы еще дополним ее деталями, фото и точными датами, "
            "но уже сейчас фиксируем главное: TwoComms движется по плану и собирает историю бренда в одном каноническом месте.</p>"
        ),
        "content_html_en": (
            "<p>TwoComms continues to develop the brand after support from the Ukrainian Veterans Fund. "
            "The fund's public story covers Artem Synilo, veteran experience and the launch of TwoComms as a Ukrainian brand with character.</p>"
            "<p>According to the team's internal roadmap, 2 of 4 stages are already complete: core production processes are stabilized, "
            "and the content and product system now has its first working structure. The next stages will focus on scaling, "
            "new materials and stronger communication around TwoComms pieces.</p>"
            "<p>This is a test editorial post for the new News and Blog section. We will expand it with details, images and exact dates, "
            "but the main point is already here: TwoComms is moving according to plan and collecting the brand story in one canonical place.</p>"
        ),
        "source_url": SOURCE_URL,
        "seo_title": "TwoComms і Український ветеранський фонд",
        "seo_title_uk": "TwoComms і Український ветеранський фонд",
        "seo_title_ru": "TwoComms и Украинский ветеранский фонд",
        "seo_title_en": "TwoComms and the Ukrainian Veterans Fund",
        "seo_description": "TwoComms фіксує внутрішній прогрес після підтримки Українського ветеранського фонду: 2 з 4 етапів уже закрито.",
        "seo_description_uk": "TwoComms фіксує внутрішній прогрес після підтримки Українського ветеранського фонду: 2 з 4 етапів уже закрито.",
        "seo_description_ru": "TwoComms фиксирует внутренний прогресс после поддержки Украинского ветеранского фонда: 2 из 4 этапов уже закрыты.",
        "seo_description_en": "TwoComms tracks internal progress after support from the Ukrainian Veterans Fund: 2 of 4 stages are already complete.",
        "seo_keywords": "TwoComms, Український ветеранський фонд, Артем Синіло, ветеранський бізнес",
        "seo_keywords_uk": "TwoComms, Український ветеранський фонд, Артем Синіло, ветеранський бізнес",
        "seo_keywords_ru": "TwoComms, Украинский ветеранский фонд, Артем Синило, ветеранский бизнес",
        "seo_keywords_en": "TwoComms, Ukrainian Veterans Fund, Artem Synilo, veteran business",
        "is_published": True,
        "published_at": published_at,
    }
    post, _ = BlogPost.objects.using(db_alias).get_or_create(
        slug="twocomms-veteran-fund-progress",
        defaults=post_values,
    )
    _set_fields(post, post_values)
    post.save(using=db_alias)


class Migration(migrations.Migration):

    dependencies = [
        ("storefront", "0068_blogcategory_blogpost_blogpostview_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_blog, migrations.RunPython.noop),
    ]
