"""
Сервіс для оцінки потенціалу менеджера-кандидата

Аналізує якість роботи кандидата на основі:
- MOSAIC рейтингу (якість обробки)
- KPI (кількість конверсій)
- Якості перезвонів та follow-up
- Повноти обробки клієнтів
- Активного часу роботи

Виводить оцінку від 0 до 10
"""
from decimal import Decimal, ROUND_HALF_UP
from datetime import timedelta

from django.db.models import Count, Q, Avg
from django.utils import timezone

from management.models import (
    Client,
    ClientFollowUp,
    ClientInteractionAttempt,
    ManagementDailyActivity,
    NightlyScoreSnapshot,
)
from management.services.visible_points import CONVERSION_RESULTS


TWO_PLACES = Decimal('0.01')


def calculate_candidate_potential(user) -> dict:
    """
    Розрахувати потенціал кандидата (оцінка 0-10)

    Компоненти оцінки:
    1. Якість обробки (MOSAIC) - 30%
    2. Результативність (конверсії) - 25%
    3. Активність та зусилля - 20%
    4. Якість follow-up - 15%
    5. Повнота даних - 10%

    Returns:
        dict з полями:
        - score: Decimal (0-10)
        - components: dict з оцінками компонентів
        - grade: str (A+, A, B+, B, C+, C, D, F)
        - recommendation: str
        - details: dict з детальною інформацією
    """
    # Отримати всі клієнти кандидата
    all_clients = Client.objects.filter(owner=user)
    total_clients = all_clients.count()

    if total_clients == 0:
        return {
            'score': Decimal('0'),
            'components': {},
            'grade': 'N/A',
            'recommendation': 'Немає даних для оцінки',
            'details': {},
        }

    # 1. Якість обробки (MOSAIC) - 30%
    quality_score = _calculate_quality_score(user, all_clients)

    # 2. Результативність (конверсії) - 25%
    results_score = _calculate_results_score(user, all_clients, total_clients)

    # 3. Активність та зусилля - 20%
    activity_score = _calculate_activity_score(user, total_clients)

    # 4. Якість follow-up - 15%
    followup_score = _calculate_followup_score(user, all_clients)

    # 5. Повнота даних - 10%
    data_quality_score = _calculate_data_quality_score(all_clients)

    # Загальна оцінка (зважена сума)
    total_score = (
        quality_score['score'] * Decimal('0.30') +
        results_score['score'] * Decimal('0.25') +
        activity_score['score'] * Decimal('0.20') +
        followup_score['score'] * Decimal('0.15') +
        data_quality_score['score'] * Decimal('0.10')
    ).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    # Визначити grade
    grade = _determine_grade(total_score)

    # Рекомендація
    recommendation = _generate_recommendation(total_score, {
        'quality': quality_score,
        'results': results_score,
        'activity': activity_score,
        'followup': followup_score,
        'data_quality': data_quality_score,
    })

    return {
        'score': total_score,
        'components': {
            'quality': quality_score,
            'results': results_score,
            'activity': activity_score,
            'followup': followup_score,
            'data_quality': data_quality_score,
        },
        'grade': grade,
        'recommendation': recommendation,
        'details': {
            'total_clients': total_clients,
            'conversions': results_score.get('conversions', 0),
            'conversion_rate': results_score.get('conversion_rate', Decimal('0')),
        },
    }


def _mosaic_to_ten(value: Decimal) -> Decimal:
    """Конвертувати MOSAIC/KPD (0-100) у оцінку 0-10 лінійно з кліпом."""
    ten = (value / Decimal('10')).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    return max(Decimal('0'), min(Decimal('10'), ten))


