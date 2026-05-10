"""
2026-05-11 — Inject sales-oriented H2 blocks at the top of each category's
``description`` for stronger commercial SEO (купити / замовити / ціна
+ Київ / Харків / Львів). Idempotent: the rendered HTML carries a
marker ``<!-- twc-sales-seo-h2:v1 -->`` so repeated invocations skip
already-injected categories.

Run::

    python manage.py inject_sales_seo_h2

Use ``--force`` to re-inject (will strip the previous marker block and
replace it with the latest content).
"""
from __future__ import annotations

import re

from django.core.management.base import BaseCommand

from storefront.models import Category


MARKER_OPEN = "<!-- twc-sales-seo-h2:v1 -->"
MARKER_CLOSE = "<!-- /twc-sales-seo-h2:v1 -->"


# Per-slug commercial SEO blocks. Each one targets a distinct keyword
# cluster (купити / замовити / ціна) and surfaces high-frequency cities
# (Київ, Харків, Львів, Дніпро, Одеса) in the H2 itself, which has the
# strongest weight for category landings on Google UA.
SEO_PACKS: dict[str, str] = {
    "tshirts": """
<h2>Купити чоловічу футболку з принтом — доставка по Києву, Харкову, Львову</h2>
<p><strong>Купити футболку з принтом</strong> у TwoComms можна онлайн із
відправленням у будь-яке місто України: <strong>Київ, Харків, Львів,
Дніпро, Одеса, Запоріжжя, Вінниця, Полтава, Чернівці, Івано-Франківськ,
Тернопіль, Луцьк, Хмельницький, Ужгород, Чернігів</strong>. Чоловічі
футболки з авторськими принтами — від 590 грн, доставка Новою Поштою
1–2 дні, безкоштовний обмін розміру протягом 14 днів.</p>

<h2>Замовити жіночу футболку онлайн в Україні — авторський streetwear</h2>
<p><strong>Замовити жіночу футболку</strong> з принтом ЗСУ або
streetwear-графікою — на цій сторінці зібрані всі моделі унісекс- та
жіночих фасонів TwoComms. Шиємо в Україні з преміум-бавовни 220 г/м²,
друк DTF — стійкий до прання та носіння. Розміри XS–XXL, тонкі шви,
посадка під будь-яку фігуру.</p>

<h2>Унісекс футболки TwoComms — патріотичні принти ЗСУ за справедливою ціною</h2>
<p><strong>Унісекс-футболки TwoComms</strong> — це патріотичні принти,
тризуб, авторські колаборації з ЗСУ та streetwear-ілюстрації українських
митців. Ціни — від 590 до 990 грн залежно від моделі та складності
друку. Частину прибутку від кожної покупки направляємо на підтримку
Збройних Сил України.</p>
""",
    "hoodie": """
<h2>Купити худі з принтом онлайн у Києві, Харкові, Львові — доставка по Україні</h2>
<p><strong>Купити худі з принтом</strong> у TwoComms можна з доставкою
у <strong>Київ, Харків, Львів, Дніпро, Одесу, Запоріжжя, Вінницю,
Полтаву, Чернівці, Івано-Франківськ, Тернопіль, Луцьк, Хмельницький,
Ужгород, Чернігів</strong>. Чоловічі та жіночі худі від 1490 грн,
доставка Новою Поштою 1–2 дні, обмін розміру протягом 14 днів безкоштовно.</p>

<h2>Замовити чоловіче або жіноче худі з доставкою — щільна тканина 320 г/м²</h2>
<p><strong>Замовити худі</strong> у TwoComms — це український streetwear
із мілітарним характером: щільна петельчаста тканина 320 г/м², посилені
шви, двошарова резинка манжет і капюшона. Чоловічі худі прямого крою,
жіночі моделі з трохи звуженою посадкою, унісекс-фасони — підходять усім.
Розміри XS–XXL.</p>

<h2>Тепле унісекс-худі TwoComms — авторські патріотичні принти ЗСУ</h2>
<p><strong>Худі TwoComms</strong> — це авторські принти на тему ЗСУ,
тризуба, української історії та сучасної pop-культури. DTF-друк
зберігає кольори після 30+ циклів прання. Гарантія на принт — 6 місяців.
Працюємо лише з українським виробництвом і донатимо частину прибутку
на потреби Збройних Сил України.</p>
""",
    "long-sleeve": """
<h2>Купити лонгслів з принтом у Києві, Харкові, Львові — від 890 грн</h2>
<p><strong>Купити лонгслів з принтом</strong> можна з доставкою у
<strong>Київ, Харків, Львів, Дніпро, Одесу, Запоріжжя, Вінницю,
Полтаву, Чернівці, Івано-Франківськ, Тернопіль, Луцьк, Хмельницький,
Ужгород, Чернігів</strong>. Базові моделі — від 890 грн, лонгсліви з
повноколірним DTF-принтом — до 1490 грн. Доставка Новою Поштою 1–2 дні,
14 днів на обмін розміру.</p>

<h2>Замовити чоловічі або жіночі лонгсліви онлайн в Україні</h2>
<p><strong>Замовити лонгслів</strong> у TwoComms — універсальний шар
streetwear-гардероба: сильніший за футболку, легший за худі. Бавовняний
трикотаж 200–240 г/м², двошарові резинки манжет, прямий або oversize-крій.
Чоловічі лонгсліви прямого силуету, жіночі моделі зі звуженою посадкою,
унісекс — універсальні. Розміри XS–XXL.</p>

<h2>Лонгсліви TwoComms — базовий streetwear із характером</h2>
<p><strong>Лонгсліви TwoComms</strong> — лаконічні принти з мілітарним
ДНК: тризуб на грудях, авторські написи на рукаві, символи ЗСУ на спині.
Можна носити окремо у міжсезоння або шарувати під худі та куртки. 100%
українського виробництва, 6 місяців гарантії на принт, частину прибутку
донатимо на ЗСУ.</p>
""",
}


