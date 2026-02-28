"""Custom CSRF handling helpers."""

from django.http import HttpResponseRedirect
from django.views.csrf import csrf_failure as django_csrf_failure


_RECOVERABLE_ROOT_REASONS = (
    "csrf token missing",
    "csrf cookie not set",
    "referer checking failed - no referer",
)


def csrf_failure(request, reason=""):
    """
    Gracefully recover from noisy POST / requests (bots, stale browser resubmits).

    For real form endpoints we keep Django's default failure response.
    """
    reason_text = str(reason or "")
    reason_lc = reason_text.lower()

    if request.method == "POST" and request.path == "/":
        if any(marker in reason_lc for marker in _RECOVERABLE_ROOT_REASONS):
            response = HttpResponseRedirect("/")
            response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response["Pragma"] = "no-cache"
            return response

    return django_csrf_failure(request, reason=reason)

