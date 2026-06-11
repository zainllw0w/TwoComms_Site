"""Phase 13.5 — manually-crafted, theme-aware product copy (plain text).

Replaces broken Phase 13 HTML output. Each garment gets theme-tailored
intro + theme-FAQ, with shared per-category material/style/care text.
All plain-text (template uses |linebreaksbr which would escape HTML).

Public API:
  * ``build_copy(product)`` → dict of fields ready to assign.
  * ``looks_like_phase13_autofill(field, value)`` → True if value
    matches the Phase 13 generator signature (safe to overwrite).

Phase 17v (2026-05-16) — DATA-LEVEL TRANSLATION. The static UA copy in
``THEMES`` (sibling module) and ``CATEGORY_COMMON`` is wrapped with
``gettext_lazy``; translations live in the standard ``django.po``
files for ``ru`` and ``en``. ``_fmt`` casts every value to ``str`` so
the lazy proxies resolve at request time using the active locale.
"""
from __future__ import annotations

from typing import Iterable

from django.utils.translation import gettext_lazy as _, pgettext_lazy


# --- per-category labels & base copy ---------------------------------------

# Phase 17v: case-aware labels. Ukrainian «худі» / «лонгслів» are
# invariant across nominative/accusative/genitive, so we use ``pgettext``
# with explicit context to give translators a chance to inflect the
# Russian forms (футболка/футболку/футболки → футболка/футболку/футболки;
# худи is invariant; лонгслив → лонгслива genitive).
LABEL_NOM = {
    "tshirts":     pgettext_lazy("nominative", "футболка"),
    "hoodie":      pgettext_lazy("nominative", "худі"),
    "long-sleeve": pgettext_lazy("nominative", "лонгслів"),
}
LABEL_ACC = {
    "tshirts":     pgettext_lazy("accusative", "футболку"),
    "hoodie":      pgettext_lazy("accusative", "худі"),
    "long-sleeve": pgettext_lazy("accusative", "лонгслів"),
}
LABEL_GEN = {
    "tshirts":     pgettext_lazy("genitive", "футболки"),
    "hoodie":      pgettext_lazy("genitive", "худі"),
    "long-sleeve": pgettext_lazy("genitive", "лонгсліва"),
}


def _nom(cat):  return str(LABEL_NOM.get(cat, pgettext_lazy("nominative", "товар")))
def _acc(cat):  return str(LABEL_ACC.get(cat, pgettext_lazy("accusative", "товар")))
def _gen(cat):  return str(LABEL_GEN.get(cat, pgettext_lazy("genitive", "товару")))
def _nom_cap(cat): return _nom(cat).capitalize()


