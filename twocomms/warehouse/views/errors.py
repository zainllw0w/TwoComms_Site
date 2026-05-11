"""Custom error handlers для storage subdomain."""
from __future__ import annotations

from django.shortcuts import render


def handler404(request, exception=None):
    return render(request, "warehouse/404.html", status=404)


def handler500(request):
    return render(request, "warehouse/500.html", status=500)
