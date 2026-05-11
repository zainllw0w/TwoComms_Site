"""Фінансовий дашборд."""
from __future__ import annotations

import json

from django.shortcuts import render

from warehouse.permissions import warehouse_admin_required
from warehouse.services.finance import (
    frozen_value_by_category,
    frozen_value_by_print,
    movements_chart_data,
    total_frozen_value,
)


@warehouse_admin_required
def finance_dashboard(request):
    chart = movements_chart_data(days=30)
    context = {
        "total_frozen": total_frozen_value(),
        "by_category": frozen_value_by_category(),
        "by_print": frozen_value_by_print(),
        "chart_json": json.dumps(chart),
        "active_section": "finance",
    }
    return render(request, "warehouse/finance.html", context)
