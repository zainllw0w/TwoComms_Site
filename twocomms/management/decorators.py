"""
Декоратори для перевірки рівня доступу менеджерів
"""
from functools import wraps

from django.http import JsonResponse
from django.shortcuts import redirect

from management.services.manager_levels import get_current_level, has_required_level, has_permission


def require_manager_level(min_level: str, redirect_to='management_home'):
    """
    Декоратор для перевірки мінімального рівня менеджера

    Args:
        min_level: Мінімальний рівень (з ManagerLevel.Level)
        redirect_to: URL name для редиректу (для HTML views)

    Usage:
        @require_manager_level('level_2')
        def process_base_lead(request, lead_id):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Перевірка аутентифікації
            if not request.user.is_authenticated:
                return redirect('management_login')

            # Суперюзери та staff мають повний доступ
            if request.user.is_superuser or request.user.is_staff:
                return view_func(request, *args, **kwargs)

            # Перевірка рівня
            user_level = get_current_level(request.user)

            if not user_level or not user_level.is_active:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'error': 'У вас немає рівня менеджера'
                    }, status=403)
                return redirect(redirect_to)

            if not has_required_level(user_level.level, min_level):
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'error': f'Недостатній рівень доступу. Потрібен рівень: {min_level}'
                    }, status=403)
                return redirect(redirect_to)

            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def require_permission(permission: str, redirect_to='management_home'):
    """
    Декоратор для перевірки конкретного права доступу

    Args:
        permission: Назва права (напр. 'can_view_payouts', 'can_run_parsing')
        redirect_to: URL name для редиректу

    Usage:
        @require_permission('can_run_parsing')
        def start_parsing(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('management_login')

            if not has_permission(request.user, permission):
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'error': f'Недостатньо прав: {permission}'
                    }, status=403)
                return redirect(redirect_to)

            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
