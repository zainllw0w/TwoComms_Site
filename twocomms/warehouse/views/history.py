"""Історія рухів."""
from __future__ import annotations

from django.contrib import messages
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from warehouse.models import MovementReason, StockMovement
from warehouse.permissions import warehouse_admin_required


@warehouse_admin_required
def history_list(request):
    qs = (
        StockMovement.objects.select_related(
            "created_by", "verified_by", "order", "content_type"
        )
        .order_by("-created_at")
    )

    reason = request.GET.get("reason")
    if reason and reason in dict(MovementReason.choices):
        qs = qs.filter(reason=reason)

    verified = request.GET.get("verified")
    if verified == "yes":
        qs = qs.filter(verified=True)
    elif verified == "no":
        qs = qs.filter(verified=False)

    date_from = request.GET.get("date_from")
    date_to = request.GET.get("date_to")
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)

    paginator = Paginator(qs, 50)
    page = paginator.get_page(request.GET.get("page"))

    context = {
        "page": page,
        "reasons": MovementReason.choices,
        "filter_reason": reason or "",
        "filter_verified": verified or "",
        "filter_date_from": date_from or "",
        "filter_date_to": date_to or "",
        "active_section": "history",
    }
    return render(request, "warehouse/history.html", context)


@warehouse_admin_required
@require_POST
def history_verify(request):
    """AJAX: відмітити рух як перевірений (один або декілька)."""
    ids = request.POST.getlist("movement_ids[]")
    if not ids:
        single = request.POST.get("movement_id")
        if single:
            ids = [single]
    try:
        ids_int = [int(x) for x in ids if str(x).isdigit()]
    except ValueError:
        ids_int = []
    if not ids_int:
        return JsonResponse({"ok": False, "error": "no ids"}, status=400)

    qs = StockMovement.objects.filter(pk__in=ids_int, verified=False)
    count = qs.count()
    qs.update(verified=True, verified_at=timezone.now(), verified_by=request.user)

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"ok": True, "verified": count})
    messages.success(request, f"Перевірено {count} рухів.")
    return redirect("warehouse:history")
