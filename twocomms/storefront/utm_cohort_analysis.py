"""
Когортный анализ для UTM Dispatcher.

Анализирует retention пользователей, LTV (Lifetime Value),
и поведение когорт по источникам трафика.
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional
from collections import defaultdict

from django.db.models import Count, Sum, Avg, Q, F, Min, Max
from django.utils import timezone
from .models import UTMSession, UserAction
from orders.models import Order

logger = logging.getLogger(__name__)


def get_cohort_start_date(date, cohort_type='week'):
    """
    Возвращает начальную дату когорты.
    
    Args:
        date: Дата для определения когорты
        cohort_type: 'day', 'week', 'month'
    
    Returns:
        datetime: Начало когорты
    """
    if cohort_type == 'day':
        return date.replace(hour=0, minute=0, second=0, microsecond=0)
    elif cohort_type == 'week':
        # Начало недели (понедельник)
        start = date - timedelta(days=date.weekday())
        return start.replace(hour=0, minute=0, second=0, microsecond=0)
    elif cohort_type == 'month':
        return date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        return date.replace(hour=0, minute=0, second=0, microsecond=0)


def get_cohort_analysis(
    start_date: datetime,
    end_date: datetime,
    cohort_type: str = 'week',
    metric: str = 'retention',
    utm_source: Optional[str] = None
) -> Dict:
    """
    Выполняет когортный анализ.
    
    Args:
        start_date: Начальная дата анализа
        end_date: Конечная дата анализа
        cohort_type: 'day', 'week', 'month'
        metric: 'retention', 'ltv', 'orders', 'revenue'
        utm_source: Фильтр по источнику (опционально)
    
    Returns:
        dict: {
            'cohorts': [список когорт],
            'periods': [список периодов],
            'matrix': [[значения]],
            'totals': {агрегаты по когортам}
        }
    """
    try:
        # Получаем все сессии за период
        sessions_qs = UTMSession.objects.filter(
            first_seen__gte=start_date,
            first_seen__lte=end_date
        )
        
        if utm_source:
            sessions_qs = sessions_qs.filter(utm_source=utm_source)
        
        # Группируем сессии по когортам
        cohorts_data = defaultdict(lambda: {
            'sessions': set(),
            'converted_sessions': set(),
            'users_with_orders': set(),
        })
        
        for session in sessions_qs.iterator():
            cohort_start = get_cohort_start_date(session.first_seen, cohort_type)
            cohort_key = cohort_start.strftime('%Y-%m-%d')
            
            cohorts_data[cohort_key]['sessions'].add(session.session_key)
            if session.is_converted:
                cohorts_data[cohort_key]['converted_sessions'].add(session.session_key)
        
        # Определяем периоды для анализа (недели после когорты)
        max_periods = 12  # 12 недель/месяцев/дней после начала когорты
        
        cohorts = sorted(cohorts_data.keys())
        matrix = []
        totals = []
        
        for cohort_key in cohorts:
            cohort_start = datetime.strptime(cohort_key, '%Y-%m-%d')
            cohort_start = timezone.make_aware(cohort_start)
            cohort_sessions = cohorts_data[cohort_key]['sessions']
            cohort_size = len(cohort_sessions)
            
            row = []
            cohort_revenue = Decimal('0')
            cohort_orders = 0
            
            for period in range(max_periods):
                # Определяем диапазон периода
                if cohort_type == 'day':
                    period_start = cohort_start + timedelta(days=period)
                    period_end = cohort_start + timedelta(days=period + 1)
                elif cohort_type == 'week':
                    period_start = cohort_start + timedelta(weeks=period)
                    period_end = cohort_start + timedelta(weeks=period + 1)
                else:  # month
                    # Упрощенный расчет (30 дней)
                    period_start = cohort_start + timedelta(days=period * 30)
                    period_end = cohort_start + timedelta(days=(period + 1) * 30)
                
                if period_end > timezone.now():
                    break
                
                if metric == 'retention':
                    # Retention: сколько сессий из когорты были активны в этом периоде
                    active_sessions = UTMSession.objects.filter(
                        session_key__in=cohort_sessions,
                        last_seen__gte=period_start,
                        last_seen__lt=period_end
                    ).count()
                    
                    value = (active_sessions / cohort_size * 100) if cohort_size > 0 else 0
                    row.append(round(value, 1))
                
                elif metric == 'ltv':
                    # LTV: суммарный доход от сессий когорты за период
                    period_revenue = Order.objects.filter(
                        utm_session__session_key__in=cohort_sessions,
                        payment_status='paid',
                        created__gte=period_start,
                        created__lt=period_end
                    ).aggregate(total=Sum('total_sum'))['total'] or Decimal('0')
                    
                    cohort_revenue += period_revenue
                    ltv_per_user = (cohort_revenue / cohort_size) if cohort_size > 0 else Decimal('0')
                    row.append(float(ltv_per_user))
                
                elif metric == 'orders':
                    # Количество заказов за период
                    period_orders = Order.objects.filter(
                        utm_session__session_key__in=cohort_sessions,
                        created__gte=period_start,
                        created__lt=period_end
                    ).count()
                    
                    cohort_orders += period_orders
                    row.append(cohort_orders)
                
                elif metric == 'revenue':
                    # Кумулятивный доход за период
                    period_revenue = Order.objects.filter(
                        utm_session__session_key__in=cohort_sessions,
                        payment_status='paid',
                        created__gte=period_start,
                        created__lt=period_end
                    ).aggregate(total=Sum('total_sum'))['total'] or Decimal('0')
                    
                    cohort_revenue += period_revenue
                    row.append(float(cohort_revenue))
            
            matrix.append(row)
            totals.append({
                'cohort': cohort_key,
                'size': cohort_size,
                'converted': len(cohorts_data[cohort_key]['converted_sessions']),
                'revenue': float(cohort_revenue),
                'orders': cohort_orders
            })
        
        # Генерируем названия периодов
        period_labels = []
        for i in range(max_periods):
            if cohort_type == 'day':
                period_labels.append(f'День {i}')
            elif cohort_type == 'week':
                period_labels.append(f'Тиждень {i}')
            else:
                period_labels.append(f'Місяць {i}')
        
        return {
            'cohorts': cohorts,
            'periods': period_labels[:len(matrix[0]) if matrix else 0],
            'matrix': matrix,
            'totals': totals,
            'metric': metric,
            'cohort_type': cohort_type
        }
    
    except Exception as e:
        logger.error(f"Error in cohort analysis: {e}", exc_info=True)
        return {
            'cohorts': [],
            'periods': [],
            'matrix': [],
            'totals': [],
            'error': str(e)
        }


def get_source_ltv_comparison(period: str = 'month') -> List[Dict]:
    """
    Сравнивает LTV (Lifetime Value) по источникам трафика.
    
    Args:
        period: 'week', 'month', 'all_time'
    
    Returns:
        list of dict: [{
            'utm_source': str,
            'total_sessions': int,
            'converted_sessions': int,
            'total_revenue': Decimal,
            'ltv_per_session': Decimal,
            'avg_order_value': Decimal,
            'orders_per_session': float
        }]
    """
    from .utm_analytics import get_period_dates
    
    start_date, end_date = get_period_dates(period)
    
    sessions_qs = UTMSession.objects.all()
    if start_date and end_date:
        sessions_qs = sessions_qs.filter(first_seen__gte=start_date, first_seen__lte=end_date)
    
    # Группируем по источникам
    sources = sessions_qs.values('utm_source').annotate(
        total_sessions=Count('id'),
        converted_sessions=Count('id', filter=Q(is_converted=True))
    ).order_by('-total_sessions')
    
    results = []
    for source in sources:
        utm_source = source['utm_source'] or 'direct'
        
        # Получаем все заказы из этого источника
        orders = Order.objects.filter(
            utm_session__utm_source=source['utm_source'],
            payment_status='paid'
        )
        
        if start_date and end_date:
            orders = orders.filter(created__gte=start_date, created__lte=end_date)
        
        revenue_data = orders.aggregate(
            total_revenue=Sum('total_sum'),
            avg_order=Avg('total_sum'),
            total_orders=Count('id')
        )
        
        total_revenue = revenue_data['total_revenue'] or Decimal('0')
        avg_order = revenue_data['avg_order'] or Decimal('0')
        total_orders = revenue_data['total_orders'] or 0
        
        total_sessions = source['total_sessions']
        ltv_per_session = (total_revenue / total_sessions) if total_sessions > 0 else Decimal('0')
        orders_per_session = (total_orders / total_sessions) if total_sessions > 0 else 0
        
        results.append({
            'utm_source': utm_source,
            'total_sessions': total_sessions,
            'converted_sessions': source['converted_sessions'],
            'total_revenue': total_revenue,
            'ltv_per_session': round(ltv_per_session, 2),
            'avg_order_value': round(avg_order, 2),
            'orders_per_session': round(orders_per_session, 2),
            'total_orders': total_orders
        })
    
    # Сортируем по LTV
    results.sort(key=lambda x: x['ltv_per_session'], reverse=True)
    
    return results


def get_repeat_purchase_rate(period: str = 'month', utm_source: Optional[str] = None) -> Dict:
    """
    Рассчитывает процент повторных покупок.
    
    Args:
        period: 'week', 'month', 'all_time'
        utm_source: Фильтр по источнику
    
    Returns:
        dict: {
            'total_customers': int,
            'repeat_customers': int,
            'repeat_rate': float,
            'avg_orders_per_customer': float,
            'avg_time_between_orders': int (days)
        }
    """
    from .utm_analytics import get_period_dates
    
    start_date, end_date = get_period_dates(period)
    
    # Получаем заказы за период
    orders_qs = Order.objects.filter(payment_status='paid')
    
    if start_date and end_date:
        orders_qs = orders_qs.filter(created__gte=start_date, created__lte=end_date)
    
    # Фильтруем по UTM источнику, если указан
    if utm_source:
        orders_qs = orders_qs.filter(utm_session__utm_source=utm_source)
    
    # Считаем уникальных клиентов по email или phone
    # Используем комбинацию email и phone для идентификации клиента
    customers_data = orders_qs.values('email', 'phone').annotate(
        order_count=Count('id'),
        first_order=Min('created'),
        last_order=Max('created')
    )
    
    total_customers = customers_data.count()
    repeat_customers = sum(1 for item in customers_data if item['order_count'] > 1)
    total_orders = sum(item['order_count'] for item in customers_data)
    
    repeat_rate = (repeat_customers / total_customers * 100) if total_customers > 0 else 0
    avg_orders = (total_orders / total_customers) if total_customers > 0 else 0
    
    # Средний интервал между заказами для клиентов с повторными покупками
    time_between_orders = []
    for customer in customers_data:
        if customer['order_count'] > 1:
            # Получаем все заказы этого клиента
            customer_orders = orders_qs.filter(
                Q(email=customer['email']) | Q(phone=customer['phone'])
            ).order_by('created')
            
            orders_list = list(customer_orders)
            if len(orders_list) >= 2:
                for i in range(1, len(orders_list)):
                    delta = (orders_list[i].created - orders_list[i-1].created).days
                    if delta > 0:  # Игнорируем заказы в один день
                        time_between_orders.append(delta)
    
    avg_time_between = sum(time_between_orders) / len(time_between_orders) if time_between_orders else 0
    
    return {
        'total_customers': total_customers,
        'repeat_customers': repeat_customers,
        'one_time_customers': total_customers - repeat_customers,
        'repeat_rate': round(repeat_rate, 2),
        'avg_orders_per_customer': round(avg_orders, 2),
        'avg_time_between_orders': round(avg_time_between, 0),
        'total_orders': total_orders
    }


def get_campaign_ab_test_results(campaign_name: str, period: str = 'month') -> Dict:
    """
    Анализирует результаты A/B тестирования креативов в рамках одной кампании.
    
    Args:
        campaign_name: Название кампании
        period: 'week', 'month', 'all_time'
    
    Returns:
        dict: {
            'campaign': str,
            'variants': [{
                'utm_content': str,
                'sessions': int,
                'conversions': int,
                'conversion_rate': float,
                'revenue': Decimal,
                'avg_order_value': Decimal,
                'confidence': float  # Статистическая значимость
            }],
            'winner': str,  # Лучший вариант
            'winner_lift': float  # Насколько лучше в %
        }
    """
    from .utm_analytics import get_period_dates
    import math
    
    start_date, end_date = get_period_dates(period)
    
    sessions_qs = UTMSession.objects.filter(utm_campaign=campaign_name)
    
    if start_date and end_date:
        sessions_qs = sessions_qs.filter(first_seen__gte=start_date, first_seen__lte=end_date)
    
    # Группируем по utm_content (варианты креативов)
    variants_data = sessions_qs.values('utm_content').annotate(
        sessions=Count('id'),
        conversions=Count('id', filter=Q(is_converted=True))
    ).filter(utm_content__isnull=False).order_by('-sessions')
    
    variants = []
    
    for variant in variants_data:
        utm_content = variant['utm_content']
        sessions_count = variant['sessions']
        conversions_count = variant['conversions']
        
        conversion_rate = (conversions_count / sessions_count * 100) if sessions_count > 0 else 0
        
        # Получаем доход
        revenue_data = Order.objects.filter(
            utm_session__utm_campaign=campaign_name,
            utm_session__utm_content=utm_content,
            payment_status='paid'
        )
        
        if start_date and end_date:
            revenue_data = revenue_data.filter(created__gte=start_date, created__lte=end_date)
        
        revenue_stats = revenue_data.aggregate(
            total=Sum('total_sum'),
            avg=Avg('total_sum')
        )
        
        revenue = revenue_stats['total'] or Decimal('0')
        avg_order = revenue_stats['avg'] or Decimal('0')
        
        # Упрощенный расчет статистической значимости (Z-тест для пропорций)
        # Для полноценного A/B теста нужна более сложная статистика
        p = conversion_rate / 100
        se = math.sqrt(p * (1 - p) / sessions_count) if sessions_count > 0 else 0
        confidence = round(min(1.0 - se * 1.96, 1.0) * 100, 1) if se > 0 else 0
        
        variants.append({
            'utm_content': utm_content,
            'sessions': sessions_count,
            'conversions': conversions_count,
            'conversion_rate': round(conversion_rate, 2),
            'revenue': revenue,
            'avg_order_value': round(avg_order, 2),
            'confidence': confidence
        })
    
    # Определяем победителя (по CR%)
    if variants:
        winner = max(variants, key=lambda x: x['conversion_rate'])
        baseline = min(variants, key=lambda x: x['conversion_rate'])
        
        if baseline['conversion_rate'] > 0:
            lift = ((winner['conversion_rate'] - baseline['conversion_rate']) / baseline['conversion_rate'] * 100)
        else:
            lift = 0
        
        return {
            'campaign': campaign_name,
            'variants': variants,
            'winner': winner['utm_content'],
            'winner_lift': round(lift, 2),
            'total_sessions': sum(v['sessions'] for v in variants),
            'total_conversions': sum(v['conversions'] for v in variants)
        }
    
    return {
        'campaign': campaign_name,
        'variants': [],
        'winner': None,
        'winner_lift': 0,
        'total_sessions': 0,
        'total_conversions': 0
    }
