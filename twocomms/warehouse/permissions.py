"""Авторизація для warehouse subdomain.

Доступ потребує:
- автентифікації;
- is_staff;
- членства в Group 'warehouse_admins' (АБО superuser).
"""
from __future__ import annotations

from functools import wraps

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.urls import reverse

WAREHOUSE_GROUP_NAME = "warehouse_admins"


def user_is_warehouse_admin(user) -> bool:
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if not user.is_staff:
        return False
    return user.groups.filter(name=WAREHOUSE_GROUP_NAME).exists()


def warehouse_admin_required(view_func=None, *, raise_403: bool = False):
    """Декоратор: вимагає warehouse_admin доступу.

    За замовчуванням редіректить на login. Якщо raise_403=True — 403.
    """

    def decorator(func):
        @wraps(func)
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                login_url = reverse("warehouse:login")
                return redirect(f"{login_url}?next={request.get_full_path()}")
            if not user_is_warehouse_admin(request.user):
                if raise_403:
                    return HttpResponseForbidden(
                        "У вас немає доступу до складу. Зверніться до адміністратора."
                    )
                # render simple forbidden page
                from django.shortcuts import render
                return render(
                    request,
                    "warehouse/forbidden.html",
                    {"username": request.user.username},
                    status=403,
                )
            return func(request, *args, **kwargs)

        return _wrapped

    if view_func is None:
        return decorator
    return decorator(view_func)
