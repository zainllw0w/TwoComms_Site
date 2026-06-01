"""Довідник MCC (Merchant Category Code) → людська категорія.

Monobank повертає ``mcc`` у кожній операції за карткою. Це дозволяє
автоматично групувати витрати (продукти, кафе, паливо, тощо) без ручного
тегування. Тут — компактний мапінг найпоширеніших діапазонів MCC у
укрупнені групи для аналітики та автокатегоризації.

Довідник свідомо неповний: невідомі MCC лишаються 'other'. За потреби —
розширюйте діапазони.
"""
from __future__ import annotations

# Точкові MCC та діапазони (включно) → ключ групи.
# Порядок має значення: специфічні діапазони — раніше за ширші.
_RANGES = [
    # Продукти та супермаркети
    ((5411, 5411), 'groceries'),   # супермаркети, бакалія
    ((5412, 5422), 'groceries'),   # м'ясо, морепродукти
    ((5441, 5451), 'groceries'),   # кондитерська, молочна
    ((5462, 5499), 'groceries'),   # пекарні, інші продукти
    # Кафе, ресторани, фастфуд, бари
    ((5811, 5814), 'food_out'),
    ((5462, 5462), 'food_out'),
    # Паливо, АЗС
    ((5541, 5542), 'fuel'),
    ((5983, 5983), 'fuel'),
    # Доставка, пошта, кур'єри, логістика
    ((4214, 4215), 'delivery'),    # вантажні, кур'єри (Нова Пошта тощо)
    ((4225, 4225), 'delivery'),    # склади/зберігання
    # Транспорт, таксі, громадський транспорт, паркінг
    ((4111, 4120), 'transport'),
    ((4131, 4131), 'transport'),   # автобуси
    ((4011, 4011), 'transport'),
    ((4121, 4121), 'transport'),   # таксі/лімузини
    ((7512, 7523), 'transport'),   # прокат авто, паркінг
    # Подорожі: авіа, готелі, турагенції
    ((3000, 3350), 'travel'),      # авіакомпанії
    ((3501, 3999), 'travel'),      # готелі
    ((4511, 4511), 'travel'),
    ((4722, 4723), 'travel'),
    ((7011, 7011), 'travel'),
    # Одяг, взуття, аксесуари
    ((5611, 5699), 'clothing'),
    ((5948, 5949), 'clothing'),    # шкіргалантерея, тканини
    # Аптеки, медицина, лікарні
    ((5912, 5912), 'health'),
    ((5975, 5976), 'health'),      # слухові апарати, ортопедія
    ((8011, 8099), 'health'),
    ((8042, 8049), 'health'),
    # Зв'язок, інтернет, мобільний
    ((4812, 4816), 'telecom'),
    ((4899, 4899), 'telecom'),     # кабельне/стрімінг
    # Підписки, ПЗ, цифрові товари
    ((5817, 5818), 'software'),
    ((5734, 5734), 'software'),    # магазини ПЗ
    # Розваги, кіно, ігри, спорт
    ((7800, 7999), 'entertainment'),
    ((7832, 7841), 'entertainment'),  # кінотеатри
    ((5815, 5816), 'entertainment'),  # цифрові медіа/ігри
    # Електроніка, побутова техніка
    ((5722, 5722), 'electronics'),
    ((5732, 5733), 'electronics'),
    ((5045, 5045), 'electronics'),    # комп'ютери
    # Краса, перукарні, спа
    ((7230, 7298), 'beauty'),
    ((5977, 5977), 'beauty'),         # косметика
    # Комунальні, держпослуги, податки, штрафи
    ((9211, 9311), 'gov_fees'),
    ((9399, 9399), 'gov_fees'),
    ((9222, 9223), 'gov_fees'),       # штрафи
    ((4900, 4900), 'utilities'),
    # Перекази, банкомати, фінпослуги, P2P
    ((6010, 6012), 'cash_finance'),
    ((6050, 6051), 'cash_finance'),   # квазі-готівка, крипто
    ((6529, 6540), 'cash_finance'),   # перекази/поповнення
    ((4829, 4829), 'cash_finance'),   # грошові перекази
    # Товари для дому, меблі, будматеріали
    ((5200, 5211), 'home'),
    ((5712, 5719), 'home'),
    ((5231, 5231), 'home'),
    # Дитячі товари, іграшки, зоотовари
    ((5641, 5641), 'kids'),
    ((5945, 5945), 'kids'),           # іграшки
    ((5995, 5995), 'pets'),           # зоотовари
    ((742, 742), 'pets'),             # ветеринарія
    # Освіта, книги
    ((8211, 8299), 'education'),
    ((5942, 5943), 'education'),       # книгарні, канцтовари
]

