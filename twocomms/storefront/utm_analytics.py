"""
Аналитические функции для UTM Диспетчера.

Содержит функции для расчета статистики по:
- Источникам трафика (utm_source, utm_medium, utm_campaign)
- Креативам (utm_content)
- Воронке конверсий
- Геолокации
- Устройствам и браузерам
- Повторным визитам
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from django.db.models import (
    Count, Sum, Avg, Q, F, DecimalField,
    ExpressionWrapper, DurationField, Max, Min
)
from django.utils import timezone
from .models import UTMSession, UserAction
from orders.models import Order

logger = logging.getLogger(__name__)


def get_period_dates(period: str) -> Tuple[Optional[datetime], Optional[datetime]]:
    """
    Возвращает даты начала и конца периода.
    
    Args:
        period: 'today', 'week', 'month', 'all_time'
    
    Returns:
        tuple: (start_date, end_date) или (None, None) для all_time
    """
    today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    if period == 'today':
        return today, timezone.now()
    elif period == 'week':
        start = today - timedelta(days=7)
        return start, timezone.now()
    elif period == 'month':
        start = today - timedelta(days=30)
        return start, timezone.now()
    elif period == 'all_time':
        return None, None
    else:
        # По умолчанию - сегодня
        return today, timezone.now()


def filter_by_period(queryset, date_field: str, period: str):
    """Фильтрует queryset по периоду"""
    start_date, end_date = get_period_dates(period)
    
    if start_date and end_date:
        filter_kwargs = {
            f'{date_field}__gte': start_date,
            f'{date_field}__lte': end_date,
        }
        return queryset.filter(**filter_kwargs)
    
    return queryset


def get_general_stats(period: str = 'today') -> Dict:
    """
    Возвращает общую статистику по UTM-сессиям.
    
    Returns:
        dict: {
            'total_sessions': int,
            'unique_visitors': int,
            'total_conversions': int,
            'conversion_rate': float,
            'total_revenue': Decimal,
            'avg_order_value': Decimal,
            'total_score': int,
            'avg_score_per_session': float,
        }
    """
    sessions_qs = UTMSession.objects.all()
    sessions_qs = filter_by_period(sessions_qs, 'first_seen', period)
    
    total_sessions = sessions_qs.count()
    
    # Уникальные посетители (по IP)
    unique_visitors = sessions_qs.values('ip_address').distinct().count()
    
    # Конверсии
    converted_sessions = sessions_qs.filter(is_converted=True)
    total_conversions = converted_sessions.count()
    conversion_rate = (total_conversions / total_sessions * 100) if total_sessions > 0 else 0
    
    # Доход (из заказов)
    orders_qs = Order.objects.filter(
        utm_session__in=sessions_qs,
        payment_status='paid'
    )
    revenue_data = orders_qs.aggregate(
        total=Sum('total_sum'),
        avg=Avg('total_sum')
    )
    total_revenue = revenue_data['total'] or Decimal('0')
    avg_order_value = revenue_data['avg'] or Decimal('0')
    
    # Баллы (из действий)
    actions_qs = UserAction.objects.filter(utm_session__in=sessions_qs)
    score_data = actions_qs.aggregate(
        total=Sum('points_earned'),
        avg=Avg('points_earned')
    )
    total_score = score_data['total'] or 0
    avg_score_per_session = (total_score / total_sessions) if total_sessions > 0 else 0
    
    return {
        'total_sessions': total_sessions,
        'unique_visitors': unique_visitors,
        'total_conversions': total_conversions,
        'conversion_rate': round(conversion_rate, 2),
        'total_revenue': total_revenue,
        'avg_order_value': round(avg_order_value, 2),
        'total_score': total_score,
        'avg_score_per_session': round(avg_score_per_session, 2),
    }


def get_sources_stats(period: str = 'today', limit: int = 20) -> List[Dict]:
    """
    Возвращает статистику по источникам трафика (utm_source).
    
    Returns:
        list of dict: [{
            'utm_source': str,
            'sessions': int,
            'conversions': int,
            'conversion_rate': float,
            'revenue': Decimal,
            'avg_order_value': Decimal,
            'total_score': int,
        }]
    """
    sessions_qs = UTMSession.objects.all()
    sessions_qs = filter_by_period(sessions_qs, 'first_seen', period)
    
    # Группируем по utm_source
    sources = sessions_qs.values('utm_source').annotate(
        sessions=Count('id'),
        conversions=Count('id', filter=Q(is_converted=True))
    ).order_by('-sessions')[:limit]
    
    results = []
    for source in sources:
        source_name = source['utm_source'] or 'direct'
        sessions_count = source['sessions']
        conversions_count = source['conversions']
        conversion_rate = (conversions_count / sessions_count * 100) if sessions_count > 0 else 0
        
        # Доход для этого источника
        source_sessions = sessions_qs.filter(utm_source=source['utm_source'])
        orders_qs = Order.objects.filter(
            utm_session__in=source_sessions,
            payment_status='paid'
        )
        revenue_data = orders_qs.aggregate(
            total=Sum('total_sum'),
            avg=Avg('total_sum')
        )
        revenue = revenue_data['total'] or Decimal('0')
        avg_order_value = revenue_data['avg'] or Decimal('0')
        
        # Баллы
        actions_qs = UserAction.objects.filter(utm_session__in=source_sessions)
        total_score = actions_qs.aggregate(total=Sum('points_earned'))['total'] or 0
        
        results.append({
            'utm_source': source_name,
            'sessions': sessions_count,
            'conversions': conversions_count,
            'conversion_rate': round(conversion_rate, 2),
            'revenue': revenue,
            'avg_order_value': round(avg_order_value, 2),
            'total_score': total_score,
        })
    
    return results


def get_campaigns_stats(period: str = 'today', source_filter: Optional[str] = None, limit: int = 20) -> List[Dict]:
    """
    Возвращает статистику по кампаниям (utm_campaign).
    
    Args:
        period: Период
        source_filter: Фильтр по utm_source (опционально)
        limit: Максимальное количество результатов
    
    Returns:
        list of dict
    """
    sessions_qs = UTMSession.objects.all()
    sessions_qs = filter_by_period(sessions_qs, 'first_seen', period)
    
    if source_filter:
        sessions_qs = sessions_qs.filter(utm_source=source_filter)
    
    # Группируем по utm_campaign
    campaigns = sessions_qs.values('utm_campaign', 'utm_source').annotate(
        sessions=Count('id'),
        conversions=Count('id', filter=Q(is_converted=True))
    ).order_by('-sessions')[:limit]
    
    results = []
    for campaign in campaigns:
        campaign_name = campaign['utm_campaign'] or 'N/A'
        source_name = campaign['utm_source'] or 'direct'
        sessions_count = campaign['sessions']
        conversions_count = campaign['conversions']
        conversion_rate = (conversions_count / sessions_count * 100) if sessions_count > 0 else 0
        
        # Доход
        campaign_sessions = sessions_qs.filter(
            utm_campaign=campaign['utm_campaign'],
            utm_source=campaign['utm_source']
        )
        orders_qs = Order.objects.filter(
            utm_session__in=campaign_sessions,
            payment_status='paid'
        )
        revenue = orders_qs.aggregate(total=Sum('total_sum'))['total'] or Decimal('0')
        
        # Баллы
        actions_qs = UserAction.objects.filter(utm_session__in=campaign_sessions)
        total_score = actions_qs.aggregate(total=Sum('points_earned'))['total'] or 0
        
        results.append({
            'utm_campaign': campaign_name,
            'utm_source': source_name,
            'sessions': sessions_count,
            'conversions': conversions_count,
            'conversion_rate': round(conversion_rate, 2),
            'revenue': revenue,
            'total_score': total_score,
        })
    
    return results


def get_content_stats(period: str = 'today', campaign_filter: Optional[str] = None, limit: int = 20) -> List[Dict]:
    """
    Возвращает статистику по креативам/контенту (utm_content).
    """
    sessions_qs = UTMSession.objects.all()
    sessions_qs = filter_by_period(sessions_qs, 'first_seen', period)
    
    if campaign_filter:
        sessions_qs = sessions_qs.filter(utm_campaign=campaign_filter)
    
    # Группируем по utm_content
    contents = sessions_qs.values('utm_content', 'utm_campaign').annotate(
        sessions=Count('id'),
        conversions=Count('id', filter=Q(is_converted=True))
    ).order_by('-sessions')[:limit]
    
    results = []
    for content in contents:
        content_name = content['utm_content'] or 'N/A'
        campaign_name = content['utm_campaign'] or 'N/A'
        sessions_count = content['sessions']
        conversions_count = content['conversions']
        conversion_rate = (conversions_count / sessions_count * 100) if sessions_count > 0 else 0
        
        # Доход
        content_sessions = sessions_qs.filter(
            utm_content=content['utm_content'],
            utm_campaign=content['utm_campaign']
        )
        orders_qs = Order.objects.filter(
            utm_session__in=content_sessions,
            payment_status='paid'
        )
        revenue = orders_qs.aggregate(total=Sum('total_sum'))['total'] or Decimal('0')
        
        # Баллы
        actions_qs = UserAction.objects.filter(utm_session__in=content_sessions)
        total_score = actions_qs.aggregate(total=Sum('points_earned'))['total'] or 0
        
        results.append({
            'utm_content': content_name,
            'utm_campaign': campaign_name,
            'sessions': sessions_count,
            'conversions': conversions_count,
            'conversion_rate': round(conversion_rate, 2),
            'revenue': revenue,
            'total_score': total_score,
        })
    
    return results


def get_funnel_stats(period: str = 'today') -> Dict:
    """
    Возвращает статистику по воронке конверсий.
    
    Returns:
        dict: {
            'total': int,
            'product_views': int,
            'add_to_cart': int,
            'initiate_checkout': int,
            'leads': int,
            'purchases': int,
            'product_views_rate': float,
            'add_to_cart_rate': float,
            'checkout_rate': float,
            'lead_rate': float,
            'purchase_rate': float,
        }
    """
    sessions_qs = UTMSession.objects.all()
    sessions_qs = filter_by_period(sessions_qs, 'first_seen', period)
    total_sessions = sessions_qs.count()
    
    if total_sessions == 0:
        return {
            'total': 0,
            'product_views': 0,
            'add_to_cart': 0,
            'initiate_checkout': 0,
            'leads': 0,
            'purchases': 0,
            'product_views_rate': 0,
            'add_to_cart_rate': 0,
            'checkout_rate': 0,
            'lead_rate': 0,
            'purchase_rate': 0,
        }
    
    actions_qs = UserAction.objects.filter(utm_session__in=sessions_qs)
    
    # Подсчитываем уникальные сессии для каждого этапа
    product_views = actions_qs.filter(action_type='product_view').values('utm_session').distinct().count()
    add_to_cart = actions_qs.filter(action_type='add_to_cart').values('utm_session').distinct().count()
    initiate_checkout = actions_qs.filter(action_type='initiate_checkout').values('utm_session').distinct().count()
    leads = actions_qs.filter(action_type='lead').values('utm_session').distinct().count()
    purchases = actions_qs.filter(action_type='purchase').values('utm_session').distinct().count()
    
    return {
        'total': total_sessions,
        'product_views': product_views,
        'add_to_cart': add_to_cart,
        'initiate_checkout': initiate_checkout,
        'leads': leads,
        'purchases': purchases,
        'product_views_rate': round((product_views / total_sessions * 100), 2),
        'add_to_cart_rate': round((add_to_cart / total_sessions * 100), 2),
        'checkout_rate': round((initiate_checkout / total_sessions * 100), 2),
        'lead_rate': round((leads / total_sessions * 100), 2),
        'purchase_rate': round((purchases / total_sessions * 100), 2),
    }


def get_geo_stats(period: str = 'today', limit: int = 20) -> List[Dict]:
    """
    Возвращает статистику по геолокации (страны и города).
    """
    sessions_qs = UTMSession.objects.all()
    sessions_qs = filter_by_period(sessions_qs, 'first_seen', period)
    
    # По странам
    countries = sessions_qs.values('country', 'country_name').annotate(
        sessions=Count('id'),
        conversions=Count('id', filter=Q(is_converted=True))
    ).order_by('-sessions')[:limit]
    
    countries_list = []
    for country in countries:
        country_name = country['country_name'] or country['country'] or 'Unknown'
        sessions_count = country['sessions']
        conversions_count = country['conversions']
        conversion_rate = (conversions_count / sessions_count * 100) if sessions_count > 0 else 0
        
        countries_list.append({
            'country': country_name,
            'code': country['country'],
            'sessions': sessions_count,
            'conversions': conversions_count,
            'conversion_rate': round(conversion_rate, 2),
        })
    
    # По городам
    cities = sessions_qs.values('city', 'country_name').annotate(
        sessions=Count('id'),
        conversions=Count('id', filter=Q(is_converted=True))
    ).order_by('-sessions')[:limit]
    
    cities_list = []
    for city in cities:
        city_name = city['city'] or 'Unknown'
        country_name = city['country_name'] or 'Unknown'
        sessions_count = city['sessions']
        conversions_count = city['conversions']
        conversion_rate = (conversions_count / sessions_count * 100) if sessions_count > 0 else 0
        
        cities_list.append({
            'city': city_name,
            'country': country_name,
            'sessions': sessions_count,
            'conversions': conversions_count,
            'conversion_rate': round(conversion_rate, 2),
        })
    
    return {
        'countries': countries_list,
        'cities': cities_list,
    }


def get_device_stats(period: str = 'today') -> List[Dict]:
    """
    Возвращает статистику по типам устройств.
    """
    sessions_qs = UTMSession.objects.all()
    sessions_qs = filter_by_period(sessions_qs, 'first_seen', period)
    
    devices = sessions_qs.values('device_type').annotate(
        sessions=Count('id'),
        conversions=Count('id', filter=Q(is_converted=True))
    ).order_by('-sessions')
    
    results = []
    for device in devices:
        device_type = device['device_type'] or 'unknown'
        sessions_count = device['sessions']
        conversions_count = device['conversions']
        conversion_rate = (conversions_count / sessions_count * 100) if sessions_count > 0 else 0
        
        results.append({
            'device_type': device_type.title(),
            'sessions': sessions_count,
            'conversions': conversions_count,
            'conversion_rate': round(conversion_rate, 2),
        })
    
    return results


def get_browser_stats(period: str = 'today', limit: int = 10) -> List[Dict]:
    """
    Возвращает статистику по браузерам.
    """
    sessions_qs = UTMSession.objects.all()
    sessions_qs = filter_by_period(sessions_qs, 'first_seen', period)
    
    browsers = sessions_qs.values('browser_name').annotate(
        sessions=Count('id'),
        conversions=Count('id', filter=Q(is_converted=True))
    ).order_by('-sessions')[:limit]
    
    results = []
    for browser in browsers:
        browser_name = browser['browser_name'] or 'Unknown'
        sessions_count = browser['sessions']
        conversions_count = browser['conversions']
        conversion_rate = (conversions_count / sessions_count * 100) if sessions_count > 0 else 0
        
        results.append({
            'browser_name': browser_name,
            'sessions': sessions_count,
            'conversions': conversions_count,
            'conversion_rate': round(conversion_rate, 2),
        })
    
    return results


def get_os_stats(period: str = 'today', limit: int = 10) -> List[Dict]:
    """
    Возвращает статистику по операционным системам.
    """
    sessions_qs = UTMSession.objects.all()
    sessions_qs = filter_by_period(sessions_qs, 'first_seen', period)
    
    os_list = sessions_qs.values('os_name').annotate(
        sessions=Count('id'),
        conversions=Count('id', filter=Q(is_converted=True))
    ).order_by('-sessions')[:limit]
    
    results = []
    for os in os_list:
        os_name = os['os_name'] or 'Unknown'
        sessions_count = os['sessions']
        conversions_count = os['conversions']
        conversion_rate = (conversions_count / sessions_count * 100) if sessions_count > 0 else 0
        
        results.append({
            'os_name': os_name,
            'sessions': sessions_count,
            'conversions': conversions_count,
            'conversion_rate': round(conversion_rate, 2),
        })
    
    return results


def get_returning_visitors_stats(period: str = 'today') -> Dict:
    """
    Возвращает статистику по повторным визитам.
    """
    sessions_qs = UTMSession.objects.all()
    sessions_qs = filter_by_period(sessions_qs, 'first_seen', period)
    
    total_sessions = sessions_qs.count()
    first_visits = sessions_qs.filter(is_first_visit=True).count()
    returning_visits = sessions_qs.filter(is_returning_visitor=True).count()
    
    return {
        'total_sessions': total_sessions,
        'first_visits': first_visits,
        'returning_visits': returning_visits,
        'first_visits_rate': round((first_visits / total_sessions * 100), 2) if total_sessions > 0 else 0,
        'returning_visits_rate': round((returning_visits / total_sessions * 100), 2) if total_sessions > 0 else 0,
    }


def get_recent_sessions(period: str = 'today', limit: int = 50) -> List:
    """
    Возвращает список последних UTM-сессий.
    """
    sessions_qs = UTMSession.objects.select_related('session').prefetch_related('actions', 'orders')
    sessions_qs = filter_by_period(sessions_qs, 'first_seen', period)
    sessions_qs = sessions_qs.order_by('-first_seen')[:limit]
    
    return list(sessions_qs)
