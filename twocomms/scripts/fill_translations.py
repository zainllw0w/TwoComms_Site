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

    # ===== Accounts =====
    "Вхід":                   {"ru": "Вход",               "en": "Sign in"},
    "Вхід до акаунту":        {"ru": "Вход в аккаунт",     "en": "Sign in to account"},
    "Швидкий доступ до замовлень, балів та обраного": {
        "ru": "Быстрый доступ к заказам, баллам и избранному",
        "en": "Quick access to orders, points and favorites",
    },
    "Вхід через Google - TwoComms": {"ru": "Вход через Google - TwoComms", "en": "Sign in via Google - TwoComms"},
    "Увійти через Google":    {"ru": "Войти через Google", "en": "Continue with Google"},
    "Продовжуючи, ви погоджуєтесь з умовами використання": {
        "ru": "Продолжая, вы соглашаетесь с условиями использования",
        "en": "By continuing, you agree to the terms of use",
    },
    "Логін":                  {"ru": "Логин",              "en": "Login"},
    "Використовуйте свій нікнейм. Реєстрація — за хвилину.": {
        "ru": "Используйте свой никнейм. Регистрация — за минуту.",
        "en": "Use your nickname. Registration takes a minute.",
    },
    "Пароль":                 {"ru": "Пароль",             "en": "Password"},
    "Показати пароль":        {"ru": "Показать пароль",    "en": "Show password"},
    "Увійти":                 {"ru": "Войти",              "en": "Sign in"},
    "Немає облікового запису?": {"ru": "Нет аккаунта?",    "en": "No account yet?"},
    "Зареєструватись":        {"ru": "Зарегистрироваться", "en": "Sign up"},
    "Реєстрація":             {"ru": "Регистрация",        "en": "Sign up"},
    "Створення акаунту":      {"ru": "Создание аккаунта",  "en": "Create account"},
    "Отримуйте бонуси, спостерігайте за замовленнями та обраним": {
        "ru": "Получайте бонусы, следите за заказами и избранным",
        "en": "Earn bonuses, track your orders and favorites",
    },
    "Продовжити через Google": {"ru": "Продолжить через Google", "en": "Continue with Google"},
    "Ми створимо акаунт на основі вашого Google профілю": {
        "ru": "Мы создадим аккаунт на основе вашего Google-профиля",
        "en": "We'll create an account based on your Google profile",
    },
    "Мін. 3 символи, латиниця/цифри/._-": {
        "ru": "Мин. 3 символа, латиница/цифры/._-",
        "en": "Min. 3 characters, Latin letters/digits/._-",
    },
    "8+ символів, бажано букви велики/малі та цифри": {
        "ru": "8+ символов, желательно большие/маленькие буквы и цифры",
        "en": "8+ characters, ideally mixed case and digits",
    },
    "Складність паролю":      {"ru": "Сложность пароля",   "en": "Password strength"},
    "Повтор паролю":          {"ru": "Повтор пароля",      "en": "Repeat password"},
    "Створити акаунт":        {"ru": "Создать аккаунт",    "en": "Create account"},
    "Вже маєте акаунт?":      {"ru": "Уже есть аккаунт?",  "en": "Already have an account?"},

    # favorites
    "Обрані товари":          {"ru": "Избранные товары",   "en": "Favorite items"},
    "Перейти в каталог":      {"ru": "Перейти в каталог",  "en": "Go to catalog"},
    "Кольори:":               {"ru": "Цвета:",             "en": "Colors:"},
    "Увага!":                 {"ru": "Внимание!",          "en": "Notice!"},
    "Ви переглядаєте обрані товари як гість.": {
        "ru": "Вы просматриваете избранные товары как гость.",
        "en": "You're viewing favorites as a guest.",
    },
    "Увійдіть в акаунт":      {"ru": "Войдите в аккаунт",  "en": "Sign in"},
    "або":                    {"ru": "или",                "en": "or"},
    "зареєструйтесь":         {"ru": "зарегистрируйтесь",  "en": "sign up"},
    "щоб зберегти обрані товари назавжди.": {
        "ru": "чтобы сохранить избранные товары навсегда.",
        "en": "to save your favorites permanently.",
    },
    "У вас поки немає обраних товарів": {
        "ru": "У вас пока нет избранных товаров",
        "en": "You don't have any favorites yet",
    },
    "Додавайте товари до обраного, натискаючи на сердечко на карточці товару": {
        "ru": "Добавляйте товары в избранное, нажимая на сердечко на карточке товара",
        "en": "Add items to favorites by clicking the heart on a product card",
    },

    # my_orders
    "Мої замовлення":         {"ru": "Мои заказы",         "en": "My orders"},
    "Відстежуйте статус ваших замовлень": {
        "ru": "Отслеживайте статус своих заказов",
        "en": "Track the status of your orders",
    },

    # my_reviews
    "Мої відгуки":            {"ru": "Мои отзывы",         "en": "My reviews"},
    "Усі ваші відгуки про куплені товари TwoComms.": {
        "ru": "Все ваши отзывы о купленных товарах TwoComms.",
        "en": "All your reviews of TwoComms products you've purchased.",
    },
    "Статистика відгуків":    {"ru": "Статистика отзывов", "en": "Reviews statistics"},
    "Опубліковано":           {"ru": "Опубликовано",       "en": "Published"},
    "На модерації":           {"ru": "На модерации",       "en": "Pending"},
    "Відхилено":              {"ru": "Отклонено",          "en": "Rejected"},
    "Відгук про %(t)s":       {"ru": "Отзыв о %(t)s",      "en": "Review of %(t)s"},
    "Оцінка %(n)s з 5":       {"ru": "Оценка %(n)s из 5",  "en": "Rating %(n)s out of 5"},
    "Фото відгуку %(n)s про %(t)s": {
        "ru": "Фото отзыва %(n)s о %(t)s",
        "en": "Review photo %(n)s of %(t)s",
    },
    "Причина відхилення:":    {"ru": "Причина отклонения:", "en": "Rejection reason:"},
    "Ви ще не залишили жодного відгуку.": {
        "ru": "Вы ещё не оставили ни одного отзыва.",
        "en": "You haven't left any reviews yet.",
    },
    "Перейти до моїх замовлень": {"ru": "Перейти к моим заказам", "en": "Go to my orders"},
    "та поділіться враженнями про придбані товари.": {
        "ru": "и поделитесь впечатлениями о купленных товарах.",
        "en": "and share your impressions of the purchased items.",
    },

    # support_content (footer)
    "Streetwear / Military-adjacent / Made in Ukraine": {
        "ru": "Стритвир / Military-adjacent / сделано в Украине",
        "en": "Streetwear / Military-adjacent / Made in Ukraine",
    },
    "All Rights Reserved © TWOCOMMS, 2026": {
        "ru": "Все права защищены © TWOCOMMS, 2026",
        "en": "All Rights Reserved © TWOCOMMS, 2026",
    },
    "Швидкий доступ":         {"ru": "Быстрый доступ",     "en": "Quick access"},
    "Доставка і оплата":      {"ru": "Доставка и оплата",  "en": "Delivery & payment"},
    "Кастомний принт":        {"ru": "Кастомный принт",    "en": "Custom print"},
    "Догляд за одягом":       {"ru": "Уход за одеждой",    "en": "Garment care"},
    "Розмірна сітка":         {"ru": "Размерная сетка",    "en": "Size guide"},
    "Відстеження замовлення": {"ru": "Отслеживание заказа","en": "Order tracking"},
    "Політика конфіденційності": {"ru": "Политика конфиденциальности", "en": "Privacy Policy"},
    "Умови використання":     {"ru": "Условия использования", "en": "Terms of Service"},

    # profile_setup
    "Профіль":                {"ru": "Профиль",            "en": "Profile"},
    "Налаштування профілю":   {"ru": "Настройки профиля",  "en": "Profile settings"},
    "Заповніть інформацію для зручного замовлення": {
        "ru": "Заполните информацию для удобного оформления заказа",
        "en": "Fill in your details for a smooth checkout",
    },

    # ===== order_failed / order_success (Phase 17d.8) =====
    "Оплату не завершено": {"ru": "Оплата не завершена", "en": "Payment not completed"},
    "Платіж не пройшов. Спробуйте ще раз або оберіть інший спосіб оплати.": {
        "ru": "Платёж не прошёл. Попробуйте ещё раз или выберите другой способ оплаты.",
        "en": "The payment did not go through. Try again or choose another payment method.",
    },
    "Повернутися в кошик": {"ru": "Вернуться в корзину", "en": "Back to cart"},
    "На головну": {"ru": "На главную", "en": "Back to home"},

    "Замовлення оформлено": {"ru": "Заказ оформлен", "en": "Order placed"},
    "Замовлення успішно оформлено!": {"ru": "Заказ успешно оформлен!", "en": "Order placed successfully!"},
    "Номер замовлення:": {"ru": "Номер заказа:", "en": "Order number:"},
    "Переглянути деталі замовлення": {"ru": "Посмотреть детали заказа", "en": "View order details"},
    "Оплата успішно пройшла!": {"ru": "Оплата прошла успешно!", "en": "Payment completed successfully!"},
    "Дякуємо, брат! Твоє замовлення оплачено та відправлено в обробку. Ми розпочнемо підготовку найближчим часом.": {
        "ru": "Спасибо, брат! Твой заказ оплачен и отправлен в обработку. Мы начнём подготовку в ближайшее время.",
        "en": "Thanks, brother! Your order is paid and is being processed. We'll start preparing it shortly.",
    },
    "Дякуємо за покупку! Твоє замовлення оплачено через Monobank та відправлено в обробку. Ми розпочнемо підготовку найближчим часом.": {
        "ru": "Спасибо за покупку! Ваш заказ оплачен через Monobank и отправлен в обработку. Мы начнём подготовку в ближайшее время.",
        "en": "Thanks for your purchase! Your order is paid via Monobank and is being processed. We'll start preparing it shortly.",
    },
    "Передплата внесена!": {"ru": "Предоплата внесена!", "en": "Prepayment received!"},
    "Дякуємо, брат! Передплата внесена. Залишок оплатиш при отриманні на Новій Пошті. Ми розпочнемо підготовку та відправимо на вказане відділення.": {
        "ru": "Спасибо, брат! Предоплата внесена. Остаток оплатишь при получении в Новой Почте. Мы начнём подготовку и отправим на указанное отделение.",
        "en": "Thanks, brother! Prepayment received. You'll pay the remainder on pickup at Nova Poshta. We'll start preparing and ship to the chosen branch.",
    },
    "Дякуємо за покупку! Передплата внесена. Залишок необхідно оплатити при отриманні посилки на відділенні Нової Пошти. Ми розпочнемо підготовку та відправимо на вказане відділення.": {
        "ru": "Спасибо за покупку! Предоплата внесена. Остаток необходимо оплатить при получении посылки в отделении Новой Почты. Мы начнём подготовку и отправим на указанное отделение.",
        "en": "Thanks for your purchase! Prepayment received. The remainder is payable on pickup at the Nova Poshta branch. We'll start preparing and ship to the chosen branch.",
    },
    "Ваша заявка відправлена в обробку": {"ru": "Ваша заявка отправлена в обработку", "en": "Your request has been submitted"},
    "Дякуємо, брат! Замовлення відправлено в обробку. Статус надійде в Telegram.": {
        "ru": "Спасибо, брат! Заказ отправлен в обработку. Статус придёт в Telegram.",
        "en": "Thanks, brother! The order is in processing. You'll get status updates in Telegram.",
    },
    "Дякуємо за замовлення! Заявка відправлена в обробку.": {
        "ru": "Спасибо за заказ! Заявка отправлена в обработку.",
        "en": "Thanks for your order! The request has been submitted.",
    },
    "Внесена передплата:": {"ru": "Внесённая предоплата:", "en": "Prepayment made:"},
    "грн": {"ru": "грн", "en": "UAH"},
    "Залишок (при отриманні):": {"ru": "Остаток (при получении):", "en": "Remainder (on pickup):"},
    "Дякуємо за вибір стилю TwoComms!": {"ru": "Спасибо за выбор стиля TwoComms!", "en": "Thanks for choosing TwoComms style!"},
    "Твій стиль — твоя сильна сторона. Ми цінуємо, що ти обрав саме нас для свого образу.": {
        "ru": "Твой стиль — твоя сильная сторона. Мы ценим, что ты выбрал именно нас для своего образа.",
        "en": "Your style is your strength. We appreciate you choosing us for your look.",
    },
    "Є питання чи потрібна допомога?": {"ru": "Есть вопросы или нужна помощь?", "en": "Have questions or need help?"},
    "Написати в Telegram": {"ru": "Написать в Telegram", "en": "Message us on Telegram"},
    "Демо режим": {"ru": "Демо режим", "en": "Demo mode"},
    "Це тестовий перегляд сторінки. Для реального замовлення дані будуть заповнені автоматично.": {
        "ru": "Это тестовый просмотр страницы. Для реального заказа данные заполнятся автоматически.",
        "en": "This is a preview page. Real order data will be filled in automatically.",
    },
    "Деталі замовлення": {"ru": "Детали заказа", "en": "Order details"},
    "Деталі замовлення (демо)": {"ru": "Детали заказа (демо)", "en": "Order details (demo)"},
    "ПІБ": {"ru": "ФИО", "en": "Full name"},
    "Телефон": {"ru": "Телефон", "en": "Phone"},
    "Місто": {"ru": "Город", "en": "City"},
    "Відділення НП": {"ru": "Отделение НП", "en": "Nova Poshta branch"},
    "Не вказано": {"ru": "Не указано", "en": "Not provided"},
    "Тип оплати": {"ru": "Тип оплаты", "en": "Payment type"},
    "Передплата 200 грн": {"ru": "Предоплата 200 грн", "en": "Prepayment 200 UAH"},
    "Онлайн оплата (повна сума)": {"ru": "Онлайн оплата (полная сумма)", "en": "Online payment (full amount)"},
    "Оплата при отриманні": {"ru": "Оплата при получении", "en": "Cash on delivery"},
    "Сума замовлення": {"ru": "Сумма заказа", "en": "Order total"},
    "Товари в замовленні:": {"ru": "Товары в заказе:", "en": "Items in order:"},
    "Розмір:": {"ru": "Размер:", "en": "Size:"},
    "Посадка:": {"ru": "Посадка:", "en": "Fit:"},
    "Колір:": {"ru": "Цвет:", "en": "Colour:"},
    "Кількість:": {"ru": "Количество:", "en": "Quantity:"},
    "Тип:": {"ru": "Тип:", "en": "Type:"},
    "Статус: погоджено": {"ru": "Статус: согласовано", "en": "Status: approved"},
    "Система балів": {"ru": "Система баллов", "en": "Points programme"},
    "Дякуємо, брат! Твоє замовлення оформлено. Бали будуть нараховані після отримання товару.": {
        "ru": "Спасибо, брат! Заказ оформлен. Баллы будут начислены после получения товара.",
        "en": "Thanks, brother! The order is placed. Points will be credited after you receive the item.",
    },
    "Статус замовлення приходить в Telegram": {
        "ru": "Статус заказа приходит в Telegram",
        "en": "Order status is sent to Telegram",
    },
    "Оновлення про твоє замовлення надсилаються автоматично": {
        "ru": "Обновления по твоему заказу отправляются автоматически",
        "en": "Updates about your order are sent automatically",
    },
    "Мої замовлення": {"ru": "Мои заказы", "en": "My orders"},
    "Створіть акаунт або увійдіть в систему, щоб отримувати бали за покупки!": {
        "ru": "Создайте аккаунт или войдите в систему, чтобы получать баллы за покупки!",
        "en": "Create an account or log in to earn points on your purchases!",
    },
    "Накопичувати бали за покупки": {"ru": "Копить баллы за покупки", "en": "Earn points on purchases"},
    "Відстежувати статус замовлень": {"ru": "Отслеживать статус заказов", "en": "Track order statuses"},
    "Зберігати історію покупок": {"ru": "Хранить историю покупок", "en": "Keep purchase history"},
    "Отримувати персональні пропозиції": {"ru": "Получать персональные предложения", "en": "Receive personal offers"},
    "Увійти": {"ru": "Войти", "en": "Sign in"},
    "Зареєструватись": {"ru": "Зарегистрироваться", "en": "Sign up"},
    "Якщо ви зареєструєтесь, це замовлення автоматично привʼяжеться до вашого акаунту": {
        "ru": "Если вы зарегистрируетесь, этот заказ автоматически привяжется к вашему аккаунту",
        "en": "If you register, this order will automatically be linked to your account",
    },
    "Отримати чек на email": {"ru": "Получить чек на email", "en": "Get the receipt by email"},
    "Введіть вашу email адресу, і ми надішлемо чек про оплату": {
        "ru": "Введите ваш email, и мы пришлём чек об оплате",
        "en": "Enter your email and we'll send you the payment receipt",
    },
    "Відправити чек": {"ru": "Отправить чек", "en": "Send receipt"},
    "Залиште відгук в Instagram": {"ru": "Оставьте отзыв в Instagram", "en": "Leave a review on Instagram"},
    "Поділіться своїми враженнями про покупку! Залиште відгук в Instagram з відміткою нашої сторінки, і ми даруємо вам промокод на знижку 10% на наступне замовлення!": {
        "ru": "Поделитесь впечатлениями о покупке! Оставьте отзыв в Instagram с отметкой нашей страницы — и мы подарим вам промокод на 10% скидку на следующий заказ!",
        "en": "Share your purchase experience! Leave a review on Instagram tagging our page and we'll gift you a 10% discount code for your next order!",
    },
    "Ваш промокод на знижку": {"ru": "Ваш промокод на скидку", "en": "Your discount code"},
    "10% знижка на наступне замовлення": {"ru": "10% скидка на следующий заказ", "en": "10% off your next order"},
    "Відкрити Instagram": {"ru": "Открыть Instagram", "en": "Open Instagram"},
    "Повернутись на головну": {"ru": "Вернуться на главную", "en": "Back to home"},
    "Переглянути каталог": {"ru": "Посмотреть каталог", "en": "Browse catalog"},
    "Будь ласка, введіть коректну email адресу": {"ru": "Пожалуйста, введите корректный email адрес", "en": "Please enter a valid email address"},
    "Відправляється...": {"ru": "Отправляется...", "en": "Sending..."},
    "Чек буде відправлено на": {"ru": "Чек будет отправлен на", "en": "Receipt will be sent to"},
    "Функціонал буде додано найближчим часом.": {"ru": "Функционал будет добавлен в ближайшее время.", "en": "This feature will be added shortly."},

    # ===== Phase 17g — home page survey card =====
    "Бонус за фідбек":            {"ru": "Бонус за фидбэк",                 "en": "Feedback bonus"},
    "грн":                          {"ru": "грн",                              "en": "UAH"},
    "Промокод активується автоматично одразу після проходження та діє на весь асортимент.": {
        "ru": "Промокод активируется автоматически сразу после прохождения и действует на весь ассортимент.",
        "en": "The promo code is activated automatically right after completion and applies to the entire range.",
    },
    "≈ 5 хвилин часу":             {"ru": "≈ 5 минут времени",                "en": "≈ 5 minutes"},
    "Один раз на рік":             {"ru": "Один раз в год",                   "en": "Once a year"},
    "Можна повернутись потім":     {"ru": "Можно вернуться позже",            "en": "Can return later"},
    "Допоможи покращити":          {"ru": "Помоги улучшить",                  "en": "Help us improve"},
    "Коротке опитування без довгої анкети: відповіді допоможуть нам стати кращими.": {
        "ru": "Короткий опрос без длинной анкеты: ответы помогут нам стать лучше.",
        "en": "A short survey — no lengthy form. Your answers help us improve.",
    },
    "БІЛЬШЕ НЕ ПОКАЗУВАТИ":         {"ru": "БОЛЬШЕ НЕ ПОКАЗЫВАТЬ",             "en": "DO NOT SHOW AGAIN"},
    "ВИГРАЙ %(amount)s ГРН":        {"ru": "ВЫИГРАЙ %(amount)s ГРН",           "en": "WIN %(amount)s UAH"},
    "ЗА ОПИТУВАННЯ!":              {"ru": "ЗА ОПРОС!",                        "en": "FOR THE SURVEY!"},
    "Дай відповідь на кілька запитань та забери свій промокод!": {
        "ru": "Ответь на несколько вопросов и забери свой промокод!",
        "en": "Answer a few questions and grab your promo code!",
    },
    "Без форми на одну сторінку":  {"ru": "Без формы на одну страницу",       "en": "No single-page form"},
    "Лише для зареєстрованих користувачів": {
        "ru": "Только для зарегистрированных пользователей",
        "en": "Registered users only",
    },
    "Пройти опитування":           {"ru": "Пройти опрос",                     "en": "Take the survey"},
    "Продовжити опитування":       {"ru": "Продолжить опрос",                 "en": "Continue the survey"},
    "Опитування":                  {"ru": "Опрос",                            "en": "Survey"},
    "Коротке опитування про TWOCOMMS": {
        "ru": "Короткий опрос о TWOCOMMS",
        "en": "Short survey about TWOCOMMS",
    },
    "Твої відповіді допоможуть покращити сайт і колекції. Орієнтовно 5 хвилин.": {
        "ru": "Твои ответы помогут улучшить сайт и коллекции. Примерно 5 минут.",
        "en": "Your answers will help improve the site and collections. Around 5 minutes.",
    },
    "Ми використовуємо відповіді лише для аналітики та покращення сервісу. Контактні дані — лише за твоєю згодою.": {
        "ru": "Мы используем ответы только для аналитики и улучшения сервиса. Контактные данные — только с твоего согласия.",
        "en": "We use answers solely for analytics and service improvement. Contact details — only with your consent.",
    },
    "Завантаження…":               {"ru": "Загрузка…",                        "en": "Loading…"},
    "Далі":                         {"ru": "Далее",                            "en": "Next"},
    "Повернутись на 1 крок":       {"ru": "Вернуться на 1 шаг",               "en": "Back one step"},
    "Закрити":                     {"ru": "Закрыть",                          "en": "Close"},
    "Пропустити":                  {"ru": "Пропустить",                       "en": "Skip"},
    "Дякуємо!":                    {"ru": "Спасибо!",                         "en": "Thank you!"},
    "Твій промокод готовий.":      {"ru": "Твой промокод готов.",             "en": "Your promo code is ready."},
    "Скопіювати код":              {"ru": "Скопировать код",                  "en": "Copy code"},

    # ===== Phase 17g — home categories + custom-design CTA =====
    "Категорії":                   {"ru": "Категории",                        "en": "Categories"},
    "Перейти в каталог":           {"ru": "Перейти в каталог",                "en": "Go to catalog"},
    "Згорнути/розгорнути категорії": {"ru": "Свернуть/развернуть категории",  "en": "Collapse/expand categories"},
    "Згорнути":                    {"ru": "Свернуть",                         "en": "Collapse"},
    "Весь каталог":                {"ru": "Весь каталог",                     "en": "Full catalog"},
    "Замовити кастомний одяг":     {"ru": "Заказать кастомную одежду",        "en": "Order custom apparel"},
    "Свій дизайн":                 {"ru": "Свой дизайн",                      "en": "Your design"},
    "Збери одяг під себе":         {"ru": "Собери одежду под себя",           "en": "Build your own apparel"},
    "Обери основу, свій принт, матеріали й деталі — вартість побачиш одразу.": {
        "ru": "Выбери основу, свой принт, материалы и детали — стоимость увидишь сразу.",
        "en": "Pick the base, your print, materials and details — see the price instantly.",
    },
    "Спробувати конструктор":      {"ru": "Попробовать конструктор",          "en": "Try the builder"},
    "Потрібна допомога? Менеджер підкаже.": {
        "ru": "Нужна помощь? Менеджер подскажет.",
        "en": "Need help? Our manager will assist you.",
    },

    # ===== Phase 17g — home color filter + new products =====
    "Перейти до каталогу за кольором": {
        "ru": "Перейти к каталогу по цвету",
        "en": "Browse catalog by colour",
    },
    "Обери за кольором":           {"ru": "Выбери по цвету",                  "en": "Choose by colour"},
    "Усі кольори":                 {"ru": "Все цвета",                        "en": "All colours"},
    "Новинки":                     {"ru": "Новинки",                          "en": "New arrivals"},
    "Немає товарів.":              {"ru": "Нет товаров.",                     "en": "No products."},
    "Показати ще":                 {"ru": "Показать ещё",                     "en": "Show more"},
    "Завантаження...":             {"ru": "Загрузка...",                      "en": "Loading..."},
    "Наступна сторінка":           {"ru": "Следующая страница",               "en": "Next page"},

    # ===== Phase 17g — product detail recommendations =====
    "Схожі товари":                {"ru": "Похожие товары",                   "en": "Related products"},
    "Переглянути всі":             {"ru": "Смотреть все",                     "en": "View all"},
    "Рекомендовані товари":        {"ru": "Рекомендуемые товары",             "en": "Recommended products"},

    # ===== Phase 17g — catalog general SEO H2 block =====
    "Купити одяг з принтом онлайн в Україні — доставка Києвом, Харковом, Львовом": {
        "ru": "Купить одежду с принтом онлайн в Украине — доставка по Киеву, Харькову, Львову",
        "en": "Buy printed apparel online in Ukraine — delivery to Kyiv, Kharkiv, Lviv",
    },
    "<strong>Купити одяг з принтом</strong> у TwoComms можна онлайн із доставкою у будь-яке місто України: <strong>Київ, Харків, Львів, Дніпро, Одеса, Запоріжжя, Вінниця, Полтава, Чернівці, Івано-Франківськ, Тернопіль, Луцьк, Хмельницький, Ужгород, Чернігів</strong>. У каталозі — <a href=\"/catalog/tshirts/\">футболки</a>, <a href=\"/catalog/hoodie/\">худі</a> та <a href=\"/catalog/long-sleeve/\">лонгсліви</a> з авторськими принтами ЗСУ та streetwear-графікою. Доставка Новою Поштою 1–2 дні, безкоштовний обмін розміру протягом 14 днів.": {
        "ru": "<strong>Купить одежду с принтом</strong> в TwoComms можно онлайн с доставкой в любой город Украины: <strong>Киев, Харьков, Львов, Днепр, Одесса, Запорожье, Винница, Полтава, Черновцы, Ивано-Франковск, Тернополь, Луцк, Хмельницкий, Ужгород, Чернигов</strong>. В каталоге — <a href=\"/catalog/tshirts/\">футболки</a>, <a href=\"/catalog/hoodie/\">худи</a> и <a href=\"/catalog/long-sleeve/\">лонгсливы</a> с авторскими принтами ВСУ и streetwear-графикой. Доставка Новой Почтой 1–2 дня, бесплатный обмен размера в течение 14 дней.",
        "en": "<strong>Buy printed apparel</strong> at TwoComms online with delivery to any city in Ukraine: <strong>Kyiv, Kharkiv, Lviv, Dnipro, Odesa, Zaporizhzhia, Vinnytsia, Poltava, Chernivtsi, Ivano-Frankivsk, Ternopil, Lutsk, Khmelnytskyi, Uzhhorod, Chernihiv</strong>. The catalog features <a href=\"/catalog/tshirts/\">t-shirts</a>, <a href=\"/catalog/hoodie/\">hoodies</a> and <a href=\"/catalog/long-sleeve/\">longsleeves</a> with original Armed Forces and streetwear artwork. Nova Poshta delivery in 1–2 days, free size exchange within 14 days.",
    },
    "Замовити чоловічий або жіночий streetwear від українського бренду TwoComms": {
        "ru": "Заказать мужской или женский streetwear от украинского бренда TwoComms",
        "en": "Order men's or women's streetwear from the Ukrainian brand TwoComms",
    },
    "<strong>Замовити streetwear-одяг</strong> онлайн — це спосіб підтримати українське виробництво. Усі футболки, худі та лонгсліви TwoComms шиємо в Україні з преміум-бавовни та трикотажу щільністю 200–320 г/м². У каталозі є чоловічі моделі прямого крою, жіночі фасони зі звуженою посадкою та унісекс-варіанти у розмірах XS–XXL. Принти виконуємо в техніці DTF — стійкі до 30+ циклів прання.": {
        "ru": "<strong>Заказать streetwear-одежду</strong> онлайн — это способ поддержать украинское производство. Все футболки, худи и лонгсливы TwoComms мы шьём в Украине из премиум-хлопка и трикотажа плотностью 200–320 г/м². В каталоге есть мужские модели прямого кроя, женские фасоны с приталенной посадкой и унисекс-варианты в размерах XS–XXL. Принты выполняем по технологии DTF — устойчивы к 30+ циклам стирки.",
        "en": "<strong>Order streetwear apparel</strong> online — your way to support Ukrainian production. All TwoComms t-shirts, hoodies and longsleeves are made in Ukraine from premium cotton and 200–320 g/m² jersey. The catalog includes straight-cut men's models, fitted women's silhouettes and unisex options in sizes XS–XXL. Prints are produced using DTF technology — they survive 30+ wash cycles.",
    },
    "Український патріотичний streetwear — авторські принти ЗСУ та колаборації": {
        "ru": "Украинский патриотический streetwear — авторские принты ВСУ и коллаборации",
        "en": "Ukrainian patriotic streetwear — original Armed Forces prints and collaborations",
    },
    "<strong>TwoComms</strong> — український streetwear-бренд із мілітарним ДНК. Створюємо одяг для тих, хто живе в Україні, підтримує ЗСУ та цінує спокійну, але сильну естетику. У каталозі — колаборації з військовими підрозділами, авторські ілюстрації на тему Збройних Сил України, тризуба й сучасної української поп-культури. Частину прибутку від кожного замовлення направляємо на потреби ЗСУ. Дізнайтеся більше про <a href=\"/pro-brand/\">філософію бренду</a> або обирайте <a href=\"/custom-print/\">кастомний друк</a> власного принта на обраній моделі.": {
        "ru": "<strong>TwoComms</strong> — украинский streetwear-бренд с милитари-ДНК. Создаём одежду для тех, кто живёт в Украине, поддерживает ВСУ и ценит спокойную, но сильную эстетику. В каталоге — коллаборации с военными подразделениями, авторские иллюстрации на тему Вооружённых Сил Украины, тризуба и современной украинской поп-культуры. Часть прибыли с каждого заказа направляем на нужды ВСУ. Узнайте больше о <a href=\"/pro-brand/\">философии бренда</a> или выбирайте <a href=\"/custom-print/\">кастомную печать</a> собственного принта на выбранной модели.",
        "en": "<strong>TwoComms</strong> is a Ukrainian streetwear brand with military DNA. We make apparel for people who live in Ukraine, support the Armed Forces and value calm yet powerful aesthetics. The catalog includes collaborations with military units, original illustrations dedicated to the Armed Forces of Ukraine, the trident and contemporary Ukrainian pop culture. We donate a share of every order to the Armed Forces. Learn more about <a href=\"/pro-brand/\">our brand philosophy</a> or choose <a href=\"/custom-print/\">custom printing</a> of your own artwork on a selected model.",
    },

    # ===== Phase 17g — general catalog SEO panel (color_seo_copy.py) =====
    "Каталог одягу TwoComms — український стрітвір з характером": {
        "ru": "Каталог одежды TwoComms — украинский стритвир с характером",
        "en": "TwoComms apparel catalog — Ukrainian streetwear with character",
    },
    "TwoComms — це український бренд одягу, який створює стрітвір у трьох ключових категоріях: <a href=\"/catalog/hoodie/\">худі</a>, <a href=\"/catalog/tshirts/\">футболки</a> й <a href=\"/catalog/long-sleeve/\">лонгсліви</a>. Усі моделі ми розробляємо в Україні, друкуємо принти на власному обладнанні за технологією DTF і підбираємо тканини так, щоб одяг витримував щоденне носіння, прання й любий клімат — від літньої спеки до сирої осені.": {
        "ru": "TwoComms — это украинский бренд одежды, который создаёт стритвир в трёх ключевых категориях: <a href=\"/catalog/hoodie/\">худи</a>, <a href=\"/catalog/tshirts/\">футболки</a> и <a href=\"/catalog/long-sleeve/\">лонгсливы</a>. Все модели мы разрабатываем в Украине, печатаем принты на собственном оборудовании по технологии DTF и подбираем ткани так, чтобы одежда выдерживала ежедневную носку, стирку и любой климат — от летней жары до сырой осени.",
        "en": "TwoComms is a Ukrainian apparel brand creating streetwear in three core categories: <a href=\"/catalog/hoodie/\">hoodies</a>, <a href=\"/catalog/tshirts/\">t-shirts</a> and <a href=\"/catalog/long-sleeve/\">longsleeves</a>. Every model is designed in Ukraine, printed on our own DTF equipment, and made from fabrics chosen to withstand daily wear, laundering and any climate — from summer heat to damp autumn.",
    },
    "Кожен товар у каталозі доступний у кількох кольорах: класичний <a href=\"/catalog/?color=black\">чорний</a> для тих, хто шукає універсальну базу під будь-який принт; <a href=\"/catalog/?color=coyote\">кайот</a> і <a href=\"/catalog/?color=olive\">олива</a> для прихильників мілітарної естетики; нейтральний <a href=\"/catalog/?color=grey\">сірий</a> і чистий <a href=\"/catalog/?color=white\">білий</a> для весняно-літніх образів. Усі кольори перевіряються на стійкість до УФ та перфектне зберігання форми навіть після 30+ циклів прання.": {
        "ru": "Каждый товар в каталоге доступен в нескольких цветах: классический <a href=\"/catalog/?color=black\">чёрный</a> для тех, кто ищет универсальную базу под любой принт; <a href=\"/catalog/?color=coyote\">койот</a> и <a href=\"/catalog/?color=olive\">олива</a> для поклонников милитари-эстетики; нейтральный <a href=\"/catalog/?color=grey\">серый</a> и чистый <a href=\"/catalog/?color=white\">белый</a> для весенне-летних образов. Все цвета проверяются на устойчивость к УФ и идеально держат форму даже после 30+ циклов стирки.",
        "en": "Every item in the catalog comes in several colours: classic <a href=\"/catalog/?color=black\">black</a> for those who want a universal base for any print; <a href=\"/catalog/?color=coyote\">coyote</a> and <a href=\"/catalog/?color=olive\">olive</a> for fans of military aesthetics; neutral <a href=\"/catalog/?color=grey\">grey</a> and clean <a href=\"/catalog/?color=white\">white</a> for spring–summer looks. All colours are tested for UV resistance and hold their shape even after 30+ wash cycles.",
    },
    "Більшість принтів TwoComms — це авторські ілюстрації на тему патріотизму, ЗСУ, української історії та сучасної поп-культури. Ми передаємо частину прибутку на підтримку Збройних Сил України, тому кожна покупка — це одночасно вибір якісного одягу й вклад у перемогу. На сторінці кожного товару ви знайдете розмірну сітку, детальні фото матеріалу, відгуки клієнтів і прозору інформацію про склад тканини.": {
        "ru": "Большинство принтов TwoComms — это авторские иллюстрации на тему патриотизма, ВСУ, украинской истории и современной поп-культуры. Мы передаём часть прибыли на поддержку Вооружённых Сил Украины, поэтому каждая покупка — это одновременно выбор качественной одежды и вклад в победу. На странице каждого товара вы найдёте размерную сетку, детальные фото материала, отзывы клиентов и прозрачную информацию о составе ткани.",
        "en": "Most TwoComms prints are original illustrations on themes of patriotism, the Armed Forces, Ukrainian history and contemporary pop culture. We donate a portion of the profit to the Armed Forces of Ukraine, so every purchase combines quality apparel with a contribution to victory. On every product page you'll find a size guide, detailed material photos, customer reviews and transparent fabric composition.",
    },
    "Якщо ви не знайшли потрібну графіку — спробуйте розділ <a href=\"/custom-print/\">«Власний принт»</a>: ми надрукуємо будь-яку ілюстрацію на обраній моделі від однієї одиниці. Доставка по Україні — Новою Поштою на відділення або в поштомат за 1–2 дні. Оплата — карткою через Monobank/LiqPay або накладеним платежем. Усі товари мають 14 днів на повернення, якщо не підійшов розмір.": {
        "ru": "Если вы не нашли нужную графику — попробуйте раздел <a href=\"/custom-print/\">«Собственный принт»</a>: мы напечатаем любую иллюстрацию на выбранной модели от одной единицы. Доставка по Украине — Новой Почтой в отделение или почтомат за 1–2 дня. Оплата — картой через Monobank/LiqPay или наложенным платежом. У всех товаров есть 14 дней на возврат, если не подошёл размер.",
        "en": "If you didn't find the right artwork — try the <a href=\"/custom-print/\">Custom Print</a> section: we'll print any illustration on the selected model from a single unit. Delivery within Ukraine — via Nova Poshta to a branch or parcel locker in 1–2 days. Payment — by card through Monobank/LiqPay or cash on delivery. Every item can be returned within 14 days if the size doesn't fit.",
    },
}

