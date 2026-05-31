"""View для дашборду фінансового здоров'я — БЛОК 7."""
from django.shortcuts import render

from ..models import get_default_company
from ..permissions import finance_access_required
from ..services import dashboard as dashboard_service
from ..services import serializers as ser


@finance_access_required
def financial_health(request):
    """Єдиний дашборд фінансового здоров'я."""
    company = get_default_company()
    data = dashboard_service.financial_health_dashboard(company)

    # Форматуємо суми
    def _m(value, signed=False):
        return ser.money(value, company.base_currency, signed=signed)

    # Визначаємо колір health score
    score = data['health_score']
    if score >= 80:
        score_class = 'excellent'
        score_label = 'Відмінно'
    elif score >= 60:
        score_class = 'good'
        score_label = 'Добре'
    elif score >= 40:
        score_class = 'fair'
        score_label = 'Задовільно'
    else:
        score_class = 'poor'
        score_label = 'Потребує уваги'

    return render(request, 'finance/financial_health.html', {
        'active_tab': 'health',
        'data': data,
        'current_balance': _m(data['current_balance']),
        'forecast_3m': _m(data['forecast_3m'], signed=True),
        'business_profit': _m(data['business_profit_month'], signed=True),
        'personal_expenses': _m(data['personal_expenses_month']),
        'frozen_warehouse': _m(data['frozen_in_warehouse']),
        'health_score': score,
        'score_class': score_class,
        'score_label': score_label,
        'upcoming_payments': [ser.serialize_transaction(t) for t in data['upcoming_payments']],
    })
