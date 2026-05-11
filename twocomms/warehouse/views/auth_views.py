"""Login/logout для subdomain (сесія розшарена з основним сайтом)."""
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponseRedirect
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from warehouse.permissions import user_is_warehouse_admin


def _safe_next(url: str) -> str:
    if not url or not url.startswith("/"):
        return "/"
    return url


@require_http_methods(["GET", "POST"])
def login_view(request):
    next_url = _safe_next(request.GET.get("next") or request.POST.get("next") or "/")

    if request.user.is_authenticated:
        if user_is_warehouse_admin(request.user):
            return redirect(next_url)
        # Authenticated, but no access — show login with hint.
        messages.warning(request, "У вас немає прав warehouse_admin")

    if request.method == "POST":
        username = (request.POST.get("username") or "").strip()
        password = request.POST.get("password") or ""
        user = authenticate(request, username=username, password=password)
        if user is None:
            messages.error(request, "Невірний логін або пароль")
        elif not user_is_warehouse_admin(user):
            messages.error(request, "У вас немає доступу до складу")
        else:
            login(request, user)
            return HttpResponseRedirect(next_url)

    return render(request, "warehouse/login.html", {"next": next_url})


def logout_view(request):
    logout(request)
    return redirect("warehouse:login")