def _strip_existing_marker(html: str) -> str:
    """Remove a previously injected sales SEO block (between markers).

    Idempotent: returns the input unchanged when no marker is present.
    """
    pattern = re.compile(
        re.escape(MARKER_OPEN) + r".*?" + re.escape(MARKER_CLOSE) + r"\s*",
        re.DOTALL,
    )
    return pattern.sub("", html)


def _wrap(payload: str) -> str:
    return f"{MARKER_OPEN}\n{payload.strip()}\n{MARKER_CLOSE}\n\n"


class Command(BaseCommand):
    help = (
        "Inject 3 sales-oriented H2 sections (купити / замовити / ціна + "
        "cities) at the top of each category's long-form description."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Re-inject even if a marker already exists "
            "(replaces the previous block).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print what would change without saving.",
        )

    def handle(self, *args, **options):
        force = options["force"]
        dry_run = options["dry_run"]

        touched = 0
        skipped = 0

        for slug, payload in SEO_PACKS.items():
            try:
                cat = Category.objects.get(slug=slug)
            except Category.DoesNotExist:
                self.stdout.write(self.style.WARNING(
                    f"[skip] category slug={slug} not found"
                ))
                continue

            current = cat.description or ""
            already = MARKER_OPEN in current
            if already and not force:
                skipped += 1
                self.stdout.write(self.style.NOTICE(
                    f"[skip] {slug}: marker present (use --force to overwrite)"
                ))
                continue

            stripped = _strip_existing_marker(current) if already else current
            new_desc = _wrap(payload) + stripped.lstrip()

            if dry_run:
                self.stdout.write(self.style.SUCCESS(
                    f"[dry] {slug}: would write {len(new_desc)} chars "
                    f"(was {len(current)})"
                ))
                continue

            cat.description = new_desc
            cat.save(update_fields=["description", "updated_at"])
            touched += 1
            self.stdout.write(self.style.SUCCESS(
                f"[ok] {slug}: injected (now {len(new_desc)} chars, "
                f"was {len(current)})"
            ))

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. injected={touched} skipped={skipped} dry_run={dry_run}"
        ))