CATEGORY_COMMON = {
    "tshirts": {
        "para_material": _(
            "Виготовлена зі щільного бавовняного трикотажу 180–220 г/м²: "
            "не просвічується, добре тримає форму після прання, м'яка до шкіри. "
            "Принт нанесено методом DTF-друку — насичені кольори, тонкі деталі "
            "та стійкість до 50+ циклів прання при дотриманні правил догляду."
        ),
        "para_style": _(
            "Універсальна форма: пасує і для сольного носіння, і для шарування "
            "під сорочку, худі або легку куртку. Поєднується з джинсами, "
            "карго-штанами, шортами чи спідницею. Доступні regular та "
            "oversize-силуети, розміри XS–XXL."
        ),
        "care": _(
            "Прати при 30 °C у режимі для бавовни, навиворіт, без агресивних "
            "відбілювачів. Сушити на повітрі, без сушильної машини. Прасувати "
            "з вивороту або через тканину — не торкайтеся праскою принта."
        ),
        "audience_base": _(
            "Підійде тим, хто шукає базову, але авторську футболку — без "
            "масмаркету і копій західних брендів. Для щоденного носіння у "
            "місті, активного відпочинку чи як подарунок патріотичним рідним."
        ),
        "kw_base": [
            _("футболка TwoComms"), _("купити футболку"), _("футболка з принтом"),
            _("патріотична футболка"), _("українська футболка"), _("футболка ЗСУ"),
            _("стрітвір футболка"), _("футболка унісекс"), _("DTF друк"),
        ],
        "faq_size": (
            _("Як обрати розмір футболки?"),
            _("Орієнтуйтеся на розмірну сітку. Для regular fit — свій звичний "
              "розмір; для oversize — на 1 менший (помірний оверсайз) або свій "
              "(виразний). У сумнівах між двома — беріть більший."),
        ),
        "faq_care": (
            _("Як прати футболку, щоб принт не зіпсувався?"),
            _("Виверніть навиворіт, періть при 30 °C у режимі для бавовни без "
              "відбілювачів. Сушіть на повітрі. Прасувати можна з вивороту або "
              "через марлю. DTF-принт витримує 50+ циклів такого прання."),
        ),
        "faq_delivery": (
            _("Як швидко доставимо футболку?"),
            _("Новою Поштою — 1–3 робочі дні по всій Україні. Відділення/"
              "поштомат від 85 ₴, кур'єр від 180 ₴. Замовлення до 14:00 "
              "відправляємо того ж дня."),
        ),
        "faq_custom": (
            _("Чи можна замовити футболку зі своїм принтом?"),
            _("Так — у TwoComms є сервіс кастомного друку. Надішліть макет, "
              "оберіть колір і розмір, ми надрукуємо й доставимо. Мінімальне "
              "замовлення — 1 одиниця."),
        ),
    },
    "hoodie": {
        "para_material": _(
            "Худі виготовлене зі щільного трикотажу з начосом 280–320 г/м²: "
            "тримає тепло, добре сидить, не витягується після прання. Капюшон "
            "двошаровий, із плетеним шнурком; манжети та низ — посилена "
            "резинка. Принт нанесено DTF-друком — стійка фарба, що передає всі "
            "деталі ілюстрації."
        ),
        "para_style": _(
            "Базовий шар streetwear-гардероба: сидить як у regular, так і в "
            "oversize-силуеті, поєднується з футболкою, лонгслівом або "
            "сорочкою. Підходить для прохолодної погоди, активного відпочинку "
            "та щоденного носіння. Розміри XS–XXL."
        ),
        "care": _(
            "Прати при 30 °C, навиворіт, без агресивних засобів. Сушити "
            "природним способом — не на батареї та не в сушильній машині. "
            "Прасувати лише з вивороту або через тканину. При перших пранні "
            "можлива усадка до 2% — це природна властивість бавовни."
        ),
        "audience_base": _(
            "Для тих, хто шукає тепле стильне худі з характером — без "
            "масмаркетного «лубочного» патріотизму та копій західних брендів. "
            "Для міста, активного відпочинку, або як патріотичний подарунок."
        ),
        "kw_base": [
            _("худі TwoComms"), _("купити худі"), _("худі з принтом"),
            _("патріотичне худі"), _("українське худі"), _("худі ЗСУ"),
            _("стрітвір худі"), _("худі унісекс"), _("тепле худі"), _("DTF друк"),
        ],
        "faq_size": (
            _("Як обрати розмір худі?"),
            _("Для класичного силуету — свій звичний розмір; для oversize — на "
              "1 більший. Якщо плануєте шарувати худі поверх сорочки/лонгсліва, "
              "рекомендуємо взяти на розмір більший за звичний."),
        ),
        "faq_care": (
            _("Як прати худі, щоб не зіпсувалося?"),
            _("Прання при 30 °C, режим для бавовни, навиворіт, без відбілювачів. "
              "Сушити горизонтально або на плічках — не на батареї та не в "
              "сушарці. Прасування лише з вивороту, не торкайтеся праскою "
              "принта."),
        ),
        "faq_delivery": (
            _("Як швидко доставимо худі?"),
            _("Новою Поштою — 1–3 робочі дні. Відділення/поштомат від 85 ₴, "
              "адресна кур'єрська доставка від 180 ₴. Замовлення до 14:00 "
              "йдуть того ж дня."),
        ),
        "faq_custom": (
            _("Чи можна замовити худі зі своїм принтом?"),
            _("Так — оформіть кастомний друк через нашу форму: завантажте "
              "макет, оберіть колір і розмір базового худі, ми надрукуємо й "
              "доставимо персональну модель."),
        ),
    },
    "long-sleeve": {
        "para_material": _(
            "Лонгслів виготовлений з бавовняного трикотажу 200–240 г/м² — "
            "щільнішого за футбольний, легшого за худі. Манжети — двошарова "
            "резинка, тримає рукав на місці. Принт нанесено DTF-друком: "
            "насичені стійкі кольори, тонкі деталі."
        ),
        "para_style": _(
            "Універсальний базовий шар streetwear-гардероба: можна носити "
            "окремо у прохолодну погоду, шарувати під худі або легку куртку. "
            "Поєднується з джинсами, карго та темним низом. Силуети — regular "
            "та oversize, розміри XS–XXL."
        ),
        "care": _(
            "Прати при 30 °C у режимі для бавовни, навиворіт. Сушити на "
            "повітрі, без сушильної машини. Прасувати з вивороту або через "
            "тканину. Мінімальна усадка (до 2%) при першому пранні є "
            "природною властивістю бавовни."
        ),
        "audience_base": _(
            "Для тих, кому замало футболки, але худі поки зайве. Базовий шар "
            "із характером, добре виглядає самостійно і у багатошаровому "
            "образі. Гарний для активного відпочинку та повсякденного носіння."
        ),
        "kw_base": [
            _("лонгслів TwoComms"), _("купити лонгслів"), _("лонгслів з принтом"),
            _("український лонгслів"), _("патріотичний лонгслів"), _("лонгслів ЗСУ"),
            _("стрітвір лонгслів"), _("лонгслів унісекс"), _("DTF друк"),
        ],
        "faq_size": (
            _("Як обрати розмір лонгсліва?"),
            _("Для класичного (regular) силуету — свій звичний розмір; для "
              "oversize — на 1 більший. Якщо плануєте шарувати лонгслів під "
              "худі або куртку, беріть свій звичний розмір."),
        ),
        "faq_care": (
            _("Як прати лонгслів, щоб принт залишився яскравим?"),
            _("Прання при 30 °C, навиворіт, без відбілювачів. Сушити природним "
              "способом. Прасування лише з вивороту або через тканину, не "
              "торкаючись праскою принта."),
        ),
        "faq_delivery": (
            _("Як довго їде доставка?"),
            _("Новою Поштою — 1–3 робочі дні. Відділення/поштомат від 85 ₴, "
              "адресна кур'єрська від 180 ₴. Оформлюйте до 14:00 — відправимо "
              "сьогодні."),
        ),
        "faq_custom": (
            _("Чи можна замовити лонгслів зі своїм принтом?"),
            _("Так — у TwoComms є сервіс кастомного друку. Надішліть макет, "
              "оберіть колір і розмір лонгсліва — ми надрукуємо й доставимо."),
        ),
    },
}


