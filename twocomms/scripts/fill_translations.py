#!/usr/bin/env python3
"""Phase 17b — fill RU/EN translations for chrome strings in locale/.

Usage:  python scripts/fill_translations.py
Idempotent: if a msgstr is already non-empty for a known msgid, it is left as-is.

Adds translations for header/footer/common UI labels we marked with
``{% trans %}`` in Phase 17b. Page-level templates will be added in
subsequent phases (17d).
"""
from __future__ import annotations
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCALE_DIR = ROOT / "locale"

# msgid -> {ru: ..., en: ...}
TRANSLATIONS: dict[str, dict[str, str]] = {
    # ===== Footer / language switcher =====
    "Мова сайту":             {"ru": "Язык сайта",         "en": "Site language"},
    "Мова":                   {"ru": "Язык",               "en": "Language"},
    "Соцмережі TwoComms":     {"ru": "Соцсети TwoComms",   "en": "TwoComms socials"},
    "Контакти TwoComms":      {"ru": "Контакты TwoComms",  "en": "TwoComms contacts"},
    # ===== Footer columns =====
    "Покупка":                {"ru": "Покупка",            "en": "Shopping"},
    "Підтримка":              {"ru": "Поддержка",          "en": "Support"},
    "Бренд":                  {"ru": "Бренд",              "en": "Brand"},
    "Швидкий доступ":         {"ru": "Быстрый доступ",     "en": "Quick links"},
    "Каталог":                {"ru": "Каталог",            "en": "Catalog"},
    "Доставка і оплата":      {"ru": "Доставка и оплата",  "en": "Delivery & payment"},
    "Кастомний принт":        {"ru": "Кастомный принт",    "en": "Custom print"},
    "Співпраця":              {"ru": "Сотрудничество",     "en": "Cooperation"},
    "Допомога":               {"ru": "Помощь",             "en": "Help"},
    "FAQ":                    {"ru": "FAQ",                "en": "FAQ"},
    "Повернення та обмін":    {"ru": "Возврат и обмен",    "en": "Returns & exchanges"},
    "Догляд за одягом":       {"ru": "Уход за одеждой",    "en": "Garment care"},
    "Про бренд":              {"ru": "О бренде",           "en": "About the brand"},
    "Новини":                 {"ru": "Новости",            "en": "News"},
    "Контакти":               {"ru": "Контакты",           "en": "Contacts"},
    "Карта сайту":            {"ru": "Карта сайта",        "en": "Site map"},
    "Розмірна сітка":         {"ru": "Размерная сетка",    "en": "Size guide"},
    "Відстеження замовлення": {"ru": "Отслеживание заказа", "en": "Order tracking"},
    "Політика конфіденційності": {"ru": "Политика конфиденциальности", "en": "Privacy policy"},
    "Умови використання":     {"ru": "Условия использования", "en": "Terms of use"},

    # ===== Header / navigation =====
    "TwoComms логотип — стріт & мілітарі одяг": {
        "ru": "TwoComms логотип — стрит & милитари одежда",
        "en": "TwoComms logo — street & military apparel",
    },
    "Перемикач навігації":    {"ru": "Переключатель навигации", "en": "Navigation toggler"},
    "Пошук…":                 {"ru": "Поиск…",             "en": "Search…"},
    "Пошук":                  {"ru": "Поиск",              "en": "Search"},
    "Створити свій принт":    {"ru": "Создать свой принт", "en": "Create your print"},

    # ===== Header — favorites/cart/user =====
    "Перейти до обраних товарів": {"ru": "Перейти к избранным товарам", "en": "Go to favorites"},
    "Відкрити міні-корзину":  {"ru": "Открыть мини-корзину", "en": "Open mini cart"},
    "Кошик":                  {"ru": "Корзина",            "en": "Cart"},
    "Закрити":                {"ru": "Закрыть",            "en": "Close"},
    "Завантаження…":          {"ru": "Загрузка…",          "en": "Loading…"},
    "Умови доставки і оплати": {"ru": "Условия доставки и оплаты", "en": "Delivery & payment terms"},
    "Залишайте заявку на сайті або оплачуйте миттєво через mono checkout": {
        "ru": "Оставляйте заявку на сайте или оплачивайте моментально через mono checkout",
        "en": "Submit an order on the site or pay instantly via mono checkout",
    },
    "Відкрити панель користувача": {"ru": "Открыть панель пользователя", "en": "Open user panel"},
    "Аватар користувача — TwoComms": {"ru": "Аватар пользователя — TwoComms", "en": "User avatar — TwoComms"},
    "Телефон не вказано":     {"ru": "Телефон не указан",  "en": "Phone not specified"},
    "Ваші бали":              {"ru": "Ваши баллы",         "en": "Your points"},
    "Знижки • Промокоди • Підтримка ЗСУ": {
        "ru": "Скидки • Промокоды • Поддержка ВСУ",
        "en": "Discounts • Promo codes • UA Army support",
    },
    "Налаштування профілю":   {"ru": "Настройки профиля",  "en": "Profile settings"},
    "Мої замовлення":         {"ru": "Мои заказы",         "en": "My orders"},
    "Мої відгуки":            {"ru": "Мои отзывы",         "en": "My reviews"},
    "Обрані товари":          {"ru": "Избранные товары",   "en": "Favorite items"},
    "Кількість товарів у обраних": {"ru": "Количество товаров в избранном", "en": "Number of favorites"},
    "Мої промокоди":          {"ru": "Мои промокоды",      "en": "My promo codes"},
    "Панель адміністратора":  {"ru": "Панель администратора", "en": "Admin panel"},
    "Вийти":                  {"ru": "Выйти",              "en": "Sign out"},
    "Вхід в акаунт":          {"ru": "Вход в аккаунт",     "en": "Sign in"},
    "Увійти":                 {"ru": "Войти",              "en": "Sign in"},
    "Зареєструватись":        {"ru": "Зарегистрироваться", "en": "Sign up"},
    "Вхід через Google — TwoComms": {"ru": "Вход через Google — TwoComms", "en": "Sign in with Google — TwoComms"},
    "Увійти через Google":    {"ru": "Войти через Google", "en": "Sign in with Google"},
    "Авторизуйтесь, щоб не вводити дані кожного разу та накопичувати бали": {
        "ru": "Авторизуйтесь, чтобы не вводить данные каждый раз и копить баллы",
        "en": "Sign in to skip re-entering details and earn points",
    },
    "Головна":                {"ru": "Главная",            "en": "Home"},
    "Обране":                 {"ru": "Избранное",          "en": "Favorites"},
    "Профіль":                {"ru": "Профиль",            "en": "Profile"},

    # ===== Product card =====
    "Купити":                 {"ru": "Купить",             "en": "Buy"},
    "Додати до обраних":      {"ru": "Добавить в избранное", "en": "Add to favorites"},
    "Дізнатись про бали":     {"ru": "Узнать о баллах",    "en": "About points"},
    "Доступні кольори":       {"ru": "Доступные цвета",    "en": "Available colors"},
    "Кольори товару":         {"ru": "Цвета товара",       "en": "Product colors"},
    "Колір":                  {"ru": "Цвет",               "en": "Color"},
    "плюс":                   {"ru": "плюс",               "en": "plus"},
    "грн":                    {"ru": "грн",                "en": "UAH"},
    "0 балів":                {"ru": "0 баллов",           "en": "0 points"},
    # blocktrans plural strings — Django stores them with msgid/msgid_plural
    "Переглянути %(title)s":  {"ru": "Просмотреть %(title)s", "en": "View %(title)s"},
    "Купити %(title)s":       {"ru": "Купить %(title)s",   "en": "Buy %(title)s"},
    "Показати кольори %(title)s": {"ru": "Показать цвета %(title)s", "en": "Show colors of %(title)s"},

    # ===== Home page (index.html) =====
    "TwoComms — Стріт & Мілітарі Одяг | Головна": {
        "ru": "TwoComms — стрит & милитари одежда | Главная",
        "en": "TwoComms — Street & Military Apparel | Home",
    },
    "TwoComms — український магазин стріт і мілітарі одягу: футболки, худі, лонгсліви, кастомний друк і швидка доставка по Україні.": {
        "ru": "TwoComms — украинский магазин стрит и милитари одежды: футболки, худи, лонгсливы, кастомный принт и быстрая доставка по Украине.",
        "en": "TwoComms — Ukrainian streetwear & military apparel store: t-shirts, hoodies, longsleeves, custom print and fast Ukraine-wide shipping.",
    },
    "TwoComms — стріт & мілітарі одяг з ексклюзивним дизайном": {
        "ru": "TwoComms — стрит & милитари одежда с эксклюзивным дизайном",
        "en": "TwoComms — street & military apparel with exclusive design",
    },
    "Футболки, худі та лонгсліви з авторськими принтами. Бренд TwoComms — українське виробництво, швидка доставка.": {
        "ru": "Футболки, худи и лонгсливы с авторскими принтами. Бренд TwoComms — украинское производство, быстрая доставка.",
        "en": "T-shirts, hoodies and longsleeves with original prints. TwoComms — Ukrainian production with fast delivery.",
    },
    "TwoComms — стріт & мілітарі одяг": {
        "ru": "TwoComms — стрит & милитари одежда",
        "en": "TwoComms — street & military apparel",
    },
    "Ексклюзивні футболки, худі та лонгсліви з характером. Швидка доставка по Україні.": {
        "ru": "Эксклюзивные футболки, худи и лонгсливы с характером. Быстрая доставка по Украине.",
        "en": "Exclusive t-shirts, hoodies and longsleeves with character. Fast Ukraine-wide shipping.",
    },
    "TwoComms — бренд:":      {"ru": "TwoComms — бренд:",  "en": "TwoComms — the brand:"},
    "Стріт & мілітарі":       {"ru": "Стрит & милитари",   "en": "Street & military"},
    "одяг":                   {"ru": "одежда",             "en": "apparel"},
    "Ексклюзивні футболки, худі та лонгсліви. Бренд TwoComms — дизайн з характером.": {
        "ru": "Эксклюзивные футболки, худи и лонгсливы. Бренд TwoComms — дизайн с характером.",
        "en": "Exclusive t-shirts, hoodies and longsleeves. TwoComms — design with character.",
    },
    "Перейти в каталог":      {"ru": "Перейти в каталог",  "en": "Go to catalog"},
    "Ексклюзивний дизайн":    {"ru": "Эксклюзивный дизайн", "en": "Exclusive design"},

    # ===== Catalog page =====
    "Streetwear / Military-adjacent / Made in Ukraine": {
        "ru": "Streetwear / Military-adjacent / Made in Ukraine",
        "en": "Streetwear / Military-adjacent / Made in Ukraine",
    },
    "Пошук у каталозі":       {"ru": "Поиск в каталоге",   "en": "Search the catalog"},
    "одягу":                  {"ru": "одежды",             "en": "of apparel"},
    "Результати за запитом «%(q)s» у каталозі TwoComms.": {
        "ru": "Результаты по запросу «%(q)s» в каталоге TwoComms.",
        "en": "Results for «%(q)s» in the TwoComms catalog.",
    },
    "Обирайте футболки, худі та лонгсліви з авторськими принтами, українським виробництвом та швидкою доставкою по всій країні.": {
        "ru": "Выбирайте футболки, худи и лонгсливы с авторскими принтами, украинским производством и быстрой доставкой по всей стране.",
        "en": "Pick t-shirts, hoodies and longsleeves with original prints — Ukrainian production with fast country-wide delivery.",
    },
    "Переваги TwoComms":      {"ru": "Преимущества TwoComms", "en": "TwoComms advantages"},
    "Дизайни":                {"ru": "Дизайны",            "en": "Designs"},
    "власного виробництва":   {"ru": "собственного производства", "en": "in-house"},
    "Якість":                 {"ru": "Качество",           "en": "Quality"},
    "преміум матеріалів":     {"ru": "премиум материалов", "en": "premium materials"},
    "Доставка":               {"ru": "Доставка",           "en": "Delivery"},
    "по всій Україні":        {"ru": "по всей Украине",    "en": "Ukraine-wide"},
    "Створити свій дизайн":   {"ru": "Создать свой дизайн", "en": "Design your own"},
    "Створи свій":            {"ru": "Создай свой",        "en": "Make your"},
    "дизайн":                 {"ru": "дизайн",             "en": "design"},
    "Свій принт. Своя ідея.": {"ru": "Свой принт. Своя идея.", "en": "Your print. Your idea."},
    "Своє розташування.":     {"ru": "Своё расположение.", "en": "Your placement."},
    "Етапи створення принта": {"ru": "Этапы создания принта", "en": "Print design steps"},
    "Свій принт":             {"ru": "Свой принт",         "en": "Your print"},
    "Своя ідея":              {"ru": "Своя идея",          "en": "Your idea"},
    "Своє розташування":      {"ru": "Своё расположение",  "en": "Your placement"},
    "Приклад чорного худі TwoComms з власним принтом": {
        "ru": "Пример чёрного худи TwoComms с собственным принтом",
        "en": "Example of a black TwoComms hoodie with custom print",
    },
    "Зона друку":             {"ru": "Зона печати",        "en": "Print area"},
    "Створити свій принт":    {"ru": "Создать свой принт", "en": "Create your print"},
    "Від 1 одиниці • Швидке виготовлення": {
        "ru": "От 1 единицы • Быстрое изготовление",
        "en": "From 1 unit • Fast turnaround",
    },
    "Фільтр категорій":       {"ru": "Фильтр категорий",   "en": "Category filter"},
    "Усі товари":             {"ru": "Все товары",         "en": "All items"},
    "Усі категорії":          {"ru": "Все категории",      "en": "All categories"},
    "Категорії одягу TwoComms": {"ru": "Категории одежды TwoComms", "en": "TwoComms apparel categories"},
    "Опис категорії":         {"ru": "Описание категории", "en": "Category description"},
    "Результати пошуку":      {"ru": "Результаты поиска",  "en": "Search results"},
    "Товари категорії":       {"ru": "Товары категории",   "en": "Category products"},
    "Кольори:":               {"ru": "Цвета:",             "en": "Colors:"},
    "Немає товарів.":         {"ru": "Нет товаров.",       "en": "No products."},
    "Попередня":              {"ru": "Предыдущая",         "en": "Previous"},
    "Наступна":               {"ru": "Следующая",          "en": "Next"},
    "Додаткові розділи каталогу": {"ru": "Дополнительные разделы каталога", "en": "More catalog sections"},
    # blocktrans plurals
    "%(counter)s бал":        {"ru": "%(counter)s балл",   "en": "%(counter)s point"},
    "%(counter)s балів":      {"ru": "%(counter)s баллов", "en": "%(counter)s points"},
    "%(counter)s товар":      {"ru": "%(counter)s товар",  "en": "%(counter)s item"},
    "%(counter)s товарів":    {"ru": "%(counter)s товаров", "en": "%(counter)s items"},
    "%(counter)s товар знайдено": {"ru": "%(counter)s товар найден", "en": "%(counter)s item found"},
    "%(counter)s товарів знайдено": {"ru": "%(counter)s товаров найдено", "en": "%(counter)s items found"},

    # ===== Product detail page (PDP) =====
    "Галерея товару":         {"ru": "Галерея товара",     "en": "Product gallery"},
    "Дії з фото":             {"ru": "Действия с фото",    "en": "Photo actions"},
    "Збільшити фото":         {"ru": "Увеличить фото",     "en": "Zoom photo"},
    "Попереднє фото":         {"ru": "Предыдущее фото",    "en": "Previous photo"},
    "Наступне фото":          {"ru": "Следующее фото",     "en": "Next photo"},
    "Мініатюри товару":       {"ru": "Миниатюры товара",   "en": "Product thumbnails"},
    "Переваги покупки":       {"ru": "Преимущества покупки", "en": "Purchase benefits"},
    "Швидка відправка":       {"ru": "Быстрая отправка",   "en": "Fast shipping"},
    "1-2 дні по Україні":     {"ru": "1-2 дня по Украине", "en": "1-2 days in Ukraine"},
    "Індивідуальний підхід":  {"ru": "Индивидуальный подход", "en": "Personal approach"},
    "Допоможемо з вибором":   {"ru": "Поможем с выбором",  "en": "We help with the choice"},
    "Обмін розміру":          {"ru": "Обмен размера",      "en": "Size exchange"},
    "14 днів на обмін":       {"ru": "14 дней на обмен",   "en": "14 days for exchange"},
    "Індивідуальний позивний або бренд?": {
        "ru": "Индивидуальный позывной или бренд?",
        "en": "Custom call sign or brand?",
    },
    "Створимо принт з нуля під ваш позивний, логотип або ідею. Унікальна річ разом з TwoComms.": {
        "ru": "Создадим принт с нуля под ваш позывной, логотип или идею. Уникальная вещь вместе с TwoComms.",
        "en": "We'll design a print from scratch for your call sign, logo or idea. A unique piece with TwoComms.",
    },
    "Дії з товаром":          {"ru": "Действия с товаром", "en": "Product actions"},
    "Поділитися товаром":     {"ru": "Поделиться товаром", "en": "Share product"},
    "Особливості товару":     {"ru": "Особенности товара", "en": "Product features"},
    "Преміум тканина":        {"ru": "Премиум ткань",      "en": "Premium fabric"},
    "Лімітований дроп":       {"ru": "Лимитированный дроп", "en": "Limited drop"},
    "Розмір":                 {"ru": "Размер",             "en": "Size"},
    "Як обрати розмір?":      {"ru": "Как выбрать размер?", "en": "How to choose a size?"},
    "Розміри уточнюються менеджером після замовлення.": {
        "ru": "Размеры уточняются менеджером после заказа.",
        "en": "Sizes are confirmed by the manager after the order is placed.",
    },
    "Для цього товару доступний один колір.": {
        "ru": "Для этого товара доступен один цвет.",
        "en": "Only one color is available for this product.",
    },
    "Посадка":                {"ru": "Посадка",            "en": "Fit"},
    "Інформація про товар":   {"ru": "Информация о товаре", "en": "Product information"},
    "Опис":                   {"ru": "Описание",           "en": "Description"},
    "Розмірна сітка":         {"ru": "Размерная сетка",    "en": "Size guide"},
    "Догляд":                 {"ru": "Уход",               "en": "Care"},
    "FAQ товару":             {"ru": "FAQ товара",         "en": "Product FAQ"},
    # PDP plurals + dynamic strings
    "Рейтинг товару, %(counter)s відгук": {
        "ru": "Рейтинг товара, %(counter)s отзыв",
        "en": "Product rating, %(counter)s review",
    },
    "Рейтинг товару, %(counter)s відгуків": {
        "ru": "Рейтинг товара, %(counter)s отзывов",
        "en": "Product rating, %(counter)s reviews",
    },
    "%(counter)s відгук":     {"ru": "%(counter)s отзыв",  "en": "%(counter)s review"},
    "%(counter)s відгуків":   {"ru": "%(counter)s отзывов", "en": "%(counter)s reviews"},
    "Бонусні бали за покупку: %(n)s": {
        "ru": "Бонусные баллы за покупку: %(n)s",
        "en": "Bonus points for the purchase: %(n)s",
    },
}


