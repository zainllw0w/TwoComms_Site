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
_RANGES = [
    # Продукти та супермаркети
    ((5411, 5411), 'groceries'),
    ((5412, 5499), 'groceries'),
    # Кафе, ресторани, фастфуд
    ((5811, 5814), 'food_out'),
    # Паливо, АЗС
    ((5541, 5542), 'fuel'),
    ((5983, 5983), 'fuel'),
    # Транспорт, таксі, авіа, готелі
    ((4111, 4131), 'transport'),
    ((4011, 4011), 'transport'),
    ((4511, 4511), 'travel'),
    ((4722, 4722), 'travel'),
    ((7011, 7011), 'travel'),
    # Одяг, взуття
    ((5611, 5699), 'clothing'),
    # Аптеки, медицина
    ((5912, 5912), 'health'),
    ((8011, 8099), 'health'),
    ((8011, 8011), 'health'),
    # Зв'язок, інтернет, підписки, ПЗ
    ((4812, 4816), 'telecom'),
    ((5817, 5818), 'software'),
    # Розваги, кіно
    ((7800, 7999), 'entertainment'),
    # Електроніка, побутова техніка
    ((5722, 5722), 'electronics'),
    ((5732, 5734), 'electronics'),
    # Краса, перукарні
    ((7230, 7298), 'beauty'),
    # Комунальні, держпослуги, податки
    ((9211, 9311), 'gov_fees'),
    ((4900, 4900), 'utilities'),
    # Перекази, банкомати, фінпослуги
    ((6010, 6012), 'cash_finance'),
    ((6536, 6540), 'cash_finance'),
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