# Themes are loaded from a sibling module to keep this file lean.
from ._product_themes import THEMES


# --- Phase 13 detector signatures -----------------------------------------

_PHASE13_SIGNATURES = {
    "full_description":  lambda v: v.lstrip().startswith("<p>") and
                                   "TwoComms у мілітарно-streetwear" in v,
    "short_description": lambda v: v.rstrip().endswith(
        "Якісний DTF-друк, бавовна, шиємо в Україні."),
    "seo_description":   lambda v: (
        "DTF-друк, бавовна, шиємо в Україні. Доставка Новою Поштою" in v),
    "seo_keywords":      lambda v: (
        ", TwoComms, DTF друк, одяг ЗСУ" in v),
    "main_image_alt":    lambda v: v.rstrip().endswith(
        "TwoComms, авторський принт, DTF-друк"),
    "care_instructions": lambda v: v.lstrip().startswith(
        "Прання при 30 °C у режимі для бавовни, без агресивних"),
    "target_audience":   lambda v: v.lstrip().startswith(
        "Тим, хто живе в Україні й цінує мілітарну"),
    # SEO v1.0 Phase 2 (2026-05-12) — recognise three historical auto-
    # generator formats so the regeneration command picks them all up
    # without needing ``--force`` (which would blow away hand-edited
    # copy). The original Phase 13 autofill emitted «Купити … —
    # TwoComms» (ends with " — TwoComms"); Phase 13.5 emitted
    # «… — купити <category> TwoComms» with the nominative form
    # (finding A) and ENDS with «<NOM> TwoComms» (no em-dash before
    # TwoComms). Earlier signature only checked for the v0 ending,
    # which is why the regeneration silently no-op'd on every v1
    # title. Match both endings explicitly.
    "seo_title":         lambda v: (
        # v0 — Phase 13 autofill format «Купити X — TwoComms».
        (v.endswith(" — TwoComms") and v.startswith("Купити ")) or
        # v1 — Phase 13.5 nominative bug «X — купити <NOM> TwoComms».
        v.endswith(" — купити футболка TwoComms") or
        v.endswith(" — купити худі TwoComms") or
        v.endswith(" — купити лонгслів TwoComms") or
        v.endswith(" — купити товар TwoComms")
    ),
}