def _calculate_quality_score(user, all_clients) -> dict:
    """
    Оцінка якості обробки на основі MOSAIC + KPD (нічні snapshot-и)

    Беремо обидва існуючі рейтинги:
    - mosaic_score: загальна якість роботи по 6 осях (результат, процес, follow-up,
      якість даних, верифікація, справедливість джерел)
    - kpd_value: ефективність результату (EWR)
    Вага MOSAIC 70%, KPD 30%, бо MOSAIC ширший.
    score_confidence використовується щоб не переоцінити кандидата з малою вибіркою.
    """
    # Останні 14 днів snapshot-ів (для кандидата вибірка зазвичай мала)
    period_ago = timezone.now().date() - timedelta(days=14)
    snapshots = list(
        NightlyScoreSnapshot.objects.filter(
            owner=user,
            snapshot_date__gte=period_ago,
        ).order_by('-snapshot_date')[:14]
    )

    if not snapshots:
        # Немає snapshot-ів — нейтральна оцінка з позначкою низької впевненості
        return {
            'score': Decimal('5.0'),
            'mosaic_avg': None,
            'kpd_avg': None,
            'confidence': Decimal('0'),
            'note': 'Недостатньо даних MOSAIC/KPD для точної оцінки',
        }

    mosaic_values = [s.mosaic_score for s in snapshots if s.mosaic_score is not None]
    kpd_values = [s.kpd_value for s in snapshots if s.kpd_value is not None]
    confidence_values = [s.score_confidence for s in snapshots if s.score_confidence is not None]

    mosaic_avg = (sum(mosaic_values) / len(mosaic_values)) if mosaic_values else Decimal('50')
    kpd_avg = (sum(kpd_values) / len(kpd_values)) if kpd_values else Decimal('50')
    confidence = (sum(confidence_values) / len(confidence_values)) if confidence_values else Decimal('0')

    # Зважена якість (MOSAIC 70% + KPD 30%), обидва в шкалі 0-100
    blended_100 = (mosaic_avg * Decimal('0.70') + kpd_avg * Decimal('0.30'))
    raw_score = _mosaic_to_ten(blended_100)

    # Корекція на впевненість: при дуже низькій впевненості тягнемо до нейтральних 5.0,
    # щоб не завищити оцінку кандидату з 1-2 днями даних.
    # score_confidence зберігається у шкалі 0..1 (compute_score_confidence), тому
    # БЕЗ ділення на 100 (раніше conf_ratio≈0.005 завжди → корекція зламана).
    conf_ratio = max(Decimal('0'), min(Decimal('1'), confidence))
    # При conf=1 -> повний raw_score; при conf=0 -> 60% raw + 40% нейтраль (5.0)
    neutral = Decimal('5.0')
    adj_factor = Decimal('0.6') + Decimal('0.4') * conf_ratio
    score = (raw_score * adj_factor + neutral * (Decimal('1') - adj_factor)).quantize(
        TWO_PLACES, rounding=ROUND_HALF_UP
    )

    return {
        'score': max(Decimal('0'), min(Decimal('10'), score)),
        'mosaic_avg': mosaic_avg.quantize(TWO_PLACES, rounding=ROUND_HALF_UP),
        'kpd_avg': kpd_avg.quantize(TWO_PLACES, rounding=ROUND_HALF_UP),
        'confidence': confidence.quantize(TWO_PLACES, rounding=ROUND_HALF_UP),
        'snapshots_count': len(snapshots),
    }