_PO_ENTRY_RE = re.compile(
    r'(^msgid (?:"[^"]*"\s*)+\n)((?:msgstr (?:"[^"]*"\s*)+\n)+)',
    re.MULTILINE,
)


def _decode_po_string(block: str) -> str:
    """Concatenate consecutive ``"..."`` lines from a PO field block.

    PO files are UTF-8; we only need to translate backslash escapes
    (``\\n``, ``\\t``, ``\\"``, ``\\\\``). Using ``unicode_escape`` would
    corrupt non-ASCII bytes — handle escapes by hand instead.
    """
    parts = re.findall(r'"((?:[^"\\]|\\.)*)"', block)
    raw = "".join(parts)
    return (
        raw.replace("\\\\", "\x00")  # protect literal backslashes
        .replace('\\"', '"')
        .replace("\\n", "\n")
        .replace("\\t", "\t")
        .replace("\\r", "\r")
        .replace("\x00", "\\")
    )


def _encode_po_string(s: str) -> str:
    """Encode a string for a single-line PO value."""
    return s.replace("\\", "\\\\").replace('"', r"\"")


_BLOCK_RE = re.compile(
    r"((?:^#.*\n)*)(^msgid (?:\"[^\"]*\"\s*)+\n)((?:msgstr (?:\"[^\"]*\"\s*)+\n)+)",
    re.MULTILINE,
)


