"""
Views для системи рівнів менеджерів
"""
from decimal import Decimal
from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from management.models import ManagerLevel, ManagerLevelHistory, WeeklySalaryAccrual
from management.services.manager_levels import (
    get_current_level,
    get_level_display_name,
    get_level_description,
    promote_manager,
    demote_manager,
    has_permission,
)
from management.services.weekly_kpi import (
    get_current_week_kpi_status,
    get_weekly_kpi_history,
)
from management.services.level_progression import (
    get_progression_status,
    get_unlocked_features,
    get_locked_features,
)
from management.views import user_is_management

User = get_user_model()


@login_required(login_url='management_login')
def manager_profile(request):
    """Профіль менеджера з рівнем, KPI та прогресом"""
    if not user_is_management(request.user):
        return redirect('management_login')

    user = request.user
    level = get_current_level(user)

    if not level:
        context = {
            'has_level': False,
            'message': 'У вас ще не призначено рівень менеджера',
        }
        return render(request, 'management/profile.html', context)

    level_desc = get_level_description(level.level)
    progression = get_progression_status(user)
    kpi_status = get_current_week_kpi_status(user)
    kpi_history = get_weekly_kpi_history(user, weeks=4)

    history = ManagerLevelHistory.objects.filter(user=user).order_by('-changed_at')[:10]

    context = {
        'has_level': True,
        'level': level,
        'level_desc': level_desc,
        'progression': progression,
        'kpi_status': kpi_status,
        'kpi_history': kpi_history,
        'history': history,
        'unlocked_features': get_unlocked_features(level.level),
        'locked_features': get_locked_features(level.level),
    }

    return render(request, 'management/profile.html', context)


@login_required(login_url='management_login')
@require_GET
def manager_progression_api(request):
    """API для отримання прогресу до наступного рівня"""
    if not user_is_management(request.user):
        return JsonResponse({'success': False, 'error': 'Доступ заборонено'}, status=403)

    progression = get_progression_status(request.user)

    return JsonResponse({
        'success': True,
        'progression': {
            'current_level': progression['current_level'],
            'next_level': progression['next_level'],
            'requirements_met': progression['requirements_met'],
            'progress_pct': progression['progress_pct'],
            'description': progression['description'],
            'conditions': progression['conditions'],
        }
    })


@login_required(login_url='management_login')
@require_GET
def manager_weekly_kpi_api(request):
    """API для отримання поточного тижневого KPI"""
    if not user_is_management(request.user):
        return JsonResponse({'success': False, 'error': 'Доступ заборонено'}, status=403)

    kpi_status = get_current_week_kpi_status(request.user)

    return JsonResponse({
        'success': True,
        'kpi': {
            'week_start': kpi_status['week_start'].isoformat(),
            'week_end': kpi_status['week_end'].isoformat(),
            'conversions': kpi_status['conversions'],
            'conversions_target': kpi_status['conversions_target'],
            'conversions_progress_pct': kpi_status['conversions_progress_pct'],
            'processed_clients': kpi_status['processed_clients'],
            'kpi_multiplier': str(kpi_status['kpi_multiplier']),
            'projected_salary': str(kpi_status['projected_salary']),
            'base_salary': str(kpi_status['base_salary']),
            'kpi_status': kpi_status['kpi_status'],
            'days_remaining': kpi_status['days_remaining'],
        }
    })


@login_required(login_url='management_login')
@require_POST
def admin_assign_level_api(request):
    """API для призначення рівня менеджеру (тільки для адміна)"""
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Доступ тільки для адміністраторів'}, status=403)

    try:
        user_id = int(request.POST.get('user_id'))
        level = request.POST.get('level')
        weekly_salary = int(request.POST.get('weekly_salary', 0))
        commission_percent = Decimal(request.POST.get('commission_percent', '0'))
        start_date_str = request.POST.get('start_date')
        comment = request.POST.get('comment', '')

        if start_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        else:
            start_date = timezone.now().date()

        user = User.objects.get(id=user_id)

        manager_level = promote_manager(
            user=user,
            new_level=level,
            promoted_by=request.user,
            weekly_salary=weekly_salary,
            commission_percent=commission_percent,
            start_date=start_date,
            comment=comment,
        )

        return JsonResponse({
            'success': True,
            'message': f'Рівень успішно призначено: {get_level_display_name(level)}',
            'level': {
                'id': manager_level.id,
                'level': manager_level.level,
                'level_display': get_level_display_name(manager_level.level),
                'weekly_salary': manager_level.weekly_salary_uah,
                'commission_percent': str(manager_level.commission_percent),
            }
        })

    except User.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Користувача не знайдено'}, status=404)
    except ValueError as e:
        return JsonResponse({'success': False, 'error': f'Помилка валідації: {str(e)}'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Помилка: {str(e)}'}, status=500)


@login_required(login_url='management_login')
@require_GET
def admin_managers_list_api(request):
    """API для отримання списку всіх менеджерів з рівнями"""
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Доступ тільки для адміністраторів'}, status=403)

    managers = User.objects.filter(
        userprofile__is_manager=True
    ).select_related('manager_level', 'userprofile').order_by('username')

    managers_data = []
    for user in managers:
        level = get_current_level(user)
        progression = get_progression_status(user)

        managers_data.append({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'level': level.level if level else None,
            'level_display': get_level_display_name(level.level) if level else 'Немає рівня',
            'weekly_salary': level.weekly_salary_uah if level else 0,
            'commission_percent': str(level.commission_percent) if level else '0',
            'assigned_at': level.assigned_at.isoformat() if level else None,
            'is_active': level.is_active if level else False,
            'progress_pct': progression['progress_pct'],
            'requirements_met': progression['requirements_met'],
        })

    return JsonResponse({
        'success': True,
        'managers': managers_data,
    })