_PHASE13_FAQ_Q_PREFIXES = (
    "Як обрати розмір",          # v1 universal q1
    "Чи можна прати",             # v1 universal q2
    "Скільки триває доставка",   # v1 universal q3
    "Як повернути або обміняти",  # v1 universal q4
    "Чи можна замовити з власним принтом",  # v1 universal q5
)


def looks_like_phase13_autofill(field: str, value: str | None) -> bool:
    """Detect values produced by Phase 13 auto-fill (safe to overwrite)."""
    if not value:
        return False
    sig = _PHASE13_SIGNATURES.get(field)
    return bool(sig and sig(value))


def looks_like_phase13_faq(question: str) -> bool:
    return any(question.startswith(p) for p in _PHASE13_FAQ_Q_PREFIXES)


# --- THEME lookup ---------------------------------------------------------

_PRODUCT_ID_TO_THEME: dict[int, str] = {}
for theme_key, theme in THEMES.items():
    for pid in theme.get("ids", ()):
        _PRODUCT_ID_TO_THEME[pid] = theme_key


def get_theme_for_product(product) -> dict | None:
    key = _PRODUCT_ID_TO_THEME.get(product.pk)
    return THEMES.get(key) if key else None


# --- Field builders --------------------------------------------------------

def _fmt(text, cat: str) -> str:
    # ``text`` may be a ``gettext_lazy`` proxy (Phase 17v) — coerce to ``str``
    # so the active locale is materialised before we ``.format()`` it.
    return str(text).format(
        nom=_nom(cat), nom_cap=_nom_cap(cat),
        acc=_acc(cat), gen=_gen(cat),
    )


def _kw_list(theme: dict, common: dict, cat: str) -> list[str]:
    base = [_fmt(k, cat) for k in theme.get("kw", [])]
    base.extend(common["kw_base"])
    # Dedupe case-insensitively, preserve order.
    seen, out = set(), []
    for k in base:
        kl = k.lower().strip()
        if kl and kl not in seen:
            seen.add(kl)
            out.append(k.strip())
    return out