def patch_po(path: Path, lang: str) -> tuple[int, int]:
    """Fill empty / fuzzy msgstr for known msgids. Returns (filled, matched).

    Also strips ``#, fuzzy`` flags from blocks we override and removes
    the speculative ``#| msgid ...`` previous-msgid hints, since our
    explicit translation supersedes them.
    """
    text = path.read_text(encoding="utf-8")
    filled = 0
    seen = 0

    def repl(m: re.Match) -> str:
        nonlocal filled, seen
        comments = m.group(1)
        msgid_block = m.group(2)
        msgstr_block = m.group(3)
        msgid_val = _decode_po_string(msgid_block)
        msgstr_val = _decode_po_string(msgstr_block)
        entry = TRANSLATIONS.get(msgid_val)
        if not entry or not entry.get(lang):
            return m.group(0)
        seen += 1
        is_fuzzy = bool(re.search(r"^#, .*fuzzy", comments, re.MULTILINE))
        if msgstr_val.strip() and not is_fuzzy:
            return m.group(0)
        new_val = entry[lang]
        filled += 1
        # Remove fuzzy flag and previous-msgid speculation lines.
        cleaned_comments = []
        for line in comments.splitlines(keepends=True):
            if line.startswith("#|"):
                continue
            if line.startswith("#,") and "fuzzy" in line:
                stripped = re.sub(r",?\s*fuzzy", "", line)
                if stripped.strip() in ("#", "#,"):
                    continue
                cleaned_comments.append(stripped)
                continue
            cleaned_comments.append(line)
        return (
            "".join(cleaned_comments)
            + msgid_block
            + f'msgstr "{_encode_po_string(new_val)}"\n'
        )

    new_text = _BLOCK_RE.sub(repl, text)
    if new_text != text:
        path.write_text(new_text, encoding="utf-8")
    return filled, seen


def main() -> None:
    for lang in ("ru", "en"):
        po = LOCALE_DIR / lang / "LC_MESSAGES" / "django.po"
        if not po.exists():
            print(f"[skip] {po} not found")
            continue
        filled, seen = patch_po(po, lang)
        print(f"[{lang}] filled {filled} / matched {seen} / known {len(TRANSLATIONS)}")


if __name__ == "__main__":
    main()
