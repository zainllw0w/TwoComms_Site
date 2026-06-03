"""View дашборду «Фінансове здоров'я» — багатошарова оцінка."""
from django.shortcuts import render

from ..models import get_default_company
from ..permissions import finance_access_required
from ..services import dashboard as dashboard_service
from ..services import health as health_service
from ..services import serializers as ser


@finance_access_required
def financial_health(request):
    """Єдиний дашборд фінансового здоров'я (Business/Personal/Boundary/Portfolio)."""
    company = get_default_company()
    result = health_service.calculate_health(company)
    m = result['metrics']

    def _m(value, signed=False):
        return ser.money(value, company.base_currency, signed=signed)

    # Старий дашборд — для деталізації складу/найближчих платежів (сумісність).
    legacy = dashboard_service.financial_health_dashboard(company)

    scores = result['scores']
    cur = company.base_currency
    biz_lm = result['layer_metrics']['business']
    pers_lm = result['layer_metrics']['personal']
    bound_lm = result['layer_metrics']['boundary']

    # Картки-метрики верхнього рівня. 15 карток → рівна сітка 5×3 на десктопі.
    # Згруповано: бізнес-ліквідність → прибутковість → робочий капітал → особисте.
    cards = [
        # --- Ряд 1: ліквідність і прогноз ---
        {'label': 'Поточний баланс', 'value': _m(m['total_cash']), 'hint': 'Усі рахунки', 'tone': 'info'},
        {'label': 'Бізнес-баланс', 'value': _m(m['business_cash']), 'hint': 'ФОП-рахунки', 'tone': 'info'},
        {'label': 'Прогноз мін. 30 днів',
         'value': _m(m['forecast_30_min']),
         'hint': 'Найнижча точка балансу',
         'tone': 'neg' if m['forecast_30_min'] < 0 else 'pos'},
        {'label': 'Запас ходу (runway)',
         'value': f'{biz_lm["runway_months"]} міс.',
         'hint': 'Скільки протримається бізнес',
         'tone': 'pos' if biz_lm['runway_months'] >= 3 else ('neg' if biz_lm['runway_months'] < 1 else 'neutral')},
        {'label': 'Маржа за місяць',
         'value': f'{biz_lm["margin"]:.0f}%',
         'hint': 'Прибуток / виручка',
         'tone': 'pos' if biz_lm['margin'] >= 15 else ('neg' if biz_lm['margin'] < 0 else 'neutral')},
        # --- Ряд 2: прибуток і робочий капітал ---
        {'label': 'Прибуток за місяць', 'value': _m(m['biz_profit_m'], signed=True),
         'hint': 'Бізнес-операції', 'tone': 'pos' if m['biz_profit_m'] >= 0 else 'neg'},
        {'label': 'Виручка за місяць', 'value': _m(m['biz_income_m']),
         'hint': 'Бізнес-доходи', 'tone': 'neutral'},
        {'label': 'Заморожено у складі', 'value': _m(m['inventory_value']),
         'hint': 'Собівартість залишків', 'tone': 'info'},
        {'label': 'Борг контрагентів', 'value': _m(m['receivables_total']),
         'hint': 'Дебіторка до отримання', 'tone': 'neg' if m['receivables_total'] > 0 else 'neutral'},
        {'label': 'Прострочена дебіторка', 'value': _m(m['overdue_receivables']),
         'hint': 'Потребує дій', 'tone': 'neg' if m['overdue_receivables'] > 0 else 'pos'},
        # --- Ряд 3: межа й особистий контур ---
        {'label': 'Вивід власнику (міс.)', 'value': _m(m['owner_draw_m']),
         'hint': 'ФОП → особисте', 'tone': 'neutral'},
        {'label': 'Особиста подушка',
         'value': ('—' if result['personal_incomplete'] else f'{pers_lm["emergency_months"]} міс.'),
         'hint': 'Запас на особисті витрати',
         'tone': 'neutral' if result['personal_incomplete'] else ('pos' if pers_lm['emergency_months'] >= 3 else 'neg')},
        {'label': 'Оренда житла (міс.)',
         'value': ('—' if result['personal_incomplete'] else _m(pers_lm['housing'])),
         'hint': (f'{pers_lm["housing_ratio_income"]:.0f}% доходу' if not result['personal_incomplete'] and pers_lm['housing'] else 'Оренда + комуналка'),
         'tone': 'neg' if (not result['personal_incomplete'] and pers_lm['housing_ratio_income'] > 35) else 'neutral'},
        {'label': 'Продукти (міс.)',
         'value': ('—' if result['personal_incomplete'] else _m(pers_lm['groceries'])),
         'hint': (f'{pers_lm["groceries_share"]:.0f}% витрат' if not result['personal_incomplete'] and pers_lm['groceries'] else 'Харчування'),
         'tone': 'neutral'},
        {'label': 'Норма заощаджень',
         'value': ('—' if result['personal_incomplete'] else f'{pers_lm["savings_rate"]:.0f}%'),
         'hint': 'Частка доходу у запас',
         'tone': 'neutral' if result['personal_incomplete'] else ('pos' if pers_lm['savings_rate'] >= 20 else ('neg' if pers_lm['savings_rate'] < 0 else 'neutral'))},
    ]

    # Розбір по слоях (Business / Personal / Boundary) — підсумкові субскори
    # з короткими поясненнями, щоб власник бачив із чого складається оцінка.
    layer_breakdown = [
        {
            'key': 'business', 'title': 'Бізнес', 'score': scores['business'],
            'tone': 'biz',
            'desc': 'Ліквідність, прибутковість, робочий капітал, прогноз і якість даних.',
            'rows': [
                {'label': 'Ліквідність / runway', 'value': biz_lm['runway_months'],
                 'score': result['subscores']['business']['liquidity'], 'suffix': ' міс.'},
                {'label': 'Прибутковість (маржа)', 'value': biz_lm['margin'],
                 'score': result['subscores']['business']['profitability'], 'suffix': '%'},
                {'label': 'Якість cash flow', 'value': None,
                 'score': result['subscores']['business']['cashflow'], 'suffix': ''},
                {'label': 'Робочий капітал', 'value': None,
                 'score': result['subscores']['business']['working_capital'], 'suffix': ''},
                {'label': 'Прогноз 30 днів', 'value': None,
                 'score': result['subscores']['business']['forecast'], 'suffix': ''},
                {'label': 'Якість даних', 'value': None,
                 'score': result['subscores']['business']['data'], 'suffix': ''},
            ],
        },
        {
            'key': 'personal', 'title': 'Особисте', 'score': scores['personal'],
            'tone': 'pers', 'incomplete': result['personal_incomplete'],
            'desc': 'Подушка безпеки, вільний грошовий потік і навантаження стилю життя.',
            'rows': [
                {'label': 'Подушка безпеки', 'value': pers_lm['emergency_months'],
                 'score': result['subscores']['personal']['cushion'], 'suffix': ' міс.'},
                {'label': 'Вільний потік (FCF)', 'value': None,
                 'score': result['subscores']['personal']['free_cash_flow'], 'suffix': ''},
                {'label': 'Стиль життя', 'value': None,
                 'score': result['subscores']['personal']['lifestyle'], 'suffix': ''},
            ],
        },
        {
            'key': 'boundary', 'title': 'Межа', 'score': scores['boundary'],
            'tone': 'bound',
            'desc': 'Чистота розділення бізнесу й особистого та дисципліна виводів власника.',
            'rows': [
                {'label': 'Розділення контурів', 'value': bound_lm['mixed_share'],
                 'score': result['subscores']['boundary']['separation'], 'suffix': '% змішано'},
                {'label': 'Вивід власника', 'value': None,
                 'score': result['subscores']['boundary']['owner_draw'], 'suffix': ''},
                {'label': 'Компенсації', 'value': None,
                 'score': result['subscores']['boundary']['reimbursements'], 'suffix': ''},
            ],
        },
    ]

    # AR aging для drill-down.
    ar_aging = m['ar_aging']
    ar_total = m['receivables_total'] or 1
    aging_rows = [
        {'label': 'Не прострочено', 'value': _m(ar_aging['not_due']),
         'pct': round(float(ar_aging['not_due'] / ar_total * 100), 1)},
        {'label': '1–30 днів', 'value': _m(ar_aging['d0_30']),
         'pct': round(float(ar_aging['d0_30'] / ar_total * 100), 1)},
        {'label': '31–60 днів', 'value': _m(ar_aging['d31_60']),
         'pct': round(float(ar_aging['d31_60'] / ar_total * 100), 1)},
        {'label': '61–90 днів', 'value': _m(ar_aging['d61_90']),
         'pct': round(float(ar_aging['d61_90'] / ar_total * 100), 1)},
        {'label': '90+ днів', 'value': _m(ar_aging['d90_plus']),
         'pct': round(float(ar_aging['d90_plus'] / ar_total * 100), 1)},
    ]

    return render(request, 'finance/financial_health.html', {
        'active_tab': 'health',
        'result': result,
        'scores': scores,
        'cards': cards,
        'caps': result['caps'],
        'lost_points': result['lost_points'],
        'alerts': result['critical_alerts'],
        'recommendations': result['recommendations'],
        'subscores': result['subscores'],
        'layer_breakdown': layer_breakdown,
        'personal_incomplete': result['personal_incomplete'],
        'aging_rows': aging_rows,
        'has_receivables': m['receivables_total'] > 0,
        'warehouse_breakdown': legacy.get('warehouse_breakdown'),
        'upcoming_payments': [ser.serialize_transaction(t) for t in legacy.get('upcoming_payments', [])],
    })