def build_copy(product) -> dict:
    """Assemble ``dict`` of fields + FAQ list for ``product``."""
    cat = product.category.slug
    common = CATEGORY_COMMON.get(cat) or CATEGORY_COMMON["tshirts"]
    theme = get_theme_for_product(product)

    if theme:
        intro_short = _fmt(theme["intro_short"], cat)
        intro_long = _fmt(theme["intro_long"], cat)
        audience_extra = _fmt(theme["audience"], cat)
        kw_list = _kw_list(theme, common, cat)
        theme_faq_q = _fmt(theme["faq"][0], cat)
        theme_faq_a = _fmt(theme["faq"][1], cat)
        alt_short = theme["alt_short"]
    else:
        # Fallback (products not yet mapped in THEMES).
        intro_short = _(
            "{nom_cap} TwoComms: {title} — авторський "
            "streetwear з мілітарним ДНК, DTF-друк, бавовна."
        ).format(nom_cap=_nom_cap(cat), title=product.title)
        intro_long = _(
            "{title} — {nom} TwoComms у мілітарно-"
            "streetwear ДНК. Виготовлена в Україні, з авторським "
            "принтом і якісним DTF-друком."
        ).format(nom=_nom(cat), title=product.title)
        audience_extra = str(_("Гарний вибір для щоденного носіння у місті."))
        kw_list = [product.title] + [str(k) for k in common["kw_base"]]
        theme_faq_q = str(_("Що особливого в цій моделі?"))
        theme_faq_a = str(_(
            "Це авторська модель TwoComms з мілітарно-streetwear ДНК. "
            "DTF-друк, щільна бавовна, пошиття в Україні. Частина "
            "прибутку йде на підтримку ЗСУ."
        ))
        alt_short = str(_("авторський принт"))

    # SEO title: «{product.title} — купити {acc} TwoComms»
    #
    # SEO v1.0 Phase 2 (2026-05-12) — finding (A) in the master audit.
    # Ukrainian grammar requires the accusative case after the transitive
    # verb «купити» («buy»). The Phase 13.5 implementation hardcoded the
    # nominative (`_nom`) and produced ungrammatical artefacts like
    # «купити футболка» / «купити лонгслів TwoComms». Google's 2024
    # scaled-content-abuse spam policy treats systematic grammar errors
    # as a strong machine-generated-content signal — the longer this
    # bug persisted the higher the algorithmic suppression risk. Switch
    # to `_acc` so the template renders «купити футболку TwoComms».
    # The 60-char truncate ceiling (was 160) closes finding (B); we
    # also tightened it from the historical phase-13 limit because the
    # full SERP title display cap on Google mobile in 2026 is ~60 chars.
    t = product.title.strip()
    # 17v: «купити» suffix is locale-aware. The {acc} placeholder is filled
    # via the per-locale ``LABEL_ACC`` (gettext_lazy) so RU shows «купить»,
    # EN shows «buy», and the article surfaces in the correct grammar.
    seo_title_template = _("{title} — купити {acc} TwoComms")
    seo_title = str(seo_title_template).format(title=t, acc=_acc(cat))
    SEO_TITLE_MAX = 60
    if len(seo_title) > SEO_TITLE_MAX:
        # Trim the product title (preserving the suffix) and avoid
        # cutting inside a word so the truncated string still reads.
        suffix = " — TwoComms"
        budget = SEO_TITLE_MAX - len(suffix)
        if budget > 0 and len(t) > budget:
            head = t[:budget].rsplit(" ", 1)[0]
        else:
            head = t[:budget] if budget > 0 else t
        seo_title = head + suffix

    # SEO description (≤320): intro_short + short call-to-action.
    seo_description = (
        f"{intro_short} "
        + str(_("Шиємо в Україні, DTF-друк, бавовна. "
                "Доставка Новою Поштою. Підтримуємо ЗСУ."))
    )
    if len(seo_description) > 320:
        seo_description = seo_description[:317].rstrip() + "…"

    # SEO keywords (≤300): joined comma list.
    kw_line, size = "", 300
    for k in kw_list:
        k_str = str(k)
        tentative = (kw_line + ", " + k_str) if kw_line else k_str
        if len(tentative) > size:
            break
        kw_line = tentative

    # Alt (≤200)
    alt = f"{t} — {alt_short}, {_nom(cat)} TwoComms"
    alt = alt[:200]

    # Short description (≤300)
    short = str(intro_short)
    if len(short) > 300:
        short = short[:297].rstrip() + "…"

    # Full description: plain-text paragraphs separated by blank line.
    full_parts = [
        str(intro_long),
        str(common["para_material"]),
        str(common["para_style"]),
        str(audience_extra) + " " + str(common["audience_base"]),
    ]
    full = "\n\n".join(p.strip() for p in full_parts if p and p.strip())

    # Target audience: theme-specific + base.
    target = (str(audience_extra) + " " + str(common["audience_base"])).strip()

    care = str(common["care"])

    faqs = [
        (str(theme_faq_q), str(theme_faq_a)),
        (str(common["faq_size"][0]), str(common["faq_size"][1])),
        (str(common["faq_care"][0]), str(common["faq_care"][1])),
        (str(common["faq_delivery"][0]), str(common["faq_delivery"][1])),
        (str(common["faq_custom"][0]), str(common["faq_custom"][1])),
    ]

    return {
        "seo_title":          seo_title,
        "seo_description":    seo_description,
        "seo_keywords":       kw_line,
        "main_image_alt":     alt,
        "short_description":  short,
        "full_description":   full,
        "care_instructions":  care,
        "target_audience":    target,
        "faqs":               faqs,
    }
