"""Review-related URL routes.

Wired into the project at ``/reviews/`` via ``twocomms/urls.py``.
"""

from __future__ import annotations

from django.urls import path

from . import views


app_name = "reviews"


urlpatterns = [
    path(
        "submit/<slug:product_slug>/",
        views.submit_review,
        name="submit",
    ),
    path(
        "vote/<int:review_id>/",
        views.vote_review,
        name="vote",
    ),
]
