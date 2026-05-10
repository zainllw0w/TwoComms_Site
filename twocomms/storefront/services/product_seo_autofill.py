"""Phase 13 — auto-fill empty SEO/content fields on Product rows.

Strategy:
  * Idempotent — never overwrite a field that's already populated.
  * No external AI calls — purely template-driven generation based on
    ``product.title`` + ``product.category.slug`` (with sensible
    fallbacks).
  * Per-category templates pick natural Ukrainian phrasing matching
    the brand tone (мілітарний streetwear / patriotic / ЗСУ DNA).
  * Generates 5 standard FAQs per product when the product has none.

The service is invoked by the ``autofill_product_seo`` management
command. It can also be called directly from views or signals when
a new product is created.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from django.db.models import Count, QuerySet


# --------------------------------------------------------------- TEMPLATES

# Per-category copy templates. Variables: {title}, {category_singular},
# {category_genitive}, {colour_list}, {price}.

CATEGORY_LABEL = {
    "hoodie":      ("худі",      "худі",      "худі"),
    "tshirts":     ("футболка",  "футболки",  "футболку"),
    "long-sleeve": ("лонгслів",  "лонгсліва", "лонгслів"),
}

# Default fallback for unknown categories.
DEFAULT_LABEL = ("товар", "товару", "товар")


def _labels(category_slug: str | None) -> tuple[str, str, str]:
    """(nominative-singular, genitive-singular, accusative) for category."""
    return CATEGORY_LABEL.get((category_slug or "").lower(), DEFAULT_LABEL)


def _build_seo_title(product) -> str:
    """80-160 char SEO title with brand suffix."""
    nom, _, _ = _labels(getattr(product.category, "slug", None))
    base = product.title.strip()
    suffix = " — TwoComms"
    # Add category if title doesn't already contain it.
    if nom not in base.lower():
        candidate = f"Купити {base} ({nom}){suffix}"
    else:
        candidate = f"Купити {base}{suffix}"
    return candidate[:160]


def _build_seo_description(product) -> str:
    """≤320 char SEO meta description."""
    nom, _, acc = _labels(getattr(product.category, "slug", None))
    title = product.title.strip()
    text = (
        f"{title} — авторський {nom} TwoComms з мілітарним ДНК. "
        f"DTF-друк, бавовна, шиємо в Україні. Доставка Новою Поштою, "
        f"оплата Monobank/накладений платіж. Підтримуємо ЗСУ."
    )
    return text[:320]


def _build_seo_keywords(product) -> str:
    """≤300 char comma-separated keyword list."""
    nom, gen, _ = _labels(getattr(product.category, "slug", None))
    title = product.title.strip()
    base = [
        title,
        f"купити {nom}",
        f"{nom} TwoComms",
        f"патріотичний {nom}",
        f"{nom} ЗСУ",
        f"{nom} з принтом",
        f"український {nom}",
        f"{nom} streetwear",
        f"{nom} тризуб",
        "TwoComms",
        "DTF друк",
        "одяг ЗСУ",
    ]
    text = ", ".join(base)
    return text[:300]


def _build_main_image_alt(product) -> str:
    """≤200 char alt text for main image."""
    nom, _, _ = _labels(getattr(product.category, "slug", None))
    title = product.title.strip()
    text = f"{title} — {nom} TwoComms, авторський принт, DTF-друк"
    return text[:200]


def _build_short_description(product) -> str:
    """≤300 char short description (used in cards and meta-fallback)."""
    nom, _, _ = _labels(getattr(product.category, "slug", None))
    title = product.title.strip()
    text = (
        f"{title} — авторський {nom} TwoComms у мілітарно-streetwear ДНК. "
        f"Якісний DTF-друк, бавовна, шиємо в Україні."
    )
    return text[:300]


def _build_care_instructions(product) -> str:
    """Standard care text (≤500 chars)."""
    nom, _, _ = _labels(getattr(product.category, "slug", None))
    return (
        f"Прання при 30 °C у режимі для бавовни, без агресивних "
        f"відбілювачів. Сушити природним способом, без сушильної "
        f"машини. Прасування дозволене з вивороту або через марлю — "
        f"уникайте прямого контакту праски з принтом. {nom.capitalize()} "
        f"може мінімально сісти (до 2%) при першому пранні — це "
        f"природна властивість бавовни."
    )


def _build_target_audience(product) -> str:
    """Standard target audience text."""
    return (
        "Тим, хто живе в Україні й цінує мілітарну streetwear-естетику. "
        "Тим, хто підтримує ЗСУ та шукає одяг з характером — без зайвого "
        "пафосу, з авторськими принтами та якісним пошиттям. Підходить "
        "для щоденного носіння у місті, активного відпочинку та як "
        "подарунок патріотичним рідним і друзям."
    )


def _build_full_description(product) -> str:
    """Long-form HTML description (~1500-2000 chars), only used if
    `description` (legacy) is empty AND no `full_description` set."""
    nom, gen, acc = _labels(getattr(product.category, "slug", None))
    title = product.title.strip()
    return (
        f"<p><strong>{title}</strong> — авторський {nom} TwoComms у "
        f"мілітарно-streetwear ДНК. Виготовлений в Україні зі щільної "
        f"бавовни з нанесенням принту методом DTF-друку: насичені "
        f"кольори, тонкі деталі, стійкість до прання й розтягнення.</p>"
        f"<p>Цей {nom} ідеально підійде тим, хто шукає базовий streetwear "
        f"з характером — мінімум зайвого, максимум сенсу. Принт "
        f"відображає мілітарну естетику без «лубочності»: сучасні "
        f"графічні рішення, що добре виглядають у місті та комбінуються "
        f"з джинсами, карго-штанами або базовим темним низом.</p>"
        f"<h3>Що ви отримуєте</h3>"
        f"<ul>"
        f"<li>Авторський дизайн TwoComms — не клон західних брендів</li>"
        f"<li>Бавовняний трикотаж високої щільності, не просвічується</li>"
        f"<li>DTF-друк — 50+ циклів прання без втрати якості</li>"
        f"<li>Розміри від XS до XXL, є oversize-силует</li>"
        f"<li>Подарункове крафт-пакування з листівкою-подякою ЗСУ</li>"
        f"</ul>"
        f"<h3>Доставка та підтримка</h3>"
        f"<p>Новою Поштою по всій Україні (від 85 ₴ за відділення/"
        f"поштомат, від 180 ₴ за адресну). Оплата — Monobank, "
        f"накладений платіж або картка. Повернення/обмін — 14 днів. "
        f"Частина прибутку йде на підтримку Збройних Сил України.</p>"
    )


# Standard FAQ template per category. Each entry: (question, answer).
# Most answers are universal — only the {nom} variable differs.

UNIVERSAL_FAQS = [
    (
        "Як обрати розмір {nom}?",
        "Орієнтуйтеся на нашу <a href=\"/rozmirna-sitka/\">розмірну "
        "сітку</a>: для класичного силуету беріть свій звичний розмір; "
        "для oversize — на 1 більший, якщо хочете виразний оверсайз, "
        "або свій розмір — для помірного. У сумнівах між двома "
        "розмірами ми рекомендуємо більший.",
    ),
    (
        "Чи можна прати {nom_acc} в машинці?",
        "Так — у режимі для бавовни при 30 °C, без агресивних "
        "відбілювачів. Сушити рекомендуємо природним способом, без "
        "сушильної машини. DTF-принт витримує 50+ циклів прання за "
        "умов правильного догляду.",
    ),
    (
        "Скільки триває доставка?",
        "По Україні — 1–3 робочі дні Новою Поштою. Адресна доставка "
        "доступна у більшості міст. Деталі — на сторінці "
        "<a href=\"/delivery/\">доставки</a>.",
    ),
    (
        "Як повернути або обміняти товар?",
        "Протягом 14 днів з моменту отримання — за умови збереження "
        "товарного вигляду та етикеток. Повернення безкоштовне у "
        "разі браку. Подробиці на сторінці "
        "<a href=\"/povernennya-ta-obmin/\">повернення та обмін</a>.",
    ),
    (
        "Чи можна замовити з власним принтом?",
        "Так — у TwoComms працює сервіс "
        "<a href=\"/custom-print/\">кастомного друку</a>: надішліть "
        "макет, оберіть колір і розмір виробу, ми надрукуємо й "
        "доставимо. Мінімальне замовлення — 1 одиниця.",
    ),
]


def _build_faqs(product) -> list[tuple[str, str]]:
    """Generate 5 standard FAQ Q/A pairs for a product."""
    nom, gen, acc = _labels(getattr(product.category, "slug", None))
    out = []
    for q, a in UNIVERSAL_FAQS:
        out.append((
            q.format(nom=nom, nom_gen=gen, nom_acc=acc),
            a.format(nom=nom, nom_gen=gen, nom_acc=acc),
        ))
    return out


# --------------------------------------------------------------- ENGINE

@dataclass
class AutofillReport:
    products_seen: int = 0
    products_changed: int = 0
    fields_filled: dict = field(default_factory=dict)
    faqs_created: int = 0

    def bump(self, field_name: str) -> None:
        self.fields_filled[field_name] = self.fields_filled.get(field_name, 0) + 1


# Map of (Product field name → builder callable). Builder is called only
# when the field is empty / whitespace.
FIELD_BUILDERS = {
    "seo_title":          _build_seo_title,
    "seo_description":    _build_seo_description,
    "seo_keywords":       _build_seo_keywords,
    "main_image_alt":     _build_main_image_alt,
    "short_description":  _build_short_description,
    "care_instructions":  _build_care_instructions,
    "target_audience":    _build_target_audience,
    "full_description":   _build_full_description,
}


def _is_blank(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    return False


def autofill_product(product, *, faq_model, dry_run: bool = False,
                     report: AutofillReport | None = None) -> AutofillReport:
    """Fill all blank SEO fields + create FAQs if none exist.

    ``faq_model`` is passed in so the function works equally from a
    management command (real ``ProductFAQ``) and from data migrations
    (historical model via ``apps.get_model``)."""
    report = report or AutofillReport()
    report.products_seen += 1

    update_fields: list[str] = []
    for field_name, builder in FIELD_BUILDERS.items():
        current = getattr(product, field_name, None)
        if _is_blank(current):
            new_value = builder(product)
            setattr(product, field_name, new_value)
            update_fields.append(field_name)
            report.bump(field_name)

    if update_fields and not dry_run:
        product.save(update_fields=update_fields)

    # FAQs — only create when there are zero existing FAQs (active or not).
    has_faqs = faq_model.objects.filter(product=product).exists()
    if not has_faqs:
        faqs = _build_faqs(product)
        if not dry_run:
            for idx, (question, answer) in enumerate(faqs):
                faq_model.objects.create(
                    product=product, question=question, answer=answer,
                    order=idx, is_active=True,
                )
        report.faqs_created += len(faqs)
        update_fields.append("faqs:+5")

    if update_fields:
        report.products_changed += 1
    return report


def autofill_queryset(queryset: "QuerySet", *, faq_model,
                      dry_run: bool = False) -> AutofillReport:
    """Run ``autofill_product`` over a queryset of Products."""
    report = AutofillReport()
    for product in queryset.select_related("category"):
        autofill_product(product, faq_model=faq_model, dry_run=dry_run,
                         report=report)
    return report
