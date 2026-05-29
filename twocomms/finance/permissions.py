"""Авторизація для fin.twocomms.shop субдомену.

Доступ до фінансового кабінету мають лише адміністратори:
- автентифіковані користувачі;
- superuser АБО staff.

Сесія спільна для всіх піддоменів `.twocomms.shop` (див. SESSION_COOKIE_DOMAIN),
тому вхід у management/основний сайт діє і тут — але цей декоратор додатково
обмежує доступ лише адмінами.
"""
from __future__ import annotations

from functools import wraps

from django.contrib.auth.decorators import login_required  # noqa: F401 (kept for parity)
from django.shortcuts import redirect, render
from django.urls import reverse


def user_is_finance_admin(user) -> bool:
    """True лише для автентифікованих superuser/staff."""
    if not getattr(user, 'is_authenticated', False):
        return False
    return bool(user.is_superuser or user.is_staff)


def finance_access_required(view_func=None, *, api: bool = False):
    """Декоратор доступу до фінансового кабінету.

    - неавтентифікований → редірект на сторінку входу (із ?next=);
    - автентифікований без прав → 403 (сторінка forbidden, або JSON для api);
    - для ``api=True`` обидва випадки повертають JSON, без редіректу.
    """

    def decorator(func):
        @wraps(func)
        def _wrapped(request, *args, **kwargs):
            user = request.user
            if not getattr(user, 'is_authenticated', False):
                if api:
                    from django.http import JsonResponse
                    return JsonResponse({'ok': False, 'error': 'auth_required'}, status=401)
                login_url = reverse('finance_login')
                return redirect(f"{login_url}?next={request.get_full_path()}")
            if not user_is_finance_admin(user):
                if api:
                    from django.http import JsonResponse
                    return JsonResponse({'ok': False, 'error': 'forbidden'}, status=403)
                return render(
                    request,
                    'finance/forbidden.html',
                    {'username': user.get_username()},
                    status=403,
                )
            return func(request, *args, **kwargs)

        return _wrapped

    if view_func is None:
        return decorator
    return decorator(view_func)
