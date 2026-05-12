"""Phase 13.5 — manually-crafted, theme-aware product copy (plain text).

Replaces broken Phase 13 HTML output. Each garment gets theme-tailored
intro + theme-FAQ, with shared per-category material/style/care text.
All plain-text (template uses |linebreaksbr which would escape HTML).

Public API:
  * ``build_copy(product)`` → dict of fields ready to assign.
  * ``looks_like_phase13_autofill(field, value)`` → True if value
    matches the Phase 13 generator signature (safe to overwrite).
"""
from __future__ import annotations

from typing import Iterable


# --- per-category labels & base copy ---------------------------------------

LABEL_NOM = {"tshirts": "футболка", "hoodie": "худі", "long-sleeve": "лонгслів"}
LABEL_ACC = {"tshirts": "футболку", "hoodie": "худі", "long-sleeve": "лонгслів"}
LABEL_GEN = {"tshirts": "футболки", "hoodie": "худі", "long-sleeve": "лонгсліва"}


def _nom(cat):  return LABEL_NOM.get(cat, "товар")
def _acc(cat):  return LABEL_ACC.get(cat, "товар")
def _gen(cat):  return LABEL_GEN.get(cat, "товару")
def _nom_cap(cat): return _nom(cat).capitalize()


CATEGORY_COMMON = {
    "tshirts": {
        "para_material": (
            "Виготовлена зі щільного бавовняного трикотажу 180–220 г/м²: "
            "не просвічується, добре тримає форму після прання, м'яка до шкіри. "
            "Принт нанесено методом DTF-друку — насичені кольори, тонкі деталі "
            "та стійкість до 50+ циклів прання при дотриманні правил догляду."
        ),
        "para_style": (
            "Універсальна форма: пасує і для сольного носіння, і для шарування "
            "під сорочку, худі або легку куртку. Поєднується з джинсами, "
            "карго-штанами, шортами чи спідницею. Доступні regular та "
            "oversize-силуети, розміри XS–XXL."
        ),
        "care": (
            "Прати при 30 °C у режимі для бавовни, навиворіт, без агресивних "
            "відбілювачів. Сушити на повітрі, без сушильної машини. Прасувати "
            "з вивороту або через тканину — не торкайтеся праскою принта."
        ),
        "audience_base": (
            "Підійде тим, хто шукає базову, але авторську футболку — без "
            "масмаркету і копій західних брендів. Для щоденного носіння у "
            "місті, активного відпочинку чи як подарунок патріотичним рідним."
        ),
        "kw_base": [
            "футболка TwoComms", "купити футболку", "футболка з принтом",
            "патріотична футболка", "українська футболка", "футболка ЗСУ",
            "стрітвір футболка", "футболка унісекс", "DTF друк",
        ],
        "faq_size": (
            "Як обрати розмір футболки?",
            "Орієнтуйтеся на розмірну сітку. Для regular fit — свій звичний "
            "розмір; для oversize — на 1 менший (помірний оверсайз) або свій "
            "(виразний). У сумнівах між двома — беріть більший.",
        ),
        "faq_care": (
            "Як прати футболку, щоб принт не зіпсувався?",
            "Виверніть навиворіт, прийте при 30 °C у режимі для бавовни без "
            "відбілювачів. Сушіть на повітрі. Прасувати можна з вивороту або "
            "через марлю. DTF-принт витримує 50+ циклів такого прання.",
        ),
        "faq_delivery": (
            "Як швидко доставимо футболку?",
            "Новою Поштою — 1–3 робочі дні по всій Україні. Відділення/"
            "поштомат від 85 ₴, кур'єр від 180 ₴. Замовлення до 14:00 "
            "відправляємо того ж дня.",
        ),
        "faq_custom": (
            "Чи можна замовити футболку зі своїм принтом?",
            "Так — у TwoComms є сервіс кастомного друку. Надішліть макет, "
            "оберіть колір і розмір, ми надрукуємо й доставимо. Мінімальне "
            "замовлення — 1 одиниця.",
        ),
    },
    "hoodie": {
        "para_material": (
            "Худі виготовлене зі щільного трикотажу з начосом 280–320 г/м²: "
            "тримає тепло, добре сидить, не витягується після прання. Капюшон "
            "двошаровий, із плетеним шнурком; манжети та низ — посилена "
            "резинка. Принт нанесено DTF-друком — стійка фарба, що передає всі "
            "деталі ілюстрації."
        ),
        "para_style": (
            "Базовий шар streetwear-гардероба: сидить як у regular, так і в "
            "oversize-силуеті, поєднується з футболкою, лонгслівом або "
            "сорочкою. Підходить для прохолодної погоди, активного відпочинку "
            "та щоденного носіння. Розміри XS–XXL."
        ),
        "care": (
            "Прати при 30 °C, навиворіт, без агресивних засобів. Сушити "
            "природним способом — не на батареї та не в сушильній машині. "
            "Прасувати лише з вивороту або через тканину. При перших пранні "
            "можлива усадка до 2% — це природна властивість бавовни."
        ),
        "audience_base": (
            "Для тих, хто шукає тепле стильне худі з характером — без "
            "масмаркетного «лубочного» патріотизму та копій західних брендів. "
            "Для міста, активного відпочинку, або як патріотичний подарунок."
        ),
        "kw_base": [
            "худі TwoComms", "купити худі", "худі з принтом",
            "патріотичне худі", "українське худі", "худі ЗСУ",
            "стрітвір худі", "худі унісекс", "тепле худі", "DTF друк",
        ],
        "faq_size": (
            "Як обрати розмір худі?",
            "Для класичного силуету — свій звичний розмір; для oversize — на "
            "1 більший. Якщо плануєте шарувати худі поверх сорочки/лонгсліва, "
            "рекомендуємо взяти на розмір більший за звичний.",
        ),
        "faq_care": (
            "Як прати худі, щоб не зіпсувалося?",
            "Прання при 30 °C, режим для бавовни, навиворіт, без відбілювачів. "
            "Сушити горизонтально або на плічках — не на батареї та не в "
            "сушарці. Прасування лише з вивороту, не торкайтеся праскою "
            "принта.",
        ),
        "faq_delivery": (
            "Як швидко доставимо худі?",
            "Новою Поштою — 1–3 робочі дні. Відділення/поштомат від 85 ₴, "
            "адресна кур'єрська доставка від 180 ₴. Замовлення до 14:00 "
            "йдуть того ж дня.",
        ),
        "faq_custom": (
            "Чи можна замовити худі зі своїм принтом?",
            "Так — оформіть кастомний друк через нашу форму: завантажте "
            "макет, оберіть колір і розмір базового худі, ми надрукуємо й "
            "доставимо персональну модель.",
        ),
    },
    "long-sleeve": {
        "para_material": (
            "Лонгслів виготовлений з бавовняного трикотажу 200–240 г/м² — "
            "щільнішого за футбольний, легшого за худі. Манжети — двошарова "
            "резинка, тримає рукав на місці. Принт нанесено DTF-друком: "
            "насичені стійкі кольори, тонкі деталі."
        ),
        "para_style": (
            "Універсальний базовий шар streetwear-гардероба: можна носити "
            "окремо у прохолодну погоду, шарувати під худі або легку куртку. "
            "Поєднується з джинсами, карго та темним низом. Силуети — regular "
            "та oversize, розміри XS–XXL."
        ),
        "care": (
            "Прати при 30 °C у режимі для бавовни, навиворіт. Сушити на "
            "повітрі, без сушильної машини. Прасувати з вивороту або через "
            "тканину. Мінімальна усадка (до 2%) при першому пранні є "
            "природною властивістю бавовни."
        ),
        "audience_base": (
            "Для тих, кому замало футболки, але худі поки зайве. Базовий шар "
            "із характером, добре виглядає самостійно і у багатошаровому "
            "образі. Гарний для активного відпочинку та повсякденного носіння."
        ),
        "kw_base": [
            "лонгслів TwoComms", "купити лонгслів", "лонгслів з принтом",
            "український лонгслів", "патріотичний лонгслів", "лонгслів ЗСУ",
            "стрітвір лонгслів", "лонгслів унісекс", "DTF друк",
        ],
        "faq_size": (
            "Як обрати розмір лонгсліва?",
            "Для класичного (regular) силуету — свій звичний розмір; для "
            "oversize — на 1 більший. Якщо плануєте шарувати лонгслів під "
            "худі або куртку, беріть свій звичний розмір.",
        ),
        "faq_care": (
            "Як прати лонгслів, щоб принт залишився яскравим?",
            "Прання при 30 °C, навиворіт, без відбілювачів. Сушити природним "
            "способом. Прасування лише з вивороту або через тканину, не "
            "торкаючись праскою принта.",
        ),
        "faq_delivery": (
            "Як довго їде доставка?",
            "Новою Поштою — 1–3 робочі дні. Відділення/поштомат від 85 ₴, "
            "адресна кур'єрська від 180 ₴. Оформлюйте до 14:00 — відправимо "
            "сьогодні.",
        ),
        "faq_custom": (
            "Чи можна замовити лонгслів зі своїм принтом?",
            "Так — у TwoComms є сервіс кастомного друку. Надішліть макет, "
            "оберіть колір і розмір лонгсліва — ми надрукуємо й доставимо.",
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
    # TwoComms»; Phase 13.5 emitted «… — купити <category> TwoComms»
    # with the nominative form (finding A); both must be rewritten.
    "seo_title":         lambda v: (
        v.endswith(" — TwoComms") and (
            v.startswith("Купити ") or
            " — купити футболка TwoComms" in v or
            " — купити худі TwoComms" in v or
            " — купити лонгслів TwoComms" in v or
            " — купити товар TwoComms" in v
        )
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

def _fmt(text: str, cat: str) -> str:
    return text.format(
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
        intro_short = (
            f"{_nom_cap(cat)} TwoComms: {product.title} — авторський "
            f"streetwear з мілітарним ДНК, DTF-друк, бавовна."
        )
        intro_long = (
            f"{product.title} — {_nom(cat)} TwoComms у мілітарно-"
            f"streetwear ДНК. Виготовлена в Україні, з авторським "
            f"принтом і якісним DTF-друком."
        )
        audience_extra = "Гарний вибір для щоденного носіння у місті."
        kw_list = [product.title] + common["kw_base"]
        theme_faq_q = f"Що особливого в цій моделі?"
        theme_faq_a = (
            f"Це авторська модель TwoComms з мілітарно-streetwear ДНК. "
            f"DTF-друк, щільна бавовна, пошиття в Україні. Частина "
            f"прибутку йде на підтримку ЗСУ."
        )
        alt_short = "авторський принт"

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
    seo_title = f"{t} — купити {_acc(cat)} TwoComms"
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
        f"{intro_short} Шиємо в Україні, DTF-друк, бавовна. "
        f"Доставка Новою Поштою. Підтримуємо ЗСУ."
    )
    if len(seo_description) > 320:
        seo_description = seo_description[:317].rstrip() + "…"

    # SEO keywords (≤300): joined comma list.
    kw_line, size = "", 300
    for k in kw_list:
        tentative = (kw_line + ", " + k) if kw_line else k
        if len(tentative) > size:
            break
        kw_line = tentative

    # Alt (≤200)
    alt = f"{t} — {alt_short}, {_nom(cat)} TwoComms"
    alt = alt[:200]

    # Short description (≤300)
    short = intro_short
    if len(short) > 300:
        short = short[:297].rstrip() + "…"

    # Full description: plain-text paragraphs separated by blank line.
    full_parts = [intro_long, common["para_material"], common["para_style"],
                  audience_extra + " " + common["audience_base"]]
    full = "\n\n".join(p.strip() for p in full_parts if p and p.strip())

    # Target audience: theme-specific + base.
    target = (audience_extra + " " + common["audience_base"]).strip()

    care = common["care"]

    faqs = [
        (theme_faq_q, theme_faq_a),
        common["faq_size"],
        common["faq_care"],
        common["faq_delivery"],
        common["faq_custom"],
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