def _calculate_results_score(user, all_clients, total_clients) -> dict:
    """
    Оцінка результативності (конверсії)

    Враховує:
    - Кількість конверсій
    - Conversion rate
    - Якість конверсій (ORDER vs TEST_BATCH)
    """
    conversions = all_clients.filter(call_result__in=CONVERSION_RESULTS)
    conversions_count = conversions.count()

    # Conversion rate
    conversion_rate = (Decimal(conversions_count) / Decimal(total_clients) * 100).quantize(
        TWO_PLACES, rounding=ROUND_HALF_UP
    ) if total_clients > 0 else Decimal('0')

    # Базова оцінка на основі conversion rate
    # 5%+ = відмінно, 3-5% = добре, 2-3% = задовільно, <2% = погано
    if conversion_rate >= 5:
        base_score = Decimal('10.0')
    elif conversion_rate >= 4:
        base_score = Decimal('9.0')
    elif conversion_rate >= 3:
        base_score = Decimal('8.0')
    elif conversion_rate >= 2.5:
        base_score = Decimal('7.0')
    elif conversion_rate >= 2:
        base_score = Decimal('6.0')
    elif conversion_rate >= 1.5:
        base_score = Decimal('5.0')
    elif conversion_rate >= 1:
        base_score = Decimal('4.0')
    elif conversion_rate >= 0.5:
        base_score = Decimal('3.0')
    elif conversions_count > 0:
        base_score = Decimal('2.0')
    else:
        base_score = Decimal('1.0')

    # Бонус за кількість конверсій (мотивація робити більше)
    if conversions_count >= 5:
        base_score = min(Decimal('10.0'), base_score + Decimal('1.0'))
    elif conversions_count >= 3:
        base_score = min(Decimal('10.0'), base_score + Decimal('0.5'))

    return {
        'score': base_score,
        'conversions': conversions_count,
        'conversion_rate': conversion_rate,
        'total_clients': total_clients,
    }


def _calculate_activity_score(user, total_clients) -> dict:
    """
    Оцінка активності та зусиль

    Враховує:
    - Активний час роботи
    - Кількість оброблених клієнтів
    - Регулярність роботи
    """
    # Активний час за останні 7 днів
    week_ago = timezone.now().date() - timedelta(days=7)
    activity_records = ManagementDailyActivity.objects.filter(
        user=user,
        date__gte=week_ago
    )

    total_active_seconds = sum(r.active_seconds for r in activity_records)
    total_active_hours = Decimal(total_active_seconds) / Decimal(3600)

    # Кількість днів з активністю
    active_days = activity_records.filter(active_seconds__gt=0).count()

    # Оцінка на основі активного часу
    # 20+ годин/тиждень = відмінно, 15-20 = добре, 10-15 = задовільно
    if total_active_hours >= 20:
        time_score = Decimal('10.0')
    elif total_active_hours >= 15:
        time_score = Decimal('8.0')
    elif total_active_hours >= 10:
        time_score = Decimal('6.0')
    elif total_active_hours >= 5:
        time_score = Decimal('4.0')
    else:
        time_score = Decimal('2.0')

    # Оцінка регулярності (скільки днів працював)
    if active_days >= 5:
        regularity_score = Decimal('10.0')
    elif active_days >= 4:
        regularity_score = Decimal('8.0')
    elif active_days >= 3:
        regularity_score = Decimal('6.0')
    elif active_days >= 2:
        regularity_score = Decimal('4.0')
    else:
        regularity_score = Decimal('2.0')

    # Середня оцінка
    score = ((time_score + regularity_score) / 2).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    return {
        'score': score,
        'active_hours': total_active_hours.quantize(TWO_PLACES, rounding=ROUND_HALF_UP),
        'active_days': active_days,
        'time_score': time_score,
        'regularity_score': regularity_score,
    }


def _calculate_followup_score(user, all_clients) -> dict:
    """
    Оцінка якості follow-up

    Враховує:
    - Чи створюються follow-up
    - Чи виконуються вчасно
    - Якість виконання
    """
    # Всі follow-up кандидата
    followups = ClientFollowUp.objects.filter(owner=user)
    total_followups = followups.count()

    if total_followups == 0:
        # Немає follow-up - погано
        return {
            'score': Decimal('3.0'),
            'total_followups': 0,
            'note': 'Не створює follow-up',
        }

    # Виконані follow-up
    completed = followups.filter(status=ClientFollowUp.Status.DONE).count()

    # Пропущені follow-up
    missed = followups.filter(status=ClientFollowUp.Status.MISSED).count()

    # Completion rate
    completion_rate = (Decimal(completed) / Decimal(total_followups) * 100).quantize(
        TWO_PLACES, rounding=ROUND_HALF_UP
    ) if total_followups > 0 else Decimal('0')

    # Оцінка на основі completion rate
    if completion_rate >= 80:
        score = Decimal('10.0')
    elif completion_rate >= 70:
        score = Decimal('8.0')
    elif completion_rate >= 60:
        score = Decimal('7.0')
    elif completion_rate >= 50:
        score = Decimal('6.0')
    elif completion_rate >= 40:
        score = Decimal('5.0')
    else:
        score = Decimal('4.0')

    # Штраф за пропущені
    if missed > 5:
        score = max(Decimal('1.0'), score - Decimal('2.0'))
    elif missed > 2:
        score = max(Decimal('1.0'), score - Decimal('1.0'))

    return {
        'score': score,
        'total_followups': total_followups,
        'completed': completed,
        'missed': missed,
        'completion_rate': completion_rate,
    }


