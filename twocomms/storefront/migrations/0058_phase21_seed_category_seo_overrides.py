"""Phase 21 (2026-05-10) — seed unique SEO copy for the three main
categories so each landing page has differentiated ``<title>`` / ``H1``
/ ``description`` instead of the boilerplate "{Назва} - TwoComms".

Only fills fields that are still empty; never overwrites editor-managed
copy. Safe to re-run.
"""
from django.db import migrations


SEEDS = {
    "tshirts": {
        "seo_title": "Футболки TwoComms — стрітвеар та мілітарі-принти від українського бренду",
        "seo_h1": "Футболки з характером — стрітвеар і мілітарі від TwoComms",
        "seo_description": (
            "Авторські футболки TwoComms: стріт, мілітарі та патріотичні принти, "
            "100% бавовна, друк DTF, доставка Новою Поштою по Україні за 1–3 дні."
        ),
    },
    "hoodie": {
        "seo_title": "Худі TwoComms — теплі толстовки зі стрітвеар-принтами та свободною посадкою",
        "seo_h1": "Худі від українського бренду TwoComms — стрітвеар, мілітарі, преміум фліс",
        "seo_description": (
            "Худі TwoComms з фліс-підкладкою, посадкою oversize та авторськими "
            "принтами. Стрітвеар і мілітарі стилі, виготовлено в Україні, "
            "доставка від 1 дня."
        ),
    },
    "long-sleeve": {
        "seo_title": "Лонгсліви TwoComms — лаконічний стрітвеар з рукавами на кожен день",
        "seo_h1": "Лонгсліви TwoComms — щільна бавовна, мілітарі та стрітвеар принти",
        "seo_description": (
            "Лонгсліви TwoComms: щільна бавовна, акуратна посадка, авторський "
            "DTF-друк. Стрітвеар і мілітарі лонгсліви від українського бренду, "
            "швидка доставка по Україні."
        ),
    },
}


def seed_overrides(apps, schema_editor):
    Category = apps.get_model("storefront", "Category")
    for slug, payload in SEEDS.items():
        try:
            category = Category.objects.get(slug=slug)
        except Category.DoesNotExist:
            # Slug not present on this environment (e.g. dev DB without
            # production seed). Skip silently — the field stays blank
            # and the template falls back to "{Назва} - TwoComms".
            continue
        update_kwargs = {}
        for field, value in payload.items():
            if not getattr(category, field, ""):
                update_kwargs[field] = value
        if update_kwargs:
            for field, value in update_kwargs.items():
                setattr(category, field, value)
            category.save(update_fields=list(update_kwargs))


def noop_reverse(apps, schema_editor):
    """Reverse is a no-op: we never blow away editor-managed copy."""
    return None


class Migration(migrations.Migration):

    dependencies = [
        ("storefront", "0057_category_seo_overrides"),
    ]

    operations = [
        migrations.RunPython(seed_overrides, noop_reverse),
    ]
