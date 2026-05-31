"""Єдиний дашборд фінансового здоров'я — БЛОК 7."""
from __future__ import annotations

from decimal import Decimal
from django.db import models
from django.utils import timezone

from . import balances as balance_service
from . import reports
from . import warehouse_link
from ..models import Transaction, RecurrenceRule


def financial_health_dashboard(company) -> dict:
    """Комплексний дашборд фінансового здоров'я компанії.

    Returns:
        {
            'current_balance': Decimal,  # Поточний баланс всіх рахунків
            'forecast_3m': Decimal,  # Прогноз через 3 місяці
            'business_profit_month': Decimal,  # Бізнес-прибуток за місяць
            'personal_expenses_month': Decimal,  # Особисті витрати за місяць
            'frozen_in_warehouse': Decimal,  # Заморожено у складі
            'warehouse_breakdown': dict,  # Деталізація складу
            'upcoming_payments': list,  # Найближчі планові платежі
            'warnings': list,  # Попередження
            'recommendations': list,  # Рекомендації
            'health_score': int,  # Оцінка здоров'я 0-100
        }
    """
    today = timezone.localdate()
    month_start = today.replace(day=1)

    # 1. Поточний баланс
    current_balance = balance_service.total_actual_balance(company)

    # 2. Прогноз на 3 місяці
    forecast_data = reports.balance_forecast_report(company, months=3)
    forecast_3m = forecast_data['final_balance']

    # 3. Бізнес-прибуток за поточний місяць
    business_income = Transaction.objects.filter(
        company=company,
        status=Transaction.STATUS_ACTUAL,
        is_business=True,
        type=Transaction.TYPE_INCOME,
        date_actual__gte=month_start,
        date_actual__lte=today
    ).aggregate(total=models.Sum('amount_base'))['total'] or Decimal('0')

    business_expense = Transaction.objects.filter(
        company=company,
        status=Transaction.STATUS_ACTUAL,
        is_business=True,
        type=Transaction.TYPE_EXPENSE,
        date_actual__gte=month_start,
        date_actual__lte=today
    ).aggregate(total=models.Sum('amount_base'))['total'] or Decimal('0')

    business_profit_month = business_income - business_expense

    # 4. Особисті витрати за місяць
    personal_expenses_month = Transaction.objects.filter(
        company=company,
        status=Transaction.STATUS_ACTUAL,
        is_business=False,
        type=Transaction.TYPE_EXPENSE,
        date_actual__gte=month_start,
        date_actual__lte=today
    ).aggregate(total=models.Sum('amount_base'))['total'] or Decimal('0')

    # 5. Заморожено у складі
    frozen = warehouse_link.frozen_in_warehouse()
    warehouse_breakdown = warehouse_link.warehouse_breakdown()

    # 5b. Заморожено під реалізацію (магазини) + борг магазинів
    from . import consignment as consignment_service
    frozen_consignment = consignment_service.consignment_frozen_total(company)
    consignment_breakdown = consignment_service.consignment_frozen_breakdown(company)
    resellers_debt = consignment_service.resellers_debt_total(company)

    # 6. Найближчі планові платежі (наступні 30 днів)
    upcoming_end = today + timezone.timedelta(days=30)
    upcoming_payments = Transaction.objects.filter(
        company=company,
        status=Transaction.STATUS_PLANNED,
        date_actual__gte=today,
        date_actual__lte=upcoming_end
    ).select_related('account', 'category').order_by('date_actual')[:10]

    # 7. Аналіз та попередження
    warnings = []
    recommendations = []
    health_score = 100

    # Перевірка балансу
    if current_balance < 0:
        warnings.append({
            'type': 'critical',
            'icon': '🔴',
            'message': f'Негативний баланс: {current_balance} грн',
        })
        health_score -= 30
    elif current_balance < Decimal('10000'):
        warnings.append({
            'type': 'warning',
            'icon': '⚠️',
            'message': f'Низький баланс: {current_balance} грн',
        })
        health_score -= 15

    # Перевірка прогнозу
    if forecast_3m < 0:
        warnings.append({
            'type': 'critical',
            'icon': '🔴',
            'message': f'Прогноз через 3 міс. негативний: {forecast_3m} грн',
        })
        health_score -= 25
        recommendations.append({
            'icon': '💡',
            'message': 'Розгляньте можливість скорочення витрат або збільшення доходів',
        })

    # Перевірка прибутковості
    if business_profit_month < 0:
        warnings.append({
            'type': 'warning',
            'icon': '⚠️',
            'message': f'Збиток за місяць: {business_profit_month} грн',
        })
        health_score -= 20
    elif business_profit_month > 0:
        recommendations.append({
            'icon': '✅',
            'message': f'Прибуток за місяць: {business_profit_month} грн — продовжуйте у тому ж дусі!',
        })

    # Перевірка співвідношення особистих витрат
    if business_income > 0:
        personal_ratio = float(personal_expenses_month / business_income * 100)
        if personal_ratio > 50:
            warnings.append({
                'type': 'warning',
                'icon': '⚠️',
                'message': f'Особисті витрати {personal_ratio:.1f}% від доходу — високий рівень',
            })
            health_score -= 10
            recommendations.append({
                'icon': '💡',
                'message': 'Розгляньте можливість оптимізації особистих витрат',
            })

    # Перевірка складу
    if frozen > current_balance * Decimal('2'):
        warnings.append({
            'type': 'info',
            'icon': 'ℹ️',
            'message': f'Заморожено у складі більше ніж подвійний баланс',
        })
        recommendations.append({
            'icon': '💡',
            'message': 'Розгляньте можливість розпродажу повільних товарів',
        })

    # Перевірка низьких залишків розхідників
    try:
        from warehouse.services.consumables import get_low_stock_consumables
        low_stock = get_low_stock_consumables()
        if low_stock:
            warnings.append({
                'type': 'info',
                'icon': 'ℹ️',
                'message': f'Низькі залишки розхідників: {len(low_stock)} позицій',
            })
    except Exception:
        pass

    # Попередження про прострочені борги магазинів
    try:
        from .models import Reseller
        overdue_resellers = []
        for r in Reseller.objects.filter(company=company).exclude(status=Reseller.STATUS_CLOSED):
            od = consignment_service.reseller_overdue_days(r)
            if od > 0:
                overdue_resellers.append((r.name, od))
        if overdue_resellers:
            overdue_resellers.sort(key=lambda x: x[1], reverse=True)
            worst = overdue_resellers[0]
            warnings.append({
                'type': 'warning',
                'icon': '⏰',
                'message': f'Прострочка виплат: {len(overdue_resellers)} магазин(ів), '
                           f'найбільше «{worst[0]}» — {worst[1]} дн',
            })
            health_score -= min(15, len(overdue_resellers) * 5)
    except Exception:
        pass

    # Обмежуємо health_score
    health_score = max(0, min(100, health_score))

    return {
        'current_balance': current_balance,
        'forecast_3m': forecast_3m,
        'business_profit_month': business_profit_month,
        'personal_expenses_month': personal_expenses_month,
        'frozen_in_warehouse': frozen,
        'warehouse_breakdown': warehouse_breakdown,
        'frozen_in_consignment': frozen_consignment,
        'consignment_breakdown': consignment_breakdown,
        'resellers_debt_total': resellers_debt,
        'upcoming_payments': list(upcoming_payments),
        'warnings': warnings,
        'recommendations': recommendations,
        'health_score': health_score,
    }
