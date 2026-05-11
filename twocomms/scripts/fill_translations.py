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

    # ===== Mini cart / cart =====
    "Кастомний друк":         {"ru": "Кастомный принт",    "en": "Custom print"},
    "Видалити кастомну позицію": {"ru": "Удалить кастомную позицию", "en": "Remove custom item"},
    "Видалити":               {"ru": "Удалить",            "en": "Remove"},
    "Разом":                  {"ru": "Итого",              "en": "Total"},
    "Кастомні позиції очікують підтвердження менеджером. Фінальну ціну узгоджуєте в кошику.": {
        "ru": "Кастомные позиции ожидают подтверждения менеджером. Финальную цену согласуете в корзине.",
        "en": "Custom items await manager confirmation. The final price is agreed in the cart.",
    },
    "Оформити на сайті":      {"ru": "Оформить на сайте",  "en": "Checkout on site"},
    "Оформити через":         {"ru": "Оформить через",     "en": "Checkout via"},
    "Кошик порожній.":        {"ru": "Корзина пуста.",     "en": "Cart is empty."},

    # ===== Cart page =====
    "Кошик":                  {"ru": "Корзина",            "en": "Cart"},
    "Ваші вибрані товари":    {"ru": "Ваши выбранные товары", "en": "Your selected items"},
    "Очистити":               {"ru": "Очистить",           "en": "Clear"},
    "Кошик порожній":         {"ru": "Корзина пуста",      "en": "Cart is empty"},
    "Додайте товари до кошика, щоб зробити замовлення": {
        "ru": "Добавьте товары в корзину, чтобы оформить заказ",
        "en": "Add products to the cart to place an order",
    },
    "Перейти до покупок":     {"ru": "Перейти к покупкам", "en": "Continue shopping"},
    "Оформлення замовлення":  {"ru": "Оформление заказа",  "en": "Checkout"},
    "Підсумок вашого замовлення": {"ru": "Итог вашего заказа", "en": "Your order summary"},
    "Промокод":               {"ru": "Промокод",           "en": "Promo code"},
    "Застосовано":            {"ru": "Применён",           "en": "Applied"},
    "Знижка:":                {"ru": "Скидка:",            "en": "Discount:"},
    "Введіть код промокоду":  {"ru": "Введите код промокода", "en": "Enter promo code"},
    "Товари":                 {"ru": "Товары",             "en": "Items"},
    "До сплати:":             {"ru": "К оплате:",          "en": "Total to pay:"},
    "Залишок при отриманні:": {"ru": "Остаток при получении:", "en": "Remainder on delivery:"},
    "Знижка магазину":        {"ru": "Скидка магазина",    "en": "Store discount"},
    "Знижка промокоду":       {"ru": "Скидка по промокоду", "en": "Promo discount"},
    "Знижка від TwoComms":    {"ru": "Скидка от TwoComms", "en": "TwoComms discount"},
    "Разом ви економите":     {"ru": "Всего вы экономите", "en": "You save in total"},
    "Бали за замовлення":     {"ru": "Баллы за заказ",     "en": "Order points"},
    "буде нараховано після отримання товару": {
        "ru": "будут начислены после получения товара",
        "en": "will be credited after receipt",
    },
    "Бали не нараховуються":  {"ru": "Баллы не начисляются", "en": "No points awarded"},
    "Для отримання балів потрібно авторизуватися": {
        "ru": "Чтобы получать баллы, необходимо авторизоваться",
        "en": "Sign in to earn points",
    },
    "Авторизуватися":         {"ru": "Авторизоваться",     "en": "Sign in"},
    "Авторизація":            {"ru": "Авторизация",        "en": "Sign in"},
    "Доставка оплачується згідно тарифів перевізника.": {
        "ru": "Доставка оплачивается согласно тарифам перевозчика.",
        "en": "Delivery is paid according to the carrier's tariffs.",
    },
    "Зберегти зміни":         {"ru": "Сохранить изменения", "en": "Save changes"},
    "Потрібна консультація?": {"ru": "Нужна консультация?", "en": "Need a consultation?"},
    "Безкоштовна консультація": {"ru": "Бесплатная консультация", "en": "Free consultation"},
    "Закрити":                {"ru": "Закрыть",            "en": "Close"},
    "Залиште свої контактні дані, і наш менеджер звʼяжеться з вами найближчим часом для консультації": {
        "ru": "Оставьте свои контактные данные, и наш менеджер свяжется с вами в ближайшее время для консультации",
        "en": "Leave your contact details and our manager will reach out shortly for a consultation",
    },
    "Щоб не вводити дані кожного разу — авторизуйтесь і накопичуйте бали.": {
        "ru": "Чтобы не вводить данные каждый раз — авторизуйтесь и копите баллы.",
        "en": "Skip re-entering details next time — sign in and earn points.",
    },
    "ПІБ":                    {"ru": "ФИО",                "en": "Full name"},
    "Прізвище Імʼя По батькові": {"ru": "Фамилия Имя Отчество", "en": "Last First Middle name"},
    "Телефон":                {"ru": "Телефон",            "en": "Phone"},
    "0931234567":             {"ru": "0931234567",         "en": "+380931234567"},
    "Можна вводити 093..., 809..., 380... або +380... — номер приведемо до потрібного формату.": {
        "ru": "Можно вводить 093..., 809..., 380... или +380... — номер приведём к нужному формату.",
        "en": "You can enter 093..., 809..., 380... or +380... — we'll normalize the format.",
    },
    "Email":                  {"ru": "Email",              "en": "Email"},
    "your@email.com":         {"ru": "your@email.com",     "en": "your@email.com"},
    "Місто":                  {"ru": "Город",              "en": "City"},
    "Почніть вводити місто Нової пошти": {
        "ru": "Начните вводить город Новой почты",
        "en": "Start typing a Nova Poshta city",
    },
    "Почніть вводити назву міста і виберіть підтверджений варіант зі списку Нової пошти.": {
        "ru": "Начните вводить название города и выберите подтверждённый вариант из списка Новой почты.",
        "en": "Start typing the city name and pick a confirmed Nova Poshta option from the list.",
    },
    "Відділення / Поштомат НП": {"ru": "Отделение / Почтомат НП", "en": "NP branch / parcel locker"},
    "Оберіть відділення або поштомат": {
        "ru": "Выберите отделение или почтомат",
        "en": "Choose a branch or parcel locker",
    },
    "Усі пункти":             {"ru": "Все пункты",         "en": "All points"},
    "Відділення":             {"ru": "Отделение",          "en": "Branch"},
    "Поштомат":               {"ru": "Почтомат",           "en": "Parcel locker"},
    "Після вибору міста почніть вводити номер або адресу і виберіть відділення чи поштомат зі списку Нової пошти.": {
        "ru": "После выбора города начните вводить номер или адрес и выберите отделение или почтомат из списка Новой почты.",
        "en": "After choosing a city, start typing a number or address and pick a branch or parcel locker from the Nova Poshta list.",
    },
    "Тип оплати":             {"ru": "Тип оплаты",         "en": "Payment type"},
    "Оберіть тип оплати":     {"ru": "Выберите тип оплаты", "en": "Choose payment type"},
    "Онлайн оплата (повна сума)": {"ru": "Онлайн оплата (полная сумма)", "en": "Online payment (full amount)"},
    "Передплата 200 грн (решта при отриманні)": {
        "ru": "Предоплата 200 грн (остаток при получении)",
        "en": "Prepayment UAH 200 (remainder on delivery)",
    },
    "недоступно з кастомним принтом": {
        "ru": "недоступно с кастомным принтом",
        "en": "unavailable with custom print",
    },
    "У кошику є кастомний принт, тому передплата 200 грн тимчасово недоступна — менеджер узгодить фінальну ціну.": {
        "ru": "В корзине есть кастомный принт, поэтому предоплата 200 грн временно недоступна — менеджер согласует финальную цену.",
        "en": "There's a custom print in the cart, so the UAH 200 prepayment is temporarily unavailable — the manager will confirm the final price.",
    },
    "Це додаткова передоплата для вас — решту сплатите при отриманні.": {
        "ru": "Это дополнительная предоплата — остаток оплатите при получении.",
        "en": "This is an extra prepayment — pay the remainder on delivery.",
    },
    "Орієнтовно за кастомний друк": {"ru": "Ориентировочно за кастомный принт", "en": "Estimated for custom print"},
    "Менеджер погодив усі кастомні позиції. Тепер можна оплатити все замовлення разом.": {
        "ru": "Менеджер согласовал все кастомные позиции. Теперь можно оплатить весь заказ сразу.",
        "en": "The manager has approved all custom items. You can now pay for the entire order.",
    },
    "Кастомний одяг уже переданий менеджеру на перевірку. Поки триває модерація, позиція відображається в кошику окремо і <strong>не входить до суми оплати зараз</strong>. Щойно менеджер погодить деталі та фінальну ціну — кастом автоматично приєднається до рахунку.": {
        "ru": "Кастомная одежда уже передана менеджеру на проверку. Пока идёт модерация, позиция отображается в корзине отдельно и <strong>не входит в сумму оплаты сейчас</strong>. Как только менеджер согласует детали и финальную цену — кастом автоматически добавится к счёту.",
        "en": "The custom item has been sent to the manager for review. While moderation is in progress, the item is shown separately and <strong>not included in the current payment total</strong>. Once the manager approves the details and final price, the custom item will be added to the invoice automatically.",
    },
    "Написати менеджеру в Telegram": {"ru": "Написать менеджеру в Telegram", "en": "Message the manager on Telegram"},
    "Менеджер відхилив попередню заявку. Перегляньте деталі вище та надішліть її повторно, або ж оформіть замовлення <strong>без кастомних позицій</strong>.": {
        "ru": "Менеджер отклонил предыдущую заявку. Просмотрите детали выше и отправьте её повторно, либо оформите заказ <strong>без кастомных позиций</strong>.",
        "en": "The manager rejected the previous request. Review the details above and resubmit, or place the order <strong>without custom items</strong>.",
    },
    "Менеджер уже працює з вашим кастомним запитом. Коли модерацію буде завершено, позиція автоматично стане доступною для оплати в цьому ж кошику.": {
        "ru": "Менеджер уже работает с вашим кастомным запросом. Когда модерация завершится, позиция автоматически станет доступной для оплаты в этой же корзине.",
        "en": "The manager is already handling your custom request. Once moderation finishes, the item will automatically become available for payment in this cart.",
    },
    "Онлайн оплата карткою":  {"ru": "Онлайн оплата картой", "en": "Online card payment"},
    "(без урахування кастомного одягу)": {
        "ru": "(без учёта кастомной одежды)",
        "en": "(custom items not included)",
    },
    "Pay":                    {"ru": "Pay",                "en": "Pay"},
    "Оформити замовлення":    {"ru": "Оформить заказ",     "en": "Place order"},
    "Замовити як гість":      {"ru": "Заказать как гость", "en": "Order as guest"},
    "Оплата стане доступною після погодження менеджером. Зараз у кошику немає позицій, які можна оплатити окремо.": {
        "ru": "Оплата станет доступной после согласования менеджером. Сейчас в корзине нет позиций, которые можно оплатить отдельно.",
        "en": "Payment becomes available after manager approval. Currently there are no items in the cart that can be paid separately.",
    },
    "Оплата покриє лише звичайні товари. Кастомна позиція приєднається до замовлення автоматично після погодження менеджером — на ваш номер надійде додаткове повідомлення з фінальною ціною.": {
        "ru": "Оплата покроет только обычные товары. Кастомная позиция добавится к заказу автоматически после согласования менеджером — на ваш номер придёт дополнительное сообщение с финальной ценой.",
        "en": "Payment will cover only standard items. The custom item will be added to the order automatically after manager approval — you'll receive an additional message with the final price.",
    },
    "Після оформлення замовлення менеджер звʼяжеться з вами за вказаним номером телефону, щоб підтвердити деталі та узгодити доставку.": {
        "ru": "После оформления заказа менеджер свяжется с вами по указанному номеру телефона, чтобы подтвердить детали и согласовать доставку.",
        "en": "After placing the order, the manager will contact you at the phone number provided to confirm details and arrange delivery.",
    },
    "Заробите %(n)s балів":   {"ru": "Заработаете %(n)s баллов", "en": "Earn %(n)s points"},
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
