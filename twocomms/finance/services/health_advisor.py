"""Генератор рекомендацій для «Фінансового здоров'я».

Кожна рекомендація — не порожня порада, а структура з проблемою, поясненням
чому це важливо, цифрою-доказом, конкретною дією та очікуваним ефектом
(cash impact / score impact). Тригери — на основі зібраних метрик.

Структура рекомендації:
    {
      'id', 'severity' (critical|high|medium|low|info), 'scope', 'title',
      'problem', 'why', 'action' (list[str]),
      'cash_impact' (str|None), 'score_impact' (int|None), 'confidence' (0..1),
    }
"""
from __future__ import annotations

from decimal import Decimal

ZERO = Decimal('0')


def _money(v):
    try:
        v = Decimal(str(v))
    except Exception:
        return '0 ₴'
    whole = f'{abs(v):,.0f}'.replace(',', ' ')
    return f'{whole} ₴'


def build_recommendations(m, biz, pers, bound) -> list:
    recs = []
    cash = m['business_cash'] if m['business_cash'] > 0 else m['total_cash']
    avg_exp = m['avg_monthly_expense']

    # 1. Прогнозний касовий розрив.
    if m['forecast_30_min'] < 0:
        gap = abs(float(m['forecast_30_min']))
        recs.append({
            'id': 'cash_gap',
            'severity': 'critical',
            'scope': 'business',
            'title': 'Уникнути касового розриву в найближчі 30 днів',
            'problem': f'Прогнозний мінімум балансу опускається до {m["forecast_30_min"]:.0f} ₴.',
            'why': 'Без дій не вистачить грошей на обов\'язкові платежі — будуть прострочки й штрафи.',
            'action': [
                'Прискорити оплату від магазинів із простроченим боргом.',
                'Перенести необов\'язкові закупівлі на пізніше.',
                'Тимчасово обмежити виводи на особисте.',
                'За потреби домовитись про відстрочку найбільшого платежу.',
            ],
            'cash_impact': f'до {_money(gap)} дефіциту, який треба закрити',
            'score_impact': 10,
            'confidence': 0.7,
        })

    # 2. Дебіторка (борг магазинів).
    ar = m['receivables_total']
    if ar > 0 and cash > 0 and float(ar / cash) > 0.5:
        collect_25 = ar * Decimal('0.25')
        recs.append({
            'id': 'collect_ar',
            'severity': 'high' if m['overdue_receivables'] > 0 else 'medium',
            'scope': 'business',
            'title': 'Забрати гроші з боргів магазинів/контрагентів',
            'problem': f'У контрагентах висить {_money(ar)} — це ~{float(ar / cash):.1f}× '
                       f'від доступного cash.',
            'why': 'Ці гроші не можуть покривати закупівлі, податки й виплати, поки не отримані.',
            'action': [
                'Відкрити дебіторку 30/60/90+ і надіслати нагадування боржникам.',
                'Зупинити нові відвантаження контрагентам із простроченням 30+.',
                'Для наступних поставок увімкнути передоплату 30–50%.',
            ],
            'cash_impact': f'повернення 25% боргу = +{_money(collect_25)} cash',
            'score_impact': 6,
            'confidence': 0.75,
        })

    # 3. Прострочена дебіторка 90+.
    if ar > 0:
        share_90 = float(m['ar_aging']['d90_plus'] / ar)
        if share_90 > 0.10:
            recs.append({
                'id': 'ar_90_plus',
                'severity': 'high',
                'scope': 'business',
                'title': 'Розібратись із дуже простроченими боргами (90+)',
                'problem': f'{share_90 * 100:.0f}% дебіторки прострочено понад 90 днів '
                           f'({_money(m["ar_aging"]["d90_plus"])}).',
                'why': 'Чим довше борг не оплачується, тим нижча ймовірність його повернути.',
                'action': [
                    'Скласти список боржників 90+ і зв\'язатися персонально.',
                    'Запропонувати графік погашення або часткову оплату.',
                    'Оцінити ризик списання й закласти його у план.',
                ],
                'cash_impact': f'під ризиком {_money(m["ar_aging"]["d90_plus"])}',
                'score_impact': 5,
                'confidence': 0.7,
            })

    # 4. Склад заморожує оборотку.
    inv = m['inventory_value']
    if avg_exp > 0 and inv > 0 and float(inv / avg_exp) > 2.0:
        recs.append({
            'id': 'inventory_frozen',
            'severity': 'medium',
            'scope': 'business',
            'title': 'Склад заморожує забагато оборотних коштів',
            'problem': f'У складі/реалізації заморожено {_money(inv)} '
                       f'(~{float(inv / avg_exp):.1f}× місячних витрат).',
            'why': 'Товар на складі не дорівнює грошам. Чим довше лежить — тим нижча ліквідність.',
            'action': [
                'Розділити свіжий / повільний / мертвий запас.',
                'По повільних SKU зробити bundle або акцію.',
                'Перед новою закупівлею перевіряти оборотність.',
            ],
            'cash_impact': f'потенційно вивільнити частину з {_money(inv)}',
            'score_impact': 4,
            'confidence': 0.6,
        })

    # 5. Нульова/непідтверджена прибутковість.
    if m['biz_income_m'] <= 0 and m['avg_monthly_revenue'] <= 0:
        recs.append({
            'id': 'no_revenue',
            'severity': 'high',
            'scope': 'business',
            'title': 'Немає підтвердженої виручки за місяць',
            'problem': 'За поточний місяць бізнес-доходи не зафіксовані або дорівнюють 0.',
            'why': 'Без виручки неможливо оцінити прибутковість і здоров\'я бізнесу.',
            'action': [
                'Перевірити, чи всі продажі занесені й позначені як бізнес.',
                'Розмітити доходи правильними категоріями.',
                'Підключити банк/інтеграцію для авто-імпорту операцій.',
            ],
            'cash_impact': None,
            'score_impact': 9,
            'confidence': 0.65,
        })
    elif m['biz_profit_m'] < 0:
        recs.append({
            'id': 'monthly_loss',
            'severity': 'high',
            'scope': 'business',
            'title': 'Бізнес працює у збиток цього місяця',
            'problem': f'Витрати перевищили доходи на {_money(abs(m["biz_profit_m"]))}.',
            'why': 'Стабільний збиток вимиває cash і скорочує запас ходу.',
            'action': [
                'Переглянути ціни й маржу найменш прибуткових позицій.',
                'Скоротити змінні витрати, що не дають віддачі.',
                'Виділити канали/товари, що тягнуть у мінус.',
            ],
            'cash_impact': f'збиток {_money(abs(m["biz_profit_m"]))}/міс.',
            'score_impact': 9,
            'confidence': 0.7,
        })

    # 6. Низька категоризація (data confidence).
    dq = m['data_quality']
    if dq['uncategorized_count'] > 0 and dq['categorized_share_amount'] < 0.85:
        recs.append({
            'id': 'categorize',
            'severity': 'medium',
            'scope': 'data',
            'title': f'Розмітити {dq["uncategorized_count"]} операцій без категорії',
            'problem': f'Категоризовано лише {dq["categorized_share_amount"] * 100:.0f}% обороту '
                       f'за останні 90 днів.',
            'why': 'Неповні дані знижують довіру до оцінки й обмежують максимальний score.',
            'action': [
                'Відкрити журнал і присвоїти категорії операціям без неї.',
                'Налаштувати автоправила для типових операцій.',
            ],
            'cash_impact': None,
            'score_impact': 8,
            'confidence': 0.85,
        })

    # 7. Особиста подушка.
    if not pers['incomplete'] and pers['metrics']['emergency_months'] < 3:
        recs.append({
            'id': 'emergency_fund',
            'severity': 'medium',
            'scope': 'personal',
            'title': 'Наростити особисту фінансову подушку',
            'problem': f'Особистої подушки вистачить лише на '
                       f'~{pers["metrics"]["emergency_months"]:.1f} міс.',
            'why': 'При слабкій подушці власник вимушено витягуватиме гроші з бізнесу.',
            'action': [
                'Відкласти фіксовану суму після кожного виводу на особисте.',
                'Сформувати ціль: 3 місяці обов\'язкових витрат.',
            ],
            'cash_impact': None,
            'score_impact': 5,
            'confidence': 0.6,
        })

    # 8. Особистий контур порожній.
    if pers['incomplete']:
        recs.append({
            'id': 'personal_setup',
            'severity': 'medium',
            'scope': 'personal',
            'title': 'Підключити особистий контур',
            'problem': 'Немає особистих рахунків/операцій — особисте здоров\'я не рахується точно.',
            'why': 'Без особистих даних не видно реальної стійкості власника.',
            'action': [
                'Додати особисту картку як рахунок (is_business=False).',
                'Заносити особисті витрати або імпортувати виписку.',
            ],
            'cash_impact': None,
            'score_impact': 6,
            'confidence': 0.7,
        })

    # 9. Змішування бізнес/особисте.
    if bound['metrics']['mixed_share'] > 5:
        recs.append({
            'id': 'boundary_mix',
            'severity': 'medium',
            'scope': 'boundary',
            'title': 'Розділити бізнес і особисті гроші',
            'problem': f'{bound["metrics"]["mixed_share"]:.1f}% обороту пройшло не через свій контур.',
            'why': 'Змішування спотворює P&L, cash flow і реальну прибутковість.',
            'action': [
                'Особисті покупки оплачувати особистою карткою.',
                'Бізнес-витрати з особистої картки позначати як owner-paid.',
                'Класифікувати перекази ФОП → особисте як вивід власника.',
            ],
            'cash_impact': None,
            'score_impact': 4,
            'confidence': 0.65,
        })

    # 10. Owner draw не налаштований.
    if m['owner_draw_m'] <= 0 and m['biz_profit_m'] > 0:
        recs.append({
            'id': 'owner_salary',
            'severity': 'low',
            'scope': 'boundary',
            'title': 'Додати план виплат власнику',
            'problem': 'Цього місяця виводів на особисте не зафіксовано.',
            'why': 'Бізнес без виплат власнику може виглядати прибутковим, але бути неstійким.',
            'action': [
                'Визначити регулярну суму виводу (owner draw).',
                'Налаштувати повторюваний переказ ФОП → особиста картка.',
            ],
            'cash_impact': None,
            'score_impact': 2,
            'confidence': 0.5,
        })

    # 11. Personal lifestyle.
    if not pers['incomplete'] and m['biz_income_m'] > 0:
        ratio = float(m['personal_expense_m'] / m['biz_income_m'] * 100) if m['biz_income_m'] else 0
        if ratio > 50:
            recs.append({
                'id': 'lifestyle',
                'severity': 'low',
                'scope': 'personal',
                'title': 'Особисті витрати з\'їдають свободу маневру',
                'problem': f'Особисті витрати становлять {ratio:.0f}% від бізнес-доходу.',
                'why': 'Високі особисті витрати тиснуть на оборотку бізнесу.',
                'action': [
                    'Встановити місячний ліміт на дискреційні категорії.',
                    'Переглянути регулярні підписки й необов\'язкові трати.',
                ],
                'cash_impact': None,
                'score_impact': 3,
                'confidence': 0.55,
            })

    # Сортуємо за серйозністю + score impact.
    sev_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3, 'info': 4}
    recs.sort(key=lambda r: (sev_order.get(r['severity'], 5), -(r.get('score_impact') or 0)))
    return recs