def _calculate_data_quality_score(all_clients) -> dict:
    """
    Оцінка повноти даних

    Враховує:
    - Чи заповнені важливі поля
    - Чи є коментарі/нотатки
    - Чи вказані причини відмов
    """
    total = all_clients.count()
    if total == 0:
        return {'score': Decimal('0'), 'note': 'Немає клієнтів'}

    # Клієнти з заповненим full_name
    with_name = all_clients.exclude(Q(full_name='') | Q(full_name__isnull=True)).count()

    # Клієнти з website_url
    with_website = all_clients.exclude(Q(website_url='') | Q(website_url__isnull=True)).count()

    # Клієнти з коментарями (нотатка менеджера)
    with_comments = all_clients.exclude(Q(manager_note='') | Q(manager_note__isnull=True)).count()

    # Відсоток заповненості
    name_pct = Decimal(with_name) / Decimal(total)
    website_pct = Decimal(with_website) / Decimal(total)
    comments_pct = Decimal(with_comments) / Decimal(total)

    # Середня заповненість
    avg_completeness = ((name_pct + website_pct + comments_pct) / 3 * 10).quantize(
        TWO_PLACES, rounding=ROUND_HALF_UP
    )

    return {
        'score': avg_completeness,
        'with_name': with_name,
        'with_website': with_website,
        'with_comments': with_comments,
        'completeness_pct': (avg_completeness * 10).quantize(TWO_PLACES, rounding=ROUND_HALF_UP),
    }


def _determine_grade(score: Decimal) -> str:
    """Визначити літерну оцінку"""
    if score >= Decimal('9.5'):
        return 'A+'
    elif score >= Decimal('9.0'):
        return 'A'
    elif score >= Decimal('8.5'):
        return 'A-'
    elif score >= Decimal('8.0'):
        return 'B+'
    elif score >= Decimal('7.5'):
        return 'B'
    elif score >= Decimal('7.0'):
        return 'B-'
    elif score >= Decimal('6.5'):
        return 'C+'
    elif score >= Decimal('6.0'):
        return 'C'
    elif score >= Decimal('5.5'):
        return 'C-'
    elif score >= Decimal('5.0'):
        return 'D+'
    elif score >= Decimal('4.0'):
        return 'D'
    else:
        return 'F'


def _generate_recommendation(score: Decimal, components: dict) -> str:
    """Генерувати рекомендацію на основі оцінки"""
    if score >= Decimal('8.5'):
        return 'Відмінний кандидат! Рекомендується підвищення до Менеджера 1-го рівня.'
    elif score >= Decimal('7.5'):
        return 'Хороший кандидат. Рекомендується підвищення після досягнення умов.'
    elif score >= Decimal('6.5'):
        return 'Задовільний кандидат. Потребує покращення якості роботи.'
    elif score >= Decimal('5.5'):
        return 'Середній кандидат. Рекомендується додаткове навчання та контроль.'
    elif score >= Decimal('4.5'):
        return 'Слабкий кандидат. Потребує серйозного покращення або розгляд звільнення.'
    else:
        return 'Незадовільний кандидат. Не рекомендується підвищення.'
