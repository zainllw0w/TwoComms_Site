"""Дашборд та сторінка сьогоднішніх змін."""
from __future__ import annotations

from datetime import date

from django.contrib import messages
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from warehouse.models import StockMovement, StorageCategory
from warehouse.permissions import warehouse_admin_required
from warehouse.services.finance import (
    frozen_value_by_category,
    frozen_value_by_print,
    total_frozen_value,
)


@warehouse_admin_required
def dashboard(request):
    today = timezone.localdate()
    today_movements = StockMovement.objects.filter(created_at__date=today).order_by(
        "-created_at"
    )[:20]
    unverified_today = StockMovement.objects.filter(
        created_at__date=today, verified=False
    ).count()

    context = {
        "today": today,
        "today_movements": today_movements,
        "unverified_today": unverified_today,
        "total_frozen": total_frozen_value(),
        "frozen_by_category": frozen_value_by_category(),
        "frozen_by_print": frozen_value_by_print(),
        "active_section": "dashboard",
    }
    return render(request, "warehouse/dashboard.html", context)


@warehouse_admin_required
def today_changes(request):
    """Сторінка для верифікації змін за день (deeplink з вечірнього reminder)."""
    target_date_str = request.GET.get("date")
    target_date = timezone.localdate()
    if target_date_str:
        try:
            from datetime import datetime
            target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
        except ValueError:
            pass

    movements = (
        StockMovement.objects.filter(created_at__date=target_date)
        .select_related("created_by", "verified_by", "order", "content_type")
        .order_by("-created_at")
    )
    context = {
        "target_date": target_date,
        "movements": movements,
        "total_count": movements.count(),
        "verified_count": movements.filter(verified=True).count(),
        "active_section": "today",
    }
    return render(request, "warehouse/today_changes.html", context)


@warehouse_admin_required
@require_POST
def verify_today_all(request):
    """Mass-verify всіх сьогоднішніх рухів."""
    today = timezone.localdate()
    qs = StockMovement.objects.filter(created_at__date=today, verified=False)
    count = qs.count()
    qs.update(verified=True, verified_at=timezone.now(), verified_by=request.user)
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"ok": True, "verified": count})
    messages.success(request, f"Перевірено {count} рухів.")
    return redirect("warehouse:today")