# ===========================================================================
# Phase 17i (2026-05-12) — color_seo_copy.py dynamic + GENERAL chip labels.
# Kept in a separate dict so we can grow the curated set without ballooning
# the original TRANSLATIONS dict. Merged into TRANSLATIONS below.
# ===========================================================================
TRANSLATIONS_PHASE_17I: dict[str, dict[str, str]] = {
    # H2 templates with %(adj_*)s / %(name)s / %(cat)s placeholders.
    # Note: source uses ``adj_m`` (Ukrainian: «чорний одяг» — masculine noun
    # «одяг»). Russian noun «одежда» is feminine, so we drop the leading
    # adjective and let «%(name)s» carry the colour. English has no gender,
    # so we keep the natural attributive order.
    "%(adj_m_cap)s одяг TwoComms — стрітвір у відтінку «%(name)s»": {
        "ru": "Одежда TwoComms в оттенке «%(name)s» — украинский стритвир",
        "en": "%(adj_m_cap)s TwoComms apparel — streetwear in the %(name)s tone",
    },
    "%(adj_n_cap)s %(cat)s TwoComms — український стрітвір з принтом": {
        "ru": "%(adj_n_cap)s %(cat)s TwoComms — украинский стритвир с принтом",
        "en": "%(adj_n_cap)s %(cat)s TwoComms — Ukrainian streetwear with print",
    },

    # Cross-category landing paragraphs.
    # RU rewording: source uses neuter «%(adj_n_cap)s одяг» (Ukrainian
    # «одяг» = masculine singular). Russian «одежда» is feminine — keep
    # the colour reference but drop the strict adjective agreement.
    "У каталозі TwoComms ви знайдете %(adj_n)s <a href=\"/catalog/hoodie/?color=%(slug)s\">худі</a>, <a href=\"/catalog/tshirts/?color=%(slug)s\">футболки</a> та <a href=\"/catalog/long-sleeve/?color=%(slug)s\">лонгсліви</a> з авторськими принтами. Усі моделі шиємо в Україні з натуральних тканин, друкуємо DTF-технологією й перевіряємо на стійкість кольору до прання. %(adj_n_cap)s одяг легко комбінувати з джинсами, карго-штанами та мілітарними аксесуарами.": {
        "ru": "В каталоге TwoComms вы найдёте <a href=\"/catalog/hoodie/?color=%(slug)s\">худи</a>, <a href=\"/catalog/tshirts/?color=%(slug)s\">футболки</a> и <a href=\"/catalog/long-sleeve/?color=%(slug)s\">лонгсливы</a> в оттенке %(adj_n)s, с авторскими принтами. Все модели шьём в Украине из натуральных тканей, печатаем по технологии DTF и проверяем на устойчивость цвета к стирке. Одежду такого оттенка легко комбинировать с джинсами, карго-штанами и милитари-аксессуарами.",
        "en": "In the TwoComms catalogue you'll find %(adj_n)s <a href=\"/catalog/hoodie/?color=%(slug)s\">hoodies</a>, <a href=\"/catalog/tshirts/?color=%(slug)s\">t-shirts</a> and <a href=\"/catalog/long-sleeve/?color=%(slug)s\">long sleeves</a> with original prints. Every model is made in Ukraine from natural fabrics, printed with DTF and colour-tested for laundering. %(adj_n_cap)s pieces pair easily with jeans, cargo trousers and tactical accessories.",
    },
    "Якщо вас цікавить конкретний принт у %(name)s — скористайтесь сторінкою <a href=\"/custom-print/\">«Власний принт»</a>: ми надрукуємо будь-яку ілюстрацію на обраній моделі від однієї одиниці. Доставка Новою Поштою по всій Україні — 1–2 дні; оплата карткою або накладеним платежем; повернення впродовж 14 днів, якщо не підійшов розмір.": {
        "ru": "Если вас интересует конкретный принт в %(name)s — воспользуйтесь страницей <a href=\"/custom-print/\">«Собственный принт»</a>: мы напечатаем любую иллюстрацию на выбранной модели от одной единицы. Доставка Новой Почтой по всей Украине — 1–2 дня; оплата картой или наложенным платежом; возврат в течение 14 дней, если не подошёл размер.",
        "en": "Looking for a specific print in %(name)s? Use the <a href=\"/custom-print/\">Custom Print</a> page: we'll print any artwork on the chosen model from a single unit. Nova Poshta delivery across Ukraine in 1–2 days; card payment or cash on delivery; 14-day return window if the size doesn't fit.",
    },

    # Category × colour paragraphs.
    "У категорії «%(cat)s» %(adj_n)s TwoComms — це поєднання якісної тканини, насиченого друку й продуманої посадки. Ми використовуємо щільні полотна, так що принт не просвічується, а сам одяг тримає форму після десятків прань. Звертайте увагу на розмірну сітку — %(cat)s у TwoComms ідуть у двох посадках: класична та оверсайз.": {
        "ru": "В категории «%(cat)s» %(adj_n)s TwoComms — это сочетание качественной ткани, насыщенной печати и продуманной посадки. Мы используем плотные полотна, поэтому принт не просвечивает, а сама одежда держит форму после десятков стирок. Обратите внимание на размерную сетку — %(cat)s в TwoComms идут в двух посадках: классическая и оверсайз.",
        "en": "In the %(cat)s category, %(adj_n)s TwoComms gear combines quality fabric, saturated print and a thought-through fit. We use heavy knits so the print doesn't show through, and the garment keeps its shape after dozens of washes. Check the size chart — TwoComms %(cat)s come in two cuts: classic and oversized.",
    },
    "Подивіться також %(adj_n)s <a href=\"/catalog/?color=%(slug)s\">в інших категоріях</a> або оберіть інший відтінок цієї ж категорії — <a href=\"/catalog/%(cat_slug)s/\">%(cat)s TwoComms</a>. Якщо потрібен конкретний принт — скористайтесь сторінкою <a href=\"/custom-print/\">«Власний принт»</a>: ми надрукуємо вашу ілюстрацію на обраній моделі від однієї одиниці.": {
        "ru": "Посмотрите также %(adj_n)s <a href=\"/catalog/?color=%(slug)s\">в других категориях</a> или выберите другой оттенок этой же категории — <a href=\"/catalog/%(cat_slug)s/\">%(cat)s TwoComms</a>. Если нужен конкретный принт — воспользуйтесь страницей <a href=\"/custom-print/\">«Собственный принт»</a>: мы напечатаем вашу иллюстрацию на выбранной модели от одной единицы.",
        "en": "Also see %(adj_n)s <a href=\"/catalog/?color=%(slug)s\">across the other categories</a> or pick a different shade in this category — <a href=\"/catalog/%(cat_slug)s/\">%(cat)s TwoComms</a>. Need a specific print? Use the <a href=\"/custom-print/\">Custom Print</a> page: we'll print your artwork on the chosen model from a single unit.",
    },

    # Generic fallback (uncurated colour) tone paragraph + chips.
    "Колір «%(label)s» у каталозі TwoComms — це вибір для тих, хто хоче відійти від базової палітри, але не готовий поступатися якістю принту. Ми друкуємо на цьому відтінку DTF-технологією з підвищеним базовим шаром, тому ілюстрація не «провалюється» у тон тканини й залишається насиченою після десятків прань.": {
        "ru": "Цвет «%(label)s» в каталоге TwoComms — это выбор для тех, кто хочет отойти от базовой палитры, но не готов уступать в качестве печати. Мы печатаем на этом оттенке по технологии DTF с усиленным базовым слоем, поэтому иллюстрация не «проваливается» в тон ткани и остаётся насыщенной после десятков стирок.",
        "en": "The %(label)s shade at TwoComms is the pick for anyone who wants to leave the basic palette behind without compromising on print quality. We print on this colour with DTF and a boosted base layer, so the artwork doesn't blend into the fabric and stays saturated after dozens of washes.",
    },
    "вибраний": {"ru": "выбранный", "en": "selected"},
    "Купити %(color)s худі":            {"ru": "Купить %(color)s худи",           "en": "Buy %(color)s hoodie"},
    "%(color)s футболка з принтом":     {"ru": "%(color)s футболка с принтом",    "en": "%(color)s t-shirt with print"},
    "%(color)s лонгслів":               {"ru": "%(color)s лонгслив",              "en": "%(color)s long sleeve"},
    "%(color)s стрітвір TwoComms":      {"ru": "%(color)s стритвир TwoComms",     "en": "%(color)s streetwear TwoComms"},
    "%(color)s одяг ЗСУ донат":         {"ru": "%(color)s одежда ВСУ донат",      "en": "%(color)s clothing AFU donation"},
    "%(color)s футболка з тризубом купити Україна": {
        "ru": "%(color)s футболка с тризубом купить Украина",
        "en": "%(color)s t-shirt with trident buy Ukraine",
    },
    "%(color)s худі з патріотичним принтом": {
        "ru": "%(color)s худи с патриотическим принтом",
        "en": "%(color)s hoodie with patriotic print",
    },

    # GENERAL_CATALOG_SEO_COPY chip labels.
    "Купити худі":                           {"ru": "Купить худи",                       "en": "Buy a hoodie"},
    "Купити футболку з принтом":             {"ru": "Купить футболку с принтом",         "en": "Buy a printed t-shirt"},
    "Купити лонгслів":                       {"ru": "Купить лонгслив",                   "en": "Buy a long sleeve"},
    "Український стрітвір":                  {"ru": "Украинский стритвир",               "en": "Ukrainian streetwear"},
    "Худі ЗСУ":                              {"ru": "Худи ВСУ",                          "en": "AFU hoodie"},
    "Чорна футболка з тризубом":             {"ru": "Чёрная футболка с тризубом",        "en": "Black t-shirt with trident"},
    "Кайотовий лонгслів":                    {"ru": "Койотовый лонгслив",                "en": "Coyote long sleeve"},
    "Оливкове худі мілітарі":                {"ru": "Оливковое худи милитари",           "en": "Olive military hoodie"},
    "Подарунок захиснику український бренд": {"ru": "Подарок защитнику украинский бренд","en": "Soldier gift Ukrainian brand"},
    "Худі з патріотичним принтом купити Київ": {
        "ru": "Худи с патриотическим принтом купить Киев",
        "en": "Hoodie with patriotic print buy Kyiv",
    },
    "Футболка ЗСУ донат на ЗСУ Україна": {
        "ru": "Футболка ВСУ донат на ВСУ Украина",
        "en": "AFU t-shirt donation to Armed Forces Ukraine",
    },
    "Власний принт на одязі від 1 одиниці": {
        "ru": "Собственный принт на одежде от 1 единицы",
        "en": "Custom print on clothing from 1 unit",
    },
}
TRANSLATIONS.update(TRANSLATIONS_PHASE_17I)