GROUP_LABELS = {
    'groceries': 'Продукти',
    'food_out': 'Кафе та ресторани',
    'fuel': 'Паливо',
    'transport': 'Транспорт',
    'travel': 'Подорожі',
    'clothing': 'Одяг',
    'health': 'Здоровʼя',
    'telecom': 'Звʼязок',
    'software': 'Підписки та ПЗ',
    'entertainment': 'Розваги',
    'electronics': 'Електроніка',
    'beauty': 'Краса',
    'gov_fees': 'Держпослуги',
    'utilities': 'Комунальні',
    'cash_finance': 'Готівка та фінанси',
    'delivery': 'Логістика та доставка',
    'home': 'Дім та меблі',
    'kids': 'Дитячі товари',
    'pets': 'Тварини',
    'education': 'Освіта та книги',
    'other': 'Інше',
}


def group_for_mcc(mcc) -> str:
    """Повертає ключ групи витрат за MCC ('other', якщо невідомо)."""
    try:
        code = int(mcc)
    except (TypeError, ValueError):
        return 'other'
    for (lo, hi), key in _RANGES:
        if lo <= code <= hi:
            return key
    return 'other'


def label_for_mcc(mcc) -> str:
    """Людська назва групи за MCC."""
    return GROUP_LABELS.get(group_for_mcc(mcc), GROUP_LABELS['other'])


# Емодзі-іконка + колір для авто-категорій (узгоджено з особистими категоріями).
GROUP_META = {
    'groceries':    ('🛒', '#f59e0b'),
    'food_out':     ('🍽️', '#ec4899'),
    'fuel':         ('⛽', '#ef4444'),
    'transport':    ('🚗', '#3b82f6'),
    'travel':       ('✈️', '#06b6d4'),
    'clothing':     ('👕', '#8b5cf6'),
    'health':       ('💊', '#10b981'),
    'telecom':      ('📱', '#6366f1'),
    'software':     ('💻', '#0ea5e9'),
    'entertainment':('🎮', '#d946ef'),
    'electronics':  ('🔌', '#64748b'),
    'beauty':       ('💄', '#f472b6'),
    'gov_fees':     ('🏛️', '#6b7280'),
    'utilities':    ('💡', '#f97316'),
    'cash_finance': ('💳', '#94a3b8'),
    'delivery':     ('📦', '#eab308'),
    'home':         ('🏠', '#a3e635'),
    'kids':         ('🧸', '#fb923c'),
    'pets':         ('🐾', '#22d3ee'),
    'education':    ('📚', '#06b6d4'),
    'other':        ('💳', '#6b7280'),
}

# Кеш {group_key: Category.id} у межах процесу, щоб не плодити запити.
_category_cache: dict = {}


def get_or_create_category_for_mcc(company, mcc):
    """Повертає finance.Category, що відповідає MCC-групі операції.

    Категорії авто-створюються один раз (is_system=False, type=expense) із
    назвою/іконкою/кольором із GROUP_LABELS/GROUP_META. Невідомі MCC → None
    (не засмічуємо «Інше» — користувач сам обере за потреби).
    """
    if mcc is None:
        return None
    group = group_for_mcc(mcc)
    if group == 'other':
        return None  # не нав'язуємо «Інше», лишаємо для ручного вибору

    cache_key = (company.id, group)
    cached_id = _category_cache.get(cache_key)
    from ..models import Category
    if cached_id:
        cat = Category.objects.filter(id=cached_id).first()
        if cat:
            return cat

    name = GROUP_LABELS.get(group, group)
    icon, color = GROUP_META.get(group, ('💳', '#6b7280'))
    cat, _ = Category.objects.get_or_create(
        company=company, name=name,
        defaults={'type': 'expense', 'icon': icon, 'color': color},
    )
    _category_cache[cache_key] = cat.id
    return cat
