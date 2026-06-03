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

    # Картки-метрики верхнього рівня.
    cards = [
        {'label': 'Поточний баланс', 'value': _m(m['total_cash']), 'hint': 'Усі рахунки', 'tone': 'info'},
        {'label': 'Бізнес-баланс', 'value': _m(m['business_cash']), 'hint': 'ФОП-рахунки', 'tone': 'info'},
        {'label': 'Прогноз мін. 30 днів',
         'value': _m(m['forecast_30_min']),
         'hint': 'Найнижча точка балансу',
         'tone': 'neg' if m['forecast_30_min'] < 0 else 'pos'},
        {'label': 'Запас ходу (runway)',
         'value': f'{result["layer_metrics"]["business"]["runway_months"]} міс.',
         'hint': 'Скільки протримається бізнес', 'tone': 'neutral'},
        {'label': 'Прибуток за місяць', 'value': _m(m['biz_profit_m'], signed=True),
         'hint': 'Бізнес-операції', 'tone': 'pos' if m['biz_profit_m'] >= 0 else 'neg'},
        {'label': 'Особисті витрати', 'value': _m(m['personal_expense_m']),
         'hint': 'За місяць', 'tone': 'neutral'},
        {'label': 'Заморожено у складі', 'value': _m(m['inventory_value']),
         'hint': 'Собівартість залишків', 'tone': 'info'},
        {'label': 'Борг контрагентів', 'value': _m(m['receivables_total']),
         'hint': 'Дебіторка до отримання', 'tone': 'neg' if m['receivables_total'] > 0 else 'neutral'},
        {'label': 'Прострочена дебіторка', 'value': _m(m['overdue_receivables']),
         'hint': 'Потребує дій', 'tone': 'neg' if m['overdue_receivables'] > 0 else 'pos'},
        {'label': 'Вивід власнику (міс.)', 'value': _m(m['owner_draw_m']),
         'hint': 'ФОП → особисте', 'tone': 'neutral'},
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
        'personal_incomplete': result['personal_incomplete'],
        'aging_rows': aging_rows,
        'has_receivables': m['receivables_total'] > 0,
        'warehouse_breakdown': legacy.get('warehouse_breakdown'),
        'upcoming_payments': [ser.serialize_transaction(t) for t in legacy.get('upcoming_payments', [])],
    })