# ===========================================================================
# Phase 17j (2026-05-13) — contacts.html + product_detail.html wrappings.
# ===========================================================================
TRANSLATIONS_PHASE_17J: dict[str, dict[str, str]] = {
    # ----- contacts.html -----
    "Контакти": {"ru": "Контакты", "en": "Contacts"},
    "Зв'яжіться з TwoComms: телефон, Telegram, Instagram. Офіційні магазини та форма зворотного зв'язку.": {
        "ru": "Свяжитесь с TwoComms: телефон, Telegram, Instagram. Официальные магазины и форма обратной связи.",
        "en": "Get in touch with TwoComms: phone, Telegram, Instagram. Official stores and a contact form.",
    },
    "контакти TwoComms, телефон, telegram, instagram, зворотній зв’язок, магазини TwoComms": {
        "ru": "контакты TwoComms, телефон, telegram, instagram, обратная связь, магазины TwoComms",
        "en": "TwoComms contacts, phone, telegram, instagram, feedback, TwoComms stores",
    },
    "Зв'яжіться з TwoComms: телефон, Telegram, Instagram. Швидка відповідь на будь-які питання.": {
        "ru": "Свяжитесь с TwoComms: телефон, Telegram, Instagram. Быстрый ответ на любые вопросы.",
        "en": "Reach out to TwoComms: phone, Telegram, Instagram. Quick answers to any question.",
    },
    "Зв'яжіться з нами будь-яким зручним способом": {
        "ru": "Свяжитесь с нами любым удобным способом",
        "en": "Reach us in any way that suits you",
    },
    "Телефон": {"ru": "Телефон", "en": "Phone"},
    "Показати телефон": {"ru": "Показать телефон", "en": "Show phone"},
    "Наші магазини": {"ru": "Наши магазины", "en": "Our stores"},
    "Відвідайте наші партнерські магазини": {
        "ru": "Посетите наши партнёрские магазины",
        "en": "Visit our partner stores",
    },
    "Магазин №1": {"ru": "Магазин №1", "en": "Store #1"},
    "Магазин №2": {"ru": "Магазин №2", "en": "Store #2"},
    "вул. Хрещатик, 22<br>\n                Київ, 01001": {
        "ru": "ул. Крещатик, 22<br>\n                Киев, 01001",
        "en": "22 Khreshchatyk St.<br>\n                Kyiv, 01001",
    },
    "пр. Соборний, 15<br>\n                Львів, 79000": {
        "ru": "пр. Соборный, 15<br>\n                Львов, 79000",
        "en": "15 Sobornyi Ave.<br>\n                Lviv, 79000",
    },
    "Графік роботи:": {"ru": "График работы:", "en": "Working hours:"},
    "Пн-Нд: 10:00 - 22:00": {"ru": "Пн-Вс: 10:00 - 22:00", "en": "Mon-Sun: 10:00 - 22:00"},
    "Написати нам": {"ru": "Написать нам", "en": "Write to us"},
    "Маєте питання? Залиште повідомлення і ми зв'яжемося з вами": {
        "ru": "Есть вопрос? Оставьте сообщение, и мы свяжемся с вами",
        "en": "Got a question? Leave a message and we'll get back to you",
    },
    "Ім'я": {"ru": "Имя", "en": "Name"},
    "Тема": {"ru": "Тема", "en": "Subject"},
    "Повідомлення": {"ru": "Сообщение", "en": "Message"},
    "Надіслати повідомлення": {"ru": "Отправить сообщение", "en": "Send message"},

    # ----- product_detail.html: copy block -----
    "%(title)s — це не просто одяг. Це стан.": {
        "ru": "%(title)s — это не просто одежда. Это состояние.",
        "en": "%(title)s is more than apparel. It's a mindset.",
    },
    "Створений для тих, хто йде своїм шляхом, навіть коли все навколо летить під три чорти.": {
        "ru": "Создано для тех, кто идёт своим путём, даже когда всё вокруг рушится.",
        "en": "Made for those who walk their own path even when everything around falls apart.",
    },
    "Деталі": {"ru": "Детали", "en": "Details"},
    "Матеріал: 95% бавовна, 5% еластан — преміум якість, щільність 190 г/м²": {
        "ru": "Материал: 95% хлопок, 5% эластан — премиум-качество, плотность 190 г/м²",
        "en": "Fabric: 95% cotton, 5% elastane — premium quality, 190 g/m²",
    },
    "М'який та приємний до тіла, дихає і не сковує рухів": {
        "ru": "Мягкий и приятный к телу, дышит и не сковывает движений",
        "en": "Soft and pleasant on the skin, breathable and unrestrictive",
    },
    "Підсилені шви та еластичні манжети для довговічності": {
        "ru": "Усиленные швы и эластичные манжеты для долговечности",
        "en": "Reinforced seams and elastic cuffs for durability",
    },
    "Принт витримує багато прань — не тріскається та не вигорає": {
        "ru": "Принт выдерживает много стирок — не трескается и не выгорает",
        "en": "The print survives many washes — no cracking, no fading",
    },
    "Зроблено в Україні з любов'ю та увагою до деталей": {
        "ru": "Сделано в Украине с любовью и вниманием к деталям",
        "en": "Made in Ukraine with love and attention to detail",
    },
    "Кому підійде": {"ru": "Кому подойдёт", "en": "Who it suits"},
    "Показати більше": {"ru": "Показать больше", "en": "Show more"},
    "Згорнути": {"ru": "Свернуть", "en": "Collapse"},
    "Рекомендації по посадці": {"ru": "Рекомендации по посадке", "en": "Fit recommendations"},
    "Підбір розміру": {"ru": "Подбор размера", "en": "Size selection"},
    "Відкрийте загальну розмірну сітку TwoComms або напишіть нам для уточнення посадки.": {
        "ru": "Откройте общую размерную сетку TwoComms или напишите нам, чтобы уточнить посадку.",
        "en": "Open the general TwoComms size chart or write to us to clarify the fit.",
    },
    "Розмірна сітка": {"ru": "Размерная сетка", "en": "Size chart"},
    "Допомога з вибором": {"ru": "Помощь с выбором", "en": "Help with selection"},

    "Відправка": {"ru": "Отправка", "en": "Shipping"},
    "1–2 дні по Україні після підтвердження замовлення.": {
        "ru": "1–2 дня по Украине после подтверждения заказа.",
        "en": "1–2 days across Ukraine after the order is confirmed.",
    },
    "Оплата": {"ru": "Оплата", "en": "Payment"},
    "Онлайн або після узгодження деталей з менеджером.": {
        "ru": "Онлайн или после согласования деталей с менеджером.",
        "en": "Online, or after the manager confirms the details.",
    },
    "Обмін": {"ru": "Обмен", "en": "Exchange"},
    "14 днів на обмін розміру, якщо річ не була у використанні.": {
        "ru": "14 дней на обмен размера, если вещь не была в использовании.",
        "en": "14 days to exchange the size if the item hasn't been worn.",
    },

    "Прання": {"ru": "Стирка", "en": "Washing"},
    "30°C, делікатний режим, навиворіт.": {
        "ru": "30°C, деликатный режим, наизнанку.",
        "en": "30°C, delicate cycle, inside out.",
    },
    "Принт": {"ru": "Принт", "en": "Print"},
    "Не прасувати напряму по нанесенню.": {
        "ru": "Не гладить напрямую по принту.",
        "en": "Do not iron directly over the print.",
    },
    "Сушка": {"ru": "Сушка", "en": "Drying"},
    "Без агресивної машинної сушки.": {
        "ru": "Без агрессивной машинной сушки.",
        "en": "Avoid aggressive tumble drying.",
    },

    "Кількість": {"ru": "Количество", "en": "Quantity"},
    "Зменшити кількість": {"ru": "Уменьшить количество", "en": "Decrease quantity"},
    "Збільшити кількість": {"ru": "Увеличить количество", "en": "Increase quantity"},
    "ДОДАТИ В КОШИК": {"ru": "ДОБАВИТЬ В КОРЗИНУ", "en": "ADD TO CART"},

    "Швидка доставка": {"ru": "Быстрая доставка", "en": "Fast delivery"},
    "1-3 дні Новою Поштою": {"ru": "1-3 дня Новой Почтой", "en": "1-3 days via Nova Poshta"},
    "Обмін розміру": {"ru": "Обмен размера", "en": "Size exchange"},
    "14 днів на повернення": {"ru": "14 дней на возврат", "en": "14-day returns"},
    "Гайд по посадці": {"ru": "Гайд по посадке", "en": "Fit guide"},

    "Отримайте %(points)s балів за покупку цього товару": {
        "ru": "Получите %(points)s баллов за покупку этого товара",
        "en": "Earn %(points)s points for buying this product",
    },

    "Нещодавно переглядали": {"ru": "Недавно просмотренные", "en": "Recently viewed"},
    "До каталогу": {"ru": "В каталог", "en": "Back to catalog"},
    "— схожий товар TwoComms": {
        "ru": "— похожий товар TwoComms",
        "en": "— related TwoComms product",
    },
    "Додати %(title)s до обраних": {
        "ru": "Добавить %(title)s в избранное",
        "en": "Add %(title)s to favourites",
    },

    # Phase 19c FAQ tab label.
    "FAQ товару": {"ru": "FAQ товара", "en": "Product FAQ"},

    # Recurring tiny labels.
    "Швидка відправка": {"ru": "Быстрая отправка", "en": "Fast shipping"},
    "1-2 дні по Україні": {"ru": "1-2 дня по Украине", "en": "1-2 days across Ukraine"},
    "Індивідуальний підхід": {"ru": "Индивидуальный подход", "en": "Personal approach"},
    "Допоможемо з вибором": {"ru": "Поможем с выбором", "en": "We'll help you choose"},
    "14 днів на обмін": {"ru": "14 дней на обмен", "en": "14 days to exchange"},
    "Галерея товару": {"ru": "Галерея товара", "en": "Product gallery"},
    "Дії з фото": {"ru": "Действия с фото", "en": "Photo actions"},
    "Збільшити фото": {"ru": "Увеличить фото", "en": "Zoom photo"},
    "Попереднє фото": {"ru": "Предыдущее фото", "en": "Previous photo"},
    "Наступне фото": {"ru": "Следующее фото", "en": "Next photo"},
    "Мініатюри товару": {"ru": "Миниатюры товара", "en": "Product thumbnails"},
    "Переваги покупки": {"ru": "Преимущества покупки", "en": "Purchase benefits"},
}
TRANSLATIONS.update(TRANSLATIONS_PHASE_17J)


# Phase 17i fix: original `[^"]*` failed on multi-line msgid blocks
# whose continuation strings contain escaped quotes (e.g. ``href=\"…\"`` in
# the catalogue SEO paragraphs). The dotted alternative
# ``(?:[^"\\]|\\.)*`` walks escape sequences as a unit so the regex stops
# only at unescaped closing quotes.
_PO_STRING = r'"(?:[^"\\]|\\.)*"'

_PO_ENTRY_RE = re.compile(
    rf'(^msgid (?:{_PO_STRING}\s*)+\n)((?:msgstr (?:{_PO_STRING}\s*)+\n)+)',
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
    """Encode a string for a single-line PO value.

    PO files use C-style escapes; real newline / tab / CR characters
    cannot appear inside a quoted string. Translate them to backslash
    sequences so multi-line msgstr values (e.g. address blocks with
    embedded ``\\n``) compile correctly under ``msgfmt``.
    """
    return (
        s.replace("\\", "\\\\")
        .replace('"', r"\"")
        .replace("\n", "\\n")
        .replace("\t", "\\t")
        .replace("\r", "\\r")
    )


_BLOCK_RE = re.compile(
    rf"((?:^#.*\n)*)(^msgid (?:{_PO_STRING}\s*)+\n)((?:msgstr (?:{_PO_STRING}\s*)+\n)+)",
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
        # Phase 17d.6 — also override msgstr that equals msgid (Django's
        # makemessages auto-copies msgid into msgstr for some entries;
        # those placeholder values should be replaced with our explicit
        # translation when one exists).
        is_placeholder = msgstr_val == msgid_val
        if msgstr_val.strip() and not is_fuzzy and not is_placeholder:
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
